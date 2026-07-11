---
name: creativity-scorer-discovery
description: Literature-grounded discovery of creativity scorers — Sonnet subagents do repeated web research (creativity literature, then NLP operationalizations per causal-graph node) and build an internet-sourced eval set; the main-session model (Opus/Fable) constructs the causal graph, organizes the measurement map, and proposes scorers data-scientist-style (reasoning before code). Use when the user wants to "discover creativity scorers from the literature", "build the creativity causal graph", or "run the creativity separation experiment". Scope: discovery + first separation test ONLY — scorer evolution/merging and adversarial pair growth are a future skill update.
---

# Creativity scorer discovery (literature-grounded)

The failure mode this skill exists to fix: the evolutionary loop's scorers were
symbolic regression over a small hand-picked probe alphabet, so their
expressiveness was capped by whatever the pipeline author already believed.
Here, the constructs come from the literature (searched, not recalled), the
measurements come from how NLP actually operationalized those constructs, and
scorer proposals are written like a data scientist building a model: stated
hypothesis and design reasoning FIRST, code second.

Division of labor is fixed:

- **Sonnet subagents** (Agent tool, `model: "sonnet"`) do the repeated
  searching and the eval-pair construction. They return raw structured
  findings — they do NOT build the graph, design scorers, or run evaluation.
- **The main-session model** (Opus/Fable — the orchestrator reading this)
  constructs the causal graph from phase-1 findings, organizes the phase-2
  measurement map, writes the scorers, and runs the separation analysis.

All artifacts go under `experiments/creativity/`.

## Phase 1 — Literature search → causal graph

Launch ONE Sonnet subagent (general-purpose) to do REPEATED searches
(≥10 distinct queries; WebSearch + WebFetch on promising hits) across the
creativity literature: psychology of creativity (novelty/usefulness
definitions, divergent thinking, remote associates), computational-creativity
work, and linguistic-creativity studies. It must return JSON:

```json
{"findings": [{"construct": "...", "definition": "...",
  "causal_claims": [{"from": "...", "to": "...", "direction": "+|-",
                     "evidence": "one sentence", "source": "paper/author/year or URL"}],
  "sources": ["..."]}],
 "queries_run": ["..."], "search_method": "websearch|webfetch|fallback_knowledge"}
```

If search tooling fails it may fall back to trained knowledge but MUST label
provenance honestly in `search_method`.

Then the ORCHESTRATOR (not the subagent) constructs the causal graph:
deduplicate constructs into ~8–14 nodes, keep edges with stated evidence,
mark each edge's sign and confidence, and identify which nodes are
*text-observable* (measurable from the words alone) vs latent. Save as
`experiments/creativity/causal_graph.json` plus a short readable summary of
the load-bearing paths (latent creativity → observable text features).

## Phase 2 — Per-node NLP operationalization search → measurement map

AFTER phase 1 completes, launch a SECOND Sonnet subagent. Input: the list of
text-observable graph nodes. For EACH node it searches (repeatedly — at least
one query per node, more when the first result is thin) how NLP / ML work has
measured that construct: named metrics, formulas, Python approaches
(surprisal, semantic distance, DSI, type-token ratios, concreteness norms,
collocation/cliché statistics, ...). Return JSON keyed by node:

```json
{"node_name": {"metrics": [{"name": "...", "how_computed": "...",
   "python_feasibility": "stdlib|needs_wordlist|needs_embeddings",
   "known_failure_modes": "...", "source": "..."}]}}
```

