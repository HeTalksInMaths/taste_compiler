# Requirements Document

## Introduction

This feature implements Stages 5–8 of the EvalWeaver Reasoning Pipeline: evaluation pair generation with source-policy validation (Stage 5), initial scorer evaluation and Pareto selection (Stage 6), failure packet and repair instruction generation (Stage 7), and repair scorer hypothesis and function generation (Stage 8). Stages 5, 7, and 8 use LLM calls via AWS Bedrock (Claude Sonnet 4); Stage 6 is purely deterministic. Each stage follows the established pattern: prompt construction → execution → JSON parsing → deterministic evaluation → artifact persistence. The pipeline uses the same hard gates vs soft targets philosophy as Stages 1–4: only structural failures halt the pipeline; quality signals are tracked but non-blocking.

## Glossary

- **Pipeline**: The sequential execution engine that orchestrates Stages 5–8
- **Stage**: A single reasoning step consisting of prompt construction, execution, response parsing, and deterministic evaluation
- **Pair_Generator**: Stage 5 — generates positive/negative text pairs testing whether scorers measure slightly more vs. slightly less of the target variable
- **Scorer_Evaluator**: Stage 6 — deterministic scorer evaluation on the pair suite with Pareto frontier computation (no LLM)
- **Failure_Analyst**: Stage 7 — converts scorer evaluation failures into actionable, leakage-safe repair instructions
- **Repair_Generator**: Stage 8 — generates evolved scorer hypotheses and executable functions addressing failure-packet patterns
- **Target_Variable**: The subjective text quality dimension being modeled (e.g., "trustworthy")
- **Pair_Suite**: The collection of positive/negative text pairs split into train and heldout sets
- **Pareto_Frontier**: The set of non-dominated scorers maximizing heldout_accuracy and heldout_mean_gap
- **Hard_Gate**: A structural threshold that halts the pipeline when violated (low bar, prevents downstream impossibility)
- **Soft_Target**: A quality signal tracked for improvement but never blocking pipeline execution
- **Failure_Packet**: A structured analysis of scorer weaknesses with leakage-safe heldout aggregate reporting
- **Mutation_Instruction**: An actionable directive for how to modify scorer logic to address a failure pattern
- **Repair_Scorer**: An evolved scorer hypothesis and function that addresses specific failure-packet patterns
- **Source_Policy**: Rules governing how pairs reference source material (trace, relevance, policy compliance)
- **Heldout_Leakage**: Exposure of raw heldout pair text to repair processes (must be prevented)
- **Eval_Engine**: The deterministic scoring subsystem that validates each stage's output against pass criteria
- **Bedrock_Provider**: The existing BedrockClaudeProvider that handles Converse API communication
- **py_run_scorer**: The existing sandboxed Python execution environment for scorer code
- **StageResult**: Dataclass capturing stage execution output (prompt, raw_response, parsed_json, parse_error, call_meta)
- **EvalResult**: Dataclass capturing evaluation results (signals, passed, failures, soft_evals)

## Requirements

### Requirement 1: Stage 5 — Evaluation Pair Generation Execution

**User Story:** As a researcher, I want the pipeline to generate balanced positive/negative text pairs testing whether scorers measure slightly more vs. slightly less of the target variable, so that scorer evaluation has a rigorous, controlled test suite.

#### Acceptance Criteria

1. WHEN Stage 4 passes evaluation, THE Pipeline SHALL construct the Stage 5 prompt using target_variable, causal_graph (from Stage 2), measurement_research (from Stage 3), scorers (from Stage 4), and source_policy configuration, and send it to the Bedrock_Provider
2. WHEN a valid JSON response is received from Stage 5, THE Pipeline SHALL parse it into the pair suite schema containing pairs array with pair_id, source_id, source_trace, anchor, positive, negative, split, target_delta, controlled_variables, causal_nodes_tested, causal_edges_tested, measurement_ideas_tested, causal_tensions_tested, label_contract, source_policy, and policy_violations fields
3. THE Pipeline SHALL assign each pair a split of either "train" or "heldout" according to pair_generation_config.heldout_count
4. WHEN Stage 5 completes, THE Pipeline SHALL save the prompt, raw_response, parsed_json, eval_result, and call_meta as persistent artifacts
5. IF Stage 5 receives a non-JSON or unparseable response, THEN THE Pipeline SHALL record the failure and halt execution
6. THE Pipeline SHALL support parallel pair generation (one pair per LLM call) using ThreadPoolExecutor, consistent with stage4_parallel.py patterns

### Requirement 2: Stage 5 — Evaluation Pair Evaluation

**User Story:** As a researcher, I want Stage 5 outputs to be validated for structural completeness and source-policy compliance, so that only well-formed pair suites proceed to scorer evaluation.

#### Acceptance Criteria

