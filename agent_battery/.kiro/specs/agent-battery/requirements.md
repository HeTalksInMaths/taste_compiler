# Requirements Document

## Introduction

`agentbattery` is a Python CLI package that audits AI agent repositories for missing evals, missing fail-safes, prompt/tool/spec mismatches, and unsafe tool-call trajectories. It scans a target repo, discovers agent artifacts, extracts obligations, classifies risk, detects architecture mismatches, generates missing test cases, checks traces against a compiled contract, and emits machine-readable and human-readable reports. The tool is deterministic (no LLM dependency), CI-friendly, and usable by both human developers and coding agents.

## Glossary

- **Scanner**: The module responsible for walking the target repository file tree, applying include/exclude globs, and producing a list of discovered files.
- **File_Classifier**: The module that categorizes discovered files into source categories using heuristic rules based on path patterns, file content, and naming conventions.
- **Prompt_Extractor**: The module that parses prompt files (Markdown, YAML, Python docstrings) and extracts structured PromptArtifact objects.
- **Tool_Extractor**: The module that uses Python AST parsing and JSON/YAML schema detection to extract ToolArtifact objects from tool source files and schema files.
- **Obligation_Extractor**: The module that applies a deterministic regex/pattern registry to prompt text and tool metadata to extract Obligation objects.
- **Risk_Classifier**: The module that classifies tools by side-effect risk level (DESTRUCTIVE, EXTERNAL_WRITE, WEAK, NONE) using keyword matching on tool names and descriptions.
- **Contract_Compiler**: The module that links obligations to tools via lexical matching and assembles the AgentContract intermediate representation.
- **Mismatch_Detector**: The module that runs architecture checks (A through G) against the AgentContract to identify structural issues.
- **Coverage_Analyzer**: The module that performs keyword matching over existing test/eval files against obligations and marks coverage status.
- **Trace_Loader**: The module that reads JSONL and JSON trace files and normalizes them into AgentTrace objects.
- **Trace_Checker**: The module that validates loaded traces against the AgentContract, running six defined checks.
- **Test_Generator**: The module that produces test cases from findings, outputting YAML test definitions.
- **Exporter**: Modules that serialize generated tests into YAML, pytest, or promptfoo formats.
- **Report_Generator**: The module that compiles all findings, coverage data, and generated tests into Markdown and JSON reports.
- **AgentContract**: The intermediate representation linking prompts, tools, obligations, forbidden transitions, and risk classifications for a scanned repository.
- **Finding**: A detected issue with a type, severity, gap_type, evidence, and optional remediation suggestion.
- **Gap Type**: The classification of a finding into one of four categories: POLICY_GAP (no obligation exists for a dangerous tool), ENFORCEMENT_GAP (obligation exists but no runtime enforcement detected), COVERAGE_GAP (obligation exists but no test covers it), TRACE_VIOLATION (actual trace violates the obligation).
- **Obligation**: A requirement extracted from prompt text or tool metadata that the agent must satisfy (e.g., confirmation_required, lookup_required).
- **SideEffectLevel**: An enumeration classifying tool risk: DESTRUCTIVE, EXTERNAL_WRITE, WEAK, NONE.
- **FileCategory**: An enumeration of source categories: PROMPT, TOOL_SOURCE, TOOL_SCHEMA, POLICY, EVAL, TRACE, CONFIG, DOC, UNKNOWN.
- **TraceStep**: A single step in an agent execution trace, with type (TOOL_CALL, TOOL_RESULT, AGENT_MESSAGE, USER_MESSAGE), tool name, arguments, and result.
- **CLI**: The command-line interface built with Typer, exposing scan, compile-contract, audit, check-trace, generate-tests, and report commands.
- **Target_Repo**: The AI agent repository being audited by agentbattery.
- **Rubric_Auditor**: The module that audits the target repo against the six hackathon agent architecture dimensions (Agent Overview, Autonomy & Decision-Making, Actions & Tool Use, Orchestration, Human-in-the-Loop, Failure Handling) and emits architecture gap findings.
- **AgentProfile**: A model describing a discovered agent's identity, purpose, and capabilities.
- **DecisionPolicy**: A model describing how the agent decides what to do next (goal decomposition, stop conditions, tool selection logic).
- **HumanInLoopPolicy**: A model describing where and how human approval, review, or override is required.
- **FailurePolicy**: A model describing how the agent handles tool errors, partial completion, timeouts, retries, and recovery.
- **OrchestrationPolicy**: A model describing how multiple agents coordinate (delegation, shared state, communication patterns).
- **AgentNode**: A model representing a single agent in a multi-agent system, with its role, tools, and delegation boundaries.

