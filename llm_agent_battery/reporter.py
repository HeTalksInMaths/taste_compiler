"""Report generation for findings — JSON and Markdown outputs."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from llm_agent_battery.models import Finding, ScanResult, Severity


# Severity badge mapping
_SEVERITY_BADGES: dict[Severity, str] = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "⚪",
}

# Severity ordering for sorting
_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


def generate_reports(
    findings: list[Finding],
    output_dir: Path,
    scan_result: ScanResult | None = None,
) -> None:
    """Generate JSON and Markdown report files from findings.

    Writes:
    - findings.json: All findings as a JSON array sorted by severity
    - report.md: Markdown report with severity badges, grouped by file

    Args:
        findings: Ranked list of findings to report.
        output_dir: Directory to write report files into.
        scan_result: Optional scan result for metadata in the report header.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sort findings by severity
    sorted_findings = sorted(findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))

    # Write JSON report
    _write_json_report(sorted_findings, output_dir / "findings.json")

    # Write Markdown report
    _write_markdown_report(sorted_findings, output_dir / "report.md", scan_result)


def _write_json_report(findings: list[Finding], path: Path) -> None:
    """Write all findings as a JSON array."""
    data = [f.model_dump(mode="json") for f in findings]
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _write_markdown_report(
    findings: list[Finding],
    path: Path,
    scan_result: ScanResult | None,
) -> None:
    """Write a Markdown report with severity badges grouped by file."""
    lines: list[str] = []

    # Header
    lines.append("# Code Review Report")
    lines.append("")

    # Metadata section
    total = len(findings)
    lines.append(f"**Total findings:** {total}")
    if scan_result:
        lines.append(f"**Files scanned:** {scan_result.total_count}")
        lines.append(f"**Scan duration:** {scan_result.elapsed_seconds:.2f}s")
    lines.append("")

    # Severity counts
    severity_counts: dict[Severity, int] = defaultdict(int)
    for f in findings:
        severity_counts[f.severity] += 1

    lines.append("## Severity Summary")
    lines.append("")
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        count = severity_counts.get(sev, 0)
        badge = _SEVERITY_BADGES[sev]
        lines.append(f"- {badge} **{sev.value.upper()}**: {count}")
    lines.append("")

    # Summary section when findings > 200
    if total > 200:
        lines.append("## Summary")
        lines.append("")
        lines.append(
            f"This report contains {total} findings. "
            f"Consider focusing on CRITICAL and HIGH severity items first."
        )
        lines.append("")

        # Category breakdown
        category_counts: dict[str, int] = defaultdict(int)
        for f in findings:
            category_counts[f.category.value] += 1

        lines.append("### By Category")
        lines.append("")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}**: {count}")
        lines.append("")

    # Group findings by file
    by_file: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_file[f.file_path].append(f)

    lines.append("## Findings by File")
    lines.append("")

    for file_path in sorted(by_file.keys()):
        file_findings = by_file[file_path]
        lines.append(f"### `{file_path}`")
        lines.append("")

        for finding in file_findings:
            badge = _SEVERITY_BADGES[finding.severity]
            confirmed = " ✓" if finding.confirmed_by_heuristic else ""
            lines.append(f"#### {badge} {finding.title}{confirmed}")
            lines.append("")
            lines.append(f"- **Severity:** {finding.severity.value}")
            lines.append(f"- **Category:** {finding.category.value}")
            lines.append(f"- **Location:** `{finding.location}`")
            lines.append(f"- **Source:** {finding.source_layer}")
            lines.append("")
            lines.append(f"**Description:** {finding.description}")
            lines.append("")
            lines.append(f"**Impact:** {finding.impact}")
            lines.append("")
            if finding.remediation:
                lines.append(f"**Remediation:** {finding.remediation}")
                lines.append("")
            lines.append("---")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
