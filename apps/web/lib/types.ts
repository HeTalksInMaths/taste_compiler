/** Top-level normalized type consumed by all UI components */
export interface TasteCompilerRun {
  run_id: string;
  goal: string;
  raw_text: string;
  run_metadata: RunMetadata;
  taste_map: TasteMap | null;
  spec_criteria: SpecCriterion[];
  scorers: ScorerEntry[];
  pair_summary: PairSummary | null;
  repair_summary: RepairSummary | null;
  selected_candidate: SelectedCandidate | null;
  agent_battery: null; // Placeholder for future
  raw_artifacts: Record<string, unknown>;
}

export interface RunMetadata {
  provider_name: string;
  model_id: string;
  aws_region: string;
  provider_generation_enabled: boolean;
  bedrock_validation_passed: boolean | null;
  bedrock_calls_made: number;
  generated_steps: string[];
  artifact_store: string;
  execution_backend: string;
}

export interface TasteMap {
  goal: string;
  rewards: TasteConcept[];
  punishes: TasteConcept[];
  preserves: TasteConcept[];
}

export interface TasteConcept {
  concept: string;
  description: string;
  research_basis: string;
  measurable_proxy_ideas: string[];
}

export interface SpecCriterion {
  criterion: string;
  status: "pass" | "warning" | "fail";
  computed_value: number | boolean;
  threshold: string;
}

export interface ScorerEntry {
  scorer_id: string;
  hypothesis: string;
  lineage: string;
  generation_round: number;
  test_accuracy: number;
  test_margin: number;
  pareto_member: boolean;
  survived_because: string;
  code?: string; // available in dev mode
}

export interface PairSummary {
  total_pairs: number;
  train_count: number;
  test_count: number;
  type_distribution: Record<string, number>;
}

export interface RepairSummary {
  honest_repair_summary: string;
  overall_improvement_claim_supported: boolean;
  new_scorer_enters_pareto: boolean;
  share_of_eligible_ensemble: number;
}

export interface SelectedCandidate {
  candidate_id: string;
  strategy: string;
  ensemble_score: number;
  explanation: string;
  text: string;
  policy_ok: boolean;
}

export type ProviderStatus =
  | { label: "Static / Mock"; badge: "red" }
  | { label: "Bedrock Metadata Only"; badge: "amber"; explanation: string }
  | { label: "Bedrock Live Research"; badge: "green" }
  | { label: "Bedrock Generation Failed / Incomplete"; badge: "red-amber" };

export type ViewMode = "product" | "dev";
export type DataMode = "mock" | "api";
