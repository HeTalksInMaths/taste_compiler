# Tasks

## Task 1: Extend stage_models.py with Stage 5–8 schema validation and pass criteria

- [x] 1.1 Add `validate_stage_5_output(data)` checking pairs array with required fields: pair_id, anchor, positive, negative, split, target_delta, controlled_variables
- [x] 1.2 Add `validate_stage_6_output(data)` checking scorer_evaluations dict, scorer_summaries array, and pareto_frontier array
- [x] 1.3 Add `validate_stage_7_output(data)` checking failure_patterns array (pattern_id, scorer_ids, reasoning_error), mutation_instructions array (instruction_id, instruction), and heldout_aggregate_only dict
- [x] 1.4 Add `validate_stage_8_output(data)` checking repair_scorers array with required fields: scorer_id, hypothesis, causal_nodes_used, functional_form, code containing `def scorer(text, anchor, params)`
- [x] 1.5 Define `STAGE_5_HARD_GATES`, `STAGE_6_HARD_GATES`, `STAGE_7_HARD_GATES`, `STAGE_8_HARD_GATES` constants
- [x] 1.6 Define `STAGE_5_SOFT_TARGETS`, `STAGE_6_SOFT_TARGETS`, `STAGE_7_SOFT_TARGETS`, `STAGE_8_SOFT_TARGETS` constants

## Task 2: Implement prompt template builders for Stages 5, 7, 8

- [x] 2.1 Implement `build_stage_5_prompt(target_variable, causal_graph, measurement_research, scorers, source_policy)` returning (system, user) tuple
- [x] 2.2 Implement `build_stage_7_prompt(target_variable, scorer_summaries, train_eval_rows, pareto_frontier, train_pairs, causal_graph, measurement_research, heldout_aggregate)` returning (system, user) tuple — must NOT include raw heldout pair text
- [x] 2.3 Implement `build_stage_8_prompt(target_variable, causal_graph, measurement_research, prior_scorers, failure_packet)` returning (system, user) tuple

## Task 3: Implement Stage 5 eval engine

- [x] 3.1 Implement `eval_stage_5(parsed_json, pass_criteria, stage2_nodes)` computing all signals
- [x] 3.2 Implement pair_schema_completeness_rate: fraction of pairs with all required fields populated
- [x] 3.3 Implement causal_node_reference_validity_rate: fraction of pairs whose causal_nodes_tested entries all exist in stage2 node_ids
- [x] 3.4 Implement length_balance_rate: fraction of pairs where abs(len(positive.split()) - len(negative.split())) <= max_words * 0.3
- [x] 3.5 Implement minimal_contrast_rate: fraction of pairs testing 1–2 causal nodes (not 3+)
- [x] 3.6 Implement target_direction_clarity_rate: fraction of pairs with non-empty label_contract
- [x] 3.7 Implement near_duplicate_pair_rate and heldout_leakage_risk

## Task 4: Implement Stage 6 deterministic scorer evaluation

- [x] 4.1 Implement `run_stage_6(scorers, pair_suite, anchor)` that runs each scorer on each pair via py_run_scorer, returns {scorer_evaluations, scorer_summaries, pareto_frontier}
- [x] 4.2 Implement per-scorer per-pair row computation: positive_score, negative_score, gap, correct
- [x] 4.3 Implement per-scorer summary: train_accuracy, train_mean_gap, heldout_accuracy, heldout_mean_gap, score_spread, exec_error_rate, nonconstant_rate
- [x] 4.4 Implement Pareto eligibility check: exec_error_rate == 0, nonconstant, score_spread >= 0.02, heldout_accuracy >= 0.50, heldout_mean_gap > 0
- [x] 4.5 Implement 2D Pareto frontier computation over (heldout_accuracy, heldout_mean_gap)

## Task 5: Implement Stage 6 eval engine

- [x] 5.1 Implement `eval_stage_6(scorer_summaries, pareto_frontier, eval_rows, pass_criteria)` computing all signals
- [x] 5.2 Implement execution_valid_rate, numeric_return_rate, nonconstant_scorer_rate
- [x] 5.3 Implement overfit_warning_count: scorers where train_accuracy > heldout_accuracy + 0.2
- [x] 5.4 Implement eligible_scorer_count and pareto_count

## Task 6: Implement Stage 7 eval engine

- [x] 6.1 Implement `eval_stage_7(parsed_json, pass_criteria, heldout_pairs)` computing all signals
- [x] 6.2 Implement heldout_raw_text_leakage_count: scan Stage 7 output for raw heldout pair text
- [x] 6.3 Implement mutation_actionability_score: fraction of instructions containing action verbs (add, remove, replace, combine, split, increase, decrease, weight, gate, normalize, multiply)
- [x] 6.4 Implement failure_pattern_specificity_score: reward patterns naming scorer_ids, visible_pair_ids, causal_nodes, and reasoning_error
- [x] 6.5 Implement causal_reference_rate: fraction of patterns/instructions referencing causal nodes

## Task 7: Implement Stage 8 eval engine

- [x] 7.1 Implement `eval_stage_8(parsed_json, pass_criteria, stage2_nodes, stage7_patterns, smoke_texts, anchor)` computing all signals
- [x] 7.2 Implement code_exec_rate: execute each repair scorer via py_run_scorer on smoke texts, count exception-free
- [x] 7.3 Implement nonconstant_behavior_rate: require at least two different outputs across smoke texts
- [x] 7.4 Implement failure_pattern_target_rate: fraction of repair scorers referencing valid Stage 7 pattern_ids
- [x] 7.5 Implement unsafe_code_penalty: detect import, open(), exec(), eval(), requests, urllib, socket in code
- [x] 7.6 Implement functional_form_diversity: count unique functional_form values
- [x] 7.7 Implement parent_distinctness_rate: fraction of scorers differing from parent in form or nodes

