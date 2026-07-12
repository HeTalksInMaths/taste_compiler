"""syntactic_elaboration_delta — elaboration_detail via subordination growth.

Mechanism: Hunt (1965) T-unit/subordination index; Ortega (2003, Applied
Linguistics) — subordinator/preposition density as the standard parse-free
proxy for syntactic elaboration; TTCT "elaboration" subscale (added
circumstantial/qualifying detail around the core proposition).

Construct: density of a CLOSED grammatical class — prepositions +
subordinating conjunctions + relative pronouns (surface markers of PP and
subordinate/relative clauses) — per token; scored as the GROWTH from anchor to
rewrite, logistic-squashed with scale = aggregate wordfreq probability mass of
the marker class itself (import-time reference, never eval-fit).

Orthogonal to incumbents: no content-word frequency lookup at all — identical-
rarity rewrites differ here only by added phrase/clause structure.

Failure mode: purely lexical elaboration (one vivid adjective, no new phrase)
is invisible; creative COMPRESSION scores negative by design.
"""

import math
import re

from wordfreq import word_frequency

_WORD = re.compile(r"[a-zA-Z']+")

# Closed class: core English prepositions (Quirk et al. 1985 inventory).
_PREPOSITIONS = frozenset(
    "aboard about above across after against along amid among around at before behind "
    "below beneath beside besides between beyond but by concerning despite down during "
    "except for from in inside into like near of off on onto out outside over past "
    "since through throughout till to toward towards under underneath until unto up "
    "upon with within without".split()
)

# Closed class: subordinating conjunctions + relative pronouns (Quirk et al. 1985).
_SUBORDINATORS = frozenset(
    "after although as because before if since so than that though unless until when "
    "whenever where whereas wherever while whether which who whom whose".split()
)

_MARKERS = _PREPOSITIONS | _SUBORDINATORS


def _tokens(s):
    return _WORD.findall((s or "").lower())


def _marker_density(s):
    toks = _tokens(s)
    if not toks:
        return 0.0
    return sum(1 for t in toks if t in _MARKERS) / len(toks)


def _ref_marker_mass():
    """Aggregate corpus probability mass of the marker class (wordfreq),
    computed once at import — the natural unit of marker-density variation."""
    total = 0.0
    for w in _MARKERS:
        p = word_frequency(w, "en")
        if p > 0:
            total += p
    return total


_P_REF = _ref_marker_mass()
_SCALE = _P_REF if _P_REF > 1e-6 else 0.15


def syntactic_elaboration_delta(text, anchor):
    if not text:
        return 0.0
    d = _marker_density(text) - _marker_density(anchor or "")
    score = 1.0 / (1.0 + math.exp(-d / _SCALE))
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "syntactic_elaboration_delta": syntactic_elaboration_delta,
}
