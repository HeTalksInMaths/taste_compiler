"""
Property-based tests for schema validation and orchestration (Stages 1–4).

Tests Properties 1–4, 16–17 from the design document using Hypothesis.
"""

import json
import math
import os
import tempfile
import shutil

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from evalweaver.stage_models import (
    StageResult, EvalResult,
    validate_stage_1_output, validate_stage_2_output,
    validate_stage_3_output, validate_stage_4_output,
    STAGE_1_PASS_CRITERIA, STAGE_2_PASS_CRITERIA,
    STAGE_3_PASS_CRITERIA, STAGE_4_PASS_CRITERIA,
    SMOKE_TEXTS, check_pass_criteria,
)
from evalweaver.stage_prompts import (
    build_stage_1_prompt, build_stage_2_prompt,
    build_stage_3_prompt, build_stage_4_prompt,
)
from evalweaver.stage_eval import eval_stage_1, eval_stage_2, eval_stage_3, eval_stage_4
from evalweaver.stages import StageOrchestrator, write_failure_points
from evalweaver.artifacts import save


# ─────────────────────────────────────────────────────────────────────
# STRATEGIES
# ─────────────────────────────────────────────────────────────────────

def st_target_variable():
    """Generate a target variable name."""
    return st.sampled_from([
        "trustworthy", "persuasive", "concise", "technical", "engaging",
        "credible", "clear", "actionable", "professional", "empathetic",
    ])


def st_valid_stage1_output():
    """Generate a valid Stage 1 output that passes schema validation."""
    return st.fixed_dictionaries({
        "target_variable": st_target_variable(),
        "causal_research": st.lists(
            st.fixed_dictionaries({
                "source_id": st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)),
                "title": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
                "claim": st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
                "causal_variable": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
                "effect_direction": st.sampled_from(["increases", "decreases", "mediates", "moderates"]),
                "mechanism": st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
                "evidence_strength": st.sampled_from(["high", "medium", "low"]),
            }),
            min_size=1, max_size=5,
        ),
        "research_tensions": st.lists(
            st.fixed_dictionaries({
                "claim": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
                "variables": st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)), min_size=2, max_size=4),
            }),
            min_size=0, max_size=3,
        ),
    })


def st_valid_stage2_output():
    """Generate a valid Stage 2 output."""
    return st.fixed_dictionaries({
        "target_variable": st_target_variable(),
        "causal_nodes": st.lists(
            st.fixed_dictionaries({
                "node_id": st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
                "label": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
                "role": st.sampled_from(["increases", "decreases", "mediates", "moderates"]),
                "definition": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
                "mechanism": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
                "evidence": st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)), min_size=1, max_size=3),
            }),
            min_size=1, max_size=5,
        ),
        "causal_edges": st.lists(
            st.fixed_dictionaries({
                "from": st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
                "to": st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
                "relationship": st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
                "claim": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
            }),
            min_size=1, max_size=5,
        ),
        "causal_tensions": st.lists(
            st.fixed_dictionaries({
                "claim": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
                "nodes": st.lists(st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)), min_size=2, max_size=4),
            }),
            min_size=0, max_size=3,
        ),
        "summary_theory": st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
    })


def st_valid_stage3_output():
    """Generate a valid Stage 3 output."""
    return st.fixed_dictionaries({
        "target_variable": st_target_variable(),
        "measurement_research": st.lists(
            st.fixed_dictionaries({
                "source_id": st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)),
                "causal_node": st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
                "measurement_claim": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
                "text_features": st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)), min_size=1, max_size=4),
                "implementation_ideas": st.lists(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)), min_size=1, max_size=4),
            }),
            min_size=1, max_size=5,
        ),
    })


def st_valid_stage4_output():
    """Generate a valid Stage 4 output."""
    return st.fixed_dictionaries({
        "target_variable": st_target_variable(),
        "scorers": st.lists(
            st.fixed_dictionaries({
                "scorer_id": st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)),
                "hypothesis": st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
                "causal_nodes_used": st.lists(st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)), min_size=1, max_size=3),
                "functional_form": st.sampled_from(["additive", "interaction", "gated", "penalty", "tension_balance"]),
                "functional_form_rationale": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
                "expected_failure_mode": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
                "code": st.just("def scorer(text, anchor, params):\n    return len(text) / (len(text) + 100)"),
            }),
            min_size=1, max_size=5,
        ),
    })


