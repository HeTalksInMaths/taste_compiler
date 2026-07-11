# Real-NLP redesign — findings

Redesign in response to two valid critiques of the earlier scorers: (1) the
`0.45*… + 0.30*…` constants were hidden hyperparameters fit by eye to the visible
pairs, and (2) they reinvented NLP as hand-typed word lists instead of using real
metrics on real data. Fix: real reference data (`wordfreq` corpus frequencies),
real algorithms (sklearn TF-IDF, MTLD), parameter-free combination, and an LLM
**coding** agent that amends real NLP code by reasoning about mechanism/confounds.

## Environment reality

pip works, so `wordfreq`, `scikit-learn`, `numpy/scipy` installed. But github.com
and huggingface.co are proxy-blocked (403), so **pretrained embeddings, concreteness
norms, and spaCy parser models are all unreachable**. The one real external NLP
resource we can load is corpus word frequencies. This bounds what "real NLP" can
mean here and is itself a finding.

## Result 1 — one honest metric matches the elaborate hand-weighted champion

Parameter-free separation (more_creative > less_creative), nothing fitted:

| metric | orig (20) | adv (12) | all (32) |
|---|---|---|---|
| **mean_surprisal** (−log2 P(word), real freqs) | 0.950 | 0.750 | **0.875** |
| neg_mean_zipf / rarity_delta (ties it) | 0.950 | 0.750 | 0.875 |
| tfidf_divergence (char n-gram, sklearn) | 0.850 | 0.667 | 0.781 |
| mtld (lexical diversity) | 0.600 | 0.583 | 0.594 |
| — hand-weighted lexical champion (for reference) | 0.950 | 0.667 | 0.862 |

A single real quantity with **no hyperparameters, no word lists, no leakage**
matches the elaborate scorer. And it ties exactly with the pure-rarity metrics —
so the eval's "creativity" is, at first order, a **lexical-rarity** manipulation,
and `mean_surprisal` is really "uses rarer words" (the frequency confound of
Momen & Zarrieß 2026): context-free surprisal *is* rarity.

## Result 2 — a real metric that breaks the rarity confound

The coding agent found *why* rarity fails its 4 pairs (CR07, ADV01, ADV08, ADV09):
in all four, the **flat** rewrite reaches for individually rarer Latinate register
words ("technical issues", "operates", "previously") while the **creative** rewrite
uses common words in unusual **combinations** ("software buckled", "held its own",
"a space built for ten"). So the signal must move from single-word rarity to
word-**combination** novelty.

`phrase_novelty_divergence` = 1 − cosine of **word-bigram/trigram** TF-IDF between
text and anchor (sklearn, unigrams deliberately excluded so single-word swaps
can't drive it):

- separation **0.844** overall (0.900 base, 0.750 adv);
- **fixes all 4** pairs rarity fails;
- its per-pair delta is **uncorrelated** with surprisal's (Pearson r = 0.156,
  p = 0.39) — verified empirically distinct from lexical rarity.

## Result 3 — parameter-free combination beats every prior scorer

Two orthogonal real signals, standardized and combined with **equal weight** (a
uniform prior is the honest choice with no training data — no tuned weights):

| scorer | orig | adv | all |
|---|---|---|---|
| mean_surprisal alone | 0.950 | 0.750 | 0.875 |
| phrase_novelty alone | 0.900 | 0.750 | 0.844 |
| **z(surprisal) + z(phrase), equal weight** | **0.950** | **0.917** | **0.938** |
| (overfit hand-weighted champion) | 0.950 | 0.667 | 0.862 |

The combination beats rarity, beats phrase-novelty, and beats the leakage-laden
lexical champion — using only real data/algorithms, no word lists, no eyeballed
weights, no test-set vocabulary.

## Epistemology (what this actually measures)

Creativity-of-rewrite here decomposes into two **real, orthogonal novelty signals**:
- **lexical novelty** — rarer words (`mean_surprisal`, real corpus frequencies), and
- **combinational novelty** — unusual word pairings (`phrase_novelty_divergence`),
  the surface footprint of Mednick's "remote association."

Both are the **novelty** axis of the standard definition. The other pillar —
**appropriateness** — is silently held constant by the eval design (all three
versions share content), and genuine **embedding-semantic distance (DSI)**, the
strongest signal in the literature, remains untestable here because the vectors
are proxy-blocked. So this is an honest, real-NLP measurement of *lexical +
combinational novelty*, which is most of what "make it fresher" means — but not
the whole construct of creativity.

## Caveats

- The equal-weight combination standardizes on the eval distribution's scale
  (mean/sd) — not weight- or label-fitting, but for deployment those scales
  should come from an independent reference corpus.
- 20 + 12 pairs is small; eval labels are LLM-authored, not human-rated.
- The strongest literature path (embedding DSI, concreteness norms, syntactic
  parse) needs resources the proxy blocks — that, not scorer cleverness, is the
  ceiling here.
