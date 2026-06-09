"""Mismatch detector module - runs checks A-G against the contract."""

from __future__ import annotations

import logging
from typing import Any

from agentbattery.models import (
    AgentContract,
    ClassifiedFile,
    Evidence,
    Finding,
    GapType,
    Obligation,
    ObligationType,
    RiskLevel,
    SideEffectLevel,
    ToolArtifact,
)

logger = logging.getLogger(__name__)

# Keywords indicating financial tools
_FINANCIAL_KEYWORDS: set[str] = {
    "refund",
    "charge",
    "payment",
    "transfer",
    "purchase",
}

# Keywords indicating retrieval tools
_RETRIEVAL_KEYWORDS: set[str] = {
    "search",
    "retrieve",
    "fetch",
    "vector",
    "rag",
    "knowledge",
}

# Keywords indicating confirmation enforcement in preconditions
_CONFIRMATION_KEYWORDS: set[str] = {
    "confirm",
    "approval",
    "permission",
    "authorized",
}

# Keywords indicating policy check enforcement in preconditions
_POLICY_CHECK_KEYWORDS: set[str] = {
    "policy",
    "eligibility",
    "policy_check",
}


def _is_dangerous(tool: ToolArtifact) -> bool:
    """Check if a tool is dangerous (DESTRUCTIVE or EXTERNAL_WRITE)."""
    return tool.side_effect_level in (
        SideEffectLevel.DESTRUCTIVE,
        SideEffectLevel.EXTERNAL_WRITE,
    )


def _is_financial(tool: ToolArtifact) -> bool:
    """Check if a tool is financial based on name keywords."""
    name_lower = tool.name.lower()
    return any(kw in name_lower for kw in _FINANCIAL_KEYWORDS)


def _is_retrieval(tool: ToolArtifact) -> bool:
    """Check if a tool is a retrieval tool based on name keywords."""
    name_lower = tool.name.lower()
    return any(kw in name_lower for kw in _RETRIEVAL_KEYWORDS)


def _has_precondition_keywords(tool: ToolArtifact, keywords: set[str]) -> bool:
    """Check if any precondition on a tool contains one of the given keywords."""
    for precondition in tool.preconditions:
        precondition_lower = precondition.lower()
        if any(kw in precondition_lower for kw in keywords):
            return True
    return False


def _obligations_linked_to_tool(
    obligations: list[Obligation], tool_name: str
) -> list[Obligation]:
    """Get all obligations linked to a specific tool."""
    return [ob for ob in obligations if tool_name in ob.linked_tool_names]


def _obligations_of_type(
    obligations: list[Obligation], ob_type: ObligationType
) -> list[Obligation]:
    """Get all obligations of a specific type."""
    return [ob for ob in obligations if ob.obligation_type == ob_type]


def _check_a_policy_gap_no_obligations(
    contract: AgentContract,
) -> list[Finding]:
    """Check A: Dangerous tool with ZERO linked obligations → POLICY_GAP."""
    findings: list[Finding] = []

    for tool in contract.tools:
        if not _is_dangerous(tool):
            continue

        linked = _obligations_linked_to_tool(contract.obligations, tool.name)
        if len(linked) == 0:
            severity = (
                RiskLevel.CRITICAL
                if tool.side_effect_level == SideEffectLevel.DESTRUCTIVE
                else RiskLevel.HIGH
            )
            findings.append(
                Finding(
                    finding_type="POLICY_GAP",
                    severity=severity,
                    gap_type=GapType.POLICY_GAP,
                    title=f"No obligation detected for dangerous tool '{tool.name}'",
                    description=(
                        f"Tool '{tool.name}' is classified as {tool.side_effect_level.value} "
                        f"but no linked obligation was detected. This tool may operate "
                        f"without any safety constraint."
                    ),
                    evidence=[
                        Evidence(
                            source=tool.source_path,
                            location=tool.name,
                            detail=(
                                f"No obligation detected linking to tool '{tool.name}' "
                                f"(side_effect_level={tool.side_effect_level.value})."
                            ),
                        )
                    ],
                    remediation=(
                        f"Add an obligation (e.g., confirmation or policy check) "
                        f"for tool '{tool.name}' in the system prompt or tool configuration."
                    ),
                    transparency=(
                        f"Raised because tool '{tool.name}' has side_effect_level "
                        f"{tool.side_effect_level.value} and zero obligations were "
                        f"linked to it during contract compilation."
                    ),
                )
            )

    return findings


