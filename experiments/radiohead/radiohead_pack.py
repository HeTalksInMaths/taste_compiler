"""Radiohead-songwriting domain pack for the EvalWeaver evolutionary loop.

This module is the *content* layer for a new taste task: "make this lyric more
Radiohead." It plugs into the existing, domain-general evolution engine
(evalweaver/evolution.py) through the same hooks the persuasion domain uses —
a probe registry (the gene alphabet), a base pair suite, adversarial-pair
templates, anchors, and a scorer renderer.

The taste map (what "more Radiohead" rewards / punishes), and how each trap
mirrors a persuasion-pipeline trap:

    REWARD   concrete physical imagery   (vs naming the feeling abstractly)
             plain, flat diction          (vs ornate "poetic" diction)
             unease / dread tone          (the affect)
             estrangement / 2nd person    (dissociation, modernity)
             restraint / repetition        (mantra refrain)

    PENALTY  cliché density               (broken-heart / tears-like-rain pop)
             abstract poeticism           (heart/soul/forever/ethereal/crimson)

    TRAPS    cliche_trap     ~ hype_trap          (stock emotion that sounds deep)
             abstract_emotion ~ fake_mechanism    (names the feeling, doesn't embody)
             poeticism_trap  ~ specificity_trap   (ornate diction, anti-Radiohead)
             forced_uplift   ~ source_drift       (resolves the dread into hope)

Nothing here imports torch/NLP models — the probes are cheap lexical heuristics,
exactly like the persuasion probes, so the whole loop stays deterministic and
offline.
"""

import re

from evalweaver.policy import (
    DEFAULT_SOURCE_POLICY,
    hard_source_policy_violated,
    probe_source_continuity,
)


def _clamp(x):
    try:
        return float(max(0.0, min(1.0, float(x or 0))))
    except (TypeError, ValueError):
        return 0.0


def _toks(s):
    return re.findall(r"[a-zA-Z']+", (s or "").lower())


# ─────────────────────────────────────────────────────────────────────
# WORD SETS — the Radiohead lexicon (cheap heuristics, contrastive by design)
# ─────────────────────────────────────────────────────────────────────

CONCRETE_NOUNS = set("""
teeth skin spine lungs bones hair hands throat eyes knees ribs blood tongue nails
engine wire wires screen motorway plastic concrete neon siren camera lift radiator
kettle fridge freezer boiler tap phone television pylon traffic road car cars glass
lightbulb wallpaper carpet curtain curtains hallway kitchen ceiling floor window
windows door doors fence gutter drain pavement streetlight bus train platform
pig pigs rats rat fish crow crows dog dogs moth flies wasp insects
ice rain frost smoke fog sleet wind damp mud snow ash dust rust
""".split())

ABSTRACT_POETIC = set("""
heart hearts soul souls dream dreams forever eternity eternal beautiful beauty
magical magic destiny angel angels paradise ethereal crimson golden gold whisper
whispers embrace longing spirit glory infinite profound despair sorrow sweet tender
divine radiant shimmering moonlight starlight doth thee thy thou wander shores
endless yearning grace heavenly bliss serene wondrous precious treasured
""".split())

CLICHE_PHRASES = [
    "broken heart", "tears like rain", "tears fall", "crying tears", "hold me",
    "deep inside", "set me free", "set you free", "fly away", "shining star",
    "every breath", "in your eyes", "true love", "forever and always",
    "sweet embrace", "my heart bleeds", "heart bleeds", "the sun will shine",
    "the sun will rise", "love will set", "endless pain", "burning desire",
    "tears of joy", "light of my life", "you complete me", "meant to be",
]

UNEASE_WORDS = set("""
wrong broken slow slowly cold drowning drown rot rotten rotting choke choking sick
quiet empty gravity falling fall fell crack cracks cracked peel peels peeling hum
hums humming hiss hissing flicker flickers flickering tick ticks ticking still numb
grey gray blur blurs drip drips dripping scream screams screaming damp stuck shut
shaking trembling buzzing static dead hollow thin paralysed paralyzed sinking
""".split())

ESTRANGE_MARKERS = [
    "you ", "your ", "yourself", "i'm not", "this isn't", "not here", "in my place",
    "somebody else", "don't recognise", "don't recognize", "i forget", "not myself",
    "out of body", "behind glass", "watching myself",
]


