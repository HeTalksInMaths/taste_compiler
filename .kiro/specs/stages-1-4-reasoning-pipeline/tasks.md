# Tasks

## Task 1: Create stage data models and schema validation

- [x] 1.1 Create `evalweaver/stage_models.py` with `StageResult` and `EvalResult` dataclasses
- [x] 1.2 Implement schema validation functions for all four stage output schemas (Stage1Output, Stage2Output, Stage3Output, Stage4Output)
- [x] 1.3 Define pass criteria constants (`STAGE_1_PASS_CRITERIA` through `STAGE_4_PASS_CRITERIA`) and `SMOKE_TEXTS`

## Task 2: Implement prompt template builders

- [x] 2.1 Implement `build_stage_1_prompt(target_variable)` returning (system, user) tuple
- [x] 2.2 Implement `build_stage_2_prompt(target_variable, stage1_research)` returning (system, user) tuple
- [x] 2.3 Implement `build_stage_3_prompt(target_variable, causal_nodes)` returning (system, user) tuple
- [x] 2.4 Implement `build_stage_4_prompt(target_variable, causal_graph, measurement_research)` returning (system, user) tuple

## Task 3: Implement Stage 1 eval engine

- [x] 3.1 Implement `eval_stage_1(parsed_json, pass_criteria)` computing: num_research_items, num_unique_causal_variables, mechanism_completeness_rate, source_trace_rate, causal_specificity_score, generic_advice_penalty, tension_count, effect_direction_coverage
- [x] 3.2 Implement mechanism_completeness_rate: fraction of items with all required fields populated
- [x] 3.3 Implement causal_specificity_score: reward mechanistic keywords (because, leads to, increases, decreases, mediates, moderates, causes, drives, reduces, through, by making, as a result)
- [x] 3.4 Implement generic_advice_penalty: penalize vague words (clear, good, engaging, effective, strong, better, important, high quality) only when mechanism is empty

## Task 4: Implement Stage 2 eval engine

- [x] 4.1 Implement `eval_stage_2(parsed_json, pass_criteria)` computing: num_nodes, num_edges, node_mechanism_rate, node_evidence_rate, edge_validity_rate, edge_explanation_rate, graph_connectedness_score, role_diversity_score, tension_count, summary_uses_graph_terms
- [x] 4.2 Implement edge_validity_rate: fraction of edges where from/to reference existing node_ids
- [x] 4.3 Implement graph_connectedness_score: fraction of nodes participating in at least one edge

## Task 5: Implement Stage 3 eval engine

- [x] 5.1 Implement `eval_stage_3(parsed_json, pass_criteria, stage2_nodes)` computing: node_measurement_coverage, num_measurement_items, text_feature_specificity_score, implementation_actionability_score, generic_metric_penalty, multi_measurement_rate, node_reference_validity_rate
- [x] 5.2 Implement node_measurement_coverage: fraction of stage2 nodes referenced by at least one item
- [x] 5.3 Implement node_reference_validity_rate: fraction of items whose causal_node matches a stage2 node_id

## Task 6: Implement Stage 4 eval engine

- [x] 6.1 Implement `eval_stage_4(parsed_json, pass_criteria, stage2_nodes, smoke_texts, anchor)` computing all 12 signals
- [x] 6.2 Implement code_exec_rate: execute each scorer via py_run_scorer on all smoke texts, count exception-free scorers
- [x] 6.3 Implement nonconstant_behavior_rate: require at least two different outputs across smoke texts
- [x] 6.4 Implement scorer_distinctness_score: unique (functional_form, causal_nodes_used, measurement_ideas_used) tuples / total
- [x] 6.5 Implement causal_node_validity_rate: fraction of referenced nodes existing in stage2 graph

## Task 7: Implement StageOrchestrator

- [x] 7.1 Create `evalweaver/stages.py` with `StageOrchestrator` class
- [x] 7.2 Implement sequential execution: Stage 1 → eval → Stage 2 → eval → Stage 3 → eval → Stage 4 → eval
- [x] 7.3 Implement fail-fast: if any eval fails, halt immediately, persist artifacts, write failure_points.md
- [x] 7.4 Implement data threading: pass parsed_json from stage N to stage N+1 prompt construction
- [x] 7.5 Implement artifact persistence per stage (prompt, raw_response, parsed_json, eval_result, call_meta)

## Task 8: Implement failure_points.md writer

- [x] 8.1 Implement `write_failure_points(out_dir, stage_results)` that generates markdown with pass/fail per stage and specific failed signals

## Task 9: Integrate with CLI

- [x] 9.1 Wire `--live-canary` flag to invoke `StageOrchestrator.run()` when stages pipeline is triggered
- [x] 9.2 Ensure existing pipeline behavior is unchanged when `--live-canary` is not set

## Task 10: Property-based tests for eval engine

- [x] 10.1 Write Hypothesis test for Property 5 (mechanism_completeness_rate)
- [x] 10.2 Write Hypothesis test for Property 6 (causal_specificity_score monotonicity)
- [x] 10.3 Write Hypothesis test for Property 7 (generic_advice_penalty only without mechanism)
- [x] 10.4 Write Hypothesis test for Property 8 (pass criteria threshold check)
- [x] 10.5 Write Hypothesis test for Property 9 (edge_validity_rate)
- [x] 10.6 Write Hypothesis test for Property 10 (graph_connectedness_score)
- [x] 10.7 Write Hypothesis test for Property 11 (node_measurement_coverage)
- [x] 10.8 Write Hypothesis test for Property 12 (node_reference_validity_rate)
- [x] 10.9 Write Hypothesis test for Property 13 (code_exec_rate)
- [x] 10.10 Write Hypothesis test for Property 14 (nonconstant_behavior_rate)
- [x] 10.11 Write Hypothesis test for Property 15 (scorer_distinctness_score)

## Task 11: Property-based tests for schema and orchestration

- [x] 11.1 Write Hypothesis test for Property 2 (schema validation: valid passes, missing fields fail)
- [x] 11.2 Write Hypothesis test for Property 3 (artifact persistence round-trip)
- [x] 11.3 Write Hypothesis test for Property 4 (unparseable response halts)
- [x] 11.4 Write Hypothesis test for Property 16 (fail-fast halts subsequent stages)
- [x] 11.5 Write Hypothesis test for Property 17 (failure report contains all stage statuses)
- [x] 11.6 Write Hypothesis test for Property 1 (prompt construction includes required inputs)

## Task 12: Unit tests and integration tests

- [x] 12.1 Write unit tests for prompt builders with known inputs/outputs
- [x] 12.2 Write integration test with mock provider executing all 4 stages successfully
- [x] 12.3 Write integration test with mock provider where Stage 2 fails (verify halt + artifacts)
- [x] 12.4 Write smoke test verifying `--live-canary` CLI flag triggers StageOrchestrator
