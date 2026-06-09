"""Unit tests for the contract compiler module."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from agentbattery.contract_compiler import compile_contract, serialize_contract
from agentbattery.models import (
    AgentContract,
    ForbiddenTransition,
    Obligation,
    ObligationType,
    PromptArtifact,
    SideEffectLevel,
    ToolArtifact,
    ToolParameter,
)


def _make_tool(name: str, description: str, side_effect: SideEffectLevel = SideEffectLevel.NONE) -> ToolArtifact:
    """Helper to create a ToolArtifact for testing."""
    return ToolArtifact(
        name=name,
        description=description,
        parameters=[],
        return_type="Any",
        source_path=f"tools/{name}.py",
        side_effect_level=side_effect,
    )


def _make_prompt(text: str, source_path: str = "prompts/system.md") -> PromptArtifact:
    """Helper to create a PromptArtifact for testing."""
    return PromptArtifact(source_path=source_path, text=text)


def _make_obligation(
    ob_id: str,
    ob_type: ObligationType,
    source_text: str,
    source_path: str = "prompts/system.md",
) -> Obligation:
    """Helper to create an Obligation for testing."""
    return Obligation(
        id=ob_id,
        obligation_type=ob_type,
        source_text=source_text,
        source_path=source_path,
    )


class TestCompileContractLinking:
    """Tests for obligation-to-tool linking in compile_contract."""

    def test_links_obligation_to_tool_by_shared_token(self):
        """Links 'Never send email without confirmation' to send_email tool."""
        tools = [
            _make_tool("send_email", "Send an email to a recipient"),
            _make_tool("read_inbox", "Read emails from the inbox"),
        ]
        obligations = [
            _make_obligation(
                "ob1",
                ObligationType.CONFIRMATION_REQUIRED,
                "Never send email without confirmation",
            ),
        ]
        risk_levels = {"send_email": SideEffectLevel.EXTERNAL_WRITE, "read_inbox": SideEffectLevel.NONE}

        contract = compile_contract(
            prompts=[_make_prompt("System prompt")],
            tools=tools,
            obligations=obligations,
            risk_levels=risk_levels,
        )

        # "email" and "send" are shared tokens between obligation and send_email tool
        assert "send_email" in contract.obligations[0].linked_tool_names

    def test_does_not_link_with_only_stopwords_overlap(self):
        """Obligation with only stopword overlap should NOT link to tool."""
        tools = [_make_tool("calculate_sum", "Add two numbers together")]
        obligations = [
            _make_obligation(
                "ob2",
                ObligationType.ERROR_REPORTING_REQUIRED,
                "Report any failure to the user",
            ),
        ]
        risk_levels = {"calculate_sum": SideEffectLevel.NONE}

        contract = compile_contract(
            prompts=[_make_prompt("System prompt")],
            tools=tools,
            obligations=obligations,
            risk_levels=risk_levels,
        )

        # "to" and "the" are stopwords; no meaningful overlap
        assert "calculate_sum" not in contract.obligations[0].linked_tool_names


class TestForbiddenTransitions:
    """Tests for ForbiddenTransition generation."""

    def test_confirmation_required_generates_transition(self):
        """CONFIRMATION_REQUIRED obligation linked to send_email generates transition."""
        tools = [_make_tool("send_email", "Send an email to a recipient")]
        obligations = [
            _make_obligation(
                "ob_conf",
                ObligationType.CONFIRMATION_REQUIRED,
                "Never send email without confirmation",
            ),
        ]
        risk_levels = {"send_email": SideEffectLevel.EXTERNAL_WRITE}

        contract = compile_contract(
            prompts=[_make_prompt("System prompt")],
            tools=tools,
            obligations=obligations,
            risk_levels=risk_levels,
        )

        # Should have a forbidden transition for send_email
        assert len(contract.forbidden_transitions) >= 1
        transition = next(
            (ft for ft in contract.forbidden_transitions if ft.successor == "send_email"),
            None,
        )
        assert transition is not None
        assert transition.predecessor == "user_confirmation"
        assert transition.obligation_id == "ob_conf"

    def test_policy_check_required_generates_transition(self):
        """POLICY_CHECK_REQUIRED generates policy_check -> tool transition."""
        tools = [_make_tool("issue_refund", "Issue a refund to customer")]
        obligations = [
            _make_obligation(
                "ob_policy",
                ObligationType.POLICY_CHECK_REQUIRED,
                "Check refund policy before issuing refund",
            ),
        ]
        risk_levels = {"issue_refund": SideEffectLevel.EXTERNAL_WRITE}

        contract = compile_contract(
            prompts=[_make_prompt("System prompt")],
            tools=tools,
            obligations=obligations,
            risk_levels=risk_levels,
        )

        transition = next(
            (ft for ft in contract.forbidden_transitions if ft.successor == "issue_refund"),
            None,
        )
        assert transition is not None
        assert transition.predecessor == "policy_check"

    def test_lookup_required_generates_transition(self):
        """LOOKUP_REQUIRED generates lookup -> tool transition."""
        tools = [_make_tool("issue_refund", "Issue a refund to customer")]
        obligations = [
            _make_obligation(
                "ob_lookup",
                ObligationType.LOOKUP_REQUIRED,
                "Look up order before issuing refund",
            ),
        ]
        risk_levels = {"issue_refund": SideEffectLevel.EXTERNAL_WRITE}

        contract = compile_contract(
            prompts=[_make_prompt("System prompt")],
            tools=tools,
            obligations=obligations,
            risk_levels=risk_levels,
        )

        transition = next(
            (ft for ft in contract.forbidden_transitions if ft.successor == "issue_refund"),
            None,
        )
        assert transition is not None
        assert transition.predecessor == "lookup"


class TestContractContents:
    """Tests that compiled contract contains all input artifacts."""

    def test_contract_contains_all_inputs(self):
        """Contract contains all input prompts, tools, and obligations."""
        prompts = [
            _make_prompt("You are a helpful assistant", "prompt1.md"),
            _make_prompt("Always be polite", "prompt2.md"),
        ]
        tools = [
            _make_tool("send_email", "Send email"),
            _make_tool("read_inbox", "Read inbox"),
            _make_tool("delete_file", "Delete a file"),
        ]
        obligations = [
            _make_obligation("ob1", ObligationType.CONFIRMATION_REQUIRED, "Confirm before sending email"),
            _make_obligation("ob2", ObligationType.ERROR_REPORTING_REQUIRED, "Report errors"),
        ]
        risk_levels = {
            "send_email": SideEffectLevel.EXTERNAL_WRITE,
            "read_inbox": SideEffectLevel.NONE,
            "delete_file": SideEffectLevel.DESTRUCTIVE,
        }

        contract = compile_contract(prompts, tools, obligations, risk_levels)

        assert len(contract.prompts) == 2
        assert len(contract.tools) == 3
        assert len(contract.obligations) == 2
        assert contract.risk_map == risk_levels

    def test_risk_map_populated_from_tools(self):
        """Risk map is populated from the tools' side_effect_levels dict."""
        tools = [
            _make_tool("send_email", "Send email", SideEffectLevel.EXTERNAL_WRITE),
            _make_tool("delete_db", "Delete database", SideEffectLevel.DESTRUCTIVE),
        ]
        risk_levels = {
            "send_email": SideEffectLevel.EXTERNAL_WRITE,
            "delete_db": SideEffectLevel.DESTRUCTIVE,
        }

        contract = compile_contract(
            prompts=[_make_prompt("System")],
            tools=tools,
            obligations=[],
            risk_levels=risk_levels,
        )

        assert contract.risk_map["send_email"] == SideEffectLevel.EXTERNAL_WRITE
        assert contract.risk_map["delete_db"] == SideEffectLevel.DESTRUCTIVE


