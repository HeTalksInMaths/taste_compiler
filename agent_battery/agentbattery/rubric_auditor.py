"""Rubric auditor module - audits repo against six architecture dimensions."""

from __future__ import annotations

import logging
import re
from typing import Any

from agentbattery.models import (
    AgentContract,
    AgentProfile,
    ClassifiedFile,
    DecisionPolicy,
    Evidence,
    FailurePolicy,
    FileCategory,
    Finding,
    GapType,
    HumanInLoopPolicy,
    ObligationType,
    OrchestrationPolicy,
    PromptArtifact,
    RiskLevel,
    SideEffectLevel,
)

logger = logging.getLogger(__name__)

# --- Keyword sets for detection heuristics ---

# Agent identity phrases (case-insensitive)
_AGENT_IDENTITY_PATTERNS: list[str] = [
    r"you are\b",
    r"your role is\b",
    r"your purpose is\b",
    r"you help\b",
]

_AGENT_IDENTITY_CONFIG_KEYS: set[str] = {
    "agent_name",
    "agent_description",
}

# Autonomy & Decision-Making
_DECISION_KEYWORDS: set[str] = {
    "break down",
    "step by step",
    "plan",
    "decide",
}

_STOP_CONDITION_KEYWORDS: set[str] = {
    "max_iterations",
    "max_steps",
    "done",
    "complete",
    "finished",
    "stop_condition",
    "termination",
}

_TOOL_SELECTION_KEYWORDS: set[str] = {
    "choose",
    "select",
    "pick",
    "route",
    "dispatch",
}

# Orchestration (multi-agent indicators)
_MULTI_AGENT_INDICATORS: set[str] = {
    "agents=",
    "crew",
    "swarm",
    "supervisor",
    "worker",
    "delegate",
}

_DELEGATION_KEYWORDS: set[str] = {
    "delegate",
    "handoff",
    "transfer",
    "assign_to",
    "forward_to",
}

_SHARED_STATE_KEYWORDS: set[str] = {
    "shared_memory",
    "blackboard",
    "message_queue",
}

# Human-in-the-Loop
_HITL_KEYWORDS: set[str] = {
    "confirm",
    "approve",
    "permission",
    "human_review",
    "ask_user",
    "override",
    "escalate",
}

_OVERRIDE_KEYWORDS: set[str] = {
    "override",
    "intervention",
    "manual",
    "escalate",
    "human_fallback",
}

# Failure Handling
_RETRY_KEYWORDS: set[str] = {
    "retry",
    "backoff",
    "max_retries",
}

_TIMEOUT_KEYWORDS: set[str] = {
    "timeout",
    "deadline",
}

_FALLBACK_KEYWORDS: set[str] = {
    "fallback",
    "default",
    "graceful",
}

_PARTIAL_COMPLETION_KEYWORDS: set[str] = {
    "checkpoint",
    "resume",
    "recover",
    "rollback",
}

_RECOVERY_KEYWORDS: set[str] = {
    "recover",
    "rollback",
    "restore",
    "compensate",
    "cleanup",
}


def _collect_all_text(
    prompts: list[PromptArtifact],
    classified_files: list[ClassifiedFile],
) -> str:
    """Collect all searchable text from prompts and classified file paths."""
    parts: list[str] = []
    for p in prompts:
        parts.append(p.text)
    # Also include file paths for config/doc detection
    for f in classified_files:
        parts.append(f.relative_path)
    return "\n".join(parts)


