# Design Document: Taste Compiler Frontend

## Overview

The Taste Compiler Frontend is a Next.js App Router application (`apps/web/`) that visualizes EvalWeaver pipeline artifacts as a judge-facing product UI. It does not execute any pipeline logic or make LLM calls — it reads pre-computed JSON artifacts and renders them across structured panels.

The system operates in two data modes:
- **Mock Artifact Mode** (MVP): reads checked-in fixture JSON from `apps/web/fixtures/sample_run/`
- **Local API Mode** (future): fetches from `/api/runs/[runId]` endpoints

An artifact adapter (`artifactAdapter.ts`) normalizes raw EvalWeaver JSON into a `TasteCompilerRun` TypeScript type consumed by all UI components. Provider status classification logic determines how to badge a run based on its metadata. A product/dev mode toggle controls panel visibility.

## Architecture

```mermaid
graph TD
    subgraph "Next.js App Router (apps/web/)"
        A[Layout - Dark Theme] --> B[Landing Page /]
        A --> C[Run Page /runs/[runId]]
        C --> D[RunHeader]
        C --> E[HonestyCard]
        C --> F[PipelineTimeline]
        C --> G[TasteMapPanel]
        C --> H[ScorerParetoTable]
        C --> I[PairSuitePanel]
        C --> J[RepairPanel]
        C --> K[CandidatePanel]
        C --> L[AgentBatteryPanel]
        C --> M[ArtifactDebugPanel]
    end

    subgraph "Data Layer"
        N[artifactAdapter.ts] --> O[TasteCompilerRun]
        P[fixtures/sample_run/*.json] --> N
        Q[/api/runs/runId] --> N
        R[providerStatus.ts] --> D
        R --> E
    end

    subgraph "Mode Control"
        S[DataModeProvider] --> |mock| P
        S --> |api| Q
        T[ViewModeProvider] --> |product| C
        T --> |dev| C
    end
```

### Key Architectural Decisions

1. **Adapter-first data contract**: All components consume `TasteCompilerRun`, never raw artifact JSON. This decouples UI from artifact naming/versioning.
2. **Server Components for data loading**: The run page uses async Server Components to load fixtures or call API routes. No client-side fetching for initial render.
3. **Client Components for interactivity**: Mode toggle, collapsible panels, and debug views are Client Components.
4. **No runtime secrets in browser**: API keys live exclusively in server-side env vars accessed by API route handlers.
5. **Fixture-first development**: The app is fully functional with zero network dependencies using checked-in fixtures.

## Components and Interfaces

### Page Structure

```
apps/web/
├── app/
│   ├── layout.tsx              # Root layout: dark theme, fonts, providers
│   ├── page.tsx                # Landing page (/)
│   ├── runs/
│   │   └── [runId]/
│   │       └── page.tsx        # Run page - Server Component, loads data
│   └── api/
│       └── runs/
│           ├── route.ts        # GET /api/runs - list available runs
│           └── [runId]/
│               └── route.ts    # GET /api/runs/[runId] - full artifact JSON
├── components/
│   ├── RunHeader.tsx           # run_id, goal, raw_text, ProviderStatus badge
│   ├── HonestyCard.tsx         # Provider status, generation steps, evaluator type
│   ├── PipelineTimeline.tsx    # Research → Taste Map → ... → Rewrite
│   ├── TasteMapPanel.tsx       # rewards, punishes, preserves
│   ├── ScorerParetoTable.tsx   # Pareto frontier table
│   ├── PairSuitePanel.tsx      # Pair counts, type distribution
│   ├── RepairPanel.tsx         # honest_repair_summary, claim_supported
│   ├── CandidatePanel.tsx      # Selected candidate details
│   ├── AgentBatteryPanel.tsx   # Placeholder
│   ├── ArtifactDebugPanel.tsx  # Raw JSON, collapsible (dev mode only)
│   ├── ModeToggle.tsx          # Product/Dev mode switch
│   └── PanelShell.tsx          # Shared panel wrapper with "No data" fallback
├── lib/
│   ├── artifactAdapter.ts      # Raw JSON → TasteCompilerRun
│   ├── providerStatus.ts       # Metadata → ProviderStatus classification
│   ├── dataLoader.ts           # Mode-aware data loading (fixture vs API)
│   └── types.ts                # TasteCompilerRun and related types
├── fixtures/
│   └── sample_run/
│       ├── run_summary.json          # Bedrock live research run metadata
│       ├── taste_map.json
│       ├── scorer_functions_r0.json
│       ├── scorer_functions_r1.json
│       ├── pairs_r0.json
│       ├── pareto_r0.json
│       ├── pareto_r1.json
│       ├── failure_packet_r0.json
│       ├── repair_metrics.json
│       ├── final_selection.json
│       ├── computed_criteria.json
│       └── trace.json
├── providers/
│   ├── DataModeProvider.tsx    # React context for mock vs api mode
│   └── ViewModeProvider.tsx    # React context for product vs dev mode
└── styles/
    └── globals.css             # Dark theme, monospace, status badge colors
```