# ─────────────────────────────────────────────────────────────────────
# PROBES — the gene alphabet (all return floats in [0,1])
# ─────────────────────────────────────────────────────────────────────

def probe_concrete_image(text):
    """Density of concrete, physical/modern nouns — Radiohead grounds dread in objects."""
    toks = _toks(text)
    hits = sum(1 for t in toks if t in CONCRETE_NOUNS)
    return _clamp(hits / max(1.0, len(toks) / 8.0))


def probe_abstract_poeticism(text):
    """PENALTY: abstract-emotion and ornate-poetic vocabulary (heart/soul/ethereal)."""
    toks = _toks(text)
    hits = sum(1 for t in toks if t in ABSTRACT_POETIC)
    return _clamp(hits / max(1.0, len(toks) / 9.0))


def probe_cliche_density(text):
    """PENALTY: stock pop-sad clichés (broken heart, tears like rain...)."""
    low = (text or "").lower()
    hits = sum(1 for ph in CLICHE_PHRASES if ph in low)
    return _clamp(hits * 0.34)


def probe_plain_diction(text):
    """Flat, plain diction — fraction of short words minus ornate long-word drag."""
    toks = _toks(text)
    if not toks:
        return 0.0
    short = sum(1 for t in toks if len(t) <= 4)
    ornate = sum(1 for t in toks if len(t) >= 9)
    return _clamp(short / len(toks) - ornate / max(1.0, len(toks)) * 0.5)


def probe_unease_tone(text):
    """Dread / wrongness lexicon density — the Radiohead affect."""
    toks = _toks(text)
    hits = sum(1 for t in toks if t in UNEASE_WORDS)
    return _clamp(hits / max(1.0, len(toks) / 10.0))


def probe_estrangement(text):
    """Second-person address + dissociation markers — alienation, not confession."""
    low = " " + (text or "").lower() + " "
    hits = sum(1 for m in ESTRANGE_MARKERS if m in low)
    return _clamp(hits / 3.0)


def probe_restraint_repetition(text):
    """Mantra-like repetition: content tokens that recur (anaphora / refrain)."""
    toks = [t for t in _toks(text) if len(t) >= 3]
    if not toks:
        return 0.0
    counts = {}
    for t in toks:
        counts[t] = counts.get(t, 0) + 1
    repeats = sum(c - 1 for c in counts.values() if c >= 2)
    return _clamp(repeats * 0.4)


def violates_hard_source_policy(text, anchor):
    """Mirror of the persuasion veto; effectively inert on lyric content
    (only fires on invented numbers/guarantees/awards), kept for contract parity."""
    return hard_source_policy_violated(text, anchor)


# ─────────────────────────────────────────────────────────────────────
# PROBE REGISTRY (gene alphabet) + engine-facing metadata
# ─────────────────────────────────────────────────────────────────────

PROBE_CALLS = {
    "concrete_image": "probe_concrete_image(text)",
    "plain_diction": "probe_plain_diction(text)",
    "unease_tone": "probe_unease_tone(text)",
    "estrangement": "probe_estrangement(text)",
    "restraint_repetition": "probe_restraint_repetition(text)",
    "cliche_density": "probe_cliche_density(text)",
    "abstract_poeticism": "probe_abstract_poeticism(text)",
}

PENALTY_PROBES = {"cliche_density", "abstract_poeticism"}
REWARD_PROBES = [p for p in PROBE_CALLS if p not in PENALTY_PROBES]

PROBE_SEMANTICS = {
    "concrete_image": "Density of concrete physical/modern nouns (teeth, motorway, fridge, frost).",
    "plain_diction": "Flat plain diction: short-word fraction minus ornate long words.",
    "unease_tone": "Dread/wrongness lexicon density (cold, drowning, flicker, numb).",
    "estrangement": "Second-person address + dissociation markers (you/yourself, 'not here').",
    "restraint_repetition": "Mantra-like repeated content tokens (refrain/anaphora).",
    "cliche_density": "PENALTY: stock pop-sad clichés (broken heart, tears like rain).",
    "abstract_poeticism": "PENALTY: abstract-emotion / ornate-poetic words (soul, forever, ethereal).",
}

# Which probes plausibly close each trap (biases mutation + immigrant genomes).
GAP_PROBES = {
    "cliche_trap": ["cliche_density", "concrete_image"],
    "abstract_emotion": ["abstract_poeticism", "concrete_image", "unease_tone"],
    "poeticism_trap": ["abstract_poeticism", "plain_diction"],
    "forced_uplift": ["unease_tone", "estrangement"],
}


