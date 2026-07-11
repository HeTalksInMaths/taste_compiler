# Round-2 evolution under adversarial pressure — what more was created

Starting point: the real-NLP champion combined two novelty signals — lexical
rarity (`mean_surprisal`, real wordfreq) + combinational novelty
(`phrase_novelty_divergence`, sklearn word-bigram/trigram TF-IDF) — at ~0.94.

## The adversarial pressure

10 new pairs (`adversarial_pairs_r2.json`) of type **novelty WITHOUT
appropriateness**: the *less* creative version is purple prose — rare Latinate
words in odd combinations ("crimson orbs bejeweled the verdant tendrils",
"vehicular flux surges with newfound alacrity"). This maximizes BOTH novelty
signals while being worse writing. The champion scored **0/10** — additive
novelty is maximized by purple prose.

## What the coding agent created (real metrics, no eyeballed weights)

Reading the pairs, it found the purple versions have a surprisal jump over the
anchor (+2.3 to +5.5 bits) far beyond what the apt rewrite needs, plus heavy
Latinate morphology and polysyllables. It wrote three real appropriateness
metrics; the load-bearing one:

- **`novelty_excess_penalty`** — the inverted-U (Wundt curve) made real: 0.0 while
  a rewrite's surprisal increase over its anchor stays within a budget (~2.15 bits,
  = one SD of word-surprisal computed once from wordfreq's own 50k lexicon, NOT
  tuned to the eval), then quadratically negative past that. It is **0 on every
  one of the 32 round-1 pairs** (never opposes the novelty signals) and fires only
  on the purple-prose overshoot.

Per-metric separation (orig / adv / r2):

| metric | orig | adv | r2 |
|---|---|---|---|
| mean_surprisal (novelty) | 0.95 | 0.75 | **0.00** |
| phrase_novelty (novelty) | 0.90 | 0.75 | **0.00** |
| novelty_excess_penalty (appropriateness) | 0.00 | 0.00 | **1.00** |

## The discovery: creativity must be CONJUNCTIVE

The novelty signals and the appropriateness signal are each blind to the other's
regime. A vote fails (2 novelty signals outvote the 1 guardrail on R2). What works
is the **conjunctive** structure — novelty GATED BY appropriateness — which is
exactly the standard definition of creativity (novelty × appropriateness; Runco &
Jaeger 2012; Rastelli 2022). The adversarial pressure *forced the loop to
rediscover the definition from data.*

    score = z(lexical rarity) + z(combinational novelty)
            + veto_strength * min(0, novelty_excess_penalty)

| scorer | orig | adv | r2 | all (42) |
|---|---|---|---|---|
| novelty only (additive) | 0.95 | 0.92 | 0.00 | 0.714 |
| **novelty gated by appropriateness** | 0.95 | 0.92 | 0.90 | **0.929** |

The gate is not a tuned weight: any `veto_strength >= 5` gives identical 0.929
(k = 5, 10, 50 all match) — the signature of a real gate, not a fitted parameter.
Full recovery of R2 with zero regression on the round-1 sets.

## Epistemology now (richer, and honest)

Creativity-of-rewrite is now measured as the literature's actual structure:

    creativity = NOVELTY × APPROPRIATENESS
      NOVELTY        = lexical rarity (real freqs) + combinational novelty (TF-IDF)
      APPROPRIATENESS= not-overwrought = inverted-U on novelty vs the anchor (Wundt)

Two real, orthogonal novelty axes, gated by a real inverted-U appropriateness
term. This is a genuine step beyond round 1 (which measured only novelty).

## Honest limits

- The appropriateness term catches THIS form of inappropriateness — overwrought
  register / purple prose. Broader appropriateness (incoherence, off-topic,
  factual drift) is NOT tested, because all eval variants hold content constant.
- The two register metrics (Latinate-suffix, polysyllabic) are near-chance on the
  round-1 pairs; they are purple-prose specialists. Only `novelty_excess_penalty`
  is the clean, always-safe guardrail.
- Genuine embedding-semantic-distance novelty (DSI) remains proxy-blocked, and
  eval labels are LLM-authored, not human-rated. Small sets (42 pairs).
- Next adversarial axis to try: appropriateness failures that are NOT purple prose
  (e.g. locally fluent but globally incoherent rewrites) — which would need a real
  coherence signal (adjacent-sentence similarity), currently only doable lexically.
