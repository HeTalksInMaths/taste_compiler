"""Candidate scoring, ensemble selection, and policy validation."""

import statistics

from evalweaver.runner import py_run_scorer
from evalweaver.policy import (
    extract_numbers,
    source_policy_violations,
    hard_source_policy_violated,
)


# ─────────────────────────────────────────────────────────────────────
# CANDIDATE DATA
# ─────────────────────────────────────────────────────────────────────

CANDIDATES = [
    {"candidate_id": "C001", "strategy": "mechanism_first",
     "text": "EvalWeaver lets anyone create, use, and monetise AI improvers for subjective goals like 'more persuasive' \u2014 by building a causal theory of what the goal means, testing it on real examples, and using the strongest evaluator to guide each rewrite."},
    {"candidate_id": "C002", "strategy": "audience_pain",
     "text": "Tired of asking AI to improve your writing and getting results that feel off? EvalWeaver discovers what your improvement goal actually means, validates that theory against real examples, and only then rewrites."},
    {"candidate_id": "C003", "strategy": "concrete_outcome",
     "text": "EvalWeaver turns vague goals like 'more persuasive' into testable evaluators \u2014 so you improve text based on what actually moves your readers, not what sounds plausible to an AI."},
    {"candidate_id": "C004", "strategy": "hype_control_baseline",
     "text": "EvalWeaver is the ultimate revolutionary AI that instantly transforms any writing goal into the most amazing, guaranteed persuasion results you've ever seen."},
]


# ─────────────────────────────────────────────────────────────────────
# ENSEMBLE SCORING AND SELECTION
# ─────────────────────────────────────────────────────────────────────

def build_candidate_ensemble(pareto):
    """
    Build eligible ensemble from Pareto frontier scorers.
    Eligible: valid, positive heldout margin, accuracy >= 0.5, spread >= 0.02.
    """
    return [
        s for s in pareto
        if s.get("valid") is True
        and s.get("test_margin", 0) > 0
        and s.get("test_accuracy", 0) >= 0.5
        and s.get("score_spread", 0) >= 0.02
    ]


def score_candidates(candidates, ensemble, scorer_code, raw_text):
    """
    Score candidates using the eligible ensemble.
    Returns list of scored candidate dicts, sorted by (policy_ok, ensemble_score) descending.

    Each candidate stores:
    - policy_violations: from source_policy_violations(text, anchor, role="candidate")
    - policy_ok: not hard_source_policy_violated(text, anchor, role="candidate")
    - raw_mean_score: unnormalized mean across scorers
    - normalized_ensemble_score: same as ensemble_score (explicit naming)
    """
    if not ensemble:
        return []

    # Raw scores
    raw_scores = {}
    for c in candidates:
        raw_scores[c["candidate_id"]] = {}
        for s in ensemble:
            r = py_run_scorer(scorer_code[s["scorer_id"]], c["text"], raw_text)
            raw_scores[c["candidate_id"]][s["scorer_id"]] = r["value"]

    # Normalise per scorer
    norm_scores = {}
    for s in ensemble:
        sid = s["scorer_id"]
        vals = [raw_scores[c["candidate_id"]][sid] for c in candidates]
        mn, mx = min(vals), max(vals)
        rng_s = mx - mn if mx > mn else 1
        norm_scores[sid] = {
            c["candidate_id"]: (raw_scores[c["candidate_id"]][sid] - mn) / rng_s
            for c in candidates
        }

    scored_candidates = []
    for c in candidates:
        norm_mean = statistics.mean(
            norm_scores[s["scorer_id"]][c["candidate_id"]] for s in ensemble
        )
        raw_mean = statistics.mean(
            raw_scores[c["candidate_id"]][s["scorer_id"]] for s in ensemble
        )

        # Use unified policy functions (same as scorer veto path)
        violations = source_policy_violations(c["text"], raw_text, role="candidate")
        policy_ok = not hard_source_policy_violated(c["text"], raw_text, role="candidate")

        scored_candidates.append({
            **c,
            "raw_scores": raw_scores[c["candidate_id"]],
            "norm_scores": {s["scorer_id"]: norm_scores[s["scorer_id"]][c["candidate_id"]] for s in ensemble},
            "ensemble_score": round(norm_mean, 4),
            "normalized_ensemble_score": round(norm_mean, 4),
            "raw_mean_score": round(raw_mean, 4),
            "policy_ok": policy_ok,
            "policy_violations": violations,
        })

    scored_candidates.sort(key=lambda x: (x["policy_ok"], x["ensemble_score"]), reverse=True)
    return scored_candidates


def select_candidate(scored_candidates):
    """Select the top-scoring policy-compliant candidate."""
    if not scored_candidates:
        return None
    return scored_candidates[0]
