"""skeleton_preserved_insertion_novelty — coherence via preserved content-word
order, gated by the novelty of only the inserted material.

Mechanism: coherence approximated as skeletal continuity — the LCS (Wagner &
Fischer 1974) ratio of the anchor's CONTENT-word sequence surviving in order in
the rewrite, after stripping closed grammatical classes (Quirk et al. 1985
style inventory: pronouns, determiners, auxiliaries, conjunctions,
prepositions, particles — not content words). Minimal apt edits keep the
skeleton (ratio near 1); heavy relexicalization breaks content-word order.
Preservation alone rewards doing nothing, so it is multiplied by a logistic
gate on the mean surprisal of ONLY the unmatched (new) content words vs the
wordfreq top-5000 reference mean: "novelty of what is new, given you kept what
worked" — conjunctive, but from different primitives than the incumbent
novelty*appropriateness product.
"""

import math
import re
import statistics

from wordfreq import top_n_list, word_frequency

_WORD = re.compile(r"[a-zA-Z']+")

# Closed grammatical classes only (Quirk et al. 1985 inventory style).
_PRONOUNS = frozenset(
    "i me my mine myself you your yours yourself yourselves he him his himself she her hers "
    "herself it its itself we us our ours ourselves they them their theirs themselves this "
    "that these those who whom whose which what someone something everyone everything nobody "
    "nothing anybody anything anyone none one ones".split()
)
_DETERMINERS = frozenset("a an the some any each every no all both either neither several".split())
_AUXILIARIES = frozenset(
    "be am is are was were been being have has had having do does did doing will would shall "
    "should can could may might must ought".split()
)
_CONJUNCTIONS = frozenset(
    "and but or nor for yet so although though because since unless while whereas if when "
    "whenever before after until than as".split()
)
_PREPOSITIONS = frozenset(
    "aboard about above across after against along amid among around at before behind below "
    "beneath beside besides between beyond but by concerning despite down during except for "
    "from in inside into like near of off on onto out outside over past since through "
    "throughout till to toward towards under underneath until unto up upon with within without"
    .split()
)
_PARTICLES = frozenset(
    "not to there here very too also just only even quite rather more most less least own".split()
)

_FUNCTION = _PRONOUNS | _DETERMINERS | _AUXILIARIES | _CONJUNCTIONS | _PREPOSITIONS | _PARTICLES


def _tokens(s):
    return _WORD.findall((s or "").lower())


def _content_tokens(s):
    return [t for t in _tokens(s) if t not in _FUNCTION]


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
_GATE_SPREAD = max(_REF_STD, 1e-3)


def _lcs_matched_b_indices(a, b):
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        ai = a[i - 1]
        row, prow = dp[i], dp[i - 1]
        for j in range(1, m + 1):
            if ai == b[j - 1]:
                row[j] = prow[j - 1] + 1
            else:
                row[j] = row[j - 1] if row[j - 1] >= prow[j] else prow[j]
    matched = set()
    i, j = n, m
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            matched.add(j - 1)
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return dp[n][m], matched


def skeleton_preserved_insertion_novelty(text, anchor):
    if not text or not anchor:
        return 0.05
    a_c = _content_tokens(anchor)
    b_c = _content_tokens(text)
    if not a_c or not b_c:
        return 0.05

    lcs_len, matched_b = _lcs_matched_b_indices(a_c, b_c)
    preservation = lcs_len / len(a_c)

    novel = [b_c[j] for j in range(len(b_c)) if j not in matched_b]
    if not novel:
        return 0.0

    mean_surp = sum(_surprisal(t) for t in novel) / len(novel)
    z = (mean_surp - _REF_MEAN) / _GATE_SPREAD
    gate = 1.0 / (1.0 + math.exp(-z))

    score = preservation * gate
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "skeleton_preserved_insertion_novelty": skeleton_preserved_insertion_novelty,
}
