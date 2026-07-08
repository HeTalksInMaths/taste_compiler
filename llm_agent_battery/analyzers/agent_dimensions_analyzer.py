"""Agent-specific dimension analyzers for hackathon evaluation criteria.

Evaluates an agent system against 6 key dimensions:
1. Agent Overview — identity, purpose, capability boundaries
2. Autonomy & Decision-Making — reasoning patterns, planning, tool-use strategies
3. Actions & Tool Use — tool coverage, API interactions, action completeness
4. Orchestration — multi-agent coordination, delegation, communication
5. Human-in-the-Loop — intervention points, approval gates, overrides
6. Failure Handling — error recovery, unexpected state handling, graceful degradation

Unlike the generic CodeReviewAnalyzer which finds code bugs, these analyzers
reason about whether the agent system will achieve its objectives correctly.
"""

from __future__ import annotations

from typing import Optional

from llm_agent_battery.analyzers.base import BaseAnalyzer
from llm_agent_battery.bedrock_client import BedrockClient
from llm_agent_battery.models import (
    ClassifiedFile,
    CodeChunk,
    FileCategory,
    Finding,
    FindingCategory,
    ReviewProfile,
    Severity,
)


class AgentOverviewAnalyzer(BaseAnalyzer):
    """Dimension 1: What agent(s) did you build? What is their purpose?

    Evaluates:
    - Is the agent's identity and purpose clearly defined?
    - Are capability boundaries explicit (what it can/cannot do)?
    - Is the scope narrow enough to be achievable?
    - Are there ambiguities that would cause the model to misinterpret its role?
    """

    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        return """\
You are evaluating an AI agent system's IDENTITY AND PURPOSE definition.

Your task: Read the agent's prompt/configuration and assess whether its identity, \
purpose, and capability boundaries are clearly defined enough for an LLM to \
follow consistently.

Evaluate:
1. Is the agent's role unambiguous? Could the LLM misinterpret what it should do?
2. Are capability boundaries explicit? Does it know what it CANNOT do?
3. Is the scope achievable given the tools available?
4. Are there conflicting instructions that would cause inconsistent behavior?
5. Is the purpose specific enough to guide decision-making in edge cases?

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|design_flaw",
  "location": "where in the prompt/config this issue exists",
  "title": "short title",
  "description": "what's unclear or problematic about the identity/purpose",
  "impact": "how this will cause the agent to behave incorrectly",
  "remediation": "how to fix the identity/purpose definition"
}"""

    def focus_areas(self) -> list[str]:
        return ["identity_clarity", "purpose_specificity", "capability_boundaries", "scope_achievability"]


class AutonomyDecisionMakingAnalyzer(BaseAnalyzer):
    """Dimension 2: How does the agent decide what to do next?

    Evaluates:
    - Is the decision-making strategy explicit (goal decomposition, reactive, plan-then-execute)?
    - Are there clear criteria for when to use which tool?
    - Can the agent get stuck in loops or indecision?
    - Is the reasoning chain auditable?
    - Are there situations where no decision path is defined?
    """

    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        return """\
You are evaluating an AI agent system's DECISION-MAKING AND AUTONOMY patterns.

Your task: Assess whether the agent has a clear, complete strategy for deciding \
what to do next in any situation it might encounter.

Evaluate:
1. Is the decision-making strategy explicit? (goal decomposition, reactive, plan-then-execute)
2. Are there clear criteria for when to use which tool vs. when to ask for help?
3. Can the agent get stuck in infinite loops or indecision states?
4. Are there situations where no decision path is defined (dead states)?
5. Does the agent know when to STOP (completion criteria)?
6. Is there a fallback when the primary strategy fails?
7. Can the agent reason about whether it's making progress toward its goal?

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|design_flaw",
  "location": "where this decision gap exists",
  "title": "short title",
  "description": "what's missing or broken in the decision-making logic",
  "impact": "how the agent will behave when hitting this gap",
  "remediation": "how to fix the decision-making strategy"
}"""

    def focus_areas(self) -> list[str]:
        return ["decision_strategy", "loop_prevention", "dead_states", "completion_criteria", "progress_tracking"]


class ToolUseAnalyzer(BaseAnalyzer):
    """Dimension 3: What actions can the agent take? What tools does it use?

    Evaluates:
    - Does the agent have tools for everything it needs to accomplish?
    - Are tool descriptions clear enough for the model to use them correctly?
    - Are there goals the agent will try to achieve that it has no tool for?
    - Are tool parameters validated? What happens with bad inputs?
    - Are side effects documented? Does the agent understand what's reversible?
    """

    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        return """\
You are evaluating an AI agent system's TOOL USE AND ACTIONS.

Your task: Assess whether the agent has adequate tools for its objectives, \
whether tool definitions are clear enough for correct usage, and whether \
tool interactions are safe.

Evaluate:
1. Does the agent have tools for ALL the goals stated in its purpose/prompt?
2. Are tool descriptions clear enough that the LLM will call them correctly?
3. Are there objectives the agent will try to achieve with NO appropriate tool? \
   (This causes hallucinated actions or misuse of existing tools)
4. Are tool parameters validated? What happens when the model passes bad inputs?
5. Are side effects of each tool documented? Does the agent know what's reversible?
6. Are there tools with overlapping functionality that could confuse tool selection?
7. Is there rate limiting or cost awareness for expensive tool calls?

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|design_flaw|security",
  "location": "which tool or gap this relates to",
  "title": "short title",
  "description": "what's missing or problematic about tool coverage/use",
  "impact": "how the agent will fail when hitting this tool gap",
  "remediation": "how to fix the tool coverage or definition"
}"""

    def focus_areas(self) -> list[str]:
        return ["tool_coverage", "description_clarity", "parameter_validation", "side_effect_awareness", "cost_awareness"]