def _text_contains_any(text: str, keywords: set[str]) -> list[str]:
    """Check if text contains any keyword (case-insensitive). Returns matched keywords."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw in text_lower]


def _text_matches_patterns(text: str, patterns: list[str]) -> list[str]:
    """Check if text matches any regex pattern (case-insensitive). Returns matched patterns."""
    matched = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(pattern)
    return matched


def _has_dangerous_tools(contract: AgentContract) -> bool:
    """Check if contract has dangerous tools (DESTRUCTIVE or EXTERNAL_WRITE)."""
    return any(
        t.side_effect_level in (SideEffectLevel.DESTRUCTIVE, SideEffectLevel.EXTERNAL_WRITE)
        for t in contract.tools
    )


def _has_confirmation_obligation(contract: AgentContract) -> bool:
    """Check if contract has any CONFIRMATION_REQUIRED obligation."""
    return any(
        ob.obligation_type == ObligationType.CONFIRMATION_REQUIRED
        for ob in contract.obligations
    )


def _has_multiple_prompt_roles(prompts: list[PromptArtifact]) -> bool:
    """Detect if there are multiple prompts with different agent roles."""
    if len(prompts) < 2:
        return False
    # Simple heuristic: check if multiple prompts have "You are" with different identities
    roles: set[str] = set()
    for p in prompts:
        matches = re.findall(r"you are (?:a |an )?(\w+)", p.text, re.IGNORECASE)
        for m in matches:
            roles.add(m.lower())
    return len(roles) > 1


# --- Dimension 1: Agent Overview ---


def _detect_agent_overview(
    prompts: list[PromptArtifact],
    classified_files: list[ClassifiedFile],
) -> tuple[list[AgentProfile], list[Finding]]:
    """Detect agent identity and populate AgentProfile or emit gap finding."""
    findings: list[Finding] = []
    profiles: list[AgentProfile] = []

    all_text = _collect_all_text(prompts, classified_files)

    # Search for identity patterns in prompt text
    for prompt in prompts:
        matched = _text_matches_patterns(prompt.text, _AGENT_IDENTITY_PATTERNS)
        if matched:
            # Extract a name/purpose from the match context
            name = "agent"
            purpose = ""
            # Try to extract "You are a/an <X>" pattern
            identity_match = re.search(
                r"you are (?:a |an )?(.+?)[\.\n]", prompt.text, re.IGNORECASE
            )
            if identity_match:
                purpose = identity_match.group(1).strip()
                # Use first few words as name if short enough
                words = purpose.split()
                if len(words) <= 5:
                    name = purpose
                else:
                    name = " ".join(words[:3])

            # Extract capabilities (look for list items or "can" statements)
            capabilities: list[str] = []
            cap_matches = re.findall(
                r"(?:you can|capable of|ability to)\s+(.+?)[\.\n]",
                prompt.text,
                re.IGNORECASE,
            )
            capabilities.extend(cap_matches[:5])  # Limit to 5

            profiles.append(
                AgentProfile(
                    name=name,
                    purpose=purpose,
                    capabilities=capabilities,
                    source_evidence=[f"Detected in {prompt.source_path}: matched identity pattern"],
                )
            )

    # Also check config files for agent_name / agent_description
    for f in classified_files:
        path_lower = f.relative_path.lower()
        if any(key in path_lower for key in _AGENT_IDENTITY_CONFIG_KEYS):
            if not profiles:
                profiles.append(
                    AgentProfile(
                        name="agent",
                        purpose="Detected from config file path",
                        capabilities=[],
                        source_evidence=[f"Config key detected in path: {f.relative_path}"],
                    )
                )

    if not profiles:
        findings.append(
            Finding(
                finding_type="AGENT_OVERVIEW_GAP",
                severity=RiskLevel.MEDIUM,
                gap_type=GapType.POLICY_GAP,
                title="No agent identity detected",
                description=(
                    "No evidence of agent identity, purpose, or capability description "
                    "was detected in prompts, documentation, or configuration files."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail="No identity phrases ('You are', 'Your role is', 'Your purpose is', 'You help') detected in any prompt.",
                    )
                ],
                remediation=(
                    "Add an agent identity section to your system prompt or README "
                    "describing the agent's name, purpose, and capabilities."
                ),
                transparency=(
                    "Raised because no prompt or config file contained identity "
                    "phrases matching the agent overview detection heuristics."
                ),
            )
        )

    return profiles, findings


# --- Dimension 2: Autonomy & Decision-Making ---


def _detect_decision_policy(
    prompts: list[PromptArtifact],
    classified_files: list[ClassifiedFile],
    contract: AgentContract,
) -> tuple[DecisionPolicy | None, list[Finding]]:
    """Detect decision-making patterns and stop conditions."""
    findings: list[Finding] = []
    all_text = _collect_all_text(prompts, classified_files)

    decision_matches = _text_contains_any(all_text, _DECISION_KEYWORDS)
    stop_matches = _text_contains_any(all_text, _STOP_CONDITION_KEYWORDS)
    tool_selection_matches = _text_contains_any(all_text, _TOOL_SELECTION_KEYWORDS)

    policy: DecisionPolicy | None = None

    if decision_matches or stop_matches:
        strategy = "detected"
        if any(kw in decision_matches for kw in ("plan", "break down", "step by step")):
            strategy = "goal-decomposition"
        elif "decide" in decision_matches:
            strategy = "reactive"

        policy = DecisionPolicy(
            strategy=strategy,
            stop_conditions=stop_matches,
            tool_selection_logic=(
                f"Detected keywords: {', '.join(tool_selection_matches)}"
                if tool_selection_matches
                else None
            ),
            source_evidence=[
                f"Decision keywords: {', '.join(decision_matches)}" if decision_matches else "",
                f"Stop condition keywords: {', '.join(stop_matches)}" if stop_matches else "",
            ],
        )

    if not decision_matches and not stop_matches:
        findings.append(
            Finding(
                finding_type="DECISION_POLICY_GAP",
                severity=RiskLevel.MEDIUM,
                gap_type=GapType.POLICY_GAP,
                title="No decision-making policy detected",
                description=(
                    "No evidence of goal decomposition, planning, or next-action "
                    "selection logic detected in prompts or code."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            "No decision keywords ('break down', 'step by step', "
                            "'plan', 'decide') detected."
                        ),
                    )
                ],
                remediation=(
                    "Document how the agent decides what to do next "
                    "(e.g., goal decomposition, reactive, plan-then-execute)."
                ),
                transparency=(
                    "Raised because no decision-making keywords were found "
                    "in prompts or file paths."
                ),
            )
        )
    else:
        # Decision logic found — check for stop conditions
        if not stop_matches:
            findings.append(
                Finding(
                    finding_type="STOP_CONDITION_GAP",
                    severity=RiskLevel.MEDIUM,
                    gap_type=GapType.POLICY_GAP,
                    title="No stop condition detected",
                    description=(
                        "Decision-making logic detected but no explicit stop or "
                        "termination condition was found."
                    ),
                    evidence=[
                        Evidence(
                            source="prompts",
                            location="",
                            detail=(
                                "No stop condition keywords ('max_iterations', "
                                "'max_steps', 'done', 'complete', 'finished', "
                                "'stop_condition', 'termination') detected."
                            ),
                        )
                    ],
                    remediation=(
                        "Add explicit stop conditions (e.g., max_iterations, "
                        "termination criteria) to prevent unbounded execution."
                    ),
                    transparency=(
                        "Raised because decision-making language was detected but "
                        "no stop condition keywords were found."
                    ),
                )
            )

    # Check for tool selection policy gap
    if contract.tools and not tool_selection_matches:
        findings.append(
            Finding(
                finding_type="TOOL_SELECTION_POLICY_GAP",
                severity=RiskLevel.LOW,
                gap_type=GapType.POLICY_GAP,
                title="No tool selection policy detected",
                description=(
                    "Tools are defined but no evidence of tool selection logic, "
                    "routing, or prioritization was detected."
                ),
                evidence=[
                    Evidence(
                        source="contract",
                        location="tools",
                        detail=(
                            f"{len(contract.tools)} tools defined but no tool "
                            f"selection keywords ('choose', 'select', 'pick', "
                            f"'route', 'dispatch') detected."
                        ),
                    )
                ],
                remediation=(
                    "Document how the agent selects which tool to use "
                    "(e.g., routing logic, priority rules, or selection criteria)."
                ),
                transparency=(
                    "Raised because tools exist in the contract but no tool "
                    "selection keywords were found in prompts or code."
                ),
            )
        )

    return policy, findings


# --- Dimension 3: Orchestration ---


def _detect_orchestration(
    prompts: list[PromptArtifact],
    classified_files: list[ClassifiedFile],
) -> tuple[OrchestrationPolicy | None, list[Finding]]:
    """Detect multi-agent orchestration patterns."""
    findings: list[Finding] = []
    all_text = _collect_all_text(prompts, classified_files)

    # Detect multi-agent indicators
    multi_agent_matches = _text_contains_any(all_text, _MULTI_AGENT_INDICATORS)
    has_multiple_roles = _has_multiple_prompt_roles(prompts)

    is_multi_agent = bool(multi_agent_matches) or has_multiple_roles

    if not is_multi_agent:
        # Single-agent system, no orchestration findings needed
        return None, findings

    # Multi-agent detected — check for coordination
    delegation_matches = _text_contains_any(all_text, _DELEGATION_KEYWORDS)
    shared_state_matches = _text_contains_any(all_text, _SHARED_STATE_KEYWORDS)

    policy = OrchestrationPolicy(
        source_evidence=[
            f"Multi-agent indicators: {', '.join(multi_agent_matches)}" if multi_agent_matches else "Multiple prompt roles detected",
        ],
        delegation_bounds=(
            f"Delegation keywords detected: {', '.join(delegation_matches)}"
            if delegation_matches
            else None
        ),
        shared_state_mechanism=(
            f"Shared state keywords detected: {', '.join(shared_state_matches)}"
            if shared_state_matches
            else None
        ),
    )

    # Check for missing coordination
    if not delegation_matches and not shared_state_matches:
        findings.append(
            Finding(
                finding_type="ORCHESTRATION_UNSPECIFIED",
                severity=RiskLevel.MEDIUM,
                gap_type=GapType.POLICY_GAP,
                title="No orchestration coordination detected",
                description=(
                    "Multi-agent indicators detected but no coordination policy "
                    "(delegation, shared state) was found."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            f"Multi-agent indicators found: "
                            f"{', '.join(multi_agent_matches) if multi_agent_matches else 'multiple prompt roles'}, "
                            f"but no coordination keywords detected."
                        ),
                    )
                ],
                remediation=(
                    "Document how agents coordinate: delegation bounds, "
                    "shared state mechanism, and communication patterns."
                ),
                transparency=(
                    "Raised because multi-agent indicators were detected but "
                    "no coordination or delegation keywords were found."
                ),
            )
        )

    # Check for unbounded delegation
    if delegation_matches:
        # Simple heuristic: delegation without bounds keywords
        bounds_keywords = {"limit", "bound", "max", "scope", "depth"}
        has_bounds = _text_contains_any(all_text, bounds_keywords)
        if not has_bounds:
            findings.append(
                Finding(
                    finding_type="UNBOUNDED_DELEGATION",
                    severity=RiskLevel.HIGH,
                    gap_type=GapType.POLICY_GAP,
                    title="No delegation bounds detected",
                    description=(
                        "Agent delegation detected but no scope limits, depth bounds, "
                        "or termination guarantees were found."
                    ),
                    evidence=[
                        Evidence(
                            source="prompts",
                            location="",
                            detail=(
                                f"Delegation keywords ({', '.join(delegation_matches)}) "
                                f"detected without bound/limit keywords."
                            ),
                        )
                    ],
                    remediation=(
                        "Add delegation bounds: scope limits, max delegation depth, "
                        "or termination guarantees for delegated tasks."
                    ),
                    transparency=(
                        "Raised because delegation keywords were found but no "
                        "bound/limit/scope/depth keywords were detected nearby."
                    ),
                )
            )

    # Check for shared state documentation
    if not shared_state_matches:
        findings.append(
            Finding(
                finding_type="SHARED_STATE_UNSPECIFIED",
                severity=RiskLevel.MEDIUM,
                gap_type=GapType.POLICY_GAP,
                title="No shared state mechanism detected",
                description=(
                    "Multi-agent system detected but no shared state management "
                    "(memory, context passing) was documented."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            "No shared state keywords ('shared_memory', "
                            "'blackboard', 'message_queue') detected."
                        ),
                    )
                ],
                remediation=(
                    "Document how agents share state: shared memory, "
                    "message queues, or context passing mechanisms."
                ),
                transparency=(
                    "Raised because multi-agent indicators were detected but "
                    "no shared state keywords were found."
                ),
            )
        )

    return policy, findings


# --- Dimension 4: Human-in-the-Loop ---


def _detect_hitl_policy(
    contract: AgentContract,
    prompts: list[PromptArtifact],
    classified_files: list[ClassifiedFile],
) -> tuple[HumanInLoopPolicy | None, list[Finding]]:
    """Detect human-in-the-loop patterns and emit gap findings."""
    findings: list[Finding] = []
    all_text = _collect_all_text(prompts, classified_files)

    hitl_matches = _text_contains_any(all_text, _HITL_KEYWORDS)
    override_matches = _text_contains_any(all_text, _OVERRIDE_KEYWORDS)

    has_dangerous = _has_dangerous_tools(contract)
    has_confirmation = _has_confirmation_obligation(contract)

    policy: HumanInLoopPolicy | None = None

    if hitl_matches or has_confirmation:
        # Build the HITL policy from detected evidence
        approval_tools: list[str] = []
        if has_confirmation:
            for ob in contract.obligations:
                if ob.obligation_type == ObligationType.CONFIRMATION_REQUIRED:
                    approval_tools.extend(ob.linked_tool_names)

        policy = HumanInLoopPolicy(
            approval_required_tools=list(set(approval_tools)),
            review_triggers=hitl_matches,
            override_mechanism=(
                f"Override keywords detected: {', '.join(override_matches)}"
                if override_matches
                else None
            ),
            source_evidence=[
                f"HITL keywords: {', '.join(hitl_matches)}" if hitl_matches else "",
                f"Confirmation obligations: {len(approval_tools)} tools" if approval_tools else "",
            ],
        )

    # HITL_GAP: dangerous tools with no HITL
    if has_dangerous and not hitl_matches and not has_confirmation:
        dangerous_tool_names = [
            t.name
            for t in contract.tools
            if t.side_effect_level in (SideEffectLevel.DESTRUCTIVE, SideEffectLevel.EXTERNAL_WRITE)
        ]
        findings.append(
            Finding(
                finding_type="HITL_GAP",
                severity=RiskLevel.HIGH,
                gap_type=GapType.POLICY_GAP,
                title="No human-in-the-loop mechanism detected for dangerous tools",
                description=(
                    f"Dangerous tools ({', '.join(dangerous_tool_names)}) are present "
                    f"but no human approval, confirmation, or review mechanism was detected."
                ),
                evidence=[
                    Evidence(
                        source="contract",
                        location="tools",
                        detail=(
                            f"Dangerous tools: {', '.join(dangerous_tool_names)}. "
                            f"No HITL keywords ('confirm', 'approve', 'permission', "
                            f"'human_review', 'ask_user', 'override', 'escalate') detected."
                        ),
                    )
                ],
                remediation=(
                    "Add a human-in-the-loop mechanism (confirmation gate, "
                    "approval step, or review trigger) for dangerous tools."
                ),
                transparency=(
                    "Raised because dangerous tools (DESTRUCTIVE/EXTERNAL_WRITE) "
                    "are present but no HITL keywords or confirmation obligations "
                    "were detected in prompts or code."
                ),
            )
        )

    # APPROVAL_ENFORCEMENT_GAP: HITL mentioned in prompt but not enforced
    if hitl_matches and has_dangerous and not has_confirmation:
        findings.append(
            Finding(
                finding_type="APPROVAL_ENFORCEMENT_GAP",
                severity=RiskLevel.HIGH,
                gap_type=GapType.ENFORCEMENT_GAP,
                title="Human approval mentioned but no enforcement detected",
                description=(
                    "Human approval keywords detected in prompts but no "
                    "enforcement mechanism (confirmation obligation or tool "
                    "precondition) was found."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            f"HITL keywords detected: {', '.join(hitl_matches)}, "
                            f"but no CONFIRMATION_REQUIRED obligation enforces it."
                        ),
                    )
                ],
                remediation=(
                    "Add a confirmation obligation or tool precondition that "
                    "enforces the human approval requirement at runtime."
                ),
                transparency=(
                    "Raised because HITL keywords were found in prompts but "
                    "no CONFIRMATION_REQUIRED obligation was detected, indicating "
                    "prompt-only safety without enforcement."
                ),
            )
        )

    # OVERRIDE_GAP: autonomous agent without override mechanism
    if has_dangerous and not override_matches:
        findings.append(
            Finding(
                finding_type="OVERRIDE_GAP",
                severity=RiskLevel.MEDIUM,
                gap_type=GapType.POLICY_GAP,
                title="No override mechanism detected",
                description=(
                    "No mechanism for human override or intervention detected "
                    "in an agent with dangerous tools."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            "No override keywords ('override', 'intervention', "
                            "'manual', 'escalate', 'human_fallback') detected."
                        ),
                    )
                ],
                remediation=(
                    "Add an override or escalation mechanism that allows "
                    "humans to intervene in the agent's execution."
                ),
                transparency=(
                    "Raised because dangerous tools are present but no "
                    "override/escalation keywords were detected."
                ),
            )
        )

    return policy, findings


# --- Dimension 5: Failure Handling ---


def _detect_failure_policy(
    contract: AgentContract,
    classified_files: list[ClassifiedFile],
    prompts: list[PromptArtifact],
) -> tuple[FailurePolicy | None, list[Finding]]:
    """Detect failure handling patterns."""
    findings: list[Finding] = []
    all_text = _collect_all_text(prompts, classified_files)

    retry_matches = _text_contains_any(all_text, _RETRY_KEYWORDS)
    timeout_matches = _text_contains_any(all_text, _TIMEOUT_KEYWORDS)
    fallback_matches = _text_contains_any(all_text, _FALLBACK_KEYWORDS)
    partial_matches = _text_contains_any(all_text, _PARTIAL_COMPLETION_KEYWORDS)
    recovery_matches = _text_contains_any(all_text, _RECOVERY_KEYWORDS)

    has_tools = bool(contract.tools)

    policy: FailurePolicy | None = None

    if any([retry_matches, timeout_matches, fallback_matches, partial_matches, recovery_matches]):
        policy = FailurePolicy(
            retry_strategy=(
                f"Detected keywords: {', '.join(retry_matches)}"
                if retry_matches
                else None
            ),
            fallback_behavior=(
                f"Detected keywords: {', '.join(fallback_matches)}"
                if fallback_matches
                else None
            ),
            partial_completion_handling=(
                f"Detected keywords: {', '.join(partial_matches)}"
                if partial_matches
                else None
            ),
            recovery_mechanism=(
                f"Detected keywords: {', '.join(recovery_matches)}"
                if recovery_matches
                else None
            ),
            source_evidence=[
                f"Retry: {', '.join(retry_matches)}" if retry_matches else "",
                f"Timeout: {', '.join(timeout_matches)}" if timeout_matches else "",
                f"Fallback: {', '.join(fallback_matches)}" if fallback_matches else "",
                f"Partial: {', '.join(partial_matches)}" if partial_matches else "",
                f"Recovery: {', '.join(recovery_matches)}" if recovery_matches else "",
            ],
        )

    # Emit gap findings for missing failure handling
    if has_tools and not retry_matches:
        findings.append(
            Finding(
                finding_type="RETRY_POLICY_GAP",
                severity=RiskLevel.LOW,
                gap_type=GapType.POLICY_GAP,
                title="No retry policy detected",
                description=(
                    "Tools are present but no retry or backoff policy was detected."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            "No retry keywords ('retry', 'backoff', "
                            "'max_retries') detected."
                        ),
                    )
                ],
                remediation=(
                    "Add a retry/backoff policy for tool invocations "
                    "to handle transient failures."
                ),
                transparency=(
                    "Raised because tools exist but no retry keywords "
                    "were detected in prompts or file paths."
                ),
            )
        )

    if has_tools and not timeout_matches:
        findings.append(
            Finding(
                finding_type="TIMEOUT_POLICY_GAP",
                severity=RiskLevel.LOW,
                gap_type=GapType.POLICY_GAP,
                title="No timeout policy detected",
                description=(
                    "No timeout or deadline mechanism was detected for tool operations."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            "No timeout keywords ('timeout', 'deadline') detected."
                        ),
                    )
                ],
                remediation=(
                    "Add timeout or deadline configuration for tool operations "
                    "to prevent unbounded execution."
                ),
                transparency=(
                    "Raised because tools exist but no timeout keywords "
                    "were detected in prompts or file paths."
                ),
            )
        )

    if has_tools and not fallback_matches:
        findings.append(
            Finding(
                finding_type="FALLBACK_POLICY_GAP",
                severity=RiskLevel.LOW,
                gap_type=GapType.POLICY_GAP,
                title="No fallback policy detected",
                description=(
                    "No fallback or graceful degradation strategy was detected "
                    "for tool failures."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            "No fallback keywords ('fallback', 'default', "
                            "'graceful') detected."
                        ),
                    )
                ],
                remediation=(
                    "Add a fallback strategy for when tools fail "
                    "(e.g., graceful degradation, default responses)."
                ),
                transparency=(
                    "Raised because tools exist but no fallback keywords "
                    "were detected in prompts or file paths."
                ),
            )
        )

    # PARTIAL_COMPLETION_GAP: only if multi-step detected (decision logic present)
    decision_matches = _text_contains_any(all_text, _DECISION_KEYWORDS)
    if decision_matches and not partial_matches:
        findings.append(
            Finding(
                finding_type="PARTIAL_COMPLETION_GAP",
                severity=RiskLevel.LOW,
                gap_type=GapType.POLICY_GAP,
                title="No partial completion handling detected",
                description=(
                    "Multi-step workflow detected but no partial completion "
                    "handling (checkpoint, resume, rollback) was found."
                ),
                evidence=[
                    Evidence(
                        source="prompts",
                        location="",
                        detail=(
                            "No partial completion keywords ('checkpoint', "
                            "'resume', 'recover', 'rollback') detected."
                        ),
                    )
                ],
                remediation=(
                    "Add partial completion handling: checkpoints, "
                    "resume capability, or rollback mechanism."
                ),
                transparency=(
                    "Raised because multi-step workflow indicators were detected "
                    "but no partial completion keywords were found."
                ),
            )
        )

    # RECOVERY_STATE_GAP: only if stateful (has external_write/destructive tools)
    has_stateful = any(
        t.side_effect_level in (SideEffectLevel.DESTRUCTIVE, SideEffectLevel.EXTERNAL_WRITE)
        for t in contract.tools
    )
    if has_stateful and not recovery_matches:
        findings.append(
            Finding(
                finding_type="RECOVERY_STATE_GAP",
                severity=RiskLevel.MEDIUM,
                gap_type=GapType.POLICY_GAP,
                title="No state recovery mechanism detected",
                description=(
                    "Stateful operations detected (DESTRUCTIVE/EXTERNAL_WRITE tools) "
                    "but no state recovery or rollback mechanism was found."
                ),
                evidence=[
                    Evidence(
                        source="contract",
                        location="tools",
                        detail=(
                            "No recovery keywords ('recover', 'rollback', "
                            "'restore', 'compensate', 'cleanup') detected."
                        ),
                    )
                ],
                remediation=(
                    "Add a state recovery mechanism: rollback, compensation, "
                    "or cleanup strategy for failed stateful operations."
                ),
                transparency=(
                    "Raised because DESTRUCTIVE/EXTERNAL_WRITE tools are present "
                    "but no recovery keywords were detected."
                ),
            )
        )

    return policy, findings


# --- Main entry point ---


def audit_architecture(
    contract: AgentContract,
    classified_files: list[ClassifiedFile],
    prompts: list[PromptArtifact],
) -> tuple[AgentContract, list[Finding]]:
    """Audit the repo against six architecture dimensions and populate policy models.

    Args:
        contract: The compiled AgentContract.
        classified_files: List of classified files from the scan.
        prompts: List of extracted prompt artifacts.

    Returns:
        A tuple of (updated AgentContract, list of Finding objects).
    """
    all_findings: list[Finding] = []

    # 1. Agent Overview
    profiles, overview_findings = _detect_agent_overview(prompts, classified_files)
    all_findings.extend(overview_findings)

    # 2. Autonomy & Decision-Making
    decision_policy, decision_findings = _detect_decision_policy(
        prompts, classified_files, contract
    )
    all_findings.extend(decision_findings)

    # 3. Orchestration (only if multi-agent indicators present)
    orchestration_policy, orchestration_findings = _detect_orchestration(
        prompts, classified_files
    )
    all_findings.extend(orchestration_findings)

    # 4. Human-in-the-Loop
    hitl_policy, hitl_findings = _detect_hitl_policy(
        contract, prompts, classified_files
    )
    all_findings.extend(hitl_findings)

    # 5. Failure Handling
    failure_policy, failure_findings = _detect_failure_policy(
        contract, classified_files, prompts
    )
    all_findings.extend(failure_findings)

    # Populate contract with detected policies
    contract.agent_profiles = profiles
    contract.decision_policy = decision_policy
    contract.human_in_loop_policy = hitl_policy
    contract.failure_policy = failure_policy
    contract.orchestration_policy = orchestration_policy

    return contract, all_findings
