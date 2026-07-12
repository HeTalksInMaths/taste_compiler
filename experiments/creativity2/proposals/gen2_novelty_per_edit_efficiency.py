"""novelty_per_edit_efficiency — word_frequency_confound corrected by
edit-normalized surprisal gain.

Mechanism: novelty priced per edit spent (economy-of-production; Simonton BVSR /
MDL spirit). Compute (1) token-level Levenshtein distance (Levenshtein 1966)
between anchor and rewrite, and (2) total surprisal EXCESS over the reference
mean (wordfreq top-5000, import-time) of only the changed/inserted tokens.
Efficiency = gain / (edit_distance + 1). A minimal edit landing one fresh
low-frequency image is efficient (tiny denominator, real numerator); heavy
synonym-churn racks up edit distance to buy its rarity, so the ratio collapses.
This is the direct antidote to the incumbents the churn axis broke: n-gram
divergence and mean surprisal both reward churn because neither divides rarity
gained by editing spent.
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
    words = [w for w in top_n_list("en", 5000) if w.isalpha()]
    if not words:
        return 10.0, 2.0
    vals = [_surprisal(w) for w in words]
    return sum(vals) / len(vals), (statistics.pstdev(vals) or 1.0)


_REF_MEAN, _REF_STD = _reference_stats()
_SCALE = max(_REF_STD, 1e-3)
_SHIFT = 1.0  # ratio must clear one reference std before crossing 0.5


def _levenshtein(a, b):
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def novelty_per_edit_efficiency(text, anchor):
    if not text or not anchor:
        return 0.05
    a_tok = _tokens(anchor)
    b_tok = _tokens(text)
    if not b_tok:
        return 0.05

    dist = _levenshtein(a_tok, b_tok)

    sm = difflib.SequenceMatcher(a=a_tok, b=b_tok, autojunk=False)
    gain = 0.0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                gain += max(0.0, _surprisal(b_tok[j]) - _REF_MEAN)

    efficiency = gain / (dist + 1.0)
    z = efficiency / _SCALE - _SHIFT
    score = 1.0 / (1.0 + math.exp(-z))
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "novelty_per_edit_efficiency": novelty_per_edit_efficiency,
}