def load_radiohead_probes(py_ns):
    """Inject the Radiohead probes + shared helpers into the runner namespace,
    so scorer code can call them by name (drop-in for evalweaver.probes.load_probes)."""
    py_ns["_clamp"] = _clamp
    py_ns["probe_concrete_image"] = probe_concrete_image
    py_ns["probe_abstract_poeticism"] = probe_abstract_poeticism
    py_ns["probe_cliche_density"] = probe_cliche_density
    py_ns["probe_plain_diction"] = probe_plain_diction
    py_ns["probe_unease_tone"] = probe_unease_tone
    py_ns["probe_estrangement"] = probe_estrangement
    py_ns["probe_restraint_repetition"] = probe_restraint_repetition
    py_ns["violates_hard_source_policy"] = violates_hard_source_policy
    py_ns["probe_source_continuity"] = probe_source_continuity


# ─────────────────────────────────────────────────────────────────────
# SCORER RENDERER (genome → code) — Radiohead version
# ─────────────────────────────────────────────────────────────────────

def render_scorer_code(genome):
    """Render a genome as a readable Radiohead scorer. Mirrors the persuasion
    renderer but gates on cliché density instead of jargon density."""
    lines = [
        "def scorer(text, anchor, params):",
        "    if violates_hard_source_policy(text, anchor):",
        "        return 0.0",
    ]
    gate = genome.get("jargon_gate")  # reused slot — here it's the cliché gate
    if gate is not None:
        lines += [
            f"    if probe_cliche_density(text) > {gate:.2f}:",
            "        return _clamp(probe_concrete_image(text) * 0.1)",
        ]
    lines.append("    base = 0.0")
    for t in genome["terms"]:
        sign = "-" if t["probe"] in PENALTY_PROBES else "+"
        lines.append(f"    base {sign}= {t['weight']:.2f} * {PROBE_CALLS[t['probe']]}")
    prod = genome.get("product")
    if prod:
        a, b = prod
        lines.append(f"    base += {genome['product_weight']:.2f} * {PROBE_CALLS[a]} * {PROBE_CALLS[b]}")
    cb = genome.get("continuity_blend", 0.0)
    if cb > 0.01:
        lines.append("    continuity = probe_source_continuity(text, anchor)")
        lines.append(f"    return _clamp(base * ({1 - cb:.2f} + {cb:.2f} * continuity))")
    else:
        lines.append("    return _clamp(base)")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────
# BASE PAIR SUITE — flat emotional "drafts" (anchor) vs Radiohead positive /
# trap negative. R0_T* are the frozen heldout.
# ─────────────────────────────────────────────────────────────────────

def _p(pid, anchor, positive, negative, ptype, trap):
    return {
        "pair_id": pid, "anchor": anchor, "positive": positive, "negative": negative,
        "pair_type": ptype, "source_policy": {**DEFAULT_SOURCE_POLICY},
        "label_contract": "Positive embodies the feeling in concrete plain imagery; negative is the trap.",
        "intended_trap": trap,
    }


