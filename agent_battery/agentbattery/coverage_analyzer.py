"""Coverage analyzer module - keyword-matches obligations against test files."""

from __future__ import annotations

import logging
import re

from agentbattery.models import (
    AgentContract,
    ClassifiedFile,
    CoverageResult,
    CoverageStatus,
    Evidence,
    Finding,
    GapType,
    Obligation,
    ObligationCoverage,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Common English stopwords to remove during tokenization
_STOPWORDS: set[str] = {
    "the", "a", "an", "is", "are", "to", "for", "and", "of", "in",
    "on", "it", "that", "this", "with", "be", "as", "at", "or", "by",
    "from", "not", "should", "must", "shall", "will", "can", "may",
    "do", "does", "did", "has", "have", "had", "was", "were", "been",
    "being", "if", "then", "else", "when", "where", "which", "who",
    "whom", "what", "how", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "no", "nor", "only",
    "own", "same", "so", "than", "too", "very",
}

# Coverage thresholds
_COVERED_THRESHOLD: float = 0.6
_PARTIAL_THRESHOLD: float = 0.3


def _tokenize(text: str) -> set[str]:
    """Tokenize text: lowercase, split on non-alphanumeric, remove stopwords.

    Args:
        text: The text to tokenize.

    Returns:
        A set of meaningful tokens (stopwords removed).
    """
    lower = text.lower()
    tokens = re.split(r"[^a-z0-9]+", lower)
    return {t for t in tokens if t and t not in _STOPWORDS}


def _read_file_content(file: ClassifiedFile) -> str:
    """Safely read the content of a classified file.

    Args:
        file: The ClassifiedFile to read.

    Returns:
        The file's text content, or empty string on error.
    """
    try:
        return file.path.read_text(encoding="utf-8", errors="replace")
    except (OSError, IOError) as e:
        logger.warning(f"Could not read file {file.path}: {e}")
        return ""


def _compute_coverage_score(
    obligation_tokens: set[str], file_content: str
) -> float:
    """Compute coverage score as matched_tokens / total_obligation_tokens.

    Args:
        obligation_tokens: Set of meaningful tokens from the obligation.
        file_content: The content of the eval file.

    Returns:
        Score between 0.0 and 1.0 (0.0 if no obligation tokens).
    """
    if not obligation_tokens:
        return 0.0

    content_tokens = _tokenize(file_content)
    matched = obligation_tokens & content_tokens
    return len(matched) / len(obligation_tokens)


def _classify_coverage(score: float) -> CoverageStatus:
    """Classify a coverage score into status.

    Args:
        score: The coverage score (0.0 to 1.0).

    Returns:
        CoverageStatus based on thresholds.
    """
    if score >= _COVERED_THRESHOLD:
        return CoverageStatus.COVERED
    elif score >= _PARTIAL_THRESHOLD:
        return CoverageStatus.PARTIAL
    else:
        return CoverageStatus.MISSING


def _severity_for_obligation(obligation: Obligation) -> RiskLevel:
    """Determine the severity level for a missing obligation finding.

    CONFIRMATION_REQUIRED and RETRIEVAL_INJECTION_GUARD are CRITICAL.
    Others are HIGH.
    """
    from agentbattery.models import ObligationType

    if obligation.obligation_type in (
        ObligationType.CONFIRMATION_REQUIRED,
        ObligationType.RETRIEVAL_INJECTION_GUARD,
    ):
        return RiskLevel.CRITICAL
    return RiskLevel.HIGH


def analyze_coverage(
    contract: AgentContract, eval_files: list[ClassifiedFile]
) -> CoverageResult:
    """Keyword-match obligations against test/eval file content.

    For each obligation:
    1. Extract meaningful tokens from obligation source_text.
    2. For each eval file, read content and tokenize.
    3. Compute score = matched_tokens / total_obligation_tokens.
    4. Best score across all eval files determines coverage status.
    5. Thresholds: >=0.6 → COVERED, >=0.3 → PARTIAL, <0.3 → MISSING.

    Emits COVERAGE_GAP findings for obligations with status MISSING.

    Args:
        contract: The compiled AgentContract with obligations.
        eval_files: List of ClassifiedFile objects filtered to EVAL category.

    Returns:
        CoverageResult with obligation_coverages and counts.
    """
    obligation_coverages: list[ObligationCoverage] = []
    findings: list[Finding] = []
    covered_count = 0
    partial_count = 0
    missing_count = 0

    # Pre-read eval file contents
    eval_contents: list[tuple[ClassifiedFile, str]] = []
    for ef in eval_files:
        content = _read_file_content(ef)
        if content:
            eval_contents.append((ef, content))

    for obligation in contract.obligations:
        ob_tokens = _tokenize(obligation.source_text)

        best_score = 0.0
        matching_files: list[str] = []

        for ef, content in eval_contents:
            score = _compute_coverage_score(ob_tokens, content)
            if score > best_score:
                best_score = score
            if score >= _PARTIAL_THRESHOLD:
                matching_files.append(str(ef.relative_path))

        status = _classify_coverage(best_score)

        obligation_coverages.append(
            ObligationCoverage(
                obligation_id=obligation.id,
                status=status,
                matching_files=matching_files,
                score=best_score,
            )
        )

        if status == CoverageStatus.COVERED:
            covered_count += 1
        elif status == CoverageStatus.PARTIAL:
            partial_count += 1
        else:
            missing_count += 1

    return CoverageResult(
        obligations=obligation_coverages,
        covered_count=covered_count,
        partial_count=partial_count,
        missing_count=missing_count,
    )


def get_coverage_findings(
    contract: AgentContract, coverage_result: CoverageResult
) -> list[Finding]:
    """Emit COVERAGE_GAP findings for obligations with status MISSING.

    Args:
        contract: The compiled AgentContract.
        coverage_result: The result from analyze_coverage().

    Returns:
        List of Finding objects for missing obligations.
    """
    findings: list[Finding] = []

    # Build a lookup for obligations by ID
    ob_by_id = {ob.id: ob for ob in contract.obligations}

    for oc in coverage_result.obligations:
        if oc.status != CoverageStatus.MISSING:
            continue

        obligation = ob_by_id.get(oc.obligation_id)
        if obligation is None:
            continue

        severity = _severity_for_obligation(obligation)

        findings.append(
            Finding(
                finding_type="COVERAGE_GAP",
                severity=severity,
                gap_type=GapType.COVERAGE_GAP,
                title=(
                    f"No test coverage detected for obligation '{obligation.id}'"
                ),
                description=(
                    f"Obligation '{obligation.id}' ({obligation.obligation_type.value}) "
                    f"has no matching eval/test file content (score: {oc.score:.2f}). "
                    f"This obligation may not be verified by any existing test."
                ),
                evidence=[
                    Evidence(
                        source=obligation.source_path,
                        location=obligation.id,
                        detail=(
                            f"Obligation source: \"{obligation.source_text[:80]}\""
                        ),
                    ),
                    Evidence(
                        source="coverage_analysis",
                        location="eval_files",
                        detail=(
                            f"No eval file content matched obligation tokens "
                            f"above threshold (best score: {oc.score:.2f})."
                        ),
                    ),
                ],
                remediation=(
                    f"Add a test or eval that covers obligation '{obligation.id}' "
                    f"({obligation.obligation_type.value})."
                ),
                transparency=(
                    f"Raised because obligation '{obligation.id}' had a coverage "
                    f"score of {oc.score:.2f}, below the MISSING threshold of "
                    f"{_PARTIAL_THRESHOLD}. No eval file contained sufficient "
                    f"matching tokens from the obligation text."
                ),
            )
        )

    return findings