### Component Responsibilities

| Component | Input | Responsibility |
|-----------|-------|----------------|
| `RunHeader` | `TasteCompilerRun` | Displays run_id, goal, raw_text, and ProviderStatus badge |
| `HonestyCard` | `run_metadata` | **First-screen required component.** Summarizes what is live vs deterministic. Must show: Provider status, Model ID, Generated steps, Bedrock calls made, "Evaluator: deterministic", "Scorer generation: static" (unless metadata proves otherwise), "Pair generation: static" (unless metadata proves otherwise) |
| `PipelineTimeline` | none (static) | Visual sequence: Research → Taste Map → Scorer Evolution → Pair Tests → Repair → Rewrite |
| `TasteMapPanel` | `taste_map` | Renders rewards/punishes/preserves with concept names and descriptions |
| `ScorerParetoTable` | `scorers` | Table of scorer IDs, test accuracy, test margin, Pareto membership |
| `PairSuitePanel` | `pair_summary` | Pair count, type distribution (hype_trap, fake_mechanism, etc.), train/test split |
| `RepairPanel` | `repair_summary` | Shows honest_repair_summary text and overall_improvement_claim_supported boolean |
| `CandidatePanel` | `selected_candidate` | Candidate ID, strategy, ensemble score, explanation |
| `AgentBatteryPanel` | none | Placeholder panel for future metrics |
| `ArtifactDebugPanel` | `raw_artifacts` | Collapsible raw JSON for each artifact (dev mode only) |
| `ModeToggle` | ViewMode context | Toggles product ↔ dev without page reload |
| `PanelShell` | title, children, data presence | Wraps panels with header and "No data" fallback |


## Data Models

### TasteCompilerRun Type

```typescript
// apps/web/lib/types.ts

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
  provider_name: string;          // "mock" | "bedrock"
  model_id: string;               // e.g. "anthropic.claude-3-5-sonnet-20241022-v2:0"
  aws_region: string;             // e.g. "us-west-2"
  provider_generation_enabled: boolean;
  bedrock_validation_passed: boolean | null;
  bedrock_calls_made: number;
  generated_steps: string[];      // e.g. ["research"] or []
  artifact_store: string;         // "local_json"
  execution_backend: string;      // "evalweaver_v51"
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
  type_distribution: Record<string, number>; // e.g. { hype_trap: 5, fake_mechanism: 6, ... }
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
```

### Raw Artifact Shapes (from EvalWeaver)

The adapter maps these raw JSON structures:

| Artifact File | Key Fields | Maps To |
|---------------|-----------|---------|
| `run_summary_v5.json` | `version`, `goal`, `raw_text`, `counts`, `r0_best`, `r1_best`, `selected_candidate`, `spec_criteria_summary` | `run_id`, `goal`, `raw_text`, top-level counts |
| `step2_taste_map.json` | `goal`, `rewards[]`, `punishes[]`, `preserves[]` | `taste_map` |
| `step4b_scorer_functions_r0.json` | `{scorer_id: {hypothesis, code, validation}}` | `scorers[]` (merged with pareto data) |
| `step5_pairs_r0.json` | `[{pair_id, pair_type, split, ...}]` | `pair_summary` (aggregated) |
| `step6_pareto_r0.json` | `[{scorer_id, test_accuracy, test_margin, survived_because}]` | `scorers[].pareto_member`, `scorers[].test_accuracy`, etc. |
| `step7_failure_packet_r0.json` | `{failed_visible_pairs, mutation_instructions, ...}` | Available in `raw_artifacts` |
| `step10_repair_improvement_metrics.json` | `{overall_improvement_claim_supported, honest_repair_summary, ...}` | `repair_summary` |
| `step11_final_selection.json` | `{selected: {candidate_id, strategy, ensemble_score, ...}, explanation_for_product_mode}` | `selected_candidate` |
| `step12_computed_criteria.json` | `[{criterion, status, computed_value, threshold}]` | `spec_criteria` |
| `trace.json` | `[{ts, stage, status, msg}]` | Available in `raw_artifacts` |

