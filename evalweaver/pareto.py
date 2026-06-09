"""Eligibility filter and Pareto frontier computation."""


def is_eligible_for_pareto(s):
    """
    F5 FIX: Pareto eligibility filter.
    Returns (eligible: bool, reason: str).
    Also sets pareto_eligible and pareto_ineligible_reason on the summary dict.
    """
    reason = ""
    eligible = True

    if s.get("valid") is not True:
        eligible, reason = False, "not valid (execution_valid=False)"
    elif s.get("exec_error_rate", 1) > 0:
        eligible, reason = False, "exec errors"
    elif s.get("score_spread", 0) < 0.02:
        eligible, reason = False, "score spread too low (<0.02)"
    elif s.get("train_margin", 0) <= 0:
        eligible, reason = False, "train margin <= 0"
    elif s.get("test_margin", 0) <= 0:
        eligible, reason = False, "test margin <= 0"
    elif s.get("train_accuracy", 0) < 0.50:
        eligible, reason = False, "train accuracy < 0.5"
    elif s.get("test_accuracy", 0) < 0.50:
        eligible, reason = False, "test accuracy < 0.5"

    # Set fields on the summary dict for three-tier reporting
    s["pareto_eligible"] = eligible
    s["pareto_ineligible_reason"] = reason if not eligible else ""

    return eligible, reason


def compute_pareto(summaries):
    """
    Compute Pareto frontier over eligible scorers.
    Dimensions: test_accuracy, test_margin, train_accuracy, train_margin, score_spread.
    Returns sorted list (best test_margin first).

    Also sets pareto_eligible and pareto_ineligible_reason on all summaries.
    """
    # Evaluate eligibility for all summaries (sets fields on each)
    for s in summaries:
        is_eligible_for_pareto(s)

    elig_list = [s for s in summaries if s.get("pareto_eligible")]

    front = []
    for a in elig_list:
        dominated = any(
            b is not a
            and b["test_accuracy"] >= a["test_accuracy"]
            and b["test_margin"] >= a["test_margin"]
            and b["train_accuracy"] >= a["train_accuracy"]
            and b["train_margin"] >= a["train_margin"]
            and b["score_spread"] >= a["score_spread"]
            and (b["test_accuracy"] > a["test_accuracy"]
                 or b["test_margin"] > a["test_margin"]
                 or b["train_accuracy"] > a["train_accuracy"]
                 or b["train_margin"] > a["train_margin"]
                 or b["score_spread"] > a["score_spread"])
            for b in elig_list
        )
        if not dominated:
            front.append(a)

    return sorted(front, key=lambda x: (x["test_margin"], x["test_accuracy"], x["train_margin"]), reverse=True)
