"""Tests for agentbattery.rubric_auditor module."""

from __future__ import annotations

from pathlib import Path

import pytest

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
)
from agentbattery.rubric_auditor import audit_architecture


def _make_contract(
    tools: list[ToolArtifact] | None = None,
    obligations: list[Obligation] | None = None,
    prompts: list[PromptArtifact] | None = None,
) -> AgentContract:
    """Helper to create a minimal AgentContract."""
    return AgentContract(
        prompts=prompts or [],
        tools=tools or [],
        obligations=obligations or [],
    )


def _make_prompt(text: str, source_path: str = "system_prompt.md") -> PromptArtifact:
    """Helper to create a PromptArtifact."""
    return PromptArtifact(source_path=source_path, text=text)


def _make_tool(
    name: str,
    side_effect_level: SideEffectLevel = SideEffectLevel.NONE,
    description: str = "",
) -> ToolArtifact:
    """Helper to create a ToolArtifact."""
    return ToolArtifact(
        name=name,
        description=description,
        source_path=f"tools/{name}.py",
        side_effect_level=side_effect_level,
    )


def _make_classified_file(
    relative_path: str,
    category: FileCategory = FileCategory.DOC,
) -> ClassifiedFile:
    """Helper to create a ClassifiedFile."""
    return ClassifiedFile(
        path=Path(relative_path),
        relative_path=relative_path,
        size_bytes=100,
        primary_category=category,
    )


class TestAgentOverviewGap:
    """Tests for Agent Overview dimension detection."""

    def test_emits_agent_overview_gap_when_no_identity(self):
        """AGENT_OVERVIEW_GAP emitted when no identity found in prompts."""
        contract = _make_contract()
        prompts = [_make_prompt("Do some tasks. Handle user requests.")]
        files = [_make_classified_file("src/main.py", FileCategory.TOOL_SOURCE)]

        updated_contract, findings = audit_architecture(contract, files, prompts)

        gap_findings = [f for f in findings if f.finding_type == "AGENT_OVERVIEW_GAP"]
        assert len(gap_findings) == 1
        assert gap_findings[0].gap_type == GapType.POLICY_GAP
        assert gap_findings[0].severity == RiskLevel.MEDIUM

    def test_no_agent_overview_gap_when_identity_present(self):
        """No AGENT_OVERVIEW_GAP when prompt says 'You are a helpful assistant'."""
        contract = _make_contract()
        prompts = [_make_prompt("You are a helpful assistant that manages emails.")]
        files = [_make_classified_file("src/main.py", FileCategory.TOOL_SOURCE)]

        updated_contract, findings = audit_architecture(contract, files, prompts)

        gap_findings = [f for f in findings if f.finding_type == "AGENT_OVERVIEW_GAP"]
        assert len(gap_findings) == 0

    def test_populates_agent_profile_when_identity_detected(self):
        """AgentProfile populated when identity detected in prompts."""
        contract = _make_contract()
        prompts = [_make_prompt("You are a customer support agent.\nYou help users resolve issues.")]
        files = []

        updated_contract, findings = audit_architecture(contract, files, prompts)

        assert len(updated_contract.agent_profiles) >= 1
        profile = updated_contract.agent_profiles[0]
        assert profile.name != ""
        assert profile.purpose != ""
        assert len(profile.source_evidence) > 0


class TestHITLGap:
    """Tests for Human-in-the-Loop dimension detection."""

    def test_emits_hitl_gap_when_dangerous_tools_no_confirmation(self):
        """HITL_GAP emitted when dangerous tools present without confirmation."""
        tools = [
            _make_tool("delete_account", SideEffectLevel.DESTRUCTIVE),
            _make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE),
        ]
        contract = _make_contract(tools=tools)
        prompts = [_make_prompt("Process user requests efficiently.")]
        files = []

        updated_contract, findings = audit_architecture(contract, files, prompts)

        hitl_findings = [f for f in findings if f.finding_type == "HITL_GAP"]
        assert len(hitl_findings) == 1
        assert hitl_findings[0].gap_type == GapType.POLICY_GAP
        assert hitl_findings[0].severity == RiskLevel.HIGH

    def test_no_hitl_gap_when_confirmation_present(self):
        """No HITL_GAP when confirmation obligation exists for dangerous tools."""
        tools = [_make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)]
        obligations = [
            Obligation(
                id="ob1",
                obligation_type=ObligationType.CONFIRMATION_REQUIRED,
                source_text="Always confirm before sending",
                source_path="prompt.md",
                linked_tool_names=["send_email"],
            )
        ]
        contract = _make_contract(tools=tools, obligations=obligations)
        prompts = [_make_prompt("Always confirm before sending emails.")]
        files = []

        updated_contract, findings = audit_architecture(contract, files, prompts)

        hitl_findings = [f for f in findings if f.finding_type == "HITL_GAP"]
        assert len(hitl_findings) == 0

    def test_emits_approval_enforcement_gap_when_hitl_mentioned_no_obligation(self):
        """APPROVAL_ENFORCEMENT_GAP when HITL mentioned in prompt but not enforced."""
        tools = [_make_tool("send_email", SideEffectLevel.EXTERNAL_WRITE)]
        contract = _make_contract(tools=tools)
        # Prompt mentions confirmation but no obligation extracted
        prompts = [_make_prompt("You must confirm with the user before sending any email.")]
        files = []

        updated_contract, findings = audit_architecture(contract, files, prompts)

        enforcement_findings = [
            f for f in findings if f.finding_type == "APPROVAL_ENFORCEMENT_GAP"
        ]
        assert len(enforcement_findings) == 1
        assert enforcement_findings[0].gap_type == GapType.ENFORCEMENT_GAP


