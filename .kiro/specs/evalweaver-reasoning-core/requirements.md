# Requirements Document

## Introduction

EvalWeaver v5.1 Reasoning Core is an automated pipeline that takes a subjective text improvement goal (e.g., "make this more persuasive") and discovers, validates, and evolves quality scorers that evaluate text against that goal. It then uses those scorers to select the best candidate rewrite. The system operates through a multi-round evolutionary loop: research → taste map → NLP theory → scorer generation → pair-based evaluation → Pareto frontier selection → failure analysis → repair → re-evaluation → candidate selection. Version 5.1 hardens the pipeline beyond v5's known bugs with unified source policy enforcement, three-tier scorer validity vocabulary, honest execution isolation semantics, repair-improvement metrics, a mechanism_result_alignment probe, and artifact path robustness.

## Glossary

- **Pipeline**: The complete EvalWeaver execution from taste research through candidate selection
- **Taste_Research**: Gathered linguistic and psychological research related to the improvement goal; currently implemented as a mocked/seeded research artifact (live search via Exa and LLM calls via AWS are planned for future but not required now)
- **Taste_Map**: A structured synthesis of research into rewards, punishes, preserves, key tensions, and scorer hypothesis seeds
- **NLP_Theory**: A mapping from taste concepts to measurable NLP probes with implementation methods
- **Probe**: A Python function that measures a specific text property and returns a value in [0.0, 1.0]
- **Scorer**: A Python function combining multiple probes with weighting and gating logic to produce a quality score in [0.0, 1.0] for a text relative to an anchor
- **Scorer_Hypothesis**: A documented theory of how probes should combine to measure quality, including research basis, expected failure modes, and constants
- **Pair**: An evaluation unit consisting of an anchor text, a positive rewrite (higher quality), and a negative rewrite (lower quality)
- **Pair_Type**: A category indicating the trap or quality gap the pair tests (hype_trap, fake_mechanism, specificity_trap, subtle_quality_gap, source_drift)
- **Source_Policy**: Rules governing what a rewrite may introduce relative to its anchor (hard policy = veto via source_policy_violations, soft continuity = weighting)
- **source_policy_violations()**: A unified function that detects ALL hard source policy violations in a text relative to an anchor, returning a list of specific violation objects; used by both the scorer veto path and the candidate validation path
- **Source_Policy_Violation_Taxonomy**: The full set of violation types checked by source_policy_violations(): invented digit numbers, written-out numbers (e.g., "thousands", "triple"), time/quantity claims (e.g., "in seconds", "3x faster"), guarantee words ("guaranteed", "100%", "always", "never fails", "zero errors", "perfectly"), new named entities not present in the anchor, new customer/company claims, and award/certification/compliance claims
- **Hard_Source_Policy**: A binary check based on source_policy_violations() that vetoes text containing ANY violation from the Source_Policy_Violation_Taxonomy
- **Soft_Source_Continuity**: A continuous [0.0, 1.0] score measuring token, action-word, and domain-noun overlap between text and anchor
- **execution_valid**: A scorer that loads, runs without error, outputs bounded in [0,1], and produces non-constant outputs across pairs
- **pair_quality_valid**: A scorer that is execution_valid AND clears a low sanity threshold on validation pairs (e.g., accuracy > 0.5 and margin > 0)
- **pareto_eligible**: A scorer that is pair_quality_valid AND meets the full eligibility filter criteria (positive margins, minimum accuracy, minimum spread) for Pareto frontier and ensemble use
- **Pareto_Frontier**: The set of non-dominated scorers across multiple objectives (test accuracy, test margin, train accuracy, train margin, score spread)
- **Eligibility_Filter**: A set of preconditions a scorer must pass to be pareto_eligible (execution_valid, pair_quality_valid, no exec errors, positive margins, minimum accuracy, minimum spread)
- **Failure_Packet**: An analysis of top scorer failures including failed pairs, pair-type weaknesses, and generated mutation/adversarial instructions
- **Mutation_Instruction**: A directive for evolving scorers, tracked to avoid repetition across rounds
- **Adversarial_Pair**: A pair specifically designed to exploit weaknesses in current top scorers
- **Heldout_Set**: A frozen set of test pairs never exposed to repair prompts, with anti-leakage guarantees
- **Candidate**: A rewritten version of the input text produced by a generation strategy
- **Ensemble_Score**: A normalized, averaged score across all pareto_eligible scorers used to rank candidates
- **Computed_Criteria**: Self-validation metrics derived from pipeline artifacts at runtime, not hardcoded
- **Namespace_Isolation**: The restricted Python execution environment using exec() with a controlled globals dict; provides namespace isolation and exception catching but is NOT a security sandbox
- **Validation_Pairs**: A small diverse set of pairs used to verify scorer correctness before full evaluation
- **mechanism_result_alignment**: A probe that extracts mechanism-ish and result-ish clauses from text, rewards concrete action/object terms in both clauses, and penalizes jargon-only mechanism/result bridges
- **Repair_Improvement_Metrics**: Comparative metrics between old and new scorers on original and adversarial heldout sets, used to validate that the repair loop produces measurable improvement

