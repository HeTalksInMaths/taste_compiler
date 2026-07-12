# Haiku arm continuation (gens 6-7): convergence by red-team exhaustion

Continued from gen 5 as requested. Final trajectory:

| gen | train | champion | SEP | heldout SEP | core SEP | red-team result |
|---|---|---|---|---|---|---|
| 4 | 57 | structural_diversity_content_gated | 0.106 | 0.158 | 0.359 | new champion |
| 5 | 63 | (same) | 0.139 | 0.187 | 0.359 | jargon attack failed |
| 6 | 70 | (same) | 0.123 | 0.169 | 0.359 | translation-ease + Latinate attacks: worst margin only -0.22 |
| 7 | 77 | (same) | 0.154 | **0.198** | 0.359 | deletion-creativity + mechanical-inversion attacks: **all 10 kept margins POSITIVE** (0.07..0.77) |

## What happened

1. **The champion survived four consecutive targeted attack rounds** and ended at
   its heldout peak (0.198). Four different red-team axes (jargon substitution,
   translation-ease, Latinate nominalization, deletion-creativity + mechanical
   inversion) all failed to invert it.
2. **The engineers ran out of reachable signal.** Gen-6: 1/9 accepted. Gen-7:
   2/6, both weak (0.027-0.052); the properly-implemented "untried mechanisms"
   all failed on the merits — full MTLD was a behavioral duplicate (r=0.89),
   frequency residualization was near-constant, bigram-transition surprisal had
   negative SEP. The uncovered causal nodes are uncovered because wordfreq-level
   statistics cannot reach them, not because nobody tried.
3. **Convergence mode = red-team exhaustion, and it exposes a harness design
   flaw worth fixing**: hardest-first keeps the 10 lowest-margin candidates
   REGARDLESS of sign, so when every attack fails, the eval absorbs
   champion-friendly pairs and the champion's measured fitness inflates. A
   growing adversarial eval only stays hard while the red team stays
   competitive; the keep rule should require margin below a threshold (or
   discard the batch) so failed attacks cannot dilute the eval.

## Terminal state

- Final champion: `structural_diversity_content_gated` (gen 4, Haiku) —
  structural diversity of the rewrite conjunctively gated by content lexical
  rarity. SEP 0.154 train / 0.198 frozen heldout / 0.359 stationary core, with
  the eval grown to 110 pairs (77 train / 33 heldout) across 9 adversarial axes.
- The design's formal early-stop (2 stale gens) did not fire only because
  failed attacks inflated gen-7 heldout — an artifact, not progress. Declared
  converged on the substantive evidence above.
- Remaining uncovered nodes (semantic_distance, concreteness norms, true
  surprisal, the frequency confound) all require resources beyond wordfreq
  unigrams: embeddings, concreteness norms, or an LM — the same external-
  resource ceiling identified in every prior phase. The loop found everything
  its toolbox could express.
