"""Mock provider returning hardcoded/seeded outputs for local testing.

This is the default provider. It returns the same mocked research, taste maps,
scorer hypotheses, pairs, and candidates that the v5/v5.1 pipeline uses.
No AWS or LLM dependency required.
"""

from evalweaver.providers.base import AgentProvider


class MockProvider:
    """Returns hardcoded/seeded outputs — no LLM calls."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_id(self) -> str:
        return "mock-v1-seeded"

    def generate_research(self, goal: str, raw_text: str) -> dict:
        """Return mocked research (same as pipeline step 1)."""
        # Import here to avoid circular deps
        from evalweaver.pipeline import RAW_RESEARCH
        return RAW_RESEARCH

    def generate_taste_map(self, goal: str, research: dict) -> dict:
        """Return mocked taste map (same as pipeline step 2)."""
        from evalweaver.pipeline import TASTE_MAP
        return TASTE_MAP

    def generate_scorer_hypotheses(self, taste_map: dict, nlp_theory: dict, count: int) -> list:
        """Return hardcoded scorer hypotheses R0."""
        from evalweaver.pipeline import SCORER_HYPOTHESES_R0
        return SCORER_HYPOTHESES_R0[:count]

    def generate_scorer_code(self, hypothesis: dict) -> str:
        """Return hardcoded scorer code for the given hypothesis."""
        from evalweaver.pipeline import SCORER_CODE_R0
        sid = hypothesis.get("scorer_id", "")
        return SCORER_CODE_R0.get(sid, "def scorer(text, anchor, params): return 0.5")

    def generate_pairs(self, taste_map: dict, scorer_weaknesses: dict, count: int) -> list:
        """Return hardcoded pairs R0."""
        from evalweaver.pairs import ALL_PAIRS_R0
        return ALL_PAIRS_R0[:count]

    def generate_mutations(self, failure_packet: dict, count: int) -> list:
        """Return hardcoded repair hypotheses R1."""
        from evalweaver.repair import SCORER_HYPOTHESES_R1
        return SCORER_HYPOTHESES_R1[:count]

    def generate_candidates(self, goal: str, raw_text: str, taste_map: dict, count: int) -> list:
        """Return hardcoded candidates."""
        from evalweaver.candidates import CANDIDATES
        return CANDIDATES[:count]


# Verify MockProvider satisfies the protocol at import time
assert isinstance(MockProvider(), AgentProvider), "MockProvider does not satisfy AgentProvider protocol"
