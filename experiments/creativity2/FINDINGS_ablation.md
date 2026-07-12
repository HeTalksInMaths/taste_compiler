# Ablation: is it the model or the evolution that drives discovery?

Two arms, identical harness/seeds/gates/fitness/initial eval. Sonnet arm:
3 proposals + 6 kept pairs per gen, 3 agent-generations. Haiku arm: 6-9
proposals + 10 kept pairs per gen (3x mutation volume, ~2x adversarial growth),
5 agent-generations.

## Head-to-head

| | Sonnet arm | Haiku arm |
|---|---|---|
| agent generations | 3 | 5 |
| scorer proposals | 9 | 33 |
| accepted | 3 (33%) | 11 (33%) |
| disguised duplicates caught by |r| gate | 3 | 12 |
| champion turnovers | 2 | 4 (incl. one regression) |
| final champion | skeleton_preserved_insertion (gen 2) | structural_diversity_content_gated (gen 4) |
| final champion train SEP | 0.074 | 0.139 |
| final champion frozen-heldout SEP | 0.121 | 0.187 |
| final champion STATIONARY CORE SEP (same 6 pairs both arms) | 0.202 | **0.359** |
| strongest red-team attack | margins −0.68..−0.48 | margins **−1.0 × 10** (maximum) |
| eval size at end | 41 train / 19 heldout | 63 train / 27 heldout |

(Heldout sets diverge across arms after gen 0 — grown by different red teams —
so heldout SEP is only roughly comparable; the STATIONARY CORE is the same six
original pairs in both arms and is the honest cross-arm metric.)

## Trajectory shapes (the real difference)

- **Sonnet**: clean two-step — one weak novel champion (gen 1), then the robust
  discovery (gen 2) that held its crown through two targeted attack rounds.
- **Haiku**: chaotic then convergent — champion turnover every generation for
  three rounds (including an overfit champion, core SEP −0.009, that the
  stationary tier caught, and a total −1.0×10 annihilation), a regression to a
  gen-1 scorer, and THEN a breakthrough at gen 4 that held and improved through
  the gen-5 attack (0.158→0.187 heldout).

## Verdict: evolution drives it; the model sets the pace, not the destination

1. **Acceptance rate was identical (33%)** at both model tiers — the gates, not
   the proposer, set the quality bar. Haiku produced 4x more disguised
   duplicates, and the margin-correlation gate caught every one.
2. **Attack is model-insensitive.** Haiku red teams matched and then exceeded
   Sonnet's attack strength (the −1.0 sweep is the hardest hit in either arm).
   Finding a scorer's blind spot is easier than building a scorer.
3. **Synthesis is model-sensitive but volume-compensable.** Haiku needed ~3x
   the proposals and +2 generations to reach a robust conjunctive champion —
   but it got there, and on the only strictly comparable metric (stationary
   core) its champion is stronger (0.359 vs 0.202).
4. **The loop's memory did real work in both arms.** Each breakthrough
   immediately followed the orchestrator feeding back the previous
   generations' lesson (Sonnet gen 2: "no scorer is strong on both sets";
   Haiku gen 4: "single-proxy scorers die; conjunctive survives"). The
   evolutionary system here is not just selection — it is selection +
   adversarial pressure + explicit lesson-passing in context, and that loop,
   not raw model intelligence, is what converts failures into designs.
5. **Convergent discovery is evidence about the problem, not the model.** Both
   arms independently converged on the same design grammar: anchor-relative
   structure gated conjunctively by an orthogonal signal. When two different
   models under the same pressure find the same shape, the shape belongs to
   the fitness landscape.

## Caveats

- One run per arm; no seed replicates — trajectory noise is real (champion
  turnover order could differ on another seed).
- Haiku got 2 extra generations and a progressively harder/larger eval; core
  SEP is the only clean cross-arm comparison.
- Haiku's gen-4 breakthrough is behaviorally correlated (r=0.85) with an
  earlier scorer — a robustness improvement within a family rather than a new
  behavioral axis; the Sonnet discovery was decorrelated novel.
- All eval labels remain LLM-authored; the stationary core is only 6 pairs.
