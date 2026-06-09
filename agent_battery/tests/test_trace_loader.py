"""Unit tests for the trace loader module."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from agentbattery.models import (
    ClassifiedFile,
    FileCategory,
    TraceStepType,
)
from agentbattery.trace_loader import load_traces


def _make_trace_file(
    tmp_dir: Path, filename: str, content: str
) -> ClassifiedFile:
    """Create a trace file on disk and return a ClassifiedFile for it."""
    file_path = tmp_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return ClassifiedFile(
        path=file_path,
        relative_path=filename,
        size_bytes=len(content.encode()),
        primary_category=FileCategory.TRACE,
    )


class TestTraceLoaderJSONL:
    """Tests for JSONL trace file parsing."""

    def test_parses_jsonl_with_tool_call_and_model_message(self):
        """Parses JSONL with tool_call and model_message types into correct TraceSteps."""
        lines = [
            json.dumps({"type": "user_message", "content": "Send Alex an email saying hi"}),
            json.dumps({"type": "tool_call", "tool": "search_contacts", "args": {"query": "Alex"}}),
            json.dumps({"type": "tool_result", "tool": "search_contacts", "result": "alex@example.com"}),
            json.dumps({"type": "tool_call", "tool": "send_email", "args": {"to": "alex@example.com", "body": "hi"}}),
            json.dumps({"type": "tool_result", "tool": "send_email", "result": "sent"}),
            json.dumps({"type": "model_message", "content": "Done, I sent the email to Alex."}),
        ]
        content = "\n".join(lines)

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "trace.jsonl", content)
            traces = load_traces([classified])

        assert len(traces) == 1
        trace = traces[0]
        assert trace.source_path == "trace.jsonl"
        assert len(trace.steps) == 6

        # Check step types
        assert trace.steps[0].type == TraceStepType.USER_MESSAGE
        assert trace.steps[1].type == TraceStepType.TOOL_CALL
        assert trace.steps[1].tool_name == "search_contacts"
        assert trace.steps[1].arguments == {"query": "Alex"}
        assert trace.steps[2].type == TraceStepType.TOOL_RESULT
        assert trace.steps[2].result == "alex@example.com"
        assert trace.steps[3].type == TraceStepType.TOOL_CALL
        assert trace.steps[3].tool_name == "send_email"
        assert trace.steps[4].type == TraceStepType.TOOL_RESULT
        assert trace.steps[5].type == TraceStepType.AGENT_MESSAGE
        assert "sent" in trace.steps[5].result.lower()

    def test_parses_assistant_type_as_agent_message(self):
        """The 'assistant' type value maps to AGENT_MESSAGE."""
        lines = [
            json.dumps({"type": "assistant", "content": "Hello!"}),
        ]
        content = "\n".join(lines)

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "trace.jsonl", content)
            traces = load_traces([classified])

        assert len(traces) == 1
        assert traces[0].steps[0].type == TraceStepType.AGENT_MESSAGE

    def test_handles_malformed_lines_without_crashing(self):
        """Malformed JSON lines are skipped, valid lines still parsed."""
        lines = [
            "not valid json at all",
            json.dumps({"type": "user_message", "content": "Hello"}),
            "{broken: json",
            json.dumps({"type": "model_message", "content": "Hi there!"}),
            "42",  # valid JSON but not an object
        ]
        content = "\n".join(lines)

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "trace.jsonl", content)
            traces = load_traces([classified])

        assert len(traces) == 1
        trace = traces[0]
        # Only 2 valid steps
        assert len(trace.steps) == 2
        assert trace.steps[0].type == TraceStepType.USER_MESSAGE
        assert trace.steps[1].type == TraceStepType.AGENT_MESSAGE

    def test_extracts_error_field_as_result(self):
        """When error field is present, it becomes the result."""
        lines = [
            json.dumps({"type": "tool_result", "tool": "send_email", "error": "connection timeout"}),
        ]
        content = "\n".join(lines)

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "trace.jsonl", content)
            traces = load_traces([classified])

        assert traces[0].steps[0].result == "connection timeout"

    def test_incremental_index(self):
        """Steps are indexed incrementally from 0."""
        lines = [
            json.dumps({"type": "user_message", "content": "hi"}),
            json.dumps({"type": "tool_call", "tool": "read", "args": {}}),
            json.dumps({"type": "model_message", "content": "ok"}),
        ]
        content = "\n".join(lines)

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "trace.jsonl", content)
            traces = load_traces([classified])

        assert [s.index for s in traces[0].steps] == [0, 1, 2]


class TestTraceLoaderJSON:
    """Tests for JSON trace file parsing with steps list."""

    def test_parses_json_with_steps_list(self):
        """Parses JSON file with a 'steps' list into AgentTrace."""
        data = {
            "steps": [
                {"type": "user_message", "content": "Do something"},
                {"type": "tool_call", "tool": "my_tool", "args": {"x": 1}},
                {"type": "tool_result", "tool": "my_tool", "result": "done"},
                {"type": "model_message", "content": "All done!"},
            ]
        }
        content = json.dumps(data)

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "trace.json", content)
            traces = load_traces([classified])

        assert len(traces) == 1
        assert len(traces[0].steps) == 4
        assert traces[0].steps[0].type == TraceStepType.USER_MESSAGE
        assert traces[0].steps[1].type == TraceStepType.TOOL_CALL
        assert traces[0].steps[1].tool_name == "my_tool"

    def test_skips_non_trace_files(self):
        """Files not classified as TRACE are skipped."""
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            file_path = tmp_path / "code.py"
            file_path.write_text("print('hello')")
            classified = ClassifiedFile(
                path=file_path,
                relative_path="code.py",
                size_bytes=15,
                primary_category=FileCategory.TOOL_SOURCE,
            )
            traces = load_traces([classified])

        assert len(traces) == 0


class TestTraceLoaderEdgeCases:
    """Tests for edge cases in trace loading."""

    def test_empty_jsonl_returns_no_traces(self):
        """Empty JSONL file produces no traces."""
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "empty.jsonl", "")
            traces = load_traces([classified])

        assert len(traces) == 0

    def test_all_malformed_returns_no_traces(self):
        """JSONL where all lines are malformed produces no traces."""
        content = "not json\nalso not json\n{bad"

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "bad.jsonl", content)
            traces = load_traces([classified])

        assert len(traces) == 0

    def test_entries_without_type_field_skipped(self):
        """Entries missing a 'type' field are skipped."""
        lines = [
            json.dumps({"content": "no type field here"}),
            json.dumps({"type": "user_message", "content": "valid"}),
        ]
        content = "\n".join(lines)

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            classified = _make_trace_file(tmp_path, "partial.jsonl", content)
            traces = load_traces([classified])

        assert len(traces) == 1
        assert len(traces[0].steps) == 1
        assert traces[0].steps[0].type == TraceStepType.USER_MESSAGE