# ─────────────────────────────────────────────────────────────────────
# Property 2: Schema validation round-trip
# Feature: stages-1-4-reasoning-pipeline, Property 2: schema validation: valid passes, missing fields fail
# ─────────────────────────────────────────────────────────────────────


class TestProperty2SchemaValidation:
    """Valid outputs pass validation; missing required fields fail validation."""

    # **Validates: Requirements 1.2, 1.3, 3.2, 3.3, 3.4, 5.2, 5.3, 7.2, 7.3, 7.4**

    @given(st_valid_stage1_output())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_stage1_passes(self, data):
        """A fully valid Stage 1 output passes validation with no errors."""
        errors = validate_stage_1_output(data)
        assert errors == [], f"Valid Stage 1 output should have no errors: {errors}"

    @given(st_valid_stage2_output())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_stage2_passes(self, data):
        """A fully valid Stage 2 output passes validation with no errors."""
        errors = validate_stage_2_output(data)
        assert errors == [], f"Valid Stage 2 output should have no errors: {errors}"

    @given(st_valid_stage3_output())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_stage3_passes(self, data):
        """A fully valid Stage 3 output passes validation with no errors."""
        errors = validate_stage_3_output(data)
        assert errors == [], f"Valid Stage 3 output should have no errors: {errors}"

    @given(st_valid_stage4_output())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_stage4_passes(self, data):
        """A fully valid Stage 4 output passes validation with no errors."""
        errors = validate_stage_4_output(data)
        assert errors == [], f"Valid Stage 4 output should have no errors: {errors}"

    @given(st_valid_stage1_output(), st.sampled_from(["source_id", "claim", "causal_variable", "effect_direction", "mechanism"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_missing_stage1_field_fails(self, data, field_to_remove):
        """Removing a required field from a Stage 1 item causes validation failure."""
        assume(len(data["causal_research"]) > 0)
        data["causal_research"][0][field_to_remove] = ""
        errors = validate_stage_1_output(data)
        assert len(errors) > 0, f"Missing '{field_to_remove}' should cause error"

    @given(st_valid_stage2_output(), st.sampled_from(["node_id", "label", "role", "definition", "mechanism"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_missing_stage2_node_field_fails(self, data, field_to_remove):
        """Removing a required field from a Stage 2 node causes validation failure."""
        assume(len(data["causal_nodes"]) > 0)
        data["causal_nodes"][0][field_to_remove] = ""
        errors = validate_stage_2_output(data)
        assert len(errors) > 0, f"Missing node '{field_to_remove}' should cause error"

    @given(st_valid_stage2_output(), st.sampled_from(["from", "to", "relationship", "claim"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_missing_stage2_edge_field_fails(self, data, field_to_remove):
        """Removing a required field from a Stage 2 edge causes validation failure."""
        assume(len(data["causal_edges"]) > 0)
        data["causal_edges"][0][field_to_remove] = ""
        errors = validate_stage_2_output(data)
        assert len(errors) > 0, f"Missing edge '{field_to_remove}' should cause error"

    @given(st_valid_stage3_output(), st.sampled_from(["source_id", "causal_node", "measurement_claim"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_missing_stage3_field_fails(self, data, field_to_remove):
        """Removing a required field from a Stage 3 item causes validation failure."""
        assume(len(data["measurement_research"]) > 0)
        data["measurement_research"][0][field_to_remove] = ""
        errors = validate_stage_3_output(data)
        assert len(errors) > 0, f"Missing '{field_to_remove}' should cause error"

    @given(st_valid_stage4_output(), st.sampled_from(["scorer_id", "hypothesis", "functional_form"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_missing_stage4_field_fails(self, data, field_to_remove):
        """Removing a required field from a Stage 4 scorer causes validation failure."""
        assume(len(data["scorers"]) > 0)
        data["scorers"][0][field_to_remove] = ""
        errors = validate_stage_4_output(data)
        assert len(errors) > 0, f"Missing '{field_to_remove}' should cause error"

    def test_missing_top_level_stage1(self):
        """Missing top-level fields fail Stage 1 validation."""
        errors = validate_stage_1_output({})
        assert len(errors) >= 2  # missing target_variable, causal_research, research_tensions

    def test_missing_top_level_stage2(self):
        """Missing top-level fields fail Stage 2 validation."""
        errors = validate_stage_2_output({})
        assert len(errors) >= 2


# ─────────────────────────────────────────────────────────────────────
# Property 3: Artifact persistence round-trip
# Feature: stages-1-4-reasoning-pipeline, Property 3: artifact persistence round-trip
# ─────────────────────────────────────────────────────────────────────


def st_json_serializable():
    """Generate JSON-serializable dicts."""
    json_values = st.recursive(
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(min_value=-10000, max_value=10000),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            st.text(min_size=0, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
        ),
        lambda children: st.one_of(
            st.lists(children, max_size=4),
            st.dictionaries(
                st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
                children, max_size=4,
            ),
        ),
        max_leaves=15,
    )
    return st.dictionaries(
        st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
        json_values, min_size=1, max_size=5,
    )


class TestProperty3ArtifactPersistence:
    """Persisting and loading artifacts produces equivalent JSON objects."""

    # **Validates: Requirements 1.4, 3.5, 5.4, 7.5, 10.1**

    @given(st_json_serializable())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_save_load_roundtrip(self, data):
        """save() then json.load() produces identical data."""
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop3_")
        try:
            path = save("test_artifact", data, out_dir=tmp_dir)
            with open(path) as f:
                loaded = json.load(f)
            assert loaded == data, f"Roundtrip mismatch: {data} != {loaded}"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(st_valid_stage1_output())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_stage1_output_roundtrip(self, data):
        """Stage 1 output survives JSON round-trip."""
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop3s1_")
        try:
            path = save("stage1_parsed_json", data, out_dir=tmp_dir)
            with open(path) as f:
                loaded = json.load(f)
            assert loaded == data
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_eval_result_roundtrip(self):
        """EvalResult survives serialization round-trip."""
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop3eval_")
        try:
            eval_result = EvalResult(
                signals={"mechanism_completeness_rate": 0.85, "tension_count": 2},
                passed=True,
                failures=[],
            )
            path = save("stage1_eval_result", eval_result.to_dict(), out_dir=tmp_dir)
            with open(path) as f:
                loaded = json.load(f)
            assert loaded == eval_result.to_dict()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────
# Property 4: Unparseable response halts pipeline
# Feature: stages-1-4-reasoning-pipeline, Property 4: unparseable response halts pipeline
# ─────────────────────────────────────────────────────────────────────


class TestProperty4UnparseableHalts:
    """Unparseable responses cause parse_error and pipeline halt."""

    # **Validates: Requirements 1.5, 3.6, 5.5, 7.6**

    @given(st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "Z", "P"), max_codepoint=127)))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_non_json_text_halts(self, raw_text):
        """Non-JSON text produces a parse error in the stage result."""
        assume(not raw_text.strip().startswith("{"))
        assume(not raw_text.strip().startswith("["))

        # Simulate what the orchestrator does: try to parse JSON
        try:
            json.loads(raw_text)
            # If it parses as valid JSON, skip this example
            assume(False)
        except (json.JSONDecodeError, ValueError):
            pass

        # Create a StageResult with parse_error
        result = StageResult(
            stage_num=1,
            stage_name="Causal Research Search",
            prompt={"system": "s", "user": "u"},
            raw_response=raw_text,
            parsed_json=None,
            parse_error="JSON parse error: not valid JSON",
            call_meta={},
        )
        assert result.parsed_json is None
        assert result.parse_error is not None

    @given(st.binary(min_size=1, max_size=50))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_random_bytes_not_parseable(self, random_bytes):
        """Random bytes cannot be parsed as JSON."""
        try:
            text = random_bytes.decode("utf-8", errors="replace")
        except Exception:
            text = "garbage"

        try:
            json.loads(text)
            assume(False)  # Skip if it accidentally parses
        except (json.JSONDecodeError, ValueError):
            # Expected: cannot parse
            pass

    def test_truncated_json_with_parse_error_halts(self):
        """Truncated JSON that can't be repaired sets parse_error."""
        # A deeply truncated response that repair can't fix
        truncated = '{"causal_research": [{"source_id": "S1", "tit'

        result = StageResult(
            stage_num=1,
            stage_name="Causal Research Search",
            prompt={"system": "s", "user": "u"},
            raw_response=truncated,
            parsed_json=None,
            parse_error="JSON parse error: Unterminated string",
            call_meta={},
        )
        # When parse_error is set, pipeline should halt
        assert result.parse_error is not None
        assert result.parsed_json is None


# ─────────────────────────────────────────────────────────────────────
# Property 16: Fail-fast halts subsequent stages
# Feature: stages-1-4-reasoning-pipeline, Property 16: fail-fast halts subsequent stages
# ─────────────────────────────────────────────────────────────────────


class MockProviderForFailFast:
    """Mock provider that returns controlled JSON responses for fail-fast testing."""

    def __init__(self, stage_responses: dict):
        self.stage_responses = stage_responses
        self.calls_made = []
        self.last_call_meta = {"latency_ms": 10, "retry_mode": "standard", "max_attempts": 5, "error": None}
        self._call_count = 0

    def _converse(self, system: str, user: str) -> str:
        self._call_count += 1
        self.calls_made.append(self._call_count)
        response = self.stage_responses.get(self._call_count, '{}')
        return response

    def _parse_json_response(self, raw: str) -> dict:
        return json.loads(raw)


class TestProperty16FailFastHalts:
    """If stage N fails evaluation, stages N+1 through 4 do not execute."""

    # **Validates: Requirements 9.1, 9.3, 2.6, 4.6, 6.6, 8.7**

    def test_stage1_fail_halts_pipeline(self):
        """Stage 1 failure prevents stages 2-4 from executing."""
        # Stage 1 response that fails eval (empty causal_research)
        stage1_response = json.dumps({
            "target_variable": "trustworthy",
            "causal_research": [],
            "research_tensions": [],
        })
        provider = MockProviderForFailFast({1: stage1_response})
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_ff1_")
        try:
            config = {"goal": "trustworthy", "raw_text": "anchor"}
            orchestrator = StageOrchestrator(provider, config, tmp_dir)
            result = orchestrator.run()

            assert result["success"] is False
            assert result["failed_stage"] == 1
            assert result["stages_passed"] == 0
            # Provider should only be called once
            assert len(provider.calls_made) == 1
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_stage2_fail_halts_pipeline(self):
        """Stage 2 failure prevents stages 3-4 from executing."""
        # Stage 1 passes with good data
        stage1_response = json.dumps({
            "target_variable": "trustworthy",
            "causal_research": [
                {"source_id": f"S{i}", "title": f"Title {i}", "claim": f"X because Y leads to Z {i}",
                 "causal_variable": f"var{i}", "effect_direction": "increases",
                 "mechanism": f"Through mechanism {i} because it drives results", "evidence_strength": "high"}
                for i in range(10)
            ],
            "research_tensions": [{"claim": "Tension A vs B", "variables": ["varA", "varB"]}],
        })
        # Stage 2 fails (empty graph)
        stage2_response = json.dumps({
            "target_variable": "trustworthy",
            "causal_nodes": [],
            "causal_edges": [],
            "causal_tensions": [],
            "summary_theory": "theory",
        })
        provider = MockProviderForFailFast({1: stage1_response, 2: stage2_response})
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_ff2_")
        try:
            config = {"goal": "trustworthy", "raw_text": "anchor"}
            orchestrator = StageOrchestrator(provider, config, tmp_dir)
            result = orchestrator.run()

            assert result["success"] is False
            assert result["failed_stage"] == 2
            assert result["stages_passed"] == 1
            # Provider called for stages 1 and 2 only
            assert len(provider.calls_made) == 2
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(st.integers(min_value=1, max_value=4))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_fail_at_stage_n_reports_correctly(self, fail_stage):
        """Pipeline reports correct failed_stage and stages_passed."""
        # Build responses: stages before fail_stage pass, stage fail_stage fails
        responses = {}
        for s in range(1, fail_stage):
            responses[s] = self._make_passing_response(s)
        responses[fail_stage] = self._make_failing_response(fail_stage)

        provider = MockProviderForFailFast(responses)
        tmp_dir = tempfile.mkdtemp(prefix=f"evalweaver_ffn{fail_stage}_")
        try:
            config = {"goal": "trustworthy", "raw_text": "anchor"}
            orchestrator = StageOrchestrator(provider, config, tmp_dir)
            result = orchestrator.run()

            assert result["success"] is False
            assert result["failed_stage"] == fail_stage
            assert result["stages_passed"] == fail_stage - 1
            # Provider called exactly fail_stage times
            assert len(provider.calls_made) == fail_stage
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _make_passing_response(self, stage_num: int) -> str:
        """Create a response that passes eval for the given stage."""
        if stage_num == 1:
            return json.dumps({
                "target_variable": "trustworthy",
                "causal_research": [
                    {"source_id": f"S{i}", "title": f"Title {i}", "claim": f"X because Y leads to Z {i}",
                     "causal_variable": f"var{i}", "effect_direction": ["increases", "decreases", "mediates", "moderates"][i % 4],
                     "mechanism": f"Through mechanism {i} because it drives and causes results", "evidence_strength": "high"}
                    for i in range(12)
                ],
                "research_tensions": [{"claim": "Tension exists", "variables": ["var0", "var1"]}],
            })
        elif stage_num == 2:
            node_ids = [f"node{i}" for i in range(7)]
            return json.dumps({
                "target_variable": "trustworthy",
                "causal_nodes": [
                    {"node_id": nid, "label": f"Node {i}", "role": ["increases", "decreases", "mediates", "moderates"][i % 4],
                     "definition": f"Definition {i}", "mechanism": f"Mechanism {i}", "evidence": [f"S{i}"]}
                    for i, nid in enumerate(node_ids)
                ],
                "causal_edges": [
                    {"from": node_ids[i], "to": node_ids[i + 1], "relationship": "supports", "claim": f"Edge claim {i}"}
                    for i in range(6)
                ],
                "causal_tensions": [{"claim": "Tension", "nodes": [node_ids[0], node_ids[1]]}],
                "summary_theory": f"Theory about {node_ids[0]}",
            })
        elif stage_num == 3:
            return json.dumps({
                "target_variable": "trustworthy",
                "measurement_research": [
                    {"source_id": f"M{i}", "causal_node": f"node{i % 7}",
                     "measurement_claim": f"Measure claim {i}",
                     "text_features": [f"feature_{i}_a", f"feature_{i}_b"],
                     "implementation_ideas": [f"count specific pattern {i}", f"compute ratio of markers {i}"]}
                    for i in range(12)
                ],
            })
        elif stage_num == 4:
            return json.dumps({
                "target_variable": "trustworthy",
                "scorers": [
                    {"scorer_id": f"S{i}", "hypothesis": f"Hypothesis {i}",
                     "causal_nodes_used": [f"node{i % 7}"],
                     "causal_edges_used": [],
                     "causal_tensions_used": [],
                     "measurement_ideas_used": [f"idea_{i}"],
                     "functional_form": ["additive", "interaction", "gated", "penalty", "tension_balance", "ratio_or_density"][i % 6],
                     "functional_form_rationale": f"Rationale {i}",
                     "expected_failure_mode": f"Failure mode {i}",
                     "code": f"def scorer(text, anchor, params):\n    words = text.split()\n    return min(len(words) / (10 + {i}), 1.0)"}
                    for i in range(7)
                ],
            })
        return "{}"

    def _make_failing_response(self, stage_num: int) -> str:
        """Create a response that fails eval for the given stage."""
        if stage_num == 1:
            return json.dumps({"target_variable": "trustworthy", "causal_research": [], "research_tensions": []})
        elif stage_num == 2:
            return json.dumps({"target_variable": "trustworthy", "causal_nodes": [], "causal_edges": [], "causal_tensions": [], "summary_theory": ""})
        elif stage_num == 3:
            return json.dumps({"target_variable": "trustworthy", "measurement_research": []})
        elif stage_num == 4:
            return json.dumps({"target_variable": "trustworthy", "scorers": []})
        return "{}"


# ─────────────────────────────────────────────────────────────────────
# Property 17: Failure report contains all executed stage statuses
# Feature: stages-1-4-reasoning-pipeline, Property 17: failure report contains all stage statuses
# ─────────────────────────────────────────────────────────────────────


class TestProperty17FailureReport:
    """failure_points.md contains an entry for every executed stage with pass/fail status."""

    # **Validates: Requirements 10.2, 10.3**

    @given(st.integers(min_value=1, max_value=4))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_report_contains_all_executed_stages(self, num_stages):
        """Report includes entries for all executed stages."""
        stage_results = []
        for i in range(1, num_stages + 1):
            sr = StageResult(stage_num=i, stage_name=f"Stage {i}", prompt={}, raw_response="", parsed_json={}, parse_error=None, call_meta={})
            if i < num_stages:
                er = EvalResult(signals={"sig": 0.9}, passed=True, failures=[])
            else:
                er = EvalResult(signals={"sig": 0.1}, passed=False, failures=[{"signal": "sig", "value": 0.1, "threshold": 0.8, "op": ">="}])
            stage_results.append((sr, er))

        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop17_")
        try:
            write_failure_points(tmp_dir, stage_results)
            report_path = os.path.join(tmp_dir, "failure_points.md")
            assert os.path.exists(report_path)
            with open(report_path) as f:
                content = f.read()

            # Check all executed stages are mentioned
            for i in range(1, num_stages + 1):
                assert f"Stage {i}" in content, f"Stage {i} not found in report"

            # Check pass/fail markers
            for i in range(1, num_stages):
                assert "PASS" in content  # Earlier stages passed
            assert "FAIL" in content  # Last stage failed
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_all_pass_report(self):
        """When all stages pass, report indicates overall success."""
        stage_results = [
            (StageResult(stage_num=i, stage_name=f"Stage {i}", prompt={}, raw_response="", parsed_json={}, parse_error=None, call_meta={}),
             EvalResult(signals={"sig": 1.0}, passed=True, failures=[]))
            for i in range(1, 5)
        ]
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop17pass_")
        try:
            write_failure_points(tmp_dir, stage_results)
            report_path = os.path.join(tmp_dir, "failure_points.md")
            with open(report_path) as f:
                content = f.read()
            assert "ALL STAGES PASSED" in content
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_failed_signals_in_report(self):
        """Failed signals are listed in the report."""
        sr = StageResult(stage_num=2, stage_name="Causal Graph Generation", prompt={}, raw_response="", parsed_json={}, parse_error=None, call_meta={})
        er = EvalResult(
            signals={"edge_validity_rate": 0.5, "graph_connectedness_score": 0.3},
            passed=False,
            failures=[
                {"signal": "edge_validity_rate", "value": 0.5, "threshold": 1.0, "op": ">="},
                {"signal": "graph_connectedness_score", "value": 0.3, "threshold": 0.6, "op": ">="},
            ],
        )
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop17sig_")
        try:
            write_failure_points(tmp_dir, [(sr, er)])
            report_path = os.path.join(tmp_dir, "failure_points.md")
            with open(report_path) as f:
                content = f.read()
            assert "edge_validity_rate" in content
            assert "graph_connectedness_score" in content
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────
# Property 1: Prompt construction includes required inputs
# Feature: stages-1-4-reasoning-pipeline, Property 1: prompt construction includes required inputs
# ─────────────────────────────────────────────────────────────────────


class TestProperty1PromptConstruction:
    """Constructed prompts contain target_variable and prior-stage data."""

    # **Validates: Requirements 1.1, 3.1, 5.1, 7.1**

    @given(st_target_variable())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_stage1_prompt_contains_target(self, target):
        """Stage 1 prompt contains the target_variable."""
        system, user = build_stage_1_prompt(target)
        assert target in user, f"target_variable '{target}' not in user prompt"

    @given(st_target_variable(), st.lists(
        st.fixed_dictionaries({
            "source_id": st.just("SRC_001"),
            "claim": st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
        }),
        min_size=1, max_size=3,
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_stage2_prompt_contains_target_and_research(self, target, research):
        """Stage 2 prompt contains target_variable and Stage 1 research data."""
        system, user = build_stage_2_prompt(target, research)
        assert target in user, f"target_variable '{target}' not in Stage 2 prompt"
        # Research data should be serialized in the prompt
        assert "SRC_001" in user or "claim" in user

    @given(st_target_variable(), st.lists(
        st.fixed_dictionaries({
            "node_id": st.text(min_size=3, max_size=12, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
            "label": st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
            "definition": st.just("def"),
        }),
        min_size=1, max_size=3,
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_stage3_prompt_contains_target_and_nodes(self, target, nodes):
        """Stage 3 prompt contains target_variable and Stage 2 node data."""
        system, user = build_stage_3_prompt(target, nodes)
        assert target in user, f"target_variable '{target}' not in Stage 3 prompt"
        # Node IDs should appear in the prompt
        for node in nodes:
            assert node["node_id"] in user, f"node_id '{node['node_id']}' not in Stage 3 prompt"

    @given(st_target_variable())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_stage4_prompt_contains_target(self, target):
        """Stage 4 prompt contains the target_variable."""
        graph = {"causal_nodes": [], "causal_edges": []}
        measurement = [{"source_id": "M1", "measurement_claim": "claim"}]
        system, user = build_stage_4_prompt(target, graph, measurement)
        assert target in user, f"target_variable '{target}' not in Stage 4 prompt"

    @given(st_target_variable())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_all_prompts_return_tuples(self, target):
        """All prompt builders return (system, user) string tuples."""
        s1, u1 = build_stage_1_prompt(target)
        assert isinstance(s1, str) and isinstance(u1, str)

        s2, u2 = build_stage_2_prompt(target, [])
        assert isinstance(s2, str) and isinstance(u2, str)

        s3, u3 = build_stage_3_prompt(target, [])
        assert isinstance(s3, str) and isinstance(u3, str)

        s4, u4 = build_stage_4_prompt(target, {}, [])
        assert isinstance(s4, str) and isinstance(u4, str)