## Requirements

### Requirement 1: Taste Research Gathering

**User Story:** As a pipeline operator, I want to gather linguistic and psychological research related to the improvement goal, so that scorer design is grounded in established theory.

#### Acceptance Criteria

1. WHEN an improvement goal is provided, THE Pipeline SHALL gather research on linguistic features, NLP measurable properties, and failure modes related to that goal
2. THE Pipeline SHALL produce research covering at least three distinct research dimensions (linguistic features, measurable NLP properties, failure modes)
3. THE Pipeline SHALL persist the raw research as a JSON artifact for downstream consumption
4. THE Pipeline SHALL document that research is currently a mocked/seeded research artifact; live search (via Exa) and LLM calls (via AWS) are planned for future iterations but are not required for the current version

### Requirement 2: Taste Map Synthesis

**User Story:** As a pipeline operator, I want research synthesized into a structured taste map, so that scorer hypotheses have a clear theoretical foundation.

#### Acceptance Criteria

1. WHEN raw research is available, THE Pipeline SHALL synthesize it into a Taste_Map containing rewards, punishes, preserves, key tensions, and scorer hypothesis seeds
2. THE Taste_Map SHALL contain at least three reward concepts, each with a research basis and measurable proxy ideas
3. THE Taste_Map SHALL contain at least one punish concept identifying quality-negative patterns
4. THE Taste_Map SHALL contain at least one preserve concept identifying properties that must be maintained
5. THE Taste_Map SHALL identify key tensions between competing quality signals
6. THE Taste_Map SHALL include scorer hypothesis seeds that inform initial scorer design

### Requirement 3: NLP Theory Mapping

**User Story:** As a pipeline operator, I want taste concepts mapped to measurable NLP probes, so that scorers can be implemented as executable code.

#### Acceptance Criteria

1. WHEN a Taste_Map is available, THE Pipeline SHALL produce an NLP_Theory mapping each taste concept to a probe with a defined measurement method and research reference
2. THE NLP_Theory SHALL include probes for: argument_progression, real_mechanism_quality, abstract_jargon_density, specificity_without_invention, mechanism_result_alignment, probe_source_continuity, source_policy_violations, probe_causal_density, probe_audience_relevance, probe_persuasion_risk, and probe_epistemic_calibration
3. THE Pipeline SHALL load all mapped probes into the Namespace_Isolation environment and confirm successful loading

### Requirement 4: Scorer Hypothesis Generation

**User Story:** As a pipeline operator, I want multiple scorer hypotheses generated before code, so that each scorer has documented rationale, expected failures, and tunable constants.

#### Acceptance Criteria

