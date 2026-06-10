# Agent Battery

A deterministic, LLM-free CLI that audits AI agent repositories for safety gaps, missing evals, prompt/tool mismatches, and unsafe tool-call trajectories.

## Quick Start

```bash
# Install
pip install -e .

# Run a full audit
agentbattery audit path/to/agent/repo --generate-tests --report

# Scan only (discover and classify files)
agentbattery scan path/to/agent/repo

# Compile contract without detection
agentbattery compile-contract path/to/agent/repo

# Check a specific trace file
agentbattery check-trace trace.jsonl .agentbattery/contract.yaml

# Generate tests from existing findings
agentbattery generate-tests .agentbattery/contract.yaml .agentbattery/findings.yaml

# Generate reports from existing findings
agentbattery report .agentbattery/findings.yaml .agentbattery/contract.yaml
```

## CLI Options

```bash
agentbattery audit <target> [OPTIONS]

Options:
  --generate-tests    Generate missing test cases from findings
  --report            Generate Markdown and JSON reports
  --threshold TEXT    Severity threshold for exit code (CRITICAL|HIGH|MEDIUM|LOW) [default: HIGH]
  --ci                CI mode — suppress progress output, stable exit codes
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No findings at or above threshold |
| 1 | Findings detected at or above threshold |
| 2 | Internal error |

## Output Structure

After running `agentbattery audit`, outputs are written to `.agentbattery/` in the target repo:

```
.agentbattery/
├── contract.yaml          # Compiled agent contract
├── obligations.yaml       # Extracted obligations
├── findings.yaml          # All detected findings
├── repair_input.json      # Machine-readable repair input for CI/CD
├── generated_tests/       # Generated test YAML files
└── reports/
    ├── latest.md          # Human-readable Markdown report
    └── latest.json        # Machine-readable JSON report
```

## CI/CD Usage

```yaml
# .github/workflows/agentbattery.yml
name: Agent Safety Audit
on: [push, pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .
      - run: agentbattery audit . --generate-tests --report --ci --threshold HIGH
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agentbattery-audit
          path: .agentbattery/
```

## Running Tests

```bash
pip install -e .
python -m pytest tests/ -v
```

## What It Detects

Agent Battery identifies four types of gaps:

- **Policy Gap** — A dangerous tool has no associated obligation
- **Enforcement Gap** — An obligation exists but no runtime mechanism enforces it
- **Coverage Gap** — An obligation exists but no test/eval covers it
- **Trace Violation** — An actual execution trace violates the obligation

## Requirements

- Python 3.11+
- Dependencies: pydantic, typer, rich, pyyaml, jinja2
