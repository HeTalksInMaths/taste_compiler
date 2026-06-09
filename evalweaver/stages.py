"""StageOrchestrator: Sequential execution of Stages 1–4 reasoning pipeline."""

import json
import os
import time
from dataclasses import asdict

from evalweaver.artifacts import log, save
from evalweaver.providers.bedrock_claude_provider import BedrockClaudeProvider
from evalweaver.stage_models import (
    StageResult, EvalResult,
    STAGE_1_PASS_CRITERIA, STAGE_2_PASS_CRITERIA,
    STAGE_3_PASS_CRITERIA, STAGE_4_PASS_CRITERIA,
    SMOKE_TEXTS, validate_stage_1_output, validate_stage_2_output,
    validate_stage_3_output, validate_stage_4_output,
)
from evalweaver.stage_prompts import (
    build_stage_1_prompt, build_stage_2_prompt,
    build_stage_3_prompt, build_stage_4_prompt,
)
from evalweaver.stage_eval import eval_stage_1, eval_stage_2, eval_stage_3, eval_stage_4


STAGE_NAMES = {
    1: "Causal Research Search",
    2: "Causal Graph Generation",
    3: "Measurement Research Search",
    4: "Scorer Hypothesis and Function Generation",
}


def _repair_truncated_json(raw_response: str) -> dict:
    """Attempt to repair truncated JSON by extracting valid prefix."""
    text = raw_response.strip()
    # Try to extract from code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
        else:
            text = text[start:].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
        else:
            text = text[start:].strip()

    # Try to close open brackets/braces
    # Find the last complete array element by looking for the last '}' before truncation
    open_braces = 0
    open_brackets = 0
    last_valid_pos = 0

    for i, ch in enumerate(text):
        if ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
            if open_braces == 0 and open_brackets == 0:
                last_valid_pos = i + 1
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1
            if open_braces == 0 and open_brackets == 0:
                last_valid_pos = i + 1

    # Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try closing open structures
    repair = text
    if open_brackets > 0 or open_braces > 0:
        # Close at reasonable boundaries
        repair = text.rstrip().rstrip(',')
        repair += ']' * open_brackets + '}' * open_braces

    try:
        return json.loads(repair)
    except json.JSONDecodeError:
        pass

    # Last resort: truncate to last valid position and close
    if last_valid_pos > 10:
        repair = text[:last_valid_pos]
        try:
            return json.loads(repair)
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not repair truncated JSON")


def _select_top_nodes(nodes: list, edges: list, max_nodes: int = 10) -> list:
    """Select the most connected/important nodes for Stage 3 (to avoid token overflow)."""
    if len(nodes) <= max_nodes:
        return nodes
    # Score nodes by edge connectivity
    node_scores = {}
    for n in nodes:
        nid = n.get("node_id", "")
        node_scores[nid] = 0
    for e in edges:
        f, t = e.get("from", ""), e.get("to", "")
        if f in node_scores:
            node_scores[f] += 1
        if t in node_scores:
            node_scores[t] += 1
    # Sort by connectivity, take top N
    sorted_ids = sorted(node_scores, key=lambda x: node_scores[x], reverse=True)[:max_nodes]
    return [n for n in nodes if n.get("node_id") in set(sorted_ids)]