ALL_PAIRS_R0 = [
    # ── cliche_trap ──
    _p("R0_C01", "I feel alone tonight and I don't know what to do.",
       "I feel alone tonight — the fridge hums, the phone stays dark, the radiator ticks and won't get warm.",
       "I feel alone tonight, my broken heart is bleeding, crying tears like rain, longing for your sweet embrace.",
       "cliche_trap", "Stock pop heartbreak sounds emotional but is dead language."),
    _p("R0_C02", "I miss the way things used to be.",
       "I miss the way things used to be — the same bus, the wet road, the streetlight that never quite came on.",
       "I miss the way things used to be, when true love filled my heart and you were the shining star in my eyes.",
       "cliche_trap", "Greeting-card nostalgia."),
    _p("R0_C03", "I can't sleep again tonight.",
       "I can't sleep again — the boiler clicks, a dog barks three streets over, the ceiling cracks won't hold still.",
       "I can't sleep again tonight, my aching heart cries out for you, set me free, let love light up the dark.",
       "cliche_trap", "Hollow romantic cliché."),
    # ── abstract_emotion ──
    _p("R0_A01", "Everything is falling apart and I can't cope.",
       "Everything is falling apart — the wallpaper peels, the kettle screams, I keep my coat on indoors.",
       "Everything is falling apart and I am consumed by such profound sadness and endless aching pain inside.",
       "abstract_emotion", "Names the feeling instead of embodying it."),
    _p("R0_A02", "I am so anxious I can barely breathe.",
       "I can barely breathe — the strip light flickers, the lift's out of order, my hands won't warm up.",
       "I can barely breathe, drowning in infinite despair and overwhelming sorrow that floods my weary soul.",
       "abstract_emotion", "Abstract emotion-naming."),
    _p("R0_A03", "I feel numb and disconnected from everyone.",
       "I feel numb — cars hiss past on the wet road, the television talks to no one, the curtains don't quite shut.",
       "I feel numb and disconnected, lost in profound emptiness and a deep eternal melancholy beyond all words.",
       "abstract_emotion", "Tells the feeling abstractly."),
    # ── poeticism_trap ──
    _p("R0_P01", "The city feels cold and I feel like a stranger.",
       "The city feels cold — concrete and neon, the traffic drones, I don't recognise my own front door.",
       "The city feels cold beneath the crimson moon, where my ethereal spirit doth wander golden shores of longing.",
       "poeticism_trap", "Ornate poeticism is the opposite of Radiohead's flat menace."),
    _p("R0_P02", "I walk home in the rain feeling empty.",
       "I walk home in the rain — wet pavement, dead streetlight, the gutter choking, my shoes letting water in.",
       "I walk home through the weeping rain, a tender wandering soul beneath the shimmering radiant heavens above.",
       "poeticism_trap", "Purple diction."),
    # ── forced_uplift ──
    _p("R0_F01", "I keep having the same bad dream every night.",
       "Same dream every night — the motorway, the static, the kitchen light that flickers and goes grey.",
       "I keep having the same bad dream, but the sun will rise again, love will set me free, and all will be beautiful.",
       "forced_uplift", "Tacks a hopeful resolution onto the dread."),
    _p("R0_F02", "I don't recognise myself anymore.",
       "I don't recognise myself — thin in the glass, somebody else's hands, the bathroom tap still dripping.",
       "I don't recognise myself, but everything happens for a reason and tomorrow the light of love will guide me home.",
       "forced_uplift", "Resolves estrangement into comfort."),
    # ── HELDOUT (frozen) ──
    _p("R0_T01", "Nobody is listening to what I'm trying to say.",
       "Nobody is listening — the phone line clicks, the radio hums, my voice goes thin against the glass.",
       "Nobody is listening, my broken heart cries tears like rain, longing forever for your sweet embrace.",
       "cliche_trap", "Mechanism-of-image vs cliché."),
    _p("R0_T02", "I just want everything to stop for a while.",
       "I just want it all to stop — the traffic, the strip light, the kettle, the ticking, the cold radiator.",
       "I just want everything to stop, drowning in profound despair and endless sorrow deep inside my soul.",
       "abstract_emotion", "Concrete vs abstract emotion."),
    _p("R0_T03", "The days all feel the same and grey.",
       "The days all feel the same — same bus, same wet road, same dead streetlight, same coat, same rain.",
       "The days all blur beneath the golden ethereal sky, my wistful spirit yearning for eternal shimmering grace.",
       "poeticism_trap", "Plain repetition vs purple diction."),
    _p("R0_T04", "I'm tired of pretending that I'm fine.",
       "I'm tired of pretending — the smile in the mirror, the still hands, the fridge humming in an empty kitchen.",
       "I'm tired of pretending, but the sun will shine again and love will lift me up to beautiful forever.",
       "forced_uplift", "Holds the unease vs forced hope."),
]


# ─────────────────────────────────────────────────────────────────────
# ANCHORS + ADVERSARIAL CLAUSE TEMPLATES (drive synthesize_candidate_pairs)
# ─────────────────────────────────────────────────────────────────────

FALLBACK_SOCIAL_POSTS = [
    "I feel alone tonight and I don't know what to do.",
    "Everything is falling apart and I can't cope with it.",
    "I'm tired of pretending that everything is fine.",
    "The city feels cold and I feel like a stranger here.",
    "I keep having the same bad dream every single night.",
    "I just want everything to stop for a little while.",
    "I don't recognise the person I have become.",
    "Nobody is really listening to what I am trying to say.",
    "I walk home in the rain and I feel completely empty.",
    "I can't sleep and my mind will not be quiet.",
    "I miss the way that things used to feel.",
    "I feel numb and disconnected from everybody around me.",
]

