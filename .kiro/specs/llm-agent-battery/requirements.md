# Requirements Document

## Introduction

The LLM Agent Battery is a comprehensive code analysis tool that combines deterministic structural heuristics with LLM-powered semantic reasoning to debug and review any agent architecture. Unlike the current `agent_battery/` which only detects structural patterns (prompt files, tool schemas, traces) in repos that follow specific conventions, this system uses LLM reasoning to understand code intent, find logic bugs, detect design flaws, and produce actionable findings — regardless of the target codebase's folder structure or agent framework.

The system operates in two layers:
1. A fast deterministic layer that classifies files and detects structural patterns heuristically
2. An LLM reasoning layer that chunks code semantically, sends it to Bedrock/Sonnet with domain-aware context, and produces structured findings

## Glossary

- **Battery**: The complete analysis tool — both deterministic and LLM layers combined
- **Scanner**: The component that recursively discovers and collects source files from a target codebase
- **Classifier**: The component that assigns semantic categories (agent logic, tool definition, orchestration, state management, etc.) to discovered files using heuristics and optionally LLM assistance
- **Chunker**: The component that splits source files into reviewable units (functions, classes, modules) preserving semantic coherence
- **Analyzer**: An LLM-powered review pass that examines code chunks with a specific domain prompt and returns structured findings
- **Finding**: A discrete issue discovered by the Battery, containing severity, location, category, description, and impact
- **Review_Profile**: A configurable set of domain-specific system prompts and analysis focus areas tailored to a particular agent architecture style
- **Bedrock_Client**: The AWS Bedrock Runtime integration that handles LLM invocations via the Converse API
- **Report_Generator**: The component that aggregates findings and produces human-readable and machine-readable output

## Requirements

### Requirement 1: Architecture-Agnostic File Discovery

**User Story:** As a developer, I want the Battery to scan any codebase regardless of folder structure, so that I can analyze agent systems that don't follow conventional directory layouts.

#### Acceptance Criteria

1. WHEN a target directory path is provided, THE Scanner SHALL recursively discover all source files matching configurable include/exclude glob patterns
2. THE Scanner SHALL support Python, TypeScript, JavaScript, Go, Rust, and YAML/JSON file types by default
3. WHEN no include patterns are specified, THE Scanner SHALL use a sensible default set covering common source file extensions
4. THE Scanner SHALL exclude version control directories, dependency caches, and build artifacts by default
5. WHEN a file exceeds 500KB, THE Scanner SHALL skip the file and record a warning in the scan results

### Requirement 2: Semantic File Classification

**User Story:** As a developer, I want the Battery to intelligently classify files by their role in the agent system, so that analysis can be targeted appropriately regardless of naming conventions.

#### Acceptance Criteria

1. THE Classifier SHALL assign one primary category and zero or more secondary categories to each discovered file
2. THE Classifier SHALL support the following categories: AGENT_LOGIC, TOOL_DEFINITION, ORCHESTRATION, STATE_MANAGEMENT, PROMPT_TEMPLATE, CONFIGURATION, TEST, INFRASTRUCTURE, and UNKNOWN
3. WHEN a file's category cannot be determined by heuristics alone, THE Classifier SHALL optionally invoke the LLM to classify the file based on content analysis
4. THE Classifier SHALL use content-based heuristics (AST patterns, import analysis, decorator detection) before falling back to path-based heuristics
5. WHEN running in fast mode, THE Classifier SHALL use only deterministic heuristics without LLM calls

### Requirement 3: Semantic Code Chunking

**User Story:** As a developer, I want code to be split into meaningful reviewable units, so that LLM analysis has appropriate context to reason about correctness.

#### Acceptance Criteria

1. THE Chunker SHALL split Python source files into chunks at function and class boundaries using AST parsing
2. THE Chunker SHALL split TypeScript/JavaScript files into chunks at function, class, and exported declaration boundaries
3. WHEN a single function exceeds the configured maximum chunk size, THE Chunker SHALL include that function as a standalone chunk with truncation warning
4. THE Chunker SHALL preserve module-level context (imports, constants, type definitions) as a preamble attached to each chunk from that module
5. WHEN a class has methods that reference shared state, THE Chunker SHALL keep the class as a single chunk rather than splitting methods individually
6. THE Chunker SHALL produce chunks no larger than a configurable maximum character count (default: 12000 characters)

### Requirement 4: LLM-Powered Code Analysis

**User Story:** As a developer, I want the Battery to use LLM reasoning to find logic bugs, correctness issues, and design flaws that structural linting cannot detect.

#### Acceptance Criteria

1. WHEN a code chunk is submitted for analysis, THE Analyzer SHALL send the chunk to Bedrock with a domain-specific system prompt and file context
2. THE Analyzer SHALL return findings as structured JSON objects containing severity, category, location, title, description, and impact fields
3. THE Analyzer SHALL support configurable Review_Profiles that customize the system prompt for different agent architecture styles (multi-agent, pipeline, reactive, etc.)
4. IF the Bedrock API call fails with a retryable error, THEN THE Analyzer SHALL retry up to 3 times with exponential backoff
5. IF the Bedrock API call fails with a non-retryable error, THEN THE Analyzer SHALL record a review-incomplete finding and continue with the next chunk
6. THE Analyzer SHALL use temperature 0.2 or lower to maximize consistency of findings across runs
7. WHEN the LLM response is not valid JSON, THE Analyzer SHALL attempt to extract JSON from markdown code blocks before recording a parse error

### Requirement 5: Deterministic Heuristic Layer

**User Story:** As a developer, I want fast structural checks to run without LLM calls, so that I get immediate feedback on common issues without API latency or cost.

#### Acceptance Criteria

