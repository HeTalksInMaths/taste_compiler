"""Deterministic heuristic analyzers for fast structural analysis.

Two analyzer groups:
- analyzers.py: generic agent anti-patterns (error handling, mutations,
  confirmation gates, prompt injection)
- agent_patterns.py: agent-architecture design failure patterns (runaway
  loops, missing timeouts, unsafe execution of model output, context
  growth, hardcoded credentials, unvalidated LLM output)

ALL_HEURISTIC_ANALYZERS is the canonical battery; the pipeline runs every
analyzer listed there.
"""

from llm_agent_battery.heuristics.base import BaseHeuristicAnalyzer
from llm_agent_battery.heuristics.analyzers import (
    MissingConfirmationGateAnalyzer,
    MissingErrorHandlingAnalyzer,
    PromptInjectionAnalyzer,
    UnguardedMutationAnalyzer,
)
from llm_agent_battery.heuristics.agent_patterns import (
    HardcodedCredentialsAnalyzer,
    MissingTimeoutAnalyzer,
    UnboundedAgentLoopAnalyzer,
    UnboundedContextGrowthAnalyzer,
    UnsafeCodeExecutionAnalyzer,
    UnvalidatedLLMOutputAnalyzer,
)

ALL_HEURISTIC_ANALYZERS: list[type[BaseHeuristicAnalyzer]] = [
    MissingErrorHandlingAnalyzer,
    UnguardedMutationAnalyzer,
    MissingConfirmationGateAnalyzer,
    PromptInjectionAnalyzer,
    UnboundedAgentLoopAnalyzer,
    MissingTimeoutAnalyzer,
    UnsafeCodeExecutionAnalyzer,
    UnboundedContextGrowthAnalyzer,
    HardcodedCredentialsAnalyzer,
    UnvalidatedLLMOutputAnalyzer,
]

__all__ = [
    "BaseHeuristicAnalyzer",
    "ALL_HEURISTIC_ANALYZERS",
    "MissingErrorHandlingAnalyzer",
    "UnguardedMutationAnalyzer",
    "MissingConfirmationGateAnalyzer",
    "PromptInjectionAnalyzer",
    "UnboundedAgentLoopAnalyzer",
    "MissingTimeoutAnalyzer",
    "UnsafeCodeExecutionAnalyzer",
    "UnboundedContextGrowthAnalyzer",
    "HardcodedCredentialsAnalyzer",
    "UnvalidatedLLMOutputAnalyzer",
]
