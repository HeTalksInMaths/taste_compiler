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

# Evolutionary loop: scorer population vs adversarial pairs across generations
python -m evalweaver evolve --config configs/persuasive.yaml --generations 5 --population 12

# Scale experiment: many seeds × goals, aggregated stats
python -m evalweaver evolve-batch --config configs/persuasive.yaml --seeds 40 --goals persuasive trustworthy --workers 4

# Claude-as-the-model (no AWS needed): stepped run + file-exchange proposals
python -m evalweaver evolve --config configs/persuasive.yaml --provider claude --step
# ... fill claude_exchange/scorers_genNN.json + pairs_genNN.json, then:
python -m evalweaver evolve --config configs/persuasive.yaml --provider claude --resume --step
```

## Evolutionary loop (`evolve`)

`evolve` closes the discover→attack→repair cycle into a multi-generation
evolutionary algorithm:

- **Scorers are interpretable genomes** — weighted compositions of the NLP
  probes rendered to plain Python scoring functions, evolved by mutation,
  crossover, and gap-biased immigrants.
- **Adversarial pairs exploit coverage gaps**: each generation, candidate
  pairs are synthesized from social media post anchors and the ones the
  current Pareto frontier separates *worst* are added to the suite (a slice
  goes to the frozen heldout set).
- **Dynamic goal keyword**: `--goal trustworthy` (or any config goal)
  switches the subjective target without editing YAML.
- Fully deterministic offline; `--use-exa-search` grounds anchors in real
  LinkedIn/Twitter posts (needs `EXA_API_KEY`) and `--provider bedrock`
  adds live LLM scorer mutations — both degrade gracefully to the
  deterministic engine.

Artifacts land in `$EVALWEAVER_OUTPUT_DIR/evolve_<goal>_seed<seed>/`:
per-generation populations, Pareto frontiers, failure packets, new
adversarial pairs, plus `evolve_history.json` and `evolve_best_scorers.json`.

Runs are checkpointed (`evolve_state.json`): `--step` executes one
generation per invocation and `--resume` continues exactly where it left
off (stepped histories are byte-identical to single-process runs).

**Providers.** `--provider bedrock` proposes scorer mutations and
adversarial pairs via structured tool calls. `--provider claude` writes
proposal *requests* into an exchange directory between stepped
generations and reads back responses — letting an interactive Claude Code
session (see `.claude/skills/claude-scorer-evolution/`) or a human play
the model with no AWS credentials. All proposals pass the same
validation: scorers must execute, stay in range, and separate validation
pairs; pairs must pass source policy and survive hardest-first
frontier-margin selection against template candidates.

**Scale experiments.** `evolve-batch` sweeps seeds × goals (optionally in
parallel with `--workers`) and writes `evolve_batch_summary.json` with
improvement rate, evolved-winner rate, gain distribution, and winner
lineage histogram.

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

## AWS Setup (optional)

For using Bedrock Claude instead of mocked outputs:

```bash
# Install AWS dependencies
pip install -e ".[aws]"

# Configure credentials
aws configure sso  # or: aws configure --profile next-sandbox
export AWS_PROFILE=next-sandbox
export AWS_REGION=us-east-1

# Validate
python scripts/check_aws.py

# Run with Bedrock
python -m evalweaver run --config configs/persuasive.yaml --provider bedrock
```

See [docs/aws-setup.md](docs/aws-setup.md) for full setup instructions.

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
