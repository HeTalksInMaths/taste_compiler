"""CLI interface for agentbattery - Typer commands for auditing agent repos."""

from __future__ import annotations

import json
import sys
import logging
from pathlib import Path
from typing import Optional

import typer
import yaml

from agentbattery.models import (
    AgentContract,
    CoverageResult,
    FileCategory,
    Finding,
    GeneratedTest,
    RiskLevel,
)

app = typer.Typer(
    name="agentbattery",
    help="Audit AI agent repositories for safety and compliance gaps.",
)

logger = logging.getLogger(__name__)

# Severity ordering for threshold comparison
_SEVERITY_ORDER: dict[str, int] = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


def _findings_above_threshold(findings: list[Finding], threshold: str) -> list[Finding]:
    """Filter findings at or above the given threshold severity."""
    threshold_level = _SEVERITY_ORDER.get(threshold.upper(), 1)
    return [
        f for f in findings
        if _SEVERITY_ORDER.get(f.severity.value, 99) <= threshold_level
    ]


def exit_code_for_threshold(findings: list[Finding], threshold: str) -> int:
    """Determine exit code based on findings and threshold.

    Returns:
        0: No findings at or above threshold.
        1: Findings at or above threshold detected.
    """
    above = _findings_above_threshold(findings, threshold)
    return 1 if above else 0