## Non-Negotiable MVP Invariants

The following invariants apply across all requirements and take precedence over any individual acceptance criterion:

1. **Prompt-only safety detection**: The core product must identify cases where the prompt promises a safety property but no runtime/tool/schema/test enforcement is detected. This is the primary value proposition.
2. **Policy gap as a finding**: A dangerous tool (DESTRUCTIVE or EXTERNAL_WRITE) with no detected prompt/policy obligation is itself a finding. The absence of an obligation must not suppress the finding — it elevates it.
3. **Four gap types**: Every finding SHALL be classified into exactly one gap type:
   - **Policy gap**: No prompt/policy obligation exists for a dangerous tool.
   - **Enforcement gap**: Obligation exists but no runtime/tool precondition is detected.
   - **Coverage gap**: Obligation exists but no test/eval covers it.
   - **Trace violation**: Actual trace violates the obligation or safety expectation.
4. **Deterministic priority-based classification**: File classification must be deterministic with a defined priority order. A file receives exactly one primary category. Secondary categories may be recorded but must not affect primary assignment.
5. **Uncertainty wording**: All findings must emit evidence and use uncertainty wording (e.g., "no precondition detected", "no confirmation step found") rather than claiming absolute absence, unless the evidence is definitive.
6. **Email_agent acceptance gate**: The MVP is not complete unless auditing the email_agent fixture finds unconfirmed send_email as a CRITICAL or HIGH issue and generates a regression test for it. This is the primary acceptance test.

## Requirements

### Requirement 1: Repository Scanning

**User Story:** As a developer, I want to scan an agent repository to discover all relevant files, so that the auditing pipeline has a complete inventory of artifacts to analyze.

#### Acceptance Criteria

1. WHEN a directory path is provided, THE Scanner SHALL recursively walk the file tree and return a list of DiscoveredFile objects for all files matching the default include patterns (*.py, *.md, *.yaml, *.yml, *.json, *.jsonl, *.toml).
2. WHEN include globs are specified, THE Scanner SHALL restrict discovered files to those matching the provided patterns.
3. WHEN exclude globs are specified, THE Scanner SHALL omit files matching those patterns from results.
4. THE Scanner SHALL apply default excludes for common non-relevant directories (.git, __pycache__, node_modules, .venv, .env, dist, build, *.egg-info).
5. IF the provided directory path does not exist, THEN THE Scanner SHALL raise a descriptive error indicating the path is invalid.
6. WHEN scanning completes, THE Scanner SHALL record the total file count and elapsed time for diagnostic purposes.

### Requirement 2: File Classification

**User Story:** As a developer, I want discovered files automatically categorized by type using a deterministic priority order, so that downstream modules process only the relevant artifacts and classification is reproducible.

#### Acceptance Criteria

1. WHEN a DiscoveredFile is provided, THE File_Classifier SHALL assign exactly one primary FileCategory from: PROMPT, TOOL_SOURCE, TOOL_SCHEMA, POLICY, EVAL, TRACE, CONFIG, DOC, UNKNOWN.
2. THE File_Classifier SHALL apply classification rules in a fixed priority order: TRACE > TOOL_SCHEMA > TOOL_SOURCE > PROMPT > POLICY > EVAL > CONFIG > DOC > UNKNOWN. When multiple heuristics match, the highest-priority category wins.
3. THE File_Classifier SHALL record secondary categories that also matched, stored as metadata on the DiscoveredFile, but the primary category is the only one used for routing.
4. THE File_Classifier SHALL classify files as PROMPT when path or filename contains patterns like "prompt", "system", "instructions" or content contains imperative phrases ("You must", "You are", "Always").
5. THE File_Classifier SHALL classify files as TOOL_SOURCE when Python files contain decorators (@tool, @function_tool, @agent.tool) or function names matching tool-naming conventions.
6. THE File_Classifier SHALL classify files as TOOL_SCHEMA when JSON or YAML files contain OpenAI-style or Anthropic-style function/tool schema structures.
7. THE File_Classifier SHALL classify files as TRACE when files are .jsonl or JSON files containing trace-specific keys (steps, tool_calls, messages with role fields).
8. THE File_Classifier SHALL classify files as EVAL when path or filename contains "eval", "test", "spec" patterns.
9. THE File_Classifier SHALL classify files as POLICY when path or filename contains "policy", "rules", "guardrail" patterns.
10. IF no heuristic matches, THEN THE File_Classifier SHALL assign the UNKNOWN category.
11. THE File_Classifier SHALL produce identical classification results for identical inputs across all runs (deterministic guarantee).

