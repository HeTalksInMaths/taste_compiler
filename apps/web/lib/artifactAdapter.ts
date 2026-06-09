import type {
  TasteCompilerRun,
  RunMetadata,
  TasteMap,
  TasteConcept,
  SpecCriterion,
  ScorerEntry,
  PairSummary,
  RepairSummary,
  SelectedCandidate,
} from "./types";

/**
 * Raw artifact shape matching the fixture file structure.
 * All fields are optional/unknown — the adapter never assumes presence.
 */
export interface RawArtifacts {
  run_summary?: unknown;
  taste_map?: unknown;
  scorer_functions_r0?: unknown;
  scorer_functions_r1?: unknown;
  pairs_r0?: unknown;
  pareto_r0?: unknown;
  pareto_r1?: unknown;
  failure_packet_r0?: unknown;
  repair_metrics?: unknown;
  final_selection?: unknown;
  computed_criteria?: unknown;
  trace?: unknown;
}

// ---------------------------------------------------------------------------
// Internal helpers — safe field extraction
// ---------------------------------------------------------------------------

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function str(v: unknown, fallback: string = ""): string {
  return typeof v === "string" ? v : fallback;
}

function num(v: unknown, fallback: number = 0): number {
  return typeof v === "number" && !Number.isNaN(v) ? v : fallback;
}

function bool(v: unknown, fallback: boolean | null = null): boolean | null {
  return typeof v === "boolean" ? v : fallback;
}

function boolStrict(v: unknown, fallback: boolean = false): boolean {
  return typeof v === "boolean" ? v : fallback;
}

function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function strArr(v: unknown): string[] {
  return arr(v).filter((x): x is string => typeof x === "string");
}

// ---------------------------------------------------------------------------
// Section adapters
// ---------------------------------------------------------------------------

function adaptRunMetadata(summary: unknown): RunMetadata {
  const meta = isRecord(summary) && isRecord((summary as Record<string, unknown>).run_metadata)
    ? (summary as Record<string, unknown>).run_metadata as Record<string, unknown>
    : {} as Record<string, unknown>;

  return {
    provider_name: str(meta.provider_name, "mock"),
    model_id: str(meta.model_id, "unknown"),
    aws_region: str(meta.aws_region, ""),
    provider_generation_enabled: boolStrict(meta.provider_generation_enabled, false),
    bedrock_validation_passed: bool(meta.bedrock_validation_passed, null),
    bedrock_calls_made: num(meta.bedrock_calls_made, 0),
    generated_steps: strArr(meta.generated_steps),
    artifact_store: str(meta.artifact_store, "local_json"),
    execution_backend: str(meta.execution_backend, "unknown"),
  };
}

function adaptTasteMap(raw: unknown): TasteMap | null {
  if (!isRecord(raw)) return null;

  const adaptConcepts = (list: unknown): TasteConcept[] =>
    arr(list)
      .filter(isRecord)
      .map((c) => ({
        concept: str(c.concept),
        description: str(c.description),
        research_basis: str(c.research_basis),
        measurable_proxy_ideas: strArr(c.measurable_proxy_ideas),
      }));

  return {
    goal: str(raw.goal),
    rewards: adaptConcepts(raw.rewards),
    punishes: adaptConcepts(raw.punishes),
    preserves: adaptConcepts(raw.preserves),
  };
}

function adaptScorers(
  scorerFunctionsR0: unknown,
  scorerFunctionsR1: unknown,
  paretoR0: unknown,
  paretoR1: unknown,
): ScorerEntry[] {
  // Build a lookup of pareto entries by scorer_id
  const paretoMap = new Map<string, Record<string, unknown>>();
  for (const entry of arr(paretoR0)) {
    if (isRecord(entry) && typeof entry.scorer_id === "string") {
      paretoMap.set(entry.scorer_id, entry);
    }
  }
  for (const entry of arr(paretoR1)) {
    if (isRecord(entry) && typeof entry.scorer_id === "string") {
      // R1 entries may override R0 entries if same ID
      if (!paretoMap.has(entry.scorer_id)) {
        paretoMap.set(entry.scorer_id, entry);
      }
    }
  }

  const entries: ScorerEntry[] = [];
  const seen = new Set<string>();

  // Process scorer functions from r0
  if (isRecord(scorerFunctionsR0)) {
    for (const [scorerId, value] of Object.entries(scorerFunctionsR0)) {
      seen.add(scorerId);
      const scorerData = isRecord(value) ? value : {};
      const paretoEntry = paretoMap.get(scorerId);

      entries.push(buildScorerEntry(scorerId, scorerData, paretoEntry, 0));
    }
  }

  // Process scorer functions from r1
  if (isRecord(scorerFunctionsR1)) {
    for (const [scorerId, value] of Object.entries(scorerFunctionsR1)) {
      if (seen.has(scorerId)) continue; // already processed from r0
      seen.add(scorerId);
      const scorerData = isRecord(value) ? value : {};
      const paretoEntry = paretoMap.get(scorerId);

      entries.push(buildScorerEntry(scorerId, scorerData, paretoEntry, 1));
    }
  }

  // Process pareto entries that weren't in scorer_functions
  for (const [scorerId, paretoEntry] of paretoMap.entries()) {
    if (seen.has(scorerId)) continue;
    seen.add(scorerId);
    entries.push(buildScorerEntry(scorerId, {}, paretoEntry, num(paretoEntry.generation_round, 0)));
  }

  return entries;
}

