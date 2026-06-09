"""AgentProvider protocol definition.

An AgentProvider generates text artifacts (scorers, pairs, candidates, mutations)
that in the current v5.1 implementation are hardcoded/seeded. When connected to
a real LLM (e.g., Bedrock Claude), these methods will call the model and parse
structured outputs.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class AgentProvider(Protocol):
    """Protocol for agent providers that generate pipeline artifacts."""

    @property
    def provider_name(self) -> str:
        """Human-readable provider name (e.g., 'mock', 'bedrock-claude')."""
        ...

    @property
    def model_id(self) -> str:
        """Model identifier (e.g., 'mock-v1', 'anthropic.claude-3-sonnet')."""
        ...

    def generate_research(self, goal: str, raw_text: str) -> dict:
        """
        Generate taste research for the given goal.

        Returns:
            dict with research dimensions as keys and research text as values.
        """
        ...

    def generate_taste_map(self, goal: str, research: dict) -> dict:
        """
        Synthesize research into a structured taste map.

        Returns:
            TasteMap dict with rewards, punishes, preserves, key_tensions,
            scorer_hypothesis_seeds.
        """
        ...

    def generate_scorer_hypotheses(self, taste_map: dict, nlp_theory: dict, count: int) -> list:
        """
        Generate scorer hypotheses from taste map and NLP theory.

        Returns:
            List of ScorerHypothesis dicts.
        """
        ...

    def generate_scorer_code(self, hypothesis: dict) -> str:
        """
        Generate Python scorer code from a hypothesis.

        Returns:
            Python code string defining a scorer(text, anchor, params) function.
        """
        ...

    def generate_pairs(self, taste_map: dict, scorer_weaknesses: dict, count: int) -> list:
        """
        Generate evaluation pairs targeting scorer weaknesses.

        Returns:
            List of Pair dicts with anchor, positive, negative, pair_type, etc.
        """
        ...

    def generate_mutations(self, failure_packet: dict, count: int) -> list:
        """
        Generate evolved scorer hypotheses from failure analysis.

        Returns:
            List of ScorerHypothesis dicts with lineage info.
        """
        ...

    def generate_candidates(self, goal: str, raw_text: str, taste_map: dict, count: int) -> list:
        """
        Generate candidate rewrites of the raw_text.

        Returns:
            List of Candidate dicts with candidate_id, strategy, text.
        """
        ...
