"""Eligibility filter and Pareto frontier computation."""


def is_eligible_for_pareto(s):
    """
    F5 FIX: Pareto eligibility filter.
    Returns (eligible: bool, reason: str).
    """
    if s.get("valid") is not True:
        return False, "not valid"
    if s.get("exec_error_rate", 1) > 0:
        return False, "exec errors"
    if s.get("score_spread", 0) < 0.02:
        return False, "score spread too low"
    if s.get("train_margin", 0) <= 0:
        return False, "train margin <= 0"
    if s.get("test_margin", 0) <= 0:
        return False, "test margin <= 0"
    if s.get("train_accuracy", 0) < 0.50:
        return False, "train accuracy < 0.5"
    if s.get("test_accuracy", 0) < 0.50:
        return False, "test accuracy < 0.5"
    return True, "ok"


def compute_pareto(summaries):
    """
    Compute Pareto frontier over eligible scorers.
    Dimensions: test_accuracy, test_margin, train_accuracy, train_margin, score_spread.
    Returns sorted list (best test_margin first).
    """
    elig_list = [s for s in summaries if is_eligible_for_pareto(s)[0]]

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
