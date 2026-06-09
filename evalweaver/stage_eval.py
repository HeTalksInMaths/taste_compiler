"""Deterministic evaluation engines for Stages 1–4 reasoning pipeline."""

import re
from evalweaver.stage_models import EvalResult, check_pass_criteria
from evalweaver.runner import py_run_scorer


# ─────────────────────────────────────────────────────────────────────
# KEYWORD SETS
# ─────────────────────────────────────────────────────────────────────

MECHANISTIC_KEYWORDS = [
    "because", "leads to", "increases", "decreases", "mediates", "moderates",
    "causes", "drives", "reduces", "through", "by making", "as a result",
    "signals", "facilitates", "triggers", "enables", "undermines", "enhances",
    "diminishes", "amplifies", "weakens", "strengthens", "resulting in",
    "thereby", "which in turn", "is attributed to", "is misattributed",
    "functions as", "acts as", "serves as",
]

VAGUE_ADVICE_WORDS = [
    "clear", "good", "engaging", "effective", "strong", "better", "important", "high quality",
]

INTERACTION_PATTERNS = ["*", "min(", "max(", "if ", "penalty", "gate", "threshold", "ratio", "density"]

NORMALIZATION_PATTERNS = [
    "len(text", "len(sentences", "len(clauses", "num_sentences", "num_clauses",
    "word_count", "token_count", "/ len(", "/ num_", "sentence_count",
]

FUNCTIONAL_FORMS = [
    "additive", "interaction", "gated", "penalty", "tension_balance",
    "causal_path", "ratio_or_density", "threshold",
]


# ─────────────────────────────────────────────────────────────────────
# STAGE 1 EVAL
# ─────────────────────────────────────────────────────────────────────


def eval_stage_1(parsed_json: dict, pass_criteria: dict) -> EvalResult:
    """Evaluate Stage 1 (Causal Research Search) output."""
    items = parsed_json.get("causal_research", [])
    tensions = parsed_json.get("research_tensions", [])

    num_research_items = len(items)
    num_unique_causal_variables = len(set(it.get("causal_variable", "") for it in items if it.get("causal_variable")))

    # mechanism_completeness_rate
    required_fields = ["claim", "causal_variable", "effect_direction", "mechanism", "source_id"]
    complete_count = sum(1 for it in items if all(it.get(f) for f in required_fields))
    mechanism_completeness_rate = complete_count / max(len(items), 1)

    # source_trace_rate
    source_traced = sum(1 for it in items if it.get("source_id"))
    source_trace_rate = source_traced / max(len(items), 1)

    # effect_direction_coverage
    directions = {"increases": 0, "decreases": 0, "mediates": 0, "moderates": 0}
    for it in items:
        d = it.get("effect_direction", "")
        if d in directions:
            directions[d] += 1

    # causal_specificity_score
    causal_specificity_score = _compute_causal_specificity(items)

    # generic_advice_penalty
    generic_advice_penalty = _compute_generic_penalty(items)

    # tension_count
    valid_tensions = [t for t in tensions if t.get("claim") and isinstance(t.get("variables"), list) and len(t.get("variables", [])) >= 2]
    tension_count = len(valid_tensions)

    signals = {
        "num_research_items": num_research_items,
        "num_unique_causal_variables": num_unique_causal_variables,
        "mechanism_completeness_rate": mechanism_completeness_rate,
        "source_trace_rate": source_trace_rate,
        "effect_direction_coverage": directions,
        "causal_specificity_score": causal_specificity_score,
        "generic_advice_penalty": generic_advice_penalty,
        "tension_count": tension_count,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)


def _compute_causal_specificity(items: list) -> float:
    """Reward claims with mechanistic language."""
    if not items:
        return 0.0
    score_sum = 0.0
    for it in items:
        claim = (it.get("claim", "") + " " + it.get("mechanism", "")).lower()
        has_keyword = any(kw in claim for kw in MECHANISTIC_KEYWORDS)
        score_sum += 1.0 if has_keyword else 0.0
    return score_sum / len(items)


