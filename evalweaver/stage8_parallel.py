"""Parallel Stage 8: Generate repair scorers concurrently via Bedrock."""

import json
import time
import concurrent.futures

from evalweaver.artifacts import log, save
from evalweaver.stage_models import STAGE_8_HARD_GATES, STAGE_8_SOFT_TARGETS, SMOKE_TEXTS, check_soft_targets
from evalweaver.stage_eval import eval_stage_8
from evalweaver.runner import py_run_scorer


FUNCTIONAL_FORMS = [
    "additive", "interaction", "gated", "penalty", "tension_balance",
    "ratio_or_density", "threshold", "multiplicative", "causal_path",
    "subtractive_penalty",
]


def build_single_repair_scorer_prompt(
    target_variable: str,
    causal_graph: dict,
    measurement_research: list,
    scorer_index: int,
    failure_packet: dict,
    parent_scorer: dict,
    functional_form_hint: str,
) -> tuple[str, str]:
    """Build a prompt that asks for exactly ONE repair scorer targeting a specific failure pattern."""
    system = (
        "You are generating a single repaired scorer function that addresses a specific failure pattern. "
        "Return ONLY valid JSON matching the specified schema. No markdown, no commentary."
    )

    # Compact graph
    nodes_summary = json.dumps(
        [{"node_id": n["node_id"], "role": n.get("role", ""), "mechanism": n.get("mechanism", "")[:60]}
         for n in causal_graph.get("causal_nodes", [])],
        indent=None,
    )
    measurement_summary = json.dumps(
        [{"causal_node": m["causal_node"], "text_features": m["text_features"],
          "implementation_ideas": m["implementation_ideas"]}
         for m in measurement_research],
        indent=None,
    )

    # Failure patterns and mutation instructions
    patterns = failure_packet.get("failure_patterns", [])
    mutations = failure_packet.get("mutation_instructions", [])
    # Pick one pattern to target (round-robin by scorer_index)
    target_pattern = patterns[scorer_index % len(patterns)] if patterns else {}
    target_pattern_json = json.dumps(target_pattern, indent=None)
    mutations_json = json.dumps(mutations, indent=None)

    # Parent scorer context
    parent_json = json.dumps({
        "scorer_id": parent_scorer.get("scorer_id", ""),
        "hypothesis": parent_scorer.get("hypothesis", "")[:80],
        "functional_form": parent_scorer.get("functional_form", ""),
        "code": parent_scorer.get("code", ""),
    }, indent=None)

    user = f"""Generate ONE repair scorer for target variable: {target_variable}
Scorer index: RS{scorer_index}
Use functional form: {functional_form_hint}

Target failure pattern: {target_pattern_json}
All mutation instructions: {mutations_json}

Parent scorer to improve upon: {parent_json}

Causal nodes: {nodes_summary}
Measurement research: {measurement_summary}

REQUIREMENTS:
- Address the target failure pattern with a concrete repair strategy
- Write executable Python code with signature: def scorer(text, anchor, params): ... return score
- Score must be 0.0 to 1.0 (higher = more {target_variable})
- MUST analyze actual text content (re.findall, word counts, pattern matching)
- MUST produce DIFFERENT scores for these test texts:
  1. "This works because it gives teams a concrete way to test ideas before committing."
  2. "This is the best and most revolutionary solution ever made."
  3. "The tool helps users compare options, see tradeoffs, and choose a next step."
  4. "Maybe it helps in some cases, but the limits are unclear."
- Available imports: re, math, collections, string, statistics, unicodedata
- Use a DIFFERENT approach than the parent scorer
- Reference specific causal nodes and measurement ideas

Return JSON:
{{
  "scorer_id": "RS{scorer_index}",
  "lineage": "repair_round_1",
  "parent_scorer_ids": ["{parent_scorer.get('scorer_id', 'S0')}"],
  "targets_failure_patterns": ["{target_pattern.get('pattern_id', 'FP001')}"],
  "hypothesis": "...",
  "causal_nodes_used": ["node1", "node2"],
  "measurement_ideas_used": ["idea1"],
  "functional_form": "{functional_form_hint}",
  "repair_strategy": "addresses the failure by...",
  "expected_failure_mode": "...",
  "code_feature_map": {{"feature": "how it maps to code"}},
  "code": "def scorer(text, anchor, params):\\n    ...\\n    return score"
}}"""
    return (system, user)


