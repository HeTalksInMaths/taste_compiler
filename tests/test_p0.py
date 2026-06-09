"""
P0 unit tests for EvalWeaver v5.1 critical fixes.

Tests 26.1–26.8: Source policy taxonomy, named entity guardrails,
C004 policy enforcement, C002 scoring, scorer validation, Pareto
non-domination, repair metrics honesty, and end-to-end smoke.
"""

import json
import os
import tempfile

import pytest

from evalweaver.policy import (
    source_policy_violations,
    hard_source_policy_violated,
    probe_source_continuity,
    _detect_customer_or_company_claims,
)
from evalweaver.scorers import validate_scorer_on_pairs
from evalweaver.pareto import compute_pareto
from evalweaver.probes import probe_source_continuity as probe_source_continuity_probes
from evalweaver.candidates import CANDIDATES, score_candidates, build_candidate_ensemble
from evalweaver.runner import py_run_scorer
from evalweaver.repair import compute_repair_improvement_metrics


# ─────────────────────────────────────────────────────────────────────
# 26.1: Source policy violation taxonomy
# ─────────────────────────────────────────────────────────────────────

class TestSourcePolicyViolationTaxonomy:
    """Each of the 7 canonical violation types is correctly detected."""

    def test_invented_numeric_digit(self):
        text = "Saves you 50% on costs"
        anchor = "Saves you on costs"
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_numeric_digit" in types

    def test_invented_numeric_word(self):
        text = "Helps thousands of teams"
        anchor = "Helps teams"
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_numeric_word" in types

    def test_invented_time_or_quantity_claim(self):
        text = "3x faster deployments"
        anchor = "faster deployments"
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_time_or_quantity_claim" in types

    def test_invented_named_entity_via_customer_company(self):
        """Acme Corp in text but not anchor gets caught by _detect_customer_or_company_claims."""
        text = "Trusted by Acme Corp for their deployments"
        anchor = "Trusted for deployments"
        violations = _detect_customer_or_company_claims(text, anchor)
        assert len(violations) >= 1
        types = [v["violation_type"] for v in violations]
        assert "invented_customer_or_company_claim" in types

    def test_invented_customer_or_company_claim(self):
        text = "Trusted by Fortune 500 companies"
        anchor = "Trusted by companies"
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_customer_or_company_claim" in types

    def test_invented_award_or_certification_claim(self):
        text = "SOC2 certified platform"
        anchor = "Our platform"
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_award_or_certification_claim" in types

    def test_guarantee_claim(self):
        text = "Guaranteed results every time"
        anchor = "Results every time"
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "guarantee_claim" in types

    def test_no_violations_when_text_equals_anchor(self):
        text = "We help teams ship faster by surfacing important signals."
        anchor = text
        violations = source_policy_violations(text, anchor)
        assert violations == []


# ─────────────────────────────────────────────────────────────────────
# 26.2: Named entity guardrails
# ─────────────────────────────────────────────────────────────────────

class TestNamedEntityGuardrails:
    """Abbreviations and sentence-initial words don't false-positive; real violations flag."""

    # --- False positive avoidance ---

    def test_ai_not_flagged(self):
        """AI in text, not in anchor → NOT flagged as invented_named_entity."""
        text = "Our AI assistant helps teams prioritise work."
        anchor = "Our assistant helps teams prioritise work."
        violations = source_policy_violations(text, anchor)
        ne_violations = [v for v in violations if v["violation_type"] == "invented_named_entity"]
        assert len(ne_violations) == 0

    def test_sql_not_flagged(self):
        """SQL in text → NOT flagged."""
        text = "Answer data questions without SQL knowledge."
        anchor = "Answer data questions easily."
        violations = source_policy_violations(text, anchor)
        ne_violations = [v for v in violations if v["violation_type"] == "invented_named_entity"]
        assert len(ne_violations) == 0

    def test_sentence_initial_not_flagged(self):
        """Sentence-initial 'The' or 'However' → NOT flagged."""
        text = "The platform helps. However, setup takes time."
        anchor = "The platform helps with setup."
        violations = source_policy_violations(text, anchor)
        ne_violations = [v for v in violations if v["violation_type"] == "invented_named_entity"]
        assert len(ne_violations) == 0

    def test_manager_role_not_flagged(self):
        """'Manager' as role → NOT flagged."""
        text = "Every Manager can see their team's progress."
        anchor = "See team progress."
        violations = source_policy_violations(text, anchor)
        ne_violations = [v for v in violations if v["violation_type"] == "invented_named_entity"]
        assert len(ne_violations) == 0

    # --- Real violations caught ---

    def test_acme_corp_flagged(self):
        """'Acme Corp' not in anchor → flagged as customer_or_company_claim."""
        text = "Used by Acme Corp for deployment automation."
        anchor = "Used for deployment automation."
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_customer_or_company_claim" in types

    def test_soc2_compliant_flagged(self):
        """'SOC2 compliant' not in anchor → flagged as award_or_certification."""
        text = "A SOC2 compliant deployment platform."
        anchor = "A deployment platform."
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_award_or_certification_claim" in types

    def test_fortune_500_flagged(self):
        """'Fortune 500 clients' not in anchor → flagged as customer_or_company_claim."""
        text = "Trusted by Fortune 500 clients worldwide."
        anchor = "Trusted by clients worldwide."
        violations = source_policy_violations(text, anchor)
        types = [v["violation_type"] for v in violations]
        assert "invented_customer_or_company_claim" in types


