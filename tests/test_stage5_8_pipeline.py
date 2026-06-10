"""Property-based tests for Stages 5–8 schema validation and orchestration."""
# Feature: stages-5-8-reasoning-pipeline

from hypothesis import given, settings
from hypothesis import strategies as st

from evalweaver.stage_models import (
    validate_stage_5_output, validate_stage_6_output,
    validate_stage_7_output, validate_stage_8_output,
    check_pass_criteria, check_soft_targets,
    STAGE_5_HARD_GATES, STAGE_5_SOFT_TARGETS,
    STAGE_7_HARD_GATES,
)
from evalweaver.stage_prompts import build_stage_5_prompt, build_stage_7_prompt, build_stage_8_prompt


# ─── Property 1: Prompt includes target_variable ───

@settings(max_examples=30)
@given(st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=("L",))))
def test_prompt_includes_target_variable(target_variable):
    """P1: All stage prompts include the target_variable string."""
    # Feature: stages-5-8-reasoning-pipeline, Property 1: prompt includes target_variable
    graph = {"causal_nodes": [{"node_id": "n1", "role": "increases", "mechanism": "m"}], "causal_edges": []}
    measurement = [{"causal_node": "n1", "text_features": ["f1"], "implementation_ideas": ["count x"]}]

    sys5, usr5 = build_stage_5_prompt(target_variable, graph, measurement, [], {})
    assert target_variable in usr5

    sys7, usr7 = build_stage_7_prompt(target_variable, [], [], [], [], graph, measurement, {})
    assert target_variable in usr7

    sys8, usr8 = build_stage_8_prompt(target_variable, graph, measurement, [], {"failure_patterns": [], "mutation_instructions": []})
    assert target_variable in usr8


# ─── Property 2: Schema validation ───

def test_stage5_valid_schema_passes():
    """P2: Valid Stage 5 output passes validation."""
    # Feature: stages-5-8-reasoning-pipeline, Property 2: schema validation
    data = {
        "target_variable": "trustworthy",
        "pairs": [
            {"pair_id": "P1", "anchor": "a", "positive": "p", "negative": "n",
             "split": "train", "target_delta": "d", "controlled_variables": ["x"]}
        ],
    }
    assert validate_stage_5_output(data) == []


def test_stage5_missing_field_fails():
    """P2: Stage 5 output with missing pair_id fails."""
    data = {
        "target_variable": "trustworthy",
        "pairs": [
            {"anchor": "a", "positive": "p", "negative": "n",
             "split": "train", "target_delta": "d", "controlled_variables": ["x"]}
        ],
    }
    errors = validate_stage_5_output(data)
    assert len(errors) > 0
    assert "pair_id" in errors[0]


def test_stage7_valid_schema_passes():
    """P2: Valid Stage 7 output passes validation."""
    data = {
        "failure_patterns": [{"pattern_id": "FP1", "scorer_ids": ["S0"], "reasoning_error": "e"}],
        "mutation_instructions": [{"instruction_id": "MI1", "instruction": "add gate"}],
        "heldout_aggregate_only": {},
    }
    assert validate_stage_7_output(data) == []


def test_stage8_code_signature_required():
    """P2: Stage 8 scorer must have def scorer(text, anchor, params)."""
    data = {
        "target_variable": "t",
        "repair_scorers": [
            {"scorer_id": "RS0", "hypothesis": "h", "causal_nodes_used": ["n"],
             "functional_form": "additive", "code": "def bad_func(): return 0"}
        ],
    }
    errors = validate_stage_8_output(data)
    assert any("def scorer(text, anchor, params)" in e for e in errors)


# ─── Property 5: Hard gate threshold check ───

@settings(max_examples=50)
@given(st.integers(min_value=0, max_value=20), st.floats(min_value=0.0, max_value=1.0))
def test_hard_gate_threshold_check(num_pairs, completeness):
    """P5: Hard gates pass iff all signals meet thresholds."""
    # Feature: stages-5-8-reasoning-pipeline, Property 5: hard gate threshold
    signals = {"num_pairs": num_pairs, "pair_schema_completeness_rate": completeness}
    passed, failures = check_pass_criteria(signals, STAGE_5_HARD_GATES)

    should_pass = (num_pairs >= 6 and completeness >= 0.5)
    assert passed == should_pass


# ─── Property 21: Split assignment ───

def test_split_assignment_respects_heldout_count():
    """P21: After split assignment, exactly heldout_count pairs are heldout."""
    # Feature: stages-5-8-reasoning-pipeline, Property 21: split assignment
    from evalweaver.stages_5_8 import Stage5to8Orchestrator

    class FakeProvider:
        last_call_meta = None

    orch = Stage5to8Orchestrator(
        provider=FakeProvider(), config={"heldout_count": 3}, out_dir="/tmp",
        stage2_output={}, stage3_output={}, stage4_output={},
    )
    data = {"pairs": [{"pair_id": f"P{i}"} for i in range(10)]}
    orch._assign_splits(data)

    heldout = [p for p in data["pairs"] if p["split"] == "heldout"]
    train = [p for p in data["pairs"] if p["split"] == "train"]
    assert len(heldout) == 3
    assert len(train) == 7


# ─── Property 22: Soft targets never block ───

def test_soft_targets_never_block():
    """P22: Soft target misses appear in soft_evals, not failures."""
    # Feature: stages-5-8-reasoning-pipeline, Property 22: soft targets non-blocking
    # Signals that pass hard gates but miss soft targets
    signals = {"num_pairs": 10, "pair_schema_completeness_rate": 0.9, "source_trace_rate": 0.1}
    passed, failures = check_pass_criteria(signals, STAGE_5_HARD_GATES)
    assert passed  # hard gates pass
    assert len(failures) == 0

    soft_misses = check_soft_targets(signals, STAGE_5_SOFT_TARGETS)
    assert len(soft_misses) > 0  # but soft targets are missed
    # Verify the miss is informational
    assert soft_misses[0]["signal"] == "source_trace_rate"
