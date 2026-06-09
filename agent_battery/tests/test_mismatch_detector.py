"""Unit tests for mismatch_detector module."""

from __future__ import annotations

from agentbattery.mismatch_detector import detect_mismatches
from agentbattery.models import (
    AgentContract,
    ClassifiedFile,
    Evidence,
    FileCategory,
    Finding,
    GapType,
    Obligation,
    ObligationType,
    PromptArtifact,
    RiskLevel,
    SideEffectLevel,
    ToolArtifact,
    ToolParameter,
)
from pathlib import Path


def _make_contract(
    tools: list[ToolArtifact] | None = None,
    obligations: list[Obligation] | None = None,
    prompts: list[PromptArtifact] | None = None,
) -> AgentContract:
    """Helper to build a minimal AgentContract."""
    return AgentContract(
        prompts=prompts or [],
        tools=tools or [],
        obligations=obligations or [],
        forbidden_transitions=[],
        risk_map={},
    )


def _make_tool(
    name: str,
    side_effect: SideEffectLevel = SideEffectLevel.NONE,
    preconditions: list[str] | None = None,
    parameters: list[ToolParameter] | None = None,
) -> ToolArtifact:
    """Helper to build a ToolArtifact."""
    return ToolArtifact(
        name=name,
        description=f"Tool: {name}",
        parameters=parameters or [],
        source_path="tools.py",
        side_effect_level=side_effect,
        preconditions=preconditions or [],
    )


def _make_obligation(
    ob_id: str,
    ob_type: ObligationType,
    source_text: str = "test obligation",
    linked_tools: list[str] | None = None,
) -> Obligation:
    """Helper to build an Obligation."""
    return Obligation(
        id=ob_id,
        obligation_type=ob_type,
        source_text=source_text,
        source_path="prompt.md",
        linked_tool_names=linked_tools or [],
    )


class TestCheckA_PolicyGap:
    """Test Check A: POLICY_GAP for dangerous tool with no obligations."""

    def test_finds_policy_gap_for_send_email_with_no_obligations(self):
        """A dangerous tool (EXTERNAL_WRITE) with no linked obligations emits POLICY_GAP."""
        tool = _make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])

        # Should have at least one POLICY_GAP finding for send_email
        policy_gaps = [
            f for f in findings
            if f.gap_type == GapType.POLICY_GAP and "send_email" in f.title
        ]
        assert len(policy_gaps) >= 1
        finding = policy_gaps[0]
        assert finding.severity in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_destructive_tool_gets_critical_severity(self):
        """DESTRUCTIVE tools with no obligations get CRITICAL severity."""
        tool = _make_tool("delete_user", SideEffectLevel.DESTRUCTIVE)
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])

        policy_gaps = [
            f for f in findings
            if f.gap_type == GapType.POLICY_GAP and "delete_user" in f.title
        ]
        assert len(policy_gaps) >= 1
        assert any(f.severity == RiskLevel.CRITICAL for f in policy_gaps)

    def test_no_finding_for_safe_tool(self):
        """A tool with SideEffectLevel.NONE should not emit POLICY_GAP."""
        tool = _make_tool("read_inbox", SideEffectLevel.NONE)
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])

        policy_gaps = [
            f for f in findings
            if f.gap_type == GapType.POLICY_GAP and "read_inbox" in f.title
        ]
        assert len(policy_gaps) == 0