### Requirement 3: Prompt Extraction

**User Story:** As a developer, I want prompt content extracted into structured artifacts, so that obligations can be derived from them.

#### Acceptance Criteria

1. WHEN a file classified as PROMPT is provided, THE Prompt_Extractor SHALL parse it and produce a PromptArtifact containing the source path, extracted text, and metadata.
2. THE Prompt_Extractor SHALL handle Markdown files by extracting the full text content.
3. THE Prompt_Extractor SHALL handle YAML files by extracting text from known prompt-holding keys (system_prompt, prompt, instructions, content).
4. THE Prompt_Extractor SHALL handle Python files by extracting string literals assigned to variables matching prompt-related naming patterns or multi-line docstrings.
5. IF a PROMPT file cannot be parsed, THEN THE Prompt_Extractor SHALL log a warning and skip the file without halting the pipeline.

### Requirement 4: Tool Extraction

**User Story:** As a developer, I want tool definitions extracted from source code and schemas, so that the contract can map obligations to specific tools.

#### Acceptance Criteria

1. WHEN a Python file classified as TOOL_SOURCE is provided, THE Tool_Extractor SHALL use AST parsing to find functions decorated with @tool, @function_tool, or @agent.tool and produce ToolArtifact objects.
2. WHEN a JSON or YAML file classified as TOOL_SCHEMA is provided, THE Tool_Extractor SHALL detect OpenAI-style or Anthropic-style schema structures and produce ToolArtifact objects.
3. THE Tool_Extractor SHALL extract tool name, description, parameters (with types and required status), and return type from each discovered tool.
4. THE Tool_Extractor SHALL infer preconditions from parameter constraints and docstring content where available.
5. IF a tool source file has syntax errors preventing AST parsing, THEN THE Tool_Extractor SHALL log a warning and skip that file without halting the pipeline.

### Requirement 5: Obligation Extraction

**User Story:** As a developer, I want agent obligations automatically extracted from prompts and tool metadata, so that compliance can be verified.

#### Acceptance Criteria

1. WHEN prompt text is provided, THE Obligation_Extractor SHALL apply a deterministic regex/pattern registry to identify obligations without using any LLM.
2. THE Obligation_Extractor SHALL detect confirmation_required obligations from patterns indicating user confirmation before actions (e.g., "confirm before", "ask the user", "require approval").
3. THE Obligation_Extractor SHALL detect lookup_required obligations from patterns indicating required data retrieval before decisions.
4. THE Obligation_Extractor SHALL detect policy_check_required obligations from patterns indicating policy consultation requirements.
5. THE Obligation_Extractor SHALL detect error_reporting_required obligations from patterns indicating error disclosure requirements.
6. THE Obligation_Extractor SHALL detect retrieval_injection_guard obligations from patterns indicating input sanitization or injection prevention requirements.
7. THE Obligation_Extractor SHALL detect final_state_consistency obligations from patterns indicating state verification requirements.
8. THE Obligation_Extractor SHALL generate stable IDs for each extracted obligation based on source location and pattern type.
9. WHEN tool metadata contains risk-relevant keywords, THE Obligation_Extractor SHALL also extract obligations from tool descriptions and parameter constraints.

### Requirement 6: Tool Risk Classification

**User Story:** As a developer, I want tools classified by their side-effect risk level, so that appropriate safety checks can be enforced.

#### Acceptance Criteria

1. WHEN a ToolArtifact is provided, THE Risk_Classifier SHALL assign exactly one SideEffectLevel: DESTRUCTIVE, EXTERNAL_WRITE, WEAK, or NONE.
2. THE Risk_Classifier SHALL classify tools as DESTRUCTIVE when name or description contains keywords indicating irreversible operations (delete, remove, drop, terminate, revoke).
3. THE Risk_Classifier SHALL classify tools as EXTERNAL_WRITE when name or description contains keywords indicating external mutations (send, post, update, write, create, transfer, publish).
4. THE Risk_Classifier SHALL classify tools as WEAK when name or description indicates limited side effects (log, notify, cache).
5. THE Risk_Classifier SHALL classify tools as NONE when no side-effect keywords are detected (get, read, fetch, list, search, query).
6. IF multiple risk levels match, THEN THE Risk_Classifier SHALL assign the highest severity level.

### Requirement 7: Contract Compilation

**User Story:** As a developer, I want all extracted data compiled into a single AgentContract, so that downstream checks operate on a unified representation.

#### Acceptance Criteria