1. WHEN NLP_Theory and Taste_Map are available, THE Pipeline SHALL generate at least 8 distinct Scorer_Hypotheses for the initial round
2. EACH Scorer_Hypothesis SHALL include: scorer_id, lineage, hypothesis text, research_basis, taste_map_basis, expected_failure_mode, and constants_and_thresholds
3. THE Pipeline SHALL persist all hypotheses as a JSON artifact before code generation begins

### Requirement 5: Scorer Code Generation and Validation

**User Story:** As a pipeline operator, I want scorer code generated from hypotheses and validated on actual pairs, so that only functioning scorers enter evaluation.

#### Acceptance Criteria

1. WHEN Scorer_Hypotheses exist, THE Pipeline SHALL generate a Python scorer function for each hypothesis that combines probes with the specified weighting and gating logic
2. EACH scorer function SHALL accept (text, anchor, params) and return a clamped float in [0.0, 1.0]
3. WHEN a scorer is generated, THE Pipeline SHALL validate it using validate_scorer_on_pairs with diverse Validation_Pairs — not single-anchor spread testing
4. THE Pipeline SHALL classify each scorer into the three-tier validity vocabulary: execution_valid, pair_quality_valid, or pareto_eligible
5. A scorer SHALL be classified as execution_valid if it loads, runs without error on all validation pairs, outputs are bounded in [0.0, 1.0], and outputs are non-constant across pairs (spread ≥ 0.001)
6. A scorer SHALL be classified as pair_quality_valid if it is execution_valid AND achieves validation pair accuracy > 0.5 and validation pair margin > 0
7. THE Pipeline SHALL report pair_validation_accuracy, pair_validation_margin, pair_validation_spread, and validity_tier for each scorer
8. IF a scorer produces constant outputs across all pairs (spread < 0.001), THEN THE Pipeline SHALL mark it as not execution_valid with reason "constant_pair_outputs"
9. IF a scorer produces runtime errors on any validation pair, THEN THE Pipeline SHALL mark it as not execution_valid with reason "runtime_error"
10. IF a scorer produces values outside [−0.01, 1.01], THEN THE Pipeline SHALL mark it as not execution_valid with reason "out_of_range"

### Requirement 6: Pair Generation with Source Policy Validation

**User Story:** As a pipeline operator, I want evaluation pairs generated with source policy validation, so that contaminated pairs are removed before evaluation.

#### Acceptance Criteria

1. WHEN scorer validation is complete, THE Pipeline SHALL generate evaluation pairs covering at least four pair types: hype_trap, fake_mechanism, specificity_trap, subtle_quality_gap, and source_drift
2. EACH pair SHALL include: pair_id, anchor, positive, negative, pair_type, source_policy, label_contract, and intended_trap
3. THE Pipeline SHALL explicitly generate fake_mechanism pairs where both positive and negative use causal language but only the positive contains concrete content
4. WHEN pairs are generated, THE Pipeline SHALL validate each pair using the unified source_policy_violations() function applied to both positive and negative texts against the anchor
5. IF source_policy_violations() returns any violation for the positive text, THEN THE Pipeline SHALL drop that pair, recording the specific violation types and counts
6. THE Pipeline SHALL report dropped pairs grouped by violation type (invented digits, written-out numbers, time/quantity claims, guarantee words, new named entities, customer/company claims, award/certification claims)
7. THE Pipeline SHALL split valid pairs into train and heldout sets with the heldout set containing at least 8 pairs
8. THE Pipeline SHALL mark heldout pairs as frozen to prevent leakage into repair prompts

### Requirement 7: Unified Source Policy Enforcement

**User Story:** As a pipeline operator, I want a single unified source policy function covering the full violation taxonomy, so that all hard policy checks are consistent and complete.

#### Acceptance Criteria