def _check_b_enforcement_gap_confirmation(
    contract: AgentContract,
) -> list[Finding]:
    """Check B: CONFIRMATION_REQUIRED obligation linked to tool but no precondition → ENFORCEMENT_GAP."""
    findings: list[Finding] = []

    confirmation_obligations = _obligations_of_type(
        contract.obligations, ObligationType.CONFIRMATION_REQUIRED
    )

    for ob in confirmation_obligations:
        for tool_name in ob.linked_tool_names:
            # Find the tool artifact
            tool = next((t for t in contract.tools if t.name == tool_name), None)
            if tool is None:
                continue

            if not _has_precondition_keywords(tool, _CONFIRMATION_KEYWORDS):
                findings.append(
                    Finding(
                        finding_type="ENFORCEMENT_GAP",
                        severity=RiskLevel.HIGH,
                        gap_type=GapType.ENFORCEMENT_GAP,
                        title=(
                            f"No confirmation precondition detected for tool '{tool_name}'"
                        ),
                        description=(
                            f"Obligation '{ob.id}' requires confirmation before "
                            f"tool '{tool_name}', but no confirmation precondition "
                            f"was detected in the tool source."
                        ),
                        evidence=[
                            Evidence(
                                source=ob.source_path,
                                location=ob.id,
                                detail=(
                                    f"Obligation source: \"{ob.source_text[:80]}\""
                                ),
                            ),
                            Evidence(
                                source=tool.source_path,
                                location=tool.name,
                                detail=(
                                    "No confirmation precondition detected in tool source."
                                ),
                            ),
                        ],
                        remediation=(
                            f"Add a precondition to tool '{tool_name}' that enforces "
                            f"user confirmation before execution."
                        ),
                        transparency=(
                            f"Raised because obligation '{ob.id}' (CONFIRMATION_REQUIRED) "
                            f"is linked to tool '{tool_name}', but no precondition "
                            f"containing 'confirm', 'approval', 'permission', or "
                            f"'authorized' was detected in the tool's preconditions."
                        ),
                    )
                )

    return findings


def _check_c_enforcement_gap_financial(
    contract: AgentContract,
) -> list[Finding]:
    """Check C: Financial tool missing policy_check precondition → ENFORCEMENT_GAP."""
    findings: list[Finding] = []

    for tool in contract.tools:
        if not _is_financial(tool):
            continue

        if not _has_precondition_keywords(tool, _POLICY_CHECK_KEYWORDS):
            findings.append(
                Finding(
                    finding_type="ENFORCEMENT_GAP",
                    severity=RiskLevel.HIGH,
                    gap_type=GapType.ENFORCEMENT_GAP,
                    title=(
                        f"No policy/eligibility precondition detected for "
                        f"financial tool '{tool.name}'"
                    ),
                    description=(
                        f"Tool '{tool.name}' appears to be a financial operation "
                        f"but no policy or eligibility precondition was detected."
                    ),
                    evidence=[
                        Evidence(
                            source=tool.source_path,
                            location=tool.name,
                            detail="No policy/eligibility precondition detected.",
                        ),
                    ],
                    remediation=(
                        f"Add a policy_check precondition to tool '{tool.name}' "
                        f"that verifies eligibility before executing the financial operation."
                    ),
                    transparency=(
                        f"Raised because tool '{tool.name}' contains financial "
                        f"keywords (refund/charge/payment/transfer/purchase) but "
                        f"no precondition containing 'policy' or 'eligibility' "
                        f"was detected."
                    ),
                )
            )

    return findings


