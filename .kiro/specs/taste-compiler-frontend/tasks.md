# Implementation Plan: Taste Compiler Frontend

## Overview

Incremental build of the Next.js App Router frontend at `apps/web/`. Each task builds on previous steps, starting with project skeleton and types, then data layer (adapter, fixtures, loader), then UI components, then API routes, and finally property-based tests and build verification.

## Tasks

- [x] 1. Project skeleton and dark theme
  - [x] 1.1 Initialize Next.js App Router project with TypeScript at `apps/web/`
    - Run `npx create-next-app@latest` with App Router and TypeScript flags (or scaffold manually)
    - Configure `tsconfig.json` with strict mode
    - Ensure `npm run dev` starts without errors
    - _Requirements: 1.1, 1.3_

  - [x] 1.2 Create root layout with dark theme styling
    - Create `apps/web/app/layout.tsx` with dark background, monospace fonts
    - Create `apps/web/styles/globals.css` with dark theme variables, green/amber/red badge classes
    - Apply shared layout to all pages
    - _Requirements: 1.2, 1.4_

- [x] 2. Type definitions
  - [x] 2.1 Define TasteCompilerRun and all related TypeScript types
    - Create `apps/web/lib/types.ts` with interfaces: TasteCompilerRun, RunMetadata, TasteMap, TasteConcept, SpecCriterion, ScorerEntry, PairSummary, RepairSummary, SelectedCandidate, ProviderStatus, ViewMode, DataMode
    - Follow exact type shapes from the design document
    - _Requirements: 3.1, 3.2_

- [x] 3. Sample artifact fixtures
  - [x] 3.1 Create fixture directory and populate sample run JSON files
    - Create `apps/web/fixtures/sample_run/` with: run_summary.json, taste_map.json, scorer_functions_r0.json, scorer_functions_r1.json, pairs_r0.json, pareto_r0.json, pareto_r1.json, failure_packet_r0.json, repair_metrics.json, final_selection.json, computed_criteria.json, trace.json
    - Derive content from existing `experiments/batch/` EvalWeaver outputs
    - Ensure run_summary includes Bedrock live research metadata: provider_name="bedrock", model_id="us.anthropic.claude-sonnet-4-6", provider_generation_enabled=true, bedrock_calls_made=1, generated_steps=["research"], bedrock_validation_passed=true
    - _Requirements: 2.1, 2.2, 2.4_

- [x] 4. Artifact adapter
  - [x] 4.1 Implement `adaptArtifacts` function in `apps/web/lib/artifactAdapter.ts`
    - Accept a RawArtifacts object (individual artifact JSON files)
    - Map run_summary → run_id, goal, raw_text, run_metadata
    - Map taste_map → TasteMap or null
    - Merge scorer_functions + pareto data → ScorerEntry[]
    - Aggregate pairs → PairSummary
    - Map repair_metrics → RepairSummary
    - Map final_selection → SelectedCandidate
    - Map computed_criteria → SpecCriterion[]
    - Store all raw inputs in raw_artifacts
    - Never throw: use null/safe defaults for missing data
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

  - [ ]* 4.2 Write property test: Adapter structural completeness (Property 1)
    - **Property 1: Adapter structural completeness**
    - Generate random valid RawArtifacts using fast-check arbitraries
    - Assert output has non-empty run_id, non-empty goal, string raw_text, all 9 RunMetadata fields, and raw_artifacts containing all inputs
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 4.3 Write property test: Adapter graceful handling of partial inputs (Property 2)
    - **Property 2: Adapter graceful handling of partial inputs**
    - Generate RawArtifacts with random fields set to undefined/null
    - Assert adapter never throws; missing sections are null or empty arrays
    - **Validates: Requirements 3.3**

  - [ ]* 4.4 Write property test: Adapter round-trip idempotence (Property 3)
    - **Property 3: Adapter round-trip idempotence**
    - Generate valid RawArtifacts, adapt, serialize to JSON, adapt again, deep-equal compare
    - **Validates: Requirements 3.4**

