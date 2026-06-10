"""Full pipeline integration test.

Runs the complete audit pipeline on the email_agent fixture and verifies:
1. All output files are created in correct locations
2. Report includes Hackathon Agent Architecture Summary section
3. Determinism: running twice produces identical output
4. Pipeline exit codes work correctly
"""

import json
from pathlib import Path

import pytest
import yaml

from agentbattery.cli import run_audit


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "email_agent"


@pytest.fixture
def audit_output(tmp_path):
    """Run full audit pipeline and return output directory."""
    # Copy example to tmp_path to avoid polluting the repo
    import shutil
    target = tmp_path / "email_agent"
    shutil.copytree(EXAMPLE_DIR, target)

    # Run full audit
    exit_code = run_audit(
        target=target,
        generate_tests_flag=True,
        report_flag=True,
        ci=True,
        threshold="HIGH",
    )

    return {
        "target": target,
        "out_dir": target / ".agentbattery",
        "exit_code": exit_code,
    }


class TestOutputFilesCreated:
    """Verify all output files are created in correct locations."""

    def test_agentbattery_directory_created(self, audit_output):
        assert audit_output["out_dir"].is_dir()

    def test_contract_yaml_exists(self, audit_output):
        assert (audit_output["out_dir"] / "contract.yaml").is_file()

    def test_obligations_yaml_exists(self, audit_output):
        assert (audit_output["out_dir"] / "obligations.yaml").is_file()

    def test_findings_yaml_exists(self, audit_output):
        assert (audit_output["out_dir"] / "findings.yaml").is_file()

    def test_repair_input_json_exists(self, audit_output):
        assert (audit_output["out_dir"] / "repair_input.json").is_file()

    def test_generated_tests_directory_exists(self, audit_output):
        tests_dir = audit_output["out_dir"] / "generated_tests"
        assert tests_dir.is_dir()
        # Should have at least one generated test
        yaml_files = list(tests_dir.glob("*.yaml"))
        assert len(yaml_files) > 0

    def test_reports_directory_exists(self, audit_output):
        reports_dir = audit_output["out_dir"] / "reports"
        assert reports_dir.is_dir()

    def test_latest_md_exists(self, audit_output):
        assert (audit_output["out_dir"] / "reports" / "latest.md").is_file()

    def test_latest_json_exists(self, audit_output):
        assert (audit_output["out_dir"] / "reports" / "latest.json").is_file()

    def test_exit_code_is_one_for_findings(self, audit_output):
        """Exit code should be 1 when findings exist above threshold."""
        assert audit_output["exit_code"] == 1


class TestReportContent:
    """Verify report content meets requirements."""

    def test_markdown_report_has_architecture_summary(self, audit_output):
        """Report must include Hackathon Agent Architecture Summary section."""
        md_path = audit_output["out_dir"] / "reports" / "latest.md"
        content = md_path.read_text()
        assert "Agent Architecture Summary" in content or "Architecture Summary" in content

    def test_markdown_report_has_required_sections(self, audit_output):
        md_path = audit_output["out_dir"] / "reports" / "latest.md"
        content = md_path.read_text()
        # Check for key sections
        assert "Summary" in content
        assert "Finding" in content or "finding" in content

    def test_json_report_is_valid(self, audit_output):
        """JSON report must be parseable."""
        json_path = audit_output["out_dir"] / "reports" / "latest.json"
        data = json.loads(json_path.read_text())
        assert isinstance(data, dict)
        assert "findings" in data or "summary" in data

    def test_repair_input_json_is_valid(self, audit_output):
        """repair_input.json must be valid JSON with correct schema."""
        repair_path = audit_output["out_dir"] / "repair_input.json"
        data = json.loads(repair_path.read_text())
        assert isinstance(data, dict)
        assert "findings" in data
        assert "generated_at" in data
        assert isinstance(data["findings"], list)
        if data["findings"]:
            finding = data["findings"][0]
            assert "finding_id" in finding
            assert "severity" in finding
            assert "gap_type" in finding
            assert "recommended_repair_type" in finding


class TestPipelineDeterminism:
    """Verify running the pipeline twice produces identical output."""

    def test_deterministic_output(self, tmp_path):
        """Running the audit twice on the same input produces identical output."""
        import shutil

        # First run
        target1 = tmp_path / "run1"
        shutil.copytree(EXAMPLE_DIR, target1)
        run_audit(target=target1, generate_tests_flag=True, report_flag=True, ci=True, threshold="HIGH")

        # Second run
        target2 = tmp_path / "run2"
        shutil.copytree(EXAMPLE_DIR, target2)
        run_audit(target=target2, generate_tests_flag=True, report_flag=True, ci=True, threshold="HIGH")

        # Compare key output files
        out1 = target1 / ".agentbattery"
        out2 = target2 / ".agentbattery"

        # Contract should be identical
        contract1 = yaml.safe_load((out1 / "contract.yaml").read_text())
        contract2 = yaml.safe_load((out2 / "contract.yaml").read_text())
        assert contract1 == contract2, "contract.yaml differs between runs"

        # Obligations should be identical
        obligations1 = yaml.safe_load((out1 / "obligations.yaml").read_text())
        obligations2 = yaml.safe_load((out2 / "obligations.yaml").read_text())
        assert obligations1 == obligations2, "obligations.yaml differs between runs"

        # Findings should be identical
        findings1 = yaml.safe_load((out1 / "findings.yaml").read_text())
        findings2 = yaml.safe_load((out2 / "findings.yaml").read_text())
        assert findings1 == findings2, "findings.yaml differs between runs"

        # JSON report should be identical (excluding timestamp)
        json1 = json.loads((out1 / "reports" / "latest.json").read_text())
        json2 = json.loads((out2 / "reports" / "latest.json").read_text())
        # Remove non-deterministic timestamp field before comparison
        json1.pop("generated_at", None)
        json2.pop("generated_at", None)
        assert json1 == json2, "latest.json differs between runs"

        # Generated tests count should be identical
        tests1 = list((out1 / "generated_tests").glob("*.yaml"))
        tests2 = list((out2 / "generated_tests").glob("*.yaml"))
        assert len(tests1) == len(tests2), "Different number of generated tests between runs"
