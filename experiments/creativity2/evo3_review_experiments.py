"""Experiments addressing the AAAI review critique.

  fast  : E2 bootstrap CIs on champion separations (heldout + core)
          E3 novelty-threshold sensitivity (archive composition vs |r| cutoff)
          E4 lexical-leakage slice check (margin vs train-vocab overlap)
          E5 external validation on human-masterwork lyric pairs
  sweep : E1 shape-enrichment ablation — with NO seeds and NO LLM, are
          multiplicative/gated compositions over-represented among the
          best-separating random programs? (answers "the product baseline
          seeded the two-factor rediscovery")
"""

import ast
import json
import os
import random
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "creativity")))

from evo3_blind import (gen_prog, prog_str, margins, sep_stats, eval_prog,
                        bundle, maxcorr)  # noqa: E402
from evo2 import compile_metrics  # noqa: E402

HAIKU = json.load(open(os.path.join(HERE, "haiku_state.json")))
SONNET = json.load(open(os.path.join(HERE, "state.json")))
TRAIN, HELDOUT, CORE_IDS = HAIKU["train"], HAIKU["heldout"], HAIKU["core_ids"]
CORE = [p for p in HELDOUT if p["pair_id"] in CORE_IDS]
DISC = json.load(open(os.path.join(HERE, "evo3_discoveries.json")))


def get_scorer(state, sid):
    m = next(x for x in state["population"] if x["id"] == sid)
    return compile_metrics(m["code"], [m["metric_key"]])[m["metric_key"]]


def prog_fn(tree_repr):
    p = ast.literal_eval(tree_repr)
    return lambda t, a: eval_prog(p, t, a)


CHAMPIONS = {
    "haiku champ (variety x rarity gate)": get_scorer(HAIKU, "S_g4_02_structural_diversity_con"),
    "sonnet champ (skeleton x insertion)": get_scorer(SONNET, "S_g2_03_skeleton_preserved_inser"),
    "EVO3 D2 (blind: freshness/word-len)": prog_fn(DISC[1]["tree"]),
    "EVO3 D6 (blind: edit-info alignment)": prog_fn(DISC[5]["tree"]),
}


def pair_margins(fn, pairs):
    return np.array([fn(p["more_creative"], p["anchor"]) - fn(p["less_creative"], p["anchor"])
                     for p in pairs])


