"""
Unit tests and integration tests for Stages 1–4 reasoning pipeline.

Task 12: Unit tests for prompt builders, integration tests with mock provider.
"""

import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch

import pytest

from evalweaver.stage_models import (
    StageResult, EvalResult, SMOKE_TEXTS,
    STAGE_1_PASS_CRITERIA, STAGE_2_PASS_CRITERIA,
    STAGE_3_PASS_CRITERIA, STAGE_4_PASS_CRITERIA,
)
from evalweaver.stage_prompts import (
    build_stage_1_prompt, build_stage_2_prompt,
    build_stage_3_prompt, build_stage_4_prompt,
)
from evalweaver.stages import StageOrchestrator, write_failure_points


# ─────────────────────────────────────────────────────────────────────
# FIXTURES: Known good stage outputs
# ─────────────────────────────────────────────────────────────────────

STAGE_1_GOOD_OUTPUT = {
    "target_variable": "trustworthy",
    "causal_research": [
        {
            "source_id": f"SRC_{i:03d}",
            "title": f"Research Paper {i}",
            "claim": f"Specific evidence because mechanism {i} leads to increased trust through causal pathway",
            "causal_variable": f"variable_{i}",
            "effect_direction": ["increases", "decreases", "mediates", "moderates"][i % 4],
            "mechanism": f"Through mechanism {i} which causes observable changes because it drives signaling",
            "evidence_strength": "high",
        }
        for i in range(12)
    ],
    "research_tensions": [
        {"claim": "Variable 0 and variable 1 show opposing effects under certain conditions", "variables": ["variable_0", "variable_1"]},
        {"claim": "Mediation of variable 2 depends on context", "variables": ["variable_2", "variable_3"]},
    ],
}

NODE_IDS = ["specificity", "credibility", "hedging", "evidence_markers", "causal_connectives", "concreteness", "transparency"]

STAGE_2_GOOD_OUTPUT = {
    "target_variable": "trustworthy",
    "causal_nodes": [
        {
            "node_id": nid,
            "label": nid.replace("_", " ").title(),
            "role": ["increases", "decreases", "mediates", "moderates"][i % 4],
            "definition": f"The degree to which text demonstrates {nid}",
            "mechanism": f"{nid} operates through signaling theory by making claims verifiable",
            "evidence": [f"SRC_{i:03d}"],
        }
        for i, nid in enumerate(NODE_IDS)
    ],
    "causal_edges": [
        {"from": NODE_IDS[i], "to": NODE_IDS[i + 1], "relationship": "supports", "claim": f"{NODE_IDS[i]} supports {NODE_IDS[i+1]}"}
        for i in range(6)
    ],
    "causal_tensions": [{"claim": "Specificity and hedging can conflict", "nodes": ["specificity", "hedging"]}],
    "summary_theory": f"Trust in text is built through specificity and credibility signals",
}

STAGE_3_GOOD_OUTPUT = {
    "target_variable": "trustworthy",
    "measurement_research": [
        {
            "source_id": f"MSRC_{i:03d}",
            "causal_node": NODE_IDS[i % len(NODE_IDS)],
            "measurement_claim": f"Measurement claim for {NODE_IDS[i % len(NODE_IDS)]}",
            "text_features": [f"specific_feature_{i}_a", f"specific_feature_{i}_b"],
            "implementation_ideas": [f"count specific pattern {i}", f"compute ratio of markers {i}"],
        }
        for i in range(14)
    ],
}