class TestCheckB_EnforcementGap:
    """Test Check B: ENFORCEMENT_GAP when confirmation obligation exists but tool has no precondition."""

    def test_finds_enforcement_gap_for_missing_precondition(self):
        """Confirmation obligation linked to tool without precondition → ENFORCEMENT_GAP."""
        tool = _make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="Always confirm before sending email",
            linked_tools=["send_email"],
        )
        contract = _make_contract(tools=[tool], obligations=[obligation])

        findings = detect_mismatches(contract, [])

        enforcement_gaps = [
            f for f in findings
            if f.gap_type == GapType.ENFORCEMENT_GAP
            and "send_email" in f.title
            and "confirmation" in f.title.lower()
        ]
        assert len(enforcement_gaps) >= 1

    def test_findings_include_evidence_and_uncertainty_wording(self):
        """Findings should have non-empty evidence with uncertainty wording."""
        tool = _make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="Always confirm before sending email",
            linked_tools=["send_email"],
        )
        contract = _make_contract(tools=[tool], obligations=[obligation])

        findings = detect_mismatches(contract, [])

        enforcement_gaps = [
            f for f in findings
            if f.gap_type == GapType.ENFORCEMENT_GAP
            and "send_email" in f.title
            and "confirmation" in f.title.lower()
        ]
        assert len(enforcement_gaps) >= 1
        finding = enforcement_gaps[0]

        # Evidence must be non-empty
        assert len(finding.evidence) > 0

        # Transparency must be non-empty
        assert finding.transparency != ""

        # Check for uncertainty wording in evidence
        all_details = " ".join(e.detail for e in finding.evidence)
        assert "detected" in all_details.lower() or "no" in all_details.lower()

    def test_no_finding_when_tool_has_confirmation_precondition(self):
        """No ENFORCEMENT_GAP when tool has a matching precondition."""
        tool = _make_tool(
            "send_email",
            SideEffectLevel.EXTERNAL_WRITE,
            preconditions=["Requires user confirmation before execution"],
        )
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="Always confirm before sending email",
            linked_tools=["send_email"],
        )
        contract = _make_contract(tools=[tool], obligations=[obligation])

        findings = detect_mismatches(contract, [])

        # Check B should NOT emit for send_email since it has confirmation precondition
        enforcement_gaps = [
            f for f in findings
            if f.gap_type == GapType.ENFORCEMENT_GAP
            and "send_email" in f.title
            and "confirmation" in f.title.lower()
        ]
        assert len(enforcement_gaps) == 0


class TestCheckG_PermissiveSchema:
    """Test Check G: ENFORCEMENT_GAP for all-optional params on high-risk tool."""

    def test_finds_permissive_schema(self):
        """High-risk tool with all optional params → ENFORCEMENT_GAP."""
        params = [
            ToolParameter(name="to", type="string", required=False),
            ToolParameter(name="body", type="string", required=False),
        ]
        tool = _make_tool(
            "send_email",
            SideEffectLevel.EXTERNAL_WRITE,
            parameters=params,
        )
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])

        permissive = [
            f for f in findings
            if "permissive" in f.title.lower() or "all parameters optional" in f.title.lower()
        ]
        assert len(permissive) >= 1

    def test_no_finding_when_required_param_exists(self):
        """No finding when at least one param is required."""
        params = [
            ToolParameter(name="to", type="string", required=True),
            ToolParameter(name="body", type="string", required=False),
        ]
        tool = _make_tool(
            "send_email",
            SideEffectLevel.EXTERNAL_WRITE,
            parameters=params,
        )
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])

        permissive = [
            f for f in findings
            if "permissive" in f.title.lower()
        ]
        assert len(permissive) == 0


class TestAllFindings:
    """Cross-cutting tests for all findings."""

    def test_all_findings_have_gap_type(self):
        """Every finding must have a gap_type set."""
        tool = _make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])

        for finding in findings:
            assert finding.gap_type in (
                GapType.POLICY_GAP,
                GapType.ENFORCEMENT_GAP,
                GapType.COVERAGE_GAP,
                GapType.TRACE_VIOLATION,
            )

    def test_all_findings_have_evidence(self):
        """Every finding must have non-empty evidence."""
        tool = _make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])
        assert len(findings) > 0

        for finding in findings:
            assert len(finding.evidence) > 0

    def test_all_findings_have_transparency(self):
        """Every finding must have non-empty transparency."""
        tool = _make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)
        contract = _make_contract(tools=[tool])

        findings = detect_mismatches(contract, [])
        assert len(findings) > 0

        for finding in findings:
            assert finding.transparency != ""
