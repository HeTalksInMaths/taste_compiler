"""lexical_chain_coherence — coherence via lexical/reference cohesion ties.

Mechanism: Halliday & Hasan (1976) "Cohesion in English": sentences tie into a
text via (1) LEXICAL cohesion (reiteration of a content word / its family
across sentence boundaries; Hoey 1991: bond strength scales with the shared
term's specificity/rarity) and (2) REFERENCE cohesion (anaphora pointing back).
Construct: rarity-weighted shared stems between adjacent sentences + closed-
class anaphoric/connective credit, normalized by sentence length, squashed by
1 - exp(-raw/SD) with SD = token-weighted surprisal SD of wordfreq's top-50k
lexicon (import-time reference, never eval-fit).

Orthogonal to incumbents: never compares text to anchor; never rewards a word
for being rare in isolation — a rare word only counts if REPEATED/referred to
(a cohesive tie needs two occurrences). Operationalizes the coherence ->
appropriateness edge, the constraint side of the causal graph.

Failure mode: elegant-variation texts that avoid literal repetition and use no
connective score 0.0 — "no detected cohesion evidence", not "incoherent".
"""

import math
import re

import numpy as np
from wordfreq import word_frequency, top_n_list

_WORD = re.compile(r"[a-zA-Z']+")

STOP = set(
    "a an the and or but if then else of to in on at by for with from as is are was were "
    "be been being it its this that these those i you he she we they me him her us them my "
    "your his their our not no so do does did have has had will would can could should may "
    "might must about into over under out up down off than too very just also".split()
)

# Closed class: anaphoric reference devices (Halliday & Hasan "reference").
_REFERENCE = frozenset(
    "it its this that these those they them their he she him her his itself such same".split()
)

# Closed class: canonical discourse connectives (Halliday & Hasan "conjunction").
_CONNECTIVES = frozenset(
    "however therefore thus meanwhile nevertheless moreover furthermore consequently "
    "subsequently afterward afterwards then finally still yet besides hence accordingly "
    "instead otherwise meantime thereafter likewise similarly after before since while "
    "when because although though".split()
)


def _toks(s):
    return _WORD.findall((s or "").lower())


def _content(s):
    return [t for t in _toks(s) if t not in STOP and len(t) > 1]


def _sentences(text):
    parts = re.split(r"[.!?]+", text or "")
    return [p.strip() for p in parts if p.strip()]


def _stem(w):
    """Crude inflectional stemmer (closed morphological operation)."""
    if len(w) > 5 and w.endswith("ing"):
        return w[:-3]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("ed"):
        return w[:-2]
    if len(w) > 4 and w.endswith("es"):
        return w[:-2]
    if len(w) > 4 and w.endswith("ly"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _ref_surprisal_sd(n=50000):
    words = top_n_list("en", n)
    ps = np.array([word_frequency(w, "en") for w in words])
    ps = ps[ps > 0]
    ps = ps / ps.sum()
    sur = -np.log2(ps)
    mu = float((ps * sur).sum())
    sd = float(math.sqrt((ps * (sur - mu) ** 2).sum()))
    return mu, sd


_MU, _SD = _ref_surprisal_sd()


def lexical_chain_coherence(text, anchor):
    sents = _sentences(text)
    if len(sents) < 2:
        return 0.5  # cannot assess cross-sentence cohesion; neutral
    total = 0.0
    npairs = 0
    for i in range(len(sents) - 1):
        c1 = _content(sents[i])
        c2 = _content(sents[i + 1])
        if not c1 or not c2:
            continue
        stems1 = {}
        for w in c1:
            stems1.setdefault(_stem(w), w)
        stems2 = set(_stem(w) for w in c2)
        shared = set(stems1) & stems2
        weight = 0.0
        for st in shared:
            w = stems1[st]
            p = word_frequency(w, "en")
            surprisal = -math.log2(p) if p > 0 else 24.0
            weight += surprisal

        toks2 = _toks(sents[i + 1])
        ref_hits = sum(1 for t in toks2 if t in _REFERENCE)
        weight += min(ref_hits, 3) * _MU * 0.25

        conn_hits = sum(1 for t in toks2[:3] if t in _CONNECTIVES)
        weight += conn_hits * _MU * 0.5

        denom = max(1.0, (len(c1) + len(c2)) / 2.0)
        total += weight / denom
        npairs += 1

    if npairs == 0:
        return 0.5
    raw = total / npairs
    score = 1.0 - math.exp(-raw / _SD)
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "lexical_chain_coherence": lexical_chain_coherence,
}