def _check_d_policy_gap_destructive_no_confirmation(
    contract: AgentContract,
) -> list[Finding]:
    """Check D: DESTRUCTIVE tool with no CONFIRMATION_REQUIRED obligation linked → POLICY_GAP."""
    findings: list[Finding] = []

    for tool in contract.tools:
        if tool.side_effect_level != SideEffectLevel.DESTRUCTIVE:
            continue

        linked = _obligations_linked_to_tool(contract.obligations, tool.name)
        has_confirmation = any(
            ob.obligation_type == ObligationType.CONFIRMATION_REQUIRED
            for ob in linked
        )

        if not has_confirmation:
            findings.append(
                Finding(
                    finding_type="POLICY_GAP",
                    severity=RiskLevel.CRITICAL,
                    gap_type=GapType.POLICY_GAP,
                    title=(
                        f"No confirmation obligation detected for destructive "
                        f"tool '{tool.name}'"
                    ),
                    description=(
                        f"Tool '{tool.name}' is classified as DESTRUCTIVE but no "
                        f"CONFIRMATION_REQUIRED obligation was detected linking to it."
                    ),
                    evidence=[
                        Evidence(
                            source=tool.source_path,
                            location=tool.name,
                            detail=(
                                f"Tool '{tool.name}' has side_effect_level=DESTRUCTIVE "
                                f"but no CONFIRMATION_REQUIRED obligation was detected."
                            ),
                        ),
                    ],
                    remediation=(
                        f"Add a confirmation requirement in the system prompt or "
                        f"tool configuration for tool '{tool.name}'."
                    ),
                    transparency=(
                        f"Raised because tool '{tool.name}' is DESTRUCTIVE and no "
                        f"obligation of type CONFIRMATION_REQUIRED was found linked to it."
                    ),
                )
            )

    return findings


def _check_e_policy_gap_retrieval_injection(
    contract: AgentContract,
) -> list[Finding]:
    """Check E: Retrieval + external write tools present but no RETRIEVAL_INJECTION_GUARD → POLICY_GAP."""
    findings: list[Finding] = []

    has_retrieval = any(_is_retrieval(t) for t in contract.tools)
    has_external_write = any(
        t.side_effect_level in (SideEffectLevel.EXTERNAL_WRITE, SideEffectLevel.DESTRUCTIVE)
        for t in contract.tools
    )

    if not (has_retrieval and has_external_write):
        return findings

    # Check if any RETRIEVAL_INJECTION_GUARD obligation exists
    has_guard = any(
        ob.obligation_type == ObligationType.RETRIEVAL_INJECTION_GUARD
        for ob in contract.obligations
    )

    if not has_guard:
        retrieval_tools = [t for t in contract.tools if _is_retrieval(t)]
        write_tools = [
            t for t in contract.tools
            if t.side_effect_level in (SideEffectLevel.EXTERNAL_WRITE, SideEffectLevel.DESTRUCTIVE)
        ]
        findings.append(
            Finding(
                finding_type="POLICY_GAP",
                severity=RiskLevel.HIGH,
                gap_type=GapType.POLICY_GAP,
                title="No retrieval injection guard detected",
                description=(
                    f"Retrieval tools ({', '.join(t.name for t in retrieval_tools)}) "
                    f"are present alongside external write tools "
                    f"({', '.join(t.name for t in write_tools)}), but no "
                    f"RETRIEVAL_INJECTION_GUARD obligation was detected."
                ),
                evidence=[
                    Evidence(
                        source="contract",
                        location="obligations",
                        detail=(
                            "No RETRIEVAL_INJECTION_GUARD obligation detected in "
                            "the contract despite retrieval and write tools being present."
                        ),
                    ),
                ],
                remediation=(
                    "Add a retrieval injection guard obligation in the system prompt "
                    "or policy to sanitize retrieval results before use in write operations."
                ),
                transparency=(
                    "Raised because retrieval tools and external write tools are both "
                    "present in the contract, but no RETRIEVAL_INJECTION_GUARD obligation "
                    "was found to protect against injection attacks via retrieved content."
                ),
            )
        )

    return findings