1. WHEN Stage 5 output is evaluated, THE Eval_Engine SHALL compute num_pairs, heldout_count, pair_schema_completeness_rate, source_trace_rate, source_relevance_rate, causal_node_reference_validity_rate, measurement_reference_validity_rate, controlled_variable_pass_rate, length_balance_rate, minimal_contrast_rate, target_direction_clarity_rate, positive_policy_pass_rate, near_duplicate_pair_rate, and heldout_leakage_risk
2. THE Eval_Engine SHALL compute pair_schema_completeness_rate as the fraction of pairs with all required fields (pair_id, anchor, positive, negative, split, target_delta, controlled_variables) populated
3. THE Eval_Engine SHALL compute causal_node_reference_validity_rate as the fraction of pairs whose causal_nodes_tested entries all exist in the Stage 2 causal graph
4. THE Eval_Engine SHALL compute length_balance_rate as the fraction of pairs where abs(len(positive.split()) - len(negative.split())) <= max_words_per_variant * 0.3
5. THE Eval_Engine SHALL use hard gates: num_pairs_min >= 6, pair_schema_completeness_rate_min >= 0.5
6. THE Eval_Engine SHALL use soft targets for all other signals (source_trace_rate, causal_node_reference_validity_rate, controlled_variable_pass_rate, length_balance_rate, minimal_contrast_rate, target_direction_clarity_rate, positive_policy_pass_rate)
7. IF Stage 5 fails hard gates, THEN THE Pipeline SHALL write the eval signals to the failure report and halt execution

### Requirement 3: Stage 6 — Initial Scorer Evaluation Execution

**User Story:** As a researcher, I want each scorer evaluated deterministically against the pair suite, so that I can identify which scorers correctly distinguish positive from negative variants.

#### Acceptance Criteria

1. WHEN Stage 5 passes evaluation, THE Scorer_Evaluator SHALL execute each scorer function on every pair: positive_score = scorer(positive, anchor, params), negative_score = scorer(negative, anchor, params), gap = positive_score - negative_score, correct = gap > 0
2. THE Scorer_Evaluator SHALL compute per-scorer per-pair evaluation rows containing scorer_id, pair_id, split, positive_score, negative_score, gap, and correct
3. THE Scorer_Evaluator SHALL compute per-scorer summary metrics: train_accuracy, train_mean_gap, heldout_accuracy, heldout_mean_gap, score_spread, exec_error_rate, nonconstant_rate
4. THE Scorer_Evaluator SHALL execute entirely without LLM calls (purely deterministic using py_run_scorer)
5. WHEN Stage 6 completes, THE Pipeline SHALL save scorer_evaluations, scorer_summaries, and pareto_frontier as persistent artifacts

### Requirement 4: Stage 6 — Pareto Selection and Evaluation

**User Story:** As a researcher, I want non-dominated scorers identified via Pareto frontier computation, so that the best scorers proceed to failure analysis.

#### Acceptance Criteria

1. THE Scorer_Evaluator SHALL compute the Pareto frontier over eligible scorers using dimensions: heldout_accuracy and heldout_mean_gap
2. THE Scorer_Evaluator SHALL determine scorer eligibility by requiring: execution without errors, nonconstant output, score_spread >= 0.02, heldout_accuracy >= 0.50, and heldout_mean_gap > 0
3. WHEN Stage 6 output is evaluated, THE Eval_Engine SHALL compute num_scorers_evaluated, eval_row_completeness_rate, execution_valid_rate, numeric_return_rate, score_range_valid_rate, nonconstant_scorer_rate, train_accuracy_presence_rate, heldout_accuracy_presence_rate, train_gap_presence_rate, heldout_gap_presence_rate, eligible_scorer_count, pareto_count, and overfit_warning_count
4. THE Eval_Engine SHALL compute overfit_warning_count as the count of scorers where train_accuracy > heldout_accuracy + 0.2
5. THE Eval_Engine SHALL use hard gates: num_scorers_evaluated_min >= 3, execution_valid_rate_min >= 0.3
6. THE Eval_Engine SHALL use soft targets for eligible_scorer_count, pareto_count, nonconstant_scorer_rate, heldout_accuracy_presence_rate
7. IF Stage 6 fails hard gates, THEN THE Pipeline SHALL write the eval signals to the failure report and halt execution

### Requirement 5: Stage 7 — Failure Packet Generation Execution

**User Story:** As a researcher, I want scorer evaluation failures converted into structured, actionable repair instructions, so that repair scorers can target specific weaknesses without heldout leakage.

#### Acceptance Criteria

