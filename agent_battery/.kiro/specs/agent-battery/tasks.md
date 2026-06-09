# Implementation Plan: agent-battery

## Overview

Implement `agentbattery`, a deterministic Python CLI that audits AI agent repositories for safety gaps. The implementation follows an incremental pipeline approach: project skeleton → scanner → extractors → contract → detection → architecture audit → traces → test generation → reports → fixtures & acceptance tests.

## Tasks

- [x] 1. Set up project skeleton and data models
  - [x] 1.1 Create pyproject.toml with metadata, dependencies (pydantic>=2.0, typer, rich, pyyaml, jinja2), Python >=3.11, and console entry point `agentbattery`
    - Define package name, version, description, author
    - Declare all dependencies with pinned minimum versions
    - Register `agentbattery = "agentbattery.cli:app"` as console script
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [x] 1.2 Create package directory structure with empty modules
    - Create `src/agentbattery/__init__.py`, `cli.py`, `scanner.py`, `file_classifier.py`, `prompt_extractor.py`, `tool_extractor.py`, `obligation_extractor.py`, `risk_classifier.py`, `contract_compiler.py`, `mismatch_detector.py`, `coverage_analyzer.py`, `trace_loader.py`, `trace_checker.py`, `rubric_auditor.py`, `test_generator.py`, `report.py`, `exceptions.py`
    - Create `src/agentbattery/exporters/__init__.py`, `yaml_exporter.py`, `pytest_exporter.py`, `promptfoo_exporter.py`
    - Create `tests/` directory with `conftest.py`
    - _Requirements: 18.1_

  - [x] 1.3 Implement all Pydantic v2 data models in `src/agentbattery/models.py`
    - Define enumerations: FileCategory, SideEffectLevel, RiskLevel, ObligationType, GapType, TraceStepType, CoverageStatus, RecommendedRepairType
    - Define core models: DiscoveredFile, ClassifiedFile, ToolParameter, ToolArtifact, PromptArtifact, Obligation, ForbiddenTransition, Evidence, Finding, ObligationCoverage, CoverageResult, TraceStep, AgentTrace, GeneratedTest, ScanResult
    - Define architecture models: AgentNode, AgentProfile, DecisionPolicy, HumanInLoopPolicy, FailurePolicy, OrchestrationPolicy
    - Define AgentContract with all fields including optional policy models
    - Define repair input models: RepairFinding, RepairInput
    - Define RecommendedRepairType enum: ADD_TEST, ADD_TOOL_PRECONDITION, TIGHTEN_SCHEMA, ADD_FINAL_STATE_VERIFIER, ADD_HITL_GATE, ADD_RETRY_OR_FALLBACK, UPDATE_ARCHITECTURE_DOC
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.10, 17.11, 17.12, 17.13, 17.14_

  - [x] 1.4 Implement custom exception classes in `src/agentbattery/exceptions.py`
    - Define AgentBatteryError, ScanError, ContractError, ReportError
    - _Requirements: 15.11_

  - [ ]* 1.5 Write property tests for Pydantic model round-trips
    - **Property 30: Pydantic model dict round-trip**
    - **Property 31: Pydantic validation rejects invalid data**
    - **Validates: Requirements 17.3, 17.4, 17.7**

