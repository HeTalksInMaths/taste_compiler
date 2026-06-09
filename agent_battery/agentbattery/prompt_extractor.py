"""Prompt extractor module - extracts structured prompt content from PROMPT-classified files."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

import yaml

from agentbattery.models import ClassifiedFile, PromptArtifact

logger = logging.getLogger(__name__)

# YAML keys that typically hold prompt content
_PROMPT_YAML_KEYS = {"system_prompt", "prompt", "instructions", "content"}

# Python variable patterns that hold prompt content
_PROMPT_VAR_PATTERN = re.compile(
    r"^[A-Z_]*(?:SYSTEM_PROMPT|_PROMPT|_INSTRUCTIONS)$"
)

# Function name patterns that contain prompts
_PROMPT_FUNC_PATTERN = re.compile(r"(?:prompt|system)", re.IGNORECASE)


def _read_file_content(path: Path) -> str | None:
    """Read file content, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logger.warning("Failed to read file %s: %s", path, e)
        return None


def _extract_from_markdown(file: ClassifiedFile) -> list[PromptArtifact]:
    """Extract full text content from a Markdown file."""
    content = _read_file_content(file.path)
    if not content:
        return []

    return [
        PromptArtifact(
            source_path=file.relative_path,
            text=content,
            metadata={"format": "markdown"},
        )
    ]


def _extract_from_yaml(file: ClassifiedFile) -> list[PromptArtifact]:
    """Extract prompt content from known YAML keys."""
    content = _read_file_content(file.path)
    if not content:
        return []

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        logger.warning("Failed to parse YAML file %s: %s", file.path, e)
        return []

    if not isinstance(data, dict):
        return []

    artifacts: list[PromptArtifact] = []
    for key in _PROMPT_YAML_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            artifacts.append(
                PromptArtifact(
                    source_path=file.relative_path,
                    text=value.strip(),
                    metadata={"format": "yaml", "key": key},
                )
            )

    return artifacts


def _extract_from_python(file: ClassifiedFile) -> list[PromptArtifact]:
    """Extract prompt content from Python files.

    Looks for:
    - Variables matching SYSTEM_PROMPT, *_PROMPT, *_INSTRUCTIONS patterns
    - Triple-quoted docstrings in functions named *prompt* or *system*
    """
    content = _read_file_content(file.path)
    if not content:
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.warning("Failed to parse Python file %s: %s", file.path, e)
        return []

    artifacts: list[PromptArtifact] = []

    for node in ast.walk(tree):
        # Check for variable assignments matching prompt patterns
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and _PROMPT_VAR_PATTERN.match(
                    target.id
                ):
                    # Extract string value
                    value = _extract_string_value(node.value)
                    if value:
                        artifacts.append(
                            PromptArtifact(
                                source_path=file.relative_path,
                                text=value,
                                metadata={
                                    "format": "python",
                                    "variable": target.id,
                                },
                            )
                        )

        # Check for functions named *prompt* or *system* with docstrings
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _PROMPT_FUNC_PATTERN.search(node.name):
                docstring = ast.get_docstring(node)
                if docstring:
                    artifacts.append(
                        PromptArtifact(
                            source_path=file.relative_path,
                            text=docstring,
                            metadata={
                                "format": "python",
                                "function": node.name,
                            },
                        )
                    )

    return artifacts


def _extract_string_value(node: ast.expr) -> str | None:
    """Extract a string value from an AST expression node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip() if node.value.strip() else None
    # Handle f-strings or joined strings - skip them
    if isinstance(node, ast.JoinedStr):
        return None
    return None


def extract_prompts(files: list[ClassifiedFile]) -> list[PromptArtifact]:
    """Extract structured prompt content from PROMPT-classified files.

    Handles Markdown, YAML, and Python files with different extraction
    strategies per file type.

    Args:
        files: List of ClassifiedFile objects (should be filtered to PROMPT category).

    Returns:
        List of PromptArtifact objects with extracted prompt text.
    """
    artifacts: list[PromptArtifact] = []

    for file in files:
        try:
            suffix = file.path.suffix.lower()

            if suffix == ".md":
                artifacts.extend(_extract_from_markdown(file))
            elif suffix in (".yaml", ".yml"):
                artifacts.extend(_extract_from_yaml(file))
            elif suffix == ".py":
                artifacts.extend(_extract_from_python(file))
            else:
                # For other file types, try reading as plain text
                content = _read_file_content(file.path)
                if content:
                    artifacts.append(
                        PromptArtifact(
                            source_path=file.relative_path,
                            text=content,
                            metadata={"format": "text"},
                        )
                    )
        except Exception as e:
            logger.warning(
                "Unexpected error extracting prompts from %s: %s", file.path, e
            )
            continue

    return artifacts
