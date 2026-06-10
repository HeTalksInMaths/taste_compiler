"""Stage5to8Orchestrator: Sequential execution of Stages 5–8 reasoning pipeline."""

import json
import os
from dataclasses import asdict

from evalweaver.artifacts import log, save
from evalweaver.providers.bedrock_claude_provider import BedrockClaudeProvider
from evalweaver.stage_models import (
    StageResult, EvalResult,
    STAGE_5_HARD_GATES, STAGE_5_SOFT_TARGETS,
    STAGE_6_HARD_GATES, STAGE_6_SOFT_TARGETS,
    STAGE_7_HARD_GATES, STAGE_7_SOFT_TARGETS,
    STAGE_8_HARD_GATES, STAGE_8_SOFT_TARGETS,
    SMOKE_TEXTS, check_pass_criteria, check_soft_targets,
)
from evalweaver.stage_prompts import (
    build_stage_5_prompt, build_stage_7_prompt, build_stage_8_prompt,
)
from evalweaver.stage_eval import eval_stage_5, eval_stage_6, eval_stage_7, eval_stage_8
from evalweaver.stage6_runner import run_stage_6
from evalweaver.stages import _repair_truncated_json, write_failure_points


STAGE_NAMES_5_8 = {
    5: "Evaluation Pair Generation",
    6: "Deterministic Scorer Evaluation",
    7: "Failure Packet Generation",
    8: "Repair Scorer Generation",
}