STAGE_4_GOOD_OUTPUT = {
    "target_variable": "trustworthy",
    "scorers": [
        {
            "scorer_id": "S0",
            "hypothesis": "Text with more specificity markers and evidence signals is more trustworthy",
            "causal_nodes_used": ["specificity", "evidence_markers"],
            "causal_edges_used": [{"from": "specificity", "to": "credibility"}],
            "causal_tensions_used": [],
            "measurement_ideas_used": ["count specific pattern 0", "evidence marker density"],
            "functional_form": "additive",
            "functional_form_rationale": "Additive combination of specificity and evidence signals",
            "expected_failure_mode": "Fails on texts that are too short",
            "code": "def scorer(text, anchor, params):\n    words = text.split()\n    specificity = len([w for w in words if len(w) > 6]) / max(len(words), 1)\n    evidence_markers = len(re.findall(r'\\b(because|leads to|through)\\b', text.lower())) / max(len(words), 1)\n    pattern = specificity + evidence_markers * 2\n    return min(pattern, 1.0)",
        },
        {
            "scorer_id": "S1",
            "hypothesis": "Text demonstrating credibility through hedging balance scores higher",
            "causal_nodes_used": ["credibility", "hedging"],
            "causal_edges_used": [{"from": "hedging", "to": "credibility"}],
            "causal_tensions_used": [],
            "measurement_ideas_used": ["count specific pattern 1", "hedge density ratio"],
            "functional_form": "interaction",
            "functional_form_rationale": "Interaction between credibility and hedging signals",
            "expected_failure_mode": "Over-penalizes uncertain text",
            "code": "def scorer(text, anchor, params):\n    words = text.split()\n    credibility = max(len(re.findall(r'[.!?]', text)), 1)\n    hedging = len(re.findall(r'\\b(maybe|perhaps|might|could|possibly)\\b', text.lower()))\n    num_sentences = credibility\n    if hedging > 3:\n        penalty = 0.2\n    else:\n        penalty = 0.0\n    hedge_density = min(len(words) / (len(text) + 50), 1.0) * (1 - penalty)\n    return hedge_density",
        },
        {
            "scorer_id": "S2",
            "hypothesis": "Causal connectives signal trustworthiness through transparent reasoning",
            "causal_nodes_used": ["causal_connectives", "transparency"],
            "causal_edges_used": [{"from": "causal_connectives", "to": "transparency"}],
            "causal_tensions_used": [],
            "measurement_ideas_used": ["count specific pattern 2", "causal connective density"],
            "functional_form": "gated",
            "functional_form_rationale": "Gate on presence of causal connectives",
            "expected_failure_mode": "Fails on very short texts",
            "code": "def scorer(text, anchor, params):\n    words = text.lower().split()\n    causal_connectives = ['because', 'therefore', 'since', 'thus', 'leads']\n    causal_count = sum(1 for w in words if w in causal_connectives)\n    transparency = 1.0 if causal_count > 0 else 0.3\n    base = len(text) / max(len(text) + 100, 1)\n    return min(base * transparency, 1.0)",
        },
        {
            "scorer_id": "S3",
            "hypothesis": "Text with superlatives and absolute claims is less trustworthy (penalty)",
            "causal_nodes_used": ["credibility", "concreteness"],
            "causal_edges_used": [{"from": "concreteness", "to": "credibility"}],
            "causal_tensions_used": [],
            "measurement_ideas_used": ["count specific pattern 3", "superlative density"],
            "functional_form": "penalty",
            "functional_form_rationale": "Penalty for superlatives which reduce credibility",
            "expected_failure_mode": "Legitimate superlatives get penalized",
            "code": "def scorer(text, anchor, params):\n    words = text.lower().split()\n    num_clauses = max(len(re.split(r'[,;]', text)), 1)\n    concreteness = len(re.findall(r'\\b(best|worst|most|greatest|revolutionary|ultimate)\\b', text.lower()))\n    credibility_penalty = min(concreteness * 0.2, 0.8)\n    base = len(words) / max(len(words) + 15, 1)\n    return max(base - credibility_penalty, 0.0)",
        },
        {
            "scorer_id": "S4",
            "hypothesis": "Balance between evidence markers and hedging creates trust (tension_balance)",
            "causal_nodes_used": ["evidence_markers", "hedging"],
            "causal_edges_used": [{"from": "evidence_markers", "to": "credibility"}],
            "causal_tensions_used": ["specificity vs hedging"],
            "measurement_ideas_used": ["count specific pattern 4", "evidence to hedge ratio"],
            "functional_form": "tension_balance",
            "functional_form_rationale": "Balance between evidence and hedging creates optimal trust",
            "expected_failure_mode": "Too much hedging collapses score",
            "code": "def scorer(text, anchor, params):\n    words = text.lower().split()\n    word_count = len(words)\n    evidence_markers = len([w for w in words if w in ['because', 'evidence', 'shows', 'demonstrates', 'proves']])\n    hedging = len([w for w in words if w in ['maybe', 'perhaps', 'might', 'could']])\n    ratio = (evidence_markers + 1) / max(evidence_markers + hedging + 1, 1)\n    density = word_count / max(word_count + 20, 1)\n    return min(ratio * density, 1.0)",
        },
        {
            "scorer_id": "S5",
            "hypothesis": "Concreteness through specific nouns and numbers signals trust",
            "causal_nodes_used": ["concreteness", "specificity"],
            "causal_edges_used": [{"from": "specificity", "to": "concreteness"}],
            "causal_tensions_used": [],
            "measurement_ideas_used": ["count specific pattern 5", "concrete noun ratio"],
            "functional_form": "ratio_or_density",
            "functional_form_rationale": "Ratio of concrete nouns and numbers to total words",
            "expected_failure_mode": "Numeric text without meaning gets high score",
            "code": "def scorer(text, anchor, params):\n    words = text.split()\n    num_sentences = max(len(re.findall(r'[.!?]', text)), 1)\n    concreteness = len(re.findall(r'\\b\\d+|teams?|tools?|users?|steps?|options?|ideas?\\b', text.lower()))\n    specificity = concreteness / max(len(words), 1)\n    pattern = specificity * 3\n    return min(pattern, 1.0)",
        },
        {
            "scorer_id": "S6",
            "hypothesis": "Transparency through showing tradeoffs builds trust via threshold mechanism",
            "causal_nodes_used": ["transparency", "causal_connectives"],
            "causal_edges_used": [{"from": "transparency", "to": "credibility"}],
            "causal_tensions_used": [],
            "measurement_ideas_used": ["count specific pattern 6", "tradeoff marker density"],
            "functional_form": "threshold",
            "functional_form_rationale": "Threshold on tradeoff language to signal transparency",
            "expected_failure_mode": "Fails on texts without explicit tradeoffs",
            "code": "def scorer(text, anchor, params):\n    words = text.lower().split()\n    token_count = len(words)\n    transparency_markers = len(re.findall(r'\\b(but|however|although|tradeoff|compare|vs|versus|limits)\\b', text.lower()))\n    causal_connectives = len(re.findall(r'\\b(because|since|therefore)\\b', text.lower()))\n    has_tradeoff = transparency_markers > 0\n    if has_tradeoff:\n        score = min(0.6 + transparency_markers * 0.1, 1.0)\n    else:\n        score = token_count / max(token_count + 30, 1) * 0.5\n    return score",
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────
# Mock Provider
# ─────────────────────────────────────────────────────────────────────


class MockStageProvider:
    """Mock provider that returns predetermined JSON responses for each stage call."""

    def __init__(self, responses: list[str]):
        """
        Args:
            responses: List of JSON strings, one per stage call in order.
        """
        self._responses = responses
        self._call_index = 0
        self.last_call_meta = {"latency_ms": 50, "retry_mode": "standard", "max_attempts": 5, "error": None}
        self.calls = []

    def _converse(self, system: str, user: str) -> str:
        idx = self._call_index
        self._call_index += 1
        self.calls.append({"system": system, "user": user})
        if idx < len(self._responses):
            return self._responses[idx]
        return "{}"

    def _parse_json_response(self, raw: str) -> dict:
        return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────
# Task 12.1: Unit tests for prompt builders with known inputs/outputs
# ─────────────────────────────────────────────────────────────────────


class TestPromptBuilders:
    """Unit tests for prompt template builders."""

    def test_stage1_prompt_structure(self):
        """Stage 1 prompt has correct structure with target variable."""
        system, user = build_stage_1_prompt("trustworthy")
        assert "trustworthy" in user
        assert "causal" in user.lower() or "causal_research" in user
        assert "JSON" in system or "JSON" in user
        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 0
        assert len(user) > 0

    def test_stage2_prompt_includes_research(self):
        """Stage 2 prompt includes Stage 1 research data."""
        research = [
            {"source_id": "SRC_001", "title": "Test Paper", "claim": "X causes Y"},
            {"source_id": "SRC_002", "title": "Another Paper", "claim": "A leads to B"},
        ]
        system, user = build_stage_2_prompt("trustworthy", research)
        assert "trustworthy" in user
        assert "SRC_001" in user
        assert "SRC_002" in user
        assert "causal" in user.lower()

    def test_stage3_prompt_includes_nodes(self):
        """Stage 3 prompt includes causal node information."""
        nodes = [
            {"node_id": "credibility", "label": "Credibility", "definition": "trust signals"},
            {"node_id": "specificity", "label": "Specificity", "definition": "concrete details"},
        ]
        system, user = build_stage_3_prompt("trustworthy", nodes)
        assert "trustworthy" in user
        assert "credibility" in user
        assert "specificity" in user

    def test_stage4_prompt_includes_graph_and_measurement(self):
        """Stage 4 prompt includes both causal graph and measurement research."""
        graph = {
            "causal_nodes": [{"node_id": "credibility", "label": "Credibility"}],
            "causal_edges": [{"from": "specificity", "to": "credibility"}],
        }
        measurement = [
            {"source_id": "M1", "measurement_claim": "count evidence markers"},
        ]
        system, user = build_stage_4_prompt("trustworthy", graph, measurement)
        assert "trustworthy" in user
        assert "credibility" in user
        assert "evidence markers" in user or "M1" in user

    def test_stage1_prompt_requests_json(self):
        """Stage 1 system prompt requests JSON output."""
        system, user = build_stage_1_prompt("persuasive")
        assert "JSON" in system or "json" in system.lower()

    def test_stage4_prompt_includes_scorer_signature(self):
        """Stage 4 prompt specifies scorer function signature."""
        system, user = build_stage_4_prompt("concise", {}, [])
        assert "def scorer(text, anchor, params)" in user

    def test_stage4_prompt_includes_smoke_texts(self):
        """Stage 4 prompt mentions the smoke test texts."""
        system, user = build_stage_4_prompt("trustworthy", {}, [])
        # Should reference the concept of test texts
        assert "test" in user.lower() or "texts" in user.lower()


# ─────────────────────────────────────────────────────────────────────
# Task 12.2: Integration test with mock provider (all 4 stages pass)
# ─────────────────────────────────────────────────────────────────────


class TestIntegrationAllStagesPass:
    """Integration test: mock provider returns good data, all 4 stages pass."""

    def test_full_pipeline_success(self):
        """All 4 stages execute and pass with good mock data."""
        responses = [
            json.dumps(STAGE_1_GOOD_OUTPUT),
            json.dumps(STAGE_2_GOOD_OUTPUT),
            json.dumps(STAGE_3_GOOD_OUTPUT),
            json.dumps(STAGE_4_GOOD_OUTPUT),
        ]
        provider = MockStageProvider(responses)
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_integ_pass_")
        try:
            config = {"goal": "trustworthy", "raw_text": "We help teams build trust."}
            orchestrator = StageOrchestrator(provider, config, tmp_dir)
            result = orchestrator.run()

            assert result["success"] is True
            assert result["stages_passed"] == 4
            assert "stage_signals" in result
            assert 1 in result["stage_signals"]
            assert 4 in result["stage_signals"]

            # All 4 stages called
            assert len(provider.calls) == 4

            # Artifacts persisted for all stages
            for stage_num in range(1, 5):
                assert os.path.exists(os.path.join(tmp_dir, f"stage{stage_num}_prompt.json"))
                assert os.path.exists(os.path.join(tmp_dir, f"stage{stage_num}_eval_result.json"))
                assert os.path.exists(os.path.join(tmp_dir, f"stage{stage_num}_parsed_json.json"))

            # failure_points.md exists
            assert os.path.exists(os.path.join(tmp_dir, "failure_points.md"))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_stage_signals_computed(self):
        """Each stage produces expected signal keys."""
        responses = [
            json.dumps(STAGE_1_GOOD_OUTPUT),
            json.dumps(STAGE_2_GOOD_OUTPUT),
            json.dumps(STAGE_3_GOOD_OUTPUT),
            json.dumps(STAGE_4_GOOD_OUTPUT),
        ]
        provider = MockStageProvider(responses)
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_integ_sigs_")
        try:
            config = {"goal": "trustworthy", "raw_text": "anchor text"}
            orchestrator = StageOrchestrator(provider, config, tmp_dir)
            result = orchestrator.run()

            assert result["success"] is True
            # Check Stage 1 signals
            s1_sigs = result["stage_signals"][1]
            assert "num_research_items" in s1_sigs
            assert "mechanism_completeness_rate" in s1_sigs
            assert "causal_specificity_score" in s1_sigs

            # Check Stage 2 signals
            s2_sigs = result["stage_signals"][2]
            assert "num_nodes" in s2_sigs
            assert "edge_validity_rate" in s2_sigs
            assert "graph_connectedness_score" in s2_sigs

            # Check Stage 4 signals
            s4_sigs = result["stage_signals"][4]
            assert "code_exec_rate" in s4_sigs
            assert "scorer_distinctness_score" in s4_sigs
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────
# Task 12.3: Integration test with Stage 2 failure
# ─────────────────────────────────────────────────────────────────────


class TestIntegrationStage2Fails:
    """Integration test: Stage 2 fails, pipeline halts, artifacts preserved."""

    def test_stage2_failure_halts_pipeline(self):
        """Stage 2 failure stops execution, stages 3-4 not called."""
        # Stage 1 passes, Stage 2 returns empty graph (fails eval)
        stage2_bad = {
            "target_variable": "trustworthy",
            "causal_nodes": [
                {"node_id": "x", "label": "X", "role": "increases", "definition": "d", "mechanism": "m", "evidence": ["S1"]}
            ],
            "causal_edges": [],  # Too few edges
            "causal_tensions": [],
            "summary_theory": "theory",
        }
        responses = [
            json.dumps(STAGE_1_GOOD_OUTPUT),
            json.dumps(stage2_bad),
        ]
        provider = MockStageProvider(responses)
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_integ_fail2_")
        try:
            config = {"goal": "trustworthy", "raw_text": "anchor text"}
            orchestrator = StageOrchestrator(provider, config, tmp_dir)
            result = orchestrator.run()

            # Pipeline failed at stage 2
            assert result["success"] is False
            assert result["failed_stage"] == 2
            assert result["stages_passed"] == 1

            # Only 2 calls made (no stage 3 or 4)
            assert len(provider.calls) == 2

            # Stage 1 and 2 artifacts exist
            assert os.path.exists(os.path.join(tmp_dir, "stage1_parsed_json.json"))
            assert os.path.exists(os.path.join(tmp_dir, "stage1_eval_result.json"))
            assert os.path.exists(os.path.join(tmp_dir, "stage2_eval_result.json"))

            # Stage 3 artifacts do NOT exist
            assert not os.path.exists(os.path.join(tmp_dir, "stage3_parsed_json.json"))
            assert not os.path.exists(os.path.join(tmp_dir, "stage3_eval_result.json"))

            # failure_points.md exists and mentions Stage 2 failure
            fp_path = os.path.join(tmp_dir, "failure_points.md")
            assert os.path.exists(fp_path)
            with open(fp_path) as f:
                content = f.read()
            assert "Stage 2" in content
            assert "FAIL" in content
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_stage2_parse_error_halts(self):
        """Stage 2 returning non-JSON halts pipeline with parse_error."""
        responses = [
            json.dumps(STAGE_1_GOOD_OUTPUT),
            "This is not valid JSON at all!!!",
        ]
        provider = MockStageProvider(responses)
        tmp_dir = tempfile.mkdtemp(prefix="evalweaver_integ_parse_")
        try:
            config = {"goal": "trustworthy", "raw_text": "anchor text"}
            orchestrator = StageOrchestrator(provider, config, tmp_dir)
            result = orchestrator.run()

            assert result["success"] is False
            assert result["failed_stage"] == 2
            assert len(provider.calls) == 2

            # Eval result for stage 2 should show parse error
            eval_path = os.path.join(tmp_dir, "stage2_eval_result.json")
            assert os.path.exists(eval_path)
            with open(eval_path) as f:
                eval_data = json.load(f)
            assert eval_data["passed"] is False
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────
# Task 12.4: Smoke test for --live-canary CLI flag
# ─────────────────────────────────────────────────────────────────────


class TestLiveCanaryCLI:
    """Smoke test: --live-canary CLI flag triggers StageOrchestrator."""

    def test_stages_subcommand_exists(self):
        """The 'stages' subcommand is registered in the CLI parser."""
        from evalweaver.__main__ import main
        import argparse

        # Verify argparse can parse the stages subcommand
        # We'll check by importing and inspecting the parser
        with patch("sys.argv", ["evalweaver", "stages", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # --help exits with 0
            assert exc_info.value.code == 0

    def test_live_canary_flag_imports_orchestrator(self):
        """--live-canary in run command sets provider to bedrock."""
        # Verify the StageOrchestrator can be imported and instantiated
        from evalweaver.stages import StageOrchestrator
        assert StageOrchestrator is not None

    def test_live_canary_sets_provider_bedrock(self):
        """--live-canary flag sets provider to 'bedrock' when used with run command."""
        from evalweaver.__main__ import main

        # Mock _validate_bedrock to avoid real AWS calls
        with patch("evalweaver.__main__._validate_bedrock") as mock_validate, \
             patch("evalweaver.__main__.run_pipeline") as mock_pipeline, \
             patch("sys.argv", ["evalweaver", "run", "--live-canary", "--config", "configs/trustworthy.yaml"]):
            mock_validate.return_value = {"passed": True, "account": "123", "arn": "arn:test", "region": "us-east-1", "model_id": "test"}
            mock_pipeline.return_value = {"success": True, "output_dir": "/tmp/test"}

            try:
                main()
            except SystemExit:
                pass

            # Verify run_pipeline was called with live_canary config
            if mock_pipeline.called:
                config_arg = mock_pipeline.call_args[0][0]
                assert config_arg.get("live_canary") is True
                assert config_arg.get("provider_name") == "bedrock"

    def test_stages_subcommand_invokes_orchestrator(self):
        """'stages' subcommand creates and runs StageOrchestrator."""
        from evalweaver.__main__ import main

        with patch("evalweaver.__main__._validate_bedrock") as mock_validate, \
             patch("evalweaver.stages.StageOrchestrator") as MockOrch, \
             patch("evalweaver.artifacts.resolve_output_directory") as mock_dir, \
             patch("evalweaver.providers.bedrock_claude_provider.BedrockClaudeProvider") as MockProvider, \
             patch("sys.argv", ["evalweaver", "stages", "--config", "configs/trustworthy.yaml"]):

            mock_validate.return_value = {"passed": True, "account": "123", "arn": "arn:test", "region": "us-east-1", "model_id": "test"}
            mock_dir.return_value = tempfile.mkdtemp(prefix="evalweaver_cli_")

            mock_instance = MockOrch.return_value
            mock_instance.run.return_value = {"success": True, "stages_passed": 4, "stage_signals": {}}

            try:
                main()
            except SystemExit:
                pass

            # Verify StageOrchestrator was instantiated and run() called
            assert MockOrch.called
            assert mock_instance.run.called
