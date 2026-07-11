"""Atomic feature probes — the merge alphabet for phase 7.

Each scorer S1..S5 is a composition of a few sub-signals. Here we expose those
sub-signals as standalone features f(text, anchor) -> float, so the merge search
can recombine them and the per-feature diagnostic can ask which raw signal (if
any) still tracks creativity once the cliché cue is decoupled (phase 6).

Lexicons are imported from scorers_build so features match the scorers exactly.
"""

import os
import re
import sys
import math
import collections
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from scorers_build import (  # noqa: E402
    COMMON_WORDS, COMMON_BIGRAMS, CLICHE_PHRASES, GENERIC_VERBS,
    STOCK_INTENSIFIERS, CONCRETE_WORDS, ABSTRACT_WORDS, DEAD_VEHICLES,
    SEMANTIC_FIELDS,
)

COMMON = set(COMMON_WORDS)
BIGRAMS = set(COMMON_BIGRAMS)
GVERBS = set(GENERIC_VERBS)
INTENS = set(STOCK_INTENSIFIERS)
CONCRETE = set(CONCRETE_WORDS)
ABSTRACT = set(ABSTRACT_WORDS)
DEAD = set(DEAD_VEHICLES)


def _toks(s):
    return [t for t in re.findall(r"[a-zA-Z']+", (s or "").lower())]


def _content(s):
    return [t for t in _toks(s) if t not in COMMON and len(t) > 2]


def _sents(s):
    parts = [p.strip() for p in re.split(r"[.!?]+", s or "") if p.strip()]
    return parts if parts else [""]


def _clamp(x):
    return max(0.0, min(1.0, x))


# ── S3 core: formulaicity (higher = more formulaic). reward = 1 - this ──
def _formulaicity(s):
    low = " " + " ".join(_toks(s)) + " "
    toks = _toks(s)
    if not toks:
        return 1.0
    cliche_hits = sum(1 for c in CLICHE_PHRASES if c in low)
    pairs = [toks[i] + " " + toks[i + 1] for i in range(len(toks) - 1)]
    bigram_cov = sum(1 for p in pairs if p in BIGRAMS) / max(1, len(pairs))
    gverbs = sum(1 for t in toks if t in GVERBS) / max(1, len(toks))
    intens = sum(1 for t in toks if t in INTENS)
    return (min(1.0, cliche_hits * 0.45)
            + min(1.0, bigram_cov / 0.35) * 0.5
            + min(1.0, gverbs / 0.18) * 0.35
            + min(1.0, intens * 0.30)) / 2.3


def f_antiformulaic_abs(text, anchor):
    return _clamp(1.0 - _formulaicity(text))


def f_antiformulaic_rel(text, anchor):
    ft = _formulaicity(text)
    fa = _formulaicity(anchor) if anchor and _toks(anchor) else ft
    return _clamp(0.5 + (fa - ft))


def f_cliche_only(text, anchor):
    """Isolated cliché-phrase signal (reward = absence of stock phrases)."""
    low = " " + " ".join(_toks(text)) + " "
    hits = sum(1 for c in CLICHE_PHRASES if c in low)
    return _clamp(1.0 - min(1.0, hits * 0.5))


# ── S1: rarity, bigram freshness, fluency band ──
def f_rarity(text, anchor):
    content = [t for t in _toks(text) if len(t) > 2]
    if not content:
        return 0.0
    return _clamp(sum(1 for t in content if t not in COMMON) / len(content))


def f_bigram_fresh(text, anchor):
    toks = _toks(text)
    if len(toks) < 2:
        return 0.0
    pairs = [toks[i] + " " + toks[i + 1] for i in range(len(toks) - 1)]
    fresh = sum(1 for p in pairs if p not in BIGRAMS) / len(pairs)
    return _clamp((fresh - 0.55) / 0.45)


def f_fluency_band(text, anchor):
    toks = _toks(text)
    if not toks:
        return 0.0
    func_ratio = sum(1 for t in toks if t in COMMON) / len(toks)
    return _clamp(1.0 - abs(func_ratio - 0.52) / 0.52)


