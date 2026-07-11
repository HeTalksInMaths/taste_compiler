# LLM-mutation evolution — findings

Mutation = **Sonnet writing new scorer functions** each generation, reasoning
from the previous run's summary stats (per-scorer separation, and the concrete
pairs the current best scorer fails). Selection = separation accuracy
(more_creative > less_creative). The adversarial set **grows** each generation
by adding the pairs the current best scorer separates worst.

## Separation trajectory

| gen | pairs | scorers | best (all) | best (orig) | best (adv) | best scorer | lineage |
|---|---|---|---|---|---|---|---|
| 0 | 20 | 5 | 0.800 | 0.800 | — | S3_antiformulaic | initial (hand-written) |
| 1 | 23 | 8 | 0.696 | 0.800 | 0.000 | S3_antiformulaic | initial |
| 2 | 26 | 10 | **0.923** | 0.950 | 0.833 | **S_g2_llm01** | **llm_gen2** |
| 3 | 29 | 13 | 0.862 | 0.950 | 0.667 | S_g2_llm01 | llm_gen2 |

(best_adv is accuracy on the adversarial pairs added so far; it fluctuates
because each generation adds the pairs the current best fails.)

## What happened

1. **The hand-written scorers topped out at 0.80, and their winner (S3,
   anti-formulaicity) scores 0.000 on the adversarial pairs** — it measures the
   absence of clichés/common bigrams, which the adversarial pairs decouple from
   creativity.

2. **Gen 1 (Sonnet):** reading S3's failures, Sonnet wrote three specialists
   (vivid-verb density, figurative detection, concreteness). Each scored ~1.000
   on the adversarial pairs S3 fails, but weaker on the 20 base pairs — so the
   aggregate best stayed S3. This exposed the real gap: *no single scorer was
   strong on both sets.*

3. **Gen 2 (Sonnet) — the breakthrough:** told about that gap, Sonnet found the
   move every hand-written scorer had missed — **contrast against the anchor.**
   `S_g2_llm01` scores a rewrite by how much it swaps the *anchor's* plain verbs
   for sharper ones, rather than scoring the text in isolation. Result: **0.923
   overall (0.950 base, 0.833 adversarial)** — the first scorer strong on both,
   beating S3 by ~0.19. The task is scoring a *rewrite*, so the signal is the
   delta from the anchor; the LLM discovered that framing from the data.

4. **Gen 3 (Sonnet):** generalized the winning idea to other axes — noun/adjective
   concreteness contrast (0.724), syntactic-rhythm contrast (0.586), figurative
   contrast (0.276). None beat the gen-2 champion; the verb-contrast mechanism
   appears near the ceiling of these lexical features. Diminishing returns.

## Read

- **LLM mutation clearly outperformed the hand-written scorers and the earlier
  weight-blend mutation** (which never beat S3). Reasoning from summary stats,
  Sonnet discovered a new *mechanism* (relative-to-anchor specificity), not just
  new weights — exactly what the weight-blend approach structurally could not do.
- **The adversarial growth drove the discovery:** gen-1's specialists only
  appeared because the adversarial pairs made S3's blind spot visible in the
  stats; gen-2's champion was written specifically to close the base-vs-adversarial
  gap those pairs created.
- **Ceiling by gen 3:** the champion's adversarial accuracy fell 0.833 → 0.667 as
  harder pairs accumulated, and no gen-3 scorer beat it — a signal that lexical
  contrast features are near their limit and the next gain needs a different
  signal (embeddings), not more lexical mutation.

## Caveats

- 20 base + 12 adversarial pairs is small; accuracies move in ~3–5% steps.
- Eval-pair creativity labels are LLM-authored, not human-rated.
- The champion relies on embedded verb lists; coverage limits generalization
  beyond these topics.
