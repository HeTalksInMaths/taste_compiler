"""Failure analysis, mutation instructions, and adversarial pair instructions."""

import statistics
from collections import defaultdict


def build_failure_packet(round_idx, summaries, eval_results, pair_suite, pareto,
                         scorer_code, prior_instructions=None):
    """
    Build a failure packet for a round. Identifies weaknesses in top scorers,
    generates mutation and adversarial pair instructions.

    F8 fix: tracks applied instructions to avoid repetition.

    Args:
        round_idx: Current round index (0 or 1).
        summaries: List of scorer summary dicts.
        eval_results: Dict of {scorer_id: [eval_rows]}.
        pair_suite: Dict with train/test/all pair lists.
        pareto: Pareto frontier list.
        scorer_code: Dict of {scorer_id: code_string}.
        prior_instructions: List of mutation instructions from prior rounds.
    """
    prior = set(prior_instructions or [])
    top_sids = [s["scorer_id"] for s in pareto[:3]]

    # Failed visible pairs by top scorers
    failed_visible = []
    low_margin_visible = []
    for sid in top_sids:
        for r in eval_results.get(sid, []):
            if r["split"] == "train":
                if not r["correct"]:
                    failed_visible.append({
                        "scorer_id": sid, "pair_id": r["pair_id"],
                        "pair_type": r["pair_type"], "pos": round(r["pos_score"], 3),
                        "neg": round(r["neg_score"], 3), "margin": round(r["margin"], 3)
                    })
                elif 0 < r["margin"] < 0.04:
                    low_margin_visible.append({
                        "scorer_id": sid, "pair_id": r["pair_id"],
                        "pair_type": r["pair_type"], "margin": round(r["margin"], 3)
                    })

    # Pair type failure counts (visible train only)
    trap_fails = defaultdict(int)
    for f in failed_visible:
        trap_fails[f["pair_type"]] += 1

    # Score collapse warnings
    collapse_warns = [f"{s['scorer_id']} spread={s['score_spread']:.3f}"
                      for s in summaries if s["score_spread"] < 0.05]

    # Heldout aggregate (anti-leakage: no raw pairs)
    heldout_by_scorer = {}
    for s in summaries:
        te_rows = [r for r in eval_results.get(s["scorer_id"], []) if r["split"] == "test"]
        if te_rows:
            heldout_by_scorer[s["scorer_id"]] = {
                "accuracy": round(sum(r["correct"] for r in te_rows) / len(te_rows), 3),
                "margin": round(statistics.mean([r["margin"] for r in te_rows]), 3),
                "failures_by_type": dict(defaultdict(int, {
                    r["pair_type"]: sum(1 for x in te_rows if x["pair_type"] == r["pair_type"] and not x["correct"])
                    for r in te_rows
                })),
            }

    # Per-pair-type heldout failure counts (aggregate only, no raw text)
    heldout_fails_by_type = defaultdict(int)
    for sid in top_sids:
        for r in eval_results.get(sid, []):
            if r["split"] == "test" and not r["correct"]:
                heldout_fails_by_type[r["pair_type"]] += 1

    # Generate new mutation instructions -- skip already-applied ones (F8 fix)
    all_possible = []
    if trap_fails.get("fake_mechanism", 0) > 0:
        all_possible.append("Do not reward causal markers unless followed by concrete action/object terms \u2014 detect fake mechanism explicitly.")
    if trap_fails.get("subtle_quality_gap", 0) > 1:
        all_possible.append("Add argument_progression \u00d7 real_mechanism_quality product scorer \u2014 surface vs argument distinction.")
    if trap_fails.get("hype_trap", 0) > 0:
        all_possible.append("Ensure persuasion_risk veto fires before continuity weighting reduces score to non-zero.")
    if any(s["score_spread"] < 0.1 for s in pareto):
        all_possible.append("Loosen source continuity floor \u2014 soft gate may be squashing spread on legitimate rephrases.")
    all_possible.append("Recombine best scorer structures: try argument_progression * real_mechanism_quality as primary signal.")

    # Separate mutation (scorer) vs adversarial (pair) instructions
    mutation_instructions = [i for i in all_possible if i not in prior]
    applied_from_prior = [i for i in all_possible if i in prior]

    adversarial_pair_instructions = [
        "Generate fake_mechanism pairs where BOTH use 'by' but only positive names a concrete object/step.",
        "Generate subtle_quality_gap pairs where both have before/after framing but only positive has a result clause.",
        "Generate hype_trap pairs where negative mimics professional language but hides superlative density.",
    ]

    return {
        "round_idx": round_idx,
        "top_scorers": [{
            "scorer_id": s["scorer_id"],
            "hypothesis": s["hypothesis"][:80],
            "lineage": s["lineage"],
            "test_accuracy": s["test_accuracy"],
            "test_margin": s["test_margin"],
            "robustness_warning": s.get("robustness_warning", ""),
            "survived_because": s.get("survived_because", ""),
            "code": scorer_code.get(s["scorer_id"], ""),
        } for s in pareto[:3]],
        "failed_visible_pairs": failed_visible[:8],
        "low_margin_visible_pairs": low_margin_visible[:6],
        "failed_pair_type_counts": dict(trap_fails),
        "score_collapse_warnings": collapse_warns,
        "heldout_aggregate_only": {
            "heldout_accuracy_by_scorer": {sid: v["accuracy"] for sid, v in heldout_by_scorer.items()},
            "heldout_margin_by_scorer": {sid: v["margin"] for sid, v in heldout_by_scorer.items()},
            "heldout_failures_by_pair_type": dict(heldout_fails_by_type),
        },
        "scorer_weakness_summary": f"Top scorers struggle with: {list(trap_fails.keys())}. Collapse warnings: {collapse_warns}.",
        "mutation_instructions": mutation_instructions,
        "adversarial_pair_instructions": adversarial_pair_instructions,
        "applied_from_prior_round": applied_from_prior,
    }
