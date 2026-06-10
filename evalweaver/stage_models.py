"""Data models, schema validation, and pass criteria for Stages 1–4 reasoning pipeline."""

from dataclasses import dataclass, field, asdict
from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────


@dataclass
class StageResult:
    """Result of executing a single stage (prompt → LLM → parse)."""
    stage_num: int
    stage_name: str
    prompt: dict  # {"system": str, "user": str}
    raw_response: str = ""
    parsed_json: Optional[dict] = None
    parse_error: Optional[str] = None
    call_meta: dict = field(default_factory=lambda: {
        "latency_ms": 0, "retry_mode": "standard", "max_attempts": 5, "error": None
    })

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvalResult:
    """Result of evaluating a stage's output against criteria."""
    signals: dict = field(default_factory=dict)
    passed: bool = False  # True if all HARD GATES pass (soft evals don't block)
    failures: list = field(default_factory=list)  # hard gate failures only
    soft_evals: list = field(default_factory=list)  # soft eval signals below target (tracked, not blocking)

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────
# SCHEMA VALIDATION
# ─────────────────────────────────────────────────────────────────────

_STAGE_1_ITEM_REQUIRED = ["source_id", "title", "claim", "causal_variable", "effect_direction", "mechanism", "evidence_strength"]
_STAGE_1_TENSION_REQUIRED = ["claim", "variables"]

_STAGE_2_NODE_REQUIRED = ["node_id", "label", "role", "definition", "mechanism", "evidence"]
_STAGE_2_EDGE_REQUIRED = ["from", "to", "relationship", "claim"]
_STAGE_2_TENSION_REQUIRED = ["claim", "nodes"]

_STAGE_3_ITEM_REQUIRED = ["source_id", "causal_node", "measurement_claim", "text_features", "implementation_ideas"]

_STAGE_4_SCORER_REQUIRED = ["scorer_id", "hypothesis", "causal_nodes_used", "functional_form", "functional_form_rationale", "expected_failure_mode", "code"]


def validate_stage_1_output(data: dict) -> list[str]:
    """Validate Stage 1 output schema. Returns list of errors (empty = valid)."""
    errors = []
    if "target_variable" not in data:
        errors.append("missing top-level field: target_variable")
    if "causal_research" not in data:
        errors.append("missing top-level field: causal_research")
    else:
        items = data["causal_research"]
        if not isinstance(items, list):
            errors.append("causal_research must be a list")
        else:
            for i, item in enumerate(items):
                for f in _STAGE_1_ITEM_REQUIRED:
                    if f not in item or not item[f]:
                        errors.append(f"causal_research[{i}] missing or empty: {f}")
    if "research_tensions" not in data:
        errors.append("missing top-level field: research_tensions")
    else:
        tensions = data["research_tensions"]
        if not isinstance(tensions, list):
            errors.append("research_tensions must be a list")
        else:
            for i, t in enumerate(tensions):
                for f in _STAGE_1_TENSION_REQUIRED:
                    if f not in t or not t[f]:
                        errors.append(f"research_tensions[{i}] missing or empty: {f}")
    return errors


def validate_stage_2_output(data: dict) -> list[str]:
    """Validate Stage 2 output schema. Returns list of errors (empty = valid)."""
    errors = []
    if "target_variable" not in data:
        errors.append("missing top-level field: target_variable")
    if "causal_nodes" not in data:
        errors.append("missing top-level field: causal_nodes")
    else:
        nodes = data["causal_nodes"]
        if not isinstance(nodes, list):
            errors.append("causal_nodes must be a list")
        else:
            for i, node in enumerate(nodes):
                for f in _STAGE_2_NODE_REQUIRED:
                    if f not in node or (not node[f] and node[f] != []):
                        errors.append(f"causal_nodes[{i}] missing or empty: {f}")
    if "causal_edges" not in data:
        errors.append("missing top-level field: causal_edges")
    else:
        edges = data["causal_edges"]
        if not isinstance(edges, list):
            errors.append("causal_edges must be a list")
        else:
            for i, edge in enumerate(edges):
                for f in _STAGE_2_EDGE_REQUIRED:
                    if f not in edge or not edge[f]:
                        errors.append(f"causal_edges[{i}] missing or empty: {f}")
    if "causal_tensions" not in data:
        errors.append("missing top-level field: causal_tensions")
    if "summary_theory" not in data:
        errors.append("missing top-level field: summary_theory")
    return errors


