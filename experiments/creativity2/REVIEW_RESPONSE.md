# Response to review: gate justification + new experiments

## Part 1 — Are the four gates needed, and do they suppress scorer creativity?

Short answer: all four are needed — each caught a real, named failure in our
logs — and none constrains *conceptual* content directly (they act on measured
behavior, not on ideas). But two of them have demonstrated indirect
creativity costs, with concrete fixes. The decisive evidence is EVO3: removing
the theory-first proposal prior while KEEPING all four gates produced the most
novel validated scorer of the project — the binding constraint was never the
gates, it was the hypothesis space.

**Gate 1 — Validity (range, determinism, non-constant).**
Needed: without it, fitness numbers are meaningless (out-of-range scores break
SEP; nondeterminism breaks reproducibility). Creativity cost: minimal but
nonzero — the spread<0.05 floor rejected frequency-residualization, which was
conceptually sound but *inert on our pair distribution*; "invalid" conflated
with "silent here". Fix: quarantine inert scorers in a nursery rather than
rejecting. Verdict: keep.

**Gate 2 — Anti-memorization (AST scan of word-list literals).**
Needed: it exists because an agent demonstrably lifted 11 distinctive verbs
from visible failure cases into its feature list; measured skill was partly a
test-set lookup. Creativity costs, both observed: (a) one false positive
(concrete_imagery_shift, 42>40 tokens, mostly closed-class); (b) it bans the
entire knowledge-lexicon scorer family (norm tables), biasing the search toward
structural/statistical mechanisms — a bias that partly *produced* our
"frequency ceiling". The reviewer is right that procedural leakage evades it;
our new E4 slice test addresses that behaviorally (below). Fix: allow lexicons
from registered external resources (hash-verified, provenance-checked) instead
of inline literals; add behavioral slice checks. Verdict: keep, extended.

**Gate 3 — Behavioral novelty (margin-vector |r| < 0.6).**
Needed: it caught 12+ disguised duplicates whose stated mechanisms sounded new
but whose behavior correlated up to 0.94 with incumbents — without it the
population collapses into one signal family and "novelty" becomes marketing.
Creativity cost: correlation is measured on the CURRENT eval, so the eval's
narrowness can masquerade as a scorer's unoriginality (zipf_band_dispersion —
spread-of-rarity, conceptually distinct from mean-of-rarity — rejected at
r=0.75; it might decorrelate on richer data). E3 (below) shows the 0.6
threshold does no hidden work. Fix: measure novelty on a broad probe battery
rather than the training pairs alone; prefer quality-diversity niching
(archive by behavior) over outright rejection. Verdict: keep, with niching.

**Gate 4 — Usefulness (SEP > population median, or novel with SEP > 0).**
Needed as drift control, but it is the most creativity-suppressing gate, with a
concrete demonstrated cost: it rejected edit_locality_gini (novel family,
SEP −0.029) — conceptually the SAME "concentration of change vs concentration
of information" family that the blind search later rediscovered as D6, which
passed every gate, scored perfect accuracy on the stationary core, and won the
external lyrics validation 5/6. The gate killed a weak embodiment of what
proved to be the project's best idea. Fix: a nursery — novel-but-weak scorers
get protected evaluation for N generations before culling. One good emergent
property to keep: the median-relative bar self-loosens when the population is
damaged (observed in Haiku gen 2), injecting fresh blood exactly when needed.
Verdict: keep, with probation.

## Part 2 — New experiments responding to the review

