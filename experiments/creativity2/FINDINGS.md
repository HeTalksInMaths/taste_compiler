# EVO2 findings — did the agent architecture surface a novel scorer?

Verdict against the pre-declared success criteria (DESIGN.md §7): **YES.**

## Trajectory (fitness = SEP = mean(score_pos) − mean(score_neg), both scored individually, all scorers in [0,1])

| gen | train | heldout | champion | SEP | acc | pos | neg | heldout SEP | core SEP |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 29 | 13 | combinational_novelty (seed) | 0.072 | 0.66 | 0.87 | 0.79 | 0.059 | 0.212 |
| 1 | 33 | 15 | syntactic_elaboration_delta (llm) | 0.032 | 0.52 | 0.51 | 0.48 | 0.018 | −0.003 |
| 2 | 37 | 17 | **skeleton_preserved_insertion_novelty (llm)** | **0.129** | 0.73 | 0.30 | 0.17 | **0.161** | **0.202** |
| 3 | 41 | 19 | skeleton_preserved_insertion_novelty | 0.074 | 0.66 | 0.29 | 0.21 | 0.121 | 0.202 |

Adversarial axes added per gen (each targeting the sitting champion):
gen1 = synonym-churn confound; gen2 = syntactic padding vs creative compression;
gen3 = register-rarity confound + restructuring penalty.

## The discovered scorer

**skeleton_preserved_insertion_novelty** (gen-2 engineer):
`LCS preservation ratio of the anchor's content-word order (Wagner–Fischer) ×
logistic surprisal gate on ONLY the newly inserted content words (wordfreq
reference calibration)` — "novelty of what is new, given you kept what worked."

Why it satisfies each success criterion:
1. **Novel on all three operational tests**: margin-vector |r| < 0.6 vs every
   incumbent; measures the then-uncovered coherence node with a named mechanism;
   leakage-clean (30 content tokens, 0 lifted, all closed-class).
2. **Improves the frozen heldout** (never shown to any agent): SEP 0.161 at
   birth vs prior champion's 0.018; stationary core 0.202 vs −0.003.
3. **Survives axes it was not bred against**: still champion after the
   padding-vs-compression pairs (merged post-birth) and after the gen-3
   register-rarity attack — degraded (train 0.129→0.074, heldout 0.161→0.121)
   but positive on every split, with the stationary core unchanged at 0.202.

Also accepted: `restructuring_vs_churn` (gen 3, NOVEL: Jaccard set overlap ×
Kendall-tau order decorrelation) — a genuinely new mechanism but a narrow
specialist (SEP 0.023; fires rarely).

## The selection gates earned their keep

Across 9 proposals: 3 accepted, 6 rejected — every rejection for a stated,
verifiable reason:
- **Behavioral-novelty gate caught 3 disguised duplicates** that sounded novel:
  zipf_band_dispersion ("spread not mean", r=0.75), novelty_per_edit_efficiency
  (r=0.94!), cliche bundle density (r=0.72). Mechanistic novelty claims do not
  survive contact with margin-vector correlation.
- **Fitness gate** rejected novel-but-useless (lexical_chain_coherence, −0.055;
  edit_locality_gini, −0.029).
- **Leakage gate** rejected concrete_imagery_shift (42>40 content tokens) — a
  borderline call (its lists were closed-class + suffixes), noted as a
  calibration point, but the rule held without exceptions.

## The adversarial loop worked as designed

Every red-team round produced a new decoupling axis that materially damaged the
sitting champion (synonym churn drove the seed champion NEGATIVE; padding
attacked elaboration; register-rarity + restructuring cut the skeleton champion
nearly in half on train). The champion that survived did so by being the only
scorer whose mechanism — conjunctive preservation × insertion novelty — is not
a single-axis signal.

## Honest caveats and the open wound

- SEP magnitudes are small (0.05–0.2 on [0,1] scores): real but modest
  separations on a hard, adversarially-hardened eval; ~40 train pairs is small.
- The champion's documented weakness stands: its insertion gate uses MEAN
  surprisal, so Latinate hedge-filler ("subsequently, ostensibly, preliminary")
  opens it while common-word images ("the ice stops talking") do not. The gen-3
  red pairs encoding this are now in train/heldout — closing this requires a
  combinational-freshness gate (are inserted words unusual NEIGHBORS for their
  context), which needs co-occurrence data beyond wordfreq unigrams, or
  embeddings (proxy-blocked).
- Eval labels remain LLM-authored; human ratings are the outstanding validation.
- restructuring_vs_churn's tiny score range (0.04/0.02) suggests the [0,1]
  contract needs a per-scorer dynamic-range requirement, not just spread ≥ 0.05.