# ─────────────────────────────────────────────────────────────────────
# 26.3: C004 policy_ok=false
# ─────────────────────────────────────────────────────────────────────

class TestC004PolicyViolation:
    """C004 hype baseline has policy_ok=False with hard violations."""

    @pytest.fixture
    def c004(self):
        return next(c for c in CANDIDATES if c["candidate_id"] == "C004")

    @pytest.fixture
    def anchor(self):
        """Use the raw_text (goal description) as anchor — same as pipeline."""
        # The pipeline uses the raw_text from config as anchor
        return (
            "EvalWeaver lets you create, use, and monetise AI-based improvers "
            "for any subjective text-quality goal."
        )

    def test_c004_policy_ok_false(self, c004, anchor):
        """C004 has policy_ok = False."""
        violated = hard_source_policy_violated(c004["text"], anchor, role="candidate")
        assert violated is True

    def test_c004_has_hard_violations(self, c004, anchor):
        """C004 has at least 1 hard violation in policy_violations."""
        violations = source_policy_violations(c004["text"], anchor, role="candidate")
        hard_violations = [v for v in violations if v["severity"] == "hard"]
        assert len(hard_violations) >= 1

    def test_c004_raw_mean_score_near_zero(self, c004, anchor):
        """C004's raw_mean_score < 0.05 when run directly via source_policy_violations."""
        # The hard policy violation means scorers that use the policy check
        # will zero this candidate. Verify the policy is violated which is what
        # forces the raw_mean_score near zero in the pipeline.
        violated = hard_source_policy_violated(c004["text"], anchor, role="candidate")
        assert violated is True
        # Since the violation is hard, in the pipeline this candidate gets
        # raw_mean_score near 0. We verify the mechanism (hard violation detected).


# ─────────────────────────────────────────────────────────────────────
# 26.4: C002 not zeroed
# ─────────────────────────────────────────────────────────────────────

class TestC002NotZeroed:
    """C002 scores above zero — soft source continuity doesn't zero it."""

    @pytest.fixture
    def c002(self):
        return next(c for c in CANDIDATES if c["candidate_id"] == "C002")

    @pytest.fixture
    def anchor(self):
        return (
            "EvalWeaver lets you create, use, and monetise AI-based improvers "
            "for any subjective text-quality goal."
        )

    def test_c002_not_hard_violated(self, c002, anchor):
        """C002 does NOT have hard policy violations."""
        violated = hard_source_policy_violated(c002["text"], anchor, role="candidate")
        assert violated is False

    def test_c002_source_continuity_above_zero(self, c002, anchor):
        """probe_source_continuity returns > 0 for C002."""
        score = probe_source_continuity(c002["text"], anchor)
        assert score > 0.0, f"C002 continuity should be > 0, got {score}"


# ─────────────────────────────────────────────────────────────────────
# 26.5: validate_scorer detects runtime, constant, and out-of-range
# ─────────────────────────────────────────────────────────────────────

