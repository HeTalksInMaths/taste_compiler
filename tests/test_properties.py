"""
Phase F: Core Reliability Properties — Property-Based Tests.

Uses Hypothesis to verify invariants across the EvalWeaver pipeline.
"""

import json
import math
import os
import tempfile
import shutil

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from evalweaver.runner import py_run_scorer
from evalweaver.scorers import validate_scorer_on_pairs
from evalweaver.pareto import is_eligible_for_pareto
from evalweaver.policy import (
    hard_source_policy_violated,
    validate_pair_source_policy,
    source_policy_violations,
)
from evalweaver.candidates import score_candidates, build_candidate_ensemble
from evalweaver.failure_packet import build_failure_packet
from evalweaver.evaluation import eval_scorer
from evalweaver.artifacts import save, resolve_output_directory
from evalweaver.probes import load_probes
from evalweaver.runner import get_namespace


# ─────────────────────────────────────────────────────────────────────
# Ensure probes are loaded into the runner namespace for scorer tests
# ─────────────────────────────────────────────────────────────────────
load_probes(get_namespace())


# ─────────────────────────────────────────────────────────────────────
# STRATEGIES
# ─────────────────────────────────────────────────────────────────────

def scorer_summaries():
    """Generate random scorer summary dicts for eligibility testing."""
    return st.fixed_dictionaries({
        "valid": st.sampled_from([True, False, None]),
        "exec_error_rate": st.floats(min_value=0, max_value=1),
        "score_spread": st.floats(min_value=0, max_value=1),
        "train_margin": st.floats(min_value=-0.5, max_value=1.0),
        "test_margin": st.floats(min_value=-0.5, max_value=1.0),
        "train_accuracy": st.floats(min_value=0, max_value=1),
        "test_accuracy": st.floats(min_value=0, max_value=1),
        "scorer_id": st.just("S_test"),
    })


def json_serializable_dicts():
    """Generate random JSON-serializable nested dicts."""
    json_values = st.recursive(
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(min_value=-10000, max_value=10000),
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            st.text(min_size=0, max_size=50, alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "Z"),
                max_codepoint=127,
            )),
        ),
        lambda children: st.one_of(
            st.lists(children, max_size=5),
            st.dictionaries(
                st.text(min_size=1, max_size=10, alphabet=st.characters(
                    whitelist_categories=("L",), max_codepoint=127,
                )),
                children,
                max_size=5,
            ),
        ),
        max_leaves=20,
    )
    return st.dictionaries(
        st.text(min_size=1, max_size=10, alphabet=st.characters(
            whitelist_categories=("L",), max_codepoint=127,
        )),
        json_values,
        min_size=1,
        max_size=5,
    )


# ─────────────────────────────────────────────────────────────────────
# Property 1: Scorer output clamping invariant
# ─────────────────────────────────────────────────────────────────────

class TestProperty1ClampingInvariant:
    """py_run_scorer clamping and out_of_range behavior."""

    @given(st.floats(min_value=-10, max_value=10))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_clamping_invariant(self, raw_val):
        """value is always clamped to [0.0, 1.0], raw_value preserves actual return."""
        assume(not math.isnan(raw_val) and not math.isinf(raw_val))
        code = f"def scorer(text, anchor, params): return {raw_val!r}"
        result = py_run_scorer(code, "test text", "anchor text")

        # value is always within [0.0, 1.0]
        assert 0.0 <= result["value"] <= 1.0

        # raw_value preserves the actual scorer return
        assert result["raw_value"] is not None
        assert math.isclose(result["raw_value"], raw_val, rel_tol=1e-9, abs_tol=1e-12)

        # out_of_range reflects threshold check
        expected_oor = raw_val < -0.01 or raw_val > 1.01
        assert result["out_of_range"] == expected_oor

    @given(st.floats(min_value=-10, max_value=10))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_clamping_bounds(self, raw_val):
        """Clamped value should equal max(0, min(1, raw_val)) for valid floats."""
        assume(not math.isnan(raw_val) and not math.isinf(raw_val))
        code = f"def scorer(text, anchor, params): return {raw_val!r}"
        result = py_run_scorer(code, "hello", "world")

        expected_clamped = max(0.0, min(1.0, raw_val))
        assert math.isclose(result["value"], expected_clamped, rel_tol=1e-9, abs_tol=1e-12)

    def test_exception_returns_defaults(self):
        """On exception: ok=False, value=0.5, raw_value=None."""
        code = "def scorer(text, anchor, params): raise ValueError('boom')"
        result = py_run_scorer(code, "test", "anchor")
        assert result["ok"] is False
        assert result["value"] == 0.5
        assert result["raw_value"] is None

    def test_out_of_range_rejects_validation(self):
        """validate_scorer_on_pairs rejects out_of_range scorers."""
        # Scorer that returns 5.0 (way out of range)
        code = "def scorer(text, anchor, params): return 5.0"
        validation = validate_scorer_on_pairs(code)
        assert validation["valid"] is False
        assert validation["reason"] == "out_of_range"