class StageOrchestrator:
    """Runs Stages 1–4 sequentially with fail-fast, artifact persistence, and data threading."""

    def __init__(self, provider: BedrockClaudeProvider, config: dict, out_dir: str):
        self.provider = provider
        self.config = config
        self.out_dir = out_dir
        self.target_variable = config.get("goal", config.get("target_variable", "trustworthy"))
        self.anchor = config.get("raw_text", "")
        self.stage_results: list[tuple[StageResult, EvalResult]] = []
        self.max_stage3_nodes = config.get("max_stage3_nodes", 10)

    def run(self, resume_from: int = None) -> dict:
        """Execute all 4 stages. Returns summary dict. Can resume from a specific stage."""
        log("stages", f"Starting Stages 1–4 pipeline for target_variable={self.target_variable}")

        if resume_from and resume_from > 1:
            # Load previous stage artifacts from disk
            stage1_parsed = self._load_artifact("stage1_parsed_json")
            stage2_parsed = self._load_artifact("stage2_parsed_json")
            if resume_from == 2:
                stage1_result = StageResult(1, STAGE_NAMES[1], {}, "", stage1_parsed, None, {})
                stage1_eval = EvalResult(signals={}, passed=True, failures=[])
                self.stage_results.append((stage1_result, stage1_eval))
            elif resume_from >= 3:
                stage1_result = StageResult(1, STAGE_NAMES[1], {}, "", stage1_parsed, None, {})
                stage1_eval = EvalResult(signals={}, passed=True, failures=[])
                self.stage_results.append((stage1_result, stage1_eval))
                stage2_result = StageResult(2, STAGE_NAMES[2], {}, "", stage2_parsed, None, {})
                stage2_eval = EvalResult(signals={}, passed=True, failures=[])
                self.stage_results.append((stage2_result, stage2_eval))

            if resume_from == 2:
                return self._run_from_stage_2(stage1_parsed)
            elif resume_from == 3:
                return self._run_from_stage_3(stage2_parsed)
            elif resume_from == 4:
                stage3_parsed = self._load_artifact("stage3_parsed_json")
                stage3_result = StageResult(3, STAGE_NAMES[3], {}, "", stage3_parsed, None, {})
                stage3_eval = EvalResult(signals={}, passed=True, failures=[])
                self.stage_results.append((stage3_result, stage3_eval))
                return self._run_from_stage_4(stage2_parsed, stage3_parsed)

        # Full run: Stage 1
        stage1_result = self._run_stage_1()
        stage1_eval = self._eval_and_persist(1, stage1_result, STAGE_1_PASS_CRITERIA)
        if not stage1_eval.passed:
            return self._fail_summary(1)

        return self._run_from_stage_2(stage1_result.parsed_json)

    def _run_from_stage_2(self, stage1_parsed: dict) -> dict:
        """Run from Stage 2 onward."""
        stage2_result = self._run_stage_2(stage1_parsed)
        stage2_eval = self._eval_and_persist(2, stage2_result, STAGE_2_PASS_CRITERIA)
        if not stage2_eval.passed:
            return self._fail_summary(2)

        return self._run_from_stage_3(stage2_result.parsed_json)

    def _run_from_stage_3(self, stage2_parsed: dict) -> dict:
        """Run from Stage 3 onward."""
        stage2_nodes = stage2_parsed.get("causal_nodes", [])
        stage2_edges = stage2_parsed.get("causal_edges", [])
        top_nodes = _select_top_nodes(stage2_nodes, stage2_edges, max_nodes=self.max_stage3_nodes)
        stage3_result = self._run_stage_3(top_nodes)
        stage3_eval = self._eval_and_persist(3, stage3_result, STAGE_3_PASS_CRITERIA, stage2_nodes=top_nodes)
        if not stage3_eval.passed:
            return self._fail_summary(3)

        return self._run_from_stage_4(stage2_parsed, stage3_result.parsed_json)

    def _run_from_stage_4(self, stage2_parsed: dict, stage3_parsed: dict) -> dict:
        """Run Stage 4."""
        # Use ALL stage2 nodes for validation (scorer code references the full graph)
        all_stage2_nodes = stage2_parsed.get("causal_nodes", [])
        stage4_result = self._run_stage_4(stage2_parsed, stage3_parsed)
        stage4_eval = self._eval_and_persist(4, stage4_result, STAGE_4_PASS_CRITERIA, stage2_nodes=all_stage2_nodes)
        if not stage4_eval.passed:
            return self._fail_summary(4)

        log("stages", "All 4 stages passed!", "ok")
        self._write_failure_points()
        return {
            "success": True,
            "stages_passed": 4,
            "stage_signals": {i + 1: sr[1].signals for i, sr in enumerate(self.stage_results)},
        }

    def _load_artifact(self, name: str) -> dict:
        """Load a JSON artifact from the output directory."""
        import json as _json
        path = os.path.join(self.out_dir, f"{name}.json")
        with open(path) as f:
            return _json.load(f)

    def _run_stage_1(self) -> StageResult:
        """Execute Stage 1: Causal Research Search."""
        system, user = build_stage_1_prompt(self.target_variable)
        return self._call_provider(1, system, user)

    def _run_stage_2(self, stage1_output: dict) -> StageResult:
        """Execute Stage 2: Causal Graph Generation."""
        research = stage1_output.get("causal_research", [])
        system, user = build_stage_2_prompt(self.target_variable, research)
        return self._call_provider(2, system, user)

    def _run_stage_3(self, stage2_nodes: list) -> StageResult:
        """Execute Stage 3: Measurement Research Search."""
        system, user = build_stage_3_prompt(self.target_variable, stage2_nodes)
        return self._call_provider(3, system, user)

    def _run_stage_4(self, stage2_output: dict, stage3_output: dict) -> StageResult:
        """Execute Stage 4: Scorer Generation."""
        measurement_research = stage3_output.get("measurement_research", [])
        system, user = build_stage_4_prompt(self.target_variable, stage2_output, measurement_research)
        return self._call_provider(4, system, user)

    def _call_provider(self, stage_num: int, system: str, user: str) -> StageResult:
        """Call Bedrock provider and parse JSON response."""
        log("stages", f"Stage {stage_num}: calling provider...")
        prompt = {"system": system, "user": user}

        try:
            raw_response = self.provider._converse(system, user)
            call_meta = self.provider.last_call_meta or {"latency_ms": 0, "retry_mode": "standard", "max_attempts": 5, "error": None}
        except Exception as e:
            call_meta = self.provider.last_call_meta or {"latency_ms": 0, "retry_mode": "standard", "max_attempts": 5, "error": str(e)}
            return StageResult(
                stage_num=stage_num,
                stage_name=STAGE_NAMES[stage_num],
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
            # Try to repair truncated JSON by closing brackets
            try:
                parsed = _repair_truncated_json(raw_response)
            except Exception:
                return StageResult(
                    stage_num=stage_num,
                    stage_name=STAGE_NAMES[stage_num],
                    prompt=prompt,
                    raw_response=raw_response,
                    parsed_json=None,
                    parse_error=f"JSON parse error: {e}",
                    call_meta=call_meta,
                )

        return StageResult(
            stage_num=stage_num,
            stage_name=STAGE_NAMES[stage_num],
            prompt=prompt,
            raw_response=raw_response,
            parsed_json=parsed,
            parse_error=None,
            call_meta=call_meta,
        )

    def _eval_and_persist(self, stage_num: int, result: StageResult, pass_criteria: dict, stage2_nodes: list = None) -> EvalResult:
        """Evaluate stage output and persist artifacts. Only hard gates block pipeline."""
        from evalweaver.stage_models import (
            check_soft_targets,
            STAGE_1_SOFT_TARGETS, STAGE_2_SOFT_TARGETS,
            STAGE_3_SOFT_TARGETS, STAGE_4_SOFT_TARGETS,
        )

        # If parse failed, create a failing eval
        if result.parse_error or result.parsed_json is None:
            eval_result = EvalResult(
                signals={"parse_error": result.parse_error},
                passed=False,
                failures=[{"signal": "parse", "value": "error", "threshold": "valid_json", "op": "=="}],
            )
            self.stage_results.append((result, eval_result))
            self._persist_artifacts(result, eval_result)
            return eval_result

        # Run appropriate eval (checks hard gates only)
        if stage_num == 1:
            eval_result = eval_stage_1(result.parsed_json, pass_criteria)
            soft_targets = STAGE_1_SOFT_TARGETS
        elif stage_num == 2:
            eval_result = eval_stage_2(result.parsed_json, pass_criteria)
            soft_targets = STAGE_2_SOFT_TARGETS
        elif stage_num == 3:
            eval_result = eval_stage_3(result.parsed_json, pass_criteria, stage2_nodes or [])
            soft_targets = STAGE_3_SOFT_TARGETS
        elif stage_num == 4:
            eval_result = eval_stage_4(result.parsed_json, pass_criteria, stage2_nodes or [], SMOKE_TEXTS, self.anchor)
            soft_targets = STAGE_4_SOFT_TARGETS
        else:
            eval_result = EvalResult(signals={}, passed=False, failures=[])
            soft_targets = {}

        # Compute soft evals (tracked, never block pipeline)
        soft_misses = check_soft_targets(eval_result.signals, soft_targets)
        eval_result.soft_evals = soft_misses

        self.stage_results.append((result, eval_result))
        self._persist_artifacts(result, eval_result)

        status = "ok" if eval_result.passed else "error"
        log("stages", f"Stage {stage_num} eval: {'PASS (hard gates)' if eval_result.passed else 'FAIL (hard gate)'}", status)
        if eval_result.failures:
            for f in eval_result.failures:
                log("stages", f"  HARD FAIL: {f['signal']} = {f['value']} (need {f['op']} {f['threshold']})", "error")
        if soft_misses:
            for s in soft_misses:
                log("stages", f"  soft miss: {s['signal']} = {s['value']:.3f} (target: {s['target']})", "warn")

        return eval_result

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
        log("stages", f"Pipeline halted at Stage {failed_stage}", "error")
        self._write_failure_points()
        return {
            "success": False,
            "failed_stage": failed_stage,
            "stages_passed": failed_stage - 1,
            "stage_signals": {i + 1: sr[1].signals for i, sr in enumerate(self.stage_results)},
        }

    def _write_failure_points(self):
        """Write failure_points.md summarizing all stage results."""
        write_failure_points(self.out_dir, self.stage_results)


def write_failure_points(out_dir: str, stage_results: list[tuple[StageResult, EvalResult]]):
    """Write failure_points.md with pass/fail per stage and specific failed signals."""
    lines = ["# Failure Points Report\n"]
    all_passed = True

    for result, eval_result in stage_results:
        status = "✓ PASS" if eval_result.passed else "✗ FAIL"
        if not eval_result.passed:
            all_passed = False
        lines.append(f"## Stage {result.stage_num}: {result.stage_name} — {status}\n")

        if result.parse_error:
            lines.append(f"**Parse Error:** {result.parse_error}\n")
        elif eval_result.failures:
            lines.append("**Failed Signals:**\n")
            for f in eval_result.failures:
                lines.append(f"- `{f['signal']}` = {f['value']} (required {f['op']} {f['threshold']})")
            lines.append("")
        else:
            lines.append("All signals within thresholds.\n")

    if all_passed:
        lines.insert(1, "\n**Overall: ALL STAGES PASSED**\n")
    else:
        failed_stages = [r[0].stage_num for r in stage_results if not r[1].passed]
        lines.insert(1, f"\n**Overall: FAILED at Stage(s) {failed_stages}**\n")

    path = os.path.join(out_dir, "failure_points.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    log("stages", f"Wrote failure_points.md to {path}")