1. WHEN prompts, tools, and obligations have been extracted, THE Contract_Compiler SHALL produce an AgentContract linking all artifacts.
2. THE Contract_Compiler SHALL associate obligations with relevant tools via lexical matching between obligation text and tool names/descriptions.
3. THE Contract_Compiler SHALL create ForbiddenTransition entries when obligations imply ordering constraints (e.g., "must confirm before sending").
4. THE Contract_Compiler SHALL serialize the AgentContract to .agentbattery/contract.yaml.
5. THE Contract_Compiler SHALL serialize extracted obligations to .agentbattery/obligations.yaml.
6. FOR ALL valid AgentContract objects, serializing to YAML then deserializing SHALL produce an equivalent AgentContract object (round-trip property).

### Requirement 8: Mismatch Detection and Gap Analysis

**User Story:** As a developer, I want architecture mismatches and safety gaps automatically detected and classified by gap type, so that I can understand the nature of each issue and prioritize fixes.

#### Acceptance Criteria

1. WHEN an AgentContract is provided, THE Mismatch_Detector SHALL run checks A through G and produce Finding objects for each detected issue.
2. EVERY Finding SHALL be tagged with exactly one gap_type: POLICY_GAP, ENFORCEMENT_GAP, COVERAGE_GAP, or TRACE_VIOLATION.
3. THE Mismatch_Detector SHALL detect Check A (Policy Gap): a dangerous tool (DESTRUCTIVE or EXTERNAL_WRITE) with NO linked obligation of any type. The absence of an obligation must not suppress the finding — it must emit a POLICY_GAP finding at HIGH or CRITICAL severity.
4. THE Mismatch_Detector SHALL detect Check B (Enforcement Gap): obligation of type CONFIRMATION_REQUIRED linked to a tool, but no runtime precondition detected in the tool source. Finding text SHALL use uncertainty wording: "No confirmation precondition detected in tool source."
5. THE Mismatch_Detector SHALL detect Check C (Enforcement Gap): financial-related tool missing a policy_check_required precondition. Finding text SHALL say: "No policy/eligibility precondition detected."
6. THE Mismatch_Detector SHALL detect Check D (Policy Gap): DESTRUCTIVE tool with no confirmation obligation linked.
7. THE Mismatch_Detector SHALL detect Check E (Policy Gap): retrieval tools present alongside external write tools but no RETRIEVAL_INJECTION_GUARD obligation detected.
8. THE Mismatch_Detector SHALL detect Check F (Enforcement Gap): final_state_consistency obligation present but no verification step linked.
9. THE Mismatch_Detector SHALL detect Check G (Enforcement Gap): tool schema with all-optional parameters on a high/critical-risk tool (permissive schema).
10. WHEN a finding is produced, THE Mismatch_Detector SHALL include evidence referencing the specific source locations and artifacts involved, with uncertainty wording where absence is inferred rather than proven.
11. THE Mismatch_Detector SHALL detect prompt-only safety: when a prompt states a safety property (e.g., "never send without confirmation") but no runtime enforcement (tool precondition, schema constraint, or test) is detected for the linked tool, a finding SHALL be emitted as an ENFORCEMENT_GAP.

### Requirement 9: Coverage Analysis

**User Story:** As a developer, I want to know which obligations are covered by existing tests, so that I can focus test-writing effort on gaps.

#### Acceptance Criteria

1. WHEN an AgentContract and eval files are provided, THE Coverage_Analyzer SHALL determine coverage status for each obligation.
2. THE Coverage_Analyzer SHALL mark an obligation as "covered" when existing test content matches obligation keywords with sufficient confidence.
3. THE Coverage_Analyzer SHALL mark an obligation as "partial" when test content partially matches obligation keywords.
4. THE Coverage_Analyzer SHALL mark an obligation as "missing" when no existing test content matches the obligation.
5. WHEN coverage analysis completes, THE Coverage_Analyzer SHALL produce a coverage summary with counts of covered, partial, and missing obligations.
6. FOR EACH obligation with coverage status "missing" and severity CRITICAL or HIGH, THE Coverage_Analyzer SHALL emit a MISSING_EVAL finding tagged with gap_type COVERAGE_GAP.

### Requirement 10: Trace Loading

**User Story:** As a developer, I want agent execution traces loaded and normalized, so that they can be checked against the contract.

#### Acceptance Criteria

