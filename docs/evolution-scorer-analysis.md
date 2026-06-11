# Did the evolutionary loop discover insight, or ad hoc functions?

Analysis of the 80-run offline batch (40 seeds × {persuasive, trustworthy},
6 generations, pop 12) plus the Claude-as-model demo run. Reproduce with
`python -m evalweaver evolve-batch --seeds 40 --goals persuasive trustworthy
--generations 6 --workers 4` and the probe-enrichment/baseline/transfer/OOD
script described below.

## 1. Selection pressure is real and convergent

Probe adoption in batch winners vs the gen-0 random population
(enrichment = winner% / seed%):

| probe | winners | gen-0 | enrichment |
|---|---|---|---|
| epistemic_calibration | 98% | 42% | **2.34×** |
| causal_density | 80% | 39% | **2.04×** |
| abstract_jargon_density | 100% | 65% | 1.53× |
| argument_progression | 100% | 70% | 1.43× |
| mechanism_result_alignment | 48% | 39% | 1.23× |
| audience_relevance | 40% | 41% | 0.98× |
| real_mechanism_quality | 30% | 39% | 0.77× |
| specificity / spec_without_invention | 40%/22% | 68%/38% | 0.59× |
| persuasion_risk | 15% | 32% | **0.47×** |

Structure converges hard: 85% of winners carry a jargon gate (~0.2–0.35),
90% an interaction term (most commonly argument_progression×causal_density
and argument_progression×epistemic_calibration), 100% a source-continuity
blend (~0.3). Mean calibration weight 0.48. This is not random drift — 80
independent runs land on the same recipe.

## 2. But the recipe is mostly recoverable without evolution

Heldout accuracy on the final *hardened* suites (20-run sample):

| scorer | accuracy |
|---|---|
| evolved winner | **0.956** |
| naive equal-weight mix of 6 sensible probes | 0.944 |
| anti-jargon alone | 0.878 |
| argument_progression alone | 0.756 |
| anti-hype alone | 0.333 (13/18 ties) |
| real_mechanism_quality alone | 0.228 (12/18 ties) |

~88% of the task is "detect jargon"; a naive composite closes to within
1.2 points of evolved winners. Evolution's tuning gain is real but small
*on this synthetic distribution*. (The sub-chance single-probe numbers are
tie-dominated — those probes are sparse, not anti-predictive.)

## 3. The genuinely interesting discovery is about the *suite*, not persuasion

`persuasion_risk` (hype detection) is strongly selected **against** (0.47×),
and anti-hype scores only 0.333 on hardened heldouts. The adversarial loop
spends the easy hype signal: selected pairs are exactly the ones where
superlatale density no longer discriminates, forcing scorers toward
argument-structure features. The de-selection of `real_mechanism_quality`
in favour of jargon-gated `causal_density` is likewise diagnostic: the rmq
probe's concrete-vocabulary list is too sparse (tie-heavy), so evolution
routes around it. Actionable: that probe needs a richer lexicon or
syntactic detection.

## 4. Transfer is perfect — and that's a warning, not a triumph

Winner_i on run_j's hardened heldout: 0.956 mean (min 0.944), identical to
home accuracy, including across goals. Offline, the goal keyword is
cosmetic and every run shares one template generator — so transfer
demonstrates *consistency of the synthetic distribution*, not
generalization. The discovered functions are best read as interpretable
reconstructions of the pair generator's structure (probes and templates
share vocabulary, and labels are template-defined), i.e. partially
circular.

## 5. The Goodhart proof: hedge-stack traps collapse every winner

Four hand-written OOD pairs (concrete positives vs hedge-stacked vacuous
negatives — "can often", "typically", "may usually" — under the jargon
gate) score **0.081 mean accuracy across all 80 winners; every single
winner ≤ 50%**. The loop's strongest "insight" — calibration language
predicts quality (98% adoption, weight 0.48) — inverts the moment hedges
are decoupled from substance. Marker-light concrete positives (12 pairs)
hold up better: 0.856, with 16/80 winners failing.

Notably, those killer pairs were produced *by the loop itself* in
Claude-as-model mode (gen-2 of the demo run: all four were selected with
frontier margins to −0.38). The adversarial half of the system can find
exactly the holes the scorer half overfits to — offline, it just runs out
of template vocabulary to express them.

## Verdict

The discovered scorers are interpretable, convergent, and structurally
sensible — the recipe (hard-policy veto → jargon gate → argument-quality
blend × source-continuity, hype as spent signal) reads like a compact
ELM-flavoured theory of the pair suite. But on offline data they are
~halfway between insight and artifact: most of their accuracy is reachable
by trivial baselines, their semantics echo the template generator, and
their flagship feature (calibration) is one distribution shift away from
inversion.

What would make the discoveries evidential rather than ad hoc:

1. **Real anchors and labels** — Exa-fetched posts with pair labels from
   human judgment or an LLM judge that does not share vocabulary with the
   probes (breaks the circularity).
2. **LLM-generated adversarial pairs every generation** (the demo showed
   this is the highest-leverage LLM insertion point — it found the hedge
   hole immediately).
3. **Probe repair in the loop** — treat tie-heavy probes (rmq) as
   failures to fix, not genes to drop.
4. **Cross-distribution heldout** — score winners on pairs from a
   *different* generator (different template bank or live LLM) as the real
   fitness, so Goodharting the home suite stops paying.
