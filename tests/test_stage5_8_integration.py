"""Integration tests for Stages 5–8 pipeline with mock provider."""
# Feature: stages-5-8-reasoning-pipeline

import json
import os
import tempfile

from evalweaver.stage6_runner import run_stage_6
from evalweaver.stage_eval import eval_stage_5, eval_stage_6, eval_stage_7, eval_stage_8
from evalweaver.stage_models import STAGE_5_HARD_GATES, STAGE_6_HARD_GATES, STAGE_7_HARD_GATES, STAGE_8_HARD_GATES, SMOKE_TEXTS


# ─── Stage 6 deterministic evaluation tests ───

def test_stage6_deterministic_known_scorer():
    """Stage 6 correctly evaluates a scorer that always ranks positive > negative."""
    scorers = [{
        "scorer_id": "S_always_right",
        "code": "def scorer(text, anchor, params):\n    return len(text) / 200.0",
    }]
    pair_suite = {
        "pairs": [
            {"pair_id": "P1", "split": "train", "anchor": "test",
             "positive": "This text has more words and is longer than the negative",
             "negative": "Short text"},
            {"pair_id": "P2", "split": "heldout", "anchor": "test",
             "positive": "Another longer positive text with more words in it",
             "negative": "Brief"},
        ],
    }

    result = run_stage_6(scorers, pair_suite, "")
    assert "S_always_right" in result["scorer_evaluations"]
    rows = result["scorer_evaluations"]["S_always_right"]
    assert len(rows) == 2
    assert all(r["correct"] for r in rows)  # longer text always scores higher

    summaries = result["scorer_summaries"]
    assert len(summaries) == 1
    assert summaries[0]["train_accuracy"] == 1.0
    assert summaries[0]["heldout_accuracy"] == 1.0
    assert summaries[0]["eligible"] is True


def test_stage6_constant_scorer_ineligible():
    """Stage 6 marks a constant scorer as ineligible."""
    scorers = [{
        "scorer_id": "S_constant",
        "code": "def scorer(text, anchor, params):\n    return 0.5",
    }]
    pair_suite = {
        "pairs": [
            {"pair_id": "P1", "split": "train", "anchor": "a",
             "positive": "positive text here", "negative": "negative text here"},
            {"pair_id": "P2", "split": "heldout", "anchor": "a",
             "positive": "another pos", "negative": "another neg"},
        ],
    }

    result = run_stage_6(scorers, pair_suite, "")
    summaries = result["scorer_summaries"]
    assert summaries[0]["eligible"] is False
    assert "constant" in summaries[0]["eligibility_reason"]


def test_stage6_broken_scorer_exec_error():
    """Stage 6 handles a scorer that raises an exception."""
    scorers = [{
        "scorer_id": "S_broken",
        "code": "def scorer(text, anchor, params):\n    raise RuntimeError('oops')",
    }]
    pair_suite = {
        "pairs": [
            {"pair_id": "P1", "split": "train", "anchor": "a",
             "positive": "pos", "negative": "neg"},
        ],
    }

    result = run_stage_6(scorers, pair_suite, "")
    summaries = result["scorer_summaries"]
    assert summaries[0]["exec_error_rate"] == 1.0
    assert summaries[0]["eligible"] is False


# ─── Stage 5 eval tests ───

def test_stage5_eval_perfect_pairs():
    """Stage 5 eval gives high scores for well-formed pairs."""
    nodes = [{"node_id": "credibility"}, {"node_id": "specificity"}]
    data = {
        "target_variable": "trustworthy",
        "pairs": [
            {
                "pair_id": "P1", "anchor": "We help teams ship faster.",
                "positive": "We help teams ship faster by surfacing evidence.",
                "negative": "We help teams ship faster with our platform.",
                "split": "train", "target_delta": "specificity",
                "controlled_variables": ["length", "topic"],
                "causal_nodes_tested": ["specificity"],
                "label_contract": "positive adds concrete mechanism",
                "source_trace": "generated", "source_id": "SRC1",
                "policy_violations": [],
            },
        ],
    }

    result = eval_stage_5(data, STAGE_5_HARD_GATES, nodes)
    assert result.signals["pair_schema_completeness_rate"] == 1.0
    assert result.signals["causal_node_reference_validity_rate"] == 1.0
    assert result.signals["target_direction_clarity_rate"] == 1.0
    assert result.signals["minimal_contrast_rate"] == 1.0


