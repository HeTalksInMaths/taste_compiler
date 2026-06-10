"""Acceptance test for the email_agent example.

Runs the full audit pipeline programmatically against examples/email_agent/
and verifies:
1. send_email classified as EXTERNAL_WRITE with HIGH or CRITICAL finding
2. Trace violation detected for unconfirmed send
3. At least one generated test blocking unconfirmed send_email
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
from agentbattery.trace_loader import load_traces
from agentbattery.trace_checker import check_traces
from agentbattery.rubric_auditor import audit_architecture
from agentbattery.coverage_analyzer import analyze_coverage, get_coverage_findings
from agentbattery.test_generator import generate_tests
from agentbattery.models import (
    FileCategory,
    GapType,
    RiskLevel,
    SideEffectLevel,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "email_agent"


@pytest.fixture
def email_agent_audit():
    """Run the full audit pipeline on the email_agent example."""
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
    # 10. Load traces
    trace_files = [f for f in classified if f.primary_category == FileCategory.TRACE]
    traces = load_traces(trace_files)
    # 11. Check traces
    trace_findings = check_traces(traces, contract)
    findings.extend(trace_findings)
    # 12. Rubric auditor
    contract, arch_findings = audit_architecture(contract, classified, prompts)
    findings.extend(arch_findings)
    # 13. Coverage
    eval_files = [f for f in classified if f.primary_category == FileCategory.EVAL]
    coverage = analyze_coverage(contract, eval_files)
    coverage_findings = get_coverage_findings(contract, coverage)
    findings.extend(coverage_findings)
    # 14. Generate tests
    generated = generate_tests(findings, contract)

    return {
        "contract": contract,
        "findings": findings,
        "trace_findings": trace_findings,
        "generated": generated,
        "tools": tools,
        "classified": classified,
    }


def test_send_email_classified_as_external_write(email_agent_audit):
    """Verify send_email is classified as EXTERNAL_WRITE with HIGH or CRITICAL finding."""
    tools = email_agent_audit["tools"]
    findings = email_agent_audit["findings"]

    # Check send_email tool classification
    send_email_tool = next((t for t in tools if t.name == "send_email"), None)
    assert send_email_tool is not None, "send_email tool not found"
    assert send_email_tool.side_effect_level == SideEffectLevel.EXTERNAL_WRITE, (
        f"Expected EXTERNAL_WRITE, got {send_email_tool.side_effect_level}"
    )

    # Check that there's a HIGH or CRITICAL finding related to send_email
    send_email_findings = [
        f for f in findings
        if "send_email" in f.title.lower() or "send_email" in f.description.lower()
        or any("send_email" in e.detail.lower() or "send_email" in e.location for e in f.evidence)
    ]
    high_or_critical = [
        f for f in send_email_findings
        if f.severity in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    ]
    assert len(high_or_critical) > 0, (
        f"Expected at least one HIGH/CRITICAL finding for send_email, "
        f"got {len(high_or_critical)} from {len(send_email_findings)} total send_email findings"
    )


def test_trace_violation_for_unconfirmed_send(email_agent_audit):
    """Verify trace violation detected for unconfirmed send."""
    trace_findings = email_agent_audit["trace_findings"]

    # Should have at least one TRACE_VIOLATION finding
    assert len(trace_findings) > 0, "No trace violations detected"

    # At least one should be about missing confirmation or forbidden tool use
    # related to send_email
    relevant = [
        f for f in trace_findings
        if f.gap_type == GapType.TRACE_VIOLATION
        and ("send_email" in f.title.lower() or "send_email" in f.description.lower()
             or "confirmation" in f.title.lower() or "forbidden" in f.title.lower())
    ]
    assert len(relevant) > 0, (
        f"Expected trace violation for unconfirmed send_email, "
        f"got findings: {[f.title for f in trace_findings]}"
    )


def test_generated_test_blocks_unconfirmed_send(email_agent_audit):
    """Verify at least one generated test blocking unconfirmed send_email."""
    generated = email_agent_audit["generated"]

    assert len(generated) > 0, "No tests generated"

    # Look for a test related to send_email or confirmation
    relevant_tests = [
        t for t in generated
        if "send_email" in t.id.lower()
        or "send_email" in t.description.lower()
        or "send_email" in str(t.setup).lower()
        or "confirmation" in t.test_type.lower()
        or any("send_email" in a for a in t.assertions)
    ]
    assert len(relevant_tests) > 0, (
        f"Expected at least one generated test blocking unconfirmed send_email, "
        f"got test ids: {[t.id for t in generated[:10]]}"
    )
