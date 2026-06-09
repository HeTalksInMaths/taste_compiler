"""Report generator module - produces Markdown and JSON reports."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from agentbattery.models import (
    AgentContract,
    CoverageResult,
    Evidence,
    Finding,
    GapType,
    GeneratedTest,
    RecommendedRepairType,
    RepairFinding,
    RepairInput,
    RiskLevel,
    SideEffectLevel,
)

logger = logging.getLogger(__name__)

# Severity ordering for sorting findings (CRITICAL first)
_SEVERITY_ORDER: dict[RiskLevel, int] = {
    RiskLevel.CRITICAL: 0,
    RiskLevel.HIGH: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 3,
}


def _severity_badge(severity: RiskLevel) -> str:
    """Return a markdown badge for a severity level."""
    badges = {
        RiskLevel.CRITICAL: "🔴 CRITICAL",
        RiskLevel.HIGH: "🟠 HIGH",
        RiskLevel.MEDIUM: "🟡 MEDIUM",
        RiskLevel.LOW: "🟢 LOW",
    }
    return badges.get(severity, str(severity.value))


def _finding_id(finding: Finding) -> str:
    """Generate a stable finding ID from type + title."""
    return hashlib.sha256(
        f"{finding.finding_type}:{finding.title}".encode()
    ).hexdigest()[:12]


def _sorted_findings(findings: list[Finding]) -> list[Finding]:
    """Sort findings by severity: CRITICAL → HIGH → MEDIUM → LOW."""
    return sorted(findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 99))


def _count_by_severity(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity level."""
    counts: dict[str, int] = {}
    for f in findings:
        key = f.severity.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _generate_markdown(
    findings: list[Finding],
    coverage: CoverageResult,
    generated_tests: list[GeneratedTest],
    contract: AgentContract,
) -> str:
    """Generate the full Markdown report content."""
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    sorted_findings = _sorted_findings(findings)
    severity_counts = _count_by_severity(findings)
    overall_status = "PASS" if len(findings) == 0 else "FINDINGS DETECTED"

    # --- Summary ---
    lines.append("# Agent Battery Audit Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Date**: {now}")
    lines.append(f"- **Status**: {overall_status}")
    lines.append(f"- **Total Findings**: {len(findings)}")
    for sev in [RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]:
        count = severity_counts.get(sev.value, 0)
        if count > 0:
            lines.append(f"  - {sev.value}: {count}")
    lines.append(f"- **Generated Tests**: {len(generated_tests)}")
    lines.append("")

    # --- Architecture Overview ---
    lines.append("## Architecture Overview")
    lines.append("")
    lines.append(f"- **Prompts Discovered**: {len(contract.prompts)}")
    lines.append(f"- **Tools Discovered**: {len(contract.tools)}")
    lines.append(f"- **Traces Discovered**: {len(contract.forbidden_transitions)}")
    lines.append("")

    # --- Tool Risk Table ---
    lines.append("## Tool Risk Table")
    lines.append("")
    if contract.tools:
        lines.append("| Tool | Side Effect | Risk | Preconditions | Source |")
        lines.append("|------|-------------|------|---------------|--------|")
        for tool in contract.tools:
            risk = contract.risk_map.get(tool.name, SideEffectLevel.NONE)
            preconditions = ", ".join(tool.preconditions) if tool.preconditions else "None"
            lines.append(
                f"| {tool.name} | {tool.side_effect_level.value} | {risk.value} | {preconditions} | {tool.source_path} |"
            )
    else:
        lines.append("No tools discovered.")
    lines.append("")

    # --- Obligations List ---
    lines.append("## Obligations List")
    lines.append("")
    if contract.obligations:
        lines.append("| ID | Type | Source | Linked Tools |")
        lines.append("|----|------|--------|--------------|")
        for obl in contract.obligations:
            linked = ", ".join(obl.linked_tool_names) if obl.linked_tool_names else "None"
            lines.append(
                f"| {obl.id} | {obl.obligation_type.value} | {obl.source_path} | {linked} |"
            )
    else:
        lines.append("No obligations extracted.")
    lines.append("")

    # --- Findings ---
    lines.append("## Findings")
    lines.append("")
    if sorted_findings:
        for finding in sorted_findings:
            lines.append(f"### {_severity_badge(finding.severity)} — {finding.title}")
            lines.append("")
            lines.append(f"- **Type**: {finding.finding_type}")
            lines.append(f"- **Gap Type**: {finding.gap_type.value}")
            lines.append(f"- **Description**: {finding.description}")
            if finding.evidence:
                lines.append("- **Evidence**:")
                for ev in finding.evidence:
                    lines.append(f"  - [{ev.source}] {ev.detail}")
            if finding.remediation:
                lines.append(f"- **Suggested Fix**: {finding.remediation}")
            lines.append("")
    else:
        lines.append("No findings detected. All checks passed.")
        lines.append("")

    # --- Coverage Analysis ---
    lines.append("## Coverage Analysis")
    lines.append("")
    if coverage.obligations:
        lines.append("| Obligation | Status | Score | Matching Files |")
        lines.append("|------------|--------|-------|----------------|")
        for obl_cov in coverage.obligations:
            matching = ", ".join(obl_cov.matching_files) if obl_cov.matching_files else "None"
            lines.append(
                f"| {obl_cov.obligation_id} | {obl_cov.status.value} | {obl_cov.score:.2f} | {matching} |"
            )
    else:
        lines.append("No obligations to analyze coverage for.")
    lines.append("")

    # --- Trace Violations ---
    lines.append("## Trace Violations")
    lines.append("")
    trace_violations = [f for f in sorted_findings if f.gap_type == GapType.TRACE_VIOLATION]
    if trace_violations:
        for tv in trace_violations:
            lines.append(f"- {_severity_badge(tv.severity)} **{tv.title}**: {tv.description}")
    else:
        lines.append("No trace violations detected.")
    lines.append("")

    # --- Hackathon Agent Architecture Summary ---
    lines.append("## Hackathon Agent Architecture Summary")
    lines.append("")

    # Agent Overview
    lines.append("### Agent Overview")
    lines.append("")
    if contract.agent_profiles:
        for profile in contract.agent_profiles:
            lines.append(f"- **{profile.name}**: {profile.purpose}")
            if profile.capabilities:
                lines.append(f"  - Capabilities: {', '.join(profile.capabilities)}")
            if profile.source_evidence:
                lines.append(f"  - Evidence: {', '.join(profile.source_evidence)}")
    else:
        lines.append("No agent identity detected.")
    _append_related_findings(lines, sorted_findings, ["AGENT_OVERVIEW_GAP"])
    _append_related_tests(lines, generated_tests, ["AGENT_OVERVIEW_GAP"])
    lines.append("")

    # Autonomy & Decision-Making
    lines.append("### Autonomy & Decision-Making")
    lines.append("")
    if contract.decision_policy:
        dp = contract.decision_policy
        lines.append(f"- **Strategy**: {dp.strategy}")
        if dp.stop_conditions:
            lines.append(f"- **Stop Conditions**: {', '.join(dp.stop_conditions)}")
        if dp.tool_selection_logic:
            lines.append(f"- **Tool Selection**: {dp.tool_selection_logic}")
        if dp.source_evidence:
            lines.append(f"- Evidence: {', '.join(dp.source_evidence)}")
    else:
        lines.append("No decision-making policy detected.")
    _append_related_findings(
        lines, sorted_findings,
        ["DECISION_POLICY_GAP", "STOP_CONDITION_GAP", "TOOL_SELECTION_POLICY_GAP"],
    )
    _append_related_tests(
        lines, generated_tests,
        ["DECISION_POLICY_GAP", "STOP_CONDITION_GAP", "TOOL_SELECTION_POLICY_GAP"],
    )
    lines.append("")

    # Actions & Tool Use
    lines.append("### Actions & Tool Use")
    lines.append("")
    if contract.tools:
        lines.append("| Tool | Side Effect | Linked Obligations |")
        lines.append("|------|-------------|-------------------|")
        for tool in contract.tools:
            linked_obls = [
                o.id for o in contract.obligations if tool.name in o.linked_tool_names
            ]
            linked_str = ", ".join(linked_obls) if linked_obls else "None"
            lines.append(f"| {tool.name} | {tool.side_effect_level.value} | {linked_str} |")
    else:
        lines.append("No tools discovered.")
    lines.append("")

    # Orchestration
    lines.append("### Orchestration")
    lines.append("")
    if contract.orchestration_policy:
        op = contract.orchestration_policy
        if op.agents:
            lines.append("- **Agents**:")
            for agent in op.agents:
                lines.append(f"  - {agent.name}: {agent.role}")
        if op.delegation_bounds:
            lines.append(f"- **Delegation Bounds**: {op.delegation_bounds}")
        if op.shared_state_mechanism:
            lines.append(f"- **Shared State**: {op.shared_state_mechanism}")
        if op.communication_pattern:
            lines.append(f"- **Communication**: {op.communication_pattern}")
        if op.source_evidence:
            lines.append(f"- Evidence: {', '.join(op.source_evidence)}")
    else:
        lines.append("Single-agent system detected (no multi-agent indicators found).")
    _append_related_findings(
        lines, sorted_findings,
        ["ORCHESTRATION_UNSPECIFIED", "UNBOUNDED_DELEGATION", "SHARED_STATE_UNSPECIFIED"],
    )
    _append_related_tests(
        lines, generated_tests,
        ["ORCHESTRATION_UNSPECIFIED", "UNBOUNDED_DELEGATION", "SHARED_STATE_UNSPECIFIED"],
    )
    lines.append("")

    # Human-in-the-Loop
    lines.append("### Human-in-the-Loop")
    lines.append("")
    if contract.human_in_loop_policy:
        hitl = contract.human_in_loop_policy
        if hitl.approval_required_tools:
            lines.append(
                f"- **Approval Required Tools**: {', '.join(hitl.approval_required_tools)}"
            )
        if hitl.review_triggers:
            lines.append(f"- **Review Triggers**: {', '.join(hitl.review_triggers)}")
        if hitl.override_mechanism:
            lines.append(f"- **Override Mechanism**: {hitl.override_mechanism}")
        if hitl.source_evidence:
            lines.append(f"- Evidence: {', '.join(hitl.source_evidence)}")
    else:
        lines.append("No human-in-the-loop policy detected.")
    _append_related_findings(
        lines, sorted_findings,
        ["HITL_GAP", "APPROVAL_ENFORCEMENT_GAP", "OVERRIDE_GAP"],
    )
    _append_related_tests(
        lines, generated_tests,
        ["HITL_GAP", "APPROVAL_ENFORCEMENT_GAP", "OVERRIDE_GAP"],
    )
    lines.append("")

    # Failure Handling
    lines.append("### Failure Handling")
    lines.append("")
    if contract.failure_policy:
        fp = contract.failure_policy
        if fp.retry_strategy:
            lines.append(f"- **Retry Strategy**: {fp.retry_strategy}")
        if fp.timeout_seconds:
            lines.append(f"- **Timeout**: {fp.timeout_seconds}s")
        if fp.fallback_behavior:
            lines.append(f"- **Fallback**: {fp.fallback_behavior}")
        if fp.partial_completion_handling:
            lines.append(f"- **Partial Completion**: {fp.partial_completion_handling}")
        if fp.recovery_mechanism:
            lines.append(f"- **Recovery**: {fp.recovery_mechanism}")
        if fp.source_evidence:
            lines.append(f"- Evidence: {', '.join(fp.source_evidence)}")
    else:
        lines.append("No failure handling policy detected.")
    _append_related_findings(
        lines, sorted_findings,
        [
            "RETRY_POLICY_GAP", "TIMEOUT_POLICY_GAP", "FALLBACK_POLICY_GAP",
            "PARTIAL_COMPLETION_GAP", "RECOVERY_STATE_GAP",
        ],
    )
    _append_related_tests(
        lines, generated_tests,
        [
            "RETRY_POLICY_GAP", "TIMEOUT_POLICY_GAP", "FALLBACK_POLICY_GAP",
            "PARTIAL_COMPLETION_GAP", "RECOVERY_STATE_GAP",
        ],
    )
    lines.append("")

    # --- Generated Tests ---
    lines.append("## Generated Tests")
    lines.append("")
    if generated_tests:
        for test in generated_tests:
            lines.append(f"- **{test.id}**: {test.description}")
    else:
        lines.append("No tests generated.")
    lines.append("")

    # --- Next Actions ---
    lines.append("## Next Actions")
    lines.append("")
    if sorted_findings:
        lines.append("Prioritized repair checklist:")
        lines.append("")
        for i, finding in enumerate(sorted_findings, 1):
            lines.append(f"{i}. [{finding.severity.value}] {finding.title} — {finding.remediation or 'Review and address'}")
    else:
        lines.append("No actions required. All checks passed.")
    lines.append("")

    return "\n".join(lines)