1. THE source_policy_violations() function SHALL check for ALL of the following violation types: invented digit numbers, written-out numbers (e.g., "thousands", "triple", "dozens"), time/quantity claims (e.g., "in seconds", "3x faster"), guarantee words ("guaranteed", "100%", "always", "never fails", "zero errors", "perfectly"), new named entities not present in the anchor, new customer/company claims, and award/certification/compliance claims
2. THE source_policy_violations() function SHALL return a list of violation objects, each containing: violation_type, evidence (the specific text matched), and severity ("hard")
3. THE Hard_Source_Policy check SHALL return True (veto) when source_policy_violations() returns a non-empty list
4. THE same source_policy_violations() function SHALL be used by both the scorer veto path (Requirement 8 evaluation) and the candidate validation path (Requirement 15)
5. THE Soft_Source_Continuity probe SHALL return a continuous value in [0.0, 1.0] computed as 0.5×token_overlap + 0.25×action_word_overlap + 0.25×domain_noun_overlap
6. THE Soft_Source_Continuity probe SHALL NOT zero the score for legitimate rephrasing that preserves domain nouns and action words
7. WHEN a scorer evaluates text, THE scorer SHALL use Hard_Source_Policy (based on source_policy_violations()) as a binary veto (score = 0.0) and Soft_Source_Continuity as a multiplicative weight

### Requirement 8: Scorer Evaluation on Pair Suite

**User Story:** As a pipeline operator, I want all execution_valid scorers evaluated against the full pair suite, so that I can compare their discriminative ability.

#### Acceptance Criteria

1. WHEN pairs are validated and split, THE Pipeline SHALL evaluate each execution_valid scorer against every pair by running the scorer on both positive and negative text with the pair's anchor
2. THE Pipeline SHALL compute per-scorer metrics: train_accuracy, train_margin, test_accuracy, test_margin, score_spread, exec_error_rate, and pair_type_accuracy breakdown
3. THE Pipeline SHALL compute a correctness indicator for each pair: correct if positive_score > negative_score
4. THE Pipeline SHALL flag robustness warnings for any pair_type where accuracy < 0.45
5. THE Pipeline SHALL report validity tier counts: "N execution_valid, M pair_quality_valid, K pareto_eligible" in the evaluation summary

### Requirement 9: Pareto Eligibility Filter

**User Story:** As a pipeline operator, I want ineligible scorers filtered before Pareto computation, so that the frontier contains only reliably discriminative scorers.

#### Acceptance Criteria

1. WHEN evaluation metrics are computed, THE Eligibility_Filter SHALL reject scorers that are not execution_valid
2. THE Eligibility_Filter SHALL reject scorers that are not pair_quality_valid (accuracy ≤ 0.5 or margin ≤ 0 on validation pairs)
3. THE Eligibility_Filter SHALL reject scorers with exec_error_rate > 0
4. THE Eligibility_Filter SHALL reject scorers with score_spread < 0.02
5. THE Eligibility_Filter SHALL reject scorers with train_margin <= 0
6. THE Eligibility_Filter SHALL reject scorers with test_margin <= 0
7. THE Eligibility_Filter SHALL reject scorers with train_accuracy < 0.50
8. THE Eligibility_Filter SHALL reject scorers with test_accuracy < 0.50
9. WHEN eligibility filtering is complete, THE Pipeline SHALL classify passing scorers as pareto_eligible and compute the Pareto_Frontier over five objectives: test_accuracy, test_margin, train_accuracy, train_margin, and score_spread

### Requirement 10: Pareto Frontier Computation

**User Story:** As a pipeline operator, I want a Pareto frontier computed over multiple objectives, so that no single metric dominates scorer selection.

#### Acceptance Criteria

1. WHEN pareto_eligible scorers are identified, THE Pipeline SHALL compute the Pareto_Frontier such that a scorer is included only if no other pareto_eligible scorer dominates it on all five objectives simultaneously
2. THE Pipeline SHALL sort the Pareto_Frontier by test_margin, then test_accuracy, then train_margin (descending)
3. THE Pipeline SHALL annotate each Pareto member with a "survived_because" explanation identifying which dimension(s) it leads on

### Requirement 11: Failure Packet Generation

**User Story:** As a pipeline operator, I want a failure analysis of top scorers, so that repair can target specific weaknesses.

