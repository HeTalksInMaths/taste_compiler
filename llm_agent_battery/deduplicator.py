"""Finding deduplication and ranking logic."""

from __future__ import annotations

from llm_agent_battery.models import Finding, FindingCategory, Severity


# Severity ranking: lower index = higher priority
_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}

# Category ranking: lower index = higher priority
_CATEGORY_ORDER: dict[FindingCategory, int] = {
    FindingCategory.LOGIC_ERROR: 0,
    FindingCategory.CORRECTNESS: 1,
    FindingCategory.EDGE_CASE: 2,
    FindingCategory.DATA_INTEGRITY: 3,
    FindingCategory.DESIGN_FLAW: 4,
    FindingCategory.SECURITY: 5,
}


def deduplicate_and_rank(findings: list[Finding]) -> list[Finding]:
    """Deduplicate findings and rank by severity then category.

    Deduplication rules:
    - Group by (title, file_path, location) tuple
    - Within each group, keep the more detailed one (longer description)
    - Cross-layer: if same finding from both 'heuristic' and 'llm' source_layer,
      keep the LLM version with confirmed_by_heuristic=True

    Ranking:
    - CRITICAL > HIGH > MEDIUM > LOW
    - Within severity: logic_error > correctness > edge_case > data_integrity > design_flaw > security

    Args:
        findings: Raw list of findings from all analysis layers.

    Returns:
        Deduplicated and ranked list of findings.
    """
    if not findings:
        return []

    # Group by dedup key
    groups: dict[tuple[str, str, str], list[Finding]] = {}
    for f in findings:
        key = (f.title, f.file_path, f.location)
        groups.setdefault(key, []).append(f)

    # Resolve each group to a single finding
    merged: list[Finding] = []
    for _key, group in groups.items():
        merged.append(_resolve_group(group))

    # Sort by severity, then category
    merged.sort(key=_sort_key)

    return merged


def _resolve_group(group: list[Finding]) -> Finding:
    """Resolve a group of duplicate findings into one.

    - If both layers present, keep LLM version with confirmed_by_heuristic=True
    - Otherwise keep the one with the longer description
    """
    if len(group) == 1:
        return group[0]

    # Check for cross-layer duplicates
    heuristic_findings = [f for f in group if f.source_layer == "heuristic"]
    llm_findings = [f for f in group if f.source_layer == "llm"]

    if heuristic_findings and llm_findings:
        # Keep the LLM version (typically more detailed), mark as confirmed
        best_llm = max(llm_findings, key=lambda f: len(f.description))
        return best_llm.model_copy(update={"confirmed_by_heuristic": True})

    # Same layer — keep the more detailed one (longer description)
    return max(group, key=lambda f: len(f.description))


def _sort_key(finding: Finding) -> tuple[int, int]:
    """Generate a sort key for ranking: (severity_rank, category_rank)."""
    severity_rank = _SEVERITY_ORDER.get(finding.severity, 99)
    category_rank = _CATEGORY_ORDER.get(finding.category, 99)
    return (severity_rank, category_rank)
