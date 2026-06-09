"""Scorer evaluation on pair suites and summary computation."""

import statistics
from collections import defaultdict

from evalweaver.runner import py_run_scorer


def eval_scorer(sid, code, pairs):
    """
    Run a scorer against all pairs. Returns list of per-pair result dicts.
    Each row includes: pair_id, split, pair_type, pos_score, neg_score,
    margin, correct, pos_err, neg_err.
    """
    rows = []
    for p in pairs:
        pr = py_run_scorer(code, p["positive"], p["anchor"])
        nr = py_run_scorer(code, p["negative"], p["anchor"])
        rows.append({
            "pair_id": p["pair_id"],
            "split": p["split"],
            "pair_type": p["pair_type"],
            "pos_score": pr["value"],
            "neg_score": nr["value"],
            "margin": pr["value"] - nr["value"],
            "correct": pr["value"] > nr["value"],
            "pos_err": pr.get("error"),
            "neg_err": nr.get("error"),
        })
    return rows


def compute_summary(sid, rows, validation, hyps, round_idx):
    """
    Compute summary statistics for a scorer's evaluation results.
    Returns a dict with accuracy, margins, spread, pair-type breakdowns, etc.
    """
    # Split into train / heldout / adversarial
    tr = [r for r in rows if r["split"] == "train"]
    te = [r for r in rows if r["split"] == "test"]
    adv = [r for r in rows if r["split"] == "adversarial"]

    def acc(lst):
        return sum(r["correct"] for r in lst) / max(1, len(lst))

    def mrg(lst):
        return statistics.mean([r["margin"] for r in lst]) if lst else 0.0

    all_scores = [x for r in rows for x in [r["pos_score"], r["neg_score"]]]
    spread = max(all_scores) - min(all_scores) if all_scores else 0
    err_rate = sum(1 for r in rows if r["pos_err"] or r["neg_err"]) / max(1, len(rows))
    hyp = next((h for h in hyps if h["scorer_id"] == sid), {})

    # Pair-type breakdown
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["pair_type"]].append(r)
    type_acc = {t: sum(r["correct"] for r in rs) / max(1, len(rs)) for t, rs in by_type.items()}

    # Robustness warning
    rob_warns = [t for t, a in type_acc.items() if a < 0.45]

    return {
        "scorer_id": sid,
        "hypothesis": hyp.get("hypothesis", ""),
        "lineage": hyp.get("lineage", "initial"),
        "generation_round": round_idx,
        "valid": validation.get("valid") is True,
        "validation_reason": validation.get("reason", ""),
        "pair_validation_accuracy": validation.get("pair_validation_accuracy", 0),
        "pair_validation_margin": validation.get("pair_validation_margin", 0),
        "pair_validation_spread": validation.get("pair_validation_spread", 0),
        "train_accuracy": acc(tr),
        "train_margin": mrg(tr),
        "test_accuracy": acc(te),
        "test_margin": mrg(te),
        "adversarial_accuracy": acc(adv) if adv else None,
        "adversarial_margin": mrg(adv) if adv else None,
        "score_spread": spread,
        "exec_error_rate": err_rate,
        "pair_type_accuracy": type_acc,
        "robustness_warning": f"fails {rob_warns}" if rob_warns else "",
    }
