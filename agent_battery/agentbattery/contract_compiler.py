"""Contract compiler module - links artifacts into AgentContract."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from agentbattery.models import (
    AgentContract,
    ForbiddenTransition,
    Obligation,
    ObligationType,
    PromptArtifact,
    SideEffectLevel,
    ToolArtifact,
)

logger = logging.getLogger(__name__)

# Common English stopwords to remove during tokenization
_STOPWORDS: set[str] = {
    "the", "a", "an", "is", "are", "to", "for", "and", "of", "in",
    "on", "it", "that", "this", "with", "be", "as", "at", "or", "by",
    "from", "not",
}

# Ordering language patterns that indicate forbidden transitions
_ORDERING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bbefore\b", re.IGNORECASE),
    re.compile(r"\bafter\b", re.IGNORECASE),
    re.compile(r"\bmust precede\b", re.IGNORECASE),
    re.compile(r"\bprior to\b", re.IGNORECASE),
    re.compile(r"\bthen\b", re.IGNORECASE),
]


def _tokenize(text: str) -> set[str]:
    """Tokenize text: lowercase, split on whitespace/punctuation, remove stopwords.

    Args:
        text: The text to tokenize.

    Returns:
        A set of meaningful tokens (stopwords removed).
    """
    # Lowercase and split on non-alphanumeric characters
    lower = text.lower()
    tokens = re.split(r"[^a-z0-9]+", lower)
    # Remove empty strings and stopwords
    return {t for t in tokens if t and t not in _STOPWORDS}


def _has_ordering_language(text: str) -> bool:
    """Check if text contains ordering language patterns."""
    return any(p.search(text) for p in _ORDERING_PATTERNS)


def _build_forbidden_transitions(
    obligations: list[Obligation],
) -> list[ForbiddenTransition]:
    """Build ForbiddenTransition entries from obligations.

    Creates transitions based on:
    - Obligations with ordering language in source_text
    - CONFIRMATION_REQUIRED obligations linked to tools
    - POLICY_CHECK_REQUIRED obligations linked to tools
    - LOOKUP_REQUIRED obligations linked to tools
    """
    transitions: list[ForbiddenTransition] = []

    for ob in obligations:
        # Type-based transitions
        if ob.obligation_type == ObligationType.CONFIRMATION_REQUIRED:
            for tool_name in ob.linked_tool_names:
                transitions.append(
                    ForbiddenTransition(
                        predecessor="user_confirmation",
                        successor=tool_name,
                        obligation_id=ob.id,
                        description=(
                            f"User confirmation must precede {tool_name} "
                            f"(obligation: {ob.source_text[:60]})"
                        ),
                    )
                )
        elif ob.obligation_type == ObligationType.POLICY_CHECK_REQUIRED:
            for tool_name in ob.linked_tool_names:
                transitions.append(
                    ForbiddenTransition(
                        predecessor="policy_check",
                        successor=tool_name,
                        obligation_id=ob.id,
                        description=(
                            f"Policy check must precede {tool_name} "
                            f"(obligation: {ob.source_text[:60]})"
                        ),
                    )
                )
        elif ob.obligation_type == ObligationType.LOOKUP_REQUIRED:
            for tool_name in ob.linked_tool_names:
                transitions.append(
                    ForbiddenTransition(
                        predecessor="lookup",
                        successor=tool_name,
                        obligation_id=ob.id,
                        description=(
                            f"Lookup must precede {tool_name} "
                            f"(obligation: {ob.source_text[:60]})"
                        ),
                    )
                )

        # Additionally, check for ordering language in other obligation types
        # that haven't already been handled above
        if (
            ob.obligation_type
            not in (
                ObligationType.CONFIRMATION_REQUIRED,
                ObligationType.POLICY_CHECK_REQUIRED,
                ObligationType.LOOKUP_REQUIRED,
            )
            and _has_ordering_language(ob.source_text)
            and ob.linked_tool_names
        ):
            # For generic ordering obligations, use first linked tool as successor
            for tool_name in ob.linked_tool_names:
                transitions.append(
                    ForbiddenTransition(
                        predecessor="ordering_check",
                        successor=tool_name,
                        obligation_id=ob.id,
                        description=(
                            f"Ordering constraint on {tool_name} "
                            f"(obligation: {ob.source_text[:60]})"
                        ),
                    )
                )

    return transitions


def compile_contract(
    prompts: list[PromptArtifact],
    tools: list[ToolArtifact],
    obligations: list[Obligation],
    risk_levels: dict[str, SideEffectLevel],
) -> AgentContract:
    """Link obligations to tools and assemble the contract.

    Linking algorithm:
    1. For each obligation, tokenize the source_text (lowercase, split on
       whitespace/punctuation).
    2. For each tool, tokenize name + description.
    3. Remove stopwords (common English words).
    4. Compute token overlap. Link obligation to tool if score >= 1 shared
       meaningful token after stopword removal.
    5. Set linked_tool_names on each obligation.

    Then builds ForbiddenTransition entries from obligations containing ordering
    language or from specific obligation types (CONFIRMATION_REQUIRED,
    POLICY_CHECK_REQUIRED, LOOKUP_REQUIRED).

    Args:
        prompts: List of extracted prompt artifacts.
        tools: List of extracted tool artifacts.
        obligations: List of extracted obligations.
        risk_levels: Dict mapping tool name to its SideEffectLevel.

    Returns:
        An assembled AgentContract with all linked artifacts.
    """
    # Pre-tokenize all tools
    tool_tokens: dict[str, set[str]] = {}
    for tool in tools:
        combined = f"{tool.name} {tool.description}"
        tool_tokens[tool.name] = _tokenize(combined)

    # Link obligations to tools via token overlap
    for obligation in obligations:
        ob_tokens = _tokenize(obligation.source_text)
        linked: list[str] = []

        for tool in tools:
            t_tokens = tool_tokens[tool.name]
            # Compute overlap: number of shared meaningful tokens
            overlap = ob_tokens & t_tokens
            if len(overlap) >= 1:
                linked.append(tool.name)

        obligation.linked_tool_names = linked

    # Build forbidden transitions
    forbidden_transitions = _build_forbidden_transitions(obligations)

    # Assemble contract
    return AgentContract(
        prompts=prompts,
        tools=tools,
        obligations=obligations,
        forbidden_transitions=forbidden_transitions,
        risk_map=risk_levels,
    )


def serialize_contract(contract: AgentContract, output_dir: Path) -> None:
    """Serialize the contract to YAML files in the output directory.

    Creates:
    - output_dir/contract.yaml: Full contract serialization.
    - output_dir/obligations.yaml: Just the obligations list.

    Args:
        contract: The AgentContract to serialize.
        output_dir: Directory to write YAML files into (created if needed).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Serialize full contract (mode="json" converts enums to plain strings)
    contract_data = contract.model_dump(mode="json")
    contract_path = output_dir / "contract.yaml"
    with open(contract_path, "w") as f:
        yaml.dump(contract_data, f, default_flow_style=False, sort_keys=False)

    # Serialize obligations only
    obligations_data = [ob.model_dump(mode="json") for ob in contract.obligations]
    obligations_path = output_dir / "obligations.yaml"
    with open(obligations_path, "w") as f:
        yaml.dump(obligations_data, f, default_flow_style=False, sort_keys=False)