1. WHEN a .jsonl trace file is provided, THE Trace_Loader SHALL parse each line as a TraceStep and assemble an AgentTrace.
2. WHEN a .json file with a steps list is provided, THE Trace_Loader SHALL parse it into an AgentTrace.
3. THE Trace_Loader SHALL normalize each step into a TraceStep with type (TOOL_CALL, TOOL_RESULT, AGENT_MESSAGE, USER_MESSAGE), tool_name, arguments, and result fields.
4. IF a trace file contains malformed entries, THEN THE Trace_Loader SHALL skip invalid entries, log warnings, and continue processing valid entries.
5. FOR ALL valid AgentTrace objects, serializing to JSON then deserializing SHALL produce an equivalent AgentTrace object (round-trip property).

### Requirement 11: Trace Checking

**User Story:** As a developer, I want existing traces validated against the contract, so that I can find runtime violations.

#### Acceptance Criteria

1. WHEN an AgentTrace and AgentContract are provided, THE Trace_Checker SHALL run six defined checks and produce Finding objects for violations.
2. THE Trace_Checker SHALL detect use of forbidden tools (tools called that violate ForbiddenTransition rules).
3. THE Trace_Checker SHALL detect missing confirmation before external write (EXTERNAL_WRITE or DESTRUCTIVE tool called without preceding user confirmation step).
4. THE Trace_Checker SHALL detect required ordering violations (steps that must precede other steps based on obligations).
5. THE Trace_Checker SHALL detect tool error hiding (tool returns an error but agent does not report it to the user).
6. THE Trace_Checker SHALL detect claimed action without tool call (agent claims to have performed an action but no corresponding tool call exists in the trace).
7. THE Trace_Checker SHALL detect retrieval injection not followed by sanitization (retrieval result used without guard step).
8. ALL findings produced by the Trace_Checker SHALL be tagged with gap_type TRACE_VIOLATION.

### Requirement 12: Test Generation

**User Story:** As a developer, I want missing test cases automatically generated from findings, so that I can quickly close coverage gaps.

#### Acceptance Criteria

1. WHEN findings are produced, THE Test_Generator SHALL create GeneratedTest objects for each finding that has a testable remediation.
2. THE Test_Generator SHALL generate side-effect confirmation tests for findings related to missing confirmation obligations.
3. THE Test_Generator SHALL generate policy lookup tests for findings related to missing policy checks on financial tools.
4. THE Test_Generator SHALL generate retrieval injection tests for findings related to missing injection guards.
5. THE Test_Generator SHALL generate final-state consistency tests for findings related to missing verification steps.
6. THE Test_Generator SHALL output generated tests as YAML to .agentbattery/generated_tests/ directory.

### Requirement 13: Test Export

**User Story:** As a developer, I want generated tests exported in multiple formats, so that I can integrate them into my existing test infrastructure.

#### Acceptance Criteria

1. THE Exporter SHALL serialize generated tests to YAML format in .agentbattery/generated_tests/.
2. WHERE pytest export is enabled, THE Exporter SHALL render generated tests as pytest test functions using a Jinja2 adapter template.
3. WHERE promptfoo export is enabled, THE Exporter SHALL render generated tests in promptfoo-compatible YAML format.
4. THE YAML Exporter SHALL produce output that is parseable by standard YAML parsers without errors.
5. FOR ALL generated test objects, exporting to YAML then reimporting SHALL produce equivalent test objects (round-trip property).

### Requirement 14: Report Generation

**User Story:** As a developer, I want a comprehensive audit report in both human-readable and machine-readable formats, so that I can review findings and share them with my team.

#### Acceptance Criteria

1. WHEN an audit completes, THE Report_Generator SHALL produce a Markdown report at .agentbattery/reports/latest.md.
2. WHEN an audit completes, THE Report_Generator SHALL produce a JSON report at .agentbattery/reports/latest.json.
3. THE Report_Generator SHALL include sections for: summary, architecture overview, tool risk table, obligations list, findings, coverage analysis, trace violations, generated tests, and next actions.
4. THE Report_Generator SHALL sort findings by severity (critical, high, medium, low).
5. THE JSON report SHALL be parseable by standard JSON parsers without errors.
6. THE Markdown report SHALL use proper Markdown formatting with headers, tables, and code blocks.

### Requirement 15: CLI Interface

**User Story:** As a developer, I want a command-line interface with clear commands and options, so that I can run audits manually or in CI pipelines.

#### Acceptance Criteria

