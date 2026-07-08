"""Base analyzer ABC and registry for LLM-powered code analysis.

Provides:
- BaseAnalyzer: Abstract base class that handles Bedrock invocation, JSON parsing,
  and conversion of raw findings into Finding pydantic models.
- AnalyzerRegistry: Simple registry for built-in and custom analyzers.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from llm_agent_battery.bedrock_client import BedrockClient
from llm_agent_battery.models import (
    CodeChunk,
    Finding,
    FindingCategory,
    ReviewProfile,
    Severity,
)

logger = logging.getLogger(__name__)


def extract_json_from_response(text: str) -> str:
    """Extract JSON content from an LLM response.

    Handles three cases:
    1. Raw JSON (starts with [ or {)
    2. JSON inside ```json ... ``` markdown code blocks
    3. JSON inside ``` ... ``` markdown code blocks

    Returns the extracted JSON string, or the original text stripped if no
    code blocks are found.
    """
    stripped = text.strip()

    # Case 1: Already raw JSON
    if stripped.startswith("[") or stripped.startswith("{"):
        return stripped

    # Case 2: ```json ... ``` blocks
    json_block_pattern = re.compile(r"```json\s*\n?(.*?)```", re.DOTALL)
    match = json_block_pattern.search(stripped)
    if match:
        return match.group(1).strip()

    # Case 3: ``` ... ``` blocks (generic code fence)
    generic_block_pattern = re.compile(r"```\s*\n?(.*?)```", re.DOTALL)
    match = generic_block_pattern.search(stripped)
    if match:
        return match.group(1).strip()

    # Fallback: return as-is
    return stripped


def parse_findings_from_json(raw_json: str, file_path: str) -> list[Finding]:
    """Parse a JSON string into a list of Finding objects.

    Handles both a JSON array of finding dicts and a JSON object with a
    "findings" key containing the array.

    Returns an empty list if parsing fails, with a logged warning.
    """
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON from LLM response: %s", e)
        return []

    # Normalize: support both {"findings": [...]} and [...]
    if isinstance(data, dict) and "findings" in data:
        items = data["findings"]
    elif isinstance(data, list):
        items = data
    else:
        logger.warning("Unexpected JSON structure from LLM: expected array or {findings: [...]}")
        return []

    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            finding = Finding(
                severity=_coerce_severity(item.get("severity", "medium")),
                category=_coerce_category(item.get("category", "correctness")),
                file_path=item.get("file_path", file_path),
                location=item.get("location", "unknown"),
                title=item.get("title", "Untitled finding"),
                description=item.get("description", ""),
                impact=item.get("impact", ""),
                remediation=item.get("remediation", ""),
                source_layer="llm",
                confirmed_by_heuristic=False,
            )
            findings.append(finding)
        except Exception as e:
            logger.warning("Skipping malformed finding: %s (error: %s)", item, e)
            continue

    return findings


def _coerce_severity(value: str) -> Severity:
    """Coerce a string to a Severity enum, defaulting to MEDIUM."""
    try:
        return Severity(value.lower())
    except (ValueError, AttributeError):
        return Severity.MEDIUM


def _coerce_category(value: str) -> FindingCategory:
    """Coerce a string to a FindingCategory enum, defaulting to CORRECTNESS."""
    try:
        return FindingCategory(value.lower())
    except (ValueError, AttributeError):
        return FindingCategory.CORRECTNESS


class BaseAnalyzer(ABC):
    """Abstract base class for LLM-powered code analyzers.

    Subclasses define a system prompt and focus areas. The base class handles:
    - Calling client.converse() with the system prompt and chunk content
    - Parsing JSON from the response (handling markdown code blocks)
    - Converting raw JSON findings to Finding pydantic models
    - Error handling (parse failures → empty list with logged warning)
    """

    @abstractmethod
    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        """Return the system prompt for this analyzer.

        Args:
            profile: Optional review profile to customize the prompt for
                     a specific architecture style.
        """
        ...

    @abstractmethod
    def focus_areas(self) -> list[str]:
        """Return the list of focus areas this analyzer checks for."""
        ...

    async def analyze_chunk(
        self,
        chunk: CodeChunk,
        context: str,
        client: BedrockClient,
        profile: Optional[ReviewProfile] = None,
    ) -> list[Finding]:
        """Analyze a code chunk using the LLM and return findings.

        Args:
            chunk: The code chunk to analyze.
            context: Additional context about the file or project.
            client: The BedrockClient instance for LLM calls.
            profile: Optional review profile for prompt customization.

        Returns:
            List of Finding objects. Empty list if analysis fails.
        """
        system = self.system_prompt(profile)
        user_message = self._build_user_message(chunk, context)

        try:
            response = await client.converse(system, user_message)
        except Exception as e:
            logger.warning(
                "LLM call failed for chunk %s in %s: %s",
                chunk.chunk_name,
                chunk.file_path,
                e,
            )
            return []

        # Extract JSON from response (handles markdown code blocks)
        json_str = extract_json_from_response(response)

        # Parse into Finding objects
        findings = parse_findings_from_json(json_str, chunk.file_path)

        return findings

    def _build_user_message(self, chunk: CodeChunk, context: str) -> str:
        """Build the user message sent to the LLM for chunk analysis."""
        parts = [
            f"File: {chunk.file_path}",
            f"Chunk: {chunk.chunk_name}",
        ]
        if chunk.functions:
            parts.append(f"Functions: {', '.join(chunk.functions)}")
        if context:
            parts.append(f"Context: {context}")

        parts.append("")
        if chunk.preamble:
            parts.append(f"Module preamble:\n```python\n{chunk.preamble}\n```\n")

        parts.append(f"```python\n{chunk.content}\n```")
        parts.append("")
        parts.append(
            "Find bugs, logic errors, correctness issues, and design flaws. "
            "Return a JSON array of findings. If no issues found, return []."
        )

        return "\n".join(parts)


class AnalyzerRegistry:
    """Registry for built-in and custom analyzers.

    Allows registering multiple analyzers and retrieving them all for use
    during the analysis pipeline.
    """

    def __init__(self) -> None:
        self._analyzers: list[BaseAnalyzer] = []

    def register(self, analyzer: BaseAnalyzer) -> None:
        """Register an analyzer instance."""
        self._analyzers.append(analyzer)

    def get_all(self) -> list[BaseAnalyzer]:
        """Return all registered analyzers."""
        return list(self._analyzers)

    def clear(self) -> None:
        """Remove all registered analyzers."""
        self._analyzers.clear()

    def __len__(self) -> int:
        return len(self._analyzers)
