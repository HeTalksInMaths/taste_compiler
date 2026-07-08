"""Base class for deterministic heuristic analyzers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from llm_agent_battery.models import ClassifiedFile, Finding


class BaseHeuristicAnalyzer(ABC):
    """Abstract base class for heuristic pattern analyzers.

    Each concrete analyzer implements `analyze()` to scan classified files
    for specific structural anti-patterns and produce findings without
    requiring any LLM invocations.
    """

    @abstractmethod
    def analyze(self, files: list[ClassifiedFile]) -> list[Finding]:
        """Analyze classified files and return any detected findings.

        Args:
            files: List of classified source files to analyze.

        Returns:
            List of Finding objects for detected issues.
        """
        ...