def _check_f_enforcement_gap_consistency(
    contract: AgentContract,
) -> list[Finding]:
    """Check F: FINAL_STATE_CONSISTENCY obligation present but no verification step linked → ENFORCEMENT_GAP."""
    findings: list[Finding] = []

    consistency_obligations = _obligations_of_type(
        contract.obligations, ObligationType.FINAL_STATE_CONSISTENCY
    )

    # Keywords that indicate a verification tool
    verification_keywords = {"verify", "check", "validate"}

    for ob in consistency_obligations:
        # Check if any linked tool has verification keywords in its name
        has_verification = False
        for tool_name in ob.linked_tool_names:
            tool_name_lower = tool_name.lower()
            if any(kw in tool_name_lower for kw in verification_keywords):
                has_verification = True
                break

        if not has_verification:
            findings.append(
                Finding(
                    finding_type="ENFORCEMENT_GAP",
                    severity=RiskLevel.HIGH,
                    gap_type=GapType.ENFORCEMENT_GAP,
                    title=(
                        f"No verification step detected for consistency obligation '{ob.id}'"
                    ),
                    description=(
                        f"Obligation '{ob.id}' requires final state consistency "
                        f"but no verification tool (containing 'verify', 'check', or "
                        f"'validate' in name) was detected among linked tools."
                    ),
                    evidence=[
                        Evidence(
                            source=ob.source_path,
                            location=ob.id,
                            detail=(
                                f"Obligation source: \"{ob.source_text[:80]}\""
                            ),
                        ),
                        Evidence(
                            source="contract",
                            location="linked_tools",
                            detail=(
                                f"No tool with 'verify', 'check', or 'validate' in name "
                                f"detected among linked tools: "
                                f"{ob.linked_tool_names or '(none)'}."
                            ),
                        ),
                    ],
                    remediation=(
                        "Add a verification step (e.g., a tool named 'verify_state' or "
                        "'check_result') and link it to the consistency obligation."
                    ),
                    transparency=(
                        f"Raised because obligation '{ob.id}' (FINAL_STATE_CONSISTENCY) "
                        f"has no linked tool with 'verify', 'check', or 'validate' in its name."
                    ),
                )
            )

    return findings


def _check_g_enforcement_gap_permissive_schema(
    contract: AgentContract,
) -> list[Finding]:
    """Check G: High-risk tool with ALL parameters optional → ENFORCEMENT_GAP."""
    findings: list[Finding] = []

    for tool in contract.tools:
        if not _is_dangerous(tool):
            continue

        # Skip tools with no parameters (not relevant to schema permissiveness)
        if not tool.parameters:
            continue

        # Check if ALL parameters are optional
        all_optional = all(not param.required for param in tool.parameters)

        if all_optional:
            findings.append(
                Finding(
                    finding_type="ENFORCEMENT_GAP",
                    severity=RiskLevel.HIGH,
                    gap_type=GapType.ENFORCEMENT_GAP,
                    title=(
                        f"Permissive schema: all parameters optional on "
                        f"high-risk tool '{tool.name}'"
                    ),
                    description=(
                        f"Tool '{tool.name}' is classified as "
                        f"{tool.side_effect_level.value} but all "
                        f"{len(tool.parameters)} parameters are optional. "
                        f"This permissive schema may allow unintended invocations."
                    ),
                    evidence=[
                        Evidence(
                            source=tool.source_path,
                            location=tool.name,
                            detail=(
                                "Permissive schema: all parameters optional on "
                                "high-risk tool."
                            ),
                        ),
                    ],
                    remediation=(
                        f"Mark at least one critical parameter as required on "
                        f"tool '{tool.name}' to prevent accidental invocations."
                    ),
                    transparency=(
                        f"Raised because tool '{tool.name}' has side_effect_level "
                        f"{tool.side_effect_level.value} and all "
                        f"{len(tool.parameters)} parameters are marked as optional "
                        f"(none are required)."
                    ),
                )
            )

    return findings