# ── S2: between-sentence divergence (peaked), semantic-field mixing ──
def f_divergence(text, anchor):
    sents = _sents(text)
    if len(sents) < 2:
        return 0.5
    a = collections.Counter(_content(sents[0]))
    b = collections.Counter(_content(sents[1]))
    dot = sum(a[t] * b.get(t, 0) for t in a)
    na = math.sqrt(sum(v * v for v in a.values())) or 1.0
    nb = math.sqrt(sum(v * v for v in b.values())) or 1.0
    divergence = 1.0 - dot / (na * nb)
    return _clamp(1.0 - abs(divergence - 0.75) / 0.75)


def f_field_mix(text, anchor):
    tokset = set(_toks(text))
    hit = sum(1 for words in SEMANTIC_FIELDS.values() if tokset & set(words))
    return {0: 0.25, 1: 0.55, 2: 1.0, 3: 1.0, 4: 0.7}.get(hit, 0.4)


# ── S4: figurative concreteness contrast ──
def f_figurative(text, anchor):
    toks = _toks(text)
    if len(toks) < 3:
        return 0.0
    n = len(toks)
    conc_idx = [i for i, t in enumerate(toks) if t in CONCRETE]
    abst_idx = [i for i, t in enumerate(toks) if t in ABSTRACT]
    low = " ".join(toks)
    fig = 0.0
    for m in re.finditer(r"\b(like a|like the|as if|as though|is a|was a|into a)\s+(\w+)\s*(\w*)", low):
        vehicle = m.group(3) if m.group(2) in ("small", "big", "old", "new", "quiet", "slow") else m.group(2)
        if vehicle in DEAD:
            fig -= 0.15
        elif vehicle in CONCRETE:
            fig += 0.45
        elif vehicle in ABSTRACT:
            fig += 0.05
    contrast = 0.0
    for ai in abst_idx:
        if any(abs(ai - ci) <= 6 for ci in conc_idx):
            contrast += 0.2
    contrast = min(0.6, contrast)
    density = len(conc_idx) / n
    imagery = (1.0 - abs(density - 0.14) / 0.14 if density <= 0.28 else 0.5)
    imagery = max(0.0, imagery) * 0.4
    return _clamp(0.15 + fig + contrast + imagery * 0.5)


def f_concrete_density(text, anchor):
    """Isolated concrete-imagery density (a cleaner read of vivid grounding)."""
    toks = _toks(text)
    if not toks:
        return 0.0
    return _clamp(sum(1 for t in toks if t in CONCRETE) / max(1.0, len(toks) / 6.0))


# ── S5: frequency-residualized recombination ──
def f_resid_recomb(text, anchor):
    toks = _toks(text)
    if len(toks) < 8:
        return 0.0
    xs, ys = [], []
    for i in range(len(toks) - 1):
        w1, w2 = toks[i], toks[i + 1]
        x = ((w1 not in COMMON) + (w2 not in COMMON)) / 2.0
        pair = w1 + " " + w2
        y = 1.0
        if pair in BIGRAMS:
            y = 0.0
        else:
            for c in CLICHE_PHRASES:
                if pair in c:
                    y = 0.2
                    break
        xs.append(x)
        ys.append(y)
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx > 1e-9 else 0.0
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    common_resid = [r for r, x in zip(resid, xs) if x <= 0.5]
    signal = statistics.mean(common_resid) if common_resid else statistics.mean(resid)
    return _clamp(0.5 + signal * 1.8)


# Feature registry: name -> (function, theorized sign toward "more creative")
FEATURES = {
    "antiformulaic_abs": (f_antiformulaic_abs, +1),
    "antiformulaic_rel": (f_antiformulaic_rel, +1),
    "cliche_only": (f_cliche_only, +1),
    "rarity": (f_rarity, +1),
    "bigram_fresh": (f_bigram_fresh, +1),
    "fluency_band": (f_fluency_band, +1),
    "divergence": (f_divergence, +1),
    "field_mix": (f_field_mix, +1),
    "figurative": (f_figurative, +1),
    "concrete_density": (f_concrete_density, +1),
    "resid_recomb": (f_resid_recomb, +1),
}
