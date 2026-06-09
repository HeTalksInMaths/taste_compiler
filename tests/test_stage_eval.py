"""
Property-based tests for Stages 1–4 eval engine.

Tests Properties 5–15 from the design document using Hypothesis.
"""

import math
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from evalweaver.stage_eval import (
    eval_stage_1, eval_stage_2, eval_stage_3, eval_stage_4,
    _compute_causal_specificity, _compute_generic_penalty,
    _eval_scorer_code, MECHANISTIC_KEYWORDS, VAGUE_ADVICE_WORDS,
)
from evalweaver.stage_models import (
    check_pass_criteria, SMOKE_TEXTS,
    STAGE_1_PASS_CRITERIA, STAGE_2_PASS_CRITERIA,
    STAGE_3_PASS_CRITERIA, STAGE_4_PASS_CRITERIA,
)


# ─────────────────────────────────────────────────────────────────────
# STRATEGIES
# ─────────────────────────────────────────────────────────────────────

def st_research_item(
    has_claim=None, has_causal_variable=None, has_effect_direction=None,
    has_mechanism=None, has_source_id=None,
):
    """Generate a causal_research item with configurable field completeness."""
    claim = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)) if has_claim is not False else st.just("")
    causal_var = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)) if has_causal_variable is not False else st.just("")
    direction = st.sampled_from(["increases", "decreases", "mediates", "moderates"]) if has_effect_direction is not False else st.just("")
    mechanism = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)) if has_mechanism is not False else st.just("")
    source = st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)) if has_source_id is not False else st.just("")

    return st.fixed_dictionaries({
        "source_id": source,
        "title": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N", "Z"), max_codepoint=127)),
        "claim": claim,
        "causal_variable": causal_var,
        "effect_direction": direction,
        "mechanism": mechanism,
        "evidence_strength": st.sampled_from(["high", "medium", "low"]),
    })


def st_research_items_mixed():
    """Generate a list of research items with mixed completeness."""
    complete_item = st_research_item(
        has_claim=True, has_causal_variable=True, has_effect_direction=True,
        has_mechanism=True, has_source_id=True,
    )
    incomplete_item = st.one_of(
        st_research_item(has_claim=False),
        st_research_item(has_mechanism=False),
        st_research_item(has_source_id=False),
    )
    return st.lists(
        st.one_of(complete_item, incomplete_item),
        min_size=1, max_size=15,
    )


def st_causal_node(node_id=None):
    """Generate a causal graph node."""
    nid = st.just(node_id) if node_id else st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127))
    return st.fixed_dictionaries({
        "node_id": nid,
        "label": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
        "role": st.sampled_from(["increases", "decreases", "mediates", "moderates"]),
        "definition": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
        "mechanism": st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "Z"), max_codepoint=127)),
        "evidence": st.lists(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)), min_size=1, max_size=3),
    })


