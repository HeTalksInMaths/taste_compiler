"""Unit tests for llm_agent_battery.deduplicator module."""

from llm_agent_battery.deduplicator import deduplicate_and_rank
from llm_agent_battery.models import Finding, FindingCategory, Severity


def _finding(
    severity=Severity.MEDIUM,
    category=FindingCategory.CORRECTNESS,
    file_path="test.py",
    location="func",
    title="Test finding",
    description="desc",
    source_layer="llm",
    confirmed_by_heuristic=False,
):
    return Finding(
        severity=severity,
        category=category,
        file_path=file_path,
        location=location,
        title=title,
        description=description,
        impact="impact",
        source_layer=source_layer,
        confirmed_by_heuristic=confirmed_by_heuristic,
    )


class TestDeduplication:
    """Tests for deduplication logic."""

    def test_empty_list(self):
        assert deduplicate_and_rank([]) == []

    def test_no_duplicates_preserved(self):
        findings = [
            _finding(title="A", file_path="a.py"),
            _finding(title="B", file_path="b.py"),
        ]
        result = deduplicate_and_rank(findings)
        assert len(result) == 2

    def test_duplicate_keeps_longer_description(self):
        findings = [
            _finding(title="Bug", description="Short"),
            _finding(title="Bug", description="A much longer description with details"),
        ]
        result = deduplicate_and_rank(findings)
        assert len(result) == 1
        assert "longer" in result[0].description

    def test_cross_layer_keeps_llm_with_confirmation(self):
        findings = [
            _finding(title="Bug", source_layer="heuristic", description="heuristic desc"),
            _finding(title="Bug", source_layer="llm", description="detailed llm desc"),
        ]
        result = deduplicate_and_rank(findings)
        assert len(result) == 1
        assert result[0].source_layer == "llm"
        assert result[0].confirmed_by_heuristic is True

    def test_different_locations_not_deduped(self):
        findings = [
            _finding(title="Bug", location="func_a"),
            _finding(title="Bug", location="func_b"),
        ]
        result = deduplicate_and_rank(findings)
        assert len(result) == 2


class TestRanking:
    """Tests for ranking logic."""

    def test_severity_order(self):
        findings = [
            _finding(severity=Severity.LOW, title="L", file_path="l.py"),
            _finding(severity=Severity.CRITICAL, title="C", file_path="c.py"),
            _finding(severity=Severity.HIGH, title="H", file_path="h.py"),
            _finding(severity=Severity.MEDIUM, title="M", file_path="m.py"),
        ]
        result = deduplicate_and_rank(findings)
        assert result[0].severity == Severity.CRITICAL
        assert result[1].severity == Severity.HIGH
        assert result[2].severity == Severity.MEDIUM
        assert result[3].severity == Severity.LOW

    def test_category_order_within_severity(self):
        findings = [
            _finding(severity=Severity.HIGH, category=FindingCategory.DESIGN_FLAW, title="D", file_path="d.py"),
            _finding(severity=Severity.HIGH, category=FindingCategory.LOGIC_ERROR, title="L", file_path="l.py"),
            _finding(severity=Severity.HIGH, category=FindingCategory.CORRECTNESS, title="C", file_path="c.py"),
            _finding(severity=Severity.HIGH, category=FindingCategory.EDGE_CASE, title="E", file_path="e.py"),
        ]
        result = deduplicate_and_rank(findings)
        assert result[0].category == FindingCategory.LOGIC_ERROR
        assert result[1].category == FindingCategory.CORRECTNESS
        assert result[2].category == FindingCategory.EDGE_CASE
        assert result[3].category == FindingCategory.DESIGN_FLAW
