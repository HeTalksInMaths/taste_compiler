"""Phase 7 — merge best separators + test on the adversarial heldout.

Three parts:
  (A) Show the phase-5 winner (S3) on the adversarial set — does it collapse?
  (B) Scorer-level merges (ensemble mean, majority vote) of the best separators.
  (C) Feature-level: per-feature more>less accuracy on original vs adversarial,
      then a low-capacity subset search (equal-weight sum of z-scored features,
      signs fixed by theory) selected on the adversarial set and reported with
      leave-one-out CV so a 12-pair set cannot manufacture an overfit win.

Honest question: once the cliché cue is decoupled, does ANY stdlib signal still
separate more_creative from less_creative?
"""

import json
import os
import sys
import itertools
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from evalweaver.runner import py_run_scorer            # noqa: E402
from creativity_probes import FEATURES                 # noqa: E402


def load(name):
    return json.load(open(os.path.join(HERE, name)))


def acc_scorer(code, pairs):
    """more>less accuracy for a runnable scorer."""
    c = t = 0
    for p in pairs:
        m = py_run_scorer(code, p["more_creative"], p["anchor"])
        l = py_run_scorer(code, p["less_creative"], p["anchor"])
        if not (m["ok"] and l["ok"]):
            continue
        if m["value"] > l["value"] + 1e-9:
            c += 1
        elif abs(m["value"] - l["value"]) < 1e-9:
            t += 1
    return c / len(pairs), t


def feat_values(pairs, which):
    """Return list of (more_val, less_val) for feature `which` over pairs."""
    fn, _ = FEATURES[which]
    out = []
    for p in pairs:
        out.append((fn(p["more_creative"], p["anchor"]), fn(p["less_creative"], p["anchor"])))
    return out


def feat_acc(pairs, which):
    vals = feat_values(pairs, which)
    sign = FEATURES[which][1]
    c = t = 0
    for m, l in vals:
        d = sign * (m - l)
        if d > 1e-9:
            c += 1
        elif abs(d) < 1e-9:
            t += 1
    return c / len(pairs), t


def zstats(pairs, which):
    vals = feat_values(pairs, which)
    pool = [v for pair in vals for v in pair]
    mu = statistics.mean(pool)
    sd = statistics.pstdev(pool) or 1e-9
    return mu, sd


def subset_score(pairs, subset, zparams):
    """Equal-weight sum of z-scored, sign-corrected features; accuracy more>less."""
    per_feat = {w: feat_values(pairs, w) for w in subset}
    c = 0
    for i in range(len(pairs)):
        sm = sl = 0.0
        for w in subset:
            mu, sd = zparams[w]
            sign = FEATURES[w][1]
            m, l = per_feat[w][i]
            sm += sign * (m - mu) / sd
            sl += sign * (l - mu) / sd
        if sm > sl + 1e-12:
            c += 1
    return c / len(pairs)


def subset_loo(pairs, subset):
    """Leave-one-out accuracy: z-stats fit on the other pairs' pooled values."""
    correct = 0
    for held in range(len(pairs)):
        train = [pairs[i] for i in range(len(pairs)) if i != held]
        zp = {w: zstats(train, w) for w in subset}
        sm = sl = 0.0
        for w in subset:
            fn, sign = FEATURES[w][0], FEATURES[w][1]
            mu, sd = zp[w]
            m = fn(pairs[held]["more_creative"], pairs[held]["anchor"])
            l = fn(pairs[held]["less_creative"], pairs[held]["anchor"])
            sm += sign * (m - mu) / sd
            sl += sign * (l - mu) / sd
        if sm > sl + 1e-12:
            correct += 1
    return correct / len(pairs)