- [x] 5. Provider status classification
  - [x] 5.1 Implement `classifyProvider` function in `apps/web/lib/providerStatus.ts`
    - Accept RunMetadata, return exactly one ProviderStatus
    - Implement four classification branches per design (mock → Bedrock Metadata Only → Bedrock Live Research → Bedrock Failed/Incomplete)
    - Pure function, deterministic, total
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 5.2 Write property test: Provider status classification correctness (Property 4)
    - **Property 4: Provider status classification correctness**
    - Generate random RunMetadata (varying provider_name, flags, steps, calls)
    - Assert output matches expected branch for each input combination
    - Assert deterministic: same input → same output
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

  - [ ]* 5.3 Write property test: Honesty Card source accuracy (Property 5)
    - **Property 5: Honesty Card source accuracy**
    - Generate RunMetadata with random generated_steps arrays
    - Assert scorer source is "static" when no scorer generation step present
    - Assert pair source is "static" when no pair generation step present
    - **Validates: Requirements 6.5**

- [x] 6. Data loader
  - [x] 6.1 Implement mode-aware data loader in `apps/web/lib/dataLoader.ts`
    - Read `TASTE_COMPILER_DATA_MODE` server-side env var (NOT NEXT_PUBLIC_)
    - In mock mode: read fixture files via `fs` in Server Components
    - In api mode: server-side fetch to `TASTE_COMPILER_API_URL`
    - Call `adaptArtifacts` on raw data before returning
    - Default to "mock" when env var not set
    - _Requirements: 7.1, 7.2, 7.6_

- [x] 7. Checkpoint - Ensure data layer works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Landing page
  - [x] 8.1 Implement landing page at `apps/web/app/page.tsx`
    - Display "Taste Compiler" product name
    - Display "Agents that learn what 'good' means" tagline
    - Render goal description input text box
    - Render goal variable selector
    - Render provider selector display
    - Render "View demo run" button linking to `/runs/demo`
    - Render disabled "Start run" button
    - Serve at `/` route
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

- [ ] 9. Run page with all panels
  - [x] 9.1 Create run page Server Component at `apps/web/app/runs/[runId]/page.tsx`
    - Use `loadRun(runId)` from dataLoader to fetch TasteCompilerRun
    - Pass data to child panel components
    - Handle loading/error states (connection error UI for API mode)
    - _Requirements: 7.5_

  - [x] 9.2 Implement PanelShell wrapper component
    - Create `apps/web/components/PanelShell.tsx`
    - Accept title, children, and data presence flag
    - Render panel header with "No data" fallback when data is absent
    - _Requirements: 9.5_

  - [x] 9.3 Implement RunHeader component
    - Create `apps/web/components/RunHeader.tsx`
    - Display run_id, goal, raw_text, and ProviderStatus badge (using classifyProvider)
    - _Requirements: 5.1_

  - [x] 9.4 Implement HonestyCard component (first-screen required)
    - Create `apps/web/components/HonestyCard.tsx`
    - Display: Provider status, Model ID, Generated steps, Bedrock calls made, "Evaluator: deterministic", Scorer generation source, Pair generation source
    - Must be visible at top of run page (first-screen)
    - Logic: show "static" for sources unless metadata explicitly includes that generation step
    - _Requirements: 5.10, 6.5_

  - [x] 9.5 Implement PipelineTimeline component
    - Create `apps/web/components/PipelineTimeline.tsx`
    - Static visual sequence: "Research → Taste Map → Scorer Evolution → Pair Tests → Repair → Rewrite"
    - _Requirements: 5.2, 11.2_

  - [x] 9.6 Implement TasteMapPanel component
    - Create `apps/web/components/TasteMapPanel.tsx`
    - Display rewards, punishes, preserves concepts with names and descriptions
    - Show "Data unavailable" when taste_map is null
    - _Requirements: 5.3, 9.1_

  - [x] 9.7 Implement ScorerParetoTable component
    - Create `apps/web/components/ScorerParetoTable.tsx`
    - Table showing scorer_id, test_accuracy, test_margin, pareto_member
    - Show empty state when scorers array is empty or null
    - _Requirements: 5.4, 9.2_

  - [x] 9.8 Implement PairSuitePanel component
    - Create `apps/web/components/PairSuitePanel.tsx`
    - Show total pair count, type distribution, train/test split
    - Show placeholder when pair_summary is null
    - _Requirements: 5.5, 9.5_

  - [x] 9.9 Implement RepairPanel component
    - Create `apps/web/components/RepairPanel.tsx`
    - Display honest_repair_summary text and "Repair claim supported: true/false"
    - Show "Repair data not available" when repair_summary is null
    - _Requirements: 5.6, 9.3_

  - [x] 9.10 Implement CandidatePanel component
    - Create `apps/web/components/CandidatePanel.tsx`
    - Display candidate_id, strategy, ensemble_score, explanation
    - Show "No candidate selected" when selected_candidate is null
    - _Requirements: 5.7, 9.4_

  - [x] 9.11 Implement AgentBatteryPanel placeholder
    - Create `apps/web/components/AgentBatteryPanel.tsx`
    - Render placeholder text for future agent evaluation metrics
    - _Requirements: 5.8_

  - [x] 9.12 Implement ArtifactDebugPanel component (dev mode only)
    - Create `apps/web/components/ArtifactDebugPanel.tsx`
    - Render collapsible raw JSON for each artifact
    - Only visible in dev mode
    - _Requirements: 5.9, 8.3_