### Artifact Adapter Design

```typescript
// apps/web/lib/artifactAdapter.ts

export interface RawArtifacts {
  run_summary: unknown;
  taste_map: unknown;
  scorer_functions_r0: unknown;
  scorer_functions_r1?: unknown;
  pairs_r0: unknown;
  pareto_r0: unknown;
  pareto_r1?: unknown;
  failure_packet_r0?: unknown;
  repair_metrics?: unknown;
  final_selection: unknown;
  computed_criteria?: unknown;
  trace?: unknown;
}

export function adaptArtifacts(raw: RawArtifacts): TasteCompilerRun {
  // 1. Extract run_summary fields (goal, raw_text, version as run_id)
  // 2. Build run_metadata from run_summary + fixture metadata
  // 3. Adapt taste_map (pass through or null)
  // 4. Merge scorer_functions + pareto into ScorerEntry[]
  // 5. Aggregate pairs into PairSummary
  // 6. Adapt repair_metrics into RepairSummary
  // 7. Adapt final_selection into SelectedCandidate
  // 8. Adapt computed_criteria into SpecCriterion[]
  // 9. Store all raw inputs in raw_artifacts
  // Safe defaults: null for missing optional sections, [] for missing arrays
}
```

The adapter follows these rules:
1. **Never throw** — missing fields produce `null` or safe defaults
2. **Mark unavailable** — panels check for null to show "Data unavailable"
3. **Preserve raw** — all original JSON is kept in `raw_artifacts` for dev mode
4. **Round-trip stable** — `adapt(serialize(adapt(raw))) === adapt(raw)`

### Provider Status Classification Logic

```typescript
// apps/web/lib/providerStatus.ts

export function classifyProvider(meta: RunMetadata): ProviderStatus {
  // Step 1: Check provider_name first
  if (!meta.provider_name || meta.provider_name === "mock") {
    return { label: "Static / Mock", badge: "red" };
  }

  // Step 2: provider_name is "bedrock"
  if (!meta.provider_generation_enabled) {
    return {
      label: "Bedrock Metadata Only",
      badge: "amber",
      explanation: "Bedrock credentials/model selected, but no live generation steps were executed."
    };
  }

  // Step 3: generation enabled — check success conditions
  const hasResearch = meta.generated_steps.includes("research");
  const hasCalls = meta.bedrock_calls_made >= 1;
  const validationNotFailed = meta.bedrock_validation_passed !== false;

  if (hasResearch && hasCalls && validationNotFailed) {
    return { label: "Bedrock Live Research", badge: "green" };
  }

  // Step 4: generation enabled but failed/incomplete
  return { label: "Bedrock Generation Failed / Incomplete", badge: "red-amber" };
}
```

### Data Loading Strategy