def _check_prompt_only_safety(
    contract: AgentContract,
) -> list[Finding]:
    """Detect prompt-only safety: obligation exists but no enforcement detected → ENFORCEMENT_GAP.

    This is essentially Check B generalized: when an obligation is linked to a tool
    but the tool has no precondition enforcing it, and Check B hasn't already caught it
    (i.e., non-CONFIRMATION_REQUIRED types).
    """
    findings: list[Finding] = []

    # Check B already covers CONFIRMATION_REQUIRED.
    # Check C covers financial tools.
    # Check F covers FINAL_STATE_CONSISTENCY.
    # This check covers remaining obligation types linked to tools without enforcement.
    already_covered_types = {
        ObligationType.CONFIRMATION_REQUIRED,
        ObligationType.FINAL_STATE_CONSISTENCY,
    }

    for ob in contract.obligations:
        if ob.obligation_type in already_covered_types:
            continue

        for tool_name in ob.linked_tool_names:
            tool = next((t for t in contract.tools if t.name == tool_name), None)
            if tool is None:
                continue

            # If the tool has no preconditions at all, that's a prompt-only safety gap
            if not tool.preconditions:
                findings.append(
                    Finding(
                        finding_type="ENFORCEMENT_GAP",
                        severity=RiskLevel.MEDIUM,
                        gap_type=GapType.ENFORCEMENT_GAP,
                        title=(
                            f"Prompt-only safety: obligation '{ob.id}' has no "
                            f"runtime enforcement on tool '{tool_name}'"
                        ),
                        description=(
                            f"Obligation '{ob.id}' ({ob.obligation_type.value}) is "
                            f"linked to tool '{tool_name}' but no precondition was "
                            f"detected in the tool source to enforce it at runtime."
                        ),
                        evidence=[
                            Evidence(
                                source=ob.source_path,
                                location=ob.id,
                                detail=(
                                    f"Obligation source: \"{ob.source_text[:80]}\""
                                ),
                            ),
                            Evidence(
                                source=tool.source_path,
                                location=tool.name,
                                detail=(
                                    "No precondition detected in tool source to "
                                    "enforce this obligation."
                                ),
                            ),
                        ],
                        remediation=(
                            f"Add a precondition or runtime check to tool '{tool_name}' "
                            f"that enforces obligation '{ob.id}'."
                        ),
                        transparency=(
                            f"Raised because obligation '{ob.id}' "
                            f"({ob.obligation_type.value}) is linked to tool "
                            f"'{tool_name}' via the contract, but the tool has no "
                            f"preconditions to enforce it at runtime (prompt-only safety)."
                        ),
                    )
                )

    return findings


def detect_mismatches(
    contract: AgentContract, classified_files: list[ClassifiedFile]
) -> list[Finding]:
    """Run checks A-G against the contract and produce findings.

    Args:
        contract: The compiled AgentContract with linked artifacts.
        classified_files: List of classified files from the scan.

    Returns:
        A list of Finding objects for all detected mismatches.
    """
    findings: list[Finding] = []

    # Check A: Dangerous tool with zero linked obligations
    findings.extend(_check_a_policy_gap_no_obligations(contract))

    # Check B: CONFIRMATION_REQUIRED obligation without precondition
    findings.extend(_check_b_enforcement_gap_confirmation(contract))

    # Check C: Financial tool missing policy check precondition
    findings.extend(_check_c_enforcement_gap_financial(contract))

    # Check D: DESTRUCTIVE tool with no CONFIRMATION_REQUIRED obligation
    findings.extend(_check_d_policy_gap_destructive_no_confirmation(contract))

    # Check E: Retrieval + write tools without injection guard
    findings.extend(_check_e_policy_gap_retrieval_injection(contract))

    # Check F: Consistency obligation without verification step
    findings.extend(_check_f_enforcement_gap_consistency(contract))

    # Check G: All-optional params on high-risk tool
    findings.extend(_check_g_enforcement_gap_permissive_schema(contract))

    # Prompt-only safety detection
    findings.extend(_check_prompt_only_safety(contract))

    return findings