The orchestrator organizes this into
`experiments/creativity/measurement_map.json`, annotating for each metric
whether it is implementable in the repo's runner (stdlib only: `re, math,
collections, string, statistics, unicodedata`; embedded word lists are fine,
external models/embeddings are not — record those as "future work" rather
than dropping them silently).

## Phase 3 — Scorer proposals (reasoning before code)

The ORCHESTRATOR now proposes 4–6 scorers. This is the anti-symbolic-
regression step; each scorer MUST be written as a design document entry
BEFORE its code:

1. **Hypothesis** — which causal-graph path it bets on.
2. **Design reasoning** — like a data scientist: what features, why this
   functional form, what the literature says, expected failure modes, what
   would falsify it.
3. **Code** — `def scorer(text, anchor, params) -> float in [0,1]`,
   self-contained (stdlib-of-runner only, embedded word lists allowed),
   deterministic, runnable via `evalweaver.runner.py_run_scorer`.

Diversity requirement: the scorers must bet on DIFFERENT graph paths /
feature families, not five reweightings of one idea. Save to
`experiments/creativity/scorers.json` (`[{scorer_id, hypothesis,
design_reasoning, graph_nodes_used, code}]`).

## Phase 4 — Internet-sourced eval pairs (Sonnet subagent)

Launch a Sonnet subagent (may run in parallel with phases 1–3; it must stay
BLIND to the scorers, and the scorer author must not see the pairs before
phase 5). Task: pull **20 real two-sentence statements from the internet**
(diverse sources — news, blogs, forum posts, product pages, wiki, essays;
record URL/source for each), then for each write:

- a **slightly MORE creative** variant (same meaning/content, small edit —
  fresher imagery, an unexpected-but-apt turn; not purple, not longer-for-
  the-sake-of-it), and
- a **slightly LESS creative** variant (same meaning, flattened into stock
  phrasing/cliché).

"Slightly" is the point — subtle gaps, not caricatures. Return JSON:
`[{pair_id, source_url, anchor, more_creative, less_creative, edit_note}]`.
Save to `experiments/creativity/eval_pairs.json`.

## Phase 5 — Separation analysis

The orchestrator runs every scorer on every pair via `py_run_scorer`
(text = variant, anchor = original statement). For each scorer report:

- **accuracy**: fraction of pairs where score(more) > score(less)
- **mean margin**: mean(score(more) − score(less)); **spread**; tie count
- per-pair margins, worst pairs, and cross-scorer agreement

Save `experiments/creativity/separation_results.json` and report the table
plus an honest read: which hypothesis separated best, which failed, whether
ties dominate (a probe firing on nothing is sparse, not anti-predictive).

## Phase 6 — Adversarial pair growth (Opus, decouple the winning signal)

After phase 5 identifies the best-separating scorer, the orchestrator (NOT a
subagent — this is the reasoning-heavy step) grows the eval set with pairs
designed to STUMP that scorer by decoupling its signal from true creativity.

The design rule: find what the winner actually keys on, then build pairs where
that cue points the WRONG way. For a cliché/formulaicity winner (S3), that means:
- **creative-keeps-cliché**: a genuinely fresher, more vivid rewrite that
  nonetheless contains a stock phrase or common collocation (winner penalizes it), and
- **flat-avoids-cliché**: a duller, more generic rewrite that scrupulously uses
  no idioms (winner sees nothing to penalize).
Same factual content across all three versions, 2 sentences, subtle. Tag each
with its trap type. Save `experiments/creativity/adversarial_pairs.json` with a
`design_note` per pair stating which cue is inverted and why the more_creative
version is still the more creative one.

The purpose is diagnostic, not to defeat the scorer for its own sake: if the
winner collapses to ≤ chance here while human judgment still ranks
more_creative > less_creative, the scorer was measuring cliché, not creativity.

## Phase 7 — Merge best separators + test on the adversarial heldout

Expose the atomic sub-signals inside every proposed scorer as standalone
feature probes (the merge alphabet). Then:

1. **Scorer-level merge**: ensemble the best separators (mean of normalized
   outputs, and majority vote); test on the adversarial set as a decoupled heldout.
2. **Feature-level diagnostic**: report each atomic feature's more>less accuracy
   on BOTH the original and the adversarial set — this reveals which raw signal,
   if any, tracks creativity once the winning cue is neutralized.
3. **Constrained merge search**: low-capacity, sign-fixed-by-theory combination
   of features (e.g. subset selection with equal weights over z-scored features),
   selected on the adversarial set, reported with leave-one-out cross-validation
   so a tiny adversarial set cannot manufacture an overfit "win."

Report honestly: does any merge beat the collapsed winner on the adversarial
heldout while holding up on the original? If yes, name the surviving signal and
what graph node it came from. If no, state plainly that stdlib creativity
scoring here reduces to cliché-detection, and that the surviving path (semantic
distance / DSI) needs embeddings the runner does not have — i.e. the honest
next step is real embeddings, not more feature engineering.

## Scope discipline

This update ends at the merged-heldout report. Still OUT of scope: a full
multi-generation genome evolution, embedding-backed probes, and any human-rating
validation of the eval pairs (all flagged as future work in the report).
