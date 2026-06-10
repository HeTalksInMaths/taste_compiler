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


# ─────────────────────────────────────────────────────────────────────
# STAGE 5 EVAL
# ─────────────────────────────────────────────────────────────────────

_STAGE_5_REQUIRED_FIELDS = ["pair_id", "anchor", "positive", "negative", "split", "target_delta", "controlled_variables"]


def _simple_text_similarity(a: str, b: str) -> float:
    """Compute simple word-overlap Jaccard similarity between two texts."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def eval_stage_5(parsed_json: dict, pass_criteria: dict, stage2_nodes: list, max_words: int = 80) -> EvalResult:
    """Evaluate Stage 5 (Evaluation Pair Generation) output."""
    pairs = parsed_json.get("pairs", [])
    node_ids = set(n.get("node_id", "") for n in stage2_nodes)

    num_pairs = len(pairs)
    heldout_count = sum(1 for p in pairs if p.get("split") == "heldout")

    # pair_schema_completeness_rate
    complete_count = sum(
        1 for p in pairs
        if all(p.get(f) not in (None, "", []) for f in _STAGE_5_REQUIRED_FIELDS)
    )
    pair_schema_completeness_rate = complete_count / max(num_pairs, 1)

    # source_trace_rate
    source_traced = sum(1 for p in pairs if p.get("source_trace") or p.get("source_id"))
    source_trace_rate = source_traced / max(num_pairs, 1)

    # causal_node_reference_validity_rate
    valid_ref_count = 0
    for p in pairs:
        nodes_tested = p.get("causal_nodes_tested", [])
        if nodes_tested and all(n in node_ids for n in nodes_tested):
            valid_ref_count += 1
        elif not nodes_tested:
            # Empty causal_nodes_tested doesn't count as valid
            pass
    causal_node_reference_validity_rate = valid_ref_count / max(num_pairs, 1)

    # length_balance_rate
    balanced_count = 0
    for p in pairs:
        pos = p.get("positive", "")
        neg = p.get("negative", "")
        pos_words = len(pos.split())
        neg_words = len(neg.split())
        if abs(pos_words - neg_words) <= max_words * 0.3:
            balanced_count += 1
    length_balance_rate = balanced_count / max(num_pairs, 1)

    # minimal_contrast_rate
    minimal_count = 0
    for p in pairs:
        nodes_tested = p.get("causal_nodes_tested", [])
        if len(nodes_tested) in (1, 2):
            minimal_count += 1
    minimal_contrast_rate = minimal_count / max(num_pairs, 1)

    # target_direction_clarity_rate
    clarity_count = sum(1 for p in pairs if p.get("label_contract"))
    target_direction_clarity_rate = clarity_count / max(num_pairs, 1)

    # controlled_variable_pass_rate
    controlled_count = sum(1 for p in pairs if p.get("controlled_variables") and len(p["controlled_variables"]) > 0)
    controlled_variable_pass_rate = controlled_count / max(num_pairs, 1)

    # positive_policy_pass_rate
    policy_pass_count = sum(1 for p in pairs if not p.get("policy_violations") or len(p["policy_violations"]) == 0)
    positive_policy_pass_rate = policy_pass_count / max(num_pairs, 1)

    # near_duplicate_pair_rate
    anchors = [p.get("anchor", "") for p in pairs]
    duplicate_count = 0
    for i in range(len(anchors)):
        for j in range(i + 1, len(anchors)):
            if _simple_text_similarity(anchors[i], anchors[j]) > 0.8:
                duplicate_count += 1
                break  # count each pair only once
    near_duplicate_pair_rate = duplicate_count / max(num_pairs, 1)

    # heldout_leakage_risk: always 0.0 (checked at orchestrator level)
    heldout_leakage_risk = 0.0

    signals = {
        "num_pairs": num_pairs,
        "heldout_count": heldout_count,
        "pair_schema_completeness_rate": pair_schema_completeness_rate,
        "source_trace_rate": source_trace_rate,
        "causal_node_reference_validity_rate": causal_node_reference_validity_rate,
        "length_balance_rate": length_balance_rate,
        "minimal_contrast_rate": minimal_contrast_rate,
        "target_direction_clarity_rate": target_direction_clarity_rate,
        "controlled_variable_pass_rate": controlled_variable_pass_rate,
        "positive_policy_pass_rate": positive_policy_pass_rate,
        "near_duplicate_pair_rate": near_duplicate_pair_rate,
        "heldout_leakage_risk": heldout_leakage_risk,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)


# ─────────────────────────────────────────────────────────────────────
# STAGE 6 EVAL
# ─────────────────────────────────────────────────────────────────────


def eval_stage_6(scorer_summaries: list, pareto_frontier: list, eval_rows: dict, pass_criteria: dict) -> EvalResult:
    """Evaluate Stage 6 (Scorer Evaluation) output quality."""
    num_scorers_evaluated = len(scorer_summaries)

    # execution_valid_rate: fraction of scorers with exec_error_rate == 0
    exec_valid_count = sum(1 for s in scorer_summaries if s.get("exec_error_rate", 1) == 0)
    execution_valid_rate = exec_valid_count / max(num_scorers_evaluated, 1)

    # numeric_return_rate: fraction of scorers that returned numeric values (no exec errors)
    numeric_count = sum(1 for s in scorer_summaries if s.get("exec_error_rate", 1) == 0)
    numeric_return_rate = numeric_count / max(num_scorers_evaluated, 1)

    # nonconstant_scorer_rate: fraction with nonconstant_rate > 0
    nonconstant_count = sum(1 for s in scorer_summaries if s.get("nonconstant_rate", 0) > 0)
    nonconstant_scorer_rate = nonconstant_count / max(num_scorers_evaluated, 1)

    # score_range_valid_rate: fraction where score_spread > 0
    range_valid_count = sum(1 for s in scorer_summaries if s.get("score_spread", 0) > 0)
    score_range_valid_rate = range_valid_count / max(num_scorers_evaluated, 1)

    # train_accuracy_presence_rate: fraction with defined train_accuracy
    train_acc_count = sum(1 for s in scorer_summaries if s.get("train_accuracy") is not None)
    train_accuracy_presence_rate = train_acc_count / max(num_scorers_evaluated, 1)

    # heldout_accuracy_presence_rate: fraction with defined heldout_accuracy
    heldout_acc_count = sum(1 for s in scorer_summaries if s.get("heldout_accuracy") is not None)
    heldout_accuracy_presence_rate = heldout_acc_count / max(num_scorers_evaluated, 1)

    # train_gap_presence_rate: fraction with defined train_mean_gap
    train_gap_count = sum(1 for s in scorer_summaries if s.get("train_mean_gap") is not None)
    train_gap_presence_rate = train_gap_count / max(num_scorers_evaluated, 1)

    # heldout_gap_presence_rate: fraction with defined heldout_mean_gap
    heldout_gap_count = sum(1 for s in scorer_summaries if s.get("heldout_mean_gap") is not None)
    heldout_gap_presence_rate = heldout_gap_count / max(num_scorers_evaluated, 1)

    # eligible_scorer_count
    eligible_scorer_count = sum(1 for s in scorer_summaries if s.get("eligible", False))

    # pareto_count
    pareto_count = len(pareto_frontier)

    # overfit_warning_count
    overfit_warning_count = sum(
        1 for s in scorer_summaries
        if (s.get("train_accuracy") or 0) > (s.get("heldout_accuracy") or 0) + 0.2
    )

    signals = {
        "num_scorers_evaluated": num_scorers_evaluated,
        "execution_valid_rate": execution_valid_rate,
        "numeric_return_rate": numeric_return_rate,
        "nonconstant_scorer_rate": nonconstant_scorer_rate,
        "score_range_valid_rate": score_range_valid_rate,
        "train_accuracy_presence_rate": train_accuracy_presence_rate,
        "heldout_accuracy_presence_rate": heldout_accuracy_presence_rate,
        "train_gap_presence_rate": train_gap_presence_rate,
        "heldout_gap_presence_rate": heldout_gap_presence_rate,
        "eligible_scorer_count": eligible_scorer_count,
        "pareto_count": pareto_count,
        "overfit_warning_count": overfit_warning_count,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)


# ─────────────────────────────────────────────────────────────────────
# STAGE 7 EVAL
# ─────────────────────────────────────────────────────────────────────

_ACTION_VERBS = ["add", "remove", "replace", "combine", "split", "increase", "decrease", "weight", "gate", "normalize", "multiply"]


def eval_stage_7(parsed_json: dict, pass_criteria: dict, heldout_pairs: list) -> EvalResult:
    """Evaluate Stage 7 (Failure Packet) output."""
    failure_patterns = parsed_json.get("failure_patterns", [])
    mutation_instructions = parsed_json.get("mutation_instructions", [])

    # failure_pattern_count
    failure_pattern_count = len(failure_patterns)

    # heldout_raw_text_leakage_count: scan raw_response (full parsed_json as text) for heldout text
    raw_text = str(parsed_json)  # serialize to check for leakage
    heldout_raw_text_leakage_count = 0
    for p in heldout_pairs:
        pos = p.get("positive", "")
        neg = p.get("negative", "")
        # Only check if the text is non-trivial (at least 10 chars to avoid false positives)
        if pos and len(pos) >= 10 and pos in raw_text:
            heldout_raw_text_leakage_count += 1
        if neg and len(neg) >= 10 and neg in raw_text:
            heldout_raw_text_leakage_count += 1

    # top_scorer_coverage_rate: fraction of pareto scorers referenced in top_scorers
    failure_packet = parsed_json.get("failure_packet", {})
    top_scorers = failure_packet.get("top_scorers", [])
    top_scorer_ids = set(s.get("scorer_id", "") for s in top_scorers)
    # We treat this as coverage of pareto scorers; if no pareto info, use top_scorers presence
    pareto_scorer_ids = set()
    heldout_agg = parsed_json.get("heldout_aggregate_only", {})
    if heldout_agg:
        pareto_scorer_ids = set(heldout_agg.get("heldout_accuracy_by_scorer", {}).keys())
    if pareto_scorer_ids:
        covered = len(top_scorer_ids & pareto_scorer_ids)
        top_scorer_coverage_rate = covered / max(len(pareto_scorer_ids), 1)
    else:
        top_scorer_coverage_rate = 1.0 if top_scorers else 0.0

    # visible_failure_reference_rate: fraction of patterns referencing at least one visible_pair_id
    visible_ref_count = sum(
        1 for fp in failure_patterns
        if fp.get("visible_pair_ids") and len(fp["visible_pair_ids"]) > 0
    )
    visible_failure_reference_rate = visible_ref_count / max(failure_pattern_count, 1)

    # mutation_actionability_score: fraction of instructions containing action verbs
    actionable_count = 0
    for inst in mutation_instructions:
        text = inst.get("instruction", "").lower()
        if any(verb in text for verb in _ACTION_VERBS):
            actionable_count += 1
    mutation_actionability_score = actionable_count / max(len(mutation_instructions), 1)

    # failure_pattern_specificity_score: patterns with non-empty scorer_ids AND visible_pair_ids AND causal_nodes_implicated AND reasoning_error
    specific_count = 0
    for fp in failure_patterns:
        has_scorers = fp.get("scorer_ids") and len(fp["scorer_ids"]) > 0
        has_pairs = fp.get("visible_pair_ids") and len(fp["visible_pair_ids"]) > 0
        has_nodes = fp.get("causal_nodes_implicated") and len(fp["causal_nodes_implicated"]) > 0
        has_error = bool(fp.get("reasoning_error"))
        if has_scorers and has_pairs and has_nodes and has_error:
            specific_count += 1
    failure_pattern_specificity_score = specific_count / max(failure_pattern_count, 1)

    # causal_reference_rate: fraction of patterns/instructions referencing causal nodes
    all_items = list(failure_patterns) + list(mutation_instructions)
    causal_ref_count = 0
    for item in all_items:
        # Check if the item references causal nodes
        if item.get("causal_nodes_implicated") and len(item["causal_nodes_implicated"]) > 0:
            causal_ref_count += 1
        elif item.get("targets_failure_patterns"):
            # Check if instruction text mentions causal-related terms
            text = item.get("instruction", "").lower()
            if any(term in text for term in ["causal", "node", "mechanism"]):
                causal_ref_count += 1
    causal_reference_rate = causal_ref_count / max(len(all_items), 1)

    signals = {
        "failure_pattern_count": failure_pattern_count,
        "heldout_raw_text_leakage_count": heldout_raw_text_leakage_count,
        "top_scorer_coverage_rate": top_scorer_coverage_rate,
        "visible_failure_reference_rate": visible_failure_reference_rate,
        "mutation_actionability_score": mutation_actionability_score,
        "failure_pattern_specificity_score": failure_pattern_specificity_score,
        "causal_reference_rate": causal_reference_rate,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)


# ─────────────────────────────────────────────────────────────────────
# STAGE 8 EVAL
# ─────────────────────────────────────────────────────────────────────

_UNSAFE_PATTERNS = [r'\bimport\b', r'open\(', r'exec\(', r'eval\(', r'\brequests\b', r'\burllib\b', r'\bsocket\b']


def eval_stage_8(parsed_json: dict, pass_criteria: dict, stage2_nodes: list, stage7_patterns: list, smoke_texts: list, anchor: str) -> EvalResult:
    """Evaluate Stage 8 (Repair Scorer Generation) output."""
    repair_scorers = parsed_json.get("repair_scorers", [])
    node_ids = set(n.get("node_id", "") for n in stage2_nodes)
    pattern_ids = set(p.get("pattern_id", "") for p in stage7_patterns)

    num_repair_scorers = len(repair_scorers)

    # code_exec_rate: execute each via py_run_scorer on smoke_texts
    exec_pass = 0
    numeric_pass = 0
    nonconstant_pass = 0
    for s in repair_scorers:
        code = s.get("code", "")
        if not code:
            continue
        all_ok = True
        all_numeric = True
        results = []
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

    code_exec_rate = exec_pass / max(num_repair_scorers, 1)
    numeric_return_rate = numeric_pass / max(num_repair_scorers, 1)
    nonconstant_behavior_rate = nonconstant_pass / max(num_repair_scorers, 1)

    # failure_pattern_target_rate: fraction referencing valid stage7 pattern_ids
    pattern_target_count = 0
    for s in repair_scorers:
        targets = s.get("targets_failure_patterns", [])
        if targets and any(t in pattern_ids for t in targets):
            pattern_target_count += 1
    failure_pattern_target_rate = pattern_target_count / max(num_repair_scorers, 1)

    # causal_node_validity_rate: fraction of all referenced causal_nodes_used that exist in stage2 nodes
    all_causal_refs = []
    for s in repair_scorers:
        all_causal_refs.extend(s.get("causal_nodes_used", []))
    valid_causal = sum(1 for r in all_causal_refs if r in node_ids)
    causal_node_validity_rate = valid_causal / max(len(all_causal_refs), 1) if all_causal_refs else 0.0

    # measurement_reference_rate: fraction of scorers with non-empty measurement_ideas_used
    measurement_count = sum(1 for s in repair_scorers if s.get("measurement_ideas_used") and len(s["measurement_ideas_used"]) > 0)
    measurement_reference_rate = measurement_count / max(num_repair_scorers, 1)

    # lineage_completeness_rate: fraction with lineage AND parent_scorer_ids
    lineage_count = sum(1 for s in repair_scorers if s.get("lineage") and s.get("parent_scorer_ids") and len(s["parent_scorer_ids"]) > 0)
    lineage_completeness_rate = lineage_count / max(num_repair_scorers, 1)

    # functional_form_diversity: count unique functional_form values
    forms = set(s.get("functional_form", "").lower() for s in repair_scorers if s.get("functional_form"))
    functional_form_diversity = len(forms)

    # unsafe_code_penalty: fraction containing import/open(/exec(/eval(/requests/urllib/socket
    unsafe_count = 0
    for s in repair_scorers:
        code = s.get("code", "")
        if any(re.search(pat, code) for pat in _UNSAFE_PATTERNS):
            unsafe_count += 1
    unsafe_code_penalty = unsafe_count / max(num_repair_scorers, 1)

    # parent_distinctness_rate: fraction with different form or nodes than parent
    # Since we don't have parent data directly, check if scorer has different functional_form
    # or causal_nodes_used compared to what's in parent_scorer_ids (approximate by uniqueness)
    distinct_count = 0
    seen_combos = set()
    for s in repair_scorers:
        combo = (s.get("functional_form", ""), frozenset(s.get("causal_nodes_used", [])))
        if combo not in seen_combos:
            distinct_count += 1
        seen_combos.add(combo)
    parent_distinctness_rate = distinct_count / max(num_repair_scorers, 1)

    # code_feature_map_completeness_rate: fraction with non-empty code_feature_map
    feature_map_count = sum(1 for s in repair_scorers if s.get("code_feature_map") and len(s["code_feature_map"]) > 0)
    code_feature_map_completeness_rate = feature_map_count / max(num_repair_scorers, 1)

    # repair_strategy_specificity_score: fraction with non-empty repair_strategy containing action verbs
    strategy_count = 0
    for s in repair_scorers:
        strategy = s.get("repair_strategy", "").lower()
        if strategy and any(verb in strategy for verb in _ACTION_VERBS):
            strategy_count += 1
    repair_strategy_specificity_score = strategy_count / max(num_repair_scorers, 1)

    signals = {
        "num_repair_scorers": num_repair_scorers,
        "code_exec_rate": code_exec_rate,
        "numeric_return_rate": numeric_return_rate,
        "nonconstant_behavior_rate": nonconstant_behavior_rate,
        "failure_pattern_target_rate": failure_pattern_target_rate,
        "causal_node_validity_rate": causal_node_validity_rate,
        "measurement_reference_rate": measurement_reference_rate,
        "lineage_completeness_rate": lineage_completeness_rate,
        "functional_form_diversity": functional_form_diversity,
        "unsafe_code_penalty": unsafe_code_penalty,
        "parent_distinctness_rate": parent_distinctness_rate,
        "code_feature_map_completeness_rate": code_feature_map_completeness_rate,
        "repair_strategy_specificity_score": repair_strategy_specificity_score,
    }

    passed, failures = check_pass_criteria(signals, pass_criteria)
    return EvalResult(signals=signals, passed=passed, failures=failures)
