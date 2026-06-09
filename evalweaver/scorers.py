"""Scorer hypotheses, code generation, and pair-based validation."""

from evalweaver.runner import py_run_scorer


VALIDATION_PAIRS = [
    {"pair_id": "VAL_01", "anchor": "We built an AI tool that helps product teams ship faster.",
     "positive": "We built an AI tool that helps product teams ship faster by surfacing which backlog items have the most customer signal -- so you prioritise based on evidence.",
     "negative": "We built an amazing AI tool that helps product teams ship faster with our revolutionary intelligent platform."},
    {"pair_id": "VAL_02", "anchor": "Our analytics tool makes data easier to understand.",
     "positive": "Instead of waiting for a BI report, our tool lets non-technical teams answer their own data questions in minutes -- without SQL.",
     "negative": "Our advanced analytics solution makes data insights easier and more accessible through seamless intelligent automation."},
    {"pair_id": "VAL_03", "anchor": "We help sales teams prioritise leads.",
     "positive": "We help sales teams prioritise leads by scoring each one against your last closed-deal patterns -- so reps call the right accounts first.",
     "negative": "We help sales teams prioritise leads with our groundbreaking AI engine that synergistically optimises your entire pipeline effortlessly."},
    {"pair_id": "VAL_04", "anchor": "Our platform helps companies reduce churn.",
     "positive": "Our platform helps CS teams flag at-risk accounts before customers cancel -- by tracking drops in product engagement and support ticket frequency.",
     "negative": "Our best-in-class platform helps companies reduce churn through our world-class customer success optimisation system. Guaranteed results."},
]


def validate_scorer_on_pairs(code, validation_pairs=None):
    """Validate scorer on actual pair behavior. F1+F2 FIX."""
    if validation_pairs is None:
        validation_pairs = VALIDATION_PAIRS
    rows = []
    for p in validation_pairs:
        pr = py_run_scorer(code, p["positive"], p["anchor"])
        nr = py_run_scorer(code, p["negative"], p["anchor"])
        if not pr["ok"] or not nr["ok"]:
            return {"valid": False, "reason": "runtime_error",
                    "pair_validation_accuracy": 0, "pair_validation_margin": 0,
                    "pair_validation_spread": 0,
                    "details": {"pos_error": pr.get("error"), "neg_error": nr.get("error")}}
        for v in [pr["value"], nr["value"]]:
            if v < -0.01 or v > 1.01:
                return {"valid": False, "reason": "out_of_range",
                        "pair_validation_accuracy": 0, "pair_validation_margin": 0,
                        "pair_validation_spread": 0}
        rows.append({"pair_id": p["pair_id"], "pos_score": pr["value"],
                     "neg_score": nr["value"], "margin": pr["value"] - nr["value"],
                     "correct": pr["value"] > nr["value"]})
    all_scores = [x for r in rows for x in [r["pos_score"], r["neg_score"]]]
    spread = max(all_scores) - min(all_scores) if all_scores else 0
    acc = sum(r["correct"] for r in rows) / max(1, len(rows))
    margin = sum(r["margin"] for r in rows) / max(1, len(rows))
    if spread < 0.001:
        return {"valid": False, "reason": "constant_pair_outputs",
                "pair_validation_accuracy": acc, "pair_validation_margin": margin,
                "pair_validation_spread": spread}
    return {"valid": True, "reason": "ok", "pair_validation_accuracy": acc,
            "pair_validation_margin": margin, "pair_validation_spread": spread,
            "validation_rows": rows}
