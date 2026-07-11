# Phase 6–7: adversarial decoupling + merge — findings

Goal: attack the phase-5 winner **S3** (labeled "anti-formulaic / cliché") with
pairs that decouple its signal from creativity — `more_creative` rewrites that
keep a stock idiom, `less_creative` rewrites that avoid idioms — then merge the
best separators and ask whether anything beyond the winning cue survives on the
adversarial heldout.

## Headline: S3 did **not** collapse (0.80 → 0.75), and that is the finding

| set | S3 more>less acc |
|---|---|
| original 20 pairs | 0.800 |
| adversarial 12 pairs (built to stump S3) | 0.750 |

The attack barely dented S3 — but the per-feature diagnostic shows **why**, and
it corrects the phase-5 label.

## What S3 actually measures is not "cliché"

- The isolated cliché-phrase feature `cliche_only` scored **0.000 (12 ties)** on
  the adversarial set: it separates nothing. Reason: the cliché *lexicon* has such
  low recall that it did not fire on **any** of the 11 idioms I hand-planted
  ("hit the ground running", "edge of your seat", "good as new", "no pain no gain"…
  none are in the list). This empirically confirms the measurement-map warning:
  cliché-list matching is high-precision, catastrophically low-recall.
- So S3 was **never** relying on the cliché list for these pairs. Its working
  signal is the other three formulaicity channels — **common-bigram density and
  generic-verb density**. Diagnostic: on the adversarial set the *less_creative*
  versions have higher common-bigram density (0.040 vs 0.025) despite containing
  no idioms, because flat generic prose ("was delayed due to", "a large number of
  residents remain") is collocation-heavy by nature. S3 ranks them correctly
  through that channel.

**Correction to the phase-5 conclusion:** the winning signal is not
cliché-detection but **common-collocation + generic-verb predictability**. My
phase-6 attack decoupled the wrong sub-signal (idioms S3 couldn't see anyway),
so it failed to stump S3 — a more informative outcome than a success.

## The frequency confound, caught red-handed

`rarity` was the single best feature on the original set (0.850) — and collapses
to exactly chance on the decoupled adversarial set (**0.500**). Its original-set
success was riding on correlation with the real predictability signal; once
decoupled, it evaporates. This is the cleanest empirical instance of the
Momen & Zarrieß frequency confound in the whole experiment.

## Merge: marginal, and confined to the same axis

Subset search (equal-weight z-sum, signs fixed by theory, leave-one-out CV):

| merge | adv (in-sample) | adv LOO | orig |
|---|---|---|---|
| {antiformulaic_abs, bigram_fresh, resid_recomb} | 0.833 | **0.833** | 0.850 |
| S3 alone | 0.750 | — | 0.800 |
| plain fixed-weight mean of that triple (deployable) | 0.667 | — | 0.750 |

The best z-scored merge beats S3 by one pair (9→10 of 12) and holds under LOO —
but every feature it adds (`bigram_fresh`, `resid_recomb`) lives on the **same
predictability axis** as `antiformulaic_abs`; they are all "common words in
uncommon-but-coherent arrangements." And the *deployable* fixed-weight form is
**worse** than S3 (0.667). So the merge does not robustly beat the winner and,
more importantly, does not reach a **new** axis.

## What stayed dead (and the real next step)

The two axes the literature says matter most for creativity —
**semantic distance / DSI** and **fresh figurative imagery** — never separated:

| feature | orig | adv |
|---|---|---|
| divergence (DSI proxy) | 0.200 | 0.000 (11 ties) |
| figurative (concreteness contrast) | 0.250 | 0.333 (6 ties) |
| concrete_density | 0.250 | 0.333 (6 ties) |

My adversarial `more_creative` versions were fresher largely through apt concrete
imagery ("the spoon nearly stood up in it", "skate once the ice stops talking",
"legs humming, the valley small below") — yet the stdlib imagery/figurative
probes barely moved, because the figurative-frame regex misses unmarked metaphor
and bag-of-words divergence is near-zero on same-content 2-sentence edits.

**Honest conclusion.** At the stdlib level, creativity scoring here reduces to
**collocational predictability** (how formulaic the word combinations are), which
is robust and even improvable — but it is a single axis. The semantic-distance
and figurative-novelty axes, which the causal graph rates as the strongest paths
to judged creativity, are not stdlib-reachable. The honest next step is **real
embeddings** (SemDis/DSI, sentence vectors for divergence, concreteness norms at
full coverage), not more feature engineering on the predictability axis.

## Caveats / future work

- 12 adversarial pairs is tiny; LOO tempers but does not eliminate overfit risk.
- The attack should be **redone against the true signal**: `less_creative`
  versions that avoid common bigrams and generic verbs while staying flat. This
  is very hard to write — genuinely un-formulaic *flat* prose barely exists in
  English — and that difficulty is itself evidence that flatness ≈ collocational
  predictability, which is why the signal is robust.
- Eval-pair creativity labels are LLM-authored, not human-rated (unvalidated).