function buildScorerEntry(
  scorerId: string,
  scorerData: Record<string, unknown>,
  paretoEntry: Record<string, unknown> | undefined,
  defaultRound: number,
): ScorerEntry {
  const entry: ScorerEntry = {
    scorer_id: scorerId,
    hypothesis: str(paretoEntry?.hypothesis ?? scorerData.hypothesis),
    lineage: str(paretoEntry?.lineage ?? scorerData.lineage, "unknown"),
    generation_round: num(paretoEntry?.generation_round ?? defaultRound, defaultRound),
    test_accuracy: num(paretoEntry?.test_accuracy ?? extractValidation(scorerData, "pair_validation_accuracy"), 0),
    test_margin: num(paretoEntry?.test_margin ?? extractValidation(scorerData, "pair_validation_margin"), 0),
    pareto_member: paretoEntry !== undefined,
    survived_because: str(paretoEntry?.survived_because),
  };

  // Attach code if available
  if (typeof scorerData.code === "string") {
    entry.code = scorerData.code;
  }

  return entry;
}

function extractValidation(scorerData: Record<string, unknown>, field: string): unknown {
  if (isRecord(scorerData.validation)) {
    return (scorerData.validation as Record<string, unknown>)[field];
  }
  return undefined;
}

function adaptPairSummary(raw: unknown): PairSummary | null {
  const pairs = arr(raw);
  if (pairs.length === 0) return null;

  let trainCount = 0;
  let testCount = 0;
  const typeDistribution: Record<string, number> = {};

  for (const pair of pairs) {
    if (!isRecord(pair)) continue;
    const split = str(pair.split);
    if (split === "train") trainCount++;
    else if (split === "test") testCount++;

    const pairType = str(pair.pair_type);
    if (pairType) {
      typeDistribution[pairType] = (typeDistribution[pairType] || 0) + 1;
    }
  }

  return {
    total_pairs: pairs.length,
    train_count: trainCount,
    test_count: testCount,
    type_distribution: typeDistribution,
  };
}

function adaptRepairSummary(raw: unknown): RepairSummary | null {
  if (!isRecord(raw)) return null;

  return {
    honest_repair_summary: str(raw.honest_repair_summary),
    overall_improvement_claim_supported: boolStrict(raw.overall_improvement_claim_supported, false),
    new_scorer_enters_pareto: boolStrict(raw.new_scorer_enters_pareto, false),
    share_of_eligible_ensemble: num(raw.share_of_eligible_ensemble, 0),
  };
}

function adaptSelectedCandidate(raw: unknown): SelectedCandidate | null {
  if (!isRecord(raw)) return null;

  // The fixture wraps the candidate in a "selected" key
  const selected = isRecord(raw.selected) ? raw.selected as Record<string, unknown> : raw;

  // If there's no candidate_id even in the selected object, it's not valid data
  if (typeof selected.candidate_id !== "string" && typeof selected.candidate_id !== "number") {
    return null;
  }

  const explanation = str(
    (raw as Record<string, unknown>).explanation_for_product_mode ?? selected.explanation
  );

  return {
    candidate_id: str(String(selected.candidate_id)),
    strategy: str(selected.strategy),
    ensemble_score: num(selected.ensemble_score, 0),
    explanation,
    text: str(selected.text),
    policy_ok: boolStrict(selected.policy_ok, true),
  };
}

function adaptSpecCriteria(raw: unknown): SpecCriterion[] {
  return arr(raw)
    .filter(isRecord)
    .map((c) => ({
      criterion: str(c.criterion),
      status: adaptCriterionStatus(c.status),
      computed_value: typeof c.computed_value === "boolean" ? c.computed_value : num(c.computed_value, 0),
      threshold: str(String(c.threshold ?? "")),
    }));
}

function adaptCriterionStatus(v: unknown): "pass" | "warning" | "fail" {
  const s = str(v as string);
  if (s === "pass" || s === "warning" || s === "fail") return s;
  return "fail";
}

// ---------------------------------------------------------------------------
// Main adapter export
// ---------------------------------------------------------------------------

/**
 * Converts raw EvalWeaver artifact JSON into a normalized TasteCompilerRun.
 * NEVER throws — returns null/safe defaults for missing fields.
 */
export function adaptArtifacts(raw: RawArtifacts): TasteCompilerRun {
  const summary = isRecord(raw.run_summary) ? raw.run_summary as Record<string, unknown> : {};

  const runId = str(summary.version, `run_${Date.now()}`);
  const goal = str(summary.goal);
  const rawText = str(summary.raw_text);

  return {
    run_id: runId,
    goal,
    raw_text: rawText,
    run_metadata: adaptRunMetadata(raw.run_summary),
    taste_map: adaptTasteMap(raw.taste_map),
    spec_criteria: adaptSpecCriteria(raw.computed_criteria),
    scorers: adaptScorers(
      raw.scorer_functions_r0,
      raw.scorer_functions_r1,
      raw.pareto_r0,
      raw.pareto_r1,
    ),
    pair_summary: adaptPairSummary(raw.pairs_r0),
    repair_summary: adaptRepairSummary(raw.repair_metrics),
    selected_candidate: adaptSelectedCandidate(raw.final_selection),
    agent_battery: null,
    raw_artifacts: buildRawArtifacts(raw),
  };
}

function buildRawArtifacts(raw: RawArtifacts): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(raw)) {
    if (value !== undefined) {
      result[key] = value;
    }
  }
  return result;
}
