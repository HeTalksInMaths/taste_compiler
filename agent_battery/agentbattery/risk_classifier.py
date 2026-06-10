"""Risk classifier module - assigns side-effect levels to tools."""

from __future__ import annotations

import logging

from agentbattery.models import RiskLevel, SideEffectLevel, ToolArtifact

logger = logging.getLogger(__name__)

# Keyword sets for risk classification, checked against lowercased tool name + description.
# Priority: DESTRUCTIVE > EXTERNAL_WRITE > WEAK > NONE (highest matching wins).

_DESTRUCTIVE_KEYWORDS: set[str] = {
    "delete",
    "remove",
    "drop",
    "terminate",
    "revoke",
    "destroy",
    "purge",
    "wipe",
    "shutdown",
    "execute_shell",
    "run_command",
    "exec",
    "eval",
}

_EXTERNAL_WRITE_KEYWORDS: set[str] = {
    "send",
    "post",
    "update",
    "write",
    "create",
    "transfer",
    "publish",
    "submit",
    "execute",
    "deploy",
    "forward",
    "invite",
    "tweet",
    "slack",
    "book",
    "purchase",
    "refund",
    "charge",
    "schedule",
}

_WEAK_KEYWORDS: set[str] = {
    "log",
    "notify",
    "cache",
    "tag",
    "mark",
    "annotate",
    "create_draft",
    "save",
    "label",
    "archive",
    "mark_read",
    "update_local",
}

_NONE_KEYWORDS: set[str] = {
    "search",
    "read",
    "fetch",
    "get",
    "list",
    "lookup",
    "retrieve",
    "query",
}

# Financial keywords that elevate EXTERNAL_WRITE to CRITICAL risk level
_FINANCIAL_KEYWORDS: set[str] = {
    "refund",
    "charge",
    "payment",
    "transfer",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words and underscore-separated parts."""
    # Split on whitespace, punctuation, underscores, and camelCase boundaries
    lower = text.lower()
    # Split on non-alphanumeric characters
    tokens = []
    for word in lower.replace("_", " ").replace("-", " ").split():
        tokens.append(word)
    return tokens


def _matches_keywords(tokens: list[str], full_text: str, keywords: set[str]) -> bool:
    """Check if any keyword matches in the tokens or as a substring of the full text."""
    # Check token-level matches
    for token in tokens:
        if token in keywords:
            return True
    # Check substring matches (for multi-word tool names like "execute_shell")
    for keyword in keywords:
        if keyword in full_text:
            return True
    return False


def classify_risk(tool: ToolArtifact) -> SideEffectLevel:
    """Assign side-effect level based on keyword matching against name and description.

    Checks lowercased tool name + description against keyword sets.
    Priority: DESTRUCTIVE > EXTERNAL_WRITE > WEAK > NONE (highest matching wins).

    For compound tool names (e.g., "create_draft"), exact match against WEAK keywords
    is checked first to avoid false positives from partial token matches.

    Args:
        tool: A ToolArtifact with name and description.

    Returns:
        The highest-priority SideEffectLevel that matches.
    """
    # Combine name and description for matching
    combined = f"{tool.name} {tool.description}".lower()
    tokens = _tokenize(f"{tool.name} {tool.description}")
    tool_name_lower = tool.name.lower()

    # Check if the tool name itself exactly matches a WEAK keyword
    # This handles cases like "create_draft" which should be WEAK
    # even though "create" alone would match EXTERNAL_WRITE
    if tool_name_lower in _WEAK_KEYWORDS:
        return SideEffectLevel.WEAK

    # Apply in priority order - first match wins
    if _matches_keywords(tokens, combined, _DESTRUCTIVE_KEYWORDS):
        return SideEffectLevel.DESTRUCTIVE

    if _matches_keywords(tokens, combined, _EXTERNAL_WRITE_KEYWORDS):
        return SideEffectLevel.EXTERNAL_WRITE

    if _matches_keywords(tokens, combined, _WEAK_KEYWORDS):
        return SideEffectLevel.WEAK

    return SideEffectLevel.NONE


def classify_risk_level(tool: ToolArtifact) -> RiskLevel:
    """Assign a RiskLevel based on the tool's side-effect classification.

    Mapping:
    - DESTRUCTIVE → CRITICAL
    - EXTERNAL_WRITE with financial terms → CRITICAL
    - EXTERNAL_WRITE without financial terms → HIGH
    - WEAK → MEDIUM
    - NONE → LOW

    Args:
        tool: A ToolArtifact with name and description.

    Returns:
        The RiskLevel for the tool.
    """
    side_effect = classify_risk(tool)

    if side_effect == SideEffectLevel.DESTRUCTIVE:
        return RiskLevel.CRITICAL

    if side_effect == SideEffectLevel.EXTERNAL_WRITE:
        # Check for financial keywords to elevate to CRITICAL
        combined = f"{tool.name} {tool.description}".lower()
        tokens = _tokenize(f"{tool.name} {tool.description}")
        if _matches_keywords(tokens, combined, _FINANCIAL_KEYWORDS):
            return RiskLevel.CRITICAL
        return RiskLevel.HIGH

    if side_effect == SideEffectLevel.WEAK:
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def classify_tools(tools: list[ToolArtifact]) -> list[ToolArtifact]:
    """Classify all tools and update their side_effect_level in-place.

    Args:
        tools: List of ToolArtifact objects to classify.

    Returns:
        The same list with side_effect_level updated on each tool.
    """
    for tool in tools:
        tool.side_effect_level = classify_risk(tool)

    return tools