def boot_ci(vals, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(vals), size=(n, len(vals)))
    means = vals[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def cmd_fast():
    print("=== E2: bootstrap 95% CIs on SEP (mean margin), 10k resamples ===")
    print(f"{'scorer':>38} {'set':>8} {'SEP':>8} {'95% CI':>20} {'excl. 0?':>8}")
    for name, fn in CHAMPIONS.items():
        for label, pairs in (("heldout", HELDOUT), ("core", CORE)):
            mv = pair_margins(fn, pairs)
            lo, hi = boot_ci(mv)
            print(f"{name:>38} {label:>8} {mv.mean():>8.3f} "
                  f"[{lo:>7.3f}, {hi:>7.3f}]   {'YES' if lo > 0 else 'no':>8}")

    print("\n=== E3: novelty-threshold sensitivity (EVO3 archive vs |r| cutoff) ===")
    incumbents = []
    for m in HAIKU["population"]:
        fn = compile_metrics(m["code"], [m["metric_key"]])[m["metric_key"]]
        incumbents.append(pair_margins(fn, TRAIN))
    progs = [(d["program"], ast.literal_eval(d["tree"])) for d in DISC]
    mvs = [(s, margins(p, TRAIN)) for s, p in progs]
    print(f"{'threshold':>10} {'archive size (of 6)':>20}  members")
    for th in (0.4, 0.5, 0.6, 0.7, 0.8):
        fps = list(incumbents)
        kept = []
        for s, mv in mvs:
            if maxcorr(mv, fps) < th:
                kept.append(s.split('(')[0][:14])
                fps.append(mv)
        print(f"{th:>10} {len(kept):>20}  {kept}")

    print("\n=== E4: lexical-leakage slice check (heldout margin vs train-vocab overlap) ===")
    W = re.compile(r"[a-zA-Z']+")
    train_vocab = set(w for p in TRAIN for t in (p["anchor"], p["more_creative"], p["less_creative"])
                      for w in W.findall(t.lower()))
    overlaps = []
    for p in HELDOUT:
        toks = set(W.findall((p["more_creative"] + " " + p["less_creative"]).lower()))
        overlaps.append(len(toks & train_vocab) / max(1, len(toks)))
    overlaps = np.array(overlaps)
    print(f"  heldout overlap with train vocab: mean={overlaps.mean():.2f} range=[{overlaps.min():.2f},{overlaps.max():.2f}]")
    for name, fn in CHAMPIONS.items():
        mv = pair_margins(fn, HELDOUT)
        r = float(np.corrcoef(overlaps, mv)[0, 1])
        print(f"  corr(margin, vocab-overlap) {name:>38}: r={r:+.2f}  "
              f"{'(no leakage gradient)' if abs(r) < 0.25 else '(INVESTIGATE)'}")

    print("\n=== E5: external validation — acclaimed lyric lines vs flattened paraphrases ===")
    lyric_pairs = [
        {"anchor": "everything is broken but some good still comes through",
         "more_creative": "there is a crack in everything, that's how the light gets in",
         "less_creative": "everything is broken but that lets some good in"},
        {"anchor": "you can see how tired she looks",
         "more_creative": "the ghost of electricity howls in the bones of her face",
         "less_creative": "you can see how tired she looks"},
        {"anchor": "everything is calm and settled now",
         "more_creative": "everything in its right place",
         "less_creative": "everything is fine and calm now"},
        {"anchor": "you cause your own pain and that is the worst part",
         "more_creative": "you do it to yourself, and that's what really hurts",
         "less_creative": "you cause your own pain and that is the worst part"},
        {"anchor": "I have seen this from different perspectives",
         "more_creative": "I've looked at clouds from both sides now",
         "less_creative": "I have seen this from different perspectives"},
        {"anchor": "I am not the drunk one, blame the music",
         "more_creative": "the piano has been drinking, not me",
         "less_creative": "I am not the drunk one, blame the music"},
    ]
    for p in lyric_pairs:
        p["pair_id"] = "LY"
    print(f"{'scorer':>38} {'picks masterwork':>18}")
    for name, fn in CHAMPIONS.items():
        c = sum(1 for p in lyric_pairs
                if fn(p["more_creative"], p["anchor"]) > fn(p["less_creative"], p["anchor"]) + 1e-12)
        print(f"{name:>38} {c:>12}/6")


def cmd_sweep(seed=11, n=12000):
    print(f"=== E1: shape-enrichment ablation (seed={seed}, n={n}, NO seeds, NO LLM) ===")
    rng = random.Random(seed)
    for p in TRAIN:
        bundle(p["more_creative"], p["anchor"])
        bundle(p["less_creative"], p["anchor"])
        bundle(p["anchor"], p["anchor"])

    def shapes(p):
        s = prog_str(p)
        return {"multiplicative": ("gate(" in s or "prod(" in s),
                "ratio": "ratio(" in s,
                "anchor_relative": "Δanchor" in s}

    rows = []
    seen = set()
    i = 0
    while len(rows) < n and i < n * 3:
        i += 1
        p = gen_prog(rng)
        s = prog_str(p)
        if s in seen:
            continue
        seen.add(s)
        mv = margins(p, TRAIN)
        if mv is None or np.std(mv) < 1e-9:
            continue
        st = sep_stats(p, TRAIN)
        rows.append((st["SEP_std"], shapes(p)))
    seps = np.array([r[0] for r in rows])
    top = seps >= np.percentile(seps, 95)
    print(f"valid programs: {len(rows)}; top-5% cutoff SEP_std={np.percentile(seps,95):.3f}")
    print(f"{'shape':>18} {'base rate':>10} {'top-5% rate':>12} {'enrichment':>11}")
    for key in ("multiplicative", "ratio", "anchor_relative"):
        base = np.mean([r[1][key] for r in rows])
        toprate = np.mean([r[1][key] for r, t in zip(rows, top) if t])
        print(f"{key:>18} {base:>10.3f} {toprate:>12.3f} {toprate/max(base,1e-9):>10.2f}x")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "fast"
    if mode == "fast":
        cmd_fast()
    else:
        cmd_sweep(seed=int(sys.argv[2]) if len(sys.argv) > 2 else 11,
                  n=int(sys.argv[3]) if len(sys.argv) > 3 else 12000)
