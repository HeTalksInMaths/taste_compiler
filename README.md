# EvalWeaver v5.1

Automated pipeline for discovering, validating, and evolving quality scorers for subjective text improvement goals.

Given a goal like "make this more persuasive", EvalWeaver:
1. Researches linguistic/psychological features of the goal
2. Builds a structured taste map (rewards, punishes, preserves)
3. Maps taste concepts to measurable NLP probes
4. Generates scorer hypotheses and implements them as Python functions
5. Creates evaluation pairs (positive/negative rewrites) with source-policy enforcement
6. Evaluates scorers, computes Pareto frontier
7. Analyzes failures, evolves scorers via repair loop
8. Selects the best candidate rewrite via ensemble scoring

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run pipeline with default config
python -m evalweaver run --config configs/persuasive.yaml

# Run tests
pytest
```

## CLI

```bash
# Single run
python -m evalweaver run --config configs/persuasive.yaml

# Experiment (multiple seeds)
python -m evalweaver experiment --config configs/persuasive.yaml --seeds 5

# Batch (multiple topics)
python -m evalweaver batch --configs configs/*.yaml
```

## Configuration

Configs are YAML files in `configs/`. Example:

```yaml
goal: persuasive
raw_text: "EvalWeaver lets anyone create, use, and monetize AI improvers..."
seed: 7
n_rounds: 2
n_init_scorers: 8
n_repair_scorers: 6
n_init_pairs: 24
n_repair_pairs: 12
```

## Project Structure

```
evalweaver/
├── config.py          # Configuration loading and defaults
├── policy.py          # Source policy violations and continuity
├── probes.py          # NLP probe functions
├── runner.py          # Namespace-isolated scorer execution
├── scorers.py         # Scorer hypotheses, code, validation
├── pairs.py           # Pair generation and splitting
├── evaluation.py      # Scorer evaluation on pair suites
├── pareto.py          # Eligibility filter and Pareto frontier
├── failure_packet.py  # Failure analysis and mutation instructions
├── repair.py          # Scorer evolution and repair-improvement metrics
├── candidates.py      # Candidate scoring and selection
├── criteria.py        # Computed spec criteria (self-validation)
├── artifacts.py       # Logging, JSON persistence, ZIP archive
└── providers/
    ├── base.py                    # AgentProvider protocol
    ├── mock_provider.py           # Hardcoded/seeded outputs (default)
    └── bedrock_claude_provider.py # AWS Bedrock Claude (future)
```

## Output

All artifacts are written as JSON to the configured output directory:
- `EVALWEAVER_OUTPUT_DIR` env var (primary)
- `./ew_v51_outputs` (fallback)
- System temp directory (final fallback)

A ZIP archive is produced containing all JSON artifacts from the run.
