"""Unit tests for the offline MockBedrockClient provider."""

import asyncio
import json

from llm_agent_battery.mock_bedrock_client import MockBedrockClient


def _converse(system: str, user: str) -> list[dict]:
    client = MockBedrockClient()
    raw = asyncio.run(client.converse(system, user))
    return json.loads(raw)


class TestInterfaceParity:

    def test_validate_credentials_is_offline_noop(self):
        identity = MockBedrockClient().validate_credentials()
        assert identity["account"] == "mock"

    def test_converse_returns_json_array_string(self):
        raw = asyncio.run(MockBedrockClient().converse("review", "def f(): pass"))
        assert isinstance(raw, str)
        assert isinstance(json.loads(raw), list)

    def test_tracks_token_usage(self):
        client = MockBedrockClient()
        asyncio.run(client.converse("system prompt", "some user content"))
        usage = client.total_usage
        assert usage.input_tokens > 0
        assert usage.total_tokens == usage.input_tokens + usage.output_tokens

    def test_is_deterministic(self):
        system, user = "code review", "try:\n    x()\nexcept Exception:\n    pass\n"
        assert _converse(system, user) == _converse(system, user)


class TestCodeReviewDetection:

    def test_detects_silent_exception(self):
        findings = _converse(
            "code reviewer",
            "def run():\n    try:\n        x()\n    except Exception:\n        pass\n",
        )
        assert any("swallowed exception" in f["title"].lower() for f in findings)

    def test_detects_mutable_default_argument(self):
        findings = _converse("code reviewer", "def acc(items=[]):\n    return items\n")
        assert any("mutable default" in f["title"].lower() for f in findings)

    def test_detects_todo_marker(self):
        findings = _converse("code reviewer", "def run():\n    # TODO: handle errors\n    pass\n")
        assert any(f["category"] == "design_flaw" for f in findings)

    def test_clean_code_yields_no_findings(self):
        findings = _converse("code reviewer", "def add(a, b):\n    return a + b\n")
        assert findings == []

    def test_finding_shape_is_parseable(self):
        findings = _converse("code reviewer", "def acc(items=[]):\n    return items\n")
        required = {"severity", "category", "location", "title", "description", "impact", "remediation"}
        for f in findings:
            assert required <= set(f)


class TestDimensionDetection:

    _AUTONOMY_PROMPT = "You are evaluating ... DECISION-MAKING AND AUTONOMY patterns ..."
    _HITL_PROMPT = "You are evaluating ... HUMAN-IN-THE-LOOP safeguards ..."

    def test_flags_missing_iteration_budget(self):
        findings = _converse(self._AUTONOMY_PROMPT, "while True:\n    step()\n")
        assert any("iteration budget" in f["title"].lower() for f in findings)

    def test_no_flag_when_budget_present(self):
        findings = _converse(self._AUTONOMY_PROMPT, "for i in range(max_steps):\n    step()\n")
        assert findings == []

    def test_flags_missing_approval_gate(self):
        findings = _converse(self._HITL_PROMPT, "def delete(x):\n    db.delete(x)\n")
        assert any(f["category"] == "security" for f in findings)

    def test_no_flag_when_confirmation_present(self):
        findings = _converse(self._HITL_PROMPT, "if confirm():\n    db.delete(x)\n")
        assert findings == []
