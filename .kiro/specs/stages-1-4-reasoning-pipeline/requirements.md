# Requirements Document

## Introduction

This feature implements Stages 1–4 of the EvalWeaver Reasoning Pipeline: a live, multi-stage reasoning chain that builds a causal evidence base for a target variable, converts it into a causal graph, maps graph nodes to measurable text features, and generates diverse executable scoring functions. Each stage runs against AWS Bedrock (Claude Sonnet 4), produces structured JSON outputs, undergoes deterministic evaluation, and fails loudly if quality thresholds are not met.

## Glossary

- **Pipeline**: The sequential execution engine that orchestrates Stages 1–4
- **Stage**: A single reasoning step consisting of prompt construction, LLM call, response parsing, and deterministic evaluation
- **Causal_Research_Search**: Stage 1 — discovers source-backed causal factors affecting a target variable
- **Causal_Graph_Generator**: Stage 2 — converts Stage 1 research into a structured causal graph with nodes and edges
- **Measurement_Research_Search**: Stage 3 — maps causal graph nodes to measurable text features
- **Scorer_Generator**: Stage 4 — produces diverse executable Python scoring functions grounded in the causal theory
- **Target_Variable**: The subjective text quality dimension being modeled (e.g., "trustworthy")
- **Eval_Engine**: The deterministic scoring subsystem that validates each stage's output against pass criteria
- **Pass_Criteria**: A set of numeric thresholds that a stage output must meet to proceed
- **Failure_Points_Report**: A markdown document recording which stages failed evaluation and why
- **Call_Meta**: Metadata captured per LLM call: latency, retry mode, max attempts, errors
- **Bedrock_Provider**: The existing BedrockClaudeProvider that handles Converse API communication
- **py_run_scorer**: The existing sandboxed Python execution environment for scorer code
- **Live_Canary_Flag**: The `--live-canary` CLI flag that triggers live Bedrock execution of all stages

## Requirements

### Requirement 1: Stage 1 — Causal Research Search Execution

**User Story:** As a researcher, I want the pipeline to automatically discover source-backed causal evidence for a target variable, so that subsequent stages have a rigorous foundation of causal claims.

#### Acceptance Criteria

1. WHEN the `--live-canary` flag is set and Stage 1 is invoked, THE Pipeline SHALL send the Stage 1 prompt (parameterized with target_variable) to the Bedrock_Provider and receive a JSON response
2. WHEN a valid JSON response is received from Stage 1, THE Pipeline SHALL parse it into the causal_research schema containing target_variable, causal_research array, and research_tensions array
3. THE Pipeline SHALL require each causal_research item to contain source_id, title, claim, causal_variable, effect_direction, mechanism, and evidence_strength fields
4. WHEN Stage 1 completes, THE Pipeline SHALL save the prompt, raw_response, parsed_json, eval_result, and call_meta as persistent artifacts
5. IF Stage 1 receives a non-JSON or unparseable response, THEN THE Pipeline SHALL record the failure in the Failure_Points_Report and halt execution

### Requirement 2: Stage 1 — Causal Research Evaluation

**User Story:** As a researcher, I want Stage 1 outputs to be deterministically evaluated for causal rigor, so that only high-quality evidence bases proceed to graph generation.

#### Acceptance Criteria

1. WHEN Stage 1 output is evaluated, THE Eval_Engine SHALL compute num_research_items, num_unique_causal_variables, mechanism_completeness_rate, effect_direction_coverage, source_trace_rate, causal_specificity_score, generic_advice_penalty, and tension_count
2. THE Eval_Engine SHALL compute mechanism_completeness_rate as the fraction of items with all of: claim, causal_variable, effect_direction, mechanism, and source_id populated
3. THE Eval_Engine SHALL compute causal_specificity_score by rewarding claims containing mechanistic language (because, leads to, increases, decreases, mediates, moderates, causes, drives, reduces, through, by making, as a result)
4. THE Eval_Engine SHALL compute generic_advice_penalty by detecting vague advice words (clear, good, engaging, effective, strong, better, important, high quality) in items lacking a mechanism
5. THE Eval_Engine SHALL mark Stage 1 as passing only when: num_research_items >= 8, num_unique_causal_variables >= 5, mechanism_completeness_rate >= 0.75, source_trace_rate >= 0.9, causal_specificity_score >= 0.6, tension_count >= 1, and generic_advice_penalty <= 0.25
6. IF Stage 1 fails pass criteria, THEN THE Pipeline SHALL write the eval signals to the Failure_Points_Report and halt execution

