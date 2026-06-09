# Implementation Plan: EvalWeaver v5.1 Reasoning Core

## Overview

Restructured into five phases prioritizing modularization and repo readiness before v5.1 fixes.
Priority order: modularize → push GitHub → run larger experiments → debug with multiple coding agents.

## Phase A: Repo and Modularization

- [x] 1. Project scaffolding
  - [x] 1.1 Create `pyproject.toml` with package metadata, dependencies (pytest, hypothesis, pyyaml, boto3), and `[project.scripts]` entry point
  - [x] 1.2 Create `requirements.txt` pinning runtime and dev dependencies
  - [x] 1.3 Create `.gitignore` (Python, IDE, __pycache__, .eggs, dist, *.egg-info, /outputs/, /tmp/)
  - [x] 1.4 Create `README.md` with project overview, quick-start, and CLI usage
  - [x] 1.5 Create package directory structure:
    - `evalweaver/__init__.py`
    - `evalweaver/config.py`
    - `evalweaver/policy.py`
    - `evalweaver/probes.py`
    - `evalweaver/runner.py`
    - `evalweaver/scorers.py`
    - `evalweaver/pairs.py`
    - `evalweaver/evaluation.py`
    - `evalweaver/pareto.py`
    - `evalweaver/failure_packet.py`
    - `evalweaver/repair.py`
    - `evalweaver/candidates.py`
    - `evalweaver/criteria.py`
    - `evalweaver/artifacts.py`
    - `evalweaver/__main__.py`
    - `evalweaver/providers/__init__.py`
    - `evalweaver/providers/base.py`
    - `evalweaver/providers/mock_provider.py`
    - `evalweaver/providers/bedrock_claude_provider.py`
    - `tests/__init__.py`
    - `tests/conftest.py`
    - `configs/persuasive.yaml`
    - `experiments/`

- [x] 2. Extract config module
  - [x] 2.1 Move constants (N_ROUNDS, N_INIT_SCORERS, N_REPAIR_SCORERS, N_INIT_PAIRS, etc.) into `evalweaver/config.py`
  - [x] 2.2 Add YAML config loading: `load_config(path) -> dict` merging defaults with file overrides
  - [x] 2.3 Create `configs/persuasive.yaml` with goal, raw_text, seed, and parameter overrides

- [x] 3. Extract artifacts module
  - [x] 3.1 Move `log()`, `save()`, `TRACE` into `evalweaver/artifacts.py`
  - [x] 3.2 Implement `resolve_output_directory()` — env var `EVALWEAVER_OUTPUT_DIR` → `./ew_v51_outputs` → `tempfile.mkdtemp()` fallback
  - [x] 3.3 Implement `build_zip_archive(out_dir)` — include all JSON artifacts, include source only when `__file__` exists
  - [x] 3.4 Graceful handling: missing dirs don't crash, log warning on fallback

- [x] 4. Extract namespace isolation (runner module)
  - [x] 4.1 Move `_py_ns`, `py_exec()`, `py_run_scorer()`, `_clamp()` into `evalweaver/runner.py`
  - [x] 4.2 Preserve current behavior exactly (v5 semantics, clamped output, exception catching)
  - [x] 4.3 Document that this is namespace isolation via exec(), NOT a security sandbox

- [x] 5. Extract policy module
  - [x] 5.1 Move `DEFAULT_SOURCE_POLICY`, `extract_numbers()`, `validate_pair_source_policy()`, `hard_source_policy_violated()`, `probe_source_continuity()` into `evalweaver/policy.py`
  - [x] 5.2 Preserve v5 behavior for now (v5.1 fixes come in Phase B)

- [x] 6. Extract probes module
  - [x] 6.1 Move all helper probe code (HELPER_CODE string) into `evalweaver/probes.py` as proper Python functions
  - [x] 6.2 Provide `load_probes(py_ns)` to inject probes into the runner namespace
  - [x] 6.3 Preserve all existing probe implementations exactly

- [x] 7. Extract scorers module
  - [x] 7.1 Move `validate_scorer_on_pairs()`, scorer hypothesis data structures, and scorer code dicts into `evalweaver/scorers.py`
  - [x] 7.2 Preserve pair-based validation behavior (F1+F2 fix already in v5)

