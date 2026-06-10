"""Property-based tests for Stages 5–8 eval signal computation."""
# Feature: stages-5-8-reasoning-pipeline

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from evalweaver.stage_eval import eval_stage_5, eval_stage_6, eval_stage_7, eval_stage_8
from evalweaver.stage_models import STAGE_5_HARD_GATES, STAGE_6_HARD_GATES, STAGE_7_HARD_GATES, STAGE_8_HARD_GATES, SMOKE_TEXTS


# ─── Strategies ───

def st_pair(node_ids):
    """Generate a random pair with variable field completeness."""
    return st.fixed_dictionaries({
        "pair_id": st.text(min_size=1, max_size=5),
        "anchor": st.text(min_size=1, max_size=30),
        "positive": st.text(min_size=5, max_size=50),
        "negative": st.text(min_size=5, max_size=50),
        "split": st.sampled_from(["train", "heldout"]),
        "target_delta": st.text(min_size=1, max_size=20),
        "controlled_variables": st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=3),
        "causal_nodes_tested": st.lists(st.sampled_from(node_ids) if node_ids else st.text(min_size=1, max_size=8), min_size=1, max_size=2),
        "label_contract": st.text(min_size=1, max_size=30),
        "source_trace": st.text(min_size=1, max_size=20),
        "source_id": st.text(min_size=1, max_size=8),
        "policy_violations": st.just([]),
    })


# ─── Property 7: pair_schema_completeness_rate ───

@settings(max_examples=100)
@given(st.integers(min_value=1, max_value=10), st.floats(min_value=0.0, max_value=1.0))
def test_pair_schema_completeness_rate(n_pairs, drop_probability):
    """P7: pair_schema_completeness_rate = complete_pairs / total_pairs."""
    # Feature: stages-5-8-reasoning-pipeline, Property 7: pair_schema_completeness_rate
    assume(n_pairs > 0)
    required = ["pair_id", "anchor", "positive", "negative", "split", "target_delta", "controlled_variables"]
    pairs = []
    expected_complete = 0
    for i in range(n_pairs):
        p = {f: f"val_{i}" for f in required}
        p["controlled_variables"] = ["length"]
        # Randomly drop a field
        if drop_probability > 0.5 and i % 2 == 0:
            del p[required[i % len(required)]]
        else:
            expected_complete += 1
        pairs.append(p)

    data = {"target_variable": "test", "pairs": pairs}
    result = eval_stage_5(data, STAGE_5_HARD_GATES, [])
    rate = result.signals["pair_schema_completeness_rate"]
    assert rate == expected_complete / n_pairs


# ─── Property 9: length_balance_rate ───

@settings(max_examples=50)
@given(st.lists(st.tuples(st.integers(min_value=1, max_value=20), st.integers(min_value=1, max_value=20)), min_size=1, max_size=8))
def test_length_balance_rate(word_counts):
    """P9: length_balance_rate checks word count difference <= max_words * 0.3."""
    # Feature: stages-5-8-reasoning-pipeline, Property 9: length_balance_rate
    max_words = 80
    threshold = max_words * 0.3  # 24

    pairs = []
    expected_balanced = 0
    for pos_words, neg_words in word_counts:
        positive = " ".join(["word"] * pos_words)
        negative = " ".join(["word"] * neg_words)
        if abs(pos_words - neg_words) <= threshold:
            expected_balanced += 1
        pairs.append({
            "pair_id": "P", "anchor": "a", "positive": positive, "negative": negative,
            "split": "train", "target_delta": "d", "controlled_variables": ["x"],
            "causal_nodes_tested": [], "label_contract": "lc", "source_trace": "s",
            "source_id": "s", "policy_violations": [],
        })

    data = {"target_variable": "test", "pairs": pairs}
    result = eval_stage_5(data, STAGE_5_HARD_GATES, [], max_words=max_words)
    assert result.signals["length_balance_rate"] == expected_balanced / len(word_counts)


# ─── Property 13: overfit_warning_count ───

@settings(max_examples=50)
@given(st.lists(st.tuples(st.floats(0, 1), st.floats(0, 1)), min_size=1, max_size=10))
def test_overfit_warning_count(acc_pairs):
    """P13: overfit_warning_count = scorers where train_accuracy > heldout_accuracy + 0.2."""
    # Feature: stages-5-8-reasoning-pipeline, Property 13: overfit_warning_count
    summaries = []
    expected_count = 0
    for i, (train_acc, heldout_acc) in enumerate(acc_pairs):
        summaries.append({
            "scorer_id": f"S{i}", "train_accuracy": train_acc, "heldout_accuracy": heldout_acc,
            "exec_error_rate": 0, "nonconstant_rate": 1, "score_spread": 0.1,
            "heldout_mean_gap": 0.1, "train_mean_gap": 0.1, "eligible": True,
        })
        if train_acc > heldout_acc + 0.2:
            expected_count += 1

    result = eval_stage_6(summaries, [], {}, STAGE_6_HARD_GATES)
    assert result.signals["overfit_warning_count"] == expected_count


# ─── Property 14: heldout leakage detection ───