def main():
    scorers = {s["scorer_id"]: s for s in load("scorers.json")}
    orig = load("eval_pairs.json")
    adv = load("adversarial_pairs.json")

    print("\n=== PHASE 7: merge + adversarial heldout ===")
    print(f"original pairs: {len(orig)}   adversarial (S3-stumping) pairs: {len(adv)}\n")

    # ── (A) the phase-5 winner on both sets ──
    print("--- (A) scorers: original vs adversarial (more>less accuracy) ---")
    print(f"{'scorer':>28} {'orig':>6} {'adv':>6}  {'adv_ties':>8}")
    scorer_adv = {}
    for sid, s in scorers.items():
        o, _ = acc_scorer(s["code"], orig)
        a, at = acc_scorer(s["code"], adv)
        scorer_adv[sid] = a
        print(f"{sid:>28} {o:>6.3f} {a:>6.3f}  {at:>8}")

    # ── (B) scorer-level merges of the best separators ──
    print("\n--- (B) scorer-level merges (best separators by original accuracy) ---")
    ranked = sorted(scorers, key=lambda sid: -acc_scorer(scorers[sid]["code"], orig)[0])
    for k in (2, 3):
        top = ranked[:k]
        # mean-of-normalized ensemble
        def ens_acc(pairs):
            c = 0
            for p in pairs:
                sm = sl = 0.0
                for sid in top:
                    m = py_run_scorer(scorers[sid]["code"], p["more_creative"], p["anchor"])["value"]
                    l = py_run_scorer(scorers[sid]["code"], p["less_creative"], p["anchor"])["value"]
                    sm += m
                    sl += l
                if sm > sl + 1e-9:
                    c += 1
            return c / len(pairs)
        print(f"  ensemble top-{k} {top}: orig={ens_acc(orig):.3f} adv={ens_acc(adv):.3f}")

    # ── (C) per-feature diagnostic ──
    print("\n--- (C) per-feature more>less accuracy: original vs adversarial ---")
    print(f"{'feature':>20} {'orig':>6} {'adv':>6} {'adv_ties':>9}")
    feat_rows = []
    for w in FEATURES:
        o, _ = feat_acc(orig, w)
        a, at = feat_acc(adv, w)
        feat_rows.append((w, o, a, at))
    for w, o, a, at in sorted(feat_rows, key=lambda r: -r[2]):
        print(f"{w:>20} {o:>6.3f} {a:>6.3f} {at:>9}")

    # ── (C) constrained subset search on the adversarial set ──
    print("\n--- (C) subset search on adversarial (equal-weight z-sum, signs fixed by theory) ---")
    zp_adv = {w: zstats(adv, w) for w in FEATURES}
    feats = list(FEATURES)
    best = []
    for r in range(1, 5):  # cap subset size at 4 to limit capacity
        for subset in itertools.combinations(feats, r):
            sc = subset_score(adv, subset, zp_adv)
            best.append((sc, subset))
    best.sort(key=lambda x: (-x[0], len(x[1])))
    print("  top subsets by in-sample adversarial accuracy (then fewest features):")
    seen_sizes = set()
    shown = 0
    for sc, subset in best:
        if shown >= 6:
            break
        loo = subset_loo(adv, subset)
        orig_sc = subset_score(orig, subset, {w: zstats(orig, w) for w in subset})
        print(f"    adv={sc:.3f}  LOO_adv={loo:.3f}  orig={orig_sc:.3f}  {subset}")
        shown += 1

    # Best single feature honesty check
    best_single = max(feat_rows, key=lambda r: r[2])
    print(f"\n  best SINGLE feature on adversarial: {best_single[0]} = {best_single[2]:.3f}")

    # ── save ──
    results = {
        "n_original": len(orig), "n_adversarial": len(adv),
        "scorers_original_vs_adversarial": {
            sid: {"orig": round(acc_scorer(scorers[sid]["code"], orig)[0], 3),
                  "adv": round(scorer_adv[sid], 3)} for sid in scorers},
        "per_feature": {w: {"orig": round(o, 3), "adv": round(a, 3), "adv_ties": at}
                        for w, o, a, at in feat_rows},
        "top_subsets_adversarial": [
            {"features": list(sub), "adv_insample": round(sc, 3),
             "adv_loo": round(subset_loo(adv, sub), 3),
             "orig": round(subset_score(orig, sub, {w: zstats(orig, w) for w in sub}), 3)}
            for sc, sub in best[:8]],
    }
    out = os.path.join(HERE, "merge_results.json")
    json.dump(results, open(out, "w"), indent=1)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