def st_node_ids():
    """Generate a list of unique node IDs."""
    return st.lists(
        st.text(min_size=2, max_size=15, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
        min_size=2, max_size=10, unique=True,
    )


# ─────────────────────────────────────────────────────────────────────
# Property 5: mechanism_completeness_rate
# Feature: stages-1-4-reasoning-pipeline, Property 5: mechanism_completeness_rate is correct fraction
# ─────────────────────────────────────────────────────────────────────


class TestProperty5MechanismCompletenessRate:
    """mechanism_completeness_rate equals fraction of items with all required fields populated."""

    # **Validates: Requirements 2.2**

    @given(st_research_items_mixed())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_mechanism_completeness_is_correct_fraction(self, items):
        """mechanism_completeness_rate == count(complete items) / total items."""
        assume(len(items) > 0)

        required_fields = ["claim", "causal_variable", "effect_direction", "mechanism", "source_id"]
        expected_complete = sum(1 for it in items if all(it.get(f) for f in required_fields))
        expected_rate = expected_complete / len(items)

        parsed = {"causal_research": items, "research_tensions": [], "target_variable": "test"}
        result = eval_stage_1(parsed, STAGE_1_PASS_CRITERIA)

        actual_rate = result.signals["mechanism_completeness_rate"]
        assert math.isclose(actual_rate, expected_rate, abs_tol=1e-9), (
            f"Expected {expected_rate}, got {actual_rate}"
        )

    @given(st.lists(st_research_item(
        has_claim=True, has_causal_variable=True, has_effect_direction=True,
        has_mechanism=True, has_source_id=True,
    ), min_size=1, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_all_complete_gives_rate_1(self, items):
        """All complete items should give rate 1.0."""
        parsed = {"causal_research": items, "research_tensions": [], "target_variable": "test"}
        result = eval_stage_1(parsed, STAGE_1_PASS_CRITERIA)
        assert math.isclose(result.signals["mechanism_completeness_rate"], 1.0, abs_tol=1e-9)


# ─────────────────────────────────────────────────────────────────────
# Property 6: causal_specificity_score monotonicity
# Feature: stages-1-4-reasoning-pipeline, Property 6: causal_specificity_score rewards mechanistic language
# ─────────────────────────────────────────────────────────────────────


class TestProperty6CausalSpecificityMonotonicity:
    """causal_specificity_score is monotonically non-decreasing as more claims contain mechanistic keywords."""

    # **Validates: Requirements 2.3**

    @given(
        st.integers(min_value=1, max_value=10),
        st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_monotonicity_with_more_keywords(self, n_with_keywords, n_without):
        """Adding more items with keywords doesn't decrease the score per-item."""
        assume(n_with_keywords > 0)

        # Items with mechanistic keywords in claim
        items_with = [{"claim": f"X because Y leads to Z item {i}", "mechanism": "mech"} for i in range(n_with_keywords)]
        # Items without mechanistic keywords
        items_without = [{"claim": f"some plain claim {i}", "mechanism": ""} for i in range(n_without)]

        # Score with just keyword items
        score_keywords_only = _compute_causal_specificity(items_with)
        # Score with mixed (keywords + plain)
        score_mixed = _compute_causal_specificity(items_with + items_without)

        # The absolute count of matching items doesn't decrease, but the rate may
        # Property: score is correct fraction of items with keyword
        expected_mixed = n_with_keywords / (n_with_keywords + n_without)
        assert math.isclose(score_mixed, expected_mixed, abs_tol=1e-9)
        assert math.isclose(score_keywords_only, 1.0, abs_tol=1e-9)

    @given(st.sampled_from(MECHANISTIC_KEYWORDS))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_each_keyword_contributes_positively(self, keyword):
        """Each mechanistic keyword in a claim contributes positively to the score."""
        items_with = [{"claim": f"variable {keyword} another variable", "mechanism": ""}]
        items_without = [{"claim": "plain statement about stuff", "mechanism": ""}]

        score_with = _compute_causal_specificity(items_with)
        score_without = _compute_causal_specificity(items_without)

        assert score_with >= score_without, (
            f"Keyword '{keyword}' did not contribute positively: {score_with} < {score_without}"
        )


# ─────────────────────────────────────────────────────────────────────
# Property 7: generic_advice_penalty only without mechanism
# Feature: stages-1-4-reasoning-pipeline, Property 7: generic_advice_penalty only activates without mechanism
# ─────────────────────────────────────────────────────────────────────


class TestProperty7GenericAdvicePenalty:
    """generic_advice_penalty only activates for items with vague words AND empty mechanism."""

    # **Validates: Requirements 2.4**

    @given(
        st.sampled_from(VAGUE_ADVICE_WORDS),
        st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_vague_with_mechanism_no_penalty(self, vague_word, mechanism):
        """Items with vague words but populated mechanism (non-whitespace) don't contribute to penalty."""
        assume(mechanism.strip() != "")  # mechanism must be non-whitespace
        items = [{"claim": f"This is a {vague_word} approach", "mechanism": mechanism}]
        penalty = _compute_generic_penalty(items)
        assert penalty == 0.0, (
            f"Penalty should be 0 with mechanism present, got {penalty}"
        )

    @given(st.sampled_from(VAGUE_ADVICE_WORDS))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_vague_without_mechanism_has_penalty(self, vague_word):
        """Items with vague words and empty mechanism contribute to penalty."""
        items = [{"claim": f"This is a {vague_word} approach", "mechanism": ""}]
        penalty = _compute_generic_penalty(items)
        assert penalty > 0.0, (
            f"Penalty should be > 0 without mechanism, got {penalty}"
        )

    @given(
        st.lists(st.sampled_from(VAGUE_ADVICE_WORDS), min_size=1, max_size=5),
        st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127)), min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_populated_mechanism_always_exempt(self, vague_words, mechanisms):
        """All items with populated non-whitespace mechanisms are exempt regardless of vague word count."""
        # Filter out whitespace-only mechanisms since implementation strips them
        items = [{"claim": f"A {w} method", "mechanism": m} for w, m in zip(vague_words, mechanisms) if m.strip()]
        assume(len(items) > 0)
        penalty = _compute_generic_penalty(items)
        assert penalty == 0.0


# ─────────────────────────────────────────────────────────────────────
# Property 8: pass criteria threshold check
# Feature: stages-1-4-reasoning-pipeline, Property 8: pass criteria threshold check is correct
# ─────────────────────────────────────────────────────────────────────


class TestProperty8PassCriteriaThreshold:
    """check_pass_criteria passes iff every signal meets its threshold."""

    # **Validates: Requirements 2.5, 4.5, 6.5, 8.6**

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1, max_size=5,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_all_above_min_passes(self, signal_values):
        """When all signals exceed their min thresholds, check passes."""
        # Create criteria that are below the signal values
        criteria = {f"{name}_min": val - 0.1 for name, val in signal_values.items()}
        passed, failures = check_pass_criteria(signal_values, criteria)
        assert passed is True
        assert failures == []

    @given(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
        st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_below_min_fails(self, signal_name, threshold):
        """When a signal is below its min threshold, check fails."""
        signals = {signal_name: threshold - 0.01}
        criteria = {f"{signal_name}_min": threshold}
        passed, failures = check_pass_criteria(signals, criteria)
        assert passed is False
        assert len(failures) == 1
        assert failures[0]["signal"] == signal_name
        assert failures[0]["op"] == ">="

    @given(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",), max_codepoint=127)),
        st.floats(min_value=0.0, max_value=99.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_above_max_fails(self, signal_name, threshold):
        """When a signal exceeds its max threshold, check fails."""
        signals = {signal_name: threshold + 0.01}
        criteria = {f"{signal_name}_max": threshold}
        passed, failures = check_pass_criteria(signals, criteria)
        assert passed is False
        assert len(failures) == 1
        assert failures[0]["signal"] == signal_name
        assert failures[0]["op"] == "<="

    def test_stage_1_criteria_format(self):
        """Stage 1 pass criteria keys all end with _min or _max."""
        for key in STAGE_1_PASS_CRITERIA:
            assert key.endswith("_min") or key.endswith("_max"), f"Invalid criteria key: {key}"

    def test_stage_2_criteria_format(self):
        """Stage 2 pass criteria keys all end with _min or _max."""
        for key in STAGE_2_PASS_CRITERIA:
            assert key.endswith("_min") or key.endswith("_max"), f"Invalid criteria key: {key}"


# ─────────────────────────────────────────────────────────────────────
# Property 9: edge_validity_rate
# Feature: stages-1-4-reasoning-pipeline, Property 9: edge_validity_rate counts only valid references
# ─────────────────────────────────────────────────────────────────────


class TestProperty9EdgeValidityRate:
    """edge_validity_rate equals fraction of edges where both from/to reference existing node_ids."""

    # **Validates: Requirements 4.2**

    @given(st_node_ids(), st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_edge_validity_correct_fraction(self, node_ids, data):
        """edge_validity_rate == valid_edges / total_edges."""
        assume(len(node_ids) >= 2)

        nodes = [{"node_id": nid, "label": nid, "role": "increases", "definition": "d", "mechanism": "m", "evidence": ["S1"]} for nid in node_ids]

        # Generate a mix of valid and invalid edges
        num_edges = data.draw(st.integers(min_value=1, max_value=8))
        edges = []
        for i in range(num_edges):
            if data.draw(st.booleans()):
                # Valid edge: both from/to in node_ids
                f = data.draw(st.sampled_from(node_ids))
                t = data.draw(st.sampled_from(node_ids))
                edges.append({"from": f, "to": t, "relationship": "supports", "claim": "c"})
            else:
                # Invalid edge: at least one reference to non-existing node
                edges.append({"from": "INVALID_NODE_XYZ", "to": node_ids[0], "relationship": "r", "claim": "c"})

        parsed = {
            "target_variable": "test",
            "causal_nodes": nodes,
            "causal_edges": edges,
            "causal_tensions": [],
            "summary_theory": "theory",
        }

        result = eval_stage_2(parsed, STAGE_2_PASS_CRITERIA)

        # Compute expected validity (note: stage_eval also considers target_variable as valid "to" target)
        node_id_set = set(node_ids)
        valid_edge_targets = node_id_set | {"test"}
        expected_valid = sum(1 for e in edges if e["from"] in node_id_set and e["to"] in valid_edge_targets)
        expected_rate = expected_valid / len(edges)

        actual_rate = result.signals["edge_validity_rate"]
        assert math.isclose(actual_rate, expected_rate, abs_tol=1e-9), (
            f"Expected {expected_rate}, got {actual_rate}"
        )


# ─────────────────────────────────────────────────────────────────────
# Property 10: graph_connectedness_score
# Feature: stages-1-4-reasoning-pipeline, Property 10: graph_connectedness_score counts participating nodes
# ─────────────────────────────────────────────────────────────────────


class TestProperty10GraphConnectedness:
    """graph_connectedness_score equals fraction of nodes participating in at least one edge."""

    # **Validates: Requirements 4.3**

    @given(st_node_ids(), st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_connectedness_correct_fraction(self, node_ids, data):
        """graph_connectedness_score == participating_nodes / total_nodes."""
        assume(len(node_ids) >= 2)

        nodes = [{"node_id": nid, "label": nid, "role": "increases", "definition": "d", "mechanism": "m", "evidence": ["S1"]} for nid in node_ids]

        # Create edges that connect only some nodes
        num_edges = data.draw(st.integers(min_value=1, max_value=6))
        connected_subset = data.draw(st.lists(
            st.sampled_from(node_ids), min_size=1, max_size=min(len(node_ids), num_edges + 1), unique=True
        ))
        edges = []
        for i in range(num_edges):
            f = data.draw(st.sampled_from(connected_subset))
            t = data.draw(st.sampled_from(connected_subset))
            edges.append({"from": f, "to": t, "relationship": "supports", "claim": "c"})

        parsed = {
            "target_variable": "test",
            "causal_nodes": nodes,
            "causal_edges": edges,
            "causal_tensions": [],
            "summary_theory": "theory",
        }

        result = eval_stage_2(parsed, STAGE_2_PASS_CRITERIA)

        # Compute expected: count nodes that appear in any edge as from or to
        node_id_set = set(node_ids)
        participating = set()
        for e in edges:
            if e["from"]:
                participating.add(e["from"])
            if e["to"]:
                participating.add(e["to"])
        expected_rate = len(participating & node_id_set) / len(node_ids)

        actual_rate = result.signals["graph_connectedness_score"]
        assert math.isclose(actual_rate, expected_rate, abs_tol=1e-9), (
            f"Expected {expected_rate}, got {actual_rate}"
        )


# ─────────────────────────────────────────────────────────────────────
# Property 11: node_measurement_coverage
# Feature: stages-1-4-reasoning-pipeline, Property 11: node_measurement_coverage is correct fraction
# ─────────────────────────────────────────────────────────────────────


class TestProperty11NodeMeasurementCoverage:
    """node_measurement_coverage equals fraction of stage2 nodes referenced by measurement items."""

    # **Validates: Requirements 6.2**

    @given(st_node_ids(), st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_coverage_correct_fraction(self, node_ids, data):
        """node_measurement_coverage == covered_nodes / total_nodes."""
        assume(len(node_ids) >= 2)

        stage2_nodes = [{"node_id": nid, "label": nid, "role": "increases", "definition": "d", "mechanism": "m", "evidence": ["S1"]} for nid in node_ids]

        # Create measurement items referencing a subset of nodes
        covered_ids = data.draw(st.lists(
            st.sampled_from(node_ids), min_size=0, max_size=len(node_ids), unique=True
        ))
        items = [
            {"source_id": f"M{i}", "causal_node": nid, "measurement_claim": "claim",
             "text_features": ["feat1"], "implementation_ideas": ["idea1"]}
            for i, nid in enumerate(covered_ids)
        ]

        parsed = {"target_variable": "test", "measurement_research": items}
        result = eval_stage_3(parsed, STAGE_3_PASS_CRITERIA, stage2_nodes)

        expected_rate = len(set(covered_ids)) / len(node_ids)
        actual_rate = result.signals["node_measurement_coverage"]
        assert math.isclose(actual_rate, expected_rate, abs_tol=1e-9), (
            f"Expected {expected_rate}, got {actual_rate}"
        )


# ─────────────────────────────────────────────────────────────────────
# Property 12: node_reference_validity_rate
# Feature: stages-1-4-reasoning-pipeline, Property 12: node_reference_validity_rate checks against Stage 2 nodes
# ─────────────────────────────────────────────────────────────────────


class TestProperty12NodeReferenceValidity:
    """node_reference_validity_rate equals fraction of items whose causal_node matches a stage2 node_id."""

    # **Validates: Requirements 6.3, 8.5**

    @given(st_node_ids(), st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_reference_validity_correct_fraction(self, node_ids, data):
        """node_reference_validity_rate == valid_refs / total_items."""
        assume(len(node_ids) >= 2)

        stage2_nodes = [{"node_id": nid} for nid in node_ids]
        node_id_set = set(node_ids)

        # Generate items: some reference valid nodes, some reference invalid nodes
        num_items = data.draw(st.integers(min_value=1, max_value=8))
        items = []
        for i in range(num_items):
            if data.draw(st.booleans()):
                # Valid reference
                nid = data.draw(st.sampled_from(node_ids))
            else:
                # Invalid reference
                nid = "NONEXISTENT_NODE_ABC"
            items.append({
                "source_id": f"M{i}", "causal_node": nid, "measurement_claim": "claim",
                "text_features": ["feat"], "implementation_ideas": ["idea"],
            })

        parsed = {"target_variable": "test", "measurement_research": items}
        result = eval_stage_3(parsed, STAGE_3_PASS_CRITERIA, stage2_nodes)

        expected_valid = sum(1 for it in items if it["causal_node"] in node_id_set)
        expected_rate = expected_valid / len(items)
        actual_rate = result.signals["node_reference_validity_rate"]
        assert math.isclose(actual_rate, expected_rate, abs_tol=1e-9), (
            f"Expected {expected_rate}, got {actual_rate}"
        )


# ─────────────────────────────────────────────────────────────────────
# Property 13: code_exec_rate
# Feature: stages-1-4-reasoning-pipeline, Property 13: code_exec_rate counts exceptions correctly
# ─────────────────────────────────────────────────────────────────────


class TestProperty13CodeExecRate:
    """code_exec_rate equals fraction of scorers that execute without exception on ALL smoke texts."""

    # **Validates: Requirements 8.2, 11.2, 11.3**

    @given(st.lists(
        st.sampled_from([
            # Valid scorer code
            "def scorer(text, anchor, params):\n    return len(text) / (len(text) + 100)",
            "def scorer(text, anchor, params):\n    return 0.5",
            # Invalid scorer code (will raise)
            "def scorer(text, anchor, params):\n    raise ValueError('boom')",
            "def scorer(text, anchor, params):\n    return 1/0",
        ]),
        min_size=1, max_size=6,
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_code_exec_rate_correct(self, code_list):
        """code_exec_rate == exception_free_scorers / total_scorers."""
        scorers = [{"code": code, "scorer_id": f"S{i}"} for i, code in enumerate(code_list)]
        smoke_texts = SMOKE_TEXTS
        anchor = "test anchor"

        code_exec_rate, _, _ = _eval_scorer_code(scorers, smoke_texts, anchor)

        # Manually compute expected
        valid_codes = [
            "def scorer(text, anchor, params):\n    return len(text) / (len(text) + 100)",
            "def scorer(text, anchor, params):\n    return 0.5",
        ]
        expected_pass = sum(1 for c in code_list if c in valid_codes)
        expected_rate = expected_pass / len(code_list)

        assert math.isclose(code_exec_rate, expected_rate, abs_tol=1e-9), (
            f"Expected {expected_rate}, got {code_exec_rate}"
        )

    def test_single_failing_text_fails_scorer(self):
        """A scorer raising on any single smoke text counts as failing."""
        # This scorer raises only when text contains "best"
        code = "def scorer(text, anchor, params):\n    if 'best' in text:\n        raise ValueError('no best')\n    return 0.5"
        scorers = [{"code": code, "scorer_id": "S0"}]
        code_exec_rate, _, _ = _eval_scorer_code(scorers, SMOKE_TEXTS, "anchor")
        assert code_exec_rate == 0.0, "Scorer should fail if it raises on any smoke text"


# ─────────────────────────────────────────────────────────────────────
# Property 14: nonconstant_behavior_rate
# Feature: stages-1-4-reasoning-pipeline, Property 14: nonconstant_behavior_rate requires output variance
# ─────────────────────────────────────────────────────────────────────


class TestProperty14NonconstantBehavior:
    """Nonconstant behavior requires at least two different values across smoke texts."""

    # **Validates: Requirements 8.3, 12.3**

    @given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_constant_scorer_fails_nonconstant(self, constant_val):
        """A scorer that always returns the same value fails nonconstant check."""
        code = f"def scorer(text, anchor, params):\n    return {constant_val!r}"
        scorers = [{"code": code, "scorer_id": "S0"}]
        _, _, nonconstant_rate = _eval_scorer_code(scorers, SMOKE_TEXTS, "anchor")
        assert nonconstant_rate == 0.0, (
            f"Constant scorer should fail nonconstant, got rate={nonconstant_rate}"
        )

    def test_varying_scorer_passes_nonconstant(self):
        """A scorer producing different values across smoke texts passes."""
        code = "def scorer(text, anchor, params):\n    return len(text) / (len(text) + 100)"
        scorers = [{"code": code, "scorer_id": "S0"}]
        _, _, nonconstant_rate = _eval_scorer_code(scorers, SMOKE_TEXTS, "anchor")
        assert nonconstant_rate == 1.0, (
            f"Varying scorer should pass nonconstant, got rate={nonconstant_rate}"
        )

    @given(st.lists(
        st.sampled_from([
            # Constant scorers
            "def scorer(text, anchor, params):\n    return 0.5",
            "def scorer(text, anchor, params):\n    return 0.0",
            # Varying scorers
            "def scorer(text, anchor, params):\n    return len(text) / (len(text) + 100)",
            "def scorer(text, anchor, params):\n    words = text.split()\n    return min(len(words) / 20.0, 1.0)",
        ]),
        min_size=1, max_size=6,
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_nonconstant_rate_correct_fraction(self, code_list):
        """nonconstant_behavior_rate == varying_scorers / total_scorers."""
        scorers = [{"code": code, "scorer_id": f"S{i}"} for i, code in enumerate(code_list)]
        _, _, nonconstant_rate = _eval_scorer_code(scorers, SMOKE_TEXTS, "anchor")

        varying_codes = [
            "def scorer(text, anchor, params):\n    return len(text) / (len(text) + 100)",
            "def scorer(text, anchor, params):\n    words = text.split()\n    return min(len(words) / 20.0, 1.0)",
        ]
        expected_pass = sum(1 for c in code_list if c in varying_codes)
        expected_rate = expected_pass / len(code_list)

        assert math.isclose(nonconstant_rate, expected_rate, abs_tol=1e-9), (
            f"Expected {expected_rate}, got {nonconstant_rate}"
        )


# ─────────────────────────────────────────────────────────────────────
# Property 15: scorer_distinctness_score
# Feature: stages-1-4-reasoning-pipeline, Property 15: scorer_distinctness_score is unique tuple fraction
# ─────────────────────────────────────────────────────────────────────


class TestProperty15ScorerDistinctness:
    """scorer_distinctness_score equals unique tuples of (form, nodes, ideas) / total scorers."""

    # **Validates: Requirements 8.4**

    @given(st.data())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_distinctness_correct_fraction(self, data):
        """scorer_distinctness_score == unique_tuples / num_scorers."""
        num_scorers = data.draw(st.integers(min_value=1, max_value=8))
        forms = data.draw(st.lists(
            st.sampled_from(["additive", "interaction", "gated", "penalty", "ratio"]),
            min_size=num_scorers, max_size=num_scorers,
        ))
        node_lists = data.draw(st.lists(
            st.lists(st.sampled_from(["credibility", "specificity", "hedging", "evidence"]), min_size=1, max_size=3),
            min_size=num_scorers, max_size=num_scorers,
        ))
        idea_lists = data.draw(st.lists(
            st.lists(st.sampled_from(["word_count", "regex_match", "density", "ratio"]), min_size=1, max_size=3),
            min_size=num_scorers, max_size=num_scorers,
        ))

        scorers = []
        for i in range(num_scorers):
            scorers.append({
                "scorer_id": f"S{i}",
                "functional_form": forms[i],
                "causal_nodes_used": node_lists[i],
                "measurement_ideas_used": idea_lists[i],
                "hypothesis": "h",
                "functional_form_rationale": "r",
                "expected_failure_mode": "f",
                "code": "def scorer(text, anchor, params):\n    return 0.5",
            })

        # Compute expected
        tuples_seen = set()
        for s in scorers:
            key = (s["functional_form"], frozenset(s["causal_nodes_used"]), frozenset(s["measurement_ideas_used"]))
            tuples_seen.add(key)
        expected_score = len(tuples_seen) / num_scorers

        # Run eval
        parsed = {"target_variable": "test", "scorers": scorers}
        stage2_nodes = [{"node_id": nid} for nid in ["credibility", "specificity", "hedging", "evidence"]]
        result = eval_stage_4(parsed, STAGE_4_PASS_CRITERIA, stage2_nodes, SMOKE_TEXTS, "anchor")

        actual_score = result.signals["scorer_distinctness_score"]
        assert math.isclose(actual_score, expected_score, abs_tol=1e-9), (
            f"Expected {expected_score}, got {actual_score}"
        )

    def test_all_identical_gives_min_distinctness(self):
        """All identical scorers give distinctness = 1/N."""
        scorers = [
            {
                "scorer_id": f"S{i}",
                "functional_form": "additive",
                "causal_nodes_used": ["credibility"],
                "measurement_ideas_used": ["word_count"],
                "hypothesis": "h",
                "functional_form_rationale": "r",
                "expected_failure_mode": "f",
                "code": "def scorer(text, anchor, params):\n    return 0.5",
            }
            for i in range(4)
        ]
        parsed = {"target_variable": "test", "scorers": scorers}
        stage2_nodes = [{"node_id": "credibility"}]
        result = eval_stage_4(parsed, STAGE_4_PASS_CRITERIA, stage2_nodes, SMOKE_TEXTS, "anchor")
        assert math.isclose(result.signals["scorer_distinctness_score"], 1.0 / 4.0, abs_tol=1e-9)

    def test_all_unique_gives_distinctness_1(self):
        """All unique scorers give distinctness = 1.0."""
        scorers = [
            {"scorer_id": "S0", "functional_form": "additive", "causal_nodes_used": ["credibility"],
             "measurement_ideas_used": ["word_count"], "hypothesis": "h", "functional_form_rationale": "r",
             "expected_failure_mode": "f", "code": "def scorer(text, anchor, params):\n    return 0.5"},
            {"scorer_id": "S1", "functional_form": "interaction", "causal_nodes_used": ["specificity"],
             "measurement_ideas_used": ["regex_match"], "hypothesis": "h", "functional_form_rationale": "r",
             "expected_failure_mode": "f", "code": "def scorer(text, anchor, params):\n    return 0.5"},
            {"scorer_id": "S2", "functional_form": "gated", "causal_nodes_used": ["hedging"],
             "measurement_ideas_used": ["density"], "hypothesis": "h", "functional_form_rationale": "r",
             "expected_failure_mode": "f", "code": "def scorer(text, anchor, params):\n    return 0.5"},
        ]
        parsed = {"target_variable": "test", "scorers": scorers}
        stage2_nodes = [{"node_id": nid} for nid in ["credibility", "specificity", "hedging"]]
        result = eval_stage_4(parsed, STAGE_4_PASS_CRITERIA, stage2_nodes, SMOKE_TEXTS, "anchor")
        assert math.isclose(result.signals["scorer_distinctness_score"], 1.0, abs_tol=1e-9)