def write_findings(findings: list[Finding], out_dir: Path) -> Path:
    """Write findings.yaml to the output directory.

    Args:
        findings: List of Finding objects.
        out_dir: Output directory (e.g., .agentbattery/).

    Returns:
        Path to the written findings.yaml file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    findings_data = [f.model_dump(mode="json") for f in findings]
    findings_path = out_dir / "findings.yaml"
    with open(findings_path, "w") as f:
        yaml.dump(findings_data, f, default_flow_style=False, sort_keys=False)
    return findings_path


def _run_scan(target: Path, include: list[str] | None = None, exclude: list[str] | None = None):
    """Run scanner + file classifier on target."""
    from agentbattery.scanner import scan
    from agentbattery.file_classifier import classify_files

    scan_result = scan(target, include_globs=include, exclude_globs=exclude)
    classified = classify_files(scan_result.files)
    return scan_result, classified


def _run_extraction(classified):
    """Run prompt and tool extraction on classified files."""
    from agentbattery.prompt_extractor import extract_prompts
    from agentbattery.tool_extractor import extract_tools
    from agentbattery.obligation_extractor import extract_obligations
    from agentbattery.risk_classifier import classify_tools

    prompt_files = [f for f in classified if f.primary_category == FileCategory.PROMPT]
    prompts = extract_prompts(prompt_files)

    tool_files = [f for f in classified if f.primary_category in (FileCategory.TOOL_SOURCE, FileCategory.TOOL_SCHEMA)]
    tools = extract_tools(tool_files)
    tools = classify_tools(tools)

    obligations = extract_obligations(prompts, tools)
    return prompts, tools, obligations


def run_audit(
    target: Path,
    generate_tests_flag: bool,
    report_flag: bool,
    ci: bool,
    threshold: str,
) -> int:
    """Run the full audit pipeline.

    Returns exit code: 0 (no findings above threshold), 1 (findings above threshold).
    """
    from agentbattery.scanner import scan
    from agentbattery.file_classifier import classify_files
    from agentbattery.prompt_extractor import extract_prompts
    from agentbattery.tool_extractor import extract_tools
    from agentbattery.obligation_extractor import extract_obligations
    from agentbattery.risk_classifier import classify_tools
    from agentbattery.contract_compiler import compile_contract, serialize_contract
    from agentbattery.mismatch_detector import detect_mismatches
    from agentbattery.trace_loader import load_traces
    from agentbattery.trace_checker import check_traces
    from agentbattery.rubric_auditor import audit_architecture
    from agentbattery.coverage_analyzer import analyze_coverage, get_coverage_findings
    from agentbattery.test_generator import generate_tests as generate_tests_func, write_generated_tests
    from agentbattery.report import generate_report, emit_repair_input

    def _echo(msg: str) -> None:
        if not ci:
            typer.echo(msg)

    # 1. Scan repo
    _echo(f"Scanning {target}...")
    scan_result = scan(target)
    _echo(f"  Found {scan_result.total_count} files in {scan_result.elapsed_seconds:.2f}s")

    # 2. Classify files
    _echo("Classifying files...")
    classified = classify_files(scan_result.files)

    # 3. Extract prompts from PROMPT files
    _echo("Extracting prompts...")
    prompt_files = [f for f in classified if f.primary_category == FileCategory.PROMPT]
    prompts = extract_prompts(prompt_files)
    _echo(f"  Extracted {len(prompts)} prompt artifact(s)")

    # 4. Extract tools from TOOL_SOURCE and TOOL_SCHEMA files
    _echo("Extracting tools...")
    tool_files = [f for f in classified if f.primary_category in (FileCategory.TOOL_SOURCE, FileCategory.TOOL_SCHEMA)]
    tools = extract_tools(tool_files)
    _echo(f"  Extracted {len(tools)} tool artifact(s)")

    # 5. Classify tool risks
    _echo("Classifying tool risks...")
    tools = classify_tools(tools)

    # 6. Extract obligations from prompts and tools
    _echo("Extracting obligations...")
    obligations = extract_obligations(prompts, tools)
    _echo(f"  Extracted {len(obligations)} obligation(s)")

    # 7. Build risk levels dict
    risk_levels = {t.name: t.side_effect_level for t in tools}

    # 8. Compile contract
    _echo("Compiling contract...")
    contract = compile_contract(prompts, tools, obligations, risk_levels)

    # 9. Detect mismatches
    _echo("Detecting mismatches...")
    findings = detect_mismatches(contract, classified)
    _echo(f"  Found {len(findings)} mismatch finding(s)")

    # 10. Load traces
    _echo("Loading traces...")
    trace_files = [f for f in classified if f.primary_category == FileCategory.TRACE]
    traces = load_traces(trace_files)
    _echo(f"  Loaded {len(traces)} trace(s)")

    # 11. Check traces
    _echo("Checking traces...")
    trace_findings = check_traces(traces, contract)
    findings.extend(trace_findings)
    _echo(f"  Found {len(trace_findings)} trace violation(s)")

    # 12. Run rubric auditor
    _echo("Auditing architecture...")
    contract, arch_findings = audit_architecture(contract, classified, prompts)
    findings.extend(arch_findings)
    _echo(f"  Found {len(arch_findings)} architecture finding(s)")

    # 13. Analyze coverage
    _echo("Analyzing coverage...")
    eval_files = [f for f in classified if f.primary_category == FileCategory.EVAL]
    coverage = analyze_coverage(contract, eval_files)
    coverage_findings = get_coverage_findings(contract, coverage)
    findings.extend(coverage_findings)
    _echo(f"  Coverage: {coverage.covered_count} covered, {coverage.partial_count} partial, {coverage.missing_count} missing")

    # 14. Generate tests (if enabled)
    generated: list[GeneratedTest] = []
    if generate_tests_flag:
        _echo("Generating tests...")
        generated = generate_tests_func(findings, contract)
        _echo(f"  Generated {len(generated)} test(s)")

    # 15. Write outputs to .agentbattery/ in target
    out_dir = target / ".agentbattery"
    _echo(f"Writing outputs to {out_dir}/...")

    serialize_contract(contract, out_dir)
    write_findings(findings, out_dir)

    if generate_tests_flag:
        write_generated_tests(generated, out_dir / "generated_tests")

    if report_flag:
        generate_report(findings, coverage, generated, contract, out_dir)

    emit_repair_input(findings, generated, contract, out_dir)

    # 16. Exit code based on threshold
    code = exit_code_for_threshold(findings, threshold)

    total = len(findings)
    above = len(_findings_above_threshold(findings, threshold))
    _echo(f"\nAudit complete: {total} total finding(s), {above} at/above {threshold} threshold.")
    if code == 0:
        _echo("PASS — no findings at or above threshold.")
    else:
        _echo(f"FAIL — {above} finding(s) at or above {threshold} threshold.")

    return code


@app.command()
def scan(
    target: Path = typer.Argument(..., help="Target repository path to scan"),
    include: Optional[list[str]] = typer.Option(None, help="Include glob patterns"),
    exclude: Optional[list[str]] = typer.Option(None, help="Exclude glob patterns"),
) -> None:
    """Scan a target directory and classify discovered files."""
    from agentbattery.scanner import scan as run_scanner
    from agentbattery.file_classifier import classify_files

    try:
        scan_result = run_scanner(target, include_globs=include, exclude_globs=exclude)
        classified = classify_files(scan_result.files)

        typer.echo(f"Scanned {scan_result.total_count} files in {scan_result.elapsed_seconds:.2f}s\n")

        # Group by category
        by_category: dict[str, list[str]] = {}
        for f in classified:
            cat = f.primary_category.value
            by_category.setdefault(cat, []).append(f.relative_path)

        for cat, files in sorted(by_category.items()):
            typer.echo(f"[{cat}] ({len(files)} files)")
            for fp in sorted(files):
                typer.echo(f"  {fp}")
            typer.echo("")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command(name="compile-contract")
def compile_contract_cmd(
    target: Path = typer.Argument(..., help="Target repository path"),
) -> None:
    """Scan, extract, and compile the agent contract."""
    from agentbattery.scanner import scan as run_scanner
    from agentbattery.file_classifier import classify_files
    from agentbattery.prompt_extractor import extract_prompts
    from agentbattery.tool_extractor import extract_tools
    from agentbattery.obligation_extractor import extract_obligations
    from agentbattery.risk_classifier import classify_tools
    from agentbattery.contract_compiler import compile_contract, serialize_contract

    try:
        scan_result = run_scanner(target)
        classified = classify_files(scan_result.files)

        prompt_files = [f for f in classified if f.primary_category == FileCategory.PROMPT]
        prompts = extract_prompts(prompt_files)

        tool_files = [f for f in classified if f.primary_category in (FileCategory.TOOL_SOURCE, FileCategory.TOOL_SCHEMA)]
        tools = extract_tools(tool_files)
        tools = classify_tools(tools)

        obligations = extract_obligations(prompts, tools)
        risk_levels = {t.name: t.side_effect_level for t in tools}

        contract = compile_contract(prompts, tools, obligations, risk_levels)

        out_dir = target / ".agentbattery"
        serialize_contract(contract, out_dir)
        write_findings([], out_dir)  # Empty findings for compile-only

        typer.echo(f"Contract compiled: {len(prompts)} prompts, {len(tools)} tools, {len(obligations)} obligations")
        typer.echo(f"Output written to {out_dir}/")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command()
def audit(
    target: Path = typer.Argument(..., help="Target repository path"),
    generate_tests: bool = typer.Option(False, "--generate-tests", help="Generate missing tests"),
    report: bool = typer.Option(False, "--report", help="Generate reports"),
    threshold: str = typer.Option("HIGH", "--threshold", help="Finding severity threshold"),
    ci: bool = typer.Option(False, "--ci", help="CI mode - suppress progress output"),
) -> None:
    """Run the full audit pipeline."""
    try:
        code = run_audit(target, generate_tests, report, ci, threshold)
        raise typer.Exit(code=code)
    except typer.Exit:
        raise
    except Exception as e:
        if not ci:
            typer.echo(f"Error: {e}", err=True)
        logger.exception("Internal error during audit")
        raise typer.Exit(code=2)


@app.command(name="check-trace")
def check_trace(
    trace_file: Path = typer.Argument(..., help="Path to trace file"),
    contract_file: Path = typer.Argument(..., help="Path to contract YAML file"),
) -> None:
    """Check a trace file against a compiled contract."""
    from agentbattery.trace_checker import check_traces
    from agentbattery.models import AgentTrace, ClassifiedFile, TraceStep

    try:
        # Load contract from YAML
        with open(contract_file) as f:
            contract_data = yaml.safe_load(f)
        contract = AgentContract.model_validate(contract_data)

        # Load trace file
        from agentbattery.trace_loader import load_traces
        from agentbattery.file_classifier import classify_file
        from agentbattery.models import DiscoveredFile

        discovered = DiscoveredFile(
            path=trace_file,
            relative_path=str(trace_file),
            size_bytes=trace_file.stat().st_size,
        )
        classified = classify_file(discovered)
        traces = load_traces([classified])

        if not traces:
            typer.echo("No valid trace steps found in the file.")
            raise typer.Exit(code=0)

        # Check traces against contract
        findings = check_traces(traces, contract)

        if findings:
            typer.echo(f"Found {len(findings)} trace violation(s):\n")
            for f in findings:
                typer.echo(f"  [{f.severity.value}] {f.title}")
                typer.echo(f"    {f.description}\n")
            raise typer.Exit(code=1)
        else:
            typer.echo("No trace violations detected.")
            raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command(name="generate-tests")
def generate_tests_cmd(
    contract_file: Path = typer.Argument(..., help="Path to contract YAML file"),
    findings_file: Path = typer.Argument(..., help="Path to findings YAML file"),
) -> None:
    """Generate tests from an existing contract and findings."""
    from agentbattery.test_generator import generate_tests as gen_tests, write_generated_tests

    try:
        # Load contract
        with open(contract_file) as f:
            contract_data = yaml.safe_load(f)
        contract = AgentContract.model_validate(contract_data)

        # Load findings
        with open(findings_file) as f:
            findings_data = yaml.safe_load(f)

        findings = [Finding.model_validate(fd) for fd in (findings_data or [])]

        # Generate tests
        generated = gen_tests(findings, contract)

        # Write to output directory (same parent as findings file)
        out_dir = findings_file.parent / "generated_tests"
        written = write_generated_tests(generated, out_dir)

        typer.echo(f"Generated {len(generated)} test(s), written to {out_dir}/")
        for path in written:
            typer.echo(f"  {path.name}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)


@app.command()
def report(
    findings_file: Path = typer.Argument(..., help="Path to findings YAML file"),
    contract_file: Path = typer.Argument(..., help="Path to contract YAML file"),
) -> None:
    """Generate reports from existing findings data."""
    from agentbattery.report import generate_report as gen_report

    try:
        # Load contract
        with open(contract_file) as f:
            contract_data = yaml.safe_load(f)
        contract = AgentContract.model_validate(contract_data)

        # Load findings
        with open(findings_file) as f:
            findings_data = yaml.safe_load(f)
        findings = [Finding.model_validate(fd) for fd in (findings_data or [])]

        # Generate report with empty coverage and no generated tests
        coverage = CoverageResult(obligations=[], covered_count=0, partial_count=0, missing_count=0)
        out_dir = findings_file.parent
        md_path, json_path = gen_report(findings, coverage, [], contract, out_dir)

        typer.echo(f"Reports generated:")
        typer.echo(f"  Markdown: {md_path}")
        typer.echo(f"  JSON: {json_path}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