```typescript
// apps/web/lib/dataLoader.ts

export async function loadRun(runId: string): Promise<TasteCompilerRun> {
  const mode = (process.env.TASTE_COMPILER_DATA_MODE || "mock") as DataMode;

  if (mode === "mock") {
    // Server Component reads fixture JSON via fs from apps/web/fixtures/sample_run/
    // Zero network requests — purely filesystem reads at build/render time
    const raw = await loadFixturesFromDisk(runId);
    return adaptArtifacts(raw);
  }

  // mode === "api"
  // Server-side fetch to absolute backend URL (never browser-side)
  const apiUrl = process.env.TASTE_COMPILER_API_URL || "http://localhost:3001";
  const res = await fetch(`${apiUrl}/api/runs/${runId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Run fetch failed: ${res.status}`);
  const raw = await res.json();
  return adaptArtifacts(raw);
}
```

Data mode is determined by:
- Server-side environment variable `TASTE_COMPILER_DATA_MODE` (values: `"mock"` | `"api"`)
- Defaults to `"mock"` when not set
- This is NOT a `NEXT_PUBLIC_` variable — it is only accessible in Server Components and API route handlers
- In mock mode, Server Components read fixture JSON directly via `fs` (no network requests)
- In api mode, Server Components call an absolute backend URL from `TASTE_COMPILER_API_URL` env var

### Product/Dev Mode Toggle

- Stored in React context (`ViewModeProvider`)
- Defaults to `"product"` on initial load
- Toggle is a client-side state change — no page reload
- Product mode hides: `ArtifactDebugPanel`, scorer `code` fields, artifact download buttons
- Dev mode shows: all panels, raw JSON, scorer code, download buttons

### Fixture Requirements

The primary demo fixture (`apps/web/fixtures/sample_run/`) must represent a **successful Bedrock live research run** with:
- `provider_name`: `"bedrock"`
- `model_id`: `"us.anthropic.claude-sonnet-4-6"`
- `provider_generation_enabled`: `true`
- `bedrock_calls_made`: `1`
- `generated_steps`: `["research"]`
- `bedrock_validation_passed`: `true`
- Research character count should be visible in the taste_map or run_summary if available

This ensures the demo screenshot shows "Bedrock Live Research" (green badge) with a real model ID. Exa or other research providers are not part of MVP — current research proof is the Bedrock live research step.

### Build Acceptance Criteria

The following must pass before the frontend is considered complete:

1. `npm run dev` starts without errors in `apps/web/`
2. `npm run build` completes without errors in `apps/web/`
3. `/` renders the landing page
4. `/runs/demo` renders the full run page from fixture JSON
5. `/runs/demo` works with no backend running and no network calls
6. No client-side Anthropic, Bedrock, or Exa API calls in browser code
7. No API keys present in the client-side JavaScript bundle
8. HonestyCard is visible on first screen of `/runs/demo`


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Adapter structural completeness

*For any* valid set of raw EvalWeaver artifact JSON files (run_summary, taste_map, scorer_functions, pairs, pareto, repair_metrics, final_selection, computed_criteria), adapting them should produce a TasteCompilerRun object where: `run_id` is a non-empty string, `goal` is a non-empty string, `raw_text` is a string, `run_metadata` contains all nine specified fields (provider_name, model_id, aws_region, provider_generation_enabled, bedrock_validation_passed, bedrock_calls_made, generated_steps, artifact_store, execution_backend), and `raw_artifacts` contains all input artifacts.

**Validates: Requirements 3.1, 3.2**

### Property 2: Adapter graceful handling of partial inputs

*For any* set of raw artifact files where one or more files are missing or contain null values for expected fields, the adapter should never throw an exception, and should produce a valid TasteCompilerRun where missing sections are represented as `null` (for optional objects like taste_map, repair_summary, selected_candidate) or empty arrays (for lists like scorers, spec_criteria).

**Validates: Requirements 3.3**

### Property 3: Adapter round-trip idempotence

*For any* valid set of raw EvalWeaver artifact JSON files, applying `adaptArtifacts(raw)` to get a TasteCompilerRun, serializing it to JSON, and then adapting the serialized form again should produce a TasteCompilerRun object that is deeply equal to the first adaptation result.

**Validates: Requirements 3.4**

### Property 4: Provider status classification correctness

*For any* RunMetadata object, `classifyProvider(meta)` should return exactly one of the four defined ProviderStatus values according to these rules: (a) if provider_name is "mock" or falsy → "Static / Mock", (b) if provider_name is "bedrock" and provider_generation_enabled is false → "Bedrock Metadata Only", (c) if provider_name is "bedrock" and provider_generation_enabled is true and generated_steps includes "research" and bedrock_calls_made >= 1 and bedrock_validation_passed is not false → "Bedrock Live Research", (d) otherwise → "Bedrock Generation Failed / Incomplete". The classification is total (always returns a value) and deterministic (same input always produces same output).

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 5: Honesty Card source accuracy

*For any* RunMetadata where `generated_steps` does not include a scorer/code generation step, the derived Honesty Card fields should report scorer generation source as "static". Similarly, if `generated_steps` does not include a pair generation step, pair generation source should be reported as "static". The Honesty Card should never claim Bedrock-generated content unless the corresponding step is explicitly listed.

**Validates: Requirements 6.5**

### Property 6: View mode panel visibility

*For any* valid TasteCompilerRun and for either view mode, the set of visible panels should satisfy: in Product Mode, raw JSON panels, scorer code fields, and artifact download buttons are absent from the rendered output; in Dev Mode, they are present. The toggle between modes should not alter the underlying data, only visibility.

**Validates: Requirements 8.2, 8.3**

### Property 7: Graceful degradation for null panel data

*For any* TasteCompilerRun where one or more data sections (taste_map, scorers, repair_summary, selected_candidate, pair_summary) are null, the corresponding panel should render its header with a "No data" or section-specific placeholder message and remain interactive (not crash or produce an error boundary).

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

### Property 8: Panel renders all required fields from its data

*For any* valid TasteCompilerRun with non-null data in a given section, the corresponding panel's rendered output should contain all required display fields: RunHeader shows run_id, goal, raw_text, and provider status label; TasteMapPanel shows all concept names from rewards, punishes, and preserves; ScorerParetoTable shows scorer_id, test_accuracy, test_margin, and pareto_member for each scorer; PairSuitePanel shows total_pairs and type_distribution keys; RepairPanel shows honest_repair_summary text and claim_supported boolean; CandidatePanel shows candidate_id, strategy, ensemble_score, and explanation.

**Validates: Requirements 5.1, 5.3, 5.4, 5.5, 5.6, 5.7, 5.9, 5.10**

## Error Handling

| Scenario | Handling |
|----------|----------|
| Missing fixture file in mock mode | Adapter returns null for that section; panel shows "Data unavailable" |
| Malformed JSON in fixture | Adapter catches parse error, returns null for that section, logs warning |
| API endpoint unreachable (API mode) | Data loader throws; page shows connection error UI with retry button |
| API returns non-200 status | Data loader throws; page shows error with status code |
| Unknown provider_name value | Treated as "mock" → "Static / Mock" status (safe fallback) |
| Missing `generated_steps` array | Defaults to empty array `[]` — all sources reported as "static" |
| Scorer with null test_accuracy | Displayed as "—" in table, sorted to bottom |
| Extremely large artifact JSON | Rendered in collapsible panels with virtualized JSON viewer in dev mode |

## Testing Strategy

### Dual Approach

Both unit tests and property-based tests are required for comprehensive coverage.

### Unit Tests (examples and edge cases)

- Landing page renders required text elements (4.1–4.8)
- Pipeline Timeline renders correct sequence text
- Agent Battery panel renders placeholder content
- API route `/api/runs` returns fixture run list
- API route `/api/runs/demo` returns valid artifact JSON
- Mode toggle defaults to Product Mode on load
- Demo page renders without backend (integration smoke test)
- No API keys present in client bundle (security check)
- Connection error UI shown when API unreachable

### Property-Based Tests

Library: **fast-check** (TypeScript property-based testing library for Node.js/browser)

Each property test should run a minimum of **100 iterations** with randomly generated inputs.

| Property | Test Strategy | Tag |
|----------|--------------|-----|
| 1: Structural completeness | Generate random valid RawArtifacts using arbitraries for each artifact shape. Assert output has all required fields. | `Feature: taste-compiler-frontend, Property 1: Adapter structural completeness` |
| 2: Graceful partial inputs | Generate RawArtifacts with random fields set to undefined/null. Assert adapter never throws. | `Feature: taste-compiler-frontend, Property 2: Adapter graceful handling of partial inputs` |
| 3: Round-trip idempotence | Generate valid RawArtifacts, adapt, serialize to JSON, adapt again, deep-equal compare. | `Feature: taste-compiler-frontend, Property 3: Adapter round-trip idempotence` |
| 4: Provider classification | Generate random RunMetadata (varying provider_name, flags, steps, calls). Assert output matches expected branch. | `Feature: taste-compiler-frontend, Property 4: Provider status classification correctness` |
| 5: Honesty Card source | Generate RunMetadata with random generated_steps arrays. Assert source labels are "static" when no generation step present. | `Feature: taste-compiler-frontend, Property 5: Honesty Card source accuracy` |
| 6: View mode visibility | Generate valid TasteCompilerRun + mode. Assert dev-only elements present/absent based on mode. | `Feature: taste-compiler-frontend, Property 6: View mode panel visibility` |
| 7: Graceful degradation | Generate TasteCompilerRun with random null sections. Assert no render errors and placeholders present. | `Feature: taste-compiler-frontend, Property 7: Graceful degradation for null panel data` |
| 8: Panel field presence | Generate valid TasteCompilerRun with non-null sections. Assert rendered output contains all required field values. | `Feature: taste-compiler-frontend, Property 8: Panel renders all required fields` |

### Test Configuration

```typescript
// Example fast-check configuration
import fc from "fast-check";

fc.assert(
  fc.property(arbitraryRunMetadata(), (meta) => {
    const status = classifyProvider(meta);
    // Assert exactly one of the four statuses is returned
    // Assert deterministic: classifyProvider(meta) === classifyProvider(meta)
  }),
  { numRuns: 100 }
);
```

### Priority

1. **Properties 3 & 4** (adapter round-trip and provider classification) are the highest-value property tests — they validate the core data transformation logic that all UI depends on.
2. **Properties 1 & 2** (structural completeness and graceful handling) catch regressions when artifact shapes evolve.
3. **Properties 5–8** (UI rendering properties) can use React Testing Library with fast-check arbitraries to verify component contracts.
