"""File classifier module - assigns categories to discovered files using priority-ordered heuristics."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentbattery.models import ClassifiedFile, DiscoveredFile, FileCategory


# --- Heuristic Functions ---
# Each returns True if the file matches the category.
# Priority order: TRACE > TOOL_SCHEMA > TOOL_SOURCE > PROMPT > POLICY > EVAL > CONFIG > DOC > UNKNOWN


def _read_content(path: Path, max_bytes: int = 64 * 1024) -> str | None:
    """Read file content, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except (OSError, UnicodeDecodeError):
        return None


def _is_trace(path: Path, content: str | None) -> bool:
    """TRACE: .jsonl extension, or JSON with steps/tool_calls/messages[].role keys."""
    if path.suffix == ".jsonl":
        return True

    if content and path.suffix == ".json":
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                if "steps" in data or "tool_calls" in data:
                    return True
                messages = data.get("messages")
                if isinstance(messages, list) and any(
                    isinstance(m, dict) and "role" in m for m in messages
                ):
                    return True
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict) and ("role" in first or "tool_call" in first or "tool_calls" in first):
                    return True
        except (json.JSONDecodeError, TypeError):
            pass

    return False


def _is_tool_schema(path: Path, content: str | None) -> bool:
    """TOOL_SCHEMA: JSON/YAML containing functions[].parameters or tools[].input_schema."""
    if not content:
        return False

    if path.suffix in (".json", ".yaml", ".yml"):
        # Check for OpenAI-style: functions[].parameters
        if path.suffix == ".json":
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    functions = data.get("functions", [])
                    tools = data.get("tools", [])
                    if isinstance(functions, list) and any(
                        isinstance(f, dict) and "parameters" in f for f in functions
                    ):
                        return True
                    if isinstance(tools, list) and any(
                        isinstance(t, dict) and "input_schema" in t for t in tools
                    ):
                        return True
            except (json.JSONDecodeError, TypeError):
                pass
        else:
            # YAML - use simple string matching for performance
            if "functions:" in content and "parameters:" in content:
                return True
            if "tools:" in content and "input_schema:" in content:
                return True

    return False


def _is_tool_source(path: Path, content: str | None) -> bool:
    """TOOL_SOURCE: Python file with @tool/@function_tool/@agent.tool decorator or tool-like function names."""
    if path.suffix != ".py":
        return False

    if not content:
        return False

    # Check for tool decorators
    decorator_patterns = [
        r"@tool\b",
        r"@function_tool\b",
        r"@agent\.tool\b",
    ]
    for pattern in decorator_patterns:
        if re.search(pattern, content):
            return True

    # Check for tool-like function names
    tool_function_patterns = [
        r"def\s+send_email\b",
        r"def\s+delete_\w+",
        r"def\s+create_\w+",
        r"def\s+send_\w+",
    ]
    for pattern in tool_function_patterns:
        if re.search(pattern, content):
            return True

    # Check path-based heuristic: files in a "tools" directory with function definitions
    path_str = str(path).lower()
    if "tools" in path_str.split("/") or "tools" in path_str.split("\\"):
        if re.search(r"def\s+\w+\(", content):
            return True

    return False


def _is_prompt(path: Path, content: str | None) -> bool:
    """PROMPT: Path contains prompt/system/instructions/agent.md/AGENTS.md/CLAUDE.md, or imperative content."""
    path_str = str(path).lower()

    # Check path patterns
    path_patterns = ["prompt", "system", "instructions"]
    for pattern in path_patterns:
        if pattern in path_str:
            return True

    # Check for known agent instruction filenames
    name_lower = path.name.lower()
    if name_lower in ("agent.md", "agents.md", "claude.md"):
        return True

    # Check content for imperative phrases
    if content:
        imperative_patterns = [
            r"\bYou are\b",
            r"\bYou must\b",
            r"\bAlways\b",
            r"\bNever\b",
            r"\bDo not\b",
        ]
        for pattern in imperative_patterns:
            if re.search(pattern, content):
                return True

    return False


def _is_policy(path: Path, content: str | None) -> bool:
    """POLICY: Path contains policy/rules/guardrail/safety/compliance."""
    path_str = str(path).lower()
    policy_patterns = ["policy", "rules", "guardrail", "safety", "compliance"]
    for pattern in policy_patterns:
        if pattern in path_str:
            return True
    return False


def _is_eval(path: Path, content: str | None) -> bool:
    """EVAL: Path contains eval/test_cases/golden/benchmark/cases."""
    path_str = str(path).lower()
    eval_patterns = ["eval", "test_cases", "golden", "benchmark", "cases"]
    for pattern in eval_patterns:
        if pattern in path_str:
            return True
    return False


def _is_config(path: Path, content: str | None) -> bool:
    """CONFIG: .toml, .cfg, or path contains config/settings."""
    if path.suffix in (".toml", ".cfg"):
        return True

    path_str = str(path).lower()
    if "config" in path_str or "settings" in path_str:
        return True

    return False


def _is_doc(path: Path, content: str | None) -> bool:
    """DOC: .md not matching PROMPT/POLICY, or .txt, .rst, README."""
    name_lower = path.name.lower()

    if name_lower.startswith("readme"):
        return True

    if path.suffix in (".txt", ".rst"):
        return True

    if path.suffix == ".md":
        return True

    return False


# Priority-ordered list of heuristics
_HEURISTICS: list[tuple[FileCategory, callable]] = [
    (FileCategory.TRACE, _is_trace),
    (FileCategory.TOOL_SCHEMA, _is_tool_schema),
    (FileCategory.TOOL_SOURCE, _is_tool_source),
    (FileCategory.PROMPT, _is_prompt),
    (FileCategory.POLICY, _is_policy),
    (FileCategory.EVAL, _is_eval),
    (FileCategory.CONFIG, _is_config),
    (FileCategory.DOC, _is_doc),
]


def classify_file(file: DiscoveredFile) -> ClassifiedFile:
    """Assign primary FileCategory using priority-ordered heuristics.

    Runs all heuristics in priority order. The first match becomes the
    primary_category. Remaining matches are recorded as secondary_categories.

    Args:
        file: A DiscoveredFile to classify.

    Returns:
        ClassifiedFile with primary and secondary categories assigned.
    """
    path = file.path
    content = _read_content(path)

    primary: FileCategory | None = None
    secondaries: list[FileCategory] = []

    for category, heuristic in _HEURISTICS:
        if heuristic(path, content):
            if primary is None:
                primary = category
            else:
                secondaries.append(category)

    if primary is None:
        primary = FileCategory.UNKNOWN

    return ClassifiedFile(
        path=file.path,
        relative_path=file.relative_path,
        size_bytes=file.size_bytes,
        primary_category=primary,
        secondary_categories=secondaries,
    )


def classify(file: DiscoveredFile) -> ClassifiedFile:
    """Alias for classify_file for API compatibility."""
    return classify_file(file)


def classify_files(files: list[DiscoveredFile]) -> list[ClassifiedFile]:
    """Classify a list of discovered files.

    Args:
        files: List of DiscoveredFile objects to classify.

    Returns:
        List of ClassifiedFile objects with categories assigned.
    """
    return [classify_file(f) for f in files]
