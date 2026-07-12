"""zipf_band_dispersion — metaphor_novelty via frequency-band contrast.

Mechanism: Laufer & Nation (1995) Lexical Frequency Profile — describe a text
by the SPREAD of its vocabulary across corpus-frequency bands, not one mean;
Fauconnier & Turner (1998, 2002) conceptual blending — novel figuration yokes
a familiar frame to an unexpected one, whose textual footprint is words drawn
from MULTIPLE frequency bands at once (everyday anchor word next to a markedly
rarer, specific one). Flat prose — cliched (uniformly common) OR purple
(uniformly rare) — clusters in one band.

Construct: SD (second moment) of content-word Zipf frequencies within the
text, delta'd against the anchor's own SD, logistic-squashed with scale = the
probability-weighted Zipf SD of wordfreq's top-50k lexicon (import-time
reference, never eval-fit).

Orthogonal to incumbents: rarity metrics summarize the SAME distribution by
its MEAN; this uses its SPREAD, which moves independently (equal-rarity
synonym swaps raise mean, not spread; one rare word beside common ones raises
spread, barely mean).

Failure mode: 2-3 content words give a noisy SD; a remote pairing of two
similar-frequency words shows no band contrast despite being a real metaphor.
"""

import math
import re

import numpy as np
from wordfreq import zipf_frequency, word_frequency, top_n_list

_WORD = re.compile(r"[a-zA-Z']+")

STOP = set(
    "a an the and or but if then else of to in on at by for with from as is are was were "
    "be been being it its this that these those i you he she we they me him her us them my "
    "your his their our not no so do does did have has had will would can could should may "
    "might must about into over under out up down off than too very just also".split()
)


def _toks(s):
    return _WORD.findall((s or "").lower())


def _content(s):
    return [t for t in _toks(s) if t not in STOP and len(t) > 1]


def _band_sd(s):
    toks = _content(s)
    if len(toks) < 2:
        return 0.0
    zs = [zipf_frequency(w, "en") for w in toks]
    return float(np.std(zs))


def _ref_zipf_dispersion(n=50000):
    """Probability-weighted SD of Zipf frequency across wordfreq's top-n
    lexicon — the typical spread of word rarity in English, from the lexicon
    alone, computed once at import time."""
    words = top_n_list("en", n)
    ps = np.array([word_frequency(w, "en") for w in words])
    zs = np.array([zipf_frequency(w, "en") for w in words])
    mask = ps > 0
    ps = ps[mask]
    zs = zs[mask]
    ps = ps / ps.sum()
    mean_z = float((ps * zs).sum())
    var_z = float((ps * (zs - mean_z) ** 2).sum())
    return math.sqrt(var_z)


_ZIPF_SD_REF = _ref_zipf_dispersion()
_SCALE = _ZIPF_SD_REF if _ZIPF_SD_REF > 1e-6 else 1.0


def zipf_band_dispersion(text, anchor):
    dt = _band_sd(text)
    da = _band_sd(anchor)
    delta = dt - da
    score = 1.0 / (1.0 + math.exp(-delta / _SCALE))
    return float(max(0.0, min(1.0, score)))


METRICS = {
    "zipf_band_dispersion": zipf_band_dispersion,
}