**E1. Seeding ablation via shape enrichment (reviewer: "the product baseline
seeded the two-factor rediscovery").** 12,000 random programs, no seeds, no
LLM: multiplicative/gated shapes show NO meaningful enrichment among the top
5% of separators (1.07x; ratio 1.01x; anchor-relative 1.00x). The reviewer's
skepticism is partly vindicated and the claim must be RE-QUALIFIED: on a static
eval, multiplicative forms are not fitness-favored. What the runs actually
show is that multiplicative forms are ATTACK-SURVIVAL-favored: every champion
that survived adversarial rounds in both arms was gated/conjunctive, and every
single-signal champion was destroyed within one generation of taking the lead.
The correct claim is "two-factor structure is selected by adversarial
robustness, not by static fitness" — a sharper and better-supported statement.

**E2. Bootstrap confidence intervals (reviewer: "no significance testing").**
10k resamples, 95% CI on SEP (mean margin):
- Haiku champion: heldout [0.090, 0.309], core [0.249, 0.490] — both exclude 0.
- Sonnet champion (evaluated cross-arm on the Haiku heldout): heldout
  [−0.017, 0.141] does NOT exclude 0; core [0.077, 0.336] does. The reviewer's
  small-core concern is fair; cross-arm heldout claims should be dropped or
  hedged, and the core expanded in future work.
- EVO3 blind discoveries: D2 heldout [0.013, 0.064], core [0.016, 0.063];
  D6 heldout [0.013, 0.115], core [0.078, 0.208] — all exclude 0.

**E3. Novelty-threshold sensitivity (reviewer: "0.6 is arbitrary").** The
EVO3 archive is IDENTICAL for thresholds 0.5, 0.6, 0.7, 0.8 (6/6 members) and
drops to 4/6 at 0.4. The threshold does no hidden work in the reported result.

**E4. Procedural/distributional leakage (reviewer: "AST scan is
insufficient").** Behavioral slice check: correlation between each champion's
per-pair heldout margin and that pair's lexical overlap with the training text
(overlap range 0.29–0.79). All four scorers: |r| ≤ 0.15 (haiku champ −0.15,
sonnet champ −0.06, D2 +0.01, D6 −0.00). No leakage gradient detected.

**E5. External validation beyond LLM-authored labels (reviewer's central
concern).** Six pairs of acclaimed human lyric lines (Cohen, Dylan, Radiohead,
Joni Mitchell, Waits) vs flattened paraphrases — external critical consensus,
not LLM labels: haiku champion 0/6, sonnet champion 0/6, blind D2 1/6,
**blind D6 5/6**. The strongest external-validity signal in the project belongs
to the blind, non-intuitive discovery — and both evolved champions fail
completely off-distribution, supporting the reviewer's demand for human-grounded
validation as the top priority.

**E6. Explanation gate with falsification (new, beyond the review).** A
separate interpreter agent produced mechanics + 3 falsifiable predictions per
blind program + 12 fresh probe pairs (6 designed as falsification bait).
Independent verification: **12/12 predictions held**, including all bait. The
explanations also surface honest failure modes (D2 prefers a thesaurus cliché
over a common-word metaphor; D6 is blind to function-word edits). D2 and D6
are therefore non-intuitive AND explainable in the strong sense: their
interpretations predict behavior on unseen cases.

**Seed-repeat of the blind search** (seed 1, smaller sweep): different specific
programs, same recurring FAMILIES — concentration statistics (max_share/gini)
composed with anchor-relative ratios; one program again reached core accuracy
1.00 (prod(max_share(zipf[sent]), ratio(Δchanged_content, Δzipf))); one archive
member overfit (core 0.00), reconfirming that per-tier reporting is essential.

## What D6 — the discovered non-intuitive scorer — actually says

`max_share(op[changed]) − |gini(edit locations among content words) −
gini(information profile)|`: prefer rewrites with FEW edits whose spatial
concentration MATCHES the concentration of information in the text. In plain
terms: *creative editing places its few changes where the information lives.*
No agent, no hand-coder, and no prior phase of this project proposed measuring
the alignment of two concentration profiles; it survived all four gates, is
decorrelated from every incumbent (max |r| = 0.23), holds on the frozen
heldout, scores 1.00 on the stationary core, transfers to human masterworks
(5/6), and carries a validated explanation. This is the existence proof that
the pipeline can deliver what was asked: a non-intuitive but explainable
creativity scorer.

## Remaining items we cannot address in-session

Human ratings on a representative subset (the essential validation), an
equalized-compute arm isolating model size from volume/generations, an expanded
stationary core, and seed replicates of the full agent arms. All are budgeted
designs, not open problems.
