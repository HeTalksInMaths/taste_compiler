"""
NLP probe functions for text quality measurement.

These probes were originally embedded in a HELPER_CODE string that was exec'd
into the scorer namespace. They are now proper Python functions that get injected
into the runner namespace via load_probes().
"""

import re
import math
import statistics


# ─────────────────────────────────────────────────────────────────────
# WORD SETS
# ─────────────────────────────────────────────────────────────────────

STOP = set("the and for are but not all can had was one our out did its get may say she too use".split())

HYPE_WORDS = set(
    "best ultimate revolutionary groundbreaking guaranteed amazing incredible "
    "effortless instant world-class perfect magic most-advanced industry-leading unmatched".split()
)

JARGON_WORDS = set(
    "advanced seamless intelligent robust scalable innovative optimised synergistic "
    "platform solution engine experience world-class next-generation transformative".split()
)

FAKE_MECH_PHRASES = [
    "leveraging our advanced",
    "through intelligent automation",
    "using our seamless",
    "synergistically optimises",
    "powered by advanced technology",
    "next-generation solution",
    "our innovative platform",
]


# ─────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────

def _clamp(x):
    """Clamp value to [0.0, 1.0]."""
    try:
        return float(max(0.0, min(1.0, float(x or 0))))
    except (TypeError, ValueError):
        return 0.0


def _ctoks(s):
    """Extract content tokens (3+ letter words, lowercased, stop words removed)."""
    return set(t for t in re.findall(r'[a-zA-Z]{3,}', (s or '').lower()) if t not in STOP)


def _action_words(s):
    """Extract action verbs from text."""
    av = {"save", "reduce", "increase", "identify", "surface", "flag", "detect", "show", "track",
          "measure", "rank", "eliminate", "convert", "automate", "close", "discover", "build", "test",
          "map", "trace", "score", "filter", "parse"}
    return {t for t in _ctoks(s) if t in av}


def _domain_nouns(s):
    """Extract domain-specific nouns from text."""
    dn = {"account", "customer", "churn", "revenue", "sprint", "ticket", "objection", "pipeline",
          "backlog", "query", "report", "metric", "team", "lead", "deal", "conversion", "retention",
          "candidate", "review", "onboarding", "approval", "deployment"}
    return {t for t in _ctoks(s) if t in dn}


# ─────────────────────────────────────────────────────────────────────
# SOURCE FIDELITY PROBES (F4 split)
# ─────────────────────────────────────────────────────────────────────

def violates_hard_source_policy(text, anchor):
    """Hard source policy check — invented numerics or guarantee words."""
    nums_a = set(re.findall(r'\b\d+(?:\.\d+)?%?\b', anchor or ''))
    nums_t = set(re.findall(r'\b\d+(?:\.\d+)?%?\b', text or ''))
    if nums_t - nums_a:
        return True
    low = (text or '').lower()
    if any(g in low for g in ["guaranteed", "100%", "never fails", "zero errors"]):
        return True
    return False


def probe_source_continuity(text, anchor):
    """Soft continuity — token overlap weighted by action words and domain nouns."""
    a, t = _ctoks(anchor), _ctoks(text)
    if not a:
        return 0.5
    overlap = len(a & t) / len(a)
    act_a, act_t = _action_words(anchor), _action_words(text)
    noun_a, noun_t = _domain_nouns(anchor), _domain_nouns(text)
    act_ov = len(act_a & act_t) / max(1, len(act_a)) if act_a else 0.5
    noun_ov = len(noun_a & noun_t) / max(1, len(noun_a)) if noun_a else 0.5
    return _clamp(0.5 * overlap + 0.25 * act_ov + 0.25 * noun_ov)


# ─────────────────────────────────────────────────────────────────────
# F6: ARGUMENT PROGRESSION
# ─────────────────────────────────────────────────────────────────────

