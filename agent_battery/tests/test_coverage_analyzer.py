"""Unit tests for coverage_analyzer module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from agentbattery.coverage_analyzer import analyze_coverage, get_coverage_findings
from agentbattery.models import (
    AgentContract,
    ClassifiedFile,
    CoverageStatus,
    FileCategory,
    GapType,
    Obligation,
    ObligationType,
    PromptArtifact,
    RiskLevel,
    ToolArtifact,
)


def _make_contract(
    obligations: list[Obligation] | None = None,
    tools: list[ToolArtifact] | None = None,
) -> AgentContract:
    """Helper to build a minimal AgentContract."""
    return AgentContract(
        prompts=[],
        tools=tools or [],
        obligations=obligations or [],
        forbidden_transitions=[],
        risk_map={},
    )


def _make_obligation(
    ob_id: str,
    ob_type: ObligationType,
    source_text: str,
) -> Obligation:
    """Helper to build an Obligation."""
    return Obligation(
        id=ob_id,
        obligation_type=ob_type,
        source_text=source_text,
        source_path="prompt.md",
        linked_tool_names=[],
    )


def _make_eval_file(content: str, filename: str = "test_safety.py") -> ClassifiedFile:
    """Create a temporary eval file and return a ClassifiedFile pointing to it."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=f"_{filename}", delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return ClassifiedFile(
        path=Path(tmp.name),
        relative_path=filename,
        size_bytes=len(content),
        primary_category=FileCategory.EVAL,
    )


class TestCoverageAnalyzer_Missing:
    """Test that obligations are marked MISSING when no eval files exist."""

    def test_marks_obligation_as_missing_when_no_eval_files(self):
        """Obligation with no eval files → MISSING status."""
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="Always confirm before sending email to user",
        )
        contract = _make_contract(obligations=[obligation])

        result = analyze_coverage(contract, [])

        assert len(result.obligations) == 1
        assert result.obligations[0].status == CoverageStatus.MISSING
        assert result.obligations[0].score == 0.0
        assert result.missing_count == 1
        assert result.covered_count == 0
        assert result.partial_count == 0


class TestCoverageAnalyzer_Covered:
    """Test that obligations are marked COVERED when eval file contains obligation keywords."""

    def test_marks_obligation_as_covered_with_matching_eval(self):
        """Obligation tokens matched in eval file → COVERED status."""
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="confirm before sending email",
        )
        contract = _make_contract(obligations=[obligation])

        # Create an eval file that contains the obligation keywords
        eval_file = _make_eval_file(
            "def test_confirm_before_sending_email():\n"
            "    # Test that confirmation is required before sending email\n"
            "    assert agent.confirm() is True\n"
            "    agent.sending()\n"
            "    agent.email()\n"
        )

        result = analyze_coverage(contract, [eval_file])

        assert len(result.obligations) == 1
        assert result.obligations[0].status == CoverageStatus.COVERED
        assert result.obligations[0].score >= 0.6
        assert result.covered_count == 1

    def test_partial_coverage_with_some_matching_tokens(self):
        """Some tokens match but not enough → PARTIAL status."""
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="confirm approval sending email attachment notification",
        )
        contract = _make_contract(obligations=[obligation])

        # Eval file with only some matching keywords
        eval_file = _make_eval_file(
            "def test_email_sending():\n"
            "    # Test email functionality\n"
            "    assert send_email() is not None\n"
        )

        result = analyze_coverage(contract, [eval_file])

        assert len(result.obligations) == 1
        # Should be PARTIAL (some tokens match but not most)
        assert result.obligations[0].status in (
            CoverageStatus.PARTIAL,
            CoverageStatus.MISSING,
        )


class TestCoverageGapFindings:
    """Test that COVERAGE_GAP findings are emitted for MISSING obligations."""

    def test_emits_coverage_gap_for_missing_critical_obligation(self):
        """MISSING obligation emits COVERAGE_GAP finding."""
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="Always confirm before sending email to user",
        )
        contract = _make_contract(obligations=[obligation])

        result = analyze_coverage(contract, [])
        findings = get_coverage_findings(contract, result)

        assert len(findings) >= 1
        finding = findings[0]
        assert finding.gap_type == GapType.COVERAGE_GAP
        assert finding.severity in (RiskLevel.CRITICAL, RiskLevel.HIGH)
        assert finding.finding_type == "COVERAGE_GAP"
        assert len(finding.evidence) > 0
        assert finding.transparency != ""

    def test_no_coverage_gap_for_covered_obligation(self):
        """COVERED obligation should NOT emit COVERAGE_GAP finding."""
        obligation = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="confirm before sending email",
        )
        contract = _make_contract(obligations=[obligation])

        eval_file = _make_eval_file(
            "def test_confirm_before_sending_email():\n"
            "    # Confirm sending email test\n"
            "    confirm()\n"
            "    sending()\n"
            "    email()\n"
        )

        result = analyze_coverage(contract, [eval_file])
        findings = get_coverage_findings(contract, result)

        # No COVERAGE_GAP should be emitted for covered obligations
        gap_findings = [
            f for f in findings if "ob1" in f.title
        ]
        assert len(gap_findings) == 0

    def test_coverage_result_counts(self):
        """CoverageResult should correctly tally covered/partial/missing."""
        ob1 = _make_obligation(
            "ob1",
            ObligationType.CONFIRMATION_REQUIRED,
            source_text="confirm before sending email",
        )
        ob2 = _make_obligation(
            "ob2",
            ObligationType.LOOKUP_REQUIRED,
            source_text="retrieve order details inventory pricing",
        )
        contract = _make_contract(obligations=[ob1, ob2])

        # Only one eval file that covers ob1 but not ob2
        eval_file = _make_eval_file(
            "def test_confirm_before_sending_email():\n"
            "    confirm()\n"
            "    sending()\n"
            "    email()\n"
        )

        result = analyze_coverage(contract, [eval_file])

        assert result.covered_count + result.partial_count + result.missing_count == 2
