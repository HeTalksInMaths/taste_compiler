"""Goodhart / decoupling test for the Radiohead scorers.

In-distribution, the traps are lexically separable by a single probe
(concrete_image alone ties the evolved winner). This harness asks the real
question: when the easy signal is DECOUPLED — negatives that carry MORE
concrete nouns than the positive but are cliché/poeticism/uplift-stuffed —
does the evolved composite still rank positive > negative, where the trivial
baseline cannot? That is the test of whether evolutionary fitness is guiding
toward the taste, or just toward "count concrete nouns."
"""

import json
import os
import sys
from functools import partial

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import radiohead_pack as rh
from evalweaver.runner import get_namespace, py_run_scorer

rh.load_radiohead_probes(get_namespace())

# HARD pairs: negative has >= concrete nouns as positive, but stuffs the trap.
# (concrete_image-only will mis-rank these; a cliché/poeticism-aware scorer won't.)
HARD_PAIRS = [
    {"anchor": "I feel alone tonight.",
     "positive": "the radiator ticks and my hands won't warm up",
     "negative": "the radiator ticks and the streetlight glows and the rain falls as my broken heart bleeds for your sweet embrace"},
    {"anchor": "Everything is falling apart.",
     "positive": "the wallpaper peels and the kettle screams",
     "negative": "the wallpaper peels and the window glows and the candle flickers while true love lifts my soul to forever"},
    {"anchor": "I can't sleep.",
     "positive": "the boiler clicks and the ceiling cracks won't hold still",
     "negative": "the boiler clicks and the moon glows and the curtains drift as tears like rain fall from my aching heart"},
    {"anchor": "The city feels cold.",
     "positive": "concrete and neon and the traffic droning",
     "negative": "concrete and neon and the river and the bridge where my ethereal spirit doth wander golden shores of longing"},
    {"anchor": "I walk home in the rain.",
     "positive": "wet pavement and a dead streetlight and the gutter choking",
     "negative": "wet pavement and a streetlight and a fountain glowing as my tender soul drifts on shimmering wings of grace"},
    {"anchor": "I keep having the same bad dream.",
     "positive": "the motorway and the static and the kitchen light gone grey",
     "negative": "the motorway and the harbour and the garden bloom, but the sun will rise and love will set me free forever"},
    {"anchor": "I don't recognise myself.",
     "positive": "thin in the glass with somebody else's hands",
     "negative": "thin in the glass beside the roses and the candlelight, my beautiful heart still dreams of sweet eternal love"},
    {"anchor": "I feel numb.",
     "positive": "cars hiss past on the wet road and the television talks to no one",
     "negative": "cars hiss past the meadow and the willow and the stream, yet every breath I take is a prayer to fly away"},
]


def rank_acc(code, pairs):
    correct = ties = 0
    detail = []
    for p in pairs:
        pr = py_run_scorer(code, p["positive"], p["anchor"])["value"]
        nr = py_run_scorer(code, p["negative"], p["anchor"])["value"]
        if pr > nr + 1e-9:
            correct += 1
        elif abs(pr - nr) < 1e-9:
            ties += 1
        detail.append((round(pr, 3), round(nr, 3)))
    return correct / len(pairs), ties, detail


BASELINES = {
    "concrete_image only":
        "def scorer(text, anchor, params):\n    return _clamp(probe_concrete_image(text))\n",
    "unease_tone only":
        "def scorer(text, anchor, params):\n    return _clamp(probe_unease_tone(text))\n",
    "anti-cliché only":
        "def scorer(text, anchor, params):\n    return _clamp(0.5 - probe_cliche_density(text))\n",
    "anti-poeticism only":
        "def scorer(text, anchor, params):\n    return _clamp(0.5 - probe_abstract_poeticism(text))\n",
    "naive sensible mix":
        "def scorer(text, anchor, params):\n"
        "    return _clamp(0.4*probe_concrete_image(text) + 0.3*probe_plain_diction(text)\n"
        "                  + 0.3*probe_unease_tone(text) - 0.4*probe_cliche_density(text)\n"
        "                  - 0.4*probe_abstract_poeticism(text))\n",
}


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    out_dir = os.path.join(HERE, "outputs", f"evolve_radiohead_seed{seed}")
    with open(os.path.join(out_dir, "evolve_best_scorers.json")) as f:
        best = json.load(f)
    winner = best[0]

    print(f"\n=== Hard decoupled (Goodhart) test — {len(HARD_PAIRS)} pairs, negative has >= concrete nouns ===\n")
    rows = []
    wacc, wties, _ = rank_acc(winner["code"], HARD_PAIRS)
    rows.append((f"EVOLVED WINNER ({winner['scorer_id']})", wacc, wties))
    for name, code in BASELINES.items():
        acc, ties, _ = rank_acc(code, HARD_PAIRS)
        rows.append((name, acc, ties))
    rows.sort(key=lambda r: -r[1])
    print(f"{'scorer':>34}  {'hard_acc':>8}  {'ties':>5}")
    for name, acc, ties in rows:
        print(f"{name:>34}  {acc:>8.3f}  {ties:>5}")
    print()


if __name__ == "__main__":
    main()