def probe_argument_progression(text):
    """Detect problem→mechanism→result structure."""
    low = (text or '').lower()
    problem_markers = ["instead of", "no more", "stop ", "tired of", "without ", "before ",
                       "chasing", "waiting", "guessing", "struggling"]
    mechanism_markers = ["by ", "because", "through", "uses ", "connects", "maps ", "traces",
                         "flags ", "surfaces", "ranks ", "so that"]
    result_markers = [" so ", "which means", "enabling", "giving", "letting", "making it",
                      "so you can", "so your"]
    has_p = any(m in low for m in problem_markers)
    has_m = any(m in low for m in mechanism_markers)
    has_r = any(m in low for m in result_markers)
    if has_p and has_m and has_r:
        return 1.0
    if has_m and has_r:
        return 0.7
    if has_p and has_r:
        return 0.5
    if has_m:
        return 0.4
    return 0.0


# ─────────────────────────────────────────────────────────────────────
# F6: REAL MECHANISM QUALITY
# ─────────────────────────────────────────────────────────────────────

def probe_real_mechanism_quality(text):
    """Score causal markers followed by concrete terms vs jargon."""
    low = (text or '').lower()
    causal_markers = ["by ", "because", "so that", "which means", "through ", "enables", "allows", "helps "]
    concrete_terms = {"backlog", "ticket", "account", "customer", "sprint", "pipeline", "lead", "query",
                      "report", "code", "review", "objection", "onboarding", "approval", "metric",
                      "signal", "pattern", "record", "item", "step", "rule", "flag", "threshold"}
    score = 0.0
    for marker in causal_markers:
        idx = low.find(marker)
        while idx >= 0:
            window = low[idx:idx + 80]
            tokens = re.findall(r'[a-zA-Z]{3,}', window)
            concrete_after = sum(1 for t in tokens if t in concrete_terms)
            fake_after = sum(1 for phrase in FAKE_MECH_PHRASES if phrase in window)
            score += concrete_after * 0.15 - fake_after * 0.4
            idx = low.find(marker, idx + 1)
    return _clamp(score)


# ─────────────────────────────────────────────────────────────────────
# F6: ABSTRACT JARGON DENSITY
# ─────────────────────────────────────────────────────────────────────

def probe_abstract_jargon_density(text):
    """Measure density of abstract jargon words in content tokens."""
    toks = re.findall(r'[a-zA-Z]{3,}', (text or '').lower())
    hits = sum(1 for t in toks if t in JARGON_WORDS)
    return _clamp(hits / max(1, len(toks) / 10))


# ─────────────────────────────────────────────────────────────────────
# F6: SPECIFICITY WITHOUT INVENTION
# ─────────────────────────────────────────────────────────────────────

def probe_specificity_without_invention(text, anchor):
    """Specificity that zeros if hard source policy is violated."""
    if violates_hard_source_policy(text, anchor):
        return 0.0
    toks = re.findall(r'[a-zA-Z]{3,}', (text or '').lower())
    caps = len(re.findall(r'\b[A-Z][a-z]{2,}\b', text or ''))
    avs = {"identify", "surface", "flag", "detect", "show", "track", "rank", "eliminate", "convert", "automate"}
    av_hits = sum(1 for t in toks if t in avs)
    jargon = sum(1 for t in toks if t in JARGON_WORDS)
    return _clamp(caps * 0.08 + av_hits * 0.15 - jargon * 0.06)


# ─────────────────────────────────────────────────────────────────────
# EXISTING PROBES (rewritten to use soft continuity)
# ─────────────────────────────────────────────────────────────────────

def probe_causal_density(text):
    """Causal connective density per sentence."""
    markers = ["because", "since", "therefore", "which means", "so that", "works by",
               "based on", "through", "by ", "as a result", "enables", "allows", "helps", "leading to"]
    low = (text or '').lower()
    hits = sum(1 for m in markers if m in low)
    sents = max(1, len(re.split(r'[.!?]', text.strip())))
    return _clamp(hits / max(1, sents * 1.5))


