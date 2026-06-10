"""Unit tests for the report generator module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentbattery.models import (
    AgentContract,
    AgentProfile,
    CoverageResult,
    CoverageStatus,
    DecisionPolicy,
    Evidence,
    FailurePolicy,
    Finding,
    GapType,
    GeneratedTest,
    HumanInLoopPolicy,
    Obligation,
    ObligationCoverage,
    ObligationType,
    OrchestrationPolicy,
    PromptArtifact,
    RiskLevel,
    SideEffectLevel,
    ToolArtifact,
)
from agentbattery.report import emit_repair_input, generate_report


@pytest.fixture
def sample_contract() -> AgentContract:
    """Create a sample AgentContract for testing."""
    return AgentContract(
        prompts=[
            PromptArtifact(
                source_path="prompts/system.md",
                text="You are an email assistant. Always confirm before sending.",
            )
        ],
        tools=[
            ToolArtifact(
                name="send_email",
                description="Send an email to a recipient",
                source_path="tools/email.py",
                side_effect_level=SideEffectLevel.EXTERNAL_WRITE,
                preconditions=["user_confirmation"],
            ),
            ToolArtifact(
                name="read_inbox",
                description="Read the user's inbox",
                source_path="tools/email.py",
                side_effect_level=SideEffectLevel.NONE,
            ),
        ],
        obligations=[
            Obligation(
                id="ob_abc123def4",
                obligation_type=ObligationType.CONFIRMATION_REQUIRED,
                source_text="Always confirm before sending",
                source_path="prompts/system.md",
                linked_tool_names=["send_email"],
            )
        ],
        risk_map={
            "send_email": SideEffectLevel.EXTERNAL_WRITE,
            "read_inbox": SideEffectLevel.NONE,
        },
        agent_profiles=[
            AgentProfile(
                name="Email Assistant",
                purpose="Help users manage email",
                capabilities=["send", "read"],
                source_evidence=["prompts/system.md"],
            )
        ],
        decision_policy=DecisionPolicy(
            strategy="reactive",
            stop_conditions=["user says done"],
            tool_selection_logic="based on user request",
            source_evidence=["prompts/system.md"],
        ),
        human_in_loop_policy=HumanInLoopPolicy(
            approval_required_tools=["send_email"],
            review_triggers=["sending email"],
            source_evidence=["prompts/system.md"],
        ),
        failure_policy=FailurePolicy(
            retry_strategy="retry once",
            timeout_seconds=30,
            source_evidence=["config.yaml"],
        ),
        orchestration_policy=None,
    )


@pytest.fixture
def sample_findings() -> list[Finding]:
    """Create sample findings with different severities."""
    return [
        Finding(
            finding_type="HITL_GAP",
            severity=RiskLevel.HIGH,
            gap_type=GapType.POLICY_GAP,
            title="Missing confirmation for send_email",
            description="The send_email tool may lack a human confirmation gate",
            evidence=[
                Evidence(source="contract", location="send_email", detail="No HITL gate")
            ],
            remediation="Add confirmation step before send_email",
        ),
        Finding(
            finding_type="POLICY_GAP",
            severity=RiskLevel.CRITICAL,
            gap_type=GapType.POLICY_GAP,
            title="Dangerous tool without obligation",
            description="A destructive tool appears to have no linked obligation",
            evidence=[
                Evidence(source="mismatch_detector", location="delete_file", detail="Zero linked obligations")
            ],
            remediation="Add obligation for delete_file",
        ),
        Finding(
            finding_type="MISSING_CONFIRMATION",
            severity=RiskLevel.MEDIUM,
            gap_type=GapType.TRACE_VIOLATION,
            title="Trace: email sent without confirmation",
            description="Agent sent email without user confirmation in trace",
            evidence=[
                Evidence(source="trace_checker", location="step 3", detail="send_email without confirmation")
            ],
            remediation="Ensure confirmation before sending",
        ),
        Finding(
            finding_type="RETRY_POLICY_GAP",
            severity=RiskLevel.LOW,
            gap_type=GapType.POLICY_GAP,
            title="No retry strategy documented",
            description="No retry/backoff strategy appears to be documented",
            evidence=[],
            remediation="Document retry strategy",
        ),
    ]


@pytest.fixture
def sample_coverage() -> CoverageResult:
    """Create a sample CoverageResult."""
    return CoverageResult(
        obligations=[
            ObligationCoverage(
                obligation_id="ob_abc123def4",
                status=CoverageStatus.COVERED,
                matching_files=["tests/test_email.py"],
                score=0.8,
            )
        ],
        covered_count=1,
        partial_count=0,
        missing_count=0,
    )


@pytest.fixture
def sample_generated_tests() -> list[GeneratedTest]:
    """Create sample generated tests."""
    return [
        GeneratedTest(
            id="generated_hitl_gap_send_email_abc12345",
            title="Test: Missing confirmation for send_email",
            description="Verify confirmation before sending email",
            finding_id="abc123def456",
            test_type="confirmation",
            setup={"scenario": "user requests send email"},
            assertions=["must_call: ask_user_confirmation before send_email"],
            tags=["gap_type:POLICY_GAP", "severity:HIGH"],
        )
    ]


class TestGenerateReport:
    """Tests for generate_report function."""

    def test_generates_md_and_json_files(
        self,
        tmp_path: Path,
        sample_findings: list[Finding],
        sample_coverage: CoverageResult,
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """Report generates latest.md and latest.json files."""
        md_path, json_path = generate_report(
            sample_findings, sample_coverage, sample_generated_tests,
            sample_contract, tmp_path,
        )

        assert md_path.exists()
        assert json_path.exists()
        assert md_path.name == "latest.md"
        assert json_path.name == "latest.json"
        assert md_path.parent.name == "reports"
        assert json_path.parent.name == "reports"

    def test_markdown_contains_required_section_headers(
        self,
        tmp_path: Path,
        sample_findings: list[Finding],
        sample_coverage: CoverageResult,
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """Markdown contains required section headers."""
        md_path, _ = generate_report(
            sample_findings, sample_coverage, sample_generated_tests,
            sample_contract, tmp_path,
        )
        content = md_path.read_text()

        assert "## Summary" in content
        assert "## Architecture Overview" in content
        assert "## Tool Risk Table" in content
        assert "## Obligations List" in content
        assert "## Findings" in content
        assert "## Coverage Analysis" in content
        assert "## Trace Violations" in content
        assert "## Hackathon Agent Architecture Summary" in content
        assert "## Generated Tests" in content
        assert "## Next Actions" in content

    def test_json_is_parseable(
        self,
        tmp_path: Path,
        sample_findings: list[Finding],
        sample_coverage: CoverageResult,
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """JSON is parseable with json.loads."""
        _, json_path = generate_report(
            sample_findings, sample_coverage, sample_generated_tests,
            sample_contract, tmp_path,
        )
        content = json_path.read_text()
        data = json.loads(content)

        assert "repo_root" in data
        assert "generated_at" in data
        assert "findings" in data
        assert "generated_tests" in data
        assert "coverage_summary" in data
        assert "contract_summary" in data

    def test_findings_sorted_by_severity_in_markdown(
        self,
        tmp_path: Path,
        sample_findings: list[Finding],
        sample_coverage: CoverageResult,
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """Findings sorted by severity in markdown (CRITICAL first)."""
        md_path, _ = generate_report(
            sample_findings, sample_coverage, sample_generated_tests,
            sample_contract, tmp_path,
        )
        content = md_path.read_text()

        # CRITICAL should appear before HIGH in the findings section
        critical_pos = content.find("CRITICAL")
        high_pos = content.find("HIGH", critical_pos + 1)
        assert critical_pos < high_pos, "CRITICAL findings should appear before HIGH"

    def test_hackathon_architecture_summary_present(
        self,
        tmp_path: Path,
        sample_findings: list[Finding],
        sample_coverage: CoverageResult,
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """Hackathon Agent Architecture Summary section present with subsections."""
        md_path, _ = generate_report(
            sample_findings, sample_coverage, sample_generated_tests,
            sample_contract, tmp_path,
        )
        content = md_path.read_text()

        assert "## Hackathon Agent Architecture Summary" in content
        assert "### Agent Overview" in content
        assert "### Autonomy & Decision-Making" in content
        assert "### Actions & Tool Use" in content
        assert "### Orchestration" in content
        assert "### Human-in-the-Loop" in content
        assert "### Failure Handling" in content

    def test_empty_findings_produces_valid_report(
        self,
        tmp_path: Path,
        sample_coverage: CoverageResult,
        sample_contract: AgentContract,
    ) -> None:
        """Report works with empty findings and tests."""
        md_path, json_path = generate_report(
            [], sample_coverage, [], sample_contract, tmp_path,
        )

        assert md_path.exists()
        assert json_path.exists()

        content = md_path.read_text()
        assert "PASS" in content

        data = json.loads(json_path.read_text())
        assert data["findings"] == []


class TestEmitRepairInput:
    """Tests for emit_repair_input function."""

    def test_repair_input_is_written_and_parseable(
        self,
        tmp_path: Path,
        sample_findings: list[Finding],
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """repair_input.json is written and parseable."""
        repair_path = emit_repair_input(
            sample_findings, sample_generated_tests, sample_contract, tmp_path,
        )

        assert repair_path.exists()
        assert repair_path.name == "repair_input.json"

        data = json.loads(repair_path.read_text())
        assert "repo_root" in data
        assert "generated_at" in data
        assert "findings" in data
        assert isinstance(data["findings"], list)
        assert len(data["findings"]) == len(sample_findings)

    def test_repair_findings_have_required_fields(
        self,
        tmp_path: Path,
        sample_findings: list[Finding],
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """Each repair finding has required fields."""
        repair_path = emit_repair_input(
            sample_findings, sample_generated_tests, sample_contract, tmp_path,
        )

        data = json.loads(repair_path.read_text())
        for rf in data["findings"]:
            assert "finding_id" in rf
            assert "severity" in rf
            assert "gap_type" in rf
            assert "linked_tools" in rf
            assert "linked_obligations" in rf
            assert "generated_test_ids" in rf
            assert "recommended_repair_type" in rf

    def test_repair_type_inference(
        self,
        tmp_path: Path,
        sample_generated_tests: list[GeneratedTest],
        sample_contract: AgentContract,
    ) -> None:
        """Repair types are correctly inferred from finding characteristics."""
        findings = [
            Finding(
                finding_type="RETRY_POLICY_GAP",
                severity=RiskLevel.LOW,
                gap_type=GapType.POLICY_GAP,
                title="No retry",
                description="No retry strategy",
            ),
            Finding(
                finding_type="MISSING_CONFIRMATION",
                severity=RiskLevel.HIGH,
                gap_type=GapType.TRACE_VIOLATION,
                title="Trace violation",
                description="Missing confirmation in trace",
            ),
        ]

        repair_path = emit_repair_input(
            findings, sample_generated_tests, sample_contract, tmp_path,
        )

        data = json.loads(repair_path.read_text())
        # RETRY_POLICY_GAP → ADD_RETRY_OR_FALLBACK
        assert data["findings"][0]["recommended_repair_type"] == "ADD_RETRY_OR_FALLBACK"
        # TRACE_VIOLATION → ADD_TEST
        assert data["findings"][1]["recommended_repair_type"] == "ADD_TEST"
