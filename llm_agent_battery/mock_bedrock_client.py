"""Offline mock of the Bedrock Converse client.

Mimics the public surface of ``BedrockClient`` (``converse``,
``validate_credentials``, ``total_usage``) so the full LLM pipeline can run
without AWS credentials, network access, or token spend.

This is NOT a language model. It is a deterministic, content-aware responder:
it inspects the system prompt to learn which analyzer is calling, scans the
user message for a curated set of code/design signals, and emits findings in
the exact JSON shape the analyzers expect to parse. The goal is to exercise
the end-to-end pipeline (chunking, concurrency, dedup, reporting) and to give
reproducible, input-dependent output for tests, demos, and CI — not to replace
real semantic review.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from llm_agent_battery.models import ConcurrencyConfig, InferenceConfig, TokenUsage


@dataclass(frozen=True)
class _Rule:
    """A single content detector used to synthesize a finding."""

    pattern: re.Pattern[str]
    severity: str
    category: str
    title: str
    description: str
    impact: str
    remediation: str


# --- Per-chunk code-review rules -------------------------------------------
# These read like semantic findings (not pure structural lints) so the mock's
# output is distinguishable from, and complementary to, the heuristic layer.

_CODE_REVIEW_RULES: list[_Rule] = [
    _Rule(
        pattern=re.compile(r"except[^:\n]*:\s*(?:\n\s*)?(?:pass|return\s+None|return)\b"),
        severity="medium",
        category="edge_case",
        title="Silently swallowed exception",
        description=(
            "An except handler discards the error (pass/return) without logging "
            "or re-raising, so failures disappear with no diagnostic trail."
        ),
        impact="Real failures are masked; the agent proceeds on bad state and is hard to debug.",
        remediation="Log the exception with context and either recover deliberately or re-raise.",
    ),
    _Rule(
        pattern=re.compile(r"def\s+\w+\([^)]*=\s*(?:\[\]|\{\}|set\(\))"),
        severity="medium",
        category="correctness",
        title="Mutable default argument",
        description=(
            "A function uses a mutable default (list/dict/set). The default is "
            "shared across all calls and accumulates state between invocations."
        ),
        impact="State leaks between calls, producing nondeterministic, hard-to-reproduce bugs.",
        remediation="Default to None and create the container inside the function body.",
    ),
    _Rule(
        pattern=re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b"),
        severity="low",
        category="design_flaw",
        title="Unfinished work marker in shipped path",
        description="A TODO/FIXME/HACK marker indicates incomplete or provisional logic.",
        impact="Known gaps may be exercised in production with undefined behavior.",
        remediation="Resolve the marker or convert it into a tracked issue with a guard.",
    ),
    _Rule(
        pattern=re.compile(r"\btime\.sleep\s*\("),
        severity="medium",
        category="design_flaw",
        title="Blocking sleep on an async/agent path",
        description=(
            "A synchronous time.sleep() blocks the thread; on an async or "
            "concurrent agent path it stalls unrelated work."
        ),
        impact="Reduced throughput and stalled concurrency during back-off or polling.",
        remediation="Use awaitable delays (asyncio.sleep) on async paths and bound the wait.",
    ),
    _Rule(
        pattern=re.compile(r"=\s*\[\s*0\s*\]|\bcontent\s*\[\s*0\s*\]|\[\s*0\s*\]\s*\["),
        severity="medium",
        category="edge_case",
        title="Unchecked index into a possibly-empty sequence",
        description="Indexing [0] without first checking length raises IndexError when empty.",
        impact="An empty model response or tool result crashes the step instead of degrading.",
        remediation="Guard the length (or use a safe accessor) before indexing.",
    ),
]


# --- Agent-dimension rules --------------------------------------------------
# Keyed on distinctive phrases in each dimension analyzer's system prompt. Each
# rule fires only when the aggregated context LACKS an expected safeguard.

@dataclass(frozen=True)
class _DimensionRule:
    prompt_marker: str
    absent_signal: re.Pattern[str]
    severity: str
    category: str
    title: str
    description: str
    impact: str
    remediation: str


_DIMENSION_RULES: list[_DimensionRule] = [
    _DimensionRule(
        prompt_marker="DECISION-MAKING AND AUTONOMY",
        absent_signal=re.compile(r"max_?(?:iter|steps?|turns?|rounds?|attempts?)", re.IGNORECASE),
        severity="high",
        category="design_flaw",
        title="No explicit iteration budget in the agent's control loop",
        description=(
            "The aggregated agent context shows no max-iteration / max-step / "
            "max-turn bound governing the decision loop."
        ),
        impact="If the model never emits a stop signal the agent can loop without termination.",
        remediation="Introduce a hard iteration cap with a defined fallback when it is reached.",
    ),
    _DimensionRule(
        prompt_marker="HUMAN-IN-THE-LOOP",
        absent_signal=re.compile(r"confirm|approval|authorize|human_in_the_loop|review", re.IGNORECASE),
        severity="high",
        category="security",
        title="No human approval gate for high-stakes actions",
        description=(
            "No confirmation/approval/authorization signal appears anywhere in the "
            "agent context, yet the system can take consequential actions."
        ),
        impact="Irreversible or sensitive actions execute autonomously with no oversight.",
        remediation="Add an approval gate for irreversible/high-impact tools before execution.",
    ),
    _DimensionRule(
        prompt_marker="FAILURE HANDLING AND RECOVERY",
        absent_signal=re.compile(r"try\s*:|except|retry|fallback|circuit", re.IGNORECASE),
        severity="high",
        category="edge_case",
        title="No visible failure-recovery strategy",
        description=(
            "The agent context contains no try/except, retry, fallback, or "
            "circuit-breaker constructs."
        ),
        impact="A single tool or model failure propagates unhandled and halts the agent.",
        remediation="Add retry-with-backoff, fallbacks, and graceful degradation on tool/model errors.",
    ),
]


class MockBedrockClient:
    """Drop-in, offline replacement for :class:`BedrockClient`.

    Implements the same public interface but returns deterministic,
    content-aware JSON instead of calling AWS.
    """

    def __init__(
        self,
        config: InferenceConfig | None = None,
        concurrency_config: ConcurrencyConfig | None = None,
    ) -> None:
        self._config = config or InferenceConfig()
        self._concurrency_config = concurrency_config or ConcurrencyConfig()
        self._usage = TokenUsage()

    def validate_credentials(self) -> dict:
        """No-op credential check; the mock never touches AWS."""
        return {"account": "mock", "arn": "arn:mock:offline", "user_id": "mock"}

    async def converse(self, system: str, user: str) -> str:
        """Return a JSON array of findings synthesized from the inputs."""
        findings = self._synthesize(system, user)
        response = json.dumps(findings)
        self._track_usage(system, user, response)
        return response

    def _synthesize(self, system: str, user: str) -> list[dict]:
        """Pick the right rule set from the system prompt and scan the content."""
        # Dimension analyzers carry distinctive prompt markers.
        for rule in _DIMENSION_RULES:
            if rule.prompt_marker in system:
                if not rule.absent_signal.search(user):
                    return [self._dimension_finding(rule)]
                return []

        # Other dimension analyzers (overview, tool use, orchestration) have no
        # absence-rule wired up yet; return clean rather than noisy.
        dimension_only_markers = (
            "IDENTITY AND PURPOSE",
            "TOOL USE AND ACTIONS",
            "ORCHESTRATION AND COORDINATION",
        )
        if any(marker in system for marker in dimension_only_markers):
            return []

        # Default: per-chunk code review.
        findings: list[dict] = []
        for rule in _CODE_REVIEW_RULES:
            match = rule.pattern.search(user)
            if not match:
                continue
            findings.append({
                "severity": rule.severity,
                "category": rule.category,
                "location": self._locate(user, match.start()),
                "title": rule.title,
                "description": rule.description,
                "impact": rule.impact,
                "remediation": rule.remediation,
            })
        return findings

    @staticmethod
    def _dimension_finding(rule: _DimensionRule) -> dict:
        return {
            "severity": rule.severity,
            "category": rule.category,
            "location": "agent system (aggregate)",
            "title": rule.title,
            "description": rule.description,
            "impact": rule.impact,
            "remediation": rule.remediation,
        }

    @staticmethod
    def _locate(text: str, offset: int) -> str:
        """Best-effort location: nearest preceding def/class, else line number."""
        prefix = text[:offset]
        line_no = prefix.count("\n") + 1
        for line in reversed(prefix.splitlines()):
            stripped = line.strip()
            if stripped.startswith(("def ", "async def ", "class ")):
                name = stripped.split("(")[0].split()[-1].rstrip(":")
                return name
        return f"line {line_no}"

    def _track_usage(self, system: str, user: str, response: str) -> None:
        """Approximate token usage (~4 chars/token) so reports populate."""
        self._usage.input_tokens += (len(system) + len(user)) // 4
        self._usage.output_tokens += len(response) // 4
        self._usage.total_tokens = self._usage.input_tokens + self._usage.output_tokens

    @property
    def total_usage(self) -> TokenUsage:
        return self._usage