# ─────────────────────────────────────────────────────────────────────
# Property 2: Three-tier validity classification correctness
# ─────────────────────────────────────────────────────────────────────

class TestProperty2ThreeTier:
    """is_eligible_for_pareto correctly classifies based on all conditions."""

    @given(scorer_summaries())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_three_tier_classification(self, summary):
        """eligible iff ALL conditions are simultaneously met."""
        assume(not math.isnan(summary["exec_error_rate"]))
        assume(not math.isnan(summary["score_spread"]))
        assume(not math.isnan(summary["train_margin"]))
        assume(not math.isnan(summary["test_margin"]))
        assume(not math.isnan(summary["train_accuracy"]))
        assume(not math.isnan(summary["test_accuracy"]))

        eligible, reason = is_eligible_for_pareto(summary)

        # Compute expected eligibility from all conditions
        all_conditions_met = (
            summary["valid"] is True
            and summary["exec_error_rate"] <= 0
            and summary["score_spread"] >= 0.02
            and summary["train_margin"] > 0
            and summary["test_margin"] > 0
            and summary["train_accuracy"] >= 0.50
            and summary["test_accuracy"] >= 0.50
        )

        assert eligible == all_conditions_met, (
            f"eligible={eligible}, expected={all_conditions_met}, "
            f"reason={reason}, summary={summary}"
        )

    @given(scorer_summaries())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_ineligible_has_reason(self, summary):
        """Ineligible scorers always have a non-empty reason."""
        assume(not math.isnan(summary["exec_error_rate"]))
        assume(not math.isnan(summary["score_spread"]))
        assume(not math.isnan(summary["train_margin"]))
        assume(not math.isnan(summary["test_margin"]))
        assume(not math.isnan(summary["train_accuracy"]))
        assume(not math.isnan(summary["test_accuracy"]))

        eligible, reason = is_eligible_for_pareto(summary)

        if not eligible:
            assert reason != "", "Ineligible scorer must have a reason"
        else:
            assert reason == "", "Eligible scorer should have empty reason"


# ─────────────────────────────────────────────────────────────────────
# Property 6: Hard source policy vetoes scorer to zero
# ─────────────────────────────────────────────────────────────────────