class TestFindingsHaveRequiredFields:
    """Tests that all findings have gap_type and evidence."""

    def test_all_findings_have_gap_type_and_evidence(self):
        """Every finding must have gap_type and at least one evidence entry."""
        tools = [
            _make_tool("delete_record", SideEffectLevel.DESTRUCTIVE),
        ]
        contract = _make_contract(tools=tools)
        prompts = [_make_prompt("Handle requests.")]
        files = []

        _, findings = audit_architecture(contract, files, prompts)

        assert len(findings) > 0, "Expected at least some findings for this scenario"
        for finding in findings:
            assert finding.gap_type is not None, f"Finding {finding.finding_type} missing gap_type"
            assert isinstance(finding.gap_type, GapType), (
                f"Finding {finding.finding_type} has invalid gap_type: {finding.gap_type}"
            )
            assert len(finding.evidence) > 0, (
                f"Finding {finding.finding_type} has no evidence"
            )


class TestDecisionPolicy:
    """Tests for Autonomy & Decision-Making dimension."""

    def test_emits_decision_policy_gap_when_no_decision_language(self):
        """DECISION_POLICY_GAP emitted when no decision keywords found."""
        contract = _make_contract()
        prompts = [_make_prompt("You are a helpful assistant.")]
        files = []

        _, findings = audit_architecture(contract, files, prompts)

        gap_findings = [f for f in findings if f.finding_type == "DECISION_POLICY_GAP"]
        assert len(gap_findings) == 1
        assert gap_findings[0].gap_type == GapType.POLICY_GAP

    def test_populates_decision_policy_when_detected(self):
        """DecisionPolicy populated when planning language detected."""
        contract = _make_contract()
        prompts = [_make_prompt("You are an assistant. Break down tasks step by step and plan.")]
        files = []

        updated_contract, findings = audit_architecture(contract, files, prompts)

        assert updated_contract.decision_policy is not None
        assert updated_contract.decision_policy.strategy != ""


class TestFailureHandling:
    """Tests for Failure Handling dimension."""

    def test_emits_retry_policy_gap_when_tools_no_retry(self):
        """RETRY_POLICY_GAP emitted when tools exist but no retry detected."""
        tools = [_make_tool("get_data", SideEffectLevel.NONE)]
        contract = _make_contract(tools=tools)
        prompts = [_make_prompt("You are a data fetcher.")]
        files = []

        _, findings = audit_architecture(contract, files, prompts)

        retry_findings = [f for f in findings if f.finding_type == "RETRY_POLICY_GAP"]
        assert len(retry_findings) == 1
        assert retry_findings[0].gap_type == GapType.POLICY_GAP

    def test_no_retry_gap_when_retry_keyword_present(self):
        """No RETRY_POLICY_GAP when retry keywords found in prompts."""
        tools = [_make_tool("get_data", SideEffectLevel.NONE)]
        contract = _make_contract(tools=tools)
        prompts = [_make_prompt("You are a data fetcher. If a call fails, retry up to 3 times.")]
        files = []

        _, findings = audit_architecture(contract, files, prompts)

        retry_findings = [f for f in findings if f.finding_type == "RETRY_POLICY_GAP"]
        assert len(retry_findings) == 0


class TestOrchestration:
    """Tests for Orchestration dimension."""

    def test_no_orchestration_findings_for_single_agent(self):
        """No orchestration findings when no multi-agent indicators."""
        contract = _make_contract()
        prompts = [_make_prompt("You are a helpful assistant.")]
        files = []

        _, findings = audit_architecture(contract, files, prompts)

        orchestration_findings = [
            f for f in findings
            if f.finding_type in (
                "ORCHESTRATION_UNSPECIFIED",
                "UNBOUNDED_DELEGATION",
                "SHARED_STATE_UNSPECIFIED",
            )
        ]
        assert len(orchestration_findings) == 0

    def test_emits_orchestration_findings_for_multi_agent(self):
        """Orchestration findings emitted when multi-agent indicators detected."""
        contract = _make_contract()
        prompts = [
            _make_prompt("You are a supervisor agent that can delegate tasks to worker agents."),
        ]
        files = []

        _, findings = audit_architecture(contract, files, prompts)

        # Should detect multi-agent (delegate, supervisor, worker keywords)
        orchestration_findings = [
            f for f in findings
            if f.finding_type in (
                "ORCHESTRATION_UNSPECIFIED",
                "UNBOUNDED_DELEGATION",
                "SHARED_STATE_UNSPECIFIED",
            )
        ]
        assert len(orchestration_findings) > 0