def generate_repair_scorers_parallel(
    provider_factory,
    target_variable: str,
    causal_graph: dict,
    measurement_research: list,
    prior_scorers: list,
    failure_packet: dict,
    n_scorers: int = 10,
    max_workers: int = 5,
    anchor: str = "",
    out_dir: str = None,
) -> dict:
    """
    Generate N repair scorers in parallel, each via a separate Bedrock call.

    Args:
        provider_factory: callable that returns a new BedrockClaudeProvider instance
        target_variable: the target variable
        causal_graph: Stage 2 output
        measurement_research: Stage 3 measurement_research list
        prior_scorers: scorers from Stage 4 (parents)
        failure_packet: Stage 7 failure packet output
        n_scorers: number of repair scorers to generate
        max_workers: max concurrent API calls
        anchor: the raw_text anchor for smoke testing
        out_dir: directory to save artifacts

    Returns:
        dict conforming to Stage 8 output schema
    """
    log("stage8_parallel", f"Generating {n_scorers} repair scorers with {max_workers} parallel workers")

    # Assign functional forms round-robin for diversity
    form_assignments = [FUNCTIONAL_FORMS[i % len(FUNCTIONAL_FORMS)] for i in range(n_scorers)]

    # Assign parent scorers round-robin
    parent_assignments = [prior_scorers[i % len(prior_scorers)] if prior_scorers else {} for i in range(n_scorers)]

    # Build all prompts
    prompts = []
    for i in range(n_scorers):
        system, user = build_single_repair_scorer_prompt(
            target_variable, causal_graph, measurement_research,
            i, failure_packet, parent_assignments[i], form_assignments[i]
        )
        prompts.append((i, system, user, form_assignments[i]))

    # Execute in parallel
    results = []
    start_time = time.time()

    def _call_one(args):
        idx, system, user, form = args
        provider = provider_factory()
        try:
            raw = provider._converse(system, user)
            parsed = provider._parse_json_response(raw)
            return {"idx": idx, "ok": True, "parsed": parsed, "form": form}
        except Exception as e:
            return {"idx": idx, "ok": False, "error": str(e), "form": form}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_call_one, p) for p in prompts]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    elapsed = time.time() - start_time
    results.sort(key=lambda r: r["idx"])

    # Collect successful scorers
    repair_scorers = []
    failed_calls = []
    for r in results:
        if r["ok"]:
            scorer = r["parsed"]
            if "scorer_id" not in scorer:
                scorer["scorer_id"] = f"RS{r['idx']}"
            repair_scorers.append(scorer)
        else:
            failed_calls.append({"idx": r["idx"], "error": r["error"], "form": r["form"]})

    log("stage8_parallel", f"Got {len(repair_scorers)}/{n_scorers} scorers ({len(failed_calls)} failed) in {elapsed:.1f}s")

    # Smoke-test each repair scorer
    working_scorers = []
    broken_scorers = []
    for s in repair_scorers:
        code = s.get("code", "")
        if not code:
            broken_scorers.append({**s, "failure_reason": "no code"})
            continue

        smoke_results = []
        all_ok = True
        for text in SMOKE_TEXTS:
            r = py_run_scorer(code, text, anchor)
            if not r["ok"]:
                all_ok = False
                break
            smoke_results.append(r["raw_value"])

        if not all_ok:
            broken_scorers.append({**s, "failure_reason": "execution error"})
        elif len(set(smoke_results)) <= 1:
            broken_scorers.append({**s, "failure_reason": "constant output", "smoke_values": smoke_results})
        else:
            s["smoke_values"] = smoke_results
            working_scorers.append(s)

    log("stage8_parallel", f"Working: {len(working_scorers)}, Broken: {len(broken_scorers)}")
    for ws in working_scorers:
        log("stage8_parallel", f"  ✓ {ws['scorer_id']} [{ws.get('functional_form','')}]")
    for bs in broken_scorers:
        log("stage8_parallel", f"  ✗ {bs['scorer_id']} [{bs.get('functional_form','')}]: {bs['failure_reason']}")

    output = {
        "target_variable": target_variable,
        "repair_scorers": repair_scorers,  # all scorers (eval will re-validate)
    }

    # Compute eval signals
    stage2_nodes = causal_graph.get("causal_nodes", [])
    stage7_patterns = failure_packet.get("failure_patterns", [])
    eval_result = eval_stage_8(output, STAGE_8_HARD_GATES, stage2_nodes, stage7_patterns, SMOKE_TEXTS, anchor)
    soft_misses = check_soft_targets(eval_result.signals, STAGE_8_SOFT_TARGETS)

    summary = {
        "target_variable": target_variable,
        "n_requested": n_scorers,
        "n_returned": len(repair_scorers),
        "n_working": len(working_scorers),
        "n_broken": len(broken_scorers),
        "n_failed_calls": len(failed_calls),
        "elapsed_seconds": round(elapsed, 1),
        "max_workers": max_workers,
        "eval_signals": eval_result.signals,
        "hard_gate_passed": eval_result.passed,
        "hard_gate_failures": eval_result.failures,
        "soft_eval_misses": soft_misses,
        "working_scorers": working_scorers,
        "broken_scorers": broken_scorers,
        "failed_calls": failed_calls,
        "functional_form_distribution": {},
    }

    for s in working_scorers:
        form = s.get("functional_form", "unknown")
        summary["functional_form_distribution"][form] = summary["functional_form_distribution"].get(form, 0) + 1

    if out_dir:
        save("stage8_parallel_summary", summary, out_dir)
        save("stage8_parallel_working_scorers", working_scorers, out_dir)
        save("stage8_parallel_broken_scorers", broken_scorers, out_dir)

    return output
