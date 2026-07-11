# Scorer lineage and separation each round

Datasets: Orig (20 base pairs), Adv-1 (12 round-1 adversarial), Adv-2 (10 round-2
"purple prose" adversarial). Value = fraction ranking more_creative > less_creative.
Every scorer scored on all three sets uniformly.

| # | scorer (what it measures) | mutated from | Orig | Adv-1 | Adv-2 |
|---|---|---|---|---|---|
| Track A — lexical (hand-written -> LLM-mutated) ||||||
| 1 | novelty x appropriateness (hand) | initial | 0.30 | 0.25 | 1.00 |
| 2 | divergent integration (hand) | initial | 0.40 | 0.42 | 0.20 |
| 3 | anti-formulaicity (hand) | initial | 0.80 | 0.75 | 0.00 |
| 4 | figurative contrast (hand) | initial | 0.25 | 0.33 | 0.40 |
| 5 | residualized combination (hand) | initial | 0.40 | 0.33 | 0.30 |
| 6 | vivid-verb density | 3 | 0.35 | 0.33 | 0.20 |
| 7 | figurative detection | 3 | 0.10 | 0.50 | 0.10 |
| 8 | concreteness | 3 | 0.55 | 0.83 | 0.50 |
| 9 | verb-specificity contrast vs anchor | 3 (+6-8 gap) | 0.95 | 0.75 | 0.00 |
| 10 | sensory density | 8 | 0.55 | 0.58 | 0.50 |
| 11 | figurative/idiom contrast | 9 | 0.15 | 0.50 | 0.10 |
| 12 | noun/adj concreteness contrast | 9 | 0.70 | 0.83 | 0.30 |
| 13 | syntactic-rhythm contrast | 9 | 0.40 | 1.00 | 0.40 |
| Track B — real NLP (restart) ||||||
| 14 | lexical rarity / surprisal (real freqs) | new baseline | 0.95 | 0.75 | 0.00 |
| 15 | combinational novelty (phrase TF-IDF) | 14's failures | 0.90 | 0.75 | 0.00 |
| 16 | appropriateness (over-novelty penalty) | 14+15 failures | 0.00 | 0.00 | 1.00 |
| 17 | 14 + 15 gated by 16 (conjunctive) | 14+15+16 | 0.95 | 0.92 | 0.90 |

Reading:
- Track A converged on #9 (verb contrast): strong on Orig, 0.00 on Adv-2 (novelty only).
- Track B rebuilt with real parameter-free NLP; #14/#15 still 0.00 on Adv-2.
- #17 is the only scorer strong on all three (0.95/0.92/0.90): round-2 purple-prose
  pressure forced novelty (#14+#15) to be GATED BY appropriateness (#16) -- the
  conjunctive definition of creativity.
