"""Stage 6: Deterministic scorer evaluation on pair suite with Pareto frontier computation.

This module executes all scorers on all pairs via py_run_scorer (no LLM calls).
It computes per-scorer summaries and identifies the Pareto frontier over eligible scorers.
"""

from evalweaver.runner import py_run_scorer


def _compute_pareto_frontier_2d(eligible_summaries: list) -> list:
    """Compute 2D Pareto frontier over (heldout_accuracy, heldout_mean_gap).

    A scorer is non-dominated if no other eligible scorer has both dimensions >= and at least one strictly >.
    Returns list of frontier scorers as dicts with {scorer_id, heldout_accuracy, heldout_mean_gap}.
    """
    if not eligible_summaries:
        return []

    frontier = []
    for a in eligible_summaries:
        dominated = False
        for b in eligible_summaries:
            if b is a:
                continue
            if (b["heldout_accuracy"] >= a["heldout_accuracy"] and
                    b["heldout_mean_gap"] >= a["heldout_mean_gap"] and
                    (b["heldout_accuracy"] > a["heldout_accuracy"] or
                     b["heldout_mean_gap"] > a["heldout_mean_gap"])):
                dominated = True
                break
        if not dominated:
            frontier.append({
                "scorer_id": a["scorer_id"],
                "heldout_accuracy": a["heldout_accuracy"],
                "heldout_mean_gap": a["heldout_mean_gap"],
            })

    return sorted(frontier, key=lambda x: (x["heldout_accuracy"], x["heldout_mean_gap"]), reverse=True)


def run_stage_6(scorers: list, pair_suite: dict, anchor: str) -> dict:
    """
    Execute all scorers on all pairs deterministically.

    For each scorer, runs code on each pair via py_run_scorer.
    Computes per-scorer per-pair rows and per-scorer summaries.
    Computes Pareto frontier over eligible scorers.

    Args:
        scorers: list of scorer dicts, each with at least 'scorer_id' and 'code'
        pair_suite: dict with 'pairs' list, each pair having pair_id, split, anchor, positive, negative
        anchor: the raw_text anchor for scorer execution

    Returns:
        dict with {scorer_evaluations, scorer_summaries, pareto_frontier}
    """
    pairs = pair_suite.get("pairs", [])

    scorer_evaluations = {}  # scorer_id -> list of eval rows
    scorer_summaries = []

    for scorer in scorers:
        scorer_id = scorer.get("scorer_id", "")
        code = scorer.get("code", "")

        rows = []
        exec_errors = 0
        total_pairs = len(pairs)

        all_scores = []

        for pair in pairs:
            pair_id = pair.get("pair_id", "")
            split = pair.get("split", "train")
            positive_text = pair.get("positive", "")
            negative_text = pair.get("negative", "")
            pair_anchor = pair.get("anchor", anchor)

            # Run scorer on positive
            pos_result = py_run_scorer(code, positive_text, pair_anchor)
            # Run scorer on negative
            neg_result = py_run_scorer(code, negative_text, pair_anchor)

            if not pos_result["ok"] or not neg_result["ok"]:
                exec_errors += 1
                rows.append({
                    "pair_id": pair_id,
                    "split": split,
                    "positive_score": None,
                    "negative_score": None,
                    "gap": None,
                    "correct": False,
                })
                continue

            positive_score = pos_result["value"]
            negative_score = neg_result["value"]
            gap = positive_score - negative_score
            correct = gap > 0

            all_scores.append(positive_score)
            all_scores.append(negative_score)

            rows.append({
                "pair_id": pair_id,
                "split": split,
                "positive_score": positive_score,
                "negative_score": negative_score,
                "gap": gap,
                "correct": correct,
            })

        scorer_evaluations[scorer_id] = rows

        # Compute per-scorer summary
        exec_error_rate = exec_errors / max(total_pairs, 1)

        # Split rows by train/heldout (only valid rows)
        valid_rows = [r for r in rows if r["positive_score"] is not None]
        train_rows = [r for r in valid_rows if r["split"] == "train"]
        heldout_rows = [r for r in valid_rows if r["split"] == "heldout"]

        train_accuracy = (sum(1 for r in train_rows if r["correct"]) / len(train_rows)) if train_rows else None
        train_mean_gap = (sum(r["gap"] for r in train_rows) / len(train_rows)) if train_rows else None
        heldout_accuracy = (sum(1 for r in heldout_rows if r["correct"]) / len(heldout_rows)) if heldout_rows else None
        heldout_mean_gap = (sum(r["gap"] for r in heldout_rows) / len(heldout_rows)) if heldout_rows else None

        # score_spread: range of all scores
        score_spread = (max(all_scores) - min(all_scores)) if all_scores else 0.0

        # nonconstant_rate: 1.0 if produces different scores, 0.0 if constant
        nonconstant_rate = 1.0 if (all_scores and len(set(round(v, 10) for v in all_scores)) >= 2) else 0.0

        # Eligibility check
        eligible, eligibility_reason = _check_eligibility(
            exec_error_rate, nonconstant_rate, score_spread, heldout_accuracy, heldout_mean_gap
        )

        summary = {
            "scorer_id": scorer_id,
            "train_accuracy": train_accuracy,
            "train_mean_gap": train_mean_gap,
            "heldout_accuracy": heldout_accuracy,
            "heldout_mean_gap": heldout_mean_gap,
            "score_spread": score_spread,
            "exec_error_rate": exec_error_rate,
            "nonconstant_rate": nonconstant_rate,
            "eligible": eligible,
            "eligibility_reason": eligibility_reason,
        }
        scorer_summaries.append(summary)

    # Compute Pareto frontier over eligible scorers
    eligible_summaries = [s for s in scorer_summaries if s["eligible"]]
    pareto_frontier = _compute_pareto_frontier_2d(eligible_summaries)

    return {
        "scorer_evaluations": scorer_evaluations,
        "scorer_summaries": scorer_summaries,
        "pareto_frontier": pareto_frontier,
    }


def _check_eligibility(exec_error_rate: float, nonconstant_rate: float, score_spread: float,
                        heldout_accuracy, heldout_mean_gap) -> tuple:
    """Check Pareto eligibility. Returns (eligible: bool, reason: str)."""
    if exec_error_rate != 0:
        return (False, "exec_error_rate > 0")
    if nonconstant_rate <= 0:
        return (False, "constant output")
    if score_spread < 0.02:
        return (False, "score_spread < 0.02")
    if heldout_accuracy is None or heldout_accuracy < 0.50:
        return (False, "heldout_accuracy < 0.50")
    if heldout_mean_gap is None or heldout_mean_gap <= 0:
        return (False, "heldout_mean_gap <= 0")
    return (True, "eligible")
