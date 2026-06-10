# Requirements Document

## Introduction

Taste Compiler Frontend is a Next.js (App Router) web application that surfaces EvalWeaver backend artifacts as a judge-visible product loop. The MVP is an artifact viewer and demo runner shell — it does not reimplement the EvalWeaver Python pipeline in the browser or make direct LLM API calls. It supports two data modes: mock artifacts (checked-in JSON fixtures) and a local API mode (wirable to a backend returning artifact JSON).

## Glossary

- **Frontend**: The Next.js App Router application deployed at `apps/web/`
- **Artifact**: A JSON file produced by the EvalWeaver pipeline (e.g., run_summary_v5.json, taste_map, scorer functions, pairs, failure_packet, repair_metrics, final_selection)
- **TasteCompilerRun**: The normalized TypeScript type the Frontend consumes, adapted from raw EvalWeaver artifacts
- **Adapter**: The module (`artifactAdapter.ts`) that converts raw EvalWeaver artifact JSON into a TasteCompilerRun object
- **Mock_Artifact_Mode**: Data mode where the Frontend reads checked-in sample artifacts from `apps/web/fixtures/sample_run/` with no backend required
- **Local_API_Mode**: Data mode where the Frontend calls a backend endpoint that returns EvalWeaver artifact JSON
- **Product_Mode**: UI display mode that hides raw internals and shows only judge-relevant summaries
- **Dev_Mode**: UI display mode that exposes raw JSON, scorer code details, artifact download buttons, and debug panels
- **Run**: A single execution of the EvalWeaver pipeline, identified by a run_id
- **Taste_Map**: A structured representation of rewards, punishes, and preserves concepts for a goal
- **Pareto_Frontier**: The set of non-dominated scorers by accuracy and margin
- **Pair_Suite**: The collection of evaluation pairs (positive/negative rewrites) used to validate scorers
- **Repair_Summary**: Metrics comparing pre-repair and post-repair scorer performance, including an honesty claim
- **Provider_Status**: A classification label derived from run metadata indicating whether a run is static/mock, Bedrock metadata-only, or Bedrock live research
- **Agent_Battery**: A placeholder section for future agent evaluation metrics

## Requirements

### Requirement 1: Project Skeleton and Dark Theme

**User Story:** As a developer, I want a Next.js App Router project with TypeScript and a dark terminal-like theme, so that I can build UI components on a consistent foundation.

#### Acceptance Criteria

1. THE Frontend SHALL use Next.js App Router with TypeScript located at `apps/web/`
2. THE Frontend SHALL apply a dark background with monospace labels and green/amber/red status badges as the default visual theme
3. WHEN `npm run dev` is executed in `apps/web/`, THE Frontend SHALL start a development server without errors
4. THE Frontend SHALL provide a shared layout component that applies dark theme styling to all pages

### Requirement 2: Sample Artifact Fixtures

**User Story:** As a developer, I want checked-in sample artifacts at `apps/web/fixtures/sample_run/`, so that I can render demo pages without a running backend.

#### Acceptance Criteria

1. THE Frontend SHALL include sample artifact fixture files at `apps/web/fixtures/sample_run/` containing at minimum: run_summary, taste_map, scorer_functions, pairs, failure_packet, repair_metrics, and final_selection JSON
2. THE Frontend SHALL derive fixture content from existing EvalWeaver batch experiment outputs
3. WHEN fixture files are present, THE Frontend SHALL be able to render the demo run page using only those fixtures with no network requests
4. THE Frontend SHALL include at least one sample fixture representing a successful Bedrock live research run with generated_steps=["research"] and bedrock_calls_made>=1, so that demo screenshots can show the "Bedrock Live Research" provider status

### Requirement 3: Artifact Adapter

**User Story:** As a developer, I want an adapter that converts raw EvalWeaver artifact JSON into a normalized TasteCompilerRun type, so that UI components consume a stable contract regardless of backend artifact naming.

#### Acceptance Criteria