### Requirement 3: Stage 2 — Causal Graph Generation Execution

**User Story:** As a researcher, I want the pipeline to convert causal research into a structured graph, so that the causal theory is made explicit with nodes, edges, and tensions.

#### Acceptance Criteria

1. WHEN Stage 1 passes evaluation, THE Pipeline SHALL construct the Stage 2 prompt using the target_variable and Stage 1 parsed output, and send it to the Bedrock_Provider
2. WHEN a valid JSON response is received from Stage 2, THE Pipeline SHALL parse it into the causal graph schema containing target_variable, causal_nodes array, causal_edges array, causal_tensions array, and summary_theory
3. THE Pipeline SHALL require each causal_node to contain node_id, label, role, definition, mechanism, and evidence fields
4. THE Pipeline SHALL require each causal_edge to contain from, to, relationship, and claim fields
5. WHEN Stage 2 completes, THE Pipeline SHALL save the prompt, raw_response, parsed_json, eval_result, and call_meta as persistent artifacts
6. IF Stage 2 receives a non-JSON or unparseable response, THEN THE Pipeline SHALL record the failure in the Failure_Points_Report and halt execution

### Requirement 4: Stage 2 — Causal Graph Evaluation

**User Story:** As a researcher, I want Stage 2 outputs to be validated for graph structure and evidence traceability, so that only well-connected causal graphs proceed to measurement research.

#### Acceptance Criteria

1. WHEN Stage 2 output is evaluated, THE Eval_Engine SHALL compute num_nodes, num_edges, node_mechanism_rate, node_evidence_rate, edge_validity_rate, edge_explanation_rate, graph_connectedness_score, role_diversity_score, tension_count, and summary_uses_graph_terms
2. THE Eval_Engine SHALL compute edge_validity_rate as the fraction of edges where both from and to reference existing node_ids
3. THE Eval_Engine SHALL compute graph_connectedness_score as the fraction of nodes that participate in at least one edge (as source or target)
4. THE Eval_Engine SHALL compute role_diversity_score as the count of distinct roles (increases, decreases, mediates, moderates) present across all nodes
5. THE Eval_Engine SHALL mark Stage 2 as passing only when: num_nodes >= 5, num_edges >= 4, node_mechanism_rate >= 0.85, node_evidence_rate >= 0.8, edge_validity_rate >= 1.0, edge_explanation_rate >= 0.9, graph_connectedness_score >= 0.6, role_diversity_score >= 2, and tension_count >= 1
6. IF Stage 2 fails pass criteria, THEN THE Pipeline SHALL write the eval signals to the Failure_Points_Report and halt execution

### Requirement 5: Stage 3 — Measurement Research Search Execution

**User Story:** As a researcher, I want the pipeline to discover how each causal node can be measured in text, so that scoring functions have grounded measurement strategies.

#### Acceptance Criteria

1. WHEN Stage 2 passes evaluation, THE Pipeline SHALL construct the Stage 3 prompt using the target_variable and Stage 2 causal_nodes, and send it to the Bedrock_Provider
2. WHEN a valid JSON response is received from Stage 3, THE Pipeline SHALL parse it into the measurement_research schema containing target_variable and measurement_research array
3. THE Pipeline SHALL require each measurement_research item to contain source_id, causal_node, measurement_claim, text_features array, and implementation_ideas array
4. WHEN Stage 3 completes, THE Pipeline SHALL save the prompt, raw_response, parsed_json, eval_result, and call_meta as persistent artifacts
5. IF Stage 3 receives a non-JSON or unparseable response, THEN THE Pipeline SHALL record the failure in the Failure_Points_Report and halt execution