def _compute_generic_penalty(items: list) -> float:
    """Penalize vague advice words when no mechanism is present."""
    if not items:
        return 0.0
    penalty_count = 0
    for it in items:
        mechanism = it.get("mechanism", "").strip()
        if mechanism:
            continue  # has mechanism, no penalty
        claim = it.get("claim", "").lower()
        if any(w in claim for w in VAGUE_ADVICE_WORDS):
            penalty_count += 1
    return penalty_count / len(items)


# ─────────────────────────────────────────────────────────────────────
# STAGE 2 EVAL
# ─────────────────────────────────────────────────────────────────────


def eval_stage_2(parsed_json: dict, pass_criteria: dict) -> EvalResult:
    """Evaluate Stage 2 (Causal Graph Generation) output."""
    nodes = parsed_json.get("causal_nodes", [])
    edges = parsed_json.get("causal_edges", [])
    tensions = parsed_json.get("causal_tensions", [])
    summary = parsed_json.get("summary_theory", "")

    num_nodes = len(nodes)
    num_edges = len(edges)

    # node_mechanism_rate
    nodes_with_mechanism = sum(1 for n in nodes if n.get("mechanism"))
    node_mechanism_rate = nodes_with_mechanism / max(num_nodes, 1)

    # node_evidence_rate
    nodes_with_evidence = sum(1 for n in nodes if n.get("evidence") and len(n["evidence"]) > 0)
    node_evidence_rate = nodes_with_evidence / max(num_nodes, 1)

    # edge_validity_rate
    node_ids = set(n.get("node_id", "") for n in nodes)
    # Include target_variable as a valid edge target (edges naturally terminate at the outcome)
    target_var = parsed_json.get("target_variable", "")
    valid_edge_targets = node_ids | {target_var} if target_var else node_ids
    valid_edges = sum(1 for e in edges if e.get("from") in node_ids and e.get("to") in valid_edge_targets)
    edge_validity_rate = valid_edges / max(num_edges, 1)

    # edge_explanation_rate
    edges_with_claim = sum(1 for e in edges if e.get("claim"))
    edge_explanation_rate = edges_with_claim / max(num_edges, 1)

    # graph_connectedness_score
    connected_nodes = set()
    for e in edges:
        if e.get("from"):
            connected_nodes.add(e["from"])
        if e.get("to"):
            connected_nodes.add(e["to"])
    participating = len(connected_nodes & node_ids)
    graph_connectedness_score = participating / max(num_nodes, 1)

    # role_diversity_score
    roles = set(n.get("role", "") for n in nodes if n.get("role") in {"increases", "decreases", "mediates", "moderates"})
    role_diversity_score = len(roles)

    # tension_count
    valid_tensions = [t for t in tensions if t.get("claim") and isinstance(t.get("nodes"), list) and len(t.get("nodes", [])) >= 2]
    tension_count = len(valid_tensions)

    # summary_uses_graph_terms
    summary_lower = summary.lower()
    graph_terms = [n.get("node_id", "").lower() for n in nodes if n.get("node_id")]
    summary_uses_graph_terms = any(term in summary_lower for term in graph_terms) if graph_terms else False

    signals = {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "node_mechanism_rate": node_mechanism_rate,
        "node_evidence_rate": node_evidence_rate,
        "edge_validity_rate": edge_validity_rate,
        "edge_explanation_rate": edge_explanation_rate,
        "graph_connectedness_score": graph_connectedness_score,
        "role_diversity_score": role_diversity_score,
        "tension_count": tension_count,
        "summary_uses_graph_terms": summary_uses_graph_terms,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)


# ─────────────────────────────────────────────────────────────────────
# STAGE 3 EVAL
# ─────────────────────────────────────────────────────────────────────