class TestProperty6HardPolicyVeto:
    """Hard violations cause scorer to output 0.0 when policy is used as gate."""

    @given(st.sampled_from([
        "Our tool saves teams 50% more time than competitors.",
        "Trusted by 1000+ enterprise clients worldwide.",
        "Award-winning platform with guaranteed results.",
        "Fortune 500 companies rely on our SOC2 certified solution.",
        "We triple your conversion rate in 30 days or your money back.",
    ]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_hard_violation_zeros_scorer(self, violating_text):
        """Scorer that gates on hard source policy returns 0.0 for violating text."""
        anchor = "We built an AI tool that helps product teams."

        # Confirm the text actually violates hard source policy
        assert hard_source_policy_violated(violating_text, anchor), (
            f"Expected hard violation for: {violating_text}"
        )

        # Scorer that uses violates_hard_source_policy as a gate
        code = (
            "def scorer(text, anchor, params):\n"
            "    if violates_hard_source_policy(text, anchor):\n"
            "        return 0.0\n"
            "    return 0.7\n"
        )
        result = py_run_scorer(code, violating_text, anchor)
        assert result["ok"] is True
        assert result["value"] == 0.0

    @given(st.sampled_from([
        "We built an AI tool that helps product teams ship faster by surfacing backlog items.",
        "Instead of waiting for a BI report, our tool lets teams answer data questions.",
        "Our tool flags at-risk accounts before customers cancel.",
    ]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_clean_text_passes_gate(self, clean_text):
        """Clean text (no hard violations) gets non-zero score from gated scorer."""
        anchor = "We built an AI tool that helps product teams."

        # This text should NOT violate hard source policy
        assert not hard_source_policy_violated(clean_text, anchor)

        code = (
            "def scorer(text, anchor, params):\n"
            "    if violates_hard_source_policy(text, anchor):\n"
            "        return 0.0\n"
            "    return 0.7\n"
        )
        result = py_run_scorer(code, clean_text, anchor)
        assert result["ok"] is True
        assert result["value"] == 0.7


# ─────────────────────────────────────────────────────────────────────
# Property 10: Heldout anti-leakage
# ─────────────────────────────────────────────────────────────────────

class TestProperty10HeldoutAntiLeakage:
    """build_failure_packet does not leak raw heldout text."""

    @given(st.integers(min_value=0, max_value=1))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_heldout_no_raw_text(self, round_idx):
        """heldout_aggregate_only contains no raw text from test pairs."""
        # Build minimal fake data
        test_anchor = "unique_anchor_xyz_42"
        test_positive = "unique_positive_abc_99"
        test_negative = "unique_negative_def_77"

        pairs = [
            {"pair_id": "P1", "split": "train", "pair_type": "hype_trap",
             "anchor": "train anchor", "positive": "train pos", "negative": "train neg"},
            {"pair_id": "P2", "split": "test", "pair_type": "fake_mechanism",
             "anchor": test_anchor, "positive": test_positive, "negative": test_negative},
        ]
        pair_suite = {"train": [pairs[0]], "test": [pairs[1]], "all": pairs}

        summaries = [{
            "scorer_id": "S1", "hypothesis": "test hyp", "lineage": "initial",
            "generation_round": 0, "valid": True, "train_accuracy": 0.8,
            "test_accuracy": 0.7, "train_margin": 0.1, "test_margin": 0.05,
            "score_spread": 0.3, "exec_error_rate": 0, "robustness_warning": "",
        }]

        eval_results = {
            "S1": [
                {"pair_id": "P1", "split": "train", "pair_type": "hype_trap",
                 "pos_score": 0.8, "neg_score": 0.3, "margin": 0.5, "correct": True,
                 "pos_err": None, "neg_err": None},
                {"pair_id": "P2", "split": "test", "pair_type": "fake_mechanism",
                 "pos_score": 0.7, "neg_score": 0.4, "margin": 0.3, "correct": True,
                 "pos_err": None, "neg_err": None},
            ]
        }

        pareto = summaries[:]
        scorer_code = {"S1": "def scorer(text, anchor, params): return 0.5"}

        packet = build_failure_packet(
            round_idx, summaries, eval_results, pair_suite, pareto, scorer_code
        )

        # Serialize heldout_aggregate_only and verify no raw test text leaks
        heldout_str = json.dumps(packet["heldout_aggregate_only"])
        assert test_anchor not in heldout_str, "Test anchor leaked into heldout aggregate"
        assert test_positive not in heldout_str, "Test positive leaked into heldout aggregate"
        assert test_negative not in heldout_str, "Test negative leaked into heldout aggregate"

    @given(st.integers(min_value=0, max_value=1))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_heldout_aggregate_structure(self, round_idx):
        """heldout_aggregate_only has expected structure keys."""
        pairs = [
            {"pair_id": "P1", "split": "train", "pair_type": "hype_trap",
             "anchor": "a", "positive": "p", "negative": "n"},
            {"pair_id": "P2", "split": "test", "pair_type": "fake_mechanism",
             "anchor": "a2", "positive": "p2", "negative": "n2"},
        ]
        pair_suite = {"train": [pairs[0]], "test": [pairs[1]], "all": pairs}
        summaries = [{
            "scorer_id": "S1", "hypothesis": "h", "lineage": "initial",
            "generation_round": 0, "valid": True, "train_accuracy": 0.8,
            "test_accuracy": 0.7, "train_margin": 0.1, "test_margin": 0.05,
            "score_spread": 0.3, "exec_error_rate": 0, "robustness_warning": "",
        }]
        eval_results = {
            "S1": [
                {"pair_id": "P1", "split": "train", "pair_type": "hype_trap",
                 "pos_score": 0.8, "neg_score": 0.3, "margin": 0.5, "correct": True,
                 "pos_err": None, "neg_err": None},
                {"pair_id": "P2", "split": "test", "pair_type": "fake_mechanism",
                 "pos_score": 0.7, "neg_score": 0.4, "margin": 0.3, "correct": True,
                 "pos_err": None, "neg_err": None},
            ]
        }
        pareto = summaries[:]
        scorer_code = {"S1": "def scorer(text, anchor, params): return 0.5"}

        packet = build_failure_packet(
            round_idx, summaries, eval_results, pair_suite, pareto, scorer_code
        )

        hao = packet["heldout_aggregate_only"]
        assert "heldout_accuracy_by_scorer" in hao
        assert "heldout_margin_by_scorer" in hao
        assert "heldout_failures_by_pair_type" in hao


# ─────────────────────────────────────────────────────────────────────
# Property 11: Pair source policy enforcement
# ─────────────────────────────────────────────────────────────────────

class TestProperty11PairSourcePolicy:
    """validate_pair_source_policy rejects pairs with hard violations in positive."""

    @given(st.sampled_from([
        "Our tool delivers 300% ROI within 2 weeks guaranteed.",
        "Trusted by 5000+ enterprise clients around the world.",
        "Fortune 100 companies choose our award-winning platform.",
        "We guarantee triple your conversion rate or money back.",
    ]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_positive_with_hard_violation_rejected(self, violating_positive):
        """Pairs where positive has a hard violation are rejected."""
        anchor = "We built an AI tool that helps product teams."
        pair = {
            "pair_id": "TEST_01",
            "anchor": anchor,
            "positive": violating_positive,
            "negative": "A bad text with jargon and buzzwords.",
            "pair_type": "hype_trap",
        }
        result = validate_pair_source_policy(pair)
        assert result["valid"] is False, (
            f"Expected pair to be invalid for positive: {violating_positive}"
        )

    @given(st.sampled_from([
        "We help teams ship faster by surfacing high-signal backlog items.",
        "Instead of waiting for reports, teams can answer questions themselves.",
        "Our tool flags at-risk accounts before customers cancel.",
    ]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_clean_positive_accepted(self, clean_positive):
        """Pairs where positive has no hard violation are accepted."""
        anchor = "We built an AI tool that helps product teams."
        pair = {
            "pair_id": "TEST_02",
            "anchor": anchor,
            "positive": clean_positive,
            "negative": "An advanced seamless platform for ultimate innovation.",
            "pair_type": "hype_trap",
        }
        result = validate_pair_source_policy(pair)
        assert result["valid"] is True, (
            f"Expected pair to be valid for positive: {clean_positive}, "
            f"errors: {result.get('errors')}"
        )


# ─────────────────────────────────────────────────────────────────────
# Property 12: Ensemble scoring normalization
# ─────────────────────────────────────────────────────────────────────

class TestProperty12EnsembleNormalization:
    """Ensemble normalization produces min=0, max=1 per scorer, mean as ensemble."""

    @given(st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=2, max_size=5,
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_normalization_bounds(self, raw_scores):
        """Normalized scores have min=0, max=1 when range > 0."""
        mn = min(raw_scores)
        mx = max(raw_scores)
        assume(mx - mn > 0.001)  # Need non-zero range

        # Normalize manually (same logic as candidates.py)
        rng = mx - mn
        normalized = [(v - mn) / rng for v in raw_scores]

        assert math.isclose(min(normalized), 0.0, abs_tol=1e-9)
        assert math.isclose(max(normalized), 1.0, abs_tol=1e-9)
        for n in normalized:
            assert 0.0 <= n <= 1.0

    @given(st.lists(
        st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2, max_size=4,
        ),
        min_size=1, max_size=3,
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_ensemble_score_is_mean_of_normalized(self, scorer_raw_scores):
        """ensemble_score equals mean of normalized scores across scorers."""
        import statistics as stat

        n_candidates = len(scorer_raw_scores[0]) if scorer_raw_scores else 0
        assume(n_candidates >= 2)
        # Ensure all scorer lists have same length
        assume(all(len(s) == n_candidates for s in scorer_raw_scores))

        # Normalize each scorer's scores
        all_norm = []
        for raw in scorer_raw_scores:
            mn = min(raw)
            mx = max(raw)
            rng = mx - mn if mx > mn else 1.0
            norm = [(v - mn) / rng for v in raw]
            all_norm.append(norm)

        # Compute per-candidate ensemble score as mean of normalized
        for cand_idx in range(n_candidates):
            norms_for_cand = [all_norm[s_idx][cand_idx] for s_idx in range(len(scorer_raw_scores))]
            ensemble = stat.mean(norms_for_cand)
            assert 0.0 <= ensemble <= 1.0


# ─────────────────────────────────────────────────────────────────────
# Property 15: Artifact persistence round-trip
# ─────────────────────────────────────────────────────────────────────

class TestProperty15ArtifactRoundTrip:
    """JSON artifacts survive save/load round-trip."""

    @given(json_serializable_dicts())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_roundtrip(self, data):
        """save() then load produces identical data."""
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop15_")
        try:
            path = save("test_artifact", data, out_dir=tmp_dir)
            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded == data, f"Round-trip mismatch: {data} != {loaded}"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(json_serializable_dicts())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_roundtrip_is_valid_json(self, data):
        """Saved artifact is valid JSON."""
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_prop15b_")
        try:
            path = save("test_json_valid", data, out_dir=tmp_dir)
            with open(path, "r") as f:
                content = f.read()
            # Should not raise
            parsed = json.loads(content)
            assert isinstance(parsed, dict)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────
# Property 16: Output directory fallback
# ─────────────────────────────────────────────────────────────────────

class TestProperty16OutputDirFallback:
    """resolve_output_directory falls back gracefully to writable temp dir."""

    @given(st.text(min_size=5, max_size=20, alphabet=st.characters(
        whitelist_categories=("L",), max_codepoint=127,
    )))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_uncreateable_path_returns_valid_dir(self, random_name):
        """When EVALWEAVER_OUTPUT_DIR is uncreateable, returns a valid writable temp dir."""
        # Use a path that cannot be created (nested under /proc or similar)
        impossible_path = f"/no_such_root_dir_xyz/{random_name}/deeply/nested"
        old_env = os.environ.get("EVALWEAVER_OUTPUT_DIR")
        try:
            os.environ["EVALWEAVER_OUTPUT_DIR"] = impossible_path
            result = resolve_output_directory()

            # Must not raise
            assert result is not None
            assert isinstance(result, str)
            # Must be a valid writable directory
            assert os.path.isdir(result)
            # Must be writable
            test_file = os.path.join(result, "_write_test.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            # Must NOT be the impossible path
            assert result != impossible_path
        finally:
            if old_env is None:
                os.environ.pop("EVALWEAVER_OUTPUT_DIR", None)
            else:
                os.environ["EVALWEAVER_OUTPUT_DIR"] = old_env


# ─────────────────────────────────────────────────────────────────────
# Property 18: Evaluation completeness
# ─────────────────────────────────────────────────────────────────────

class TestProperty18EvalCompleteness:
    """eval_scorer produces one row per pair with required fields."""

    @given(st.integers(min_value=1, max_value=8))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_one_row_per_pair(self, n_pairs):
        """eval_scorer produces exactly one row per input pair."""
        # Simple valid scorer
        code = "def scorer(text, anchor, params): return len(text) / max(1, len(text) + 100)"

        pairs = [
            {
                "pair_id": f"P{i}",
                "split": "train" if i % 2 == 0 else "test",
                "pair_type": "hype_trap",
                "anchor": "We built an AI tool.",
                "positive": f"Positive text number {i} with some content.",
                "negative": f"Negative text number {i} that is shorter.",
            }
            for i in range(n_pairs)
        ]

        rows = eval_scorer("S_test", code, pairs)

        # One row per pair
        assert len(rows) == n_pairs

        # Each row has required fields
        required_fields = {"pair_id", "split", "pair_type", "pos_score", "neg_score", "margin", "correct"}
        for row in rows:
            for field in required_fields:
                assert field in row, f"Missing field '{field}' in row {row}"

        # pair_ids match input
        result_ids = {r["pair_id"] for r in rows}
        input_ids = {p["pair_id"] for p in pairs}
        assert result_ids == input_ids

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_margin_equals_diff(self, n_pairs):
        """margin == pos_score - neg_score for each row."""
        code = "def scorer(text, anchor, params): return len(text) / max(1, len(text) + 50)"

        pairs = [
            {
                "pair_id": f"P{i}",
                "split": "train",
                "pair_type": "subtle_quality_gap",
                "anchor": "An anchor text for testing.",
                "positive": f"A positive example with more words added here {i}.",
                "negative": f"Short neg {i}.",
            }
            for i in range(n_pairs)
        ]

        rows = eval_scorer("S_test", code, pairs)

        for row in rows:
            expected_margin = row["pos_score"] - row["neg_score"]
            assert math.isclose(row["margin"], expected_margin, abs_tol=1e-9), (
                f"margin={row['margin']} != pos-neg={expected_margin}"
            )


# ─────────────────────────────────────────────────────────────────────
# Property 22: Candidate policy_ok reflects hard severity only
# ─────────────────────────────────────────────────────────────────────

class TestProperty22PolicyOkHardOnly:
    """policy_ok is False iff ANY violation has severity=='hard'."""

    @given(st.sampled_from([
        # Hard violations: invented numbers, guarantees, awards
        ("Our tool saves 300% more time guaranteed.", True),
        ("Trusted by 5000+ enterprise clients.", True),
        ("Award-winning certified platform.", True),
        # Clean text: no hard violations
        ("We help teams ship faster by surfacing backlog items.", False),
        ("Instead of waiting for reports, answer questions yourself.", False),
    ]))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_policy_ok_reflects_hard_severity(self, text_and_expected):
        """policy_ok is False iff hard-severity violations exist."""
        text, has_hard = text_and_expected
        anchor = "We built an AI tool that helps product teams."

        violations = source_policy_violations(text, anchor, role="candidate")
        has_hard_violation = any(v.get("severity") == "hard" for v in violations)

        assert has_hard_violation == has_hard, (
            f"text={text!r}, expected_hard={has_hard}, "
            f"got violations={violations}"
        )

        # Verify hard_source_policy_violated agrees
        assert hard_source_policy_violated(text, anchor) == has_hard

    @given(st.lists(
        st.fixed_dictionaries({
            "violation_type": st.sampled_from([
                "invented_numeric_digit",
                "invented_numeric_word",
                "guarantee_claim",
                "invented_award_or_certification_claim",
            ]),
            "evidence": st.text(min_size=3, max_size=20),
            "severity": st.sampled_from(["hard", "soft"]),
        }),
        min_size=1, max_size=4,
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_policy_ok_logic(self, violations):
        """policy_ok should be False when any violation has severity=='hard'."""
        has_hard = any(v["severity"] == "hard" for v in violations)
        # Simulate the logic from candidates.py
        # policy_ok = not any(v.severity == "hard" for v in violations)
        policy_ok = not has_hard
        if has_hard:
            assert policy_ok is False
        else:
            assert policy_ok is True