1. THE CLI SHALL expose a "scan" command that runs only the scanner and file classifier on a target directory.
2. THE CLI SHALL expose a "compile-contract" command that runs scanning, extraction, and contract compilation.
3. THE CLI SHALL expose an "audit" command that runs the full pipeline (scan, extract, compile, detect, analyze, generate, report).
4. THE CLI SHALL expose a "check-trace" command that loads and checks a specific trace file against a compiled contract.
5. THE CLI SHALL expose a "generate-tests" command that generates tests from an existing contract and findings.
6. THE CLI SHALL expose a "report" command that generates reports from existing findings data.
7. THE CLI SHALL accept a --generate-tests flag on the audit command to enable test generation.
8. THE CLI SHALL accept a --report flag on the audit command to enable report generation.
9. WHEN the audit completes with no findings above the configured threshold, THE CLI SHALL exit with code 0.
10. WHEN the audit completes with findings above the configured threshold, THE CLI SHALL exit with code 1.
11. IF an internal error occurs, THEN THE CLI SHALL exit with code 2 and print a descriptive error message.
12. THE CLI SHALL display progress information using rich formatting during execution.

### Requirement 16: Output Directory Structure

**User Story:** As a developer, I want audit outputs organized in a consistent directory structure, so that I can easily find and version-control results.

#### Acceptance Criteria

1. WHEN an audit runs, THE CLI SHALL create a .agentbattery/ directory in the target repo root if it does not exist.
2. THE CLI SHALL write contract.yaml to .agentbattery/contract.yaml.
3. THE CLI SHALL write obligations.yaml to .agentbattery/obligations.yaml.
4. THE CLI SHALL write findings.yaml to .agentbattery/findings.yaml.
5. THE CLI SHALL write generated tests to .agentbattery/generated_tests/ directory.
6. THE CLI SHALL write reports to .agentbattery/reports/ directory with latest.md and latest.json filenames.
7. THE output files SHALL be human-editable and use clear, commented YAML or properly formatted Markdown/JSON.

### Requirement 17: Data Model Integrity

**User Story:** As a developer, I want all internal data models validated with Pydantic v2, so that invalid data is caught early and error messages are clear.

#### Acceptance Criteria

1. THE models module SHALL define all data models using Pydantic v2 BaseModel classes.
2. THE models module SHALL define enumerations for FileCategory, SideEffectLevel, RiskLevel, ObligationType, FindingType, and TraceStepType.
3. THE models module SHALL validate that required fields are present and correctly typed on instantiation.
4. IF invalid data is provided to a model constructor, THEN THE model SHALL raise a ValidationError with a descriptive message.
5. THE ToolArtifact model SHALL include fields for name, description, parameters (list of ToolParameter), return_type, source_path, and side_effect_level.
6. THE Finding model SHALL include fields for finding_type, severity, gap_type (one of POLICY_GAP, ENFORCEMENT_GAP, COVERAGE_GAP, TRACE_VIOLATION), title, description, evidence (list of Evidence), and optional remediation.
7. FOR ALL Pydantic models, serializing to dict then constructing from dict SHALL produce an equivalent model instance (round-trip property).
8. THE models module SHALL define AgentProfile with fields for name, purpose, capabilities (list[str]), and source_evidence (list[str]).
9. THE models module SHALL define DecisionPolicy with fields for strategy (str), stop_conditions (list[str]), tool_selection_logic (str | None), and source_evidence (list[str]).
10. THE models module SHALL define HumanInLoopPolicy with fields for approval_required_tools (list[str]), review_triggers (list[str]), override_mechanism (str | None), and source_evidence (list[str]).
11. THE models module SHALL define FailurePolicy with fields for retry_strategy (str | None), timeout_seconds (int | None), fallback_behavior (str | None), partial_completion_handling (str | None), recovery_mechanism (str | None), and source_evidence (list[str]).
12. THE models module SHALL define OrchestrationPolicy with fields for agents (list[AgentNode]), delegation_bounds (str | None), shared_state_mechanism (str | None), communication_pattern (str | None), and source_evidence (list[str]).
13. THE models module SHALL define AgentNode with fields for name, role, tools (list[str]), delegation_targets (list[str]), and scope_limits (str | None).
14. THE AgentContract model SHALL be extended with optional fields: agent_profiles (list[AgentProfile]), decision_policy (DecisionPolicy | None), human_in_loop_policy (HumanInLoopPolicy | None), failure_policy (FailurePolicy | None), orchestration_policy (OrchestrationPolicy | None).

### Requirement 18: Installation and Packaging

**User Story:** As a developer, I want to install agentbattery with pip, so that I can use it immediately without complex setup.

#### Acceptance Criteria