#### Acceptance Criteria

1. WHEN the Pareto_Frontier is computed, THE Pipeline SHALL build a Failure_Packet analyzing the top 3 Pareto scorers
2. THE Failure_Packet SHALL identify failed visible (train) pairs and low-margin visible pairs for top scorers
3. THE Failure_Packet SHALL compute pair-type-specific failure counts
4. THE Failure_Packet SHALL include score collapse warnings for scorers with spread < 0.05
5. THE Failure_Packet SHALL include heldout aggregate metrics (accuracy, margin, failures by type) without exposing raw heldout text
6. THE Failure_Packet SHALL generate mutation instructions targeting identified weaknesses
7. THE Failure_Packet SHALL generate adversarial pair instructions targeting scorer shortcuts
8. WHEN prior mutation instructions exist, THE Failure_Packet SHALL exclude previously applied instructions from the new mutation set

### Requirement 12: Scorer Mutation and Repair

**User Story:** As a pipeline operator, I want evolved scorer hypotheses and code generated from failure analysis, so that the pipeline improves across rounds.

#### Acceptance Criteria

1. WHEN a Failure_Packet is available, THE Pipeline SHALL generate at least 6 evolved Scorer_Hypotheses with lineage types: mutation, blind_node_repair, recombination, and novel_composition
2. EACH evolved hypothesis SHALL reference the specific weakness it addresses from the Failure_Packet
3. THE Pipeline SHALL generate code for each evolved hypothesis and validate it using validate_scorer_on_pairs
4. THE Pipeline SHALL classify each evolved scorer into the three-tier validity vocabulary (execution_valid, pair_quality_valid, pareto_eligible)
5. THE Pipeline SHALL track mutation instruction history so that repeated instructions are not applied in subsequent rounds

### Requirement 13: Adversarial Pair Generation

**User Story:** As a pipeline operator, I want adversarial pairs generated targeting specific scorer weaknesses, so that evaluation becomes progressively harder.

#### Acceptance Criteria

1. WHEN a Failure_Packet identifies scorer shortcuts, THE Pipeline SHALL generate adversarial pairs specifically attacking those shortcuts
2. EACH adversarial pair SHALL document: attacks_scorer_ids, attacked_shortcut, and intended_trap
3. THE Pipeline SHALL validate adversarial pairs against source_policy_violations() and drop invalid ones
4. THE Pipeline SHALL split adversarial pairs into a visible adversarial-train set and a new heldout set
5. THE Pipeline SHALL grow the heldout set by adding new test pairs, maintaining anti-leakage guarantees
6. WHEN adversarial pairs are added, THE Pipeline SHALL confirm the heldout set contains at least 15 pairs

### Requirement 14: Round 1 Full Re-Evaluation

**User Story:** As a pipeline operator, I want all scorers (original + evolved) re-evaluated against the expanded pair suite, so that evolved scorers are fairly compared.

#### Acceptance Criteria

1. WHEN evolved scorers and adversarial pairs are ready, THE Pipeline SHALL evaluate all scorers (Round 0 + Round 1) against the full expanded pair suite (train + adversarial + heldout)
2. THE Pipeline SHALL recompute the Eligibility_Filter and Pareto_Frontier for the combined scorer set
3. THE Pipeline SHALL generate a new Failure_Packet for Round 1 that tracks which prior mutation instructions were applied
4. THE Pipeline SHALL report validity tier counts for the combined set: "N execution_valid, M pair_quality_valid, K pareto_eligible"

### Requirement 14B: Repair-Improvement Metrics

**User Story:** As a pipeline operator, I want comparative metrics between old and new scorers on the same heldout sets, so that I can validate whether the repair loop produces measurable improvement.

#### Acceptance Criteria

