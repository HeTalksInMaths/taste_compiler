"""Trace loader module - parses trace files into AgentTrace objects."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from agentbattery.models import (
    AgentTrace,
    ClassifiedFile,
    FileCategory,
    TraceStep,
    TraceStepType,
)

logger = logging.getLogger(__name__)

# Mapping of "type" field values to TraceStepType
_TYPE_MAP: dict[str, TraceStepType] = {
    "user_message": TraceStepType.USER_MESSAGE,
    "model_message": TraceStepType.AGENT_MESSAGE,
    "assistant": TraceStepType.AGENT_MESSAGE,
    "tool_call": TraceStepType.TOOL_CALL,
    "tool_result": TraceStepType.TOOL_RESULT,
}


def _infer_step_type(entry: dict) -> TraceStepType | None:
    """Infer TraceStepType from a trace entry dict.

    Checks the "type" field first, then falls back to role-based inference.

    Args:
        entry: A dict representing a single trace entry.

    Returns:
        The inferred TraceStepType, or None if type cannot be determined.
    """
    # Check explicit "type" field
    type_value = entry.get("type", "").lower().strip()
    if type_value in _TYPE_MAP:
        return _TYPE_MAP[type_value]

    # Fallback: check role field
    role = entry.get("role", "").lower().strip()
    if role == "user":
        return TraceStepType.USER_MESSAGE
    if role in ("assistant", "model"):
        return TraceStepType.AGENT_MESSAGE
    if role == "tool":
        return TraceStepType.TOOL_RESULT

    # Check for presence of specific keys
    if "tool_call" in entry or "function_call" in entry:
        return TraceStepType.TOOL_CALL
    if "tool_result" in entry or "function_result" in entry:
        return TraceStepType.TOOL_RESULT

    return None


def _parse_entry(entry: dict, index: int) -> TraceStep | None:
    """Parse a single trace entry dict into a TraceStep.

    Args:
        entry: A dict representing a single trace entry.
        index: The step index in the trace.

    Returns:
        A TraceStep if parsing succeeds, None if the entry is malformed.
    """
    step_type = _infer_step_type(entry)
    if step_type is None:
        return None

    tool_name = entry.get("tool", "") or entry.get("tool_name", "") or ""
    arguments = entry.get("args", {}) or entry.get("arguments", {}) or {}

    # Extract result: prefer "error" > "result" > "content"
    if entry.get("error"):
        result = str(entry["error"])
    elif "result" in entry:
        result = str(entry["result"]) if entry["result"] is not None else ""
    elif "content" in entry:
        result = str(entry["content"]) if entry["content"] is not None else ""
    else:
        result = ""

    return TraceStep(
        type=step_type,
        tool_name=tool_name,
        arguments=arguments if isinstance(arguments, dict) else {},
        result=result,
        index=index,
    )


def _generate_trace_id(source_path: str) -> str:
    """Generate a stable trace ID from source path.

    Args:
        source_path: The source file path.

    Returns:
        A 12-character hex ID derived from the path.
    """
    return hashlib.sha256(source_path.encode()).hexdigest()[:12]


def _parse_jsonl(content: str, source_path: str) -> AgentTrace | None:
    """Parse JSONL content into an AgentTrace.

    Each line is a JSON object representing a trace step.

    Args:
        content: The raw JSONL file content.
        source_path: The source file path for error reporting.

    Returns:
        An AgentTrace, or None if no valid steps could be parsed.
    """
    steps: list[TraceStep] = []
    index = 0

    for line_num, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning(
                "Malformed JSON at %s line %d: %s", source_path, line_num, e
            )
            continue

        if not isinstance(entry, dict):
            logger.warning(
                "Non-object JSON at %s line %d: expected dict, got %s",
                source_path,
                line_num,
                type(entry).__name__,
            )
            continue

        step = _parse_entry(entry, index)
        if step is None:
            logger.warning(
                "Could not infer step type at %s line %d", source_path, line_num
            )
            continue

        steps.append(step)
        index += 1

    if not steps:
        return None

    return AgentTrace(source_path=source_path, steps=steps)


def _parse_json(content: str, source_path: str) -> AgentTrace | None:
    """Parse JSON content with a 'steps' list into an AgentTrace.

    Args:
        content: The raw JSON file content.
        source_path: The source file path for error reporting.

    Returns:
        An AgentTrace, or None if parsing fails.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("Malformed JSON file %s: %s", source_path, e)
        return None

    if not isinstance(data, dict):
        logger.warning("Expected dict at top level of %s", source_path)
        return None

    entries = data.get("steps", [])
    if not isinstance(entries, list):
        logger.warning("Expected 'steps' list in %s", source_path)
        return None

    steps: list[TraceStep] = []
    index = 0

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            logger.warning(
                "Non-object entry at index %d in %s", i, source_path
            )
            continue

        step = _parse_entry(entry, index)
        if step is None:
            logger.warning(
                "Could not infer step type at index %d in %s", i, source_path
            )
            continue

        steps.append(step)
        index += 1

    if not steps:
        return None

    return AgentTrace(source_path=source_path, steps=steps)


def load_traces(files: list[ClassifiedFile]) -> list[AgentTrace]:
    """Parse trace files into AgentTrace objects.

    Handles both JSONL files (line-by-line parsing) and JSON files with
    a "steps" list. Files must be classified as TRACE category.

    Args:
        files: List of ClassifiedFile objects filtered to TRACE category.

    Returns:
        List of successfully parsed AgentTrace objects.
    """
    traces: list[AgentTrace] = []

    for classified_file in files:
        if classified_file.primary_category != FileCategory.TRACE:
            continue

        source_path = str(classified_file.relative_path)
        file_path = classified_file.path

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Could not read trace file %s: %s", source_path, e)
            continue

        # Determine format based on extension
        suffix = file_path.suffix.lower()

        if suffix == ".jsonl":
            trace = _parse_jsonl(content, source_path)
        elif suffix == ".json":
            trace = _parse_json(content, source_path)
        else:
            # Try JSONL first (line-based), fall back to JSON
            trace = _parse_jsonl(content, source_path)
            if trace is None:
                trace = _parse_json(content, source_path)

        if trace is not None:
            traces.append(trace)
        else:
            logger.warning("No valid steps found in trace file %s", source_path)

    return traces