def eval_stage_3(parsed_json: dict, pass_criteria: dict, stage2_nodes: list) -> EvalResult:
    """Evaluate Stage 3 (Measurement Research Search) output."""
    items = parsed_json.get("measurement_research", [])
    node_ids = set(n.get("node_id", "") for n in stage2_nodes)

    num_measurement_items = len(items)

    # node_measurement_coverage
    covered_nodes = set(it.get("causal_node", "") for it in items if it.get("causal_node") in node_ids)
    node_measurement_coverage = len(covered_nodes) / max(len(node_ids), 1)

    # node_reference_validity_rate
    valid_refs = sum(1 for it in items if it.get("causal_node") in node_ids)
    node_reference_validity_rate = valid_refs / max(num_measurement_items, 1)

    # text_feature_specificity_score
    text_feature_specificity_score = _compute_text_feature_specificity(items)

    # implementation_actionability_score
    implementation_actionability_score = _compute_implementation_actionability(items)

    # generic_metric_penalty
    generic_metric_penalty = _compute_generic_metric_penalty(items)

    # multi_measurement_rate
    node_item_counts = {}
    for it in items:
        cn = it.get("causal_node", "")
        if cn in node_ids:
            node_item_counts[cn] = node_item_counts.get(cn, 0) + 1
    multi_measured = sum(1 for c in node_item_counts.values() if c >= 2)
    multi_measurement_rate = multi_measured / max(len(covered_nodes), 1) if covered_nodes else 0.0

    signals = {
        "node_measurement_coverage": node_measurement_coverage,
        "num_measurement_items": num_measurement_items,
        "text_feature_specificity_score": text_feature_specificity_score,
        "implementation_actionability_score": implementation_actionability_score,
        "generic_metric_penalty": generic_metric_penalty,
        "multi_measurement_rate": multi_measurement_rate,
        "node_reference_validity_rate": node_reference_validity_rate,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)


def _compute_text_feature_specificity(items: list) -> float:
    """Score how specific text features are (penalize generic terms)."""
    generic_terms = {"sentiment", "readability", "keywords", "tone", "style", "quality", "coherence"}
    if not items:
        return 0.0
    score_sum = 0.0
    for it in items:
        features = it.get("text_features", [])
        if not features:
            continue
        specific_count = sum(1 for f in features if f.lower() not in generic_terms and len(f) > 3)
        score_sum += specific_count / max(len(features), 1)
    return score_sum / len(items)


def _compute_implementation_actionability(items: list) -> float:
    """Score how actionable implementation ideas are."""
    action_keywords = ["count", "measure", "detect", "extract", "compute", "calculate", "ratio", "density", "frequency", "regex", "pattern", "parse", "split", "tokenize"]
    if not items:
        return 0.0
    score_sum = 0.0
    for it in items:
        ideas = it.get("implementation_ideas", [])
        if not ideas:
            continue
        actionable = sum(1 for idea in ideas if any(kw in idea.lower() for kw in action_keywords))
        score_sum += actionable / max(len(ideas), 1)
    return score_sum / len(items)


def _compute_generic_metric_penalty(items: list) -> float:
    """Penalize generic metric references without specifics."""
    generic_metrics = ["sentiment", "readability", "flesch", "keyword density", "word count only"]
    if not items:
        return 0.0
    penalty_count = 0
    for it in items:
        claim = it.get("measurement_claim", "").lower()
        features = " ".join(it.get("text_features", [])).lower()
        combined = claim + " " + features
        if any(g in combined for g in generic_metrics) and len(it.get("implementation_ideas", [])) < 2:
            penalty_count += 1
    return penalty_count / len(items)


# ─────────────────────────────────────────────────────────────────────
# STAGE 4 EVAL
# ─────────────────────────────────────────────────────────────────────


