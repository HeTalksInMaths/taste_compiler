"""Obligation extractor module - applies pattern registry to extract obligations."""

from __future__ import annotations

import hashlib
import logging
import re

from agentbattery.models import Obligation, ObligationType, PromptArtifact, ToolArtifact

logger = logging.getLogger(__name__)

# Pattern registry: maps ObligationType to a list of compiled regex patterns.
# Each pattern is applied case-insensitively against prompt text and tool metadata.
_PATTERN_REGISTRY: dict[ObligationType, list[re.Pattern[str]]] = {
    ObligationType.CONFIRMATION_REQUIRED: [
        re.compile(r"confirm(?:ation)?\s+before", re.IGNORECASE),
        re.compile(r"ask\s.*user\s.*before", re.IGNORECASE),
        re.compile(r"require[s]?\s.*approval", re.IGNORECASE),
        re.compile(r"never\s.*without\s.*confirm", re.IGNORECASE),
        re.compile(r"explicit\s.*confirmation", re.IGNORECASE),
        re.compile(r"get\s.*confirmation", re.IGNORECASE),
        re.compile(r"obtain\s.*confirmation", re.IGNORECASE),
        re.compile(r"require[s]?\s.*confirmation", re.IGNORECASE),
    ],
    ObligationType.LOOKUP_REQUIRED: [
        re.compile(r"look\s+up", re.IGNORECASE),
        re.compile(r"retrieve\s.*before", re.IGNORECASE),
        re.compile(r"check\s.*first", re.IGNORECASE),
        re.compile(r"fetch\s.*before", re.IGNORECASE),
        re.compile(r"check\s+the\s+database", re.IGNORECASE),
        re.compile(r"check\s+CRM", re.IGNORECASE),
        re.compile(r"verify\s+before\s+answering", re.IGNORECASE),
    ],
    ObligationType.POLICY_CHECK_REQUIRED: [
        re.compile(r"check\s.*policy", re.IGNORECASE),
        re.compile(r"verify\s.*eligibility", re.IGNORECASE),
        re.compile(r"compliance\s.*check", re.IGNORECASE),
        re.compile(r"consult\s+policy", re.IGNORECASE),
        re.compile(r"according\s+to\s+policy", re.IGNORECASE),
        re.compile(r"refund\s+policy", re.IGNORECASE),
    ],
    ObligationType.ERROR_REPORTING_REQUIRED: [
        re.compile(r"report\s.*error", re.IGNORECASE),
        re.compile(r"inform\s.*user\s.*fail", re.IGNORECASE),
        re.compile(r"disclose\s.*error", re.IGNORECASE),
        re.compile(r"if\s+the\s+tool\s+fails", re.IGNORECASE),
        re.compile(r"if\s+an\s+error\s+occurs", re.IGNORECASE),
        re.compile(r"do\s+not\s+claim\s+success", re.IGNORECASE),
        re.compile(r"tell\s+the\s+user\s+it\s+failed", re.IGNORECASE),
    ],
    ObligationType.RETRIEVAL_INJECTION_GUARD: [
        re.compile(r"untrusted", re.IGNORECASE),
        re.compile(r"do\s+not\s+trust", re.IGNORECASE),
        re.compile(r"do\s+not\s+follow\s.*instructions\s.*retrieved", re.IGNORECASE),
        re.compile(r"treat\s.*retrieved\s.*as\s+data", re.IGNORECASE),
        re.compile(r"documents\s+may\s+contain\s+malicious", re.IGNORECASE),
        re.compile(r"retrieved\s+content\s+is\s+untrusted", re.IGNORECASE),
    ],
    ObligationType.FINAL_STATE_CONSISTENCY: [
        re.compile(r"verify\s.*state", re.IGNORECASE),
        re.compile(r"confirm\s.*result", re.IGNORECASE),
        re.compile(r"ensure\s.*consistency", re.IGNORECASE),
        re.compile(r"only\s+say\s+completed\s+if", re.IGNORECASE),
        re.compile(r"verify\s+the\s+action\s+succeeded", re.IGNORECASE),
        re.compile(r"do\s+not\s+claim\s+success\s+unless", re.IGNORECASE),
    ],
}


def _generate_obligation_id(source_path: str, obligation_type: str, match_start_offset: int) -> str:
    """Generate a stable obligation ID from source path, type, and match offset.

    Uses SHA-256 hash truncated to 12 hex characters for stable, reproducible IDs.
    """
    raw = f"{source_path}:{obligation_type}:{match_start_offset}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _extract_from_text(
    text: str,
    source_path: str,
) -> list[Obligation]:
    """Apply all patterns from the registry against the given text.

    Returns a list of Obligation objects for each match found.
    """
    obligations: list[Obligation] = []

    for obligation_type, patterns in _PATTERN_REGISTRY.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                obligation_id = _generate_obligation_id(
                    source_path, obligation_type.value, match.start()
                )
                # Extract a context snippet around the match
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 40)
                source_text = text[start:end].strip()

                obligations.append(
                    Obligation(
                        id=obligation_id,
                        obligation_type=obligation_type,
                        source_text=source_text,
                        source_path=source_path,
                    )
                )

    return obligations


def extract_obligations(
    prompts: list[PromptArtifact],
    tools: list[ToolArtifact],
) -> list[Obligation]:
    """Apply pattern registry to extract obligations from prompt text and tool metadata.

    Scans both prompt text content and tool descriptions/metadata for patterns
    matching the six obligation types. Each match produces an Obligation with a
    stable ID derived from the source path, obligation type, and match offset.

    Args:
        prompts: List of PromptArtifact objects with extracted prompt text.
        tools: List of ToolArtifact objects with tool definitions.

    Returns:
        List of Obligation objects extracted from all sources.
    """
    obligations: list[Obligation] = []

    # Extract from prompt text
    for prompt in prompts:
        try:
            found = _extract_from_text(prompt.text, prompt.source_path)
            obligations.extend(found)
        except Exception as e:
            logger.warning(
                "Error extracting obligations from prompt %s: %s",
                prompt.source_path,
                e,
            )
            continue

    # Extract from tool metadata (descriptions)
    for tool in tools:
        try:
            # Combine tool description and parameter descriptions for scanning
            text_parts = [tool.description]
            for param in tool.parameters:
                if param.description:
                    text_parts.append(param.description)
            combined_text = "\n".join(text_parts)

            if combined_text.strip():
                found = _extract_from_text(combined_text, tool.source_path)
                obligations.extend(found)
        except Exception as e:
            logger.warning(
                "Error extracting obligations from tool %s: %s",
                tool.name,
                e,
            )
            continue

    return obligations
