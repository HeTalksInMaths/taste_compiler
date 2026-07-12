"""edit_locality_gini — metaphor_novelty via spatial concentration of surprisal change.

Mechanism: Gini coefficient (Gini 1912; Lorenz-curve concentration statistic)
applied to the per-token surprisal-gain vector from aligning rewrite to anchor
with difflib.SequenceMatcher (Ratcliff-Obershelp). A fresh apt image is a POINT
insertion: one or two tokens carry a large surprisal spike, the rest match the
anchor exactly — maximally unequal distribution, Gini near 1. Synonym-churn
changes many tokens by similar moderate amounts — near-equal distribution, Gini
near 0 — despite far larger total edit volume. Operationalizes "novelty
concentrated in one span vs spread everywhere", which elaboration density,
n-gram divergence and mean surprisal cannot see. A logistic gate (calibrated on
mean/std of per-token surprisal over wordfreq's top-5000, computed at import)
suppresses concentrated-but-banal edits.
"""

import difflib
import math
import re
import statistics

from wordfreq import top_n_list, word_frequency

_WORD = re.compile(r"[a-zA-Z']+")


def _tokens(s):
    return _WORD.findall((s or "").lower())


def _surprisal(tok):
    p = word_frequency(tok, "en")
    if p <= 0:
        p = 1e-9
    return -math.log2(p)


def _reference_stats():
    """Mean/std of per-token surprisal over wordfreq's top-5000 wordlist —
    import-time reference from the library's bundled data, never eval pairs."""
    words = [w for w in top_n_list("en", 5000) if w.isalpha()]
    if not words:
        return 10.0, 2.0
    vals = [_surprisal(w) for w in words]
    return sum(vals) / len(vals), (statistics.pstdev(vals) or 1.0)


_REF_MEAN, _REF_STD = _reference_stats()
_GATE_SPREAD = max(_REF_STD * 0.5, 1e-3)


def _gini(values):
    n = len(values)
    total = sum(values)
    if total <= 1e-12:
        return None
    sv = sorted(values)
    weighted_sum = sum((i + 1) * v for i, v in enumerate(sv))
    g = (2.0 * weighted_sum) / (n * total) - (n + 1.0) / n
    return max(0.0, min(1.0, g))


def edit_locality_gini(text, anchor):
    if not text or not anchor:
        return 0.05
    a_tok = _tokens(anchor)
    b_tok = _tokens(text)
    if not b_tok:
        return 0.05

    sm = difflib.SequenceMatcher(a=a_tok, b=b_tok, autojunk=False)
    weights = [0.0] * len(b_tok)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                weights[j] = _surprisal(b_tok[j])

    changed = [w for w in weights if w > 0]
    if not changed:
        return 0.05

    mean_surp = sum(changed) / len(changed)
    z = (mean_surp - _REF_MEAN) / _GATE_SPREAD
    gate = 1.0 / (1.0 + math.exp(-z))

    g = _gini(weights)
    if g is None:
        return 0.05

    return float(max(0.0, min(1.0, g * gate)))


METRICS = {
    "edit_locality_gini": edit_locality_gini,
}
