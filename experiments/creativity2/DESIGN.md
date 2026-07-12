# EVO2 — agentic discovery of novel creativity scorers (design)

Goal: give an agent system the best possible chance of discovering a **novel
scorer in deterministic NLP theory** — a real, mechanism-grounded metric that
measures a causal-graph node no incumbent scorer measures, survives a growing
adversarial eval, and is not a re-labeling of an existing signal.

Everything below encodes the failure modes we hit and fixed this session:
weight-blend mutation (dead end), hand word-lists (test-set leakage), accuracy-only
fitness (ignores calibration), single-axis novelty (purple-prose collapse).

---

## 1. Scorer contract

```python
def scorer(text: str, anchor: str) -> float   # ALWAYS in [0.0, 1.0]
```

- **Normalized [0,1] by construction**, via principled squashing (logistic /
  exponential decay) whose location/scale constants come from REFERENCE
  statistics (e.g. token-level surprisal mean/SD computed from wordfreq's own
  lexicon at import) or stated theory — never from the eval pairs.
- Deterministic (no RNG, no time). Real libraries allowed: wordfreq, sklearn,
  numpy, scipy (verified importable; downloads are proxy-blocked and forbidden).
- NO hand-typed content word-lists. Hard limit enforced by the leakage checker
  (§5). Closed grammatical classes (stopwords, suffixes) are exempt.
- Each scorer declares the **causal-graph node** it operationalizes and the
  named mechanism/paper behind it.

## 2. Fitness = separation distance over both score distributions

For each pair i: `s_pos_i = scorer(more_creative, anchor)`,
`s_neg_i = scorer(less_creative, anchor)` — both scored individually.

- **Primary fitness: SEP = mean(s_pos) − mean(s_neg)** on the train split
  (∈ [−1,1]; identical to mean pairwise margin but reported with both
  distribution means so calibration is visible).
- Reported alongside: accuracy (fraction s_pos > s_neg), effect size
  d = SEP / pooled_SD, mean±SD of s_pos and of s_neg separately, worst-pair margin.
- Selection key: (SEP, accuracy, −SD(margins)) lexicographic.
- Validity gates (hard rejects): any score outside [0,1]; exceptions; spread
  < 0.05 across all eval texts (constant-output guard); non-determinism
  (same input scored twice must match).

## 3. Eval design: three tiers, anti-leakage split

Seeded with the 42 existing pairs (20 original, 12 adv-1, 10 adv-2 purple-prose):

- **TRAIN** (~2/3, deterministic split): visible to agents; fitness computed here.
- **FROZEN HELDOUT** (~1/3): never shown to any agent, never described verbatim;
  every generation the champion's heldout SEP is reported for honesty. Grows only
  via the red team's new pairs (a fixed share is diverted here unseen).
- **STATIONARY CORE** (the original-20's heldout members): never grows, so SEP is
  comparable across generations.

## 4. Agent architecture (roles, prompts, context passing)

Deterministic orchestrator (Python harness) + two LLM agents per generation with
SEPARATED contexts (blue never sees heldout; red never sees the population beyond
the champion):

1. **Scorer Engineer (blue, Sonnet)** — writes 3 new scorer modules/generation.
   Context file (JSON, assembled by harness):
   - causal graph (nodes/edges) + **node-coverage map**: which nodes are measured
     by the current population and which are UNCOVERED (the novelty target);
   - population summary: per-scorer SEP/acc/mean_pos/mean_neg + the **margin-vector
     correlation matrix** (so redundant signals are visible and avoidable);
   - champion code + its TRAIN failures (full pair text is allowed from train only);
   - environment facts (verified libs; downloads blocked);
   - the contract, the leakage rule, and the **novelty acceptance criteria**
     (§5) verbatim — the agent designs *for* them;
   - structured output schema: JSON array of {name, causal_node, mechanism,
     reasoning, code} where code is a complete importable module exposing
     `METRICS = {name: fn}`.
2. **Adversarial Designer (red, Sonnet)** — writes 8 candidate pairs/generation.
   Context: champion code + a one-line statement of its measured axis, the causal
   graph, trap axes ALREADY USED (must pick a new decoupling axis), pair schema
   (anchor / more_creative / less_creative / trap / design_note / predicted
   champion behavior). Candidates are validated (sanity, length, distinctness),
   then **hardest-first**: keep the 6 with lowest champion margin; 4 → train,
   2 → frozen heldout (content never echoed back to agents).

Context passing is file-based (gen NN context JSONs persisted), so every
generation is auditable and resumable.

## 5. Novelty — operationalized, not vibes

A proposal is accepted as **novel** only if all three hold:

1. **Behavioral**: Pearson |r| of its per-pair margin vector vs EVERY incumbent
   < 0.6 on train (otherwise it is the same signal renamed);
2. **Mechanistic**: it declares a causal node either uncovered or measured only
   by weaker scorers, with a real named mechanism (orchestrator judges);
3. **Leakage-clean**: AST scan of the module's string/list literals — reject if
   ≥3 rare tokens (zipf < 3.5) from literals appear in train pair texts, or if
   >40 hardcoded content tokens total (the no-word-list rule, enforced).

Acceptance into the population: valid AND (fitness > population median OR novel
with SEP > 0). Non-novel but stronger scorers are still kept (they raise the
bar); novel ones are protected (below).

## 6. Evolution schedule

- **Population cap 10**: top-6 by fitness + up to 2 novelty-niche slots (lowest
  max-|r| to the kept set) + up to 2 newest. Seeds = the 4 normalized real
  metrics already discovered (rarity, combinational novelty, appropriateness
  gate, conjunctive product) — the baseline any novel scorer must beat or
  decorrelate from.
- **3 scorer proposals + 6 kept adversarial pairs per generation.**
- **5 generations** (budget-fit; each = 2 agent calls), **early stop** after 2
  consecutive generations with (a) no champion heldout-SEP improvement AND
  (b) no accepted novel scorer.
- Per-generation report: table of id / lineage / causal node / SEP / acc /
  mean_pos / mean_neg / heldout-SEP(champion) / novelty flag, plus which
  adversarial axis was added.

## 7. Success criteria (declared up front)

The experiment "surfaces a novel scorer" iff by the final generation there is a
scorer that (i) passes all three novelty tests, (ii) improves the champion's or
the ensemble's FROZEN-heldout SEP, and (iii) holds SEP > 0 on the newest
adversarial axis it was not bred against. Anything else is reported as a
negative result.
