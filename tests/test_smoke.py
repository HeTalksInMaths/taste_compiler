"""End-to-end smoke test for the modularized EvalWeaver pipeline."""

import json
import os
import tempfile

import pytest

from evalweaver.config import load_config
from evalweaver.pipeline import run_pipeline
from evalweaver.artifacts import reset_trace


@pytest.fixture
def output_dir():
    """Create a temp directory for pipeline output."""
    d = tempfile.mkdtemp(prefix="evalweaver_smoke_")
    yield d
    # Cleanup not strictly needed for temp dirs, but good practice
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def pipeline_result(output_dir):
    """Run the pipeline once and cache the result for all tests."""
    os.environ["EVALWEAVER_OUTPUT_DIR"] = output_dir
    reset_trace()
    config = load_config("configs/persuasive.yaml")
    result = run_pipeline(config)
    yield result
    del os.environ["EVALWEAVER_OUTPUT_DIR"]


class TestPipelineSmoke:
    """Smoke tests verifying the modularized pipeline produces correct outputs."""

    def test_pipeline_succeeds(self, pipeline_result):
        """Pipeline completes without error."""
        assert pipeline_result["success"] is True

    def test_at_least_one_valid_scorer(self, pipeline_result):
        """At least one scorer is valid in R0."""
        pareto = pipeline_result["pareto_r1"]
        assert len(pareto) >= 1, "Expected at least one scorer in Pareto frontier"

    def test_pareto_frontier_nonempty(self, pipeline_result):
        """Pareto frontier is non-empty after R1."""
        pareto = pipeline_result["pareto_r1"]
        assert len(pareto) > 0, "Pareto frontier should be non-empty"

    def test_candidate_selected(self, pipeline_result):
        """A candidate is selected."""
        assert pipeline_result["selected_candidate"] is not None
        assert "candidate_id" in pipeline_result["selected_candidate"]
        assert "text" in pipeline_result["selected_candidate"]

    def test_json_artifacts_produced(self, pipeline_result):
        """JSON artifacts are produced in the output directory."""
        out_dir = pipeline_result["output_dir"]
        json_files = [f for f in os.listdir(out_dir) if f.endswith(".json")]
        # Should have at least the core artifacts
        expected_prefixes = [
            "step1_", "step2_", "step3_", "step4a_", "step4b_",
            "step5_", "step6_", "step7_", "step8a_", "step8b_",
            "step9_", "step10_", "step11_", "step12_",
            "trace", "run_summary",
        ]
        for prefix in expected_prefixes:
            matching = [f for f in json_files if f.startswith(prefix)]
            assert len(matching) >= 1, f"Missing artifact with prefix '{prefix}'"

    def test_zip_archive_produced(self, pipeline_result):
        """ZIP archive is created."""
        zip_path = pipeline_result.get("zip_path")
        assert zip_path is not None
        assert os.path.exists(zip_path)

    def test_hype_baseline_zeroed(self, pipeline_result):
        """C004 hype baseline scores near zero."""
        scored = pipeline_result["scored_candidates"]
        c004 = next(c for c in scored if c["candidate_id"] == "C004")
        assert c004["ensemble_score"] < 0.05, f"Hype baseline should be near 0, got {c004['ensemble_score']}"

    def test_c002_not_zeroed(self, pipeline_result):
        """C002 audience_pain is not zeroed (F4 fix check)."""
        scored = pipeline_result["scored_candidates"]
        c002 = next(c for c in scored if c["candidate_id"] == "C002")
        assert c002["ensemble_score"] > 0.05, f"C002 should score > 0.05, got {c002['ensemble_score']}"

    def test_criteria_mostly_pass(self, pipeline_result):
        """Most spec criteria pass, no hard failures."""
        assert pipeline_result["fail_count"] == 0, "Expected no criteria failures"
        assert pipeline_result["pass_count"] >= 15, "Expected at least 15 passing criteria"

    def test_run_summary_structure(self, pipeline_result):
        """Run summary JSON has expected structure."""
        out_dir = pipeline_result["output_dir"]
        summary_path = os.path.join(out_dir, "run_summary_v5.json")
        assert os.path.exists(summary_path)
        with open(summary_path) as f:
            summary = json.load(f)
        assert summary["version"] == "v5.1"
        assert summary["goal"] == "persuasive"
        assert "counts" in summary
        assert "r1_best" in summary
        assert summary["selected_candidate"] is not None