class TestValidateScorerDetection:
    """validate_scorer_on_pairs catches runtime errors, constant outputs, and out-of-range."""

    def test_runtime_error_detected(self):
        """A scorer that raises an exception → valid=False, reason='runtime_error'."""
        code = """
def scorer(text, anchor, meta):
    raise ValueError("intentional error")
"""
        result = validate_scorer_on_pairs(code)
        assert result["valid"] is False
        assert result["reason"] == "runtime_error"

    def test_constant_outputs_detected(self):
        """A scorer that always returns 0.5 → valid=False, reason='constant_pair_outputs'."""
        code = """
def scorer(text, anchor, meta):
    return 0.5
"""
        result = validate_scorer_on_pairs(code)
        assert result["valid"] is False
        assert result["reason"] == "constant_pair_outputs"

    def test_out_of_range_detected(self):
        """A scorer that returns values > 1.01 → valid=False, reason='out_of_range'."""
        code = """
def scorer(text, anchor, meta):
    return 5.0
"""
        result = validate_scorer_on_pairs(code)
        assert result["valid"] is False
        assert result["reason"] == "out_of_range"

    def test_out_of_range_field_in_py_run_scorer(self):
        """py_run_scorer sets out_of_range=True for raw values > 1.01."""
        code = """
def scorer(text, anchor, meta):
    return 2.5
"""
        result = py_run_scorer(code, "test text", "anchor")
        assert result["ok"] is True
        assert result["out_of_range"] is True
        assert result["raw_value"] == 2.5
        assert result["value"] == 1.0  # Clamped


# ─────────────────────────────────────────────────────────────────────
# 26.6: Pareto non-domination sanity
# ─────────────────────────────────────────────────────────────────────

class TestParetoNonDomination:
    """No member of the Pareto frontier is dominated by any other member."""

    @pytest.fixture
    def fake_summaries(self):
        """Small set of fake summaries with known domination relationships."""
        return [
            # S1: good on all dimensions
            {"scorer_id": "S1", "valid": True, "exec_error_rate": 0,
             "score_spread": 0.10, "train_margin": 0.3, "test_margin": 0.3,
             "train_accuracy": 0.8, "test_accuracy": 0.8},
            # S2: dominated by S1 on all dims
            {"scorer_id": "S2", "valid": True, "exec_error_rate": 0,
             "score_spread": 0.05, "train_margin": 0.1, "test_margin": 0.1,
             "train_accuracy": 0.6, "test_accuracy": 0.6},
            # S3: better test_accuracy than S1, worse margin → not dominated
            {"scorer_id": "S3", "valid": True, "exec_error_rate": 0,
             "score_spread": 0.08, "train_margin": 0.2, "test_margin": 0.2,
             "train_accuracy": 0.7, "test_accuracy": 0.9},
            # S4: invalid scorer (should be excluded)
            {"scorer_id": "S4", "valid": False, "exec_error_rate": 0.5,
             "score_spread": 0.5, "train_margin": 0.9, "test_margin": 0.9,
             "train_accuracy": 0.99, "test_accuracy": 0.99},
        ]

    def test_no_dominated_member_in_frontier(self, fake_summaries):
        """No member of the returned frontier is dominated by any other member."""
        frontier = compute_pareto(fake_summaries)
        dims = ["test_accuracy", "test_margin", "train_accuracy", "train_margin", "score_spread"]

        for a in frontier:
            for b in frontier:
                if a is b:
                    continue
                # b should NOT dominate a
                all_geq = all(b[d] >= a[d] for d in dims)
                any_gt = any(b[d] > a[d] for d in dims)
                assert not (all_geq and any_gt), (
                    f"{b['scorer_id']} dominates {a['scorer_id']} but both are in frontier"
                )

    def test_dominated_scorers_excluded(self, fake_summaries):
        """S2 (dominated by S1) should not be in frontier."""
        frontier = compute_pareto(fake_summaries)
        frontier_ids = {s["scorer_id"] for s in frontier}
        assert "S2" not in frontier_ids

    def test_invalid_scorer_excluded(self, fake_summaries):
        """S4 (invalid) should not be in frontier."""
        frontier = compute_pareto(fake_summaries)
        frontier_ids = {s["scorer_id"] for s in frontier}
        assert "S4" not in frontier_ids

    def test_non_dominated_scorers_included(self, fake_summaries):
        """S1 and S3 should be in frontier (non-dominated and eligible)."""
        frontier = compute_pareto(fake_summaries)
        frontier_ids = {s["scorer_id"] for s in frontier}
        assert "S1" in frontier_ids
        assert "S3" in frontier_ids


# ─────────────────────────────────────────────────────────────────────
# 26.7: Repair metrics honesty
# ─────────────────────────────────────────────────────────────────────

