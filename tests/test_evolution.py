"""Tests for the multi-generation evolutionary scorer-discovery loop."""

import json
import os
import random

import pytest

from evalweaver.runner import get_namespace
from evalweaver.probes import load_probes
from evalweaver.policy import validate_pair_source_policy
from evalweaver.scorers import validate_scorer_on_pairs
from evalweaver.evolution import (
    FALLBACK_SOCIAL_POSTS,
    GAP_PROBES,
    PENALTY_PROBES,
    PROBE_CALLS,
    crossover_genomes,
    genome_hypothesis,
    mutate_genome,
    random_genome,
    render_scorer_code,
    run_evolution,
    select_adversarial_pairs,
    synthesize_candidate_pairs,
)


@pytest.fixture(autouse=True)
def _probes_loaded():
    load_probes(get_namespace())


def _anchors():
    return [{"anchor": p, "url": "", "source": "fallback_bank"} for p in FALLBACK_SOCIAL_POSTS]


# ─────────────────────────────────────────────────────────────────────
# Genome → code
# ─────────────────────────────────────────────────────────────────────

def test_random_genome_renders_valid_scorer():
    rng = random.Random(0)
    for _ in range(20):
        genome = random_genome(rng)
        code = render_scorer_code(genome)
        assert "def scorer(text, anchor, params):" in code
        result = validate_scorer_on_pairs(code)
        # Every rendered genome must at least execute without errors
        assert result["reason"] != "runtime_error", result

def test_mutation_and_crossover_render_valid_scorers():
    rng = random.Random(1)
    a, b = random_genome(rng), random_genome(rng)
    for genome in [mutate_genome(a, rng), mutate_genome(a, rng, GAP_PROBES["fake_mechanism"]),
                   crossover_genomes(a, b, rng)]:
        result = validate_scorer_on_pairs(render_scorer_code(genome))
        assert result["reason"] != "runtime_error", result
        assert len(genome["terms"]) >= 1


def test_genome_hypothesis_is_interpretable():
    rng = random.Random(2)
    genome = random_genome(rng)
    hyp = genome_hypothesis(genome)
    for term in genome["terms"]:
        assert term["probe"] in hyp
    assert "hard policy veto" in hyp


def test_penalty_probes_rendered_with_negative_sign():
    genome = {
        "terms": [{"probe": "argument_progression", "weight": 0.5},
                  {"probe": "persuasion_risk", "weight": 0.3}],
        "jargon_gate": None, "product": None, "product_weight": 0.0,
        "continuity_blend": 0.0,
    }
    code = render_scorer_code(genome)
    assert "base += 0.50 * probe_argument_progression(text)" in code
    assert "base -= 0.30 * probe_persuasion_risk(text)" in code


def test_gap_probes_cover_known_pair_types_and_registry():
    for ptype, probes in GAP_PROBES.items():
        for p in probes:
            assert p in PROBE_CALLS, f"{ptype} references unknown probe {p}"
    assert PENALTY_PROBES <= set(PROBE_CALLS)


# ─────────────────────────────────────────────────────────────────────
# Adversarial pair synthesis
# ─────────────────────────────────────────────────────────────────────

def test_synthesized_pairs_pass_source_policy():
    rng = random.Random(3)
    pairs = synthesize_candidate_pairs(_anchors(), {}, rng, 30)
    assert len(pairs) >= 20
    for p in pairs:
        check = validate_pair_source_policy({**p, "pair_id": "X"})
        assert check["valid"], (p["positive"], check["errors"])


def test_adversarial_selection_picks_lowest_frontier_margin():
    rng = random.Random(4)
    pairs = synthesize_candidate_pairs(_anchors(), {"fake_mechanism": 3}, rng, 30)
    frontier_code = {"S_x": render_scorer_code(random_genome(rng))}
    selected = select_adversarial_pairs(pairs, frontier_code, 1, 6, rng)
    assert len(selected) == 6
    margins = [p["frontier_margin_at_creation"] for p in selected]
    assert margins == sorted(margins)
    # heldout pairs are produced (every 3rd selected)
    assert any(p["pair_id"].startswith("G1_T") for p in selected)
    assert any(p["pair_id"].startswith("G1_A") for p in selected)
    for p in selected:
        assert p["attacks_scorer_ids"] == ["S_x"]


# ─────────────────────────────────────────────────────────────────────
# Full loop
# ─────────────────────────────────────────────────────────────────────

def _small_config(tmp_path, **overrides):
    cfg = {
        "goal": "persuasive",
        "seed": 11,
        "n_generations": 3,
        "population_size": 8,
        "n_adv_per_gen": 4,
        "n_adv_candidates": 24,
        "use_exa_search": False,
    }
    cfg.update(overrides)
    return cfg


def test_run_evolution_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALWEAVER_OUTPUT_DIR", str(tmp_path))
    result = run_evolution(_small_config(tmp_path))
    assert result["success"]
    assert result["generations_run"] == 3
    out = result["output_dir"]

    history = json.load(open(os.path.join(out, "evolve_history.json")))
    assert len(history) == 3
    # pair suite must grow across generations (adversarial pairs added)
    assert history[-1]["n_pairs"] > history[0]["n_pairs"]
    assert history[-1]["n_heldout"] >= history[0]["n_heldout"]

    best = json.load(open(os.path.join(out, "evolve_best_scorers.json")))
    assert best and best[0]["code"].startswith("def scorer")
    assert best[0]["test_accuracy"] >= 0.5
    assert "·" in best[0]["hypothesis"]  # interpretable weighted-blend description

    for gen in range(3):
        for name in (f"gen{gen:02d}_summaries", f"gen{gen:02d}_pareto", f"gen{gen:02d}_population"):
            assert os.path.exists(os.path.join(out, f"{name}.json")), name
    # failure packets + new pairs exist for non-final generations
    assert os.path.exists(os.path.join(out, "gen00_failure_packet.json"))
    assert os.path.exists(os.path.join(out, "gen00_new_pairs.json"))


def test_run_evolution_deterministic(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALWEAVER_OUTPUT_DIR", str(tmp_path / "a"))
    r1 = run_evolution(_small_config(tmp_path, n_generations=2))
    h1 = json.load(open(os.path.join(r1["output_dir"], "evolve_history.json")))
    monkeypatch.setenv("EVALWEAVER_OUTPUT_DIR", str(tmp_path / "b"))
    r2 = run_evolution(_small_config(tmp_path, n_generations=2))
    h2 = json.load(open(os.path.join(r2["output_dir"], "evolve_history.json")))
    assert h1 == h2


def test_run_evolution_goal_keyword_is_dynamic(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALWEAVER_OUTPUT_DIR", str(tmp_path))
    result = run_evolution(_small_config(tmp_path, goal="trustworthy", n_generations=2))
    assert result["success"]
    assert result["goal"] == "trustworthy"
    assert "evolve_trustworthy_seed11" in result["output_dir"]