def validate_stage_3_output(data: dict) -> list[str]:
    """Validate Stage 3 output schema. Returns list of errors (empty = valid)."""
    errors = []
    if "target_variable" not in data:
        errors.append("missing top-level field: target_variable")
    if "measurement_research" not in data:
        errors.append("missing top-level field: measurement_research")
    else:
        items = data["measurement_research"]
        if not isinstance(items, list):
            errors.append("measurement_research must be a list")
        else:
            for i, item in enumerate(items):
                for f in _STAGE_3_ITEM_REQUIRED:
                    if f not in item or (not item[f] and item[f] != []):
                        errors.append(f"measurement_research[{i}] missing or empty: {f}")
    return errors


def validate_stage_4_output(data: dict) -> list[str]:
    """Validate Stage 4 output schema. Returns list of errors (empty = valid)."""
    errors = []
    if "target_variable" not in data:
        errors.append("missing top-level field: target_variable")
    if "scorers" not in data:
        errors.append("missing top-level field: scorers")
    else:
        scorers = data["scorers"]
        if not isinstance(scorers, list):
            errors.append("scorers must be a list")
        else:
            for i, s in enumerate(scorers):
                for f in _STAGE_4_SCORER_REQUIRED:
                    if f not in s or (not s[f] and s[f] != []):
                        errors.append(f"scorers[{i}] missing or empty: {f}")
                # Check function signature in code
                if "code" in s and s["code"]:
                    if "def scorer(text, anchor, params)" not in s["code"]:
                        errors.append(f"scorers[{i}] code must define: def scorer(text, anchor, params)")
    return errors


VALIDATE_FUNCS = {
    1: validate_stage_1_output,
    2: validate_stage_2_output,
    3: validate_stage_3_output,
    4: validate_stage_4_output,
}


# ─────────────────────────────────────────────────────────────────────
# PASS CRITERIA — split into HARD GATES (halt pipeline) and SOFT EVALS (tracked, not blocking)
# ─────────────────────────────────────────────────────────────────────

# HARD GATES: Structural failures that make downstream stages impossible.
# If these fail, the pipeline halts.
STAGE_1_HARD_GATES = {
    "num_research_items_min": 3,      # need at least some research to build a graph
    "source_trace_rate_min": 0.5,     # need sources to be traceable
}

STAGE_2_HARD_GATES = {
    "num_nodes_min": 3,               # need at least a few nodes for a graph
    "num_edges_min": 2,               # need edges to form a graph (not a flat list)
    "edge_validity_rate_min": 0.5,    # majority of edges should reference real nodes
}

STAGE_3_HARD_GATES = {
    "num_measurement_items_min": 3,   # need some measurement ideas for scorers
    "node_reference_validity_rate_min": 0.5,  # majority should reference real nodes
}

STAGE_4_HARD_GATES = {
    "num_scorers_min": 3,             # need at least some scorers
    "code_exec_rate_min": 0.3,        # at least 30% of scorers must execute
}

# SOFT EVALS: Quality signals we track and aim to improve via prompt iteration.
# These never halt the pipeline.
STAGE_1_SOFT_TARGETS = {
    "num_research_items_target": 8,
    "num_unique_causal_variables_target": 5,
    "mechanism_completeness_rate_target": 0.75,
    "causal_specificity_score_target": 0.6,
    "tension_count_target": 1,
    "generic_advice_penalty_target": 0.25,  # lower is better (max target)
}

STAGE_2_SOFT_TARGETS = {
    "num_nodes_target": 5,
    "num_edges_target": 4,
    "node_mechanism_rate_target": 0.85,
    "node_evidence_rate_target": 0.8,
    "edge_explanation_rate_target": 0.9,
    "graph_connectedness_score_target": 0.6,
    "role_diversity_score_target": 2,
    "tension_count_target": 1,
}

STAGE_3_SOFT_TARGETS = {
    "node_measurement_coverage_target": 0.7,
    "num_measurement_items_target": 8,
    "text_feature_specificity_score_target": 0.6,
    "implementation_actionability_score_target": 0.65,
    "multi_measurement_rate_target": 0.3,
}

STAGE_4_SOFT_TARGETS = {
    "hypothesis_completeness_rate_target": 1.0,
    "causal_node_validity_rate_target": 0.8,
    "measurement_reference_rate_target": 0.8,
    "functional_form_diversity_target": 3,
    "interaction_usage_rate_target": 0.4,
    "normalization_usage_rate_target": 0.4,
    "nonconstant_behavior_rate_target": 0.6,
    "scorer_distinctness_score_target": 0.75,
    "hypothesis_code_alignment_score_target": 0.35,
}

# Legacy combined criteria (for backward compat with existing tests)
STAGE_1_PASS_CRITERIA = {**{k: v for k, v in STAGE_1_HARD_GATES.items()}}
STAGE_2_PASS_CRITERIA = {**{k: v for k, v in STAGE_2_HARD_GATES.items()}}
STAGE_3_PASS_CRITERIA = {**{k: v for k, v in STAGE_3_HARD_GATES.items()}}
STAGE_4_PASS_CRITERIA = {**{k: v for k, v in STAGE_4_HARD_GATES.items()}}