- [x] 8. Extract pairs module
  - [x] 8.1 Move pair generation, pair data, `VALIDATION_PAIRS`, and pair splitting logic into `evalweaver/pairs.py`
  - [x] 8.2 Move `seeded_shuffle()` to `evalweaver/config.py` (utility)

- [x] 9. Extract evaluation module
  - [x] 9.1 Move `eval_scorer()`, `compute_summary()` into `evalweaver/evaluation.py`

- [x] 10. Extract pareto module
  - [x] 10.1 Move `is_eligible_for_pareto()`, `compute_pareto()` into `evalweaver/pareto.py`

- [x] 11. Extract failure_packet module
  - [x] 11.1 Move `build_failure_packet()` into `evalweaver/failure_packet.py`

- [x] 12. Extract repair module
  - [x] 12.1 Move Round 1 scorer hypotheses, scorer code, and mutation logic into `evalweaver/repair.py`

- [x] 13. Extract candidates module
  - [x] 13.1 Move candidate data, ensemble scoring, and selection logic into `evalweaver/candidates.py`

- [x] 14. Extract criteria module
  - [x] 14.1 Move `spec_criterion()` and computed criteria logic into `evalweaver/criteria.py`

- [x] 15. Implement CLI and pipeline runner
  - [x] 15.1 Implement `evalweaver/runner.py` orchestrating Steps 1–12 sequentially using extracted modules
  - [x] 15.2 Implement `evalweaver/__main__.py` with CLI: `python -m evalweaver run --config configs/persuasive.yaml`
  - [x] 15.3 Ensure full pipeline run produces all JSON artifacts in configured output directory

- [x] 16. End-to-end smoke test
  - [x] 16.1 Create `tests/test_smoke.py` proving modularized run produces JSON artifacts matching v5 output structure
  - [x] 16.2 Verify: at least one scorer is valid, Pareto non-empty, candidate selected, ZIP produced
  - [x] 16.3 Run smoke test and fix any import/wiring issues

- [x] 17. Phase A checkpoint
  - Run all tests, fix non-ambiguous failures, ask user only if genuinely blocked on a product decision.

## Phase B: P0 v5.1 Fixes

- [x] 18. Unified source_policy_violations
  - [x] 18.1 Rewrite `source_policy_violations(text, anchor, policy=None, *, role="candidate", pair_type=None)` in `evalweaver/policy.py`
    - Detect all canonical taxonomy types: invented_numeric_digit, invented_numeric_word, invented_time_or_quantity_claim, invented_named_entity, invented_customer_or_company_claim, invented_award_or_certification_claim, guarantee_claim
    - Return `[{violation_type, evidence, severity}]`
    - role supports: "positive_pair", "negative_pair", "candidate"
    - pair_type allows nuance for source_drift, specificity_trap
    - IMPORTANT: Always compute violations for negatives too (record but do not drop pair based on negative violations alone). Positive hard violations drop the pair. Candidate hard violations set policy_ok=false.
  - [x] 18.2 Implement named entity detection guardrails
    - Avoid false positives: sentence-initial words, allowed abbreviations (AI, SQL, API, BI, HR, VC, P&L), anchor-present names, generic role nouns
    - Strictly flag: new customer/company names, Fortune 500 claims, award/certification/compliance claims, SOC2/ISO/HIPAA unless in anchor
  - [x] 18.3 Rewrite `hard_source_policy_violated(text, anchor, policy=None, *, role="candidate", pair_type=None)`
    - Implementation: `any(v.get("severity") == "hard" for v in source_policy_violations(...))`
    - Filters by severity field, NOT list non-emptiness
  - [x] 18.4 Update `validate_pair_source_policy(pair)` to use unified function
    - Always compute violations for both positive and negative
    - Record `negative_policy_violations` on the pair (do not drop based on these)
    - Drop pair only if positive has hard violations
  - [x] 18.5 Update `probe_specificity_without_invention(text, anchor)` to call `hard_source_policy_violated()`, NOT `source_policy_violations()` directly