1. THE Battery SHALL run all deterministic heuristic checks before invoking the LLM layer
2. THE Battery SHALL detect missing error handling patterns in tool invocation code
3. THE Battery SHALL detect unguarded state mutations in agent orchestration logic
4. THE Battery SHALL detect missing confirmation gates before destructive operations
5. THE Battery SHALL detect prompt injection vulnerabilities in user-input handling paths
6. WHEN running in fast-only mode, THE Battery SHALL produce findings from heuristics alone without any LLM invocations

### Requirement 6: Multi-Architecture Review Profiles

**User Story:** As a developer, I want the Battery to understand different agent architectures, so that it can provide relevant findings for multi-agent systems, single-agent pipelines, and reactive architectures.

#### Acceptance Criteria

1. THE Battery SHALL ship with built-in Review_Profiles for: single-agent, multi-agent-orchestrated, pipeline-sequential, and reactive-event-driven architectures
2. WHEN no Review_Profile is specified, THE Battery SHALL auto-detect the architecture style from the codebase and select the most appropriate profile
3. THE Review_Profile SHALL define: a system prompt template, focus areas (list of concern categories to prioritize), and architecture-specific anti-patterns to check
4. WHEN a custom Review_Profile YAML file is provided, THE Battery SHALL load and use it instead of built-in profiles

### Requirement 7: Structured Finding Output

**User Story:** As a developer, I want findings in a consistent structured format with severity, location, and remediation guidance, so that I can prioritize and act on them.

#### Acceptance Criteria

1. THE Finding SHALL contain: severity (critical, high, medium, low), category, file path, function/class location, title, description, impact, and suggested remediation
2. THE Report_Generator SHALL produce a JSON file containing all findings sorted by severity
3. THE Report_Generator SHALL produce a human-readable Markdown report with severity badges, grouped by file
4. THE Report_Generator SHALL deduplicate findings that have the same title and location across different analysis passes
5. WHEN findings exceed 200 items, THE Report_Generator SHALL include a summary section with counts by severity and category

### Requirement 8: CLI Interface

**User Story:** As a developer, I want a simple CLI to run the Battery against any target directory, so that I can integrate it into my workflow and CI/CD pipelines.

#### Acceptance Criteria

1. THE Battery SHALL expose a `review` command that accepts a target directory path and runs the full analysis pipeline
2. THE Battery SHALL expose a `scan` command that performs only file discovery and classification without LLM analysis
3. THE Battery SHALL accept `--profile` option to select or provide a Review_Profile
4. THE Battery SHALL accept `--fast` flag to skip LLM analysis and run only deterministic heuristics
5. THE Battery SHALL accept `--threshold` option to set the minimum severity for a non-zero exit code (default: HIGH)
6. THE Battery SHALL accept `--output-dir` option to specify where reports are written (default: `.agentbattery/` in target)
7. WHEN the `--ci` flag is provided, THE Battery SHALL suppress progress output and return only the exit code and machine-readable JSON
8. THE Battery SHALL return exit code 0 when no findings meet or exceed the threshold, and exit code 1 otherwise

### Requirement 9: Bedrock Integration

**User Story:** As a developer, I want the Battery to use AWS Bedrock for LLM calls, so that I can leverage existing cloud credentials and models without additional API key management.

#### Acceptance Criteria

1. THE Bedrock_Client SHALL use the AWS Bedrock Runtime Converse API for all LLM invocations
2. THE Bedrock_Client SHALL support configurable model ID (default: Claude Sonnet latest)
3. THE Bedrock_Client SHALL support AWS credential resolution via environment variables, profiles, or IAM roles
4. THE Bedrock_Client SHALL configure connection timeout of 30 seconds and read timeout of 300 seconds
5. IF AWS credentials are not configured or invalid, THEN THE Bedrock_Client SHALL raise a descriptive error with setup instructions before any analysis begins

### Requirement 10: Concurrency and Rate Limiting

**User Story:** As a developer, I want the Battery to review code efficiently without hitting API throttling limits, so that large codebases can be analyzed in reasonable time.

#### Acceptance Criteria

1. THE Battery SHALL process code chunks with configurable concurrency (default: 3 concurrent LLM calls)
2. THE Battery SHALL enforce a minimum delay between consecutive API calls to the same model (default: 1 second)
3. WHEN a throttling response (429 or equivalent) is received, THE Battery SHALL pause all inflight requests and retry with exponential backoff
4. THE Battery SHALL display progress indication showing chunks completed out of total during LLM analysis
5. WHILE processing chunks, THE Battery SHALL track and report total token usage and estimated cost

### Requirement 11: Finding Deduplication and Ranking

**User Story:** As a developer, I want findings to be deduplicated and ranked intelligently, so that I see unique actionable issues rather than noise from overlapping analysis.

#### Acceptance Criteria

1. THE Battery SHALL deduplicate findings that share the same title and file location
2. THE Battery SHALL merge findings from the heuristic layer and LLM layer into a single ranked list
3. WHEN the same issue is found by both layers, THE Battery SHALL keep the more detailed finding (typically from the LLM layer) and annotate it as confirmed by heuristics
4. THE Battery SHALL rank findings by: severity first, then by category (logic_error > correctness > edge_case > design_flaw > other)

### Requirement 12: Extensible Analyzer Registry

**User Story:** As a developer, I want to add custom analysis passes, so that I can extend the Battery with domain-specific checks for my particular agent system.

#### Acceptance Criteria

1. THE Battery SHALL support registering custom Analyzer implementations via a plugin interface
2. WHEN a custom Analyzer is registered, THE Battery SHALL include its findings in the unified output alongside built-in analyzers
3. THE Battery SHALL provide a base Analyzer class that handles Bedrock invocation, JSON parsing, and error handling so custom analyzers only need to define their system prompt and focus areas
