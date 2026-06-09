"""Unit tests for test_generator module and YAML exporter."""

from __future__ import annotations

from pathlib import Path

import yaml

from agentbattery.models import (
    AgentContract,
    Evidence,
    Finding,
    GapType,
    GeneratedTest,
    Obligation,
    ObligationType,
    PromptArtifact,
    RiskLevel,
    SideEffectLevel,
    ToolArtifact,
)
from agentbattery.test_generator import generate_tests, write_generated_tests
from agentbattery.exporters.yaml_exporter import export_yaml


def _make_contract(
    tools: list[ToolArtifact] | None = None,
    obligations: list[Obligation] | None = None,
) -> AgentContract:
    """Helper to build a minimal AgentContract."""
    return AgentContract(
        prompts=[],
        tools=tools or [],
        obligations=obligations or [],
        forbidden_transitions=[],
        risk_map={},
    )


def _make_finding(
    finding_type: str = "ENFORCEMENT_GAP",
    severity: RiskLevel = RiskLevel.HIGH,
    gap_type: GapType = GapType.ENFORCEMENT_GAP,
    title: str = "No confirmation precondition detected for tool 'send_email'",
    description: str = "Obligation requires confirmation before tool 'send_email'.",
    tool_name: str = "send_email",
    obligation_id: str = "ob_abc123def4",
) -> Finding:
    """Helper to build a Finding with typical evidence."""
    return Finding(
        finding_type=finding_type,
        severity=severity,
        gap_type=gap_type,
        title=title,
        description=description,
        evidence=[
            Evidence(
                source="system_prompt.md",
                location=obligation_id,
                detail=f"Obligation source: \"Always confirm before sending emails\"",
            ),
            Evidence(
                source="tools.py",
                location=tool_name,
                detail="No confirmation precondition detected in tool source.",
            ),
        ],
        remediation=f"Add a precondition to tool '{tool_name}' that enforces user confirmation.",
        transparency=f"Raised because obligation '{obligation_id}' is linked to tool '{tool_name}'.",
    )


class TestGenerateTestsConfirmation:
    """Tests for generating confirmation tests from ENFORCEMENT_GAP findings."""

    def test_generates_confirmation_test_from_enforcement_gap_for_send_email(self):
        """ENFORCEMENT_GAP finding for send_email generates a confirmation test."""
        finding = _make_finding(
            finding_type="ENFORCEMENT_GAP",
            severity=RiskLevel.HIGH,
            gap_type=GapType.ENFORCEMENT_GAP,
            title="No confirmation precondition detected for tool 'send_email'",
            description="Obligation requires confirmation before tool 'send_email'.",
            tool_name="send_email",
        )
        contract = _make_contract(
            tools=[
                ToolArtifact(
                    name="send_email",
                    description="Send an email",
                    source_path="tools.py",
                    side_effect_level=SideEffectLevel.EXTERNAL_WRITE,
                )
            ]
        )

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        test = tests[0]
        assert test.test_type == "confirmation"
        assert "send_email" in test.setup.get("linked_tools", [])
        assert any("must_call" in a or "must_not_call" in a for a in test.assertions)

    def test_generated_test_includes_finding_id(self):
        """Generated test includes finding_id for traceability."""
        finding = _make_finding()
        contract = _make_contract()

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        assert tests[0].finding_id != ""
        assert len(tests[0].finding_id) == 12  # sha256 truncated to 12 chars

    def test_generated_test_includes_gap_type_and_severity_tags(self):
        """Generated test includes gap_type and severity in tags."""
        finding = _make_finding(
            severity=RiskLevel.HIGH,
            gap_type=GapType.ENFORCEMENT_GAP,
        )
        contract = _make_contract()

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        tags = tests[0].tags
        assert "gap_type:ENFORCEMENT_GAP" in tags
        assert "severity:HIGH" in tags

    def test_generated_test_has_stable_id(self):
        """Test IDs are deterministic (same inputs → same ID)."""
        finding = _make_finding()
        contract = _make_contract()

        tests1 = generate_tests([finding], contract)
        tests2 = generate_tests([finding], contract)

        assert tests1[0].id == tests2[0].id
        assert tests1[0].id.startswith("generated_")