- [x] 19. Fix candidate policy_ok consistency
  - [x] 19.1 Update `score_candidates()` in `evalweaver/candidates.py`
    - Each candidate stores `policy_violations` from `source_policy_violations(text, anchor, role="candidate")`
    - `policy_ok = not hard_source_policy_violated(text, anchor, role="candidate")`
    - Uses the SAME function as scorer veto path
  - [x] 19.2 Add `raw_mean_score` field (unnormalized mean across scorers)
  - [x] 19.3 Verify C004 gets: policy_ok=false, ≥1 hard violation, raw_mean_score ≈ 0
  - [x] 19.4 Verify C002 gets: score > 0.05 normalized (soft continuity works)

- [x] 20. Three-tier scorer validity
  - [x] 20.1 Update `ScorerSummary` in `evalweaver/evaluation.py` to use explicit booleans:
    - `execution_valid`: loads, runs, bounded, nonconstant spread
    - `pair_quality_valid`: execution_valid AND pair_validation_accuracy >= 0.50 AND pair_validation_margin > 0
    - `pareto_eligible`: passes full eligibility filter
    - `pareto_ineligible_reason`: str
    - `valid`: deprecated alias for execution_valid
  - [x] 20.2 Update `is_eligible_for_pareto()` to set `pareto_ineligible_reason`
  - [x] 20.3 Update reporting to show tier counts: "N execution_valid, M pair_quality_valid, K pareto_eligible"

- [x] 21. Fix py_run_scorer to expose raw value
  - [x] 21.1 Change `py_run_scorer` return to: `{ok, raw_value, value, out_of_range, error}`
    - `raw_value`: the actual float before clamping (None on exception)
    - `value`: clamped to [0.0, 1.0] (0.5 on exception)
    - `out_of_range`: True if raw_value < -0.01 or raw_value > 1.01
    - Validation uses raw_value/out_of_range. Evaluation uses clamped value.
  - [x] 21.2 Update `validate_scorer_on_pairs` to check `out_of_range` field from runner

- [x] 22. Repair-improvement metrics
  - [x] 22.1 Implement `compute_repair_improvement_metrics()` in `evalweaver/repair.py`
    - Compare old vs new scorers across subsets: common_heldout, new_heldout, adversarial_train, final_heldout
    - Each subset: best_old_by_margin, best_new_by_margin, best_old_by_accuracy, best_new_by_accuracy, margin_delta, accuracy_delta
    - Compute flags: new_scorer_enters_pareto, beats_old_best_on_* subsets, share_of_eligible_ensemble
    - `overall_improvement_claim_supported`: True only if metrics support it
    - `honest_repair_summary`: human-readable, never claims improvement unless supported
  - [x] 22.2 Persist as `step10_repair_improvement_metrics.json`

- [x] 23. mechanism_result_alignment probe
  - [x] 23.1 Implement `probe_mechanism_result_alignment(text)` in `evalweaver/probes.py`
    - Extract mechanism clauses (after "by ", "through ", "using ")
    - Extract result clauses (after "so ", "which means", "enabling", "letting")
    - Score: concrete action verb in mechanism, concrete object noun in mechanism, concrete consequence verb in result, concrete operational noun in result
    - Penalty for jargon-only mechanism/result clause, penalty for missing mechanism/result
    - Does NOT require shared verbs between mechanism and result
  - [x] 23.2 Add to probe loading in `load_probes()`

- [x] 24. Artifact output path robustness
  - [x] 24.1 Verify `resolve_output_directory()` handles all cases:
    - EVALWEAVER_OUTPUT_DIR env var (primary)
    - ./ew_v51_outputs fallback
    - tempfile.mkdtemp() final fallback
    - Never assume /mnt/user-data
    - ZIP includes source only when __file__ exists
  - [x] 24.2 Remove hardcoded `/mnt/user-data` references from pipeline

- [x] 25. Phase B checkpoint
  - Run all tests, fix non-ambiguous failures, ask user only if genuinely blocked on a product decision.

## Phase C: Minimal P0 Tests