1. WHEN Round 1 re-evaluation is complete, THE Pipeline SHALL compare Round 0 best scorers vs Round 1 new scorers on the SAME original heldout set (frozen from Round 0)
2. THE Pipeline SHALL compare Round 0 best scorers vs Round 1 new scorers on the new adversarial heldout set
3. THE Pipeline SHALL report whether any Round 1 scorer beats the Round 0 best scorer, specifying which dimensions (test_accuracy, test_margin, train_accuracy, train_margin, score_spread)
4. THE Pipeline SHALL report whether any Round 1 scorer enters the Pareto frontier (displacing or joining Round 0 members)
5. THE Pipeline SHALL NOT claim "evolution improved" unless at least one new scorer beats the old best on at least one dimension on either heldout set
6. THE Pipeline SHALL persist the repair-improvement comparison as a JSON artifact with fields: old_best_scorer_id, new_scorers_evaluated, improvements_found (list of {scorer_id, dimension, old_value, new_value}), new_pareto_entrants, and improvement_claim_supported (boolean)

### Requirement 15: Candidate Selection via Ensemble Scoring

**User Story:** As a pipeline operator, I want candidates scored by the pareto_eligible ensemble and the best one selected, so that the final rewrite reflects validated quality criteria.

#### Acceptance Criteria

1. WHEN a Pareto_Frontier with pareto_eligible scorers exists, THE Pipeline SHALL score each candidate text against all pareto_eligible ensemble scorers
2. THE Pipeline SHALL normalize scores per-scorer (min-max across candidates) before averaging
3. THE Pipeline SHALL compute an ensemble_score as the mean of normalized per-scorer scores for each candidate
4. THE Pipeline SHALL validate each candidate against source_policy_violations() using the SAME function used by the scorer veto path
5. EACH candidate SHALL store a policy_violations field containing the list of specific violations found by source_policy_violations()
6. A candidate SHALL have policy_ok = false if source_policy_violations() returns any violation
7. THE Pipeline SHALL select the candidate with the highest ensemble_score among candidates where policy_ok = true
8. WHEN a hype-control baseline candidate (C004) is included, THE Pipeline SHALL confirm that source_policy_violations() returns violations for it (guarantee/hype words) AND that its policy_ok = false
9. THE Pipeline SHALL report BOTH raw_mean_score (unormalized mean across scorers) AND normalized_ensemble_score for every candidate
10. WHEN a hype-control baseline candidate is included, THE Pipeline SHALL assert its raw_mean_score is zero or near-zero (< 0.05), not just its normalized score
11. WHEN an audience-pain candidate is included, THE Pipeline SHALL confirm it scores above zero (> 0.05 normalized) — verifying the soft source continuity fix

### Requirement 16: Computed Spec Criteria (Self-Validation)

**User Story:** As a pipeline operator, I want all quality criteria computed from pipeline artifacts at runtime, so that nothing is hardcoded and the pipeline self-validates.

#### Acceptance Criteria

1. THE Pipeline SHALL compute all spec criteria from runtime artifacts — no criteria value shall be hardcoded
2. THE Computed_Criteria SHALL verify: taste research present (≥3 dimensions), taste map rewards (≥3), taste map punishes (≥1), scorer hypotheses R0 (≥8), execution_valid scorers R0 (≥2), pair_quality_valid scorers R0 (≥1), invalid pairs either absent or explicitly dropped and counted by violation type, initial heldout count (≥8), Pareto R0 non-empty, failure packet has instructions, repair hypotheses generated (≥6), adversarial pairs generated (≥12), fake mechanism pairs (≥3), heldout grew, final heldout count (≥15), Pareto R1 non-empty, pareto_eligible ensemble exists, candidate selected, hype baseline policy_ok = false, hype baseline raw_mean_score < 0.05, and C002 not zeroed
3. THE Pipeline SHALL report pass/warn/fail status for each criterion
4. THE Pipeline SHALL persist all computed criteria as a JSON artifact
5. THE Pipeline SHALL report validity tier summary: "N execution_valid, M pair_quality_valid, K pareto_eligible" in the criteria output

### Requirement 17: Namespace-Isolated Scorer Execution

