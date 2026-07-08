# Implementation Plan: LLM Agent Battery

## Overview

Incremental build of the `llm_agent_battery/` package — a unified CLI combining deterministic heuristic analysis with LLM-powered semantic code review. Each task produces a working increment, building from data models outward to the full pipeline.

## Tasks

- [x] 1. Set up project structure, data models, and configuration
  - [x] 1.1 Create `llm_agent_battery/` package with `pyproject.toml`, `__init__.py`, and `py.typed`
    - Use hatchling build system, Python >=3.11
    - Dependencies: pydantic>=2.0, typer>=0.9.0, rich>=13.0.0, pyyaml>=6.0, boto3>=1.28
    - Dev dependencies: pytest, hypothesis, pytest-asyncio
    - Entry point: `llm-agent-battery = "llm_agent_battery.cli:app"`
    - _Requirements: 8.1, 8.2_

  - [x] 1.2 Implement all Pydantic data models in `llm_agent_battery/models.py`
    - Enums: FileCategory, Severity, FindingCategory, ArchitectureStyle
    - Core models: ScanConfig, DiscoveredFile, ScanWarning, ScanResult, ClassifiedFile, ClassifyConfig, CodeChunk, ChunkConfig, Finding, ReviewProfile, InferenceConfig, ConcurrencyConfig, PipelineConfig, TokenUsage, PipelineResult
    - All models exactly as specified in the design document
    - _Requirements: 7.1, 1.1, 2.1, 3.6_

  - [ ]* 1.3 Write property test for ReviewProfile YAML round-trip
    - **Property 13: Review profile YAML round-trip**
    - **Validates: Requirements 6.4**

- [x] 2. Implement File Scanner
  - [x] 2.1 Implement `llm_agent_battery/scanner.py` with `scan()` function
    - Recursively discover files matching include globs, skip exclude globs
    - Skip files > max_file_size_bytes (default 500KB) with warning
    - Return ScanResult with elapsed_seconds timing
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.2 Write property test for scanner glob filtering
    - **Property 1: Scanner respects include/exclude glob filters**
    - **Validates: Requirements 1.1**

  - [ ]* 2.3 Write property test for oversized file handling
    - **Property 2: Scanner skips oversized files with warning**
    - **Validates: Requirements 1.5**

- [x] 3. Implement File Classifier
  - [x] 3.1 Implement `llm_agent_battery/classifier.py` with `classify_files()` function
    - Content-based heuristics: AST patterns, import analysis, decorator detection
    - Path-based heuristics as fallback
    - Assign primary_category and optional secondary_categories
    - Fast mode: skip LLM fallback entirely
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 3.2 Write property test for single primary category assignment
    - **Property 3: Classifier assigns exactly one primary category**
    - **Validates: Requirements 2.1**

  - [ ]* 3.3 Write property test for content-over-path priority
    - **Property 4: Content-based heuristics take priority over path-based**
    - **Validates: Requirements 2.4**

- [x] 4. Implement Semantic Chunker
  - [x] 4.1 Implement `llm_agent_battery/chunker.py` with `chunk_file()` function
    - Python AST-based splitting at function/class boundaries
    - Preserve module preamble (imports, constants) on each chunk
    - Keep classes with shared state as single chunks
    - Enforce max_chunk_chars, mark oversized standalone functions with is_truncated=True
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 4.2 Write property test for chunk size invariant
    - **Property 6: Chunk size invariant**
    - **Validates: Requirements 3.3, 3.6**

  - [ ]* 4.3 Write property test for preamble preservation
    - **Property 7: Chunker preserves module preamble**
    - **Validates: Requirements 3.4**

  - [ ]* 4.4 Write property test for class unity
    - **Property 8: Classes with shared state remain unified**
    - **Validates: Requirements 3.5**

- [x] 5. Checkpoint — Core data pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Bedrock Client
  - [x] 6.1 Implement `llm_agent_battery/bedrock_client.py` with async `BedrockClient` class
    - Follow pattern from `evalweaver/providers/bedrock_claude_provider.py`
    - Lazy client initialization, credential validation via STS
    - Async `converse()` method using Converse API
    - Retry with exponential backoff (3 attempts) for retryable errors
    - Connection timeout 30s, read timeout 300s
    - Temperature 0.2, token usage tracking
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 4.4, 4.5, 4.6_

  - [ ]* 6.2 Write property test for retry behavior
    - **Property 10: Retry behavior depends on error classification**
    - **Validates: Requirements 4.4, 4.5**