1. THE Adapter SHALL convert raw EvalWeaver artifact JSON into a TasteCompilerRun object containing: run_id, goal, raw_text, run_metadata, taste_map, spec_criteria, scorers, pair_summary, repair_summary, selected_candidate, agent_battery, and raw_artifacts
2. THE Adapter SHALL map run_metadata to include: provider_name, model_id, aws_region, provider_generation_enabled, bedrock_validation_passed, bedrock_calls_made, generated_steps, artifact_store, and execution_backend
3. IF a raw artifact field is missing or null, THEN THE Adapter SHALL substitute a safe default value and mark the field as unavailable rather than throwing an error
4. FOR ALL valid EvalWeaver artifact JSON inputs, adapting then serializing then adapting again SHALL produce an equivalent TasteCompilerRun object (round-trip property)
5. THE Adapter SHALL be located at `apps/web/lib/artifactAdapter.ts`
6. THE Adapter SHALL export a function that accepts individual artifact JSON files and merges them into a single TasteCompilerRun

### Requirement 4: Landing Page

**User Story:** As a judge or demo viewer, I want a landing page that introduces Taste Compiler and allows navigation to a demo run, so that I can quickly understand the product and see it in action.

#### Acceptance Criteria

1. THE Frontend SHALL display the product name "Taste Compiler" on the landing page
2. THE Frontend SHALL display the tagline "Agents that learn what 'good' means" on the landing page
3. THE Frontend SHALL display an input text box for goal description on the landing page
4. THE Frontend SHALL display a goal variable selector on the landing page
5. THE Frontend SHALL display a provider selector display on the landing page
6. THE Frontend SHALL display a "View demo run" button that navigates to `/runs/demo`
7. THE Frontend SHALL display a "Start run" button in a disabled state on the landing page
8. THE Frontend SHALL serve the landing page at the `/` route

### Requirement 5: Run Page - Core Panels

**User Story:** As a judge, I want to view a complete run with all relevant panels, so that I can evaluate the quality and honesty of an EvalWeaver pipeline execution.

#### Acceptance Criteria

1. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render a Run Header showing run_id, goal, raw_text, and Provider_Status
2. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render a Pipeline Timeline showing the sequence: "Research → Taste Map → Scorer Evolution → Pair Tests → Repair → Rewrite"
3. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render a Taste Map Panel displaying rewards, punishes, and preserves concepts with their descriptions
4. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render a Scorer Pareto Table showing scorer IDs, test accuracy, test margin, and Pareto membership
5. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render a Pair Suite Panel showing pair count, type distribution, and train/test split summary
6. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render a Repair Panel displaying the honest_repair_summary text and the overall_improvement_claim_supported status as "Repair claim supported: true/false" exactly as the artifact reports
7. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render a Candidate Panel showing the selected candidate ID, strategy, ensemble score, and explanation
8. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render an Agent Battery Panel as a placeholder for future agent evaluation metrics
9. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render an Artifact Debug Panel showing raw JSON artifacts with collapsible sections
10. WHEN a user navigates to `/runs/[runId]`, THE Frontend SHALL render an Honesty Card near the top of the page showing: Provider status, Generation steps, Bedrock calls made, Evaluator type ("deterministic"), Scorer generation source ("static" unless generated_steps indicates otherwise), and Pair generation source ("static" unless generated_steps indicates otherwise)

### Requirement 6: Provider Status Classification

**User Story:** As a judge, I want to see clearly whether a run used real Bedrock generation or mock data, so that I can assess the credibility of the results.

#### Acceptance Criteria

1. WHEN run_metadata.provider_name is "mock" or missing, THE Frontend SHALL display Provider_Status as "Static / Mock" with a red/gray badge
2. WHEN run_metadata.provider_name is "bedrock" AND run_metadata.provider_generation_enabled is false, THE Frontend SHALL display Provider_Status as "Bedrock Metadata Only" with an amber badge and the explanation "Bedrock credentials/model selected, but no live generation steps were executed."
3. WHEN run_metadata.provider_name is "bedrock" AND run_metadata.provider_generation_enabled is true AND run_metadata.generated_steps includes "research" AND run_metadata.bedrock_calls_made >= 1 AND run_metadata.bedrock_validation_passed is not false, THE Frontend SHALL display Provider_Status as "Bedrock Live Research" with a green badge
4. WHEN run_metadata.provider_name is "bedrock" AND run_metadata.provider_generation_enabled is true AND (run_metadata.bedrock_validation_passed is false OR run_metadata.bedrock_calls_made === 0), THE Frontend SHALL display Provider_Status as "Bedrock Generation Failed / Incomplete" with a red/amber badge
5. THE Frontend SHALL NOT claim Bedrock-generated scorers unless run_metadata.generated_steps explicitly includes a scorer/scorer_code generation step