@settings(max_examples=50)
@given(st.booleans())
def test_heldout_leakage_detection(inject_leakage):
    """P14: heldout_raw_text_leakage_count > 0 iff heldout text appears in output."""
    # Feature: stages-5-8-reasoning-pipeline, Property 14: heldout leakage detection
    heldout_pairs = [{"positive": "This is a unique heldout positive text for testing", "negative": "This is a unique heldout negative text for testing"}]

    if inject_leakage:
        # Include heldout text in the parsed output
        parsed = {
            "failure_patterns": [{"pattern_id": "FP1", "scorer_ids": ["S0"], "reasoning_error": "test",
                                  "visible_pair_ids": ["P1"], "causal_nodes_implicated": ["n1"]}],
            "mutation_instructions": [{"instruction_id": "MI1", "instruction": "add feature"}],
            "heldout_aggregate_only": {},
            "failure_packet": {"top_scorers": []},
            "leaked_text": "This is a unique heldout positive text for testing",
        }
    else:
        parsed = {
            "failure_patterns": [{"pattern_id": "FP1", "scorer_ids": ["S0"], "reasoning_error": "test",
                                  "visible_pair_ids": ["P1"], "causal_nodes_implicated": ["n1"]}],
            "mutation_instructions": [{"instruction_id": "MI1", "instruction": "add feature"}],
            "heldout_aggregate_only": {},
            "failure_packet": {"top_scorers": []},
        }

    result = eval_stage_7(parsed, STAGE_7_HARD_GATES, heldout_pairs)
    if inject_leakage:
        assert result.signals["heldout_raw_text_leakage_count"] > 0
        assert not result.passed  # hard gate fails
    else:
        assert result.signals["heldout_raw_text_leakage_count"] == 0


# ─── Property 15: mutation_actionability_score ───

@settings(max_examples=50)
@given(st.lists(st.booleans(), min_size=1, max_size=8))
def test_mutation_actionability_score(has_verbs):
    """P15: mutation_actionability_score = fraction with action verbs."""
    # Feature: stages-5-8-reasoning-pipeline, Property 15: mutation_actionability_score
    instructions = []
    for i, has_verb in enumerate(has_verbs):
        if has_verb:
            instructions.append({"instruction_id": f"MI{i}", "instruction": "add a weight for specificity"})
        else:
            instructions.append({"instruction_id": f"MI{i}", "instruction": "the scorer should be better"})

    parsed = {
        "failure_patterns": [{"pattern_id": "FP1", "scorer_ids": ["S0"], "reasoning_error": "test"}],
        "mutation_instructions": instructions,
        "heldout_aggregate_only": {},
        "failure_packet": {"top_scorers": []},
    }
    result = eval_stage_7(parsed, STAGE_7_HARD_GATES, [])
    expected = sum(has_verbs) / len(has_verbs)
    assert abs(result.signals["mutation_actionability_score"] - expected) < 1e-9


# ─── Property 16: code_exec_rate ───

@settings(max_examples=30)
@given(st.lists(st.booleans(), min_size=1, max_size=5))
def test_code_exec_rate(scorer_valid):
    """P16: code_exec_rate = exception-free scorers / total."""
    # Feature: stages-5-8-reasoning-pipeline, Property 16: code_exec_rate
    scorers = []
    for i, valid in enumerate(scorer_valid):
        if valid:
            code = "def scorer(text, anchor, params):\n    return len(text) / 100.0"
        else:
            code = "def scorer(text, anchor, params):\n    raise ValueError('broken')"
        scorers.append({"scorer_id": f"RS{i}", "code": code, "causal_nodes_used": [],
                        "functional_form": "additive", "hypothesis": "h",
                        "targets_failure_patterns": []})

    parsed = {"target_variable": "test", "repair_scorers": scorers}
    result = eval_stage_8(parsed, STAGE_8_HARD_GATES, [], [], SMOKE_TEXTS, "")
    expected = sum(scorer_valid) / len(scorer_valid)
    assert abs(result.signals["code_exec_rate"] - expected) < 1e-9


# ─── Property 17: nonconstant_behavior_rate ───

@settings(max_examples=30)
@given(st.lists(st.booleans(), min_size=1, max_size=5))
def test_nonconstant_behavior_rate(scorer_nonconstant):
    """P17: nonconstant = different outputs across smoke texts."""
    # Feature: stages-5-8-reasoning-pipeline, Property 17: nonconstant_behavior_rate
    scorers = []
    for i, nonconstant in enumerate(scorer_nonconstant):
        if nonconstant:
            code = "def scorer(text, anchor, params):\n    return len(text) / 200.0"
        else:
            code = "def scorer(text, anchor, params):\n    return 0.5"
        scorers.append({"scorer_id": f"RS{i}", "code": code, "causal_nodes_used": [],
                        "functional_form": "additive", "hypothesis": "h",
                        "targets_failure_patterns": []})

    parsed = {"target_variable": "test", "repair_scorers": scorers}
    result = eval_stage_8(parsed, STAGE_8_HARD_GATES, [], [], SMOKE_TEXTS, "")
    expected = sum(scorer_nonconstant) / len(scorer_nonconstant)
    assert abs(result.signals["nonconstant_behavior_rate"] - expected) < 1e-9


# ─── Property 19: unsafe_code_penalty ───

@settings(max_examples=30)
@given(st.lists(st.booleans(), min_size=1, max_size=5))
def test_unsafe_code_penalty(scorer_unsafe):
    """P19: unsafe_code_penalty detects forbidden patterns."""
    # Feature: stages-5-8-reasoning-pipeline, Property 19: unsafe_code_penalty
    scorers = []
    for i, unsafe in enumerate(scorer_unsafe):
        if unsafe:
            code = "import os\ndef scorer(text, anchor, params):\n    return 0.5"
        else:
            code = "def scorer(text, anchor, params):\n    return len(text) / 200.0"
        scorers.append({"scorer_id": f"RS{i}", "code": code, "causal_nodes_used": [],
                        "functional_form": "additive", "hypothesis": "h",
                        "targets_failure_patterns": []})

    parsed = {"target_variable": "test", "repair_scorers": scorers}
    result = eval_stage_8(parsed, STAGE_8_HARD_GATES, [], [], SMOKE_TEXTS, "")
    expected = sum(scorer_unsafe) / len(scorer_unsafe)
    assert abs(result.signals["unsafe_code_penalty"] - expected) < 1e-9
