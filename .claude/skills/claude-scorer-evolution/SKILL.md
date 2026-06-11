---
name: claude-scorer-evolution
description: Act as the LLM mutation engine for the EvalWeaver evolutionary scorer loop, replacing the Bedrock calls. Use when the user wants to run `evalweaver evolve` with Claude proposing scorers/adversarial pairs (no AWS/Bedrock credentials needed), e.g. "run the evolution with you as the model", "claude-provider evolve", "LLM-guided scorer evolution offline".
---

# Claude as the scorer-evolution LLM

You play the role the Bedrock model would play in the evolutionary loop:
each generation you read a failure-analysis context and write scorer and
adversarial-pair proposals. The engine validates everything you write, so
you cannot corrupt a run — invalid proposals are dropped with a warning.

## Workflow

1. **Start the run** (one generation per invocation):

   ```bash
   EVALWEAVER_OUTPUT_DIR=<outdir> python3 -m evalweaver evolve \
     --config configs/persuasive.yaml --provider claude --step \
     [--goal <keyword>] [--generations N] [--population N]
   ```

   The exchange directory defaults to
   `<outdir>/evolve_<goal>_seed<seed>/claude_exchange/`.

2. **Read the request** `request_genNN.json` from the exchange directory.
   Focus on:
   - `context.coverage_gaps` — pair types the Pareto frontier fails on
   - `context.frontier_scorers[*].pair_type_accuracy` and `code` — what
     the best scorers already do and where their gaps are
   - `context.failed_visible_pairs` — concrete examples they get wrong
   - `context.probe_registry` — the probes you may call, with semantics
   - `context.mutation_instructions` — accumulated, non-repeating hints

3. **Write your proposals** (paths are given in `respond_with`):
   - `scorers_genNN.json`: `{"scorers": [{"hypothesis", "lineage", "code"}]}`
     — write `n_scorers_wanted` scorers (default 3).
   - `pairs_genNN.json`: `{"pairs": [{"anchor", "positive", "negative",
     "pair_type", "label_contract", "intended_trap"}]}` — optional but
     valuable; write up to `n_pairs_wanted`.

4. **Advance one generation**: rerun the command from step 1 with
   `--resume --step` added. Watch the log: rejected proposals print a
   warning with the reason; accepted ones appear with `llm_` lineage.

5. **Repeat** steps 2–4 until the CLI prints "Evolution complete", then
   read `evolve_best_scorers.json` and `evolve_history.json` and report:
   best fitness trajectory, whether an `llm_*`-lineage scorer won or made
   the Pareto frontier, and the winning hypothesis.

## Scorer contract (violations are auto-rejected)

```python
def scorer(text, anchor, params):
    # return float in [0.0, 1.0]; wrap arithmetic in _clamp(...)
```

- Call only registered probes, `violates_hard_source_policy`,
  `probe_source_continuity`, and `_clamp`. **No imports.** Deterministic.
- Non-constant: it must separate the validation pairs (mechanism-rich
  positives vs hype/jargon negatives) with positive margin.
- Convention: start with
  `if violates_hard_source_policy(text, anchor): return 0.0`.

## Pair contract (policy-violating pairs are auto-filtered)

- The **positive** must not invent numbers, named entities, customer/award
  claims, or guarantees absent from the anchor. Keep it concrete and
  faithful: mechanism ("by <verb>ing <object>...") plus result ("so ...").
- The **negative** should *sound* good while being hollow — hype,
  fake mechanism, abstract jargon. Negatives may violate policy.
- Aim for pairs the frontier scorers will get wrong or separate with
  near-zero margin; your pairs compete against template candidates in a
  hardest-first selection, so make them genuinely confusing for the
  frontier code you read in the context.

## Strategy tips

- Target the largest `coverage_gaps` counts first; say so in `lineage`
  (`mutation` of a frontier scorer / `recombination` of two /
  `novel_composition`).
- Diversity matters: don't write three near-identical scorers. Vary gates,
  interactions (probe products), and continuity blends.
- The probes are cheap heuristics — exploit combinations the genome
  operators rarely find (e.g. conditional structures, asymmetric
  penalties), since that is your edge over the deterministic engine.