SMOKE_TEXTS = [
    "This works because it gives teams a concrete way to test ideas before committing.",
    "This is the best and most revolutionary solution ever made.",
    "The tool helps users compare options, see tradeoffs, and choose a next step.",
    "Maybe it helps in some cases, but the limits are unclear.",
]


def check_pass_criteria(signals: dict, criteria: dict) -> tuple[bool, list[dict]]:
    """Check signals against pass criteria (hard gates). Returns (passed, failures)."""
    failures = []
    for key, threshold in criteria.items():
        if key.endswith("_min"):
            signal_name = key[:-4]  # remove _min
            value = signals.get(signal_name, 0)
            if value < threshold:
                failures.append({"signal": signal_name, "value": value, "threshold": threshold, "op": ">="})
        elif key.endswith("_max"):
            signal_name = key[:-4]  # remove _max
            value = signals.get(signal_name, 1.0)
            if value > threshold:
                failures.append({"signal": signal_name, "value": value, "threshold": threshold, "op": "<="})
    return (len(failures) == 0, failures)


def check_soft_targets(signals: dict, targets: dict) -> list[dict]:
    """Check signals against soft targets. Returns list of missed targets (informational only)."""
    missed = []
    for key, target in targets.items():
        if key.endswith("_target"):
            signal_name = key[:-7]  # remove _target
            value = signals.get(signal_name, 0)
            # For most targets, higher is better. Exception: penalty targets (lower is better)
            if "penalty" in signal_name:
                if value > target:
                    missed.append({"signal": signal_name, "value": value, "target": target, "direction": "lower_is_better"})
            else:
                if value < target:
                    missed.append({"signal": signal_name, "value": value, "target": target, "direction": "higher_is_better"})
    return missed


# ─────────────────────────────────────────────────────────────────────
# STAGES 5–8: SCHEMA VALIDATION
# ─────────────────────────────────────────────────────────────────────

_STAGE_5_PAIR_REQUIRED = ["pair_id", "anchor", "positive", "negative", "split", "target_delta", "controlled_variables"]

_STAGE_7_PATTERN_REQUIRED = ["pattern_id", "scorer_ids", "reasoning_error"]
_STAGE_7_INSTRUCTION_REQUIRED = ["instruction_id", "instruction"]

_STAGE_8_SCORER_REQUIRED = ["scorer_id", "hypothesis", "causal_nodes_used", "functional_form", "code"]


def validate_stage_5_output(data: dict) -> list[str]:
    """Validate Stage 5 output schema (pair suite). Returns list of errors (empty = valid)."""
    errors = []
    if "target_variable" not in data:
        errors.append("missing top-level field: target_variable")
    if "pairs" not in data:
        errors.append("missing top-level field: pairs")
    else:
        pairs = data["pairs"]
        if not isinstance(pairs, list):
            errors.append("pairs must be a list")
        else:
            for i, p in enumerate(pairs):
                for f in _STAGE_5_PAIR_REQUIRED:
                    if f not in p or (not p[f] and p[f] != [] and p[f] != {}):
                        errors.append(f"pairs[{i}] missing or empty: {f}")
    return errors


def validate_stage_6_output(data: dict) -> list[str]:
    """Validate Stage 6 output schema (scorer evaluation). Returns list of errors (empty = valid)."""
    errors = []
    if "scorer_evaluations" not in data:
        errors.append("missing top-level field: scorer_evaluations")
    elif not isinstance(data["scorer_evaluations"], dict):
        errors.append("scorer_evaluations must be a dict")
    if "scorer_summaries" not in data:
        errors.append("missing top-level field: scorer_summaries")
    elif not isinstance(data["scorer_summaries"], list):
        errors.append("scorer_summaries must be a list")
    if "pareto_frontier" not in data:
        errors.append("missing top-level field: pareto_frontier")
    elif not isinstance(data["pareto_frontier"], list):
        errors.append("pareto_frontier must be a list")
    return errors


def validate_stage_7_output(data: dict) -> list[str]:
    """Validate Stage 7 output schema (failure packet). Returns list of errors (empty = valid)."""
    errors = []
    if "failure_patterns" not in data:
        errors.append("missing top-level field: failure_patterns")
    else:
        patterns = data["failure_patterns"]
        if not isinstance(patterns, list):
            errors.append("failure_patterns must be a list")
        else:
            for i, p in enumerate(patterns):
                for f in _STAGE_7_PATTERN_REQUIRED:
                    if f not in p or (not p[f] and p[f] != []):
                        errors.append(f"failure_patterns[{i}] missing or empty: {f}")
    if "mutation_instructions" not in data:
        errors.append("missing top-level field: mutation_instructions")
    else:
        instructions = data["mutation_instructions"]
        if not isinstance(instructions, list):
            errors.append("mutation_instructions must be a list")
        else:
            for i, inst in enumerate(instructions):
                for f in _STAGE_7_INSTRUCTION_REQUIRED:
                    if f not in inst or not inst[f]:
                        errors.append(f"mutation_instructions[{i}] missing or empty: {f}")
    if "heldout_aggregate_only" not in data:
        errors.append("missing top-level field: heldout_aggregate_only")
    return errors


