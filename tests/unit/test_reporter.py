"""Unit tests for llm_agent_battery.reporter module."""

import json
import tempfile
from pathlib import Path

from llm_agent_battery.models import Finding, FindingCategory, ScanResult, Severity
from llm_agent_battery.reporter import generate_reports


def _finding(
    severity=Severity.MEDIUM,
    category=FindingCategory.CORRECTNESS,
    file_path="test.py",
    location="func",
    title="Test finding",
    confirmed_by_heuristic=False,
):
    return Finding(
        severity=severity,
        category=category,
        file_path=file_path,
        location=location,
        title=title,
        description="A test description",
        impact="Some impact",
        remediation="Fix it",
        source_layer="llm",
        confirmed_by_heuristic=confirmed_by_heuristic,
    )


class TestGenerateReports:
    """Tests for generate_reports function."""

    def test_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "subdir" / "reports"
            generate_reports([], output)
            assert output.exists()

    def test_writes_json_file(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports([_finding()], output)
            json_path = output / "findings.json"
            assert json_path.exists()
            data = json.loads(json_path.read_text())
            assert len(data) == 1
            assert data[0]["severity"] == "medium"

    def test_writes_markdown_file(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports([_finding()], output)
            md_path = output / "report.md"
            assert md_path.exists()
            content = md_path.read_text()
            assert "# Code Review Report" in content

    def test_json_sorted_by_severity(self):
        findings = [
            _finding(severity=Severity.LOW, title="Low", file_path="l.py"),
            _finding(severity=Severity.CRITICAL, title="Crit", file_path="c.py"),
        ]
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports(findings, output)
            data = json.loads((output / "findings.json").read_text())
            assert data[0]["severity"] == "critical"
            assert data[1]["severity"] == "low"

    def test_markdown_has_severity_badges(self):
        findings = [
            _finding(severity=Severity.CRITICAL),
            _finding(severity=Severity.HIGH, title="H", file_path="h.py"),
            _finding(severity=Severity.MEDIUM, title="M", file_path="m.py"),
            _finding(severity=Severity.LOW, title="L", file_path="l.py"),
        ]
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports(findings, output)
            content = (output / "report.md").read_text()
            assert "🔴" in content
            assert "🟠" in content
            assert "🟡" in content
            assert "⚪" in content

    def test_markdown_grouped_by_file(self):
        findings = [
            _finding(file_path="alpha.py", title="A"),
            _finding(file_path="beta.py", title="B"),
        ]
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports(findings, output)
            content = (output / "report.md").read_text()
            assert "`alpha.py`" in content
            assert "`beta.py`" in content

    def test_scan_result_metadata_in_markdown(self):
        scan_result = ScanResult(files=[], total_count=50, elapsed_seconds=2.5, warnings=[])
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports([_finding()], output, scan_result=scan_result)
            content = (output / "report.md").read_text()
            assert "50" in content
            assert "2.50" in content

    def test_summary_section_above_200(self):
        findings = [_finding(title=f"F{i}", file_path=f"f{i}.py") for i in range(201)]
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports(findings, output)
            content = (output / "report.md").read_text()
            assert "## Summary" in content
            assert "201 findings" in content

    def test_no_summary_section_at_200(self):
        findings = [_finding(title=f"F{i}", file_path=f"f{i}.py") for i in range(200)]
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports(findings, output)
            content = (output / "report.md").read_text()
            assert "## Summary" not in content

    def test_confirmed_badge_in_markdown(self):
        findings = [_finding(confirmed_by_heuristic=True)]
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports(findings, output)
            content = (output / "report.md").read_text()
            assert "✓" in content

    def test_zero_findings(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            generate_reports([], output)
            data = json.loads((output / "findings.json").read_text())
            assert data == []
            content = (output / "report.md").read_text()
            assert "Total findings:** 0" in content