1. WHEN Stage 6 passes evaluation, THE Pipeline SHALL construct the Stage 7 prompt using scorer_summaries, scorer_evaluations (train split only), pareto_frontier, pair_suite (train split only), causal_graph, and measurement_research, and send it to the Bedrock_Provider
2. WHEN a valid JSON response is received from Stage 7, THE Pipeline SHALL parse it into the failure packet schema containing: failure_packet (top_scorers, failed_visible_pairs, low_margin_visible_pairs), heldout_aggregate_only (no raw text), failure_patterns (pattern_id, scorer_ids, visible_pair_ids, causal_nodes_implicated, reasoning_error, severity), mutation_instructions (instruction_id, targets_failure_patterns, instruction, expected_metric_movement), and pair_suite_coverage_notes
3. THE Pipeline SHALL ensure heldout_aggregate_only contains ONLY aggregate metrics (accuracy, mean_gap per scorer) and NEVER raw heldout pair text
4. WHEN Stage 7 completes, THE Pipeline SHALL save the prompt, raw_response, parsed_json, eval_result, and call_meta as persistent artifacts
5. IF Stage 7 receives a non-JSON or unparseable response, THEN THE Pipeline SHALL record the failure and halt execution

### Requirement 6: Stage 7 — Failure Packet Evaluation

**User Story:** As a researcher, I want failure packets validated for specificity, coverage, and leakage safety, so that only actionable repair instructions proceed to scorer repair.

#### Acceptance Criteria

1. WHEN Stage 7 output is evaluated, THE Eval_Engine SHALL compute top_scorer_coverage_rate, visible_failure_reference_rate, heldout_raw_text_leakage_count, failure_pattern_count, failure_pattern_specificity_score, mutation_actionability_score, coverage_note_specificity_score, prior_instruction_dedup_rate, and causal_reference_rate
2. THE Eval_Engine SHALL compute heldout_raw_text_leakage_count by scanning the entire Stage 7 output for any raw text matching heldout pair positive or negative variants
3. THE Eval_Engine SHALL compute mutation_actionability_score by checking that each mutation_instruction contains at least one concrete action verb (add, remove, replace, combine, split, increase, decrease, weight, gate, normalize, multiply)
4. THE Eval_Engine SHALL use hard gates: failure_pattern_count_min >= 1, heldout_raw_text_leakage_count_max = 0
5. THE Eval_Engine SHALL use soft targets for top_scorer_coverage_rate, visible_failure_reference_rate, failure_pattern_specificity_score, mutation_actionability_score, causal_reference_rate
6. IF Stage 7 fails hard gates, THEN THE Pipeline SHALL write the eval signals to the failure report and halt execution

### Requirement 7: Stage 8 — Repair Scorer Generation Execution

**User Story:** As a researcher, I want evolved scorer hypotheses and executable functions generated that address failure-packet patterns, so that the scorer population improves through targeted repair.

#### Acceptance Criteria

1. WHEN Stage 7 passes evaluation, THE Pipeline SHALL construct the Stage 8 prompt using causal_graph, measurement_research, prior_scorers (from Stage 4 or prior repair rounds), and failure_packet (from Stage 7), and send it to the Bedrock_Provider
2. WHEN a valid JSON response is received from Stage 8, THE Pipeline SHALL parse it into the repair scorers schema containing per scorer: scorer_id, lineage, parent_scorer_ids, targets_failure_patterns, hypothesis, causal_nodes_used, measurement_ideas_used, functional_form, repair_strategy, expected_failure_mode, code_feature_map, and code
3. THE Pipeline SHALL require each repair scorer code field to define a function with signature `def scorer(text, anchor, params)` that returns a numeric score
4. WHEN Stage 8 completes, THE Pipeline SHALL save the prompt, raw_response, parsed_json, eval_result, and call_meta as persistent artifacts
5. IF Stage 8 receives a non-JSON or unparseable response, THEN THE Pipeline SHALL record the failure and halt execution
6. THE Pipeline SHALL support parallel repair scorer generation (one scorer per LLM call) using ThreadPoolExecutor, consistent with stage4_parallel.py patterns

### Requirement 8: Stage 8 — Repair Scorer Evaluation

**User Story:** As a researcher, I want repair scorers validated for executability, causal grounding, and failure-pattern targeting, so that only functional and relevant repair scorers enter the next evaluation round.

#### Acceptance Criteria

