"""concrete_imagery_shift — concreteness/imageability without norm downloads,
via Latinate abstract-suffix morphology.

Mechanism: Paivio 1971 dual-coding; Cortese & Fugett 2004 / Reilly & Kean 2007
— morphological structure correlates with norm-rated abstractness: Latinate
nominalizing suffixes (-tion, -ment, -ness, -ity, -ance, -ism...) mark abstract
coinages, while concrete/imageable vocabulary is typically bare and short.
Brysbaert norms are download-blocked, so this is a deterministic morphological
proxy. Scores the SHIFT toward concreteness relative to the anchor ("show,
don't tell"), blended with a mild absolute floor; logistic spread calibrated at
import from chunked abstractness-ratio variance over wordfreq's top-20k list.

Targets uncovered node: concreteness_imageability.
"""

import math
import re
import statistics

from wordfreq import top_n_list

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

# Morphological suffix fragments (not whole words) marking abstract nominalizations.
_ABSTRACT_SUFFIXES = (
    "tion", "sion", "ment", "ness", "ity", "ance", "ence",
    "ism", "ology", "acy", "hood", "ship",
)


def _tokens(s):
    return _WORD.findall((s or "").lower())


def _content_tokens(s):
    return [t for t in _tokens(s) if t not in _FUNCTION and len(t) > 2]


def _abstractness_ratio(tokens):
    if not tokens:
        return 0.5
    hits = sum(1 for t in tokens if t.endswith(_ABSTRACT_SUFFIXES))
    return hits / len(tokens)


def _reference_abstractness_spread():
    """Spread of the abstractness-ratio statistic over fixed-size chunks of
    wordfreq's top-20k list — a natural scale computed at import, never from
    eval pairs."""
    words = [w for w in top_n_list("en", 20000) if w.isalpha() and len(w) > 2]
    if not words:
        return 0.3
    window = 12
    ratios = []
    for i in range(0, len(words) - window, window):
        chunk = words[i:i + window]
        hits = sum(1 for t in chunk if t.endswith(_ABSTRACT_SUFFIXES))
        ratios.append(hits / window)
    if not ratios:
        return 0.3
    spread = statistics.pstdev(ratios)
    return spread if spread > 1e-3 else 0.3


_SPREAD = _reference_abstractness_spread()


def concrete_imagery_shift(text, anchor):
    if not text or not anchor:
        return 0.05
    a_c = _content_tokens(anchor)
    b_c = _content_tokens(text)
    if not a_c or not b_c:
        return 0.05

    abs_a = _abstractness_ratio(a_c)
    abs_b = _abstractness_ratio(b_c)
    delta = abs_a - abs_b  # positive => rewrite became MORE concrete

    z = delta / _SPREAD
    gate = 1.0 / (1.0 + math.exp(-z))

    score = 0.7 * gate + 0.3 * (1.0 - abs_b)
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "concrete_imagery_shift": concrete_imagery_shift,
}