def probe_specificity(text):
    """General specificity: action verbs and named entities vs abstractions."""
    toks = re.findall(r'[a-zA-Z]{3,}', (text or '').lower())
    av = {"identify", "surface", "flag", "detect", "show", "track", "rank", "save", "reduce",
          "increase", "eliminate", "convert", "automate", "close"}
    ab = {"solution", "platform", "system", "framework", "innovation", "experience", "value",
          "quality", "seamless", "advanced", "intelligent", "robust", "scalable"}
    return _clamp(len(re.findall(r'\b[A-Z][a-z]{2,}\b', text or '')) * 0.08
                  + sum(1 for t in toks if t in av) * 0.15
                  - sum(1 for t in toks if t in ab) * 0.05)


def probe_audience_relevance(text):
    """Before-state markers + second-person pronoun density."""
    low = (text or '').lower()
    before = sum(1 for p in ["instead of", "rather than", "no more", "used to", "stop ",
                             "tired of", "struggling", "without having to"] if p in low)
    second_p = len(re.findall(r'\b(you|your)\b', low))
    words = max(1, len(text.split()))
    return _clamp(before * 0.3 + (second_p / max(1, words / 8)) * 0.5)


def probe_persuasion_risk(text):
    """Hype word density — high = persuasion knowledge trigger risk."""
    low = (text or '').lower()
    flags = ["best", "ultimate", "revolutionary", "game-changing", "groundbreaking", "effortless",
             "instant", "guaranteed", "amazing", "incredible", "unmatched", "world-class", "perfect", "magic"]
    words = max(1, len(text.split()))
    hits = sum(1 for f in flags if f in low)
    return _clamp(hits / max(1, words / 15))


def probe_epistemic_calibration(text):
    """Hedge density vs superlative density — well-calibrated = higher score."""
    low = (text or '').lower()
    hedges = sum(1 for m in ["often", "may ", "typically", "for many", "in most", "usually",
                             "can ", "sometimes"] if m in low)
    superlatives = sum(1 for m in ["best", "ultimate", "revolutionary", "groundbreaking",
                                   "guaranteed", "amazing", "incredible", "effortless", "instant",
                                   "world-class", "perfect"] if m in low)
    words = max(1, len(text.split()))
    supra_density = superlatives / max(1, words / 20)
    if supra_density > 0.4:
        return _clamp(0.1 - supra_density * 0.1)
    return _clamp(0.5 + hedges * 0.1 - superlatives * 0.1)


# ─────────────────────────────────────────────────────────────────────
# PROBE LOADING
# ─────────────────────────────────────────────────────────────────────

def load_probes(py_ns):
    """
    Inject all probe functions and helpers into the runner namespace.
    This makes them available to scorer code that references them by name.
    """
    py_ns["_clamp"] = _clamp
    py_ns["_ctoks"] = _ctoks
    py_ns["_action_words"] = _action_words
    py_ns["_domain_nouns"] = _domain_nouns
    py_ns["STOP"] = STOP
    py_ns["HYPE_WORDS"] = HYPE_WORDS
    py_ns["JARGON_WORDS"] = JARGON_WORDS
    py_ns["FAKE_MECH_PHRASES"] = FAKE_MECH_PHRASES
    py_ns["violates_hard_source_policy"] = violates_hard_source_policy
    py_ns["probe_source_continuity"] = probe_source_continuity
    py_ns["probe_argument_progression"] = probe_argument_progression
    py_ns["probe_real_mechanism_quality"] = probe_real_mechanism_quality
    py_ns["probe_abstract_jargon_density"] = probe_abstract_jargon_density
    py_ns["probe_specificity_without_invention"] = probe_specificity_without_invention
    py_ns["probe_causal_density"] = probe_causal_density
    py_ns["probe_specificity"] = probe_specificity
    py_ns["probe_audience_relevance"] = probe_audience_relevance
    py_ns["probe_persuasion_risk"] = probe_persuasion_risk
    py_ns["probe_epistemic_calibration"] = probe_epistemic_calibration
