"""Run the EvalWeaver evolutionary loop on the Radiohead-songwriting taste task.

This does NOT fork the engine. It swaps the *content* pack into the real
evalweaver.evolution module through its existing named hooks (probe registry,
renderer, base pairs, anchors, adversarial templates, validation pairs), then
calls the unmodified run_evolution. If fitness climbs and an evolved scorer
beats single-probe baselines on the frozen heldout, the loop's selection
pressure transfers to a brand-new domain.

Usage:
    python experiments/radiohead/run_radiohead_evolution.py [seed] [generations]
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
from evalweaver import evolution as ev
from evalweaver import scorers as sc
from evalweaver.runner import get_namespace, py_run_scorer
from evalweaver.probes import load_probes  # noqa: F401 (kept for reference)


# ── Radiohead validation pairs (replace business VALIDATION_PAIRS so a
#    Radiohead-good scorer is judged "valid" by separating Radiohead pairs) ──
RH_VALIDATION_PAIRS = [
    {"pair_id": "RVAL_01", "anchor": "I feel alone tonight.",
     "positive": "I feel alone tonight, the fridge hums and the radiator ticks and won't get warm.",
     "negative": "I feel alone tonight, my broken heart cries tears like rain for your sweet embrace."},
    {"pair_id": "RVAL_02", "anchor": "Everything is falling apart.",
     "positive": "Everything is falling apart, the wallpaper peels and the kettle screams in the cold.",
     "negative": "Everything is falling apart, consumed by profound sadness and endless aching pain inside."},
    {"pair_id": "RVAL_03", "anchor": "The city feels cold.",
     "positive": "The city feels cold, concrete and neon and the traffic droning at a stranger's door.",
     "negative": "The city feels cold beneath the crimson moon where my ethereal spirit doth wander golden shores."},
    {"pair_id": "RVAL_04", "anchor": "I keep having the same bad dream.",
     "positive": "Same dream again, the motorway and the static and the kitchen light gone grey.",
     "negative": "I keep having the same bad dream, but the sun will rise and love will set me free forever."},
]


def patch_engine_for_radiohead(hard=False):
    """Rebind every domain-specific symbol the evolution module uses."""
    # 1. Probe alphabet + metadata
    ev.PROBE_CALLS = rh.PROBE_CALLS
    ev.PENALTY_PROBES = rh.PENALTY_PROBES
    ev.REWARD_PROBES = rh.REWARD_PROBES
    ev.PROBE_SEMANTICS = rh.PROBE_SEMANTICS
    ev.GAP_PROBES = rh.GAP_PROBES
    # 2. Genome → code renderer (gates on cliché, not jargon)
    ev.render_scorer_code = rh.render_scorer_code
    # 3. Base pair suite + anchors + adversarial templates
    #    Hard mode: decoupled negatives that also carry concrete nouns, so the
    #    single-probe "count concrete nouns" shortcut can't separate them.
    ev.ALL_PAIRS_R0 = rh.HARD_PAIRS_R0 if hard else rh.ALL_PAIRS_R0
    ev.NEG_CLAUSES = rh.HARD_NEG_CLAUSES if hard else rh.NEG_CLAUSES
    ev.FALLBACK_SOCIAL_POSTS = rh.FALLBACK_SOCIAL_POSTS
    ev.MECH_CLAUSES = rh.MECH_CLAUSES
    ev.RESULT_CLAUSES = rh.RESULT_CLAUSES
    # 4. Probe loader (inject Radiohead probes into the runner namespace)
    ev.load_probes = rh.load_radiohead_probes
    # 5. Scorer validator bound to Radiohead validation pairs
    ev.validate_scorer_on_pairs = partial(
        sc.validate_scorer_on_pairs, validation_pairs=RH_VALIDATION_PAIRS
    )
    # Make probes available immediately (run_evolution also calls ev.load_probes)
    rh.load_radiohead_probes(get_namespace())


# ── Baselines: how much does the evolved composite beat trivial scorers? ──
BASELINE_SCORERS = {
    "concrete_image only":
        "def scorer(text, anchor, params):\n    return _clamp(probe_concrete_image(text))\n",
    "anti-cliché only":
        "def scorer(text, anchor, params):\n    return _clamp(0.5 - probe_cliche_density(text))\n",
    "anti-poeticism only":
        "def scorer(text, anchor, params):\n    return _clamp(0.5 - probe_abstract_poeticism(text))\n",
    "plain_diction only":
        "def scorer(text, anchor, params):\n    return _clamp(probe_plain_diction(text))\n",
    "unease_tone only":
        "def scorer(text, anchor, params):\n    return _clamp(probe_unease_tone(text))\n",
    "naive sensible mix":
        "def scorer(text, anchor, params):\n"
        "    return _clamp(0.4*probe_concrete_image(text) + 0.3*probe_plain_diction(text)\n"
        "                  + 0.3*probe_unease_tone(text) - 0.4*probe_cliche_density(text)\n"
        "                  - 0.4*probe_abstract_poeticism(text))\n",
}


def accuracy_on(code, pairs):
    correct = ties = 0
    for p in pairs:
        pr = py_run_scorer(code, p["positive"], p["anchor"])
        nr = py_run_scorer(code, p["negative"], p["anchor"])
        if not pr["ok"] or not nr["ok"]:
            return None, None
        if pr["value"] > nr["value"]:
            correct += 1
        elif abs(pr["value"] - nr["value"]) < 1e-9:
            ties += 1
    return correct / max(1, len(pairs)), ties


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    generations = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    hard = "--hard" in sys.argv

    out_base = os.path.join(HERE, "outputs_hard" if hard else "outputs")
    os.environ["EVALWEAVER_OUTPUT_DIR"] = out_base
    os.makedirs(out_base, exist_ok=True)

    patch_engine_for_radiohead(hard=hard)
    print(f"[mode: {'HARD (decoupled negatives)' if hard else 'standard'}]")

    config = {
        "goal": "radiohead",
        "seed": seed,
        "n_generations": generations,
        "population_size": 14,
        "n_adv_per_gen": 6,
        "n_adv_candidates": 48,
        "patience": 6,
    }

    print(f"\n=== Radiohead scorer evolution: seed={seed} generations={generations} ===\n")
    result = ev.run_evolution(config)

    out_dir = result["output_dir"]
    with open(os.path.join(out_dir, "evolve_history.json")) as f:
        history = json.load(f)
    with open(os.path.join(out_dir, "evolve_best_scorers.json")) as f:
        best = json.load(f)
    with open(os.path.join(out_dir, "evolve_state.json")) as f:
        state = json.load(f)
    heldout = state.get("suite_test", [])

    print("\n--- Fitness trajectory ---")
    print(f"{'gen':>3} {'pairs':>6} {'heldout':>8} {'pareto':>7} {'best_fit':>9} {'test_acc':>9} {'lineage'}")
    for h in history:
        print(f"{h['generation']:>3} {h['n_pairs']:>6} {h['n_heldout']:>8} {h['pareto_size']:>7} "
              f"{h['best_fitness']:>9} {str(h['best_test_accuracy']):>9} {h.get('best_lineage','')}")

    winner = best[0] if best else {}
    print("\n--- Winning scorer ---")
    print(f"id:        {winner.get('scorer_id')}")
    print(f"lineage:   {winner.get('lineage')}")
    print(f"fitness:   {winner.get('fitness')}")
    print(f"test_acc:  {winner.get('test_accuracy')}  test_margin: {winner.get('test_margin')}")
    print(f"per-trap:  {winner.get('pair_type_accuracy')}")
    print(f"hypothesis: {winner.get('hypothesis')}")
    print("code:")
    print("    " + (winner.get("code", "").replace("\n", "\n    ")))

    print(f"\n--- Baselines vs evolved winner on the {len(heldout)} frozen heldout pairs ---")
    rows = []
    if heldout:
        wacc, wties = accuracy_on(winner.get("code", ""), heldout)
        rows.append(("EVOLVED WINNER", wacc, wties))
        for name, code in BASELINE_SCORERS.items():
            acc, ties = accuracy_on(code, heldout)
            rows.append((name, acc, ties))
        rows.sort(key=lambda r: (-(r[1] or 0)))
        print(f"{'scorer':>22}  {'heldout_acc':>11}  {'ties':>5}")
        for name, acc, ties in rows:
            print(f"{name:>22}  {('%.3f' % acc) if acc is not None else 'ERR':>11}  {ties:>5}")

    print("\n=== done ===")


if __name__ == "__main__":
    main()