### Requirement 7: Data Modes

**User Story:** As a developer, I want the frontend to support mock_artifact and local_api data modes, so that I can demo without a backend and also wire to a real API later.

#### Acceptance Criteria

1. WHILE in Mock_Artifact_Mode, THE Frontend SHALL read artifact data exclusively from `apps/web/fixtures/sample_run/` with no network requests to external services
2. WHILE in Local_API_Mode, THE Frontend SHALL fetch artifact data from `/api/runs/[runId]` endpoint
3. THE Frontend SHALL provide an API route at `/api/runs` that lists available runs
4. THE Frontend SHALL provide an API route at `/api/runs/[runId]` that returns the full artifact JSON for a given run
5. WHEN Local_API_Mode is configured but the backend is unavailable, THE Frontend SHALL display a connection error message rather than crashing
6. THE Frontend SHALL determine data mode from an environment variable or configuration setting
7. THE API routes SHALL initially return fixture data only and SHALL NOT trigger EvalWeaver pipeline execution; backend runner integration is a later milestone

### Requirement 8: Product Mode vs Dev Mode

**User Story:** As a user, I want to toggle between Product Mode and Dev Mode, so that judges see a clean summary while developers can inspect raw internals.

#### Acceptance Criteria

1. THE Frontend SHALL provide a toggle control to switch between Product_Mode and Dev_Mode
2. WHILE in Product_Mode, THE Frontend SHALL hide raw JSON panels, scorer code details, and artifact download buttons
3. WHILE in Dev_Mode, THE Frontend SHALL display raw JSON panels, scorer code details, and artifact download buttons
4. WHEN the mode toggle is activated, THE Frontend SHALL update the visible panels without a full page reload
5. THE Frontend SHALL default to Product_Mode on initial page load

### Requirement 9: Graceful Degradation

**User Story:** As a user, I want the UI to degrade gracefully when artifact fields are missing, so that partial data still renders useful information.

#### Acceptance Criteria

1. IF a taste_map field is missing from the artifact, THEN THE Frontend SHALL display a "Data unavailable" placeholder in the Taste Map Panel rather than crashing
2. IF scorer data is missing from the artifact, THEN THE Frontend SHALL display an empty state message in the Scorer Pareto Table
3. IF repair_summary is missing from the artifact, THEN THE Frontend SHALL display "Repair data not available" in the Repair Panel
4. IF selected_candidate is missing from the artifact, THEN THE Frontend SHALL display "No candidate selected" in the Candidate Panel
5. IF any panel's data source is entirely absent, THEN THE Frontend SHALL render the panel header with a "No data" indicator and remain interactive

### Requirement 10: Security - No Browser-Side API Keys

**User Story:** As a security-conscious developer, I want to ensure no API keys are exposed in the browser, so that credentials remain server-side only.

#### Acceptance Criteria

1. THE Frontend SHALL NOT include any Anthropic, Bedrock, or third-party API keys in client-side JavaScript bundles
2. THE Frontend SHALL NOT make direct calls to Anthropic or AWS Bedrock APIs from browser code
3. IF an API key is required for Local_API_Mode backend communication, THEN THE Frontend SHALL store it exclusively in server-side environment variables accessed only by API route handlers
4. THE Frontend SHALL NOT embed API keys in HTML, inline scripts, or client-accessible configuration files

### Requirement 11: Demo Screenshot Readiness

**User Story:** As a product manager, I want the demo page to be screenshot-ready with storytelling flow, so that I can capture compelling product images without running backend services.

#### Acceptance Criteria

1. WHEN `/runs/demo` is loaded in Mock_Artifact_Mode, THE Frontend SHALL render a complete, visually polished run page suitable for screenshots
2. THE Frontend SHALL display the pipeline narrative "Research → Taste Map → Scorer Evolution → Pair Tests → Repair → Rewrite" as a visual timeline
3. THE Frontend SHALL highlight key features (taste map concepts, Pareto scorers, selected candidate) with visual emphasis suitable for a 10-second storytelling scan
4. THE Frontend SHALL render without requiring any running backend services when using Mock_Artifact_Mode