class OrchestrationAnalyzer(BaseAnalyzer):
    """Dimension 4: How do agents coordinate, delegate, or communicate?

    Evaluates:
    - Is the delegation strategy clear (who does what)?
    - Can agents get into circular delegation loops?
    - Is there a clear escalation path when a sub-agent fails?
    - Is context preserved correctly across agent boundaries?
    - Are there race conditions or ordering issues in multi-agent flows?
    """

    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        return """\
You are evaluating an AI agent system's ORCHESTRATION AND COORDINATION patterns.

Your task: Assess whether multi-agent coordination (or single-agent sub-task \
management) is robust and complete.

Evaluate:
1. Is delegation clear? Does each agent/sub-task know its boundaries?
2. Can agents get into circular delegation loops (A delegates to B delegates to A)?
3. Is there a clear escalation path when a sub-agent/sub-task fails?
4. Is context preserved correctly across agent/task boundaries? \
   (Information loss during handoffs)
5. Are there race conditions or ordering issues in parallel agent flows?
6. Is there a timeout/circuit-breaker for long-running delegated tasks?
7. Can the orchestrator detect when a sub-agent is stuck or producing garbage?

If this is a single-agent system, evaluate sub-task management and self-orchestration.

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|design_flaw",
  "location": "where the orchestration gap exists",
  "title": "short title",
  "description": "what's missing or broken in coordination",
  "impact": "how the system will fail when hitting this orchestration gap",
  "remediation": "how to fix the coordination/delegation"
}"""

    def focus_areas(self) -> list[str]:
        return ["delegation_clarity", "loop_prevention", "escalation_paths", "context_preservation", "timeout_handling"]


class HumanInTheLoopAnalyzer(BaseAnalyzer):
    """Dimension 5: Where does a human intervene, approve, or override?

    Evaluates:
    - Are high-stakes decisions gated by human approval?
    - Can the human understand what the agent is asking permission for?
    - Is there a way to override or abort an in-progress action?
    - Are irreversible actions identified and gated?
    - What happens if the human doesn't respond (timeout behavior)?
    """

    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        return """\
You are evaluating an AI agent system's HUMAN-IN-THE-LOOP safeguards.

Your task: Assess whether appropriate human oversight exists for high-stakes \
decisions, and whether the human interaction patterns are well-designed.

Evaluate:
1. Are high-stakes or irreversible actions gated by human approval?
2. Can the human understand what the agent is requesting permission for? \
   (Is the request presented clearly with context?)
3. Is there a way to override, abort, or roll back an in-progress agent action?
4. Are ALL irreversible actions identified? (Could the agent do something \
   irreversible without human awareness?)
5. What happens if the human doesn't respond? (Timeout → default behavior)
6. Can the human adjust the agent's strategy mid-execution?
7. Is there an audit trail of what the agent did autonomously vs. with approval?

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|design_flaw|security",
  "location": "where the human-in-the-loop gap exists",
  "title": "short title",
  "description": "what's missing in human oversight",
  "impact": "what could go wrong without this human gate",
  "remediation": "how to add appropriate human oversight"
}"""

    def focus_areas(self) -> list[str]:
        return ["approval_gates", "irreversible_action_coverage", "override_mechanism", "timeout_behavior", "audit_trail"]


class FailureHandlingAnalyzer(BaseAnalyzer):
    """Dimension 6: How does the agent recover from errors or unexpected states?

    Evaluates:
    - What happens when a tool call fails? Is there retry/fallback logic?
    - What happens when the LLM refuses or returns garbage?
    - What happens when context overflows?
    - Is there a graceful degradation strategy?
    - Can the agent detect it's in a bad state and recover?
    """

    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        return """\
You are evaluating an AI agent system's FAILURE HANDLING AND RECOVERY.

Your task: Assess whether the agent can gracefully handle errors, unexpected \
states, and edge cases without crashing, looping, or producing harmful output.

Evaluate:
1. What happens when a tool call fails? Is there retry logic? Fallback tools? \
   Or does the agent just crash/loop?
2. What happens when the LLM refuses a request or returns unparseable output?
3. What happens when context/conversation grows too long? (Context overflow)
4. Is there a graceful degradation strategy? (Partial results vs. total failure)
5. Can the agent detect it's in a bad state? (Stuck, looping, making no progress)
6. Are there circuit breakers for cascading failures?
7. What's the worst-case behavior if everything goes wrong simultaneously?
8. Is there logging/observability to diagnose failures after the fact?

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|design_flaw",
  "location": "where the failure handling gap exists",
  "title": "short title",
  "description": "what failure mode is unhandled",
  "impact": "what happens when this failure occurs (crash, loop, bad output, etc.)",
  "remediation": "how to add proper failure handling"
}"""

    def focus_areas(self) -> list[str]:
        return ["tool_failure_recovery", "llm_refusal_handling", "context_overflow", "graceful_degradation", "stuck_detection"]


# --- Aggregate analyzer that runs all 6 dimensions ---

ALL_DIMENSION_ANALYZERS = [
    AgentOverviewAnalyzer,
    AutonomyDecisionMakingAnalyzer,
    ToolUseAnalyzer,
    OrchestrationAnalyzer,
    HumanInTheLoopAnalyzer,
    FailureHandlingAnalyzer,
]