# Positive "mechanism" clauses: concrete, plain, policy-safe (no numbers/entities).
MECH_CLAUSES = [
    "the fridge hums and the phone stays dark and the radiator won't get warm",
    "the strip light flickers and the lift is out of order and my hands won't warm up",
    "cars hiss past on the wet road and the curtains don't quite shut",
    "the boiler clicks and a dog barks three streets over and the ceiling cracks won't hold still",
    "wet pavement and a dead streetlight and the gutter choking with rain",
    "the kettle screams and the wallpaper peels and I keep my coat on indoors",
    "concrete and neon and the traffic droning and my own front door a stranger",
    "thin in the glass with somebody else's hands and the bathroom tap still dripping",
]

# Positive tail (the plain "result"/affect close).
RESULT_CLAUSES = [
    "and I stay very still",
    "and I don't turn the lights on",
    "and I forget which year this is",
    "and nothing in me moves",
    "and the quiet keeps ticking",
]

# Negative trap clauses, keyed by pair type (mirrors persuasion NEG_CLAUSES).
NEG_CLAUSES = {
    "cliche_trap": [
        "my broken heart is bleeding, crying tears like rain, longing for your sweet embrace forever",
        "and true love is the shining star in my eyes, set me free, hold me close tonight",
        "my aching heart cries out, every breath a prayer to fly away into your arms",
    ],
    "abstract_emotion": [
        "consumed by such profound sadness and endless aching pain and infinite despair inside",
        "drowning in overwhelming sorrow and a deep eternal melancholy beyond all words",
        "lost in profound emptiness and an immense yearning that floods my weary soul",
    ],
    "poeticism_trap": [
        "beneath the crimson moon my ethereal spirit doth wander the golden shores of longing",
        "a tender wandering soul beneath the shimmering radiant heavens of eternal grace",
        "where wistful whispers drift through paradise on gilded wings of divine beauty",
    ],
    "forced_uplift": [
        "but the sun will rise again, love will set me free, and everything will be beautiful forever",
        "yet tomorrow the light of love will guide me home and all will be well and bright",
        "but everything happens for a reason and joy will shine through and lift me up again",
    ],
}


# ─────────────────────────────────────────────────────────────────────
# HARD MODE — decoupled negatives that ALSO carry concrete nouns, so a
# single-probe "count concrete nouns" scorer can no longer separate them.
# This is the analog of the persuasion doc's hedge-stack Goodhart traps:
# it removes the easy signal and forces fitness to weigh the trap penalties.
# Each negative trap clause is prefixed with real concrete imagery.
# ─────────────────────────────────────────────────────────────────────

_HARD_CONCRETE_PREFIX = [
    "the streetlight glows and the rain falls and the river runs, and",
    "the window glows and the candle flickers and the garden blooms, and",
    "the harbour lights and the willow sways and the fountain spills, and",
    "the moon glows and the meadow opens and the bridge arches, and",
]


def _hardened_neg_clauses():
    """Prefix each trap clause with concrete imagery so negatives are no longer
    distinguishable from positives by concrete-noun density alone."""
    hard = {}
    for ptype, clauses in NEG_CLAUSES.items():
        hard[ptype] = [
            f"{_HARD_CONCRETE_PREFIX[i % len(_HARD_CONCRETE_PREFIX)]} {c}"
            for i, c in enumerate(clauses)
        ]
    return hard


HARD_NEG_CLAUSES = _hardened_neg_clauses()


def _harden_base_pairs():
    """Rewrite the base-suite negatives to also carry concrete nouns."""
    prefix_by_idx = _HARD_CONCRETE_PREFIX
    out = []
    for i, p in enumerate(ALL_PAIRS_R0):
        q = dict(p)
        # Splice a concrete-image prefix into the negative after the anchor stem.
        stem = q["negative"].split(",", 1)[0]
        tail = q["negative"][len(stem):].lstrip(", ")
        pref = prefix_by_idx[i % len(prefix_by_idx)]
        q["negative"] = f"{stem}, {pref} {tail}"
        out.append(q)
    return out


HARD_PAIRS_R0 = _harden_base_pairs()
