"""Real-NLP creativity metric library — parameter-free, no fitted weights.

Every function here is a genuine, named metric from the phase-2 measurement map,
implemented on REAL reference data (wordfreq's corpus frequencies) or a
well-defined algorithm (MTLD, TF-IDF cosine) — NOT hand-typed word lists with
eyeballed weights. Because we have no training data, nothing here has tunable
hyperparameters: each metric returns a single principled quantity, and the
anchor-relative variants return a delta (text minus its source), which is the
only defensible framing for the creativity of a *revision*.

Deps: wordfreq (real SUBTLEX/corpus frequencies), scikit-learn, numpy.
"""

import math
import re
import numpy as np
from wordfreq import word_frequency, zipf_frequency
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_WORD = re.compile(r"[a-zA-Z']+")

# A minimal, standard stopword set (function words carry little creative signal).
STOP = set(
    "a an the and or but if then else of to in on at by for with from as is are was were "
    "be been being it its this that these those i you he she we they me him her us them my "
    "your his their our not no so do does did have has had will would can could should may "
    "might must about into over under out up down off than too very just also".split()
)


def tokens(s):
    return _WORD.findall((s or "").lower())


def content_tokens(s):
    return [t for t in tokens(s) if t not in STOP and len(t) > 1]


# ── Information content / surprisal (real frequencies) ──────────────────
def mean_surprisal(text):
    """Mean Shannon surprisal -log2 P(word) over content words, from real corpus
    frequencies (wordfreq). Higher = less predictable word choice. This is the
    information-theoretic novelty signal from the measurement map, on real data."""
    toks = content_tokens(text)
    if not toks:
        return 0.0
    vals = []
    for w in toks:
        p = word_frequency(w, "en")
        vals.append(-math.log2(p) if p > 0 else 24.0)  # cap OOV at ~1/16M
    return float(np.mean(vals))


def mean_zipf(text):
    """Mean Zipf frequency of content words (Brysbaert scale, real data).
    LOWER = rarer vocabulary. Returned as-is; callers negate for a rarity score."""
    toks = content_tokens(text)
    if not toks:
        return 7.0
    return float(np.mean([zipf_frequency(w, "en") for w in toks]))


def pct_rare(text, zipf_thresh=3.0):
    """Fraction of content words below a rarity threshold (Zipf<3 = rare)."""
    toks = content_tokens(text)
    if not toks:
        return 0.0
    return float(np.mean([zipf_frequency(w, "en") < zipf_thresh for w in toks]))


# ── Lexical diversity (parameter-free algorithm) ───────────────────────
def mtld(text, threshold=0.72):
    """Measure of Textual Lexical Diversity (McCarthy & Jarvis 2010) — the
    standard length-robust lexical-diversity metric. threshold=0.72 is the
    canonical value from the original paper, not a tuned hyperparameter."""
    toks = tokens(text)
    if len(toks) < 10:
        # too short for MTLD's factor logic; fall back to TTR
        return len(set(toks)) / max(1, len(toks))

    def _factors(seq):
        factors = 0.0
        types = set()
        count = 0
        for w in seq:
            count += 1
            types.add(w)
            ttr = len(types) / count
            if ttr <= threshold:
                factors += 1
                types, count = set(), 0
        if count > 0:
            ttr = len(types) / count
            factors += (1 - ttr) / (1 - threshold)
        return factors

    f_fwd = _factors(toks)
    f_bwd = _factors(list(reversed(toks)))
    n = len(toks)
    fwd = n / f_fwd if f_fwd > 0 else n
    bwd = n / f_bwd if f_bwd > 0 else n
    return float((fwd + bwd) / 2.0)


# ── Semantic/surface divergence from the anchor (real vectorizer) ──────
def tfidf_divergence(text, anchor):
    """1 - cosine similarity between char-n-gram TF-IDF vectors of text and
    anchor. A real vectorization (sklearn), but LEXICAL not embedding-semantic —
    it measures how much the rewrite's surface form departs from its source.
    (True embedding DSI needs pretrained vectors, blocked by the proxy here.)"""
    if not (text and anchor):
        return 0.0
    try:
        v = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        m = v.fit_transform([anchor, text])
        sim = float(cosine_similarity(m[0], m[1])[0, 0])
        return 1.0 - sim
    except ValueError:
        return 0.0


# ── Anchor-relative deltas (the portable framing, on real metrics) ─────
def surprisal_delta(text, anchor):
    """How much MORE information-dense the rewrite is than its source."""
    return mean_surprisal(text) - mean_surprisal(anchor)


def rarity_delta(text, anchor):
    """How much rarer the rewrite's vocabulary is than its source (Zipf drop)."""
    return mean_zipf(anchor) - mean_zipf(text)


def mtld_delta(text, anchor):
    return mtld(text) - mtld(anchor)


# ── Registry: name -> (callable, needs_anchor, higher_is_more_creative) ─
METRICS = {
    "mean_surprisal":     (lambda t, a: mean_surprisal(t), False, True),
    "neg_mean_zipf":      (lambda t, a: -mean_zipf(t),      False, True),
    "pct_rare":           (lambda t, a: pct_rare(t),        False, True),
    "mtld":               (lambda t, a: mtld(t),            False, True),
    "tfidf_divergence":   (lambda t, a: tfidf_divergence(t, a), True, True),
    "surprisal_delta":    (lambda t, a: surprisal_delta(t, a),  True, True),
    "rarity_delta":       (lambda t, a: rarity_delta(t, a),     True, True),
    "mtld_delta":         (lambda t, a: mtld_delta(t, a),       True, True),
}
