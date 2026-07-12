"""cliche_formulaicity_bundle_density — structural (frequency-free) detection
of formulaic sequences via Biber lexical-bundle scaffolding.

Mechanism: Biber, Conrad & Cortes 2004; Biber et al. 1999 — recurrent lexical
bundles ("at the end of the", "on the other hand") are built almost entirely
from CLOSED grammatical classes with one or two open slots: the fixed
scaffolding is what repeats. Slide the standard 4-word window; flag it
bundle-shaped when at least half its tokens are closed-class function words.
Score = 0.7 * (1 - bundle density) + 0.3 * reduction vs the anchor's own
density. Deliberately touches no word frequency, staying mechanistically
distinct from every rarity/surprisal scorer.

Targets uncovered node: cliche_formulaicity.
"""

import re

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

_N = 4       # Biber, Conrad & Cortes (2004): four-word bundles.
_THRESH = 2  # at least half the window is closed-class scaffolding.


def _tokens(s):
    return _WORD.findall((s or "").lower())


def _bundle_density(tokens):
    if len(tokens) < _N:
        return 0.0
    n_windows = len(tokens) - _N + 1
    hits = 0
    for i in range(n_windows):
        window = tokens[i:i + _N]
        fc = sum(1 for t in window if t in _FUNCTION)
        if fc >= _THRESH:
            hits += 1
    return hits / n_windows


def cliche_formulaicity_bundle_density(text, anchor):
    if not text:
        return 0.05
    toks = _tokens(text)
    if len(toks) < _N:
        return 0.5

    text_density = _bundle_density(toks)
    anchor_toks = _tokens(anchor)
    anchor_density = _bundle_density(anchor_toks) if len(anchor_toks) >= _N else text_density

    absolute_term = 1.0 - text_density
    relative_term = max(0.0, anchor_density - text_density)

    score = 0.7 * absolute_term + 0.3 * relative_term
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "cliche_formulaicity_bundle_density": cliche_formulaicity_bundle_density,
}
