"""Unit tests for the LLM analyzer layer (base + code review analyzer)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from llm_agent_battery.analyzers.base import (
    AnalyzerRegistry,
    BaseAnalyzer,
    extract_json_from_response,
    parse_findings_from_json,
)
from llm_agent_battery.analyzers.code_review_analyzer import CodeReviewAnalyzer
from llm_agent_battery.models import (
    ArchitectureStyle,
    CodeChunk,
    FindingCategory,
    ReviewProfile,
    Severity,
)


# --- extract_json_from_response tests ---


class TestExtractJsonFromResponse:
    """Tests for JSON extraction from LLM responses."""

    def test_raw_json_array(self) -> None:
        text = '[{"severity": "high", "title": "bug"}]'
        assert extract_json_from_response(text) == text.strip()

    def test_raw_json_object(self) -> None:
        text = '{"findings": [{"severity": "high"}]}'
        assert extract_json_from_response(text) == text.strip()

    def test_json_in_json_code_block(self) -> None:
        text = 'Here are findings:\n```json\n[{"severity": "high"}]\n```\nDone.'
        result = extract_json_from_response(text)
        assert result == '[{"severity": "high"}]'

    def test_json_in_generic_code_block(self) -> None:
        text = 'Results:\n```\n[{"severity": "low"}]\n```'
        result = extract_json_from_response(text)
        assert result == '[{"severity": "low"}]'

    def test_whitespace_handling(self) -> None:
        text = '  \n  [{"title": "test"}]  \n  '
        result = extract_json_from_response(text)
        assert result == '[{"title": "test"}]'

    def test_no_json_returns_stripped(self) -> None:
        text = "No issues found in this code."
        result = extract_json_from_response(text)
        assert result == "No issues found in this code."

    def test_empty_array(self) -> None:
        text = "```json\n[]\n```"
        result = extract_json_from_response(text)
        assert result == "[]"


# --- parse_findings_from_json tests ---


class TestParseFindingsFromJson:
    """Tests for parsing JSON strings into Finding objects."""

    def test_valid_array_of_findings(self) -> None:
        raw = '[{"severity": "high", "category": "logic_error", "location": "foo", "title": "Bug", "description": "desc", "impact": "breaks"}]'
        findings = parse_findings_from_json(raw, "test.py")
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert findings[0].category == FindingCategory.LOGIC_ERROR
        assert findings[0].file_path == "test.py"
        assert findings[0].title == "Bug"
        assert findings[0].source_layer == "llm"

    def test_findings_key_wrapper(self) -> None:
        raw = '{"findings": [{"severity": "medium", "category": "correctness", "location": "bar", "title": "Issue", "description": "d", "impact": "i"}]}'
        findings = parse_findings_from_json(raw, "module.py")
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM

    def test_empty_array(self) -> None:
        findings = parse_findings_from_json("[]", "test.py")
        assert findings == []

    def test_invalid_json_returns_empty(self) -> None:
        findings = parse_findings_from_json("not json at all", "test.py")
        assert findings == []

    def test_missing_fields_uses_defaults(self) -> None:
        raw = '[{"title": "Something"}]'
        findings = parse_findings_from_json(raw, "file.py")
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM  # default
        assert findings[0].category == FindingCategory.CORRECTNESS  # default
        assert findings[0].location == "unknown"
        assert findings[0].file_path == "file.py"

    def test_invalid_severity_defaults_to_medium(self) -> None:
        raw = '[{"severity": "super_critical", "title": "x", "location": "y", "description": "d", "impact": "i", "category": "logic_error"}]'
        findings = parse_findings_from_json(raw, "f.py")
        assert findings[0].severity == Severity.MEDIUM

    def test_invalid_category_defaults_to_correctness(self) -> None:
        raw = '[{"severity": "high", "category": "unknown_cat", "title": "x", "location": "y", "description": "d", "impact": "i"}]'
        findings = parse_findings_from_json(raw, "f.py")
        assert findings[0].category == FindingCategory.CORRECTNESS

    def test_non_dict_items_skipped(self) -> None:
        raw = '["string_item", {"severity": "low", "title": "real", "location": "z", "description": "d", "impact": "i", "category": "edge_case"}]'
        findings = parse_findings_from_json(raw, "f.py")
        assert len(findings) == 1
        assert findings[0].title == "real"

    def test_unexpected_structure_returns_empty(self) -> None:
        raw = '{"something_else": 42}'
        findings = parse_findings_from_json(raw, "f.py")
        assert findings == []


# --- AnalyzerRegistry tests ---


class TestAnalyzerRegistry:
    """Tests for the AnalyzerRegistry."""

    def test_register_and_get_all(self) -> None:
        registry = AnalyzerRegistry()
        analyzer = CodeReviewAnalyzer()
        registry.register(analyzer)
        assert registry.get_all() == [analyzer]

    def test_empty_registry(self) -> None:
        registry = AnalyzerRegistry()
        assert registry.get_all() == []
        assert len(registry) == 0

    def test_multiple_registrations(self) -> None:
        registry = AnalyzerRegistry()
        a1 = CodeReviewAnalyzer()
        a2 = CodeReviewAnalyzer()
        registry.register(a1)
        registry.register(a2)
        assert len(registry) == 2
        assert registry.get_all() == [a1, a2]

    def test_clear(self) -> None:
        registry = AnalyzerRegistry()
        registry.register(CodeReviewAnalyzer())
        registry.clear()
        assert len(registry) == 0

    def test_get_all_returns_copy(self) -> None:
        registry = AnalyzerRegistry()
        registry.register(CodeReviewAnalyzer())
        result = registry.get_all()
        result.clear()
        assert len(registry) == 1  # original unchanged


# --- CodeReviewAnalyzer tests ---


class TestCodeReviewAnalyzer:
    """Tests for the CodeReviewAnalyzer."""

    def test_system_prompt_without_profile(self) -> None:
        analyzer = CodeReviewAnalyzer()
        prompt = analyzer.system_prompt(None)
        assert "expert code reviewer" in prompt
        assert "JSON array" in prompt
        assert "logic_error" in prompt

    def test_system_prompt_with_profile(self) -> None:
        profile = ReviewProfile(
            name="test-profile",
            architecture_style=ArchitectureStyle.MULTI_AGENT,
            system_prompt_template="Focus on delegation patterns.",
            focus_areas=["inter-agent communication", "delegation correctness"],
            anti_patterns=["circular delegation", "missing timeout"],
        )
        analyzer = CodeReviewAnalyzer()
        prompt = analyzer.system_prompt(profile)
        assert "multi-agent-orchestrated" in prompt
        assert "Focus on delegation patterns." in prompt
        assert "inter-agent communication" in prompt
        assert "circular delegation" in prompt
        assert "JSON array" in prompt

    def test_focus_areas(self) -> None:
        analyzer = CodeReviewAnalyzer()
        areas = analyzer.focus_areas()
        assert "logic_error" in areas
        assert "security" in areas
        assert len(areas) == 6


# --- BaseAnalyzer.analyze_chunk tests ---


class TestAnalyzeChunk:
    """Tests for the BaseAnalyzer.analyze_chunk integration."""

    @pytest.fixture
    def chunk(self) -> CodeChunk:
        return CodeChunk(
            file_path="src/agent.py",
            chunk_name="process_request",
            content="def process_request(data):\n    return data['key']",
            functions=["process_request"],
            preamble="import json",
            start_line=1,
            end_line=2,
        )

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.converse = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_successful_analysis(self, chunk: CodeChunk, mock_client: AsyncMock) -> None:
        mock_client.converse.return_value = '[{"severity": "high", "category": "edge_case", "location": "process_request", "title": "Missing key check", "description": "No KeyError handling", "impact": "Crashes on missing key"}]'

        analyzer = CodeReviewAnalyzer()
        findings = await analyzer.analyze_chunk(chunk, "Agent request handler", mock_client)

        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert findings[0].title == "Missing key check"
        assert findings[0].file_path == "src/agent.py"

    @pytest.mark.asyncio
    async def test_llm_returns_empty_array(self, chunk: CodeChunk, mock_client: AsyncMock) -> None:
        mock_client.converse.return_value = "[]"

        analyzer = CodeReviewAnalyzer()
        findings = await analyzer.analyze_chunk(chunk, "", mock_client)

        assert findings == []

    @pytest.mark.asyncio
    async def test_llm_returns_markdown_wrapped(self, chunk: CodeChunk, mock_client: AsyncMock) -> None:
        mock_client.converse.return_value = '```json\n[{"severity": "low", "category": "design_flaw", "location": "process_request", "title": "Tight coupling", "description": "desc", "impact": "imp"}]\n```'

        analyzer = CodeReviewAnalyzer()
        findings = await analyzer.analyze_chunk(chunk, "", mock_client)

        assert len(findings) == 1
        assert findings[0].severity == Severity.LOW

    @pytest.mark.asyncio
    async def test_llm_call_failure_returns_empty(self, chunk: CodeChunk, mock_client: AsyncMock) -> None:
        mock_client.converse.side_effect = RuntimeError("API error")

        analyzer = CodeReviewAnalyzer()
        findings = await analyzer.analyze_chunk(chunk, "", mock_client)

        assert findings == []

    @pytest.mark.asyncio
    async def test_llm_returns_unparseable_text(self, chunk: CodeChunk, mock_client: AsyncMock) -> None:
        mock_client.converse.return_value = "I found no issues in this code. Everything looks fine."

        analyzer = CodeReviewAnalyzer()
        findings = await analyzer.analyze_chunk(chunk, "", mock_client)

        assert findings == []

    @pytest.mark.asyncio
    async def test_user_message_includes_context(self, chunk: CodeChunk, mock_client: AsyncMock) -> None:
        mock_client.converse.return_value = "[]"

        analyzer = CodeReviewAnalyzer()
        await analyzer.analyze_chunk(chunk, "Pipeline orchestrator", mock_client)

        call_args = mock_client.converse.call_args
        user_msg = call_args[0][1]  # second positional arg
        assert "src/agent.py" in user_msg
        assert "process_request" in user_msg
        assert "Pipeline orchestrator" in user_msg
        assert "import json" in user_msg

    @pytest.mark.asyncio
    async def test_profile_passed_to_system_prompt(self, chunk: CodeChunk, mock_client: AsyncMock) -> None:
        mock_client.converse.return_value = "[]"

        profile = ReviewProfile(
            name="single-agent",
            architecture_style=ArchitectureStyle.SINGLE_AGENT,
            system_prompt_template="Check for single-point-of-failure.",
            focus_areas=["error recovery"],
            anti_patterns=["missing fallback"],
        )

        analyzer = CodeReviewAnalyzer()
        await analyzer.analyze_chunk(chunk, "", mock_client, profile=profile)

        call_args = mock_client.converse.call_args
        system_msg = call_args[0][0]  # first positional arg
        assert "single-agent" in system_msg
        assert "single-point-of-failure" in system_msg