- [x] 26. P0 property and unit tests
  - [x] 26.1 Source policy violation taxonomy test — each of the 7 canonical types detected correctly
  - [x] 26.2 Named entity guardrails — abbreviations/sentence-initial words don't false-positive, new companies do flag
  - [x] 26.3 C004 policy_ok=false with ≥1 hard violation
  - [x] 26.4 C002 not zeroed (> 0.05 normalized)
  - [x] 26.5 validate_scorer detects: runtime errors, constant outputs, out-of-range (using raw_value/out_of_range)
  - [x] 26.6 Pareto non-domination sanity — no dominated member in frontier
  - [x] 26.7 Repair metrics honesty — overall_improvement_claim_supported matches actual data
  - [x] 26.8 End-to-end smoke test — full pipeline produces expected artifacts

- [x] 27. Phase C checkpoint
  - Run all tests, fix non-ambiguous failures, ask user only if genuinely blocked on a product decision.

## Phase D: Larger Experiments

- [x] 28. Single-topic experiment runner
  - [x] 28.1 Add experiment CLI: `python -m evalweaver experiment --config configs/persuasive.yaml --seeds 5 --scorers 12 --pairs 36`
  - [x] 28.2 Run multiple seeds, larger scorer/pair counts for goal=persuasive
  - [x] 28.3 Export summary comparison report (JSON + console table)

- [x] 29. Multi-topic configuration
  - [x] 29.1 Create configs for: persuasive, concise, narrative_cohesion, technical_clarity, trustworthiness
  - [x] 29.2 Add batch runner: `python -m evalweaver batch --configs configs/*.yaml`
  - [x] 29.3 Generate cross-topic comparison report

- [x] 30. Phase D checkpoint
  - Run all tests, fix non-ambiguous failures, ask user only if genuinely blocked on a product decision.

## Phase E: AWS Readiness

- [x] 31. AgentProvider protocol
  - [x] 31.1 Define `AgentProvider` protocol in `evalweaver/providers/base.py`
    - Methods: `generate_scorers()`, `generate_pairs()`, `generate_mutations()`, `generate_candidates()`
    - Accept config, return structured outputs
  - [x] 31.2 Implement `MockProvider` in `evalweaver/providers/mock_provider.py`
    - Returns hardcoded/seeded outputs (current v5.1 behavior)
    - Used for all local tests — no AWS dependency

- [x] 32. BedrockClaudeProvider skeleton
  - [x] 32.1 Implement `BedrockClaudeProvider` in `evalweaver/providers/bedrock_claude_provider.py`
    - Uses boto3 Bedrock Runtime Converse API
    - Accepts model_id, aws_region in config
    - Skeleton methods that format prompts and parse responses
  - [x] 32.2 Do NOT require Bedrock for local tests (MockProvider is default)

- [x] 33. Run metadata
  - [x] 33.1 Add run metadata fields to artifacts: provider_name, model_id, aws_region, execution_backend, artifact_store, run_id
  - [x] 33.2 Include in run_summary artifact and trace log

- [x] 34. Phase E checkpoint
  - Run all tests, fix non-ambiguous failures, ask user only if genuinely blocked on a product decision.

## Backlog (GitHub Issues)

Remaining property-based tests (Properties 1–22 from design) not covered in Phase C:
- Property 1: Scorer output clamping invariant
- Property 2: Three-tier validity classification correctness
- Property 5: Hard policy filters by severity
- Property 6: Hard source policy vetoes scorer to zero
- Property 8: Pareto frontier sort order
- Property 9: Mutation instruction non-repetition
- Property 10: Heldout anti-leakage
- Property 11: Pair source policy enforcement
- Property 12: Ensemble scoring normalization
- Property 14: mechanism_result_alignment bounds/semantics
- Property 15: Artifact persistence round-trip
- Property 16: Output directory fallback
- Property 17: Repair-improvement honesty (extended)
- Property 18: Evaluation completeness
- Property 19: TasteMap structural invariants
- Property 20: argument_progression correctness
- Property 21: Named entity false-positive avoidance (extended)
- Property 22: Candidate policy_ok reflects hard severity only

## Notes

- Phase A preserves v5 behavior exactly — no functional changes, only restructuring
- Phase B applies v5.1 fixes incrementally on the modularized codebase
- Phase C adds only the tests needed to validate P0 fixes before pushing
- Phase D enables experimentation at scale
- Phase E prepares for AWS deployment without breaking local development
- At checkpoints: run tests, summarize failures, fix non-ambiguous failures, only ask user if genuinely blocked on a product decision