**User Story:** As a pipeline operator, I want scorer code executed in an isolated namespace with exception catching, so that malformed scorer code cannot corrupt the pipeline state.

#### Acceptance Criteria

1. THE Namespace_Isolation environment SHALL provide a restricted Python execution context via exec() with a controlled globals dict providing access only to: re, math, collections, string, statistics, unicodedata, and helper probes
2. THE Namespace_Isolation environment SHALL isolate scorer globals and catch exceptions, but this is NOT a security boundary — it provides namespace isolation, not sandboxing against untrusted code
3. WHEN scorer code raises an exception during execution, THE Pipeline SHALL catch the error, return a default value of 0.5, and record the error without halting the pipeline
4. THE Pipeline SHALL clamp all scorer outputs to [0.0, 1.0] regardless of what the scorer function returns
5. THE Pipeline SHALL document that real sandboxing (for untrusted code execution) is a separate future project and is not provided by the current namespace isolation mechanism

### Requirement 18: Probe Implementation (Five Core Probes)

**User Story:** As a pipeline operator, I want five probes (argument_progression, real_mechanism_quality, abstract_jargon_density, specificity_without_invention, mechanism_result_alignment) implemented, so that scorers can distinguish genuine quality from fake signals.

#### Acceptance Criteria

1. THE argument_progression probe SHALL detect problem→mechanism→result structure using marker-based pattern matching and return 1.0 when all three stages are present, 0.7 for mechanism+result, 0.5 for problem+result, 0.4 for mechanism only, and 0.0 otherwise
2. THE real_mechanism_quality probe SHALL reward causal markers followed by concrete domain terms and penalize causal markers followed by fake mechanism phrases
3. THE abstract_jargon_density probe SHALL compute the density of jargon words relative to total content tokens and return a value in [0.0, 1.0]
4. THE specificity_without_invention probe SHALL return 0.0 if source_policy_violations() returns any violation, otherwise compute specificity from named entities and action verbs minus jargon penalty
5. THE mechanism_result_alignment probe SHALL extract mechanism-ish clauses and result-ish clauses from the text
6. THE mechanism_result_alignment probe SHALL reward concrete action/object terms present in both mechanism and result clauses
7. THE mechanism_result_alignment probe SHALL penalize jargon-only mechanism/result bridges (where mechanism or result clause contains only abstract jargon with no concrete domain nouns or action verbs)
8. THE mechanism_result_alignment probe SHALL return a value in [0.0, 1.0] where higher values indicate concrete mechanism-to-result alignment and lower values indicate abstract/jargon-only bridges

### Requirement 19: Artifact Persistence and Traceability

**User Story:** As a pipeline operator, I want all pipeline artifacts persisted as JSON with a structured trace log, so that any pipeline run can be audited and reproduced.

#### Acceptance Criteria

1. THE Pipeline SHALL persist a JSON artifact for each major step: raw research, taste map, NLP theory, scorer hypotheses, scorer code + validation, pairs, evaluation results, summaries, Pareto frontiers, failure packets, adversarial pairs, candidate scores, final selection, computed criteria, repair-improvement metrics, and trace log
2. THE Pipeline SHALL maintain a chronological trace log with timestamp, stage, status (ok/warn/error), and message for every significant operation
3. THE Pipeline SHALL produce a run summary artifact containing version, goal, v5.1 fixes applied, counts of all major entities, best scorers per round, selected candidate, and computed criteria summary
4. THE Pipeline SHALL allow the output directory to be configured via an environment variable (defaulting to a sensible path if unset)
5. THE Pipeline SHALL NOT assume /mnt/user-data or any specific external mount exists; missing output directories SHALL be created or gracefully handled without crashing the run
6. THE Pipeline SHALL produce a ZIP archive containing all JSON artifacts from the run
7. THE ZIP archive SHALL include the source script file only when __file__ is defined in the execution context
8. IF a configured output directory does not exist and cannot be created, THEN THE Pipeline SHALL fall back to a temporary directory and log a warning rather than crashing
