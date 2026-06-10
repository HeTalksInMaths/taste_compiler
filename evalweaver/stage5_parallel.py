"""Parallel Stage 5: Generate evaluation pairs concurrently via Bedrock."""

import json
import time
import concurrent.futures

from evalweaver.artifacts import log, save
from evalweaver.stage_models import STAGE_5_HARD_GATES, STAGE_5_SOFT_TARGETS, check_soft_targets
from evalweaver.stage_eval import eval_stage_5


def build_single_pair_prompt(
    target_variable: str,
    causal_graph: dict,
    measurement_research: list,
    pair_index: int,
    causal_node_hint: str,
    source_policy: dict,
) -> tuple[str, str]:
    """Build a prompt that asks for exactly ONE evaluation pair testing a specific causal node."""
    system = (
        "You are generating a single evaluation text pair that tests slightly more vs slightly less "
        "of a target variable. Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    # Compact representations
    nodes_summary = json.dumps(
        [{"node_id": n["node_id"], "role": n.get("role", ""), "mechanism": n.get("mechanism", "")[:60]}
         for n in causal_graph.get("causal_nodes", [])],
        indent=None,
    )
    edges_summary = json.dumps(
        [{"from": e["from"], "to": e["to"]} for e in causal_graph.get("causal_edges", [])],
        indent=None,
    )
    # Only include measurement ideas for the target node
    relevant_measurement = [
        {"causal_node": m["causal_node"], "text_features": m["text_features"]}
        for m in measurement_research
        if m.get("causal_node") == causal_node_hint
    ]
    if not relevant_measurement:
        relevant_measurement = [
            {"causal_node": m["causal_node"], "text_features": m["text_features"]}
            for m in measurement_research[:3]
        ]
    measurement_json = json.dumps(relevant_measurement, indent=None)
    policy_json = json.dumps(source_policy, indent=None)

    user = f"""Generate ONE evaluation pair for target variable: {target_variable}
Pair index: P{pair_index:03d}
Focus on causal node: {causal_node_hint}

Causal nodes: {nodes_summary}
Causal edges: {edges_summary}
Relevant measurement research: {measurement_json}
Source policy: {policy_json}

REQUIREMENTS:
- Create an anchor (shared context), a positive text (slightly MORE {target_variable}), and a negative text (slightly LESS {target_variable})
- The pair should test the causal node "{causal_node_hint}" — the positive should be stronger on this dimension
- Control for length — positive and negative should have similar word counts (within 25%)
- Include a label_contract explaining why positive > negative
- Focus on subtle, clean contrasts (not adversarial tricks)
- Keep each variant under 80 words

Return JSON:
{{
  "pair_id": "P{pair_index:03d}",
  "source_id": "generated",
  "source_trace": "generated pair testing {causal_node_hint}",
  "anchor": "shared context text",
  "positive": "text with slightly MORE {target_variable}",
  "negative": "text with slightly LESS {target_variable}",
  "split": "train",
  "target_delta": "positive is stronger on {causal_node_hint}",
  "controlled_variables": ["length", "topic", "tone", "audience"],
  "causal_nodes_tested": ["{causal_node_hint}"],
  "causal_edges_tested": [],
  "measurement_ideas_tested": [],
  "causal_tensions_tested": [],
  "label_contract": "positive scores higher because...",
  "source_policy": "compliant",
  "policy_violations": []
}}"""
    return (system, user)


def generate_pairs_parallel(
    provider_factory,
    target_variable: str,
    causal_graph: dict,
    measurement_research: list,
    n_pairs: int = 15,
    max_workers: int = 5,
    source_policy: dict = None,
    heldout_count: int = 3,
    out_dir: str = None,
) -> dict:
    """
    Generate N pairs in parallel, each via a separate Bedrock call.

    Args:
        provider_factory: callable that returns a new BedrockClaudeProvider instance
        target_variable: the target variable
        causal_graph: Stage 2 output
        measurement_research: Stage 3 measurement_research list
        n_pairs: number of pairs to generate
        max_workers: max concurrent API calls
        source_policy: source policy config
        heldout_count: how many pairs to assign as heldout
        out_dir: directory to save artifacts

    Returns:
        dict conforming to Stage 5 output schema
    """
    source_policy = source_policy or {}
    log("stage5_parallel", f"Generating {n_pairs} pairs with {max_workers} parallel workers")

    # Assign causal nodes round-robin for diversity
    nodes = causal_graph.get("causal_nodes", [])
    node_ids = [n["node_id"] for n in nodes]
    node_assignments = [node_ids[i % len(node_ids)] for i in range(n_pairs)] if node_ids else ["general"] * n_pairs

    # Build all prompts
    prompts = []
    for i in range(n_pairs):
        system, user = build_single_pair_prompt(
            target_variable, causal_graph, measurement_research, i, node_assignments[i], source_policy
        )
        prompts.append((i, system, user, node_assignments[i]))

    # Execute in parallel
    results = []
    start_time = time.time()

    def _call_one(args):
        idx, system, user, node_hint = args
        provider = provider_factory()
        try:
            raw = provider._converse(system, user)
            parsed = provider._parse_json_response(raw)
            return {"idx": idx, "ok": True, "parsed": parsed, "node_hint": node_hint}
        except Exception as e:
            return {"idx": idx, "ok": False, "error": str(e), "node_hint": node_hint}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_call_one, p) for p in prompts]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    elapsed = time.time() - start_time
    results.sort(key=lambda r: r["idx"])

    # Collect successful pairs
    pairs = []
    failed_calls = []
    for r in results:
        if r["ok"]:
            pair = r["parsed"]
            if "pair_id" not in pair:
                pair["pair_id"] = f"P{r['idx']:03d}"
            pairs.append(pair)
        else:
            failed_calls.append({"idx": r["idx"], "error": r["error"], "node_hint": r["node_hint"]})

    log("stage5_parallel", f"Got {len(pairs)}/{n_pairs} pairs ({len(failed_calls)} failed) in {elapsed:.1f}s")

    # Assign splits: last heldout_count pairs as heldout
    n = len(pairs)
    heldout_start = max(0, n - heldout_count)
    for i, p in enumerate(pairs):
        p["split"] = "heldout" if i >= heldout_start else "train"

    output = {
        "target_variable": target_variable,
        "pairs": pairs,
    }

    # Compute eval signals
    stage2_nodes = causal_graph.get("causal_nodes", [])
    eval_result = eval_stage_5(output, STAGE_5_HARD_GATES, stage2_nodes)
    soft_misses = check_soft_targets(eval_result.signals, STAGE_5_SOFT_TARGETS)

    summary = {
        "target_variable": target_variable,
        "n_requested": n_pairs,
        "n_returned": len(pairs),
        "n_failed_calls": len(failed_calls),
        "elapsed_seconds": round(elapsed, 1),
        "max_workers": max_workers,
        "eval_signals": eval_result.signals,
        "hard_gate_passed": eval_result.passed,
        "hard_gate_failures": eval_result.failures,
        "soft_eval_misses": soft_misses,
        "failed_calls": failed_calls,
        "node_distribution": {},
    }

    # Compute node distribution
    for p in pairs:
        for node in p.get("causal_nodes_tested", []):
            summary["node_distribution"][node] = summary["node_distribution"].get(node, 0) + 1

    if out_dir:
        save("stage5_parallel_summary", summary, out_dir)
        save("stage5_parallel_pairs", output, out_dir)

    return output