1. WHEN "pip install -e ." is run in the package root, THE package SHALL install successfully with all dependencies.
2. THE package SHALL declare dependencies on: pydantic (>=2.0), typer, rich, pyyaml, and jinja2.
3. THE package SHALL require Python 3.11 or higher.
4. WHEN installed, THE package SHALL register the "agentbattery" command as a console entry point.
5. THE package SHALL include a pyproject.toml with proper metadata and dependency declarations.

### Requirement 19: Example Fixtures and Acceptance Gate

**User Story:** As a developer, I want example agent repos included as fixtures, so that I can verify the tool works correctly and understand its output.

#### Acceptance Criteria

1. THE package SHALL include an email_agent example with a system prompt requiring confirmation before sending, tool definitions, and a bad trace demonstrating a violation.
2. THE package SHALL include a refund_agent example with ordered step requirements (lookup before refund) and tool definitions.
3. THE package SHALL include a lean_agent stub with placeholder interfaces for .lean file analysis.
4. WHEN the audit command is run against the email_agent fixture, THE CLI SHALL produce findings for missing confirmation and trace violations.
5. WHEN the audit command is run against the refund_agent fixture, THE CLI SHALL produce findings for ordering violations.
6. THE email_agent fixture audit SHALL identify send_email as EXTERNAL_WRITE with HIGH or CRITICAL risk (policy gap or enforcement gap finding).
7. THE email_agent fixture audit SHALL detect the unconfirmed send in the trace as a TRACE_VIOLATION finding at CRITICAL or HIGH severity.
8. THE email_agent fixture audit SHALL generate at least one regression test blocking unconfirmed send_email.
9. THE MVP is not considered complete unless criteria 6, 7, and 8 all pass. This is the primary acceptance gate.

### Requirement 20: Determinism and CI Compatibility

**User Story:** As a developer, I want audit results to be deterministic and CI-friendly, so that I can rely on consistent results across environments.

#### Acceptance Criteria

1. THE agentbattery pipeline SHALL produce identical output given identical input, with no randomness or non-deterministic behavior.
2. THE CLI SHALL operate without any network calls or external service dependencies.
3. THE CLI SHALL operate without any LLM API calls or AI model dependencies.
4. THE CLI SHALL produce output suitable for diff-based comparison in version control.
5. WHEN findings are produced, THE CLI SHALL include transparency metadata explaining why each finding was raised (false-positive transparency).
6. ALL findings describing absence (missing precondition, missing obligation, missing test) SHALL use uncertainty wording such as "no precondition detected" or "no confirmation step found" rather than asserting absolute absence, unless evidence definitively proves absence.

### Requirement 21: Hackathon Agent Architecture Audit

**User Story:** As a developer, I want the audit to assess my agent repo against six architecture dimensions (Agent Overview, Autonomy & Decision-Making, Actions & Tool Use, Orchestration, Human-in-the-Loop, Failure Handling), so that I can identify missing architecture documentation and unspecified safety-critical behaviors.

#### Acceptance Criteria