### Requirement 6: Stage 3 — Measurement Research Evaluation

**User Story:** As a researcher, I want Stage 3 outputs to be validated for measurement coverage and actionability, so that only implementable measurement strategies proceed to scorer generation.

#### Acceptance Criteria

1. WHEN Stage 3 output is evaluated, THE Eval_Engine SHALL compute node_measurement_coverage, num_measurement_items, text_feature_specificity_score, implementation_actionability_score, generic_metric_penalty, multi_measurement_rate, and node_reference_validity_rate
2. THE Eval_Engine SHALL compute node_measurement_coverage as the fraction of Stage 2 causal_nodes that have at least one measurement_research item referencing them
3. THE Eval_Engine SHALL compute node_reference_validity_rate as the fraction of measurement_research items whose causal_node field matches an existing Stage 2 node_id
4. THE Eval_Engine SHALL compute multi_measurement_rate as the fraction of covered nodes that have two or more measurement_research items
5. THE Eval_Engine SHALL mark Stage 3 as passing only when: node_measurement_coverage >= 0.7, num_measurement_items >= 8, text_feature_specificity_score >= 0.6, implementation_actionability_score >= 0.65, generic_metric_penalty <= 0.3, multi_measurement_rate >= 0.5, and node_reference_validity_rate >= 1.0
6. IF Stage 3 fails pass criteria, THEN THE Pipeline SHALL write the eval signals to the Failure_Points_Report and halt execution

### Requirement 7: Stage 4 — Scorer Hypothesis and Function Generation Execution

**User Story:** As a researcher, I want the pipeline to generate diverse executable scoring functions grounded in the causal theory and measurement research, so that the scorer population represents distinct theories of the target variable.

#### Acceptance Criteria

1. WHEN Stage 3 passes evaluation, THE Pipeline SHALL construct the Stage 4 prompt using the target_variable, Stage 2 causal graph, and Stage 3 measurement research, and send it to the Bedrock_Provider
2. WHEN a valid JSON response is received from Stage 4, THE Pipeline SHALL parse it into the scorers schema containing target_variable and scorers array
3. THE Pipeline SHALL require each scorer to contain scorer_id, hypothesis, causal_nodes_used, causal_edges_used, causal_tensions_used, measurement_ideas_used, functional_form, functional_form_rationale, expected_failure_mode, and code fields
4. THE Pipeline SHALL require each scorer code field to define a function with signature `def scorer(text, anchor, params)` that returns a numeric score
5. WHEN Stage 4 completes, THE Pipeline SHALL save the prompt, raw_response, parsed_json, eval_result, and call_meta as persistent artifacts
6. IF Stage 4 receives a non-JSON or unparseable response, THEN THE Pipeline SHALL record the failure in the Failure_Points_Report and halt execution

### Requirement 8: Stage 4 — Scorer Evaluation

**User Story:** As a researcher, I want Stage 4 outputs to be validated for hypothesis diversity, code executability, and causal grounding, so that only high-quality scorer populations proceed.

#### Acceptance Criteria