class TestSerializeContract:
    """Tests for contract serialization to YAML."""

    def test_serialize_creates_yaml_files(self):
        """serialize_contract creates contract.yaml and obligations.yaml files."""
        tools = [_make_tool("send_email", "Send email")]
        obligations = [
            _make_obligation("ob1", ObligationType.CONFIRMATION_REQUIRED, "Confirm before send email"),
        ]
        risk_levels = {"send_email": SideEffectLevel.EXTERNAL_WRITE}

        contract = compile_contract(
            prompts=[_make_prompt("System prompt")],
            tools=tools,
            obligations=obligations,
            risk_levels=risk_levels,
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            serialize_contract(contract, output_dir)

            assert (output_dir / "contract.yaml").exists()
            assert (output_dir / "obligations.yaml").exists()

    def test_serialize_contract_yaml_is_valid(self):
        """Serialized contract.yaml is valid YAML and parseable."""
        tools = [_make_tool("send_email", "Send email")]
        obligations = [
            _make_obligation("ob1", ObligationType.CONFIRMATION_REQUIRED, "Confirm before send email"),
        ]
        risk_levels = {"send_email": SideEffectLevel.EXTERNAL_WRITE}

        contract = compile_contract(
            prompts=[_make_prompt("System prompt")],
            tools=tools,
            obligations=obligations,
            risk_levels=risk_levels,
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            serialize_contract(contract, output_dir)

            with open(output_dir / "contract.yaml") as f:
                data = yaml.safe_load(f)

            assert "prompts" in data
            assert "tools" in data
            assert "obligations" in data
            assert "forbidden_transitions" in data
            assert "risk_map" in data

    def test_serialize_obligations_yaml_is_list(self):
        """Serialized obligations.yaml contains a list of obligations."""
        obligations = [
            _make_obligation("ob1", ObligationType.CONFIRMATION_REQUIRED, "Confirm before send email"),
            _make_obligation("ob2", ObligationType.LOOKUP_REQUIRED, "Look up order first"),
        ]

        contract = compile_contract(
            prompts=[_make_prompt("System")],
            tools=[_make_tool("send_email", "Send email")],
            obligations=obligations,
            risk_levels={"send_email": SideEffectLevel.EXTERNAL_WRITE},
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            serialize_contract(contract, output_dir)

            with open(output_dir / "obligations.yaml") as f:
                data = yaml.safe_load(f)

            assert isinstance(data, list)
            assert len(data) == 2

    def test_round_trip_contract(self):
        """Round-trip: serialize contract, load back, verify equivalence."""
        prompts = [_make_prompt("You are a helpful assistant")]
        tools = [
            _make_tool("send_email", "Send an email to a recipient"),
            _make_tool("read_inbox", "Read emails from inbox"),
        ]
        obligations = [
            _make_obligation(
                "ob1",
                ObligationType.CONFIRMATION_REQUIRED,
                "Never send email without confirmation",
            ),
        ]
        risk_levels = {
            "send_email": SideEffectLevel.EXTERNAL_WRITE,
            "read_inbox": SideEffectLevel.NONE,
        }

        contract = compile_contract(prompts, tools, obligations, risk_levels)

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            serialize_contract(contract, output_dir)

            # Load back from YAML
            with open(output_dir / "contract.yaml") as f:
                loaded_data = yaml.safe_load(f)

            # Reconstruct contract from loaded data
            loaded_contract = AgentContract(**loaded_data)

            # Verify structural equivalence
            assert len(loaded_contract.prompts) == len(contract.prompts)
            assert len(loaded_contract.tools) == len(contract.tools)
            assert len(loaded_contract.obligations) == len(contract.obligations)
            assert len(loaded_contract.forbidden_transitions) == len(contract.forbidden_transitions)
            assert loaded_contract.risk_map == contract.risk_map

            # Verify specific content
            assert loaded_contract.prompts[0].text == "You are a helpful assistant"
            assert loaded_contract.tools[0].name == "send_email"
            assert loaded_contract.obligations[0].id == "ob1"
            assert "send_email" in loaded_contract.obligations[0].linked_tool_names