def eval_stage_4(parsed_json: dict, pass_criteria: dict, stage2_nodes: list, smoke_texts: list, anchor: str) -> EvalResult:
    """Evaluate Stage 4 (Scorer Hypothesis and Function Generation) output."""
    scorers = parsed_json.get("scorers", [])
    node_ids = set(n.get("node_id", "") for n in stage2_nodes)
    num_scorers = len(scorers)

    # hypothesis_completeness_rate
    completeness_fields = ["hypothesis", "causal_nodes_used", "measurement_ideas_used", "functional_form", "functional_form_rationale", "expected_failure_mode", "code"]
    complete_count = sum(1 for s in scorers if all(s.get(f) for f in completeness_fields))
    hypothesis_completeness_rate = complete_count / max(num_scorers, 1)

    # causal_node_validity_rate
    all_refs = []
    for s in scorers:
        all_refs.extend(s.get("causal_nodes_used", []))
    valid_refs = sum(1 for r in all_refs if r in node_ids)
    causal_node_validity_rate = valid_refs / max(len(all_refs), 1) if all_refs else 0.0

    # measurement_reference_rate
    scorers_with_measurement = sum(1 for s in scorers if s.get("measurement_ideas_used") and len(s["measurement_ideas_used"]) > 0)
    measurement_reference_rate = scorers_with_measurement / max(num_scorers, 1)

    # functional_form_diversity
    forms = set(s.get("functional_form", "").lower() for s in scorers if s.get("functional_form"))
    functional_form_diversity = len(forms)

    # interaction_usage_rate
    interaction_count = 0
    for s in scorers:
        code = s.get("code", "")
        if any(pat in code for pat in INTERACTION_PATTERNS):
            interaction_count += 1
    interaction_usage_rate = interaction_count / max(num_scorers, 1)

    # normalization_usage_rate
    norm_count = 0
    for s in scorers:
        code = s.get("code", "")
        if any(pat in code for pat in NORMALIZATION_PATTERNS):
            norm_count += 1
    normalization_usage_rate = norm_count / max(num_scorers, 1)

    # code_exec_rate, numeric_return_rate, nonconstant_behavior_rate
    code_exec_rate, numeric_return_rate, nonconstant_behavior_rate = _eval_scorer_code(scorers, smoke_texts, anchor)

    # scorer_distinctness_score
    tuples_seen = set()
    for s in scorers:
        key = (
            s.get("functional_form", ""),
            frozenset(s.get("causal_nodes_used", [])),
            frozenset(s.get("measurement_ideas_used", [])),
        )
        tuples_seen.add(key)
    scorer_distinctness_score = len(tuples_seen) / max(num_scorers, 1)

    # hypothesis_code_alignment_score
    hypothesis_code_alignment_score = _compute_alignment(scorers)

    signals = {
        "num_scorers": num_scorers,
        "hypothesis_completeness_rate": hypothesis_completeness_rate,
        "causal_node_validity_rate": causal_node_validity_rate,
        "measurement_reference_rate": measurement_reference_rate,
        "functional_form_diversity": functional_form_diversity,
        "interaction_usage_rate": interaction_usage_rate,
        "normalization_usage_rate": normalization_usage_rate,
        "code_exec_rate": code_exec_rate,
        "numeric_return_rate": numeric_return_rate,
        "nonconstant_behavior_rate": nonconstant_behavior_rate,
        "scorer_distinctness_score": scorer_distinctness_score,
        "hypothesis_code_alignment_score": hypothesis_code_alignment_score,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)


def _eval_scorer_code(scorers: list, smoke_texts: list, anchor: str) -> tuple[float, float, float]:
    """Run scorer code on smoke texts. Returns (code_exec_rate, numeric_return_rate, nonconstant_rate)."""
    if not scorers:
        return (0.0, 0.0, 0.0)

    exec_pass = 0
    numeric_pass = 0
    nonconstant_pass = 0

    for s in scorers:
        code = s.get("code", "")
        if not code:
            continue

        results = []
        all_ok = True
        all_numeric = True

        for text in smoke_texts:
            r = py_run_scorer(code, text, anchor)
            if not r["ok"]:
                all_ok = False
                all_numeric = False
                break
            if r["raw_value"] is None:
                all_numeric = False
            else:
                results.append(r["raw_value"])

        if all_ok:
            exec_pass += 1
        if all_ok and all_numeric:
            numeric_pass += 1
        if len(results) >= 2 and len(set(round(v, 10) for v in results)) >= 2:
            nonconstant_pass += 1

    n = len(scorers)
    return (exec_pass / n, numeric_pass / n, nonconstant_pass / n)


def _compute_alignment(scorers: list) -> float:
    """Approximate overlap between hypothesis fields and code variable names."""
    if not scorers:
        return 0.0
    score_sum = 0.0
    for s in scorers:
        nodes = s.get("causal_nodes_used", [])
        ideas = s.get("measurement_ideas_used", [])
        code = s.get("code", "").lower()
        # Build terms from nodes + measurement ideas
        terms = []
        for n in nodes:
            terms.extend(n.lower().replace("_", " ").split())
        for idea in ideas:
            terms.extend(idea.lower().replace("_", " ").split())
        # Filter short/common terms
        terms = [t for t in terms if len(t) > 3]
        if not terms:
            continue
        matches = sum(1 for t in terms if t in code)
        score_sum += matches / len(terms)
    return score_sum / len(scorers)