def _append_related_findings(
    lines: list[str],
    findings: list[Finding],
    finding_types: list[str],
) -> None:
    """Append related findings for an architecture subsection."""
    related = [f for f in findings if f.finding_type in finding_types]
    if related:
        lines.append("")
        lines.append("**Related Findings:**")
        for f in related:
            lines.append(f"- {_severity_badge(f.severity)} {f.title}")


def _append_related_tests(
    lines: list[str],
    tests: list[GeneratedTest],
    finding_types: list[str],
) -> None:
    """Append related generated tests for an architecture subsection."""
    related = [
        t for t in tests
        if any(ft.lower() in t.id.lower() or ft.lower() in " ".join(t.tags).lower()
               for ft in finding_types)
    ]
    if related:
        lines.append("")
        lines.append("**Generated Tests:**")
        for t in related:
            lines.append(f"- {t.id}: {t.title}")


def _generate_json(
    findings: list[Finding],
    coverage: CoverageResult,
    generated_tests: list[GeneratedTest],
    contract: AgentContract,
) -> dict:
    """Generate the JSON report data."""
    now = datetime.now(timezone.utc).isoformat()

    # Contract summary
    contract_summary = {
        "prompts_count": len(contract.prompts),
        "tools_count": len(contract.tools),
        "obligations_count": len(contract.obligations),
        "forbidden_transitions_count": len(contract.forbidden_transitions),
        "risk_map": {k: v.value for k, v in contract.risk_map.items()},
    }

    # Coverage summary
    coverage_summary = {
        "covered_count": coverage.covered_count,
        "partial_count": coverage.partial_count,
        "missing_count": coverage.missing_count,
        "total_obligations": len(coverage.obligations),
    }

    return {
        "repo_root": ".",
        "generated_at": now,
        "findings": [f.model_dump(mode="json") for f in findings],
        "generated_tests": [t.model_dump(mode="json") for t in generated_tests],
        "coverage_summary": coverage_summary,
        "contract_summary": contract_summary,
    }


