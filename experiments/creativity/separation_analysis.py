"""Phase-5 separation analysis for the creativity-scorer-discovery experiment.

Runs each proposed scorer on all internet-sourced pairs. Because each pair has
THREE versions (less_creative < anchor < more_creative in intended freshness),
we measure two orderings per scorer:
  - more>less  : the primary separation (does the scorer rank the creative edit above the flat one?)
  - monotonic  : strict more>anchor>less (the harder, ordinal test)

Reports accuracy, mean/median margin, spread, ties, worst pairs, and
cross-scorer agreement. Writes separation_results.json. STOPS here — no
evolution or adversarial pair growth (out of scope for this skill).
"""

import json
import os
import sys
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from evalweaver.runner import py_run_scorer  # noqa: E402


def main():
    scorers = json.load(open(os.path.join(HERE, "scorers.json")))
    pairs = json.load(open(os.path.join(HERE, "eval_pairs.json")))

    results = {}
    per_pair_scores = {p["pair_id"]: {} for p in pairs}

    for s in scorers:
        sid, code = s["scorer_id"], s["code"]
        more_gt_less = 0
        monotonic = 0
        margins = []          # more - less
        all_vals = []
        ties = 0
        worst = []            # pairs where more <= less
        for p in pairs:
            a = p["anchor"]
            v_more = py_run_scorer(code, p["more_creative"], a)
            v_anch = py_run_scorer(code, a, a)
            v_less = py_run_scorer(code, p["less_creative"], a)
            if not (v_more["ok"] and v_anch["ok"] and v_less["ok"]):
                continue
            m, n, l = v_more["value"], v_anch["value"], v_less["value"]
            per_pair_scores[p["pair_id"]][sid] = {"more": round(m, 3), "anchor": round(n, 3), "less": round(l, 3)}
            all_vals += [m, n, l]
            margins.append(m - l)
            if m > l + 1e-9:
                more_gt_less += 1
            elif abs(m - l) < 1e-9:
                ties += 1
            else:
                worst.append((p["pair_id"], round(m, 3), round(l, 3)))
            if m > n + 1e-9 and n > l + 1e-9:
                monotonic += 1
        npairs = len(pairs)
        results[sid] = {
            "hypothesis": s["hypothesis"][:140] + "...",
            "graph_nodes_used": s["graph_nodes_used"],
            "accuracy_more_gt_less": round(more_gt_less / npairs, 3),
            "accuracy_monotonic": round(monotonic / npairs, 3),
            "ties": ties,
            "mean_margin": round(statistics.mean(margins), 4),
            "median_margin": round(statistics.median(margins), 4),
            "margin_std": round(statistics.pstdev(margins), 4),
            "score_spread": round(max(all_vals) - min(all_vals), 3),
            "worst_pairs_more_le_less": worst[:6],
        }

    # Cross-scorer agreement: fraction of pairs where scorers agree on more>less direction
    sids = [s["scorer_id"] for s in scorers]
    dirs = {sid: [] for sid in sids}
    for p in pairs:
        for sid in sids:
            sc = per_pair_scores[p["pair_id"]].get(sid)
            dirs[sid].append(1 if sc and sc["more"] > sc["less"] else 0)
    agreement = {}
    for i in range(len(sids)):
        for j in range(i + 1, len(sids)):
            a, b = sids[i], sids[j]
            same = sum(1 for x, y in zip(dirs[a], dirs[b]) if x == y) / len(pairs)
            agreement[f"{a} vs {b}"] = round(same, 3)

    # Simple ensemble: majority vote and mean-z across scorers on more vs less
    ensemble_correct = 0
    for p in pairs:
        votes = sum(dirs[sid][pairs.index(p)] for sid in sids)
        if votes > len(sids) / 2:
            ensemble_correct += 1
    results["_ensemble_majority_vote"] = {"accuracy_more_gt_less": round(ensemble_correct / len(pairs), 3)}
    results["_cross_scorer_agreement"] = agreement
    results["_n_pairs"] = len(pairs)

    out = os.path.join(HERE, "separation_results.json")
    json.dump({"per_scorer": results, "per_pair_scores": per_pair_scores}, open(out, "w"), indent=1)

    # ── Console report ──
    print(f"\n=== Creativity scorer separation — {len(pairs)} internet-sourced pairs ===\n")
    print(f"{'scorer':>28} {'more>less':>9} {'monotonic':>9} {'ties':>5} {'meanMrg':>8} {'spread':>7}")
    ranked = sorted([s for s in results if not s.startswith("_")],
                    key=lambda k: -results[k]["accuracy_more_gt_less"])
    for sid in ranked:
        r = results[sid]
        print(f"{sid:>28} {r['accuracy_more_gt_less']:>9.3f} {r['accuracy_monotonic']:>9.3f} "
              f"{r['ties']:>5} {r['mean_margin']:>8.4f} {r['score_spread']:>7.3f}")
    print(f"{'ENSEMBLE (majority vote)':>28} {results['_ensemble_majority_vote']['accuracy_more_gt_less']:>9.3f}")
    print("\n--- cross-scorer agreement (fraction of pairs same more>less call) ---")
    for k, v in agreement.items():
        print(f"  {k:>52}: {v}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