## Task 8: Implement Stage5to8Orchestrator

- [x] 8.1 Create `Stage5to8Orchestrator` class accepting provider, config, out_dir, stage2_output, stage3_output, stage4_output
- [x] 8.2 Implement sequential execution: Stage 5 → eval → Stage 6 → eval → Stage 7 → eval → Stage 8 → eval
- [x] 8.3 Implement fail-fast: if any hard gate fails, halt immediately, persist artifacts, write failure_points.md
- [x] 8.4 Implement data threading: pass parsed_json from stage N to stage N+1 (Stage 5 pairs → Stage 6, Stage 6 summaries/pareto → Stage 7, Stage 7 failure_packet → Stage 8)
- [x] 8.5 Implement artifact persistence per stage (prompt, raw_response, parsed_json, eval_result, call_meta)
- [x] 8.6 Implement heldout leakage boundary: Stage 7 prompt gets train pairs only + heldout aggregates only

## Task 9: Implement parallel pair generation (stage5_parallel.py)

- [x] 9.1 Implement `build_single_pair_prompt(target_variable, causal_graph, measurement_research, pair_index, causal_node_hint, source_policy)` returning (system, user) tuple
- [x] 9.2 Implement `generate_pairs_parallel(provider_factory, target_variable, causal_graph, measurement_research, n_pairs, max_workers, source_policy, out_dir)` using ThreadPoolExecutor
- [x] 9.3 Implement round-robin causal_node_hint assignment for diversity
- [x] 9.4 Implement result aggregation into Stage 5 output schema with split assignment (last N as heldout)

## Task 10: Implement parallel repair scorer generation (stage8_parallel.py)

- [x] 10.1 Implement `build_single_repair_scorer_prompt(target_variable, causal_graph, measurement_research, scorer_index, failure_packet, parent_scorer, functional_form_hint)` returning (system, user) tuple
- [x] 10.2 Implement `generate_repair_scorers_parallel(provider_factory, target_variable, causal_graph, measurement_research, prior_scorers, failure_packet, n_scorers, max_workers, anchor, out_dir)` using ThreadPoolExecutor
- [x] 10.3 Implement round-robin functional_form_hint assignment for diversity
- [x] 10.4 Implement smoke-test validation of each repair scorer immediately after generation

## Task 11: Integrate with CLI

- [x] 11.1 Wire Stage5to8Orchestrator to trigger after Stages 1–4 pass (or when `--resume-from 5` is set)
- [x] 11.2 Ensure existing Stages 1–4 pipeline behavior is unchanged

## Task 12: Property-based tests for Stage 5–8 eval engines

- [x] 12.1 Write Hypothesis test for Property 7 (pair_schema_completeness_rate)
- [ ] 12.2 Write Hypothesis test for Property 8 (causal_node_reference_validity_rate)
- [x] 12.3 Write Hypothesis test for Property 9 (length_balance_rate)
- [ ] 12.4 Write Hypothesis test for Property 10 (Stage 6 accuracy and mean_gap)
- [ ] 12.5 Write Hypothesis test for Property 11 (Pareto frontier is non-dominated set)
- [ ] 12.6 Write Hypothesis test for Property 12 (Pareto eligibility conjunction)
- [x] 12.7 Write Hypothesis test for Property 13 (overfit_warning_count)
- [x] 12.8 Write Hypothesis test for Property 14 (heldout leakage detection)
- [x] 12.9 Write Hypothesis test for Property 15 (mutation_actionability_score)
- [x] 12.10 Write Hypothesis test for Property 16 (code_exec_rate)
- [x] 12.11 Write Hypothesis test for Property 17 (nonconstant_behavior_rate)
- [ ] 12.12 Write Hypothesis test for Property 18 (failure_pattern_target_rate)
- [x] 12.13 Write Hypothesis test for Property 19 (unsafe_code_penalty)

## Task 13: Property-based tests for schema and orchestration

- [x] 13.1 Write Hypothesis test for Property 2 (schema validation: valid passes, missing fields fail)
- [ ] 13.2 Write Hypothesis test for Property 3 (artifact persistence round-trip)
- [ ] 13.3 Write Hypothesis test for Property 4 (unparseable response halts)
- [x] 13.4 Write Hypothesis test for Property 5 (hard gate threshold check)
- [ ] 13.5 Write Hypothesis test for Property 6 (fail-fast halts subsequent stages)
- [x] 13.6 Write Hypothesis test for Property 1 (prompt construction includes required inputs)
- [ ] 13.7 Write Hypothesis test for Property 20 (parallel generation aggregates into valid schema)
- [x] 13.8 Write Hypothesis test for Property 21 (split assignment respects heldout_count)
- [x] 13.9 Write Hypothesis test for Property 22 (soft targets tracked but never block)
- [ ] 13.10 Write Hypothesis test for Property 23 (failure report contains all stage statuses)

## Task 14: Unit tests and integration tests

- [ ] 14.1 Write unit tests for Stage 5/7/8 prompt builders with known inputs/outputs
- [x] 14.2 Write unit test for Stage 6 deterministic evaluation with known scorers and pairs
- [ ] 14.3 Write integration test with mock provider executing all 4 stages (5–8) successfully
- [ ] 14.4 Write integration test with mock provider where Stage 5 fails (verify halt + artifacts)
- [x] 14.5 Write integration test where Stage 7 leaks heldout text (verify hard gate fails)
- [ ] 14.6 Write integration test for parallel Stage 5 with partial call failures
- [ ] 14.7 Write integration test for parallel Stage 8 with partial call failures