def generate_report(
    findings: list[Finding],
    coverage: CoverageResult,
    generated_tests: list[GeneratedTest],
    contract: AgentContract,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Produce latest.md and latest.json in output_dir/reports/.

    Args:
        findings: List of all findings from the audit.
        coverage: Coverage analysis results.
        generated_tests: List of generated test definitions.
        contract: The compiled AgentContract.
        output_dir: Base output directory (e.g., .agentbattery/).

    Returns:
        Tuple of (markdown_path, json_path).
    """
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Generate Markdown
    md_content = _generate_markdown(findings, coverage, generated_tests, contract)
    md_path = reports_dir / "latest.md"
    md_path.write_text(md_content, encoding="utf-8")

    # Generate JSON
    json_data = _generate_json(findings, coverage, generated_tests, contract)
    json_path = reports_dir / "latest.json"
    json_path.write_text(json.dumps(json_data, indent=2, default=str), encoding="utf-8")

    logger.info("Reports written to %s", reports_dir)
    return md_path, json_path


def _infer_repair_type(finding: Finding) -> RecommendedRepairType:
    """Infer recommended repair type from finding characteristics.

    Rules:
    - POLICY_GAP with "confirmation" → ADD_HITL_GATE
    - ENFORCEMENT_GAP with "confirmation" → ADD_TOOL_PRECONDITION
    - ENFORCEMENT_GAP with "policy" → ADD_TOOL_PRECONDITION
    - ENFORCEMENT_GAP with "permissive" → TIGHTEN_SCHEMA
    - ENFORCEMENT_GAP with "consistency" → ADD_FINAL_STATE_VERIFIER
    - POLICY_GAP with "retrieval" → ADD_TOOL_PRECONDITION
    - COVERAGE_GAP → ADD_TEST
    - TRACE_VIOLATION → ADD_TEST
    - Architecture gaps → UPDATE_ARCHITECTURE_DOC
    - Failure handling gaps → ADD_RETRY_OR_FALLBACK
    """
    combined = (
        finding.finding_type.lower()
        + " "
        + finding.title.lower()
        + " "
        + finding.description.lower()
    )

    # Architecture-related gaps
    architecture_types = {
        "agent_overview_gap", "decision_policy_gap", "stop_condition_gap",
        "tool_selection_policy_gap", "orchestration_unspecified",
        "unbounded_delegation", "shared_state_unspecified", "override_gap",
    }
    if finding.finding_type.lower() in architecture_types:
        return RecommendedRepairType.UPDATE_ARCHITECTURE_DOC

    # Failure handling gaps
    failure_types = {
        "retry_policy_gap", "timeout_policy_gap", "fallback_policy_gap",
        "partial_completion_gap", "recovery_state_gap",
    }
    if finding.finding_type.lower() in failure_types:
        return RecommendedRepairType.ADD_RETRY_OR_FALLBACK

    # Gap-type based rules
    if finding.gap_type == GapType.COVERAGE_GAP:
        return RecommendedRepairType.ADD_TEST

    if finding.gap_type == GapType.TRACE_VIOLATION:
        return RecommendedRepairType.ADD_TEST

    if finding.gap_type == GapType.POLICY_GAP:
        if "confirmation" in combined or "hitl" in combined or "approval" in combined:
            return RecommendedRepairType.ADD_HITL_GATE
        if "retrieval" in combined or "injection" in combined:
            return RecommendedRepairType.ADD_TOOL_PRECONDITION
        # Default POLICY_GAP
        return RecommendedRepairType.ADD_HITL_GATE

    if finding.gap_type == GapType.ENFORCEMENT_GAP:
        if "permissive" in combined or "schema" in combined or "all-optional" in combined:
            return RecommendedRepairType.TIGHTEN_SCHEMA
        if "consistency" in combined or "verification" in combined:
            return RecommendedRepairType.ADD_FINAL_STATE_VERIFIER
        if "confirmation" in combined or "approval" in combined:
            return RecommendedRepairType.ADD_TOOL_PRECONDITION
        if "policy" in combined:
            return RecommendedRepairType.ADD_TOOL_PRECONDITION
        # Default ENFORCEMENT_GAP
        return RecommendedRepairType.ADD_TOOL_PRECONDITION

    # Fallback
    return RecommendedRepairType.ADD_TEST


def _extract_linked_tools(finding: Finding) -> list[str]:
    """Extract linked tool names from finding evidence."""
    tools: list[str] = []
    for ev in finding.evidence:
        if ev.location and ev.location not in ("obligations", "linked_tools", ""):
            if not ev.location.startswith("step ") and not ev.location.startswith("ob_"):
                tools.append(ev.location)
    return list(dict.fromkeys(tools))


def _extract_linked_obligations(finding: Finding) -> list[str]:
    """Extract linked obligation IDs from finding evidence."""
    obligation_ids: list[str] = []
    for ev in finding.evidence:
        if ev.location and (
            ev.location.startswith("ob_") or len(ev.location) == 12
        ):
            obligation_ids.append(ev.location)
        if "obligation" in ev.detail.lower() and "'" in ev.detail:
            parts = ev.detail.split("'")
            for i, part in enumerate(parts):
                if i % 2 == 1 and (part.startswith("ob_") or len(part) == 12):
                    obligation_ids.append(part)
    return list(dict.fromkeys(obligation_ids))


def _find_generated_test_ids(
    finding: Finding, generated_tests: list[GeneratedTest]
) -> list[str]:
    """Find generated test IDs that match this finding."""
    fid = _finding_id(finding)
    return [t.id for t in generated_tests if t.finding_id == fid]


def emit_repair_input(
    findings: list[Finding],
    generated_tests: list[GeneratedTest],
    contract: AgentContract,
    output_dir: Path,
) -> Path:
    """Write repair_input.json for CI/CD integration.

    Maps each finding to a RepairFinding with:
    - finding_id (hash of finding type + title)
    - severity, gap_type
    - linked_tools (from evidence)
    - linked_obligations (from evidence)
    - generated_test_ids (matching tests)
    - recommended_repair_type

    Does NOT apply patches or call LLMs — output only.

    Args:
        findings: List of all findings.
        generated_tests: List of generated tests.
        contract: The AgentContract.
        output_dir: Base output directory.

    Returns:
        Path to the written repair_input.json file.
    """
    repair_findings: list[RepairFinding] = []

    for finding in findings:
        fid = _finding_id(finding)
        linked_tools = _extract_linked_tools(finding)
        linked_obligations = _extract_linked_obligations(finding)
        test_ids = _find_generated_test_ids(finding, generated_tests)
        repair_type = _infer_repair_type(finding)

        repair_finding = RepairFinding(
            finding_id=fid,
            severity=finding.severity,
            gap_type=finding.gap_type,
            linked_tools=linked_tools,
            linked_obligations=linked_obligations,
            evidence=finding.evidence,
            generated_test_ids=test_ids,
            recommended_repair_type=repair_type,
        )
        repair_findings.append(repair_finding)

    repair_input = RepairInput(
        repo_root=".",
        generated_at=datetime.now(timezone.utc).isoformat(),
        findings=repair_findings,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    repair_path = output_dir / "repair_input.json"
    repair_path.write_text(
        json.dumps(repair_input.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    logger.info("Repair input written to %s", repair_path)
    return repair_path
