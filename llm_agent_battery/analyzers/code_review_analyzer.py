"""Built-in code review analyzer using ReviewProfile system prompts.

Produces Finding objects from LLM JSON responses. Uses the same approach
as scripts/llm_code_review.py but structured as a BaseAnalyzer subclass.
"""

from __future__ import annotations

from typing import Optional

from llm_agent_battery.analyzers.base import BaseAnalyzer
from llm_agent_battery.models import ReviewProfile


_DEFAULT_SYSTEM_PROMPT = """\
You are an expert code reviewer specializing in agent systems, orchestration pipelines, \
and LLM-powered applications.

Your job: Find REAL bugs, logic errors, correctness issues, and design flaws in the code \
chunk shown. Focus on things that cause WRONG results or dangerous behavior. Ignore style \
and formatting.

Focus areas:
- Logic errors that produce incorrect results
- Correctness issues in state management
- Edge cases that could cause crashes or silent failures
- Data integrity problems (lost updates, race conditions)
- Design flaws that make the system fragile or unreliable
- Security issues (prompt injection, unvalidated input, missing auth)

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding must have this structure:
{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|data_integrity|design_flaw|security",
  "location": "function_name or class.method_name",
  "title": "short descriptive title",
  "description": "what's wrong and why",
  "impact": "what breaks because of this",
  "remediation": "how to fix it"
}"""


_PROFILE_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert code reviewer specializing in {architecture_style} agent systems.

{system_prompt_template}

Focus areas for this architecture:
{focus_areas_section}

Anti-patterns to check:
{anti_patterns_section}

Your job: Find REAL bugs, logic errors, correctness issues, and design flaws in the code \
chunk shown. Focus on things that cause WRONG results or dangerous behavior. Ignore style \
and formatting.

Output ONLY a JSON array of findings. If no issues found, return [].
Each finding must have this structure:
{{
  "severity": "critical|high|medium|low",
  "category": "logic_error|correctness|edge_case|data_integrity|design_flaw|security",
  "location": "function_name or class.method_name",
  "title": "short descriptive title",
  "description": "what's wrong and why",
  "impact": "what breaks because of this",
  "remediation": "how to fix it"
}}"""


class CodeReviewAnalyzer(BaseAnalyzer):
    """Default code review analyzer.

    Uses a generic system prompt when no ReviewProfile is provided, or
    constructs a profile-specific prompt that includes the architecture
    style, focus areas, and anti-patterns from the profile.
    """

    def system_prompt(self, profile: Optional[ReviewProfile] = None) -> str:
        """Return the system prompt, customized for the profile if provided."""
        if profile is None:
            return _DEFAULT_SYSTEM_PROMPT

        focus_areas_section = "\n".join(f"- {area}" for area in profile.focus_areas)
        anti_patterns_section = "\n".join(f"- {ap}" for ap in profile.anti_patterns)

        return _PROFILE_SYSTEM_PROMPT_TEMPLATE.format(
            architecture_style=profile.architecture_style.value,
            system_prompt_template=profile.system_prompt_template,
            focus_areas_section=focus_areas_section,
            anti_patterns_section=anti_patterns_section,
        )

    def focus_areas(self) -> list[str]:
        """Return the default focus areas for code review."""
        return [
            "logic_error",
            "correctness",
            "edge_case",
            "data_integrity",
            "design_flaw",
            "security",
        ]