1. WHEN Stage 8 output is evaluated, THE Eval_Engine SHALL compute num_repair_scorers, failure_pattern_target_rate, lineage_completeness_rate, causal_node_validity_rate, measurement_reference_rate, code_feature_map_completeness_rate, repair_strategy_specificity_score, functional_form_diversity, code_exec_rate, numeric_return_rate, nonconstant_behavior_rate, parent_distinctness_rate, and unsafe_code_penalty
2. THE Eval_Engine SHALL compute code_exec_rate by executing each repair scorer's code via py_run_scorer with the four smoke texts and confirming no exceptions are raised
3. THE Eval_Engine SHALL compute nonconstant_behavior_rate by running each scorer on the smoke texts and requiring different numeric outputs across at least two inputs
4. THE Eval_Engine SHALL compute failure_pattern_target_rate as the fraction of repair scorers whose targets_failure_patterns field references at least one pattern_id from Stage 7
5. THE Eval_Engine SHALL compute unsafe_code_penalty by detecting import statements, open() calls, exec() calls, eval() calls, or network-related functions (requests, urllib, socket) in scorer code
6. THE Eval_Engine SHALL use hard gates: num_repair_scorers_min >= 2, code_exec_rate_min >= 0.3
7. THE Eval_Engine SHALL use soft targets for failure_pattern_target_rate, lineage_completeness_rate, causal_node_validity_rate, measurement_reference_rate, nonconstant_behavior_rate, functional_form_diversity, parent_distinctness_rate
8. IF Stage 8 fails hard gates, THEN THE Pipeline SHALL write the eval signals to the failure report and halt execution

### Requirement 9: Pipeline Orchestration for Stages 5–8

**User Story:** As a developer, I want stages 5–8 to execute sequentially with each stage's output feeding the next, so that the evaluation-repair cycle maintains coherence across all four stages.

#### Acceptance Criteria

1. THE Pipeline SHALL execute stages in strict order: Stage 5, Stage 6, Stage 7, Stage 8
2. WHEN a stage passes evaluation (hard gates), THE Pipeline SHALL pass the stage's parsed_json output as input to the next stage's prompt construction
3. IF any stage fails hard gate evaluation, THEN THE Pipeline SHALL halt immediately without executing subsequent stages
4. WHEN all four stages pass hard gate evaluation, THE Pipeline SHALL report overall success with a summary of all eval signals and soft target misses
5. THE Pipeline SHALL accept outputs from Stages 1–4 (causal_graph, measurement_research, scorers) as input prerequisites

### Requirement 10: Artifact Persistence for Stages 5–8

**User Story:** As a developer, I want every stage to save its full execution context, so that runs can be audited, debugged, and replayed.

#### Acceptance Criteria

1. THE Pipeline SHALL save for each stage: the constructed prompt, the raw LLM response text (for stages 5, 7, 8), the parsed JSON object, the eval result with all computed signals and soft target misses, and the call_meta (latency_ms, retry_mode, max_attempts, error)
2. WHEN a stage fails, THE Pipeline SHALL still persist all available artifacts up to the point of failure
3. THE Pipeline SHALL write a failure_points.md summarizing pass/fail status for each executed stage, including the specific hard gate signals that failed and soft target misses

### Requirement 11: Scorer Code Safety for Repair Scorers

**User Story:** As a developer, I want Stage 8 repair scorer code to execute in the same sandboxed namespace as Stage 4, so that generated code cannot access the file system or network.

#### Acceptance Criteria

1. WHEN evaluating Stage 8 repair scorer code, THE Eval_Engine SHALL execute each scorer function via the existing py_run_scorer mechanism with namespace isolation
2. IF a repair scorer function raises an exception during smoke-text execution, THEN THE Eval_Engine SHALL record the exception and count that scorer as failing code_exec_rate
3. IF a repair scorer function does not return a numeric value, THEN THE Eval_Engine SHALL count that scorer as failing numeric_return_rate

### Requirement 12: Heldout Leakage Prevention

**User Story:** As a researcher, I want strict separation between heldout pair data and repair processes, so that repaired scorers are not overfit to the heldout set.

#### Acceptance Criteria

1. THE Pipeline SHALL ensure that Stage 7 prompt construction includes ONLY train-split pair text and ONLY aggregate heldout metrics (accuracy, mean_gap per scorer)
2. THE Pipeline SHALL ensure that Stage 8 prompt construction receives NO raw heldout pair text
3. THE Eval_Engine SHALL detect and flag heldout leakage by scanning Stage 7 output for any text matching raw heldout pair content
4. IF heldout_raw_text_leakage_count > 0, THEN THE Pipeline SHALL fail the Stage 7 hard gate evaluation

### Requirement 13: Parallel Generation Support

**User Story:** As a developer, I want Stage 5 pair generation and Stage 8 repair scorer generation to support concurrent LLM calls, so that generation is faster and scales with available Bedrock throughput.

#### Acceptance Criteria

1. WHEN parallel mode is enabled for Stage 5, THE Pipeline SHALL generate individual pairs via concurrent Bedrock calls using ThreadPoolExecutor with configurable max_workers
2. WHEN parallel mode is enabled for Stage 8, THE Pipeline SHALL generate individual repair scorers via concurrent Bedrock calls using ThreadPoolExecutor with configurable max_workers
3. THE Pipeline SHALL aggregate parallel generation results into the same output schema as sequential generation
4. THE Pipeline SHALL handle individual call failures gracefully, continuing with remaining parallel calls and reporting partial results
