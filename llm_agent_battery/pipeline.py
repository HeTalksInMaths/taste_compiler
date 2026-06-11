"""Pipeline orchestrator — coordinates the full scan → analyze → report flow.

Manages concurrency for LLM calls via semaphore, enforces minimum inter-request
delay, supports fast mode (heuristic-only), and displays progress via Rich.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from rich.console import Console

from llm_agent_battery.models import (
    CodeChunk,
    Finding,
    PipelineConfig,
    PipelineResult,
    TokenUsage,
)

logger = logging.getLogger(__name__)


async def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Orchestrate the full scan → classify → chunk → analyze → report flow.

    Steps:
    1. Scan target directory for source files
    2. Classify files by semantic role
    3. Chunk files at AST boundaries
    4. Run deterministic heuristic analyzers
    5. Run LLM analysis (unless fast mode)
    6. Deduplicate and rank findings
    7. Generate reports

    Args:
        config: PipelineConfig with all sub-configurations.

    Returns:
        PipelineResult with findings, metadata, and token usage.
    """
    from llm_agent_battery.analyzers.base import AnalyzerRegistry
    from llm_agent_battery.analyzers.code_review_analyzer import CodeReviewAnalyzer
    from llm_agent_battery.bedrock_client import BedrockClient
    from llm_agent_battery.chunker import chunk_files
    from llm_agent_battery.classifier import classify_files
    from llm_agent_battery.deduplicator import deduplicate_and_rank
    from llm_agent_battery.profiles import detect_architecture, load_profile
    from llm_agent_battery.reporter import generate_reports
    from llm_agent_battery.scanner import scan

    console = Console(quiet=config.ci_mode)
    start_time = time.time()

    # --- Step 1: Scan ---
    with _status(console, "Scanning files..."):
        scan_result = scan(config.target_dir, config.scan_config)
    console.print(f"  Found {scan_result.total_count} files in {scan_result.elapsed_seconds:.2f}s")

    if scan_result.total_count == 0:
        elapsed = time.time() - start_time
        return PipelineResult(
            findings=[],
            scan_result=scan_result,
            classified_files=[],
            chunks_reviewed=0,
            token_usage=TokenUsage(),
            elapsed_seconds=elapsed,
        )

    # --- Step 2: Classify ---
    with _status(console, "Classifying files..."):
        classify_cfg = config.classify_config.model_copy(
            update={"fast_mode": config.fast_mode}
        )
        classified_files = classify_files(scan_result.files, classify_cfg)
    console.print(f"  Classified {len(classified_files)} files")

    # --- Step 3: Chunk ---
    with _status(console, "Chunking files..."):
        chunks = chunk_files(classified_files, config.chunk_config)
    console.print(f"  Produced {len(chunks)} chunks")

    # --- Step 4: Heuristic Analysis ---
    with _status(console, "Running heuristic analyzers..."):
        heuristic_findings = _run_heuristics(classified_files)
    console.print(f"  Heuristic findings: {len(heuristic_findings)}")

    # --- Step 5: LLM Analysis ---
    llm_findings: list[Finding] = []
    token_usage = TokenUsage()

    if not config.fast_mode and chunks:
        # Determine profile
        profile = config.profile
        if profile is None:
            detected_style = detect_architecture(classified_files)
            try:
                profile = load_profile(detected_style.value)
            except FileNotFoundError:
                profile = None
            if profile:
                console.print(f"  Auto-detected architecture: {detected_style.value}")

        # Set up Bedrock client and analyzer registry
        client = BedrockClient(
            config=config.inference_config,
            concurrency_config=config.concurrency_config,
        )
        registry = AnalyzerRegistry()
        registry.register(CodeReviewAnalyzer())

        # Run LLM analysis with concurrency control
        llm_findings = await _run_llm_analysis(
            chunks=chunks,
            client=client,
            registry=registry,
            profile=profile,
            config=config,
            console=console,
        )

        # --- Step 5b: Agent Dimension Analysis ---
        # If agent artifacts are detected (prompts, tools, orchestration),
        # run the 6-dimension agent-specific analyzers against aggregated context
        agent_dimension_findings = await _run_agent_dimension_analysis(
            classified_files=classified_files,
            client=client,
            config=config,
            console=console,
        )
        llm_findings.extend(agent_dimension_findings)

        token_usage = client.total_usage
        console.print(
            f"  LLM findings: {len(llm_findings)} "
            f"(tokens: {token_usage.total_tokens})"
        )

    # --- Step 6: Deduplicate and Rank ---
    with _status(console, "Deduplicating and ranking findings..."):
        all_findings = heuristic_findings + llm_findings
        ranked_findings = deduplicate_and_rank(all_findings)
    console.print(f"  Final findings: {len(ranked_findings)}")

    # --- Step 7: Generate Reports ---
    output_dir = config.output_dir or (config.target_dir / ".agentbattery")
    with _status(console, "Generating reports..."):
        generate_reports(ranked_findings, output_dir, scan_result)
    console.print(f"  Reports written to {output_dir}")

    elapsed = time.time() - start_time
    console.print(f"\n[bold]Done in {elapsed:.2f}s[/bold]")

    return PipelineResult(
        findings=ranked_findings,
        scan_result=scan_result,
        classified_files=classified_files,
        chunks_reviewed=len(chunks),
        token_usage=token_usage,
        elapsed_seconds=elapsed,
    )


def _run_heuristics(classified_files: list) -> list[Finding]:
    """Run the full deterministic heuristic battery."""
    from llm_agent_battery.heuristics import ALL_HEURISTIC_ANALYZERS

    findings: list[Finding] = []
    for analyzer_cls in ALL_HEURISTIC_ANALYZERS:
        try:
            findings.extend(analyzer_cls().analyze(classified_files))
        except Exception:
            logger.exception("Heuristic analyzer %s failed", analyzer_cls.__name__)
    return findings