class Stage5to8Orchestrator:
    """Runs Stages 5–8 sequentially with fail-fast, artifact persistence, and data threading."""

    def __init__(self, provider: BedrockClaudeProvider, config: dict, out_dir: str,
                 stage2_output: dict, stage3_output: dict, stage4_output: dict):
        self.provider = provider
        self.config = config
        self.out_dir = out_dir
        self.stage2_output = stage2_output
        self.stage3_output = stage3_output
        self.stage4_output = stage4_output
        self.target_variable = config.get("goal", config.get("target_variable", "trustworthy"))
        self.anchor = config.get("raw_text", "")
        self.heldout_count = config.get("heldout_count", 3)
        self.source_policy = config.get("source_policy", {})
        self.stage_results: list[tuple[StageResult, EvalResult]] = []

    def run(self) -> dict:
        """Execute all 4 stages (5–8). Returns summary dict."""
        log("stages_5_8", f"Starting Stages 5–8 pipeline for target_variable={self.target_variable}")

        # --- Stage 5: Pair Generation (LLM) ---
        stage5_result = self._run_stage_5()
        stage5_eval = self._eval_and_persist_stage5(stage5_result)
        if not stage5_eval.passed:
            return self._fail_summary(5)

        # Assign splits to pairs
        stage5_parsed = stage5_result.parsed_json
        self._assign_splits(stage5_parsed)

        # --- Stage 6: Deterministic Scorer Evaluation (No LLM) ---
        stage6_result, stage6_data = self._run_stage_6(stage5_parsed)
        stage6_eval = self._eval_and_persist_stage6(stage6_result, stage6_data)
        if not stage6_eval.passed:
            return self._fail_summary(6)

        # --- Stage 7: Failure Packet Generation (LLM) ---
        stage7_result = self._run_stage_7(stage5_parsed, stage6_data)
        stage7_eval = self._eval_and_persist_stage7(stage7_result, stage5_parsed)
        if not stage7_eval.passed:
            return self._fail_summary(7)

        # --- Stage 8: Repair Scorer Generation (LLM) ---
        stage8_result = self._run_stage_8(stage7_result.parsed_json)
        stage8_eval = self._eval_and_persist_stage8(stage8_result, stage7_result.parsed_json)
        if not stage8_eval.passed:
            return self._fail_summary(8)

        log("stages_5_8", "All Stages 5–8 passed!", "ok")
        self._write_failure_points()
        return {
            "success": True,
            "stages_passed": 4,
            "stage_signals": {i + 5: sr[1].signals for i, sr in enumerate(self.stage_results)},
        }

    def _assign_splits(self, stage5_parsed: dict):
        """Assign splits to Stage 5 pairs: last heldout_count pairs get split='heldout', rest 'train'."""
        pairs = stage5_parsed.get("pairs", [])
        n = len(pairs)
        heldout_start = max(0, n - self.heldout_count)
        for i, p in enumerate(pairs):
            p["split"] = "heldout" if i >= heldout_start else "train"

    def _run_stage_5(self) -> StageResult:
        """Execute Stage 5: Evaluation Pair Generation."""
        causal_graph = self.stage2_output
        measurement_research = self.stage3_output.get("measurement_research", [])
        scorers = self.stage4_output.get("scorers", [])

        system, user = build_stage_5_prompt(
            self.target_variable, causal_graph, measurement_research, scorers, self.source_policy
        )
        return self._call_provider(5, system, user)

    def _run_stage_6(self, stage5_parsed: dict) -> tuple:
        """Execute Stage 6: Deterministic Scorer Evaluation (no LLM)."""
        scorers = self.stage4_output.get("scorers", [])
        stage6_data = run_stage_6(scorers, stage5_parsed, self.anchor)

        # Wrap in StageResult (no prompt, no raw_response since it's deterministic)
        result = StageResult(
            stage_num=6,
            stage_name=STAGE_NAMES_5_8[6],
            prompt={"system": "", "user": ""},
            raw_response="",
            parsed_json=stage6_data,
            parse_error=None,
            call_meta={"latency_ms": 0, "retry_mode": "none", "max_attempts": 0, "error": None},
        )
        return result, stage6_data

    def _run_stage_7(self, stage5_parsed: dict, stage6_data: dict) -> StageResult:
        """Execute Stage 7: Failure Packet Generation."""
        pairs = stage5_parsed.get("pairs", [])
        train_pairs = [p for p in pairs if p.get("split") == "train"]
        heldout_pairs = [p for p in pairs if p.get("split") == "heldout"]

        scorer_summaries = stage6_data.get("scorer_summaries", [])
        pareto_frontier = stage6_data.get("pareto_frontier", [])
        scorer_evaluations = stage6_data.get("scorer_evaluations", {})

        # Build train eval rows (flatten)
        train_eval_rows = []
        for scorer_id, rows in scorer_evaluations.items():
            for row in rows:
                if row.get("split") == "train":
                    train_eval_rows.append({**row, "scorer_id": scorer_id})

        # Heldout aggregate only (no raw text)
        heldout_aggregate = {
            "heldout_accuracy_by_scorer": {
                s["scorer_id"]: s["heldout_accuracy"]
                for s in scorer_summaries if s.get("heldout_accuracy") is not None
            },
            "heldout_mean_gap_by_scorer": {
                s["scorer_id"]: s["heldout_mean_gap"]
                for s in scorer_summaries if s.get("heldout_mean_gap") is not None
            },
        }

        causal_graph = self.stage2_output
        measurement_research = self.stage3_output.get("measurement_research", [])

        system, user = build_stage_7_prompt(
            self.target_variable,
            scorer_summaries,
            train_eval_rows,
            pareto_frontier,
            train_pairs,
            causal_graph,
            measurement_research,
            heldout_aggregate,
        )
        return self._call_provider(7, system, user)

    def _run_stage_8(self, stage7_parsed: dict) -> StageResult:
        """Execute Stage 8: Repair Scorer Generation."""
        causal_graph = self.stage2_output
        measurement_research = self.stage3_output.get("measurement_research", [])
        prior_scorers = self.stage4_output.get("scorers", [])

        system, user = build_stage_8_prompt(
            self.target_variable, causal_graph, measurement_research, prior_scorers, stage7_parsed
        )
        return self._call_provider(8, system, user)

    def _call_provider(self, stage_num: int, system: str, user: str) -> StageResult:
        """Call Bedrock provider and parse JSON response."""
        log("stages_5_8", f"Stage {stage_num}: calling provider...")
        prompt = {"system": system, "user": user}

        try:
            raw_response = self.provider._converse(system, user)
            call_meta = self.provider.last_call_meta or {
                "latency_ms": 0, "retry_mode": "standard", "max_attempts": 5, "error": None
            }
        except Exception as e:
            call_meta = self.provider.last_call_meta or {
                "latency_ms": 0, "retry_mode": "standard", "max_attempts": 5, "error": str(e)
            }
            return StageResult(
                stage_num=stage_num,
                stage_name=STAGE_NAMES_5_8[stage_num],
                prompt=prompt,
                raw_response="",
                parsed_json=None,
                parse_error=str(e),
                call_meta=call_meta,
            )

        # Parse JSON
        try:
            parsed = self.provider._parse_json_response(raw_response)
        except (json.JSONDecodeError, Exception) as e:
            # Try to repair truncated JSON
            try:
                parsed = _repair_truncated_json(raw_response)
            except Exception:
                return StageResult(
                    stage_num=stage_num,
                    stage_name=STAGE_NAMES_5_8[stage_num],
                    prompt=prompt,
                    raw_response=raw_response,
                    parsed_json=None,
                    parse_error=f"JSON parse error: {e}",
                    call_meta=call_meta,
                )

        return StageResult(
            stage_num=stage_num,
            stage_name=STAGE_NAMES_5_8[stage_num],
            prompt=prompt,
            raw_response=raw_response,
            parsed_json=parsed,
            parse_error=None,
            call_meta=call_meta,
        )

    def _eval_and_persist_stage5(self, result: StageResult) -> EvalResult:
        """Evaluate Stage 5 output and persist artifacts."""
        if result.parse_error or result.parsed_json is None:
            eval_result = EvalResult(
                signals={"parse_error": result.parse_error},
                passed=False,
                failures=[{"signal": "parse", "value": "error", "threshold": "valid_json", "op": "=="}],
            )
            self.stage_results.append((result, eval_result))
            self._persist_artifacts(result, eval_result)
            return eval_result

        stage2_nodes = self.stage2_output.get("causal_nodes", [])
        eval_result = eval_stage_5(result.parsed_json, STAGE_5_HARD_GATES, stage2_nodes)
        soft_misses = check_soft_targets(eval_result.signals, STAGE_5_SOFT_TARGETS)
        eval_result.soft_evals = soft_misses

        self.stage_results.append((result, eval_result))
        self._persist_artifacts(result, eval_result)
        self._log_eval(5, eval_result)
        return eval_result

    def _eval_and_persist_stage6(self, result: StageResult, stage6_data: dict) -> EvalResult:
        """Evaluate Stage 6 output and persist artifacts."""
        scorer_summaries = stage6_data.get("scorer_summaries", [])
        pareto_frontier = stage6_data.get("pareto_frontier", [])
        eval_rows = stage6_data.get("scorer_evaluations", {})

        eval_result = eval_stage_6(scorer_summaries, pareto_frontier, eval_rows, STAGE_6_HARD_GATES)
        soft_misses = check_soft_targets(eval_result.signals, STAGE_6_SOFT_TARGETS)
        eval_result.soft_evals = soft_misses

        self.stage_results.append((result, eval_result))
        self._persist_artifacts(result, eval_result)
        self._log_eval(6, eval_result)
        return eval_result

    def _eval_and_persist_stage7(self, result: StageResult, stage5_parsed: dict) -> EvalResult:
        """Evaluate Stage 7 output and persist artifacts."""
        if result.parse_error or result.parsed_json is None:
            eval_result = EvalResult(
                signals={"parse_error": result.parse_error},
                passed=False,
                failures=[{"signal": "parse", "value": "error", "threshold": "valid_json", "op": "=="}],
            )
            self.stage_results.append((result, eval_result))
            self._persist_artifacts(result, eval_result)
            return eval_result

        # Get heldout pairs for leakage detection
        pairs = stage5_parsed.get("pairs", [])
        heldout_pairs = [p for p in pairs if p.get("split") == "heldout"]

        eval_result = eval_stage_7(result.parsed_json, STAGE_7_HARD_GATES, heldout_pairs)
        soft_misses = check_soft_targets(eval_result.signals, STAGE_7_SOFT_TARGETS)
        eval_result.soft_evals = soft_misses

        self.stage_results.append((result, eval_result))
        self._persist_artifacts(result, eval_result)
        self._log_eval(7, eval_result)
        return eval_result

    def _eval_and_persist_stage8(self, result: StageResult, stage7_parsed: dict) -> EvalResult:
        """Evaluate Stage 8 output and persist artifacts."""
        if result.parse_error or result.parsed_json is None:
            eval_result = EvalResult(
                signals={"parse_error": result.parse_error},
                passed=False,
                failures=[{"signal": "parse", "value": "error", "threshold": "valid_json", "op": "=="}],
            )
            self.stage_results.append((result, eval_result))
            self._persist_artifacts(result, eval_result)
            return eval_result

        stage2_nodes = self.stage2_output.get("causal_nodes", [])
        stage7_patterns = stage7_parsed.get("failure_patterns", [])

        eval_result = eval_stage_8(
            result.parsed_json, STAGE_8_HARD_GATES, stage2_nodes, stage7_patterns, SMOKE_TEXTS, self.anchor
        )
        soft_misses = check_soft_targets(eval_result.signals, STAGE_8_SOFT_TARGETS)
        eval_result.soft_evals = soft_misses

        self.stage_results.append((result, eval_result))
        self._persist_artifacts(result, eval_result)
        self._log_eval(8, eval_result)
        return eval_result

    def _log_eval(self, stage_num: int, eval_result: EvalResult):
        """Log eval results for a stage."""
        status = "ok" if eval_result.passed else "error"
        log("stages_5_8", f"Stage {stage_num} eval: {'PASS (hard gates)' if eval_result.passed else 'FAIL (hard gate)'}", status)
        if eval_result.failures:
            for f in eval_result.failures:
                log("stages_5_8", f"  HARD FAIL: {f['signal']} = {f['value']} (need {f['op']} {f['threshold']})", "error")
        if eval_result.soft_evals:
            for s in eval_result.soft_evals:
                log("stages_5_8", f"  soft miss: {s['signal']} = {s['value']:.3f} (target: {s['target']})", "warn")

    def _persist_artifacts(self, result: StageResult, eval_result: EvalResult):
        """Save all artifacts for a stage."""
        prefix = f"stage{result.stage_num}"
        save(f"{prefix}_prompt", result.prompt, self.out_dir)
        save(f"{prefix}_raw_response", {"text": result.raw_response}, self.out_dir)
        if result.parsed_json:
            save(f"{prefix}_parsed_json", result.parsed_json, self.out_dir)
        save(f"{prefix}_eval_result", eval_result.to_dict(), self.out_dir)
        save(f"{prefix}_call_meta", result.call_meta, self.out_dir)

    def _fail_summary(self, failed_stage: int) -> dict:
        """Generate failure summary and write failure_points.md."""
        log("stages_5_8", f"Pipeline halted at Stage {failed_stage}", "error")
        self._write_failure_points()
        return {
            "success": False,
            "failed_stage": failed_stage,
            "stages_passed": failed_stage - 5,
            "stage_signals": {i + 5: sr[1].signals for i, sr in enumerate(self.stage_results)},
        }

    def _write_failure_points(self):
        """Write failure_points.md summarizing all stage results."""
        write_failure_points(self.out_dir, self.stage_results)