def validate_stage_8_output(data: dict) -> list[str]:
    """Validate Stage 8 output schema (repair scorers). Returns list of errors (empty = valid)."""
    errors = []
    if "target_variable" not in data:
        errors.append("missing top-level field: target_variable")
    if "repair_scorers" not in data:
        errors.append("missing top-level field: repair_scorers")
    else:
        scorers = data["repair_scorers"]
        if not isinstance(scorers, list):
            errors.append("repair_scorers must be a list")
        else:
            for i, s in enumerate(scorers):
                for f in _STAGE_8_SCORER_REQUIRED:
                    if f not in s or (not s[f] and s[f] != []):
                        errors.append(f"repair_scorers[{i}] missing or empty: {f}")
                # Check function signature in code
                if "code" in s and s["code"]:
                    if "def scorer(text, anchor, params)" not in s["code"]:
                        errors.append(f"repair_scorers[{i}] code must define: def scorer(text, anchor, params)")
    return errors


# Update VALIDATE_FUNCS to include stages 5-8
VALIDATE_FUNCS[5] = validate_stage_5_output
VALIDATE_FUNCS[6] = validate_stage_6_output
VALIDATE_FUNCS[7] = validate_stage_7_output
VALIDATE_FUNCS[8] = validate_stage_8_output


# ─────────────────────────────────────────────────────────────────────
# STAGES 5–8: HARD GATES AND SOFT TARGETS
# ─────────────────────────────────────────────────────────────────────

STAGE_5_HARD_GATES = {
    "num_pairs_min": 6,                        # need at least some pairs to evaluate scorers
    "pair_schema_completeness_rate_min": 0.5,  # majority must have required fields
}

STAGE_6_HARD_GATES = {
    "num_scorers_evaluated_min": 3,            # need at least some scorers evaluated
    "execution_valid_rate_min": 0.3,           # at least 30% must execute without errors
}

STAGE_7_HARD_GATES = {
    "failure_pattern_count_min": 1,            # need at least one failure pattern identified
    "heldout_raw_text_leakage_count_max": 0,   # zero tolerance for heldout leakage
}

STAGE_8_HARD_GATES = {
    "num_repair_scorers_min": 2,               # need at least some repair scorers
    "code_exec_rate_min": 0.3,                 # at least 30% must execute
}

STAGE_5_SOFT_TARGETS = {
    "source_trace_rate_target": 0.8,
    "causal_node_reference_validity_rate_target": 0.8,
    "controlled_variable_pass_rate_target": 0.7,
    "length_balance_rate_target": 0.7,
    "minimal_contrast_rate_target": 0.6,
    "target_direction_clarity_rate_target": 0.8,
    "positive_policy_pass_rate_target": 0.9,
}

STAGE_6_SOFT_TARGETS = {
    "eligible_scorer_count_target": 3,
    "pareto_count_target": 2,
    "nonconstant_scorer_rate_target": 0.5,
    "heldout_accuracy_presence_rate_target": 0.8,
}

STAGE_7_SOFT_TARGETS = {
    "top_scorer_coverage_rate_target": 0.8,
    "visible_failure_reference_rate_target": 0.5,
    "failure_pattern_specificity_score_target": 0.6,
    "mutation_actionability_score_target": 0.7,
    "causal_reference_rate_target": 0.5,
}

STAGE_8_SOFT_TARGETS = {
    "failure_pattern_target_rate_target": 0.8,
    "lineage_completeness_rate_target": 0.9,
    "causal_node_validity_rate_target": 0.8,
    "measurement_reference_rate_target": 0.7,
    "nonconstant_behavior_rate_target": 0.6,
    "functional_form_diversity_target": 3,
    "parent_distinctness_rate_target": 0.5,
}

# Legacy combined criteria (for backward compat)
STAGE_5_PASS_CRITERIA = {**STAGE_5_HARD_GATES}
STAGE_6_PASS_CRITERIA = {**STAGE_6_HARD_GATES}
STAGE_7_PASS_CRITERIA = {**STAGE_7_HARD_GATES}
STAGE_8_PASS_CRITERIA = {**STAGE_8_HARD_GATES}