class TestGenerateTestsRegression:
    """Tests for generating regression tests from TRACE_VIOLATION findings."""

    def test_generates_regression_test_from_trace_violation(self):
        """TRACE_VIOLATION finding generates a regression test."""
        finding = Finding(
            finding_type="MISSING_CONFIRMATION",
            severity=RiskLevel.HIGH,
            gap_type=GapType.TRACE_VIOLATION,
            title="No confirmation before send_email",
            description=(
                "Tool 'send_email' was called without a preceding user confirmation step."
            ),
            evidence=[
                Evidence(
                    source="trace.jsonl",
                    location="step 3",
                    detail="Tool call to 'send_email' at step 3 with no prior user confirmation",
                )
            ],
            remediation="Add a confirmation step before calling 'send_email'.",
            transparency="No user message containing confirmation keywords was found.",
        )
        contract = _make_contract()

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        test = tests[0]
        assert test.test_type == "regression"
        assert "gap_type:TRACE_VIOLATION" in test.tags
        assert "severity:HIGH" in test.tags
        assert test.finding_id != ""

    def test_regression_test_includes_finding_type_tag(self):
        """Regression test includes finding_type in tags."""
        finding = Finding(
            finding_type="FORBIDDEN_TOOL_USE",
            severity=RiskLevel.CRITICAL,
            gap_type=GapType.TRACE_VIOLATION,
            title="Forbidden tool use: delete_all without user_confirmation",
            description="Tool 'delete_all' was called without the required predecessor.",
            evidence=[
                Evidence(
                    source="trace.jsonl",
                    location="step 5",
                    detail="Tool call to 'delete_all' at step 5",
                )
            ],
        )
        contract = _make_contract()

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        assert "finding_type:FORBIDDEN_TOOL_USE" in tests[0].tags


class TestGenerateTestsOtherTypes:
    """Tests for other test type generation."""

    def test_generates_policy_lookup_test(self):
        """ENFORCEMENT_GAP with policy keywords generates policy_lookup test."""
        finding = Finding(
            finding_type="ENFORCEMENT_GAP",
            severity=RiskLevel.HIGH,
            gap_type=GapType.ENFORCEMENT_GAP,
            title="No policy/eligibility precondition detected for financial tool 'issue_refund'",
            description="Tool 'issue_refund' appears to be a financial operation but no policy precondition was detected.",
            evidence=[
                Evidence(
                    source="tools.py",
                    location="issue_refund",
                    detail="No policy/eligibility precondition detected.",
                )
            ],
        )
        contract = _make_contract()

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        assert tests[0].test_type == "policy_lookup"

    def test_generates_injection_test(self):
        """POLICY_GAP with retrieval injection keywords generates injection test."""
        finding = Finding(
            finding_type="POLICY_GAP",
            severity=RiskLevel.HIGH,
            gap_type=GapType.POLICY_GAP,
            title="No retrieval injection guard detected",
            description="Retrieval tools are present alongside write tools but no injection guard.",
            evidence=[
                Evidence(
                    source="contract",
                    location="obligations",
                    detail="No RETRIEVAL_INJECTION_GUARD obligation detected.",
                )
            ],
        )
        contract = _make_contract()

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        assert tests[0].test_type == "injection"

    def test_generates_consistency_test(self):
        """ENFORCEMENT_GAP with consistency keywords generates consistency test."""
        finding = Finding(
            finding_type="ENFORCEMENT_GAP",
            severity=RiskLevel.HIGH,
            gap_type=GapType.ENFORCEMENT_GAP,
            title="No verification step detected for consistency obligation 'ob_xyz'",
            description="Obligation requires final state consistency but no verification tool detected.",
            evidence=[
                Evidence(
                    source="prompt.md",
                    location="ob_xyz123456",
                    detail='Obligation source: "Verify state after update"',
                )
            ],
        )
        contract = _make_contract()

        tests = generate_tests([finding], contract)

        assert len(tests) == 1
        assert tests[0].test_type == "consistency"


class TestGenerateTestsMultiple:
    """Tests for generating tests from multiple findings."""

    def test_generates_test_for_each_finding(self):
        """Each finding produces exactly one test."""
        findings = [
            _make_finding(title="Finding 1", tool_name="tool_a"),
            _make_finding(title="Finding 2", tool_name="tool_b"),
            _make_finding(
                finding_type="MISSING_CONFIRMATION",
                gap_type=GapType.TRACE_VIOLATION,
                title="Trace violation",
                tool_name="tool_c",
            ),
        ]
        contract = _make_contract()

        tests = generate_tests(findings, contract)

        assert len(tests) == 3