1. THE Rubric_Auditor SHALL scan the target repo for evidence of each of the six architecture dimensions using deterministic heuristics applied to prompts, tool sources, config files, and documentation.
2. THE Rubric_Auditor SHALL emit an AGENT_OVERVIEW_GAP finding when no agent identity, purpose, or capability description is detected in the repo.
3. THE Rubric_Auditor SHALL emit a DECISION_POLICY_GAP finding when no evidence of goal decomposition, planning, or next-action selection logic is detected.
4. THE Rubric_Auditor SHALL emit a STOP_CONDITION_GAP finding when no explicit stop/termination condition is detected for the agent loop.
5. THE Rubric_Auditor SHALL emit a TOOL_SELECTION_POLICY_GAP finding when tools exist but no evidence of tool selection logic, routing, or prioritization is detected.
6. THE Rubric_Auditor SHALL emit an ORCHESTRATION_UNSPECIFIED finding when multiple agents or delegation patterns are detected but no coordination policy is documented.
7. THE Rubric_Auditor SHALL emit an UNBOUNDED_DELEGATION finding when agent-to-agent delegation is detected without scope limits, depth bounds, or termination guarantees.
8. THE Rubric_Auditor SHALL emit a SHARED_STATE_UNSPECIFIED finding when multiple agents are detected but no shared state management (memory, context passing) is documented.
9. THE Rubric_Auditor SHALL emit a HITL_GAP finding when dangerous tools (DESTRUCTIVE or EXTERNAL_WRITE) are present but no human-in-the-loop approval mechanism is detected.
10. THE Rubric_Auditor SHALL emit an APPROVAL_ENFORCEMENT_GAP finding when human approval is mentioned in prompts but no enforcement mechanism (tool precondition, gate step) is detected.
11. THE Rubric_Auditor SHALL emit an OVERRIDE_GAP finding when no mechanism for human override or intervention is detected in an autonomous agent.
12. THE Rubric_Auditor SHALL emit a RETRY_POLICY_GAP finding when tool usage is detected but no retry/backoff policy is documented or implemented.
13. THE Rubric_Auditor SHALL emit a TIMEOUT_POLICY_GAP finding when long-running operations are detected but no timeout mechanism is documented.
14. THE Rubric_Auditor SHALL emit a FALLBACK_POLICY_GAP finding when tool failures are possible but no fallback or graceful degradation strategy is detected.
15. THE Rubric_Auditor SHALL emit a PARTIAL_COMPLETION_GAP finding when multi-step workflows are detected but no partial completion handling is documented.
16. THE Rubric_Auditor SHALL emit a RECOVERY_STATE_GAP finding when stateful operations are detected but no state recovery or rollback mechanism is documented.
17. ALL Rubric_Auditor findings SHALL be tagged with gap_type POLICY_GAP (for missing architecture documentation) or ENFORCEMENT_GAP (for documented but unenforced policies).
18. THE Rubric_Auditor SHALL populate architecture policy models (AgentProfile, DecisionPolicy, HumanInLoopPolicy, FailurePolicy, OrchestrationPolicy) with detected evidence, storing them on the AgentContract.
19. THE Report_Generator SHALL include a "Hackathon Agent Architecture Summary" section with six subsections (Agent Overview, Autonomy & Decision-Making, Actions & Tool Use, Orchestration, Human-in-the-Loop, Failure Handling), each showing detected evidence, missing elements, related findings, and generated tests where applicable.

### Requirement 22: Architecture Audit Acceptance Criteria

**User Story:** As a developer, I want the audit report to answer six fundamental questions about my agent, so that I can verify architectural completeness.

#### Acceptance Criteria

1. THE report SHALL answer "What agent(s) exist and what is their purpose?" by listing discovered AgentProfile entries with name, purpose, and capabilities.
2. THE report SHALL answer "How does the agent decide what to do next?" by showing the detected DecisionPolicy or emitting findings for missing decision logic.
3. THE report SHALL answer "What tools/actions can it take?" by showing the tool risk table with side-effect levels and linked obligations.
4. THE report SHALL answer "If multi-agent, how do agents coordinate?" by showing the OrchestrationPolicy or emitting findings for unspecified coordination.
5. THE report SHALL answer "Where does a human approve, review, or override?" by showing the HumanInLoopPolicy or emitting findings for missing HITL mechanisms.
6. THE report SHALL answer "How does it handle failures, tool errors, partial completion, and unexpected states?" by showing the FailurePolicy or emitting findings for missing failure handling.
7. THE MVP is not considered complete unless the report includes all six subsections of the Hackathon Agent Architecture Summary, with either detected evidence or findings for each dimension.

### Requirement 23: CI/CD Readiness and Repair Input

**User Story:** As a developer, I want audit outputs to be CI-pipeline-ready and to emit a machine-readable repair input file, so that downstream automation (CI bots, repair agents) can consume findings without re-parsing reports.

#### Acceptance Criteria

1. THE CLI SHALL accept a `--ci` flag on the audit command that suppresses non-deterministic rich/progress output and ensures stable machine-readable output.
2. WHEN `--ci` is set, THE CLI SHALL write all machine-readable outputs (contract.yaml, findings.yaml, repair_input.json, reports) even when findings are present (do not short-circuit file writes on failure).
3. THE CLI SHALL write `.agentbattery/repair_input.json` at the end of every audit run.
4. THE repair_input.json SHALL contain for each finding: finding_id, severity, gap_type, linked_tools, linked_obligations, evidence references, generated_test_ids, and recommended_repair_type.
5. THE recommended_repair_type SHALL be one of: ADD_TEST, ADD_TOOL_PRECONDITION, TIGHTEN_SCHEMA, ADD_FINAL_STATE_VERIFIER, ADD_HITL_GATE, ADD_RETRY_OR_FALLBACK, UPDATE_ARCHITECTURE_DOC.
6. THE repair_input.json SHALL NOT contain patches, diffs, or LLM-generated content. It is a structured finding summary only.
7. THE models module SHALL define RecommendedRepairType enum, RepairFinding model, and RepairInput model.
8. FOR ALL valid RepairInput objects, serializing to JSON then deserializing SHALL produce an equivalent RepairInput object (round-trip property).