- [x] 2. Implement Scanner and File Classifier
  - [x] 2.1 Implement `scanner.py` with `scan()` function
    - Recursively walk target directory using pathlib
    - Apply default include globs (*.py, *.md, *.yaml, *.yml, *.json, *.jsonl, *.toml)
    - Apply default exclude globs (.git, __pycache__, node_modules, .venv, .env, dist, build, *.egg-info)
    - Support custom include/exclude globs
    - Raise ScanError for invalid paths
    - Record total_count and elapsed_seconds in ScanResult
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 2.2 Write property tests for scanner
    - **Property 1: Scanner glob filtering**
    - **Property 2: Scan result count invariant**
    - **Validates: Requirements 1.2, 1.3, 1.6**

  - [x] 2.3 Implement `file_classifier.py` with `classify()` function
    - Implement priority-ordered heuristic chain: TRACE > TOOL_SCHEMA > TOOL_SOURCE > PROMPT > POLICY > EVAL > CONFIG > DOC > UNKNOWN
    - Each heuristic checks path patterns and file content
    - Assign primary_category from first match, record secondary_categories from remaining matches
    - Return UNKNOWN as fallback
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11_

  - [ ]* 2.4 Write property tests for file classifier
    - **Property 3: File classification priority and determinism**
    - **Property 4: File classification heuristic correctness**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.11**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Prompt and Tool Extraction
  - [x] 4.1 Implement `prompt_extractor.py` with `extract_prompts()` function
    - Handle Markdown files: extract full text content
    - Handle YAML files: extract from keys system_prompt, prompt, instructions, content
    - Handle Python files: extract from SYSTEM_PROMPT/*_PROMPT/*_INSTRUCTIONS variables and triple-quoted docstrings in prompt-named functions
    - Log warning and skip on parse failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 4.2 Write property tests for prompt extractor
    - **Property 5: Prompt extraction produces non-empty artifacts**
    - **Property 6: Extraction resilience (prompt part)**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

  - [x] 4.3 Implement `tool_extractor.py` with `extract_tools()` function
    - Python AST parsing: find functions with @tool, @function_tool, @agent.tool decorators
    - Extract name, docstring, parameter annotations, return annotation
    - JSON/YAML schema parsing: detect OpenAI-style (functions[].parameters) and Anthropic-style (tools[].input_schema) structures
    - Infer preconditions from parameter constraints and docstrings
    - Log warning and skip on AST parse failure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 4.4 Write property tests for tool extractor
    - **Property 7: Tool extraction completeness**
    - **Property 6: Extraction resilience (tool part)**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5**

- [x] 5. Implement Obligation Extraction and Risk Classification
  - [x] 5.1 Implement `obligation_extractor.py` with `extract_obligations()` function
    - Define regex pattern registry for six obligation types (CONFIRMATION_REQUIRED, LOOKUP_REQUIRED, POLICY_CHECK_REQUIRED, ERROR_REPORTING_REQUIRED, RETRIEVAL_INJECTION_GUARD, FINAL_STATE_CONSISTENCY)
    - Apply patterns to prompt text and tool metadata
    - Generate stable IDs: sha256(source_path + ":" + pattern_type + ":" + match_start_offset)[:12]
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [ ]* 5.2 Write property tests for obligation extractor
    - **Property 8: Obligation pattern detection**
    - **Property 9: Obligation ID stability**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9**

  - [x] 5.3 Implement `risk_classifier.py` with `classify_risk()` function
    - Define keyword sets for DESTRUCTIVE, EXTERNAL_WRITE, WEAK, NONE
    - Check lowercased tool name + description against keyword sets
    - Apply priority: DESTRUCTIVE > EXTERNAL_WRITE > WEAK > NONE
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 5.4 Write property tests for risk classifier
    - **Property 10: Risk classification priority**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**

- [x] 6. Implement Contract Compilation
  - [x] 6.1 Implement `contract_compiler.py` with `compile_contract()` function
    - Tokenize obligation text and tool name+description
    - Compute token overlap score with stopword removal; link if score >= 1 shared meaningful token
    - Build ForbiddenTransition entries from ordering language ("before", "after", "must precede")
    - Assemble AgentContract with all linked artifacts
    - Serialize contract to .agentbattery/contract.yaml
    - Serialize obligations to .agentbattery/obligations.yaml
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 6.2 Write property tests for contract compiler
    - **Property 11: Contract compilation links all artifacts**
    - **Property 12: Forbidden transition creation**
    - **Property 13: AgentContract YAML round-trip**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.6**

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Mismatch Detection and Coverage Analysis
  - [x] 8.1 Implement `mismatch_detector.py` with `detect_mismatches()` function
    - Implement Check A: POLICY_GAP for dangerous tools with zero linked obligations
    - Implement Check B: ENFORCEMENT_GAP for CONFIRMATION_REQUIRED without precondition
    - Implement Check C: ENFORCEMENT_GAP for financial tools missing policy check
    - Implement Check D: POLICY_GAP for DESTRUCTIVE tool without confirmation obligation
    - Implement Check E: POLICY_GAP for retrieval+write tools without injection guard
    - Implement Check F: ENFORCEMENT_GAP for consistency obligation without verification
    - Implement Check G: ENFORCEMENT_GAP for all-optional params on high-risk tool
    - Implement prompt-only safety detection (prompt states property → obligation exists → no enforcement → ENFORCEMENT_GAP)
    - All findings use uncertainty wording and include evidence
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11_

  - [ ]* 8.2 Write property tests for mismatch detector
    - **Property 14: Finding invariants**
    - **Property 15: Mismatch Check A — Policy Gap for dangerous unobligated tools**
    - **Property 16: Mismatch Check B — Enforcement Gap for unimplemented confirmation**
    - **Property 17: Mismatch Checks C–G**
    - **Property 18: Prompt-only safety detection**
    - **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11**

  - [x] 8.3 Implement `coverage_analyzer.py` with `analyze_coverage()` function
    - Extract tokens from obligation text
    - Match against eval file content with scoring (>=0.6 covered, >=0.3 partial, <0.3 missing)
    - Emit COVERAGE_GAP findings for MISSING obligations at CRITICAL/HIGH severity
    - Return CoverageResult with counts
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 8.4 Write property tests for coverage analyzer
    - **Property 19: Coverage scoring and threshold classification**
    - **Property 20: Coverage gap finding emission**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**

- [x] 9. Implement Rubric Auditor
  - [x] 9.1 Implement `rubric_auditor.py` with `audit_architecture()` function
    - MVP scope: report-oriented and finding-oriented, using simple evidence heuristics only
    - Implement Agent Overview dimension: detect agent identity phrases in prompts/docs/config, emit AGENT_OVERVIEW_GAP if missing
    - Implement Autonomy & Decision-Making: detect stop conditions and agent-loop language; emit DECISION_POLICY_GAP, STOP_CONDITION_GAP (only if loop language present), TOOL_SELECTION_POLICY_GAP
    - Implement Orchestration: detect multi-agent indicators only via simple heuristics (multiple prompt roles, delegation keywords); emit ORCHESTRATION_UNSPECIFIED, UNBOUNDED_DELEGATION, SHARED_STATE_UNSPECIFIED only if multi-agent detected. Do NOT deeply infer multi-agent architecture.
    - Implement Human-in-the-Loop: detect missing HITL for dangerous tools (DESTRUCTIVE/EXTERNAL_WRITE with no confirmation obligation); emit HITL_GAP, APPROVAL_ENFORCEMENT_GAP, OVERRIDE_GAP
    - Implement Failure Handling: detect retry, timeout, fallback, partial completion, recovery keywords in code/config; emit RETRY_POLICY_GAP, TIMEOUT_POLICY_GAP, FALLBACK_POLICY_GAP, PARTIAL_COMPLETION_GAP, RECOVERY_STATE_GAP
    - Populate AgentContract with detected policy models (agent_profiles, decision_policy, human_in_loop_policy, failure_policy, orchestration_policy) using detected evidence
    - Populate the six Hackathon Summary sections with detected/missing evidence
    - Tag findings with gap_type POLICY_GAP (missing docs) or ENFORCEMENT_GAP (documented but unenforced)
    - All findings use uncertainty wording
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 21.7, 21.8, 21.9, 21.10, 21.11, 21.12, 21.13, 21.14, 21.15, 21.16, 21.17, 21.18_

  - [ ]* 9.2 Write property tests for rubric auditor
    - **Property 33: Rubric Auditor emits AGENT_OVERVIEW_GAP for repos without agent identity**
    - **Property 34: Rubric Auditor emits HITL_GAP for dangerous tools without approval**
    - **Property 35: Rubric Auditor populates architecture policy models**
    - **Property 37: Architecture audit findings use uncertainty wording**
    - **Validates: Requirements 21.2, 21.9, 21.17, 21.18**

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Trace Loading and Checking
  - [x] 11.1 Implement `trace_loader.py` with `load_traces()` function
    - Parse JSONL files line by line into TraceStep objects
    - Parse JSON files with steps list into TraceStep objects
    - Normalize step types: TOOL_CALL, TOOL_RESULT, AGENT_MESSAGE, USER_MESSAGE based on content keys
    - Skip malformed entries with logged warnings
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 11.2 Write property tests for trace loader
    - **Property 21: Trace loading and normalization**
    - **Property 22: AgentTrace JSON round-trip**
    - **Property 6: Extraction resilience (trace part)**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**

  - [x] 11.3 Implement `trace_checker.py` with `check_traces()` function
    - Check 1: Forbidden tool use (violates ForbiddenTransition)
    - Check 2: Missing confirmation before external write (EXTERNAL_WRITE/DESTRUCTIVE tool without preceding user confirmation)
    - Check 3: Ordering violation (required predecessor missing)
    - Check 4: Error hiding (TOOL_RESULT error not disclosed to user)
    - Check 5: Claimed action without tool call (agent claims action but no TOOL_CALL)
    - Check 6: Retrieval injection (retrieval result without guard step)
    - All findings tagged gap_type=TRACE_VIOLATION
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [ ]* 11.4 Write property tests for trace checker
    - **Property 23: Trace checker emits TRACE_VIOLATION for violations**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8**

- [x] 12. Implement Test Generator and Exporters
  - [x] 12.1 Implement `test_generator.py` with `generate_tests()` function
    - Map finding types to test types: CONFIRMATION_REQUIRED→confirmation test, POLICY_CHECK→policy test, RETRIEVAL_INJECTION_GUARD→injection test, FINAL_STATE_CONSISTENCY→consistency test, TRACE_VIOLATION→regression test
    - Generate GeneratedTest objects with setup, assertions, tags
    - Every generated test MUST include: triggering finding_id, linked obligation_ids, linked tool names, expected must_call/must_not_call assertions where applicable, gap_type tag, severity tag
    - Output to .agentbattery/generated_tests/ as YAML
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [ ]* 12.2 Write property tests for test generator
    - **Property 24: Test generation maps finding types to test types**
    - **Property 25: Generated test YAML round-trip**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 13.5**

  - [x] 12.3 Implement exporters (yaml_exporter.py, pytest_exporter.py, promptfoo_exporter.py)
    - YAML exporter: serialize GeneratedTest list to YAML files
    - pytest exporter: render tests as pytest functions using Jinja2 templates
    - promptfoo exporter: render tests in promptfoo-compatible YAML format
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - [ ]* 12.4 Write property tests for exporters
    - **Property 26: Exporter produces parseable output**
    - **Validates: Requirements 13.1, 13.2, 13.3, 13.4**

- [x] 13. Implement Report Generator
  - [x] 13.1 Implement `report.py` with `generate_report()` function
    - Produce Markdown report at .agentbattery/reports/latest.md
    - Produce JSON report at .agentbattery/reports/latest.json
    - Include sections: Summary, Architecture Overview, Tool Risk Table, Obligations List, Findings (sorted by severity), Coverage Analysis, Trace Violations, Hackathon Agent Architecture Summary, Generated Tests, Next Actions
    - Hackathon Agent Architecture Summary section with six subsections: Agent Overview, Autonomy & Decision-Making, Actions & Tool Use, Orchestration, Human-in-the-Loop, Failure Handling
    - Each subsection shows detected evidence, missing elements (uncertainty wording), related findings, and generated tests
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 21.19, 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7_

  - [ ]* 13.2 Write property tests for report generator
    - **Property 27: Report contains all required sections**
    - **Property 28: Report findings sorted by severity**
    - **Property 29: JSON report is parseable**
    - **Property 36: Report includes Hackathon Agent Architecture Summary**
    - **Validates: Requirements 14.3, 14.4, 14.5, 21.19, 22.7**

- [x] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement CLI Interface
  - [x] 15.1 Implement `cli.py` with Typer commands
    - `scan` command: run scanner + file classifier on target directory
    - `compile-contract` command: scan + extract + compile contract
    - `audit` command: full pipeline with --generate-tests and --report flags, --threshold option
    - `check-trace` command: load and check specific trace file against contract
    - `generate-tests` command: generate tests from existing contract and findings
    - `report` command: generate reports from existing findings data
    - Exit codes: 0 (no findings above threshold), 1 (findings above threshold), 2 (internal error)
    - Rich progress display during execution
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8, 15.9, 15.10, 15.11, 15.12_

  - [x] 15.2 Implement output directory structure management
    - Create .agentbattery/ directory in target repo root
    - Write contract.yaml, obligations.yaml, findings.yaml to correct paths
    - Write generated tests to .agentbattery/generated_tests/
    - Write reports to .agentbattery/reports/ with latest.md and latest.json
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7_

- [x] 16. Create Example Fixtures and Acceptance Tests
  - [x] 16.1 Create `examples/email_agent/` fixture
    - System prompt requiring confirmation before sending emails
    - `send_email` tool definition (EXTERNAL_WRITE)
    - `read_inbox` tool definition (NONE)
    - Bad trace: agent sends email without user confirmation
    - _Requirements: 19.1_

  - [x] 16.2 Create `examples/refund_agent/` fixture
    - System prompt requiring lookup before issuing refund
    - `lookup_order` and `issue_refund` tool definitions
    - Trace with ordering violation (refund without prior lookup)
    - _Requirements: 19.2_

  - [x] 16.3 Create `examples/lean_agent/` fixture
    - Stub with placeholder interfaces for .lean file analysis
    - Minimal prompt and tool definitions
    - _Requirements: 19.3_

  - [x] 16.4 Write email_agent acceptance test
    - Verify send_email classified as EXTERNAL_WRITE with HIGH or CRITICAL finding
    - Verify trace violation detected for unconfirmed send
    - Verify at least one regression test generated blocking unconfirmed send_email
    - This test MUST pass for MVP completion
    - _Requirements: 19.4, 19.6, 19.7, 19.8, 19.9_

  - [x] 16.5 Write refund_agent acceptance test
    - Verify ordering violation findings produced
    - _Requirements: 19.5_

- [x] 17. Integration Testing and Pipeline Determinism
  - [x] 17.1 Write full pipeline integration test
    - Run complete audit pipeline on email_agent fixture
    - Verify all output files created in correct locations
    - Verify report includes Hackathon Agent Architecture Summary section
    - Verify determinism: running twice produces identical output
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6_

  - [ ]* 17.2 Write property test for pipeline determinism
    - **Property 32: Pipeline determinism**
    - **Validates: Requirements 20.1**

- [x] 18. Add CI/CD readiness outputs
  - [x] 18.1 Add `--ci` mode to `agentbattery audit`
    - Suppress non-deterministic rich/progress output when --ci is set
    - Ensure exit codes are stable: 0 pass, 1 findings above threshold, 2 internal error
    - Write all machine-readable outputs even when audit finds issues (do not short-circuit file writes)
    - _Requirements: 15.9, 15.10, 15.11, 20.1, 20.4_

  - [x] 18.2 Emit machine-readable repair input
    - Write `.agentbattery/repair_input.json` at end of audit
    - Include for each finding: finding_id, severity, gap_type, linked_tools, linked_obligations, evidence, generated_test_ids, recommended_repair_type (from RecommendedRepairType enum)
    - Do NOT apply patches or call an LLM — this is output only
    - _Requirements: 8.10, 12.1, 14.2, 20.2, 20.3_

  - [x] 18.3 Add GitHub Actions example workflow
    - Create `examples/github-actions/agentbattery.yml`
    - Steps: checkout, install Python 3.11+, `pip install -e .`, `agentbattery audit . --generate-tests --report --ci --threshold HIGH`, upload `.agentbattery/` as artifact
    - This is an example only — not required for core test suite
    - _Requirements: 15.3, 16.1, 16.6, 20.4_

- [x] 19. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Verify email_agent acceptance gate passes (Requirements 19.9)
  - Verify report includes all six Hackathon Architecture Summary subsections (Requirements 22.7)
  - Verify repair_input.json is emitted with correct schema

## Notes

- Tasks marked with `*` are optional property tests — skip for hackathon speed. Prioritize unit/integration tests. Implement property tests only after the email_agent acceptance gate passes.
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The email_agent acceptance gate (task 16.4) is the primary MVP completion criterion
- All findings must use uncertainty wording per Requirement 20.6
- No LLM or network dependencies allowed per Requirements 20.2, 20.3
- The rubric_auditor should be report-oriented and finding-oriented, not deeply inferring multi-agent architecture. Required MVP behavior: detect missing HITL for dangerous tools, detect missing stop conditions if agent-loop language present, populate six Hackathon Summary sections with detected/missing evidence.
- Generated tests must be actionable: every test includes finding_id, obligation_ids, tool names, must_call/must_not_call assertions, gap_type tag, and severity tag. This makes output usable for future CI/CD repair automation.
- repair_input.json provides a clean interface for future Taste Compiler / CI repair loop integration (Phase 2). Do NOT implement repair logic, patch generation, or LLM-assisted fixes in this MVP.
- Phase 2 (separate spec, after MVP acceptance): CI/CD repair loop, Taste Compiler integration, auto-patch PRs, approval gates, rerun loops.
