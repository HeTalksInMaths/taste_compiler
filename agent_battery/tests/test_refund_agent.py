"""Acceptance test for the refund_agent example.

Runs the audit pipeline against examples/refund_agent/
and verifies ordering-related findings are produced.
"""

from pathlib import Path

import pytest

from agentbattery.scanner import scan
from agentbattery.file_classifier import classify_files
from agentbattery.prompt_extractor import extract_prompts
from agentbattery.tool_extractor import extract_tools
from agentbattery.obligation_extractor import extract_obligations
from agentbattery.risk_classifier import classify_tools
from agentbattery.contract_compiler import compile_contract
from agentbattery.mismatch_detector import detect_mismatches
from agentbattery.rubric_auditor import audit_architecture
from agentbattery.models import (
    FileCategory,
    GapType,
    RiskLevel,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "refund_agent"


@pytest.fixture
def refund_agent_audit():
    """Run the audit pipeline on the refund_agent example."""
    # 1. Scan
    scan_result = scan(EXAMPLE_DIR)
    # 2. Classify
    classified = classify_files(scan_result.files)
    # 3. Extract prompts
    prompt_files = [f for f in classified if f.primary_category == FileCategory.PROMPT]
    prompts = extract_prompts(prompt_files)
    # 4. Extract tools
    tool_files = [f for f in classified if f.primary_category in (FileCategory.TOOL_SOURCE, FileCategory.TOOL_SCHEMA)]
    tools = extract_tools(tool_files)
    # 5. Classify risks
    tools = classify_tools(tools)
    # 6. Extract obligations
    obligations = extract_obligations(prompts, tools)
    # 7. Risk levels
    risk_levels = {t.name: t.side_effect_level for t in tools}
    # 8. Compile contract
    contract = compile_contract(prompts, tools, obligations, risk_levels)
    # 9. Detect mismatches
    findings = detect_mismatches(contract, classified)
    # 10. Rubric auditor
    contract, arch_findings = audit_architecture(contract, classified, prompts)
    findings.extend(arch_findings)

    return {
        "contract": contract,
        "findings": findings,
        "tools": tools,
        "obligations": obligations,
    }


def test_ordering_findings_produced(refund_agent_audit):
    """Verify ordering-related findings are produced for refund_agent.

    The refund_agent has:
    - issue_refund tool (financial, classified as EXTERNAL_WRITE)
    - Obligations requiring lookup, policy check, and confirmation before refund
    - No preconditions on the tools

    We expect findings related to:
    - Policy/enforcement gaps for the financial tool
    - Confirmation/ordering requirements without enforcement
    """
    findings = refund_agent_audit["findings"]
    contract = refund_agent_audit["contract"]
    obligations = refund_agent_audit["obligations"]

    # Should have findings
    assert len(findings) > 0, "No findings produced for refund_agent"

    # Check that issue_refund is classified and has findings
    tools = refund_agent_audit["tools"]
    issue_refund = next((t for t in tools if t.name == "issue_refund"), None)
    assert issue_refund is not None, "issue_refund tool not found"

    # Should have obligations extracted (ordering language in prompt)
    assert len(obligations) > 0, "No obligations extracted from refund_agent prompt"

    # There should be enforcement-gap or policy-gap findings related to the refund process
    # The prompt requires lookup/policy check/confirmation before refund, but tools have no preconditions
    relevant_findings = [
        f for f in findings
        if (
            "issue_refund" in f.title.lower()
            or "issue_refund" in f.description.lower()
            or "refund" in f.title.lower()
            or "policy" in f.title.lower()
            or "confirmation" in f.title.lower()
            or "enforcement" in f.finding_type.lower()
            or any("issue_refund" in e.detail.lower() or "issue_refund" in e.location for e in f.evidence)
        )
    ]
    assert len(relevant_findings) > 0, (
        f"Expected ordering/enforcement findings for refund_agent, "
        f"got findings: {[f.title for f in findings]}"
    )

    # Should have HIGH or CRITICAL severity findings (financial tool without enforcement)
    high_or_above = [
        f for f in findings
        if f.severity in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    ]
    assert len(high_or_above) > 0, (
        f"Expected at least one HIGH/CRITICAL finding, got severities: "
        f"{[f.severity.value for f in findings]}"
    )