- [x] 10. Product/Dev mode toggle
  - [x] 10.1 Implement ViewModeProvider and ModeToggle
    - Create `apps/web/providers/ViewModeProvider.tsx` (React context, defaults to "product")
    - Create `apps/web/components/ModeToggle.tsx` (client component, toggles without page reload)
    - Wire into layout so all panels can read current mode
    - In Product Mode: hide ArtifactDebugPanel, scorer code, download buttons
    - In Dev Mode: show all panels and raw data
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 10.2 Write property test: View mode panel visibility (Property 6)
    - **Property 6: View mode panel visibility**
    - Generate valid TasteCompilerRun + mode (product/dev)
    - Assert dev-only elements present only in dev mode, absent in product mode
    - **Validates: Requirements 8.2, 8.3**

- [x] 11. Checkpoint - Ensure UI renders correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. API routes
  - [x] 12.1 Implement API route `GET /api/runs`
    - Create `apps/web/app/api/runs/route.ts`
    - Return list of available runs (fixture-based for now)
    - Do NOT trigger pipeline execution
    - _Requirements: 7.3, 7.7_

  - [x] 12.2 Implement API route `GET /api/runs/[runId]`
    - Create `apps/web/app/api/runs/[runId]/route.ts`
    - Return full artifact JSON for given runId
    - In MVP: return fixture data only
    - Do NOT trigger pipeline execution
    - _Requirements: 7.4, 7.7_

- [ ] 13. Property-based tests
  - [ ]* 13.1 Set up fast-check testing infrastructure
    - Install fast-check as dev dependency
    - Create test directory `apps/web/__tests__/properties/`
    - Configure test runner (Jest or Vitest) for property tests
    - _Requirements: N/A (testing infrastructure)_

  - [ ]* 13.2 Write property test: Graceful degradation for null panel data (Property 7)
    - **Property 7: Graceful degradation for null panel data**
    - Generate TasteCompilerRun with random null sections
    - Render panels using React Testing Library
    - Assert no render errors and placeholder messages present
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

  - [ ]* 13.3 Write property test: Panel renders all required fields (Property 8)
    - **Property 8: Panel renders all required fields from its data**
    - Generate valid TasteCompilerRun with non-null sections
    - Render panels using React Testing Library
    - Assert all required field values appear in rendered output
    - **Validates: Requirements 5.1, 5.3, 5.4, 5.5, 5.6, 5.7, 5.9, 5.10**

- [x] 14. Build acceptance verification
  - [x] 14.1 Verify build passes and no secrets in client bundle
    - Run `npm run build` in `apps/web/` — must complete without errors
    - Verify no API keys in client-side JavaScript output
    - Verify no direct calls to Anthropic/Bedrock/Exa APIs from browser code
    - Verify `/` renders landing page
    - Verify `/runs/demo` renders full run page from fixtures with no backend
    - Verify HonestyCard is visible on first screen of `/runs/demo`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 11.1, 11.4_

- [x] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use fast-check with minimum 100 iterations
- The implementation language is TypeScript throughout
- No Exa integration in MVP
- `TASTE_COMPILER_DATA_MODE` is server-side only (not NEXT_PUBLIC_)
- API routes return fixture data only — no backend pipeline execution
- HonestyCard must be first-screen visible on the run page