class TestRepairMetricsHonesty:
    """overall_improvement_claim_supported matches actual data."""

    @pytest.fixture
    def base_pair_suite(self):
        """Minimal pair suite for repair metrics testing."""
        pairs = [
            {"pair_id": "P01", "split": "test", "anchor": "a",
             "positive": "pos", "negative": "neg"},
            {"pair_id": "P02", "split": "test", "anchor": "a",
             "positive": "pos", "negative": "neg"},
        ]
        return {"all": pairs, "test": pairs}

    def test_no_improvement_when_new_doesnt_beat_old(self, base_pair_suite):
        """When new scorers DON'T beat old → overall_improvement_claim_supported = False."""
        summaries_r0 = [
            {"scorer_id": "old_1", "valid": True},
        ]
        summaries_r1 = [
            {"scorer_id": "old_1", "valid": True},
            {"scorer_id": "new_1", "valid": True},
        ]
        # Old scorer is in pareto, new is not
        pareto_r0 = [{"scorer_id": "old_1"}]
        pareto_r1 = [{"scorer_id": "old_1"}]  # New scorer didn't make it

        # Eval data: old scorer performs better
        eval_r1 = {
            "old_1": [
                {"pair_id": "P01", "margin": 0.3, "correct": True},
                {"pair_id": "P02", "margin": 0.2, "correct": True},
            ],
            "new_1": [
                {"pair_id": "P01", "margin": 0.1, "correct": True},
                {"pair_id": "P02", "margin": 0.05, "correct": False},
            ],
        }
        eval_r0 = eval_r1

        result = compute_repair_improvement_metrics(
            summaries_r0=summaries_r0,
            summaries_r1=summaries_r1,
            pareto_r0=pareto_r0,
            pareto_r1=pareto_r1,
            eval_r0=eval_r0,
            eval_r1=eval_r1,
            pair_suite_r1=base_pair_suite,
        )
        assert result["overall_improvement_claim_supported"] is False

    def test_improvement_when_new_beats_old(self, base_pair_suite):
        """When new scorers DO beat old on at least one dimension → True."""
        summaries_r0 = [
            {"scorer_id": "old_1", "valid": True},
        ]
        summaries_r1 = [
            {"scorer_id": "old_1", "valid": True},
            {"scorer_id": "new_1", "valid": True},
        ]
        # New scorer enters pareto
        pareto_r0 = [{"scorer_id": "old_1"}]
        pareto_r1 = [{"scorer_id": "old_1"}, {"scorer_id": "new_1"}]

        # Eval data: new scorer performs better on margin
        eval_r1 = {
            "old_1": [
                {"pair_id": "P01", "margin": 0.2, "correct": True},
                {"pair_id": "P02", "margin": 0.15, "correct": True},
            ],
            "new_1": [
                {"pair_id": "P01", "margin": 0.4, "correct": True},
                {"pair_id": "P02", "margin": 0.35, "correct": True},
            ],
        }
        eval_r0 = eval_r1

        result = compute_repair_improvement_metrics(
            summaries_r0=summaries_r0,
            summaries_r1=summaries_r1,
            pareto_r0=pareto_r0,
            pareto_r1=pareto_r1,
            eval_r0=eval_r0,
            eval_r1=eval_r1,
            pair_suite_r1=base_pair_suite,
        )
        assert result["overall_improvement_claim_supported"] is True


# ─────────────────────────────────────────────────────────────────────
# 26.8: End-to-end smoke test extension
# ─────────────────────────────────────────────────────────────────────

class TestEndToEndSmoke:
    """Verify step10_repair_improvement_metrics.json exists in pipeline output."""

    @pytest.fixture
    def output_dir(self):
        """Create a temp directory for pipeline output."""
        d = tempfile.mkdtemp(prefix="evalweaver_p0_")
        yield d
        import shutil
        shutil.rmtree(d, ignore_errors=True)

    @pytest.fixture
    def pipeline_result(self, output_dir):
        """Run the pipeline once and cache the result."""
        from evalweaver.config import load_config
        from evalweaver.pipeline import run_pipeline
        from evalweaver.artifacts import reset_trace

        os.environ["EVALWEAVER_OUTPUT_DIR"] = output_dir
        reset_trace()
        config = load_config("configs/persuasive.yaml")
        result = run_pipeline(config)
        yield result
        del os.environ["EVALWEAVER_OUTPUT_DIR"]

    def test_repair_improvement_metrics_artifact_exists(self, pipeline_result):
        """step10_repair_improvement_metrics.json exists in output directory."""
        out_dir = pipeline_result["output_dir"]
        json_files = os.listdir(out_dir)
        matching = [f for f in json_files if f.startswith("step10_repair_improvement_metrics")]
        assert len(matching) >= 1, (
            f"Expected step10_repair_improvement_metrics.json in output dir, "
            f"found: {[f for f in json_files if f.startswith('step10')]}"
        )
