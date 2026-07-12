"""restructuring_vs_churn — perspective-shifting rewrites vs synonym churn.

Mechanism: Boden 1990 combinational/exploratory creativity — rearranging
existing elements into a new configuration is genuine originality. Strip closed
grammatical classes; compute (1) Jaccard overlap (Jaccard 1912) of the two
content-word SETS and (2) Kendall's tau (Kendall 1938) between anchor-position
and rewrite-position of shared content words. High set overlap + low order
agreement = the same ideas re-SEEN from a new vantage (voice/agency flips
surface automatically); low set overlap = lexical churn, not rewarded. Score =
jaccard * (1 - |tau|). Complements the champion, whose LCS mechanism treats
reordering as broken coherence.
"""

import re

from scipy.stats import kendalltau

_WORD = re.compile(r"[a-zA-Z']+")

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


def _order_positions(a_c, b_c):
    """Nth occurrence of each shared content-word type in anchor matched to
    Nth occurrence in rewrite; returns parallel position arrays."""
    a_pos_by_type = {}
    for idx, tok in enumerate(a_c):
        a_pos_by_type.setdefault(tok, []).append(idx)
    b_pos_by_type = {}
    for idx, tok in enumerate(b_c):
        b_pos_by_type.setdefault(tok, []).append(idx)

    pos_a, pos_b = [], []
    for tok, a_positions in a_pos_by_type.items():
        b_positions = b_pos_by_type.get(tok)
        if not b_positions:
            continue
        for pa, pb in zip(a_positions, b_positions):
            pos_a.append(pa)
            pos_b.append(pb)
    return pos_a, pos_b


def restructuring_vs_churn(text, anchor):
    if not text or not anchor:
        return 0.05
    a_c = _content_tokens(anchor)
    b_c = _content_tokens(text)
    if not a_c or not b_c:
        return 0.05

    set_a, set_b = set(a_c), set(b_c)
    union = set_a | set_b
    if not union:
        return 0.05
    jaccard = len(set_a & set_b) / len(union)

    pos_a, pos_b = _order_positions(a_c, b_c)
    if len(pos_a) >= 2:
        tau, _ = kendalltau(pos_a, pos_b)
        if tau != tau:  # NaN guard
            tau = 1.0
        reorder_degree = 1.0 - abs(tau)
    else:
        reorder_degree = 0.0

    score = jaccard * reorder_degree
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "restructuring_vs_churn": restructuring_vs_churn,
}
