"""Unit tests for agentbattery.file_classifier module."""

import json
import pytest
from pathlib import Path

from agentbattery.file_classifier import classify_file, classify_files, classify
from agentbattery.models import DiscoveredFile, FileCategory


def _make_file(tmp_path: Path, relative: str, content: str = "") -> DiscoveredFile:
    """Helper to create a real file and return a DiscoveredFile."""
    file_path = tmp_path / relative
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return DiscoveredFile(
        path=file_path,
        relative_path=relative,
        size_bytes=len(content),
    )


class TestPromptClassification:
    """Test PROMPT category assignment."""

    def test_file_in_prompts_directory(self, tmp_path: Path):
        """File in a prompts/ directory is classified as PROMPT."""
        df = _make_file(tmp_path, "prompts/system.md", "You are an assistant.")

        result = classify_file(df)

        assert result.primary_category == FileCategory.PROMPT

    def test_file_with_system_in_path(self, tmp_path: Path):
        """File with 'system' in path is classified as PROMPT."""
        df = _make_file(tmp_path, "system_prompt.md", "Hello")

        result = classify_file(df)

        assert result.primary_category == FileCategory.PROMPT

    def test_file_with_instructions_in_path(self, tmp_path: Path):
        """File with 'instructions' in path is classified as PROMPT."""
        df = _make_file(tmp_path, "instructions.yaml", "content: do stuff")

        result = classify_file(df)

        assert result.primary_category == FileCategory.PROMPT

    def test_file_with_imperative_content(self, tmp_path: Path):
        """File with imperative phrases classified as PROMPT."""
        content = "You must always verify the user's identity before proceeding."
        df = _make_file(tmp_path, "guide.md", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.PROMPT

    def test_agent_md_classified_as_prompt(self, tmp_path: Path):
        """agent.md is classified as PROMPT."""
        df = _make_file(tmp_path, "agent.md", "You are a helpful assistant.")

        result = classify_file(df)

        assert result.primary_category == FileCategory.PROMPT


class TestToolSourceClassification:
    """Test TOOL_SOURCE category assignment."""

    def test_python_file_with_tool_decorator(self, tmp_path: Path):
        """Python file with @tool decorator is classified as TOOL_SOURCE."""
        content = '''
from langchain.tools import tool

@tool
def search_web(query: str) -> str:
    """Search the web."""
    return "results"
'''
        df = _make_file(tmp_path, "tools/search.py", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.TOOL_SOURCE

    def test_python_file_with_function_tool_decorator(self, tmp_path: Path):
        """Python file with @function_tool decorator is classified as TOOL_SOURCE."""
        content = '''
@function_tool
def send_email(to: str, body: str) -> bool:
    """Send an email."""
    return True
'''
        df = _make_file(tmp_path, "tools/email.py", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.TOOL_SOURCE

    def test_python_file_with_agent_tool_decorator(self, tmp_path: Path):
        """Python file with @agent.tool decorator is classified as TOOL_SOURCE."""
        content = '''
@agent.tool
def delete_file(path: str) -> None:
    """Delete a file."""
    pass
'''
        df = _make_file(tmp_path, "agent_tools.py", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.TOOL_SOURCE

    def test_python_file_with_tool_function_name(self, tmp_path: Path):
        """Python file with send_email function is classified as TOOL_SOURCE."""
        content = '''
def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email to the specified recipient."""
    pass
'''
        df = _make_file(tmp_path, "email_tool.py", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.TOOL_SOURCE


class TestTraceClassification:
    """Test TRACE category assignment."""

    def test_jsonl_file_is_trace(self, tmp_path: Path):
        """File with .jsonl extension is classified as TRACE."""
        content = '{"role": "assistant", "content": "hello"}\n{"role": "user", "content": "hi"}\n'
        df = _make_file(tmp_path, "traces/run1.jsonl", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.TRACE

    def test_json_with_steps_key(self, tmp_path: Path):
        """JSON file with 'steps' key is classified as TRACE."""
        data = {"steps": [{"tool": "search", "args": {}}]}
        df = _make_file(tmp_path, "trace.json", json.dumps(data))

        result = classify_file(df)

        assert result.primary_category == FileCategory.TRACE

    def test_json_with_messages_role(self, tmp_path: Path):
        """JSON file with messages[].role is classified as TRACE."""
        data = {"messages": [{"role": "user", "content": "hello"}]}
        df = _make_file(tmp_path, "conversation.json", json.dumps(data))

        result = classify_file(df)

        assert result.primary_category == FileCategory.TRACE


class TestToolSchemaClassification:
    """Test TOOL_SCHEMA category assignment."""

    def test_json_with_functions_parameters(self, tmp_path: Path):
        """JSON with functions[].parameters is classified as TOOL_SCHEMA."""
        data = {
            "functions": [
                {"name": "search", "parameters": {"type": "object", "properties": {}}}
            ]
        }
        df = _make_file(tmp_path, "tools.json", json.dumps(data))

        result = classify_file(df)

        assert result.primary_category == FileCategory.TOOL_SCHEMA

    def test_json_with_tools_input_schema(self, tmp_path: Path):
        """JSON with tools[].input_schema is classified as TOOL_SCHEMA."""
        data = {
            "tools": [
                {"name": "search", "input_schema": {"type": "object", "properties": {}}}
            ]
        }
        df = _make_file(tmp_path, "schema.json", json.dumps(data))

        result = classify_file(df)

        assert result.primary_category == FileCategory.TOOL_SCHEMA


class TestPriorityOrder:
    """Test that priority ordering is respected."""

    def test_trace_takes_priority_over_config(self, tmp_path: Path):
        """TRACE (higher priority) wins over CONFIG for .jsonl in config dir."""
        df = _make_file(tmp_path, "config/trace.jsonl", '{"step": 1}\n')

        result = classify_file(df)

        assert result.primary_category == FileCategory.TRACE

    def test_tool_source_over_prompt(self, tmp_path: Path):
        """TOOL_SOURCE takes priority over PROMPT even if file has imperative content."""
        content = '''
# You must always validate inputs
@tool
def validate_input(data: str) -> bool:
    """Validate user input."""
    return True
'''
        df = _make_file(tmp_path, "tools.py", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.TOOL_SOURCE
        assert FileCategory.PROMPT in result.secondary_categories

    def test_prompt_over_doc(self, tmp_path: Path):
        """PROMPT takes priority over DOC for .md with imperative content."""
        content = "You are an AI assistant. You must follow these rules."
        df = _make_file(tmp_path, "readme.md", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.PROMPT
        assert FileCategory.DOC in result.secondary_categories

    def test_secondary_categories_recorded(self, tmp_path: Path):
        """Secondary categories are recorded for multi-match files."""
        content = "You must always validate. Never skip checks."
        df = _make_file(tmp_path, "policy/rules.md", content)

        result = classify_file(df)

        # PROMPT matches (imperative content + "policy" is POLICY too)
        # The first match by priority wins as primary
        assert result.primary_category == FileCategory.PROMPT
        # POLICY, DOC should be in secondaries
        assert FileCategory.POLICY in result.secondary_categories


class TestFallback:
    """Test UNKNOWN fallback behavior."""

    def test_unknown_for_unrecognized_file(self, tmp_path: Path):
        """Files not matching any heuristic get UNKNOWN."""
        df = _make_file(tmp_path, "data.bin", "\x00\x01\x02")

        result = classify_file(df)

        assert result.primary_category == FileCategory.UNKNOWN


class TestConfigClassification:
    """Test CONFIG category assignment."""

    def test_toml_file(self, tmp_path: Path):
        """TOML file is classified as CONFIG."""
        df = _make_file(tmp_path, "settings.toml", "[section]\nkey = 'value'")

        result = classify_file(df)

        assert result.primary_category == FileCategory.CONFIG


class TestDocClassification:
    """Test DOC category assignment."""

    def test_plain_markdown_is_doc(self, tmp_path: Path):
        """Plain markdown without imperative phrases is DOC."""
        content = "# API Reference\n\nThis document describes the API."
        df = _make_file(tmp_path, "docs/api.md", content)

        result = classify_file(df)

        assert result.primary_category == FileCategory.DOC


class TestClassifyFiles:
    """Test the classify_files convenience function."""

    def test_classifies_list(self, tmp_path: Path):
        """classify_files processes a list of DiscoveredFile objects."""
        f1 = _make_file(tmp_path, "trace.jsonl", '{"step": 1}\n')
        f2 = _make_file(tmp_path, "config.toml", "[section]")
        f3 = _make_file(tmp_path, "unknown.bin", "\x00")

        results = classify_files([f1, f2, f3])

        assert len(results) == 3
        assert results[0].primary_category == FileCategory.TRACE
        assert results[1].primary_category == FileCategory.CONFIG
        assert results[2].primary_category == FileCategory.UNKNOWN

    def test_classify_alias(self, tmp_path: Path):
        """classify() is an alias for classify_file()."""
        df = _make_file(tmp_path, "run.jsonl", '{"data": true}\n')

        result = classify(df)

        assert result.primary_category == FileCategory.TRACE
