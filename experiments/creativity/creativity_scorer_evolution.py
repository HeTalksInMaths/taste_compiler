"""Simple scorer evolution tracked by separation on a growing adversarial set.

Deliberately minimal — the ONLY moving parts are:
  1. the 5 proposed scorers (S1..S5) as the building blocks,
  2. mutations/merges of them: a genome is a weight vector over the 5 scorers;
     a blended scorer scores a text as the weighted average of the 5 base
     scorer outputs. mutation = jitter the weights; merge = average two genomes.
  3. a growing adversarial set: each generation we add the adversarial pairs the
     current best scorer separates WORST (lowest margin) — growing the eval set
     to stump the current best.

No new features/probes are introduced. Selection is by separation accuracy
(more_creative > less_creative) on the current eval set. We report, per
generation: eval-set size, the best scorer and its separation (overall, and
split into original vs the adversarial pairs added so far), and the population
mean — so we can see whether mutation/merge improves separation as the
adversarial set grows.

Run: python experiments/creativity/creativity_scorer_evolution.py [seed] [gens]
"""

import json
import os
import sys
import random

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from evalweaver.runner import py_run_scorer  # noqa: E402

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 7
N_GENS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
ADV_PER_GEN = 3
POP_SIZE = 12


def load(name):
    return json.load(open(os.path.join(HERE, name)))


def precompute(scorers, pairs):
    """base[pair_id][scorer_idx] = (more, less) base scorer values."""
    base = {}
    for p in pairs:
        row = []
        for s in scorers:
            m = py_run_scorer(s["code"], p["more_creative"], p["anchor"])["value"]
            l = py_run_scorer(s["code"], p["less_creative"], p["anchor"])["value"]
            row.append((m, l))
        base[p["pair_id"]] = row
    return base


def blended(genome, row):
    """(more, less) blended score for a genome given a pair's base row."""
    tot = sum(genome) or 1.0
    more = sum(w * row[i][0] for i, w in enumerate(genome)) / tot
    less = sum(w * row[i][1] for i, w in enumerate(genome)) / tot
    return more, less


def separation(genome, base, pair_ids):
    """accuracy (more>less) and mean margin on the given pairs."""
    if not pair_ids:
        return 0.0, 0.0
    correct = 0
    margin = 0.0
    for pid in pair_ids:
        m, l = blended(genome, base[pid])
        if m > l + 1e-9:
            correct += 1
        margin += (m - l)
    return correct / len(pair_ids), margin / len(pair_ids)


def mutate(genome, rng):
    g = [max(0.0, w + rng.uniform(-0.3, 0.3)) for w in genome]
    if sum(g) < 1e-6:
        g[rng.randrange(len(g))] = 1.0
    return g


def merge(ga, gb):
    return [(a + b) / 2.0 for a, b in zip(ga, gb)]


def main():
    rng = random.Random(SEED)
    scorers = load("scorers.json")
    sids = [s["scorer_id"] for s in scorers]
    orig = load("eval_pairs.json")
    adv_pool = load("adversarial_pairs.json")

    base = precompute(scorers, orig + adv_pool)
    orig_ids = [p["pair_id"] for p in orig]
    adv_ids_all = [p["pair_id"] for p in adv_pool]

    # ── Starting scorers: how each of the 5 does on the original set ──
    print(f"\n=== starting scorers on the {len(orig)} original pairs (separation) ===")
    unit = [[1.0 if i == j else 0.0 for j in range(len(sids))] for i in range(len(sids))]
    for i, sid in enumerate(sids):
        acc, mrg = separation(unit[i], base, orig_ids)
        print(f"  {sid:>28}: acc={acc:.3f}  mean_margin={mrg:+.4f}")

    # ── Population: the 5 pure scorers + random blends ──
    pop = [list(u) for u in unit]
    while len(pop) < POP_SIZE:
        pop.append([rng.random() for _ in range(len(sids))])

    used_adv = []      # adversarial pair_ids added so far
    remaining = list(adv_ids_all)
    history = []

    print(f"\n=== evolution: mutate/merge blends of the 5 scorers, grow adversarial each gen ===")
    print(f"{'gen':>3} {'pairs':>6} {'best_all':>8} {'best_orig':>9} {'best_adv':>8} {'popmean':>8}  best_blend")
    for gen in range(N_GENS):
        cur_ids = orig_ids + used_adv
        # evaluate & rank population by separation on the current eval set
        scored = []
        for g in pop:
            acc, mrg = separation(g, base, cur_ids)
            scored.append((acc, mrg, g))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best_acc, best_mrg, best_g = scored[0]

        acc_orig, _ = separation(best_g, base, orig_ids)
        acc_adv, _ = separation(best_g, base, used_adv) if used_adv else (float("nan"), 0)
        popmean = sum(s[0] for s in scored) / len(scored)

        # readable blend: weights normalized, only terms > 0.1
        tot = sum(best_g) or 1.0
        wnorm = [w / tot for w in best_g]
        blend_str = " + ".join(f"{wnorm[i]:.2f}*{sids[i].split('_')[0]}"
                               for i in range(len(sids)) if wnorm[i] > 0.1)
        adv_disp = f"{acc_adv:.3f}" if used_adv else "  -  "
        print(f"{gen:>3} {len(cur_ids):>6} {best_acc:>8.3f} {acc_orig:>9.3f} {adv_disp:>8} {popmean:>8.3f}  {blend_str}")
        history.append({"gen": gen, "n_pairs": len(cur_ids), "best_all": round(best_acc, 3),
                        "best_orig": round(acc_orig, 3),
                        "best_adv": (round(acc_adv, 3) if used_adv else None),
                        "pop_mean": round(popmean, 3), "best_blend": blend_str,
                        "n_adv_added": len(used_adv)})

        # ── grow adversarial: add the pairs the current best separates WORST ──
        if remaining:
            ranked_adv = sorted(remaining, key=lambda pid: blended(best_g, base[pid])[0]
                                - blended(best_g, base[pid])[1])
            add = ranked_adv[:ADV_PER_GEN]
            used_adv += add
            remaining = [pid for pid in remaining if pid not in add]

        # ── breed: elitism + mutations + merges ──
        elites = [s[2] for s in scored[:4]]
        newpop = [list(e) for e in elites]
        while len(newpop) < POP_SIZE:
            r = rng.random()
            if r < 0.6:
                newpop.append(mutate(rng.choice(elites), rng))
            else:
                a, b = rng.sample(elites, 2)
                newpop.append(merge(a, b))
        pop = newpop

    # final: best on the full grown set
    out = os.path.join(HERE, "evolution_results.json")
    json.dump({"seed": SEED, "generations": history,
               "n_adversarial_total": len(adv_ids_all)}, open(out, "w"), indent=1)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