# ─── Heldout leakage detection ───

def test_stage7_eval_detects_leakage():
    """Stage 7 eval correctly detects when heldout text appears in output."""
    heldout_text = "This is a unique heldout sentence that should never appear in repair prompts"
    heldout_pairs = [{"positive": heldout_text, "negative": "another heldout text"}]

    # Output that leaks heldout text
    parsed_with_leak = {
        "failure_patterns": [{"pattern_id": "FP1", "scorer_ids": ["S0"], "reasoning_error": "test"}],
        "mutation_instructions": [{"instruction_id": "MI1", "instruction": f"fix based on: {heldout_text}"}],
        "heldout_aggregate_only": {},
        "failure_packet": {"top_scorers": []},
    }

    result = eval_stage_7(parsed_with_leak, STAGE_7_HARD_GATES, heldout_pairs)
    assert result.signals["heldout_raw_text_leakage_count"] > 0
    assert not result.passed  # hard gate fails


def test_stage7_eval_no_leakage_passes():
    """Stage 7 eval passes when no heldout text is present."""
    heldout_pairs = [{"positive": "unique heldout positive text xyz123", "negative": "unique heldout negative xyz456"}]

    parsed_clean = {
        "failure_patterns": [{"pattern_id": "FP1", "scorer_ids": ["S0"], "reasoning_error": "scorer misses specificity",
                              "visible_pair_ids": ["P1"], "causal_nodes_implicated": ["specificity"]}],
        "mutation_instructions": [{"instruction_id": "MI1", "instruction": "add weight for concrete nouns"}],
        "heldout_aggregate_only": {"heldout_accuracy_by_scorer": {"S0": 0.7}},
        "failure_packet": {"top_scorers": [{"scorer_id": "S0"}]},
    }

    result = eval_stage_7(parsed_clean, STAGE_7_HARD_GATES, heldout_pairs)
    assert result.signals["heldout_raw_text_leakage_count"] == 0
    assert result.passed


# ─── Stage 8 eval tests ───

def test_stage8_eval_working_scorers():
    """Stage 8 eval correctly evaluates working repair scorers."""
    nodes = [{"node_id": "specificity"}]
    patterns = [{"pattern_id": "FP001"}]

    parsed = {
        "target_variable": "trustworthy",
        "repair_scorers": [
            {
                "scorer_id": "RS0",
                "hypothesis": "improve specificity detection",
                "causal_nodes_used": ["specificity"],
                "measurement_ideas_used": ["concrete noun ratio"],
                "functional_form": "additive",
                "lineage": "repair_round_1",
                "parent_scorer_ids": ["S0"],
                "targets_failure_patterns": ["FP001"],
                "repair_strategy": "add weight for concrete nouns",
                "code": "def scorer(text, anchor, params):\n    words = text.lower().split()\n    return min(len(words) / 20.0, 1.0)",
                "code_feature_map": {"word_count": "length proxy"},
            },
        ],
    }

    result = eval_stage_8(parsed, STAGE_8_HARD_GATES, nodes, patterns, SMOKE_TEXTS, "")
    assert result.signals["code_exec_rate"] == 1.0
    assert result.signals["nonconstant_behavior_rate"] == 1.0
    assert result.signals["failure_pattern_target_rate"] == 1.0
    assert result.signals["causal_node_validity_rate"] == 1.0
    assert result.signals["unsafe_code_penalty"] == 0.0
