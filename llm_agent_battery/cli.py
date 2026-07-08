"""CLI interface for llm-agent-battery using Typer.

Commands:
- review: Full analysis pipeline (scan → classify → chunk → analyze → report)
- scan: File discovery and classification only (no LLM analysis)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from llm_agent_battery.models import (
    ClassifyConfig,
    ConcurrencyConfig,
    InferenceConfig,
    PipelineConfig,
    ScanConfig,
    Severity,
)

app = typer.Typer(name="llm-agent-battery", help="LLM-powered agent code review tool.")


# Severity threshold ordering for exit code logic
_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
}


def _severity_meets_threshold(severity: Severity, threshold: Severity) -> bool:
    """Check if a finding's severity meets or exceeds the threshold."""
    return _SEVERITY_ORDER.get(severity, 99) <= _SEVERITY_ORDER.get(threshold, 99)


@app.command()
def review(
    target: Path = typer.Argument(
        ...,
        help="Target directory to analyze.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Review profile name or path to custom YAML profile.",
    ),
    fast: bool = typer.Option(
        False,
        "--fast",
        "-f",
        help="Skip LLM analysis, run only deterministic heuristics.",
    ),
    threshold: str = typer.Option(
        "high",
        "--threshold",
        "-t",
        help="Minimum severity for non-zero exit code (critical, high, medium, low).",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory for reports. Default: .agentbattery/ in target.",
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="CI mode: suppress Rich progress, output JSON only.",
    ),
    model_id: Optional[str] = typer.Option(
        None,
        "--model-id",
        help="Bedrock model ID to use for LLM analysis.",
    ),
) -> None:
    """Run full code review analysis on a target directory."""
    # Parse threshold severity
    try:
        threshold_severity = Severity(threshold.lower())
    except ValueError:
        console = Console(stderr=True)
        console.print(f"[red]Invalid threshold: '{threshold}'. Use: critical, high, medium, low[/red]")
        raise SystemExit(2)

    # Load profile if specified
    loaded_profile = None
    if profile:
        from llm_agent_battery.profiles import load_profile as _load_profile

        try:
            loaded_profile = _load_profile(profile)
        except FileNotFoundError as e:
            console = Console(stderr=True)
            console.print(f"[red]{e}[/red]")
            raise SystemExit(2)

    # Build inference config
    inference_config = InferenceConfig()
    if model_id:
        inference_config = InferenceConfig(model_id=model_id)

    # Build pipeline config
    pipeline_config = PipelineConfig(
        target_dir=target,
        scan_config=ScanConfig(),
        classify_config=ClassifyConfig(fast_mode=fast),
        inference_config=inference_config,
        concurrency_config=ConcurrencyConfig(),
        profile=loaded_profile,
        fast_mode=fast,
        threshold=threshold_severity,
        output_dir=output_dir,
        ci_mode=ci,
    )

    # Run the pipeline
    from llm_agent_battery.pipeline import run_pipeline

    try:
        result = asyncio.run(run_pipeline(pipeline_config))
    except FileNotFoundError as e:
        console = Console(stderr=True)
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(2)
    except RuntimeError as e:
        if "credentials" in str(e).lower() or "aws" in str(e).lower():
            console = Console(stderr=True)
            console.print(f"[red]{e}[/red]")
            raise SystemExit(2)
        raise

    # CI mode: output JSON to stdout
    if ci:
        findings_data = [f.model_dump(mode="json") for f in result.findings]
        print(json.dumps(findings_data, indent=2, default=str))

    # Exit code logic: 1 if any finding >= threshold severity
    has_findings_above_threshold = any(
        _severity_meets_threshold(f.severity, threshold_severity)
        for f in result.findings
    )

    raise SystemExit(1 if has_findings_above_threshold else 0)


@app.command()
def scan(
    target: Path = typer.Argument(
        ...,
        help="Target directory to scan.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    include: Optional[list[str]] = typer.Option(
        None,
        "--include",
        "-i",
        help="Include glob patterns (can specify multiple).",
    ),
    exclude: Optional[list[str]] = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Exclude glob patterns (can specify multiple).",
    ),
) -> None:
    """Scan a target directory for source files and classify them."""
    from llm_agent_battery.classifier import classify_files
    from llm_agent_battery.scanner import scan as run_scan

    console = Console()

    # Build scan config
    scan_config = ScanConfig()
    if include:
        scan_config = ScanConfig(include_globs=include, exclude_globs=scan_config.exclude_globs)
    if exclude:
        scan_config = ScanConfig(include_globs=scan_config.include_globs, exclude_globs=exclude)

    # Run scan
    try:
        scan_result = run_scan(target, scan_config)
    except (FileNotFoundError, NotADirectoryError) as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(2)

    console.print(f"Found {scan_result.total_count} files in {scan_result.elapsed_seconds:.2f}s")

    if scan_result.warnings:
        console.print(f"\n[yellow]Warnings ({len(scan_result.warnings)}):[/yellow]")
        for w in scan_result.warnings:
            console.print(f"  ⚠ {w.file_path}: {w.reason}")

    # Classify files
    classified = classify_files(scan_result.files)

    # Display results grouped by category
    from collections import Counter

    categories = Counter(f.primary_category.value for f in classified)
    console.print("\n[bold]File Classification:[/bold]")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        console.print(f"  {cat}: {count}")

    # Output JSON of classified files
    console.print(f"\n[dim]Total: {len(classified)} files classified[/dim]")

    raise SystemExit(0)


if __name__ == "__main__":
    app()