- [x] 7. Implement LLM Analyzer Layer
  - [x] 7.1 Implement `llm_agent_battery/analyzers/base.py` with `BaseAnalyzer` and `AnalyzerRegistry`
    - Abstract base class with system_prompt(), focus_areas(), analyze_chunk() methods
    - Registry for built-in and custom analyzers
    - JSON response parsing with markdown extraction fallback
    - _Requirements: 4.1, 4.2, 4.7, 12.1, 12.3_

  - [x] 7.2 Implement built-in analyzer in `llm_agent_battery/analyzers/code_review_analyzer.py`
    - Default code review analyzer using Review_Profile system prompt
    - Produces Finding objects from LLM JSON responses
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 7.3 Write property test for JSON extraction from markdown
    - **Property 9: LLM response parsing extracts JSON from markdown**
    - **Validates: Requirements 4.7**

  - [ ]* 7.4 Write property test for custom analyzer integration
    - **Property 21: Custom analyzer findings merge into output**
    - **Validates: Requirements 12.2**

- [x] 8. Implement Review Profiles
  - [x] 8.1 Create `llm_agent_battery/profiles/` with built-in YAML profiles and loader
    - Profile files: single-agent.yaml, multi-agent.yaml, pipeline-sequential.yaml, reactive.yaml
    - Profile loader that validates YAML into ReviewProfile model
    - Auto-detection logic based on classified file patterns
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 8.2 Write property test for architecture auto-detection
    - **Property 12: Architecture auto-detection selects matching profile**
    - **Validates: Requirements 6.2**

- [x] 9. Implement Deterministic Heuristic Analyzers
  - [x] 9.1 Implement `llm_agent_battery/heuristics/` package with base class and analyzers
    - BaseHeuristicAnalyzer ABC with `analyze(files) -> list[Finding]`
    - MissingErrorHandlingAnalyzer: detects tool calls without try/except
    - UnguardedMutationAnalyzer: detects state mutations without guards
    - MissingConfirmationGateAnalyzer: detects destructive ops without confirmation
    - PromptInjectionAnalyzer: detects user input passed to prompt templates
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 9.2 Write property test for heuristic pattern detection
    - **Property 11: Heuristic detectors identify unguarded patterns**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5**

- [x] 10. Implement Finding Deduplicator and Ranker
  - [x] 10.1 Implement `llm_agent_battery/deduplicator.py` with `deduplicate_and_rank()` function
    - Deduplicate by (title, file_path, location) tuple
    - Cross-layer confirmation: mark LLM findings confirmed by heuristic layer
    - Rank by severity (CRITICAL > HIGH > MEDIUM > LOW) then category (logic_error > correctness > edge_case > design_flaw > other)
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 10.2 Write property test for deduplication correctness
    - **Property 14: Finding deduplication reduces duplicates**
    - **Validates: Requirements 7.4, 11.1**

  - [ ]* 10.3 Write property test for cross-layer confirmation
    - **Property 15: Cross-layer confirmation annotation**
    - **Validates: Requirements 11.3**

  - [ ]* 10.4 Write property test for ranking total order
    - **Property 16: Finding ranking is total order**
    - **Validates: Requirements 11.4, 7.2**

- [x] 11. Implement Report Generator
  - [x] 11.1 Implement `llm_agent_battery/reporter.py` with `generate_reports()` function
    - JSON output: all findings sorted by severity
    - Markdown output: severity badges, grouped by file
    - Summary section when findings > 200
    - _Requirements: 7.2, 7.3, 7.5_

- [x] 12. Checkpoint — All components ready
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Implement Pipeline Orchestrator
  - [x] 13.1 Implement `llm_agent_battery/pipeline.py` with async `run_pipeline()` function
    - Coordinates: scan → classify → chunk → heuristic analyze → LLM analyze → deduplicate → report
    - Semaphore-based concurrency control for LLM calls
    - Minimum inter-request delay enforcement
    - Fast mode skips LLM layer entirely
    - Progress display via Rich
    - Token usage aggregation
    - _Requirements: 5.1, 5.6, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 13.2 Write property test for fast mode zero LLM invocations
    - **Property 5: Fast mode produces zero LLM invocations**
    - **Validates: Requirements 2.5, 5.6, 8.4**

  - [ ]* 13.3 Write property test for concurrency control
    - **Property 17: Concurrency control limits in-flight requests**
    - **Validates: Requirements 10.1**

  - [ ]* 13.4 Write property test for inter-request delay
    - **Property 18: Minimum inter-request delay**
    - **Validates: Requirements 10.2**

  - [ ]* 13.5 Write property test for token usage accounting
    - **Property 19: Token usage accounting**
    - **Validates: Requirements 10.5**

- [x] 14. Implement CLI
  - [x] 14.1 Implement `llm_agent_battery/cli.py` with Typer app
    - `review` command: target dir, --profile, --fast, --threshold, --output-dir, --ci
    - `scan` command: target dir, --include, --exclude
    - Exit code logic: 1 if any finding >= threshold severity, else 0
    - CI mode: suppress Rich progress, output JSON only
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [ ]* 14.2 Write property test for exit code threshold logic
    - **Property 20: Exit code reflects threshold**
    - **Validates: Requirements 8.5, 8.8**

- [x] 15. Final checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)`
- The Bedrock client follows the pattern in `evalweaver/providers/bedrock_claude_provider.py`
- All async code uses asyncio with semaphore-based concurrency