1. WHEN Stage 4 output is evaluated, THE Eval_Engine SHALL compute num_scorers, hypothesis_completeness_rate, causal_node_validity_rate, measurement_reference_rate, functional_form_diversity, interaction_usage_rate, normalization_usage_rate, code_exec_rate, numeric_return_rate, nonconstant_behavior_rate, scorer_distinctness_score, and hypothesis_code_alignment_score
2. THE Eval_Engine SHALL compute code_exec_rate by executing each scorer's code via py_run_scorer with the four smoke texts and confirming no exceptions are raised
3. THE Eval_Engine SHALL compute nonconstant_behavior_rate by running each scorer on the smoke texts and requiring different numeric outputs across at least two inputs
4. THE Eval_Engine SHALL compute scorer_distinctness_score as the count of unique tuples of (functional_form, causal_nodes_used, measurement_ideas_used) divided by num_scorers
5. THE Eval_Engine SHALL compute causal_node_validity_rate as the fraction of referenced causal_nodes_used entries that exist in the Stage 2 causal graph
6. THE Eval_Engine SHALL mark Stage 4 as passing only when: num_scorers >= 5, hypothesis_completeness_rate >= 1.0, causal_node_validity_rate >= 1.0, measurement_reference_rate >= 0.8, functional_form_diversity >= 4, interaction_usage_rate >= 0.4, normalization_usage_rate >= 0.5, code_exec_rate >= 1.0, numeric_return_rate >= 1.0, nonconstant_behavior_rate >= 0.8, scorer_distinctness_score >= 0.75, and hypothesis_code_alignment_score >= 0.5
7. IF Stage 4 fails pass criteria, THEN THE Pipeline SHALL write the eval signals to the Failure_Points_Report and halt execution

### Requirement 9: Pipeline Orchestration and Sequential Execution

**User Story:** As a developer, I want stages to execute sequentially with each stage's output feeding the next, so that the reasoning chain maintains causal coherence across all four stages.

#### Acceptance Criteria

1. THE Pipeline SHALL execute stages in strict order: Stage 1, Stage 2, Stage 3, Stage 4
2. WHEN a stage passes evaluation, THE Pipeline SHALL pass the stage's parsed_json output as input to the next stage's prompt construction
3. IF any stage fails evaluation, THEN THE Pipeline SHALL halt immediately without executing subsequent stages
4. WHEN all four stages pass evaluation, THE Pipeline SHALL report overall success with a summary of all eval signals
5. THE Pipeline SHALL be invoked via the existing CLI using the `--live-canary` flag with `target_variable` specified in the config file

### Requirement 10: Artifact Persistence

**User Story:** As a developer, I want every stage to save its full execution context, so that runs can be audited, debugged, and replayed.

#### Acceptance Criteria

1. THE Pipeline SHALL save for each stage: the constructed prompt, the raw LLM response text, the parsed JSON object, the eval result with all computed signals, and the call_meta (latency_ms, retry_mode, max_attempts, error)
2. WHEN a stage fails, THE Pipeline SHALL still persist all available artifacts up to the point of failure
3. THE Pipeline SHALL write a Failure_Points_Report (failure_points.md) summarizing pass/fail status for each executed stage, including the specific eval signals that failed thresholds

### Requirement 11: Scorer Code Safety

**User Story:** As a developer, I want Stage 4 scorer code to execute in a sandboxed namespace, so that generated code cannot access the file system or network.

#### Acceptance Criteria

1. WHEN evaluating Stage 4 scorer code, THE Eval_Engine SHALL execute each scorer function via the existing py_run_scorer mechanism with namespace isolation
2. IF a scorer function raises an exception during smoke-text execution, THEN THE Eval_Engine SHALL record the exception and count that scorer as failing code_exec_rate
3. IF a scorer function does not return a numeric value, THEN THE Eval_Engine SHALL count that scorer as failing numeric_return_rate

### Requirement 12: Smoke Text Validation for Scorers

**User Story:** As a researcher, I want scorers tested against predefined smoke texts, so that nonconstant behavior and numeric output can be verified without full pair evaluation.

#### Acceptance Criteria

1. THE Eval_Engine SHALL use exactly four smoke texts for Stage 4 validation: "This works because it gives teams a concrete way to test ideas before committing.", "This is the best and most revolutionary solution ever made.", "The tool helps users compare options, see tradeoffs, and choose a next step.", and "Maybe it helps in some cases, but the limits are unclear."
2. WHEN running smoke text validation, THE Eval_Engine SHALL execute each scorer with each smoke text as the text argument and use the target_variable config raw_text as the anchor argument
3. FOR ALL scorers passing code_exec_rate, THE Eval_Engine SHALL verify that at least two smoke texts produce different numeric scores to count toward nonconstant_behavior_rate