class TestWriteGeneratedTests:
    """Tests for write_generated_tests utility."""

    def test_writes_yaml_files(self, tmp_path: Path):
        """write_generated_tests creates YAML files in output directory."""
        tests = [
            GeneratedTest(
                id="test_abc",
                title="Test ABC",
                description="A test",
                finding_id="finding_123",
                test_type="confirmation",
                setup={"scenario": "test scenario"},
                assertions=["must_call: confirm"],
                tags=["gap_type:ENFORCEMENT_GAP", "severity:HIGH"],
            )
        ]

        paths = write_generated_tests(tests, tmp_path / "output")

        assert len(paths) == 1
        assert paths[0].exists()
        assert paths[0].name == "test_abc.yaml"


class TestYamlExporter:
    """Tests for the YAML exporter."""

    def test_produces_parseable_yaml_files(self, tmp_path: Path):
        """YAML exporter produces files parseable by standard YAML parser."""
        tests = [
            GeneratedTest(
                id="generated_enforcement_gap_send_email_abc12345",
                title="Test: No confirmation for send_email",
                description="Confirmation test for send_email",
                finding_id="abc123def456",
                test_type="confirmation",
                setup={
                    "scenario": "User requests send email",
                    "tools_under_test": ["send_email"],
                    "linked_tools": ["send_email"],
                },
                assertions=[
                    "must_call: ask_user_confirmation before send_email",
                    "must_not_call: send_email without prior confirmation",
                ],
                tags=[
                    "gap_type:ENFORCEMENT_GAP",
                    "severity:HIGH",
                    "finding_type:ENFORCEMENT_GAP",
                ],
            ),
            GeneratedTest(
                id="generated_trace_violation_delete_all_xyz98765",
                title="Test: Forbidden delete_all",
                description="Regression test for forbidden tool use",
                finding_id="xyz789abc012",
                test_type="regression",
                setup={"scenario": "Replay trace violation"},
                assertions=["must_not_call: delete_all without required preconditions"],
                tags=[
                    "gap_type:TRACE_VIOLATION",
                    "severity:CRITICAL",
                    "finding_type:FORBIDDEN_TOOL_USE",
                ],
            ),
        ]

        paths = export_yaml(tests, tmp_path / "exported")

        assert len(paths) == 2
        for path in paths:
            assert path.exists()
            # Verify parseable
            with open(path) as f:
                data = yaml.safe_load(f)
            assert isinstance(data, dict)
            assert "id" in data
            assert "title" in data
            assert "test_type" in data
            assert "tags" in data
            assert "assertions" in data

    def test_yaml_files_named_by_test_id(self, tmp_path: Path):
        """Each YAML file is named by test.id + '.yaml'."""
        tests = [
            GeneratedTest(
                id="my_test_id",
                title="Title",
                description="Desc",
                test_type="confirmation",
                setup={},
                assertions=[],
                tags=[],
            )
        ]

        paths = export_yaml(tests, tmp_path / "out")

        assert paths[0].name == "my_test_id.yaml"

    def test_yaml_round_trip_preserves_data(self, tmp_path: Path):
        """Exported YAML can be loaded back and matches original data."""
        test = GeneratedTest(
            id="roundtrip_test",
            title="Round Trip",
            description="Testing round trip",
            finding_id="finding_abc",
            test_type="regression",
            setup={"scenario": "test", "tools_under_test": ["tool_a"]},
            assertions=["must_not_call: tool_a without preconditions"],
            tags=["gap_type:TRACE_VIOLATION", "severity:HIGH"],
        )

        paths = export_yaml([test], tmp_path / "rt")

        with open(paths[0]) as f:
            loaded = yaml.safe_load(f)

        assert loaded["id"] == test.id
        assert loaded["title"] == test.title
        assert loaded["finding_id"] == test.finding_id
        assert loaded["test_type"] == test.test_type
        assert loaded["tags"] == test.tags
        assert loaded["assertions"] == test.assertions