async def _run_llm_analysis(
    chunks: list[CodeChunk],
    client,
    registry,
    profile,
    config: PipelineConfig,
    console: Console,
) -> list[Finding]:
    """Run LLM analysis on all chunks with semaphore-based concurrency control.

    Enforces:
    - max_concurrent simultaneous LLM calls via asyncio.Semaphore
    - min_delay_seconds between consecutive request starts
    """
    semaphore = asyncio.Semaphore(config.concurrency_config.max_concurrent)
    min_delay = config.concurrency_config.min_delay_seconds
    findings: list[Finding] = []
    lock = asyncio.Lock()
    last_request_time: list[float] = [0.0]  # mutable container for closure

    total = len(chunks)
    completed = [0]

    async def process_chunk(chunk: CodeChunk) -> list[Finding]:
        """Process a single chunk through all registered analyzers."""
        chunk_findings: list[Finding] = []

        async with semaphore:
            # Enforce minimum inter-request delay
            async with lock:
                now = asyncio.get_event_loop().time()
                elapsed_since_last = now - last_request_time[0]
                if elapsed_since_last < min_delay:
                    await asyncio.sleep(min_delay - elapsed_since_last)
                last_request_time[0] = asyncio.get_event_loop().time()

            # Run all analyzers on this chunk
            for analyzer in registry.get_all():
                result = await analyzer.analyze_chunk(
                    chunk=chunk,
                    context="",
                    client=client,
                    profile=profile,
                )
                chunk_findings.extend(result)

            completed[0] += 1
            if not config.ci_mode:
                console.print(
                    f"  [{completed[0]}/{total}] Analyzed: {chunk.file_path} / {chunk.chunk_name}",
                    highlight=False,
                )

        return chunk_findings

    # Process all chunks concurrently (bounded by semaphore)
    tasks = [process_chunk(chunk) for chunk in chunks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.warning("Chunk analysis failed: %s", result)
        elif isinstance(result, list):
            findings.extend(result)

    return findings


class _status:
    """Context manager for Rich status display (no-op in CI mode)."""

    def __init__(self, console: Console, message: str):
        self._console = console
        self._message = message
        self._status = None

    def __enter__(self):
        if not self._console.quiet:
            self._status = self._console.status(self._message)
            self._status.__enter__()
        return self

    def __exit__(self, *args):
        if self._status is not None:
            self._status.__exit__(*args)


async def _run_agent_dimension_analysis(
    classified_files: list,
    client,
    config: PipelineConfig,
    console: Console,
) -> list[Finding]:
    """Run the 6 agent-specific dimension analyzers.

    Instead of chunk-by-chunk, these analyzers get aggregated context:
    all prompts, tool definitions, and orchestration code concatenated together
    so they can reason about the agent system holistically.
    """
    from llm_agent_battery.analyzers.agent_dimensions_analyzer import ALL_DIMENSION_ANALYZERS
    from llm_agent_battery.models import FileCategory

    # Collect agent-relevant files by category
    prompts = [f for f in classified_files if f.primary_category == FileCategory.PROMPT_TEMPLATE]
    tools = [f for f in classified_files if f.primary_category == FileCategory.TOOL_DEFINITION]
    orchestration = [f for f in classified_files if f.primary_category == FileCategory.ORCHESTRATION]
    agent_logic = [f for f in classified_files if f.primary_category == FileCategory.AGENT_LOGIC]

    # Only run dimension analysis if we have agent-relevant artifacts
    agent_files = prompts + tools + orchestration + agent_logic
    if not agent_files:
        console.print("  No agent artifacts detected, skipping dimension analysis")
        return []

    console.print(
        f"  Agent artifacts: {len(prompts)} prompts, {len(tools)} tools, "
        f"{len(orchestration)} orchestration, {len(agent_logic)} agent logic"
    )

    # Build aggregated context for dimension analyzers
    context_parts = []
    for f in agent_files:
        try:
            content = f.path.read_text(encoding="utf-8", errors="ignore")[:20000]
            context_parts.append(f"--- {f.relative_path} [{f.primary_category.value}] ---\n{content}")
        except OSError:
            continue

    aggregated_context = "\n\n".join(context_parts)

    # Truncate to ~40K chars to fit in context window
    if len(aggregated_context) > 40000:
        aggregated_context = aggregated_context[:40000] + "\n\n[... truncated ...]"

    # Create a synthetic chunk representing the whole agent system
    agent_chunk = CodeChunk(
        file_path="[agent-system-aggregate]",
        chunk_name="full-agent-context",
        content=aggregated_context,
        functions=[],
        preamble="",
        start_line=0,
        end_line=0,
    )

    # Run each dimension analyzer sequentially (they're independent but
    # each gets the full context, so we space them out)
    findings: list[Finding] = []
    for i, AnalyzerClass in enumerate(ALL_DIMENSION_ANALYZERS):
        analyzer = AnalyzerClass()
        dimension_name = analyzer.focus_areas()[0] if analyzer.focus_areas() else "unknown"
        if not config.ci_mode:
            console.print(f"  [{i+1}/6] Dimension: {dimension_name}...", highlight=False)

        result = await analyzer.analyze_chunk(
            chunk=agent_chunk,
            context="Full agent system context including all prompts, tools, and orchestration code.",
            client=client,
        )
        findings.extend(result)

        # Delay between dimension calls
        await asyncio.sleep(config.concurrency_config.min_delay_seconds)

    console.print(f"  Agent dimension findings: {len(findings)}")
    return findings
