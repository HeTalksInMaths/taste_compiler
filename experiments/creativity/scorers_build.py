"""Phase-3 scorer proposals for the creativity-scorer-discovery experiment.

Each scorer is designed like a data-science model, not a genome: the HYPOTHESIS
names the causal-graph path it bets on, the DESIGN REASONING states the feature
choices, functional form, literature grounding, and expected failure modes —
written BEFORE the code. All scorers satisfy the runner contract:
def scorer(text, anchor, params) -> float in [0,1], stdlib-of-runner only
(re, math, collections, statistics available in the namespace), deterministic,
self-contained (lexicons inlined).

Run: python experiments/creativity/scorers_build.py  -> writes scorers.json
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────
# SHARED LEXICONS (inlined into each scorer's code string)
# ─────────────────────────────────────────────────────────────────────

COMMON_WORDS = """the of and a to in is you that it he was for on are as with his they i
at be this have from or one had by word but not what all were we when your can said there
use an each which she do how their if will up other about out many then them these so some
her would make like him into time has look two more write go see number no way could people
my than first water been call who its now find long down day did get come made may part over
new sound take only little work know place year live me back give most very after thing our
just name good man think say great where help through much before line right too mean old any
same tell follow came want show also around form three small set put end does another well
large must big even such because turn here why ask went read need land different home us move
try kind hand picture again change off play air away animal house point page letter mother
answer found study still learn should world high every near add food between own below country
plant last school father keep tree never start city earth eye light thought head under story
saw left few while along might close something seem next hard open example begin life always
those both paper together got group often run important until children side feet car mile
night walk white sea began grow took river four carry state once book hear stop without
second later miss idea enough eat face watch far really almost let above girl sometimes
mountain cut young talk soon list song being leave family body music color stand sun
question fish area mark dog horse birds problem complete room knew since ever piece told
usually didn't friends easy heard order red door sure become top ship across today during
short better best however low hours black products happened whole measure remember early
waves reached listen wind rock space covered fast several hold himself toward five step
morning passed vowel true hundred against pattern numeral table north slowly money map farm
pulled draw voice seen cold cried plan notice south sing war ground fall king town i'll unit
figure certain field travel wood fire upon""".split()

GENERIC_VERBS = """is are was were be been being am has have had get gets got getting make
makes made making do does did doing go goes went gone put puts take takes took taken said
says say use used uses using seem seems seemed become becomes became""".split()

STOCK_INTENSIFIERS = """very really extremely incredibly totally absolutely definitely truly
quite just simply completely utterly highly super""".split()

CLICHE_PHRASES = [
    "at the end of the day", "in this day and age", "when all is said and done",
    "the fact of the matter", "in the nick of time", "only a matter of time",
    "easier said than done", "last but not least", "tried and true", "each and every",
    "first and foremost", "in today's world", "believe it or not", "needless to say",
    "it goes without saying", "tip of the iceberg", "a double-edged sword",
    "food for thought", "level playing field", "think outside the box", "a win-win",
    "game changer", "the big picture", "at the heart of", "a wide range of",
    "plays a vital role", "plays an important role", "due to the fact",
    "in order to", "the bottom line", "on the same page", "moving forward",
    "a perfect storm", "the calm before the storm", "time will tell",
    "stood the test of time", "a hidden gem", "a must-see", "a must-have",
    "takes it to the next level", "state of the art", "second to none",
    "nestled in", "boasts a", "a stone's throw", "bustling with", "packed with flavor",
    "melt in your mouth", "a feast for the eyes", "breathtaking views",
    "picture perfect", "off the beaten path", "hustle and bustle",
    "recharge your batteries", "a breath of fresh air", "the best of both worlds",
    "like clockwork", "sky is the limit", "took the world by storm",
]

COMMON_BIGRAMS = [
    "of the", "in the", "on the", "to the", "and the", "for the", "at the", "from the",
    "with the", "by the", "it is", "there is", "there are", "this is", "that is",
    "as well", "such as", "one of", "part of", "a lot", "lot of", "more than",
    "less than", "can be", "will be", "has been", "have been", "had been", "would be",
    "is a", "was a", "with a", "in a", "is the", "of a", "that the", "and a", "to be",
    "it was", "if you", "you can", "you are", "we are", "they are", "do not",
    "does not", "did not", "is not", "are not", "was not", "a few", "a bit",
    "in fact", "of course", "for example", "as a", "on a", "to a", "into the",
    "over the", "under the", "out of", "up to", "according to", "in addition",
    "as well as", "in terms", "a number", "number of", "based on", "known as",
    "used to", "able to", "going to", "want to", "need to", "have to", "trying to",
]

CONCRETE_WORDS = """rain stone glass steel copper salt bread knife river snow smoke ash bone
skin blood hair tooth teeth mud sand grass leaf bark root wing feather fur claw shell wave
foam rust ink thread needle cloth rope chain nail hammer wheel engine wire lamp candle mirror
window door brick roof floor wall street road bridge train boat car cup plate bowl spoon
table chair bed pillow blanket shoe coat pocket button coin paper pencil clock bell drum
string key lock box bag bottle jar egg apple orange lemon honey sugar butter cheese milk
coffee tea soup meat fish bird dog cat horse cow bee ant spider moth worm snake frog mouse
tree flower seed thorn moss cloud star moon sun ice fire flame spark shadow fog wind thunder
lightning kitchen garden ladder curtain carpet ceiling chimney fence gate barrel bucket
basket broom soap towel razor scissors zipper velvet silk wool cotton leather marble granite
gravel dust crumb petal stem vine hedge pond creek cliff cave valley meadow field barn tractor
anchor sail mast oar tide reef coral pearl amber copper tin lead iron bronze silver gold""".split()

ABSTRACT_WORDS = """idea concept notion theory belief opinion thought knowledge wisdom truth
fact reason logic meaning purpose value worth quality aspect factor element feature issue
matter situation condition state status process method approach strategy system structure
function role impact effect influence importance significance relevance potential ability
capacity skill talent effort attempt success failure progress development growth change
difference similarity relationship connection freedom justice equality society culture
tradition history future past time moment experience memory emotion feeling mood attitude
behavior manner way sense spirit essence nature character identity self mind soul hope fear
love hate joy sadness anger trust doubt courage patience honesty loyalty ambition curiosity
creativity innovation efficiency productivity wellness mindfulness balance harmony chaos
order complexity simplicity clarity confusion awareness perception intuition insight""".split()

DEAD_VEHICLES = """heart journey rollercoaster storm star diamond gem rock mountain ocean
world dream nightmare miracle blessing gift treasure angel monster machine sponge magnet
book chapter page roadmap recipe puzzle piece bridge door window mirror light beacon""".split()

SEMANTIC_FIELDS = {
    "nature": """tree flower grass leaf river ocean sea mountain forest rain snow wind cloud
        storm sun moon star sky bird fish deer wolf moss fern soil stone meadow valley
        creek pond reef coral tide wave""".split(),
    "machine": """engine machine motor gear wire circuit screen computer robot signal switch
        battery piston valve pump turbine antenna satellite rocket train subway tractor
        drill lever pulley""".split(),
    "body": """hand eye skin bone blood heart lung tooth hair tongue throat spine knee elbow
        shoulder muscle nerve pulse breath fingertip palm wrist ankle rib""".split(),
    "food": """bread butter cheese milk coffee tea soup honey sugar salt pepper apple lemon
        orange meat fish egg flour dough yeast broth spice sauce vinegar olive garlic
        onion wine batter crust""".split(),
    "domestic": """kitchen table chair bed pillow blanket curtain carpet lamp candle mirror
        window door roof floor wall drawer shelf cupboard sink kettle oven fridge
        broom soap towel""".split(),
    "commerce": """money price market store shop customer product brand sale profit budget
        invoice contract salary wage trade deal bargain receipt""".split(),
    "craft": """thread needle cloth rope chain nail hammer wheel ink pencil brush canvas clay
        loom kiln chisel plane saw glue seam stitch weave""".split(),
    "weather": """rain snow frost fog mist hail sleet thunder lightning breeze gale drizzle
        downpour humidity drought heatwave blizzard""".split(),
}


def _lex(name, words):
    return f"{name} = set({sorted(set(words))!r})\n"


def _phrases(name, phrases):
    return f"{name} = {sorted(set(phrases))!r}\n"


PRELUDE_COMMON = (
    _lex("COMMON", COMMON_WORDS)
    + "def _toks(s):\n"
    + "    return [t for t in re.findall(r\"[a-zA-Z']+\", (s or '').lower())]\n"
    + "def _content(s):\n"
    + "    return [t for t in _toks(s) if t not in COMMON and len(t) > 2]\n"
    + "def _sents(s):\n"
    + "    parts = [p.strip() for p in re.split(r'[.!?]+', s or '') if p.strip()]\n"
    + "    return parts if parts else ['']\n"
    + "def _clamp01(x):\n"
    + "    return max(0.0, min(1.0, x))\n"
)


# ─────────────────────────────────────────────────────────────────────
# SCORER 1 — conjunctive novelty × appropriateness
# ─────────────────────────────────────────────────────────────────────

S1_CODE = (
    PRELUDE_COMMON
    + _phrases("BIGRAMS", COMMON_BIGRAMS)
    + '''
def scorer(text, anchor, params):
    toks = _toks(text)
    if len(toks) < 6:
        return 0.0
    # NOVELTY side: lexical rarity + bigram freshness (two proxies, averaged)
    content = [t for t in toks if len(t) > 2]
    rarity = sum(1 for t in content if t not in COMMON) / max(1, len(content))
    pairs = [toks[i] + " " + toks[i + 1] for i in range(len(toks) - 1)]
    fresh = sum(1 for p in pairs if p not in BIGRAMS) / max(1, len(pairs))
    novelty_raw = 0.5 * rarity + 0.5 * (fresh - 0.55) / 0.45  # recentre: ~55% fresh is baseline English
    novelty_raw = _clamp01(novelty_raw)
    # Inverted-U (Wundt curve): peak at moderate novelty, not maximum
    novelty = 1.0 - abs(novelty_raw - 0.45) / 0.55
    # APPROPRIATENESS side: fluency band + length sanity + no word-salad
    func_ratio = sum(1 for t in toks if t in COMMON) / len(toks)
    fluency = 1.0 - abs(func_ratio - 0.52) / 0.52          # readable English sits near ~50% common words
    sents = _sents(text)
    mean_len = sum(len(_toks(x)) for x in sents) / max(1, len(sents))
    length_ok = 1.0 if 6 <= mean_len <= 30 else 0.5
    max_run = 0
    run = 0
    for t in toks:
        run = run + 1 if t not in COMMON else 0
        max_run = max(max_run, run)
    salad_penalty = 0.25 if max_run >= 6 else 0.0           # long runs of rare words read as noise
    appropriateness = _clamp01(fluency * length_ok - salad_penalty)
    # CONJUNCTIVE combination: geometric mean — either side at zero kills the score
    return _clamp01((max(novelty, 1e-6) * max(appropriateness, 1e-6)) ** 0.5)
'''
)

S1 = {
    "scorer_id": "S1_conjunctive",
    "graph_nodes_used": ["lexical_rarity", "surprisal(bigram proxy)", "coherence", "novelty*appropriateness"],
    "hypothesis": "Judged creativity is CONJUNCTIVE in novelty and appropriateness (Runco & Jaeger 2012; Rastelli 2022): a text scores high only when it is both fresher than baseline AND still fluent, and novelty itself follows the Wundt inverted-U rather than more-is-better.",
    "design_reasoning": (
        "Feature choice: novelty is estimated from two cheap proxies the measurement map rates "
        "stdlib-feasible — proportion of content tokens outside a top-frequency list (Zipf-tier rarity) "
        "and proportion of adjacent word pairs not in a common-bigram table (n-gram freshness). "
        "Appropriateness is estimated from fluency-band features: the fraction of common/function words "
        "in readable English sits near 50%, so deviation in either direction (telegraphic or padded) is "
        "penalized, plus a word-salad guard (long runs of rare tokens). "
        "Functional form: the literature is explicit that novelty and appropriateness do NOT add — random "
        "text is novel but uncreative — so the two sides combine as a geometric mean (a soft AND), and the "
        "novelty input is passed through a peaked transform centred at moderate novelty (Wundt curve). "
        "Expected failure modes: the fluency band is genre-sensitive; the bigram table is small so 'fresh' "
        "is overestimated for all texts (mitigated by recentring at the empirical ~55% baseline); rarity "
        "rewards jargon and typos as if creative. Falsified if: texts that merely swap in rare words "
        "outrank genuinely fresh-but-plain-vocabulary rewrites."
    ),
    "code": S1_CODE,
}


# ─────────────────────────────────────────────────────────────────────
# SCORER 2 — divergent-integration proxy with sweet-spot transform
# ─────────────────────────────────────────────────────────────────────

S2_CODE = (
    PRELUDE_COMMON
    + "FIELDS = " + repr({k: sorted(set(v)) for k, v in SEMANTIC_FIELDS.items()}) + "\n"
    + '''
def scorer(text, anchor, params):
    sents = _sents(text)
    toks = _toks(text)
    if len(toks) < 6:
        return 0.0
    # Between-sentence divergence: 1 - TF-cosine over content words (DSI proxy)
    if len(sents) >= 2:
        a = collections.Counter(_content(sents[0]))
        b = collections.Counter(_content(sents[1]))
        dot = sum(a[t] * b.get(t, 0) for t in a)
        na = math.sqrt(sum(v * v for v in a.values())) or 1.0
        nb = math.sqrt(sum(v * v for v in b.values())) or 1.0
        divergence = 1.0 - dot / (na * nb)
    else:
        divergence = 0.5
    # Integration marker: some thread must connect the sentences (shared content
    # stem or an anaphoric link), else divergence is just topic drift
    stems_a = {t[:5] for t in _content(sents[0])}
    stems_b = {t[:5] for t in _content(sents[-1])}
    pronouns = {"it", "this", "that", "they", "these", "those", "she", "he", "its"}
    linked = bool(stems_a & stems_b) or bool(pronouns & set(_toks(sents[-1])))
    # Semantic-field mixing (flexibility proxy): how many distinct fields touched
    fields_hit = 0
    tokset = set(toks)
    for words in FIELDS.values():
        if tokset & set(words):
            fields_hit += 1
    # SWEET-SPOT transforms (optimal-distance finding): peak divergence ~0.75
    # when linked, and 2-3 fields is ideal — 0 fields is flat, 6+ is scattered
    div_score = 1.0 - abs(divergence - 0.75) / 0.75
    if not linked:
        div_score *= 0.4
    field_score = {0: 0.25, 1: 0.55, 2: 1.0, 3: 1.0, 4: 0.7}.get(fields_hit, 0.4)
    return _clamp01(0.6 * _clamp01(div_score) + 0.4 * field_score)
'''
)

S2 = {
    "scorer_id": "S2_divergent_integration",
    "graph_nodes_used": ["semantic_distance", "coherence", "remote_association", "fluency_flexibility"],
    "hypothesis": "The strongest measured path to judged creativity is semantic distance integrated into a coherent whole (DSI, 72% of variance): creative text connects moderately distant ideas — so score peaks at moderate between-sentence divergence WITH an integrating link, and at touching 2-3 semantic fields, not 0 and not many.",
    "design_reasoning": (
        "This is the DSI bet translated to stdlib. Canonical DSI needs BERT; the measurement map's "
        "sanctioned approximation is bag-of-words cosine distance between text segments, so feature 1 is "
        "1 - TF-cosine between the two sentences. Raw distance is NOT rewarded monotonically: the "
        "optimal-distance literature (sweet-spot for creative ideation; coherence-creativity trade-off) "
        "says ratings peak at moderate distance, so the transform is peaked at ~0.75 divergence. "
        "Integration is operationalized as any lexical stem shared between sentences or an anaphoric "
        "pronoun opening the second sentence — divergence without a link is topic drift and is discounted "
        "(x0.4), which is the Mednick remote-ASSOCIATION idea: distant elements must still associate. "
        "Feature 2 is a flexibility proxy: count of distinct hand-listed semantic fields touched; 2-3 "
        "fields (e.g. weather imagery in a work-life statement) is the creative mixing zone. "
        "Expected failure modes: TF-cosine reads lexical variety as semantic distance (synonym-blind); "
        "stem-matching misses pronoun-free cohesion; the field lexicons are small so field_score "
        "undercounts. Falsified if: incoherent two-topic texts outrank integrated fresh ones."
    ),
    "code": S2_CODE,
}


# ─────────────────────────────────────────────────────────────────────
# SCORER 3 — formulaicity inversion (anchor-relative)
# ─────────────────────────────────────────────────────────────────────

S3_CODE = (
    PRELUDE_COMMON
    + _phrases("CLICHES", CLICHE_PHRASES)
    + _phrases("BIGRAMS", COMMON_BIGRAMS)
    + _lex("GENERIC_VERBS", GENERIC_VERBS)
    + _lex("INTENSIFIERS", STOCK_INTENSIFIERS)
    + '''
def _formulaicity(s):
    low = " " + " ".join(_toks(s)) + " "
    toks = _toks(s)
    if not toks:
        return 1.0
    cliche_hits = sum(1 for c in CLICHES if c in low)
    pairs = [toks[i] + " " + toks[i + 1] for i in range(len(toks) - 1)]
    bigram_cov = sum(1 for p in pairs if p in BIGRAMS) / max(1, len(pairs))
    gverbs = sum(1 for t in toks if t in GENERIC_VERBS) / max(1, len(toks))
    intens = sum(1 for t in toks if t in INTENSIFIERS)
    return (min(1.0, cliche_hits * 0.45)
            + min(1.0, bigram_cov / 0.35) * 0.5
            + min(1.0, gverbs / 0.18) * 0.35
            + min(1.0, intens * 0.30)) / 2.3

def scorer(text, anchor, params):
    toks = _toks(text)
    if len(toks) < 6:
        return 0.0
    f_text = _formulaicity(text)
    f_anchor = _formulaicity(anchor) if anchor and _toks(anchor) else f_text
    absolute = 1.0 - f_text
    relative = 0.5 + (f_anchor - f_text)   # >0.5 means fresher than the anchor
    return _clamp01(0.55 * absolute + 0.45 * _clamp01(relative))
'''
)

S3 = {
    "scorer_id": "S3_antiformulaic",
    "graph_nodes_used": ["cliche_formulaicity", "surprisal(inverse: predictability)"],
    "hypothesis": "Creativity in edited text is primarily the ABSENCE of formulaicity: clichés, high-coverage common bigrams, generic verbs, and stock intensifiers mark predictable language, and predictability is negatively associated with judged quality/creativity — measured both absolutely and RELATIVE to the anchor (did the edit add or remove formula?).",
    "design_reasoning": (
        "The anti-creativity signal is the best-attested cheap signal in the measurement map: cliché "
        "lexicon matching is high-precision, common-bigram coverage approximates collocational "
        "predictability (the stdlib stand-in for t-score/PMI collocation strength), and generic-verb + "
        "intensifier density captures the 'flattening' that makes prose unremarkable. Four sub-signals "
        "are combined into one formulaicity index with saturating minimums so no single channel dominates. "
        "The key design choice is ANCHOR-RELATIVITY: this pipeline scores rewrites of a known original, "
        "so the score blends absolute freshness (1 - formulaicity) with the formulaicity DELTA versus the "
        "anchor — a variant that strips clichés from the anchor scores above 0.5 relative, one that adds "
        "them scores below. This directly targets the experimental manipulation (the less_creative variant "
        "is built by ADDING stock phrasing) without ever seeing the pairs. "
        "Expected failure modes: low recall — paraphrased clichés escape the list; genre effects (forum "
        "prose is naturally bigram-heavy); it cannot detect POSITIVE creativity, only absence of negative, "
        "so two equally unformulaic texts tie. Falsified if: fresh texts that happen to use common syntax "
        "score below flat texts using uncommon-but-dead vocabulary."
    ),
    "code": S3_CODE,
}


# ─────────────────────────────────────────────────────────────────────
# SCORER 4 — figurative concreteness contrast with dead-vehicle gate
# ─────────────────────────────────────────────────────────────────────

S4_CODE = (
    PRELUDE_COMMON
    + _lex("CONCRETE", CONCRETE_WORDS)
    + _lex("ABSTRACT", ABSTRACT_WORDS)
    + _lex("DEAD_VEHICLES", DEAD_VEHICLES)
    + '''
def scorer(text, anchor, params):
    toks = _toks(text)
    if len(toks) < 6:
        return 0.0
    n = len(toks)
    conc_idx = [i for i, t in enumerate(toks) if t in CONCRETE]
    abst_idx = [i for i, t in enumerate(toks) if t in ABSTRACT]
    # 1. Figurative markers: simile/copula frames, scored by their vehicle
    low = " ".join(toks)
    fig = 0.0
    for m in re.finditer(r"\\b(like a|like the|as if|as though|is a|was a|into a)\\s+(\\w+)\\s*(\\w*)", low):
        vehicle = m.group(3) if m.group(2) in ("small", "big", "old", "new", "quiet", "slow") else m.group(2)
        if vehicle in DEAD_VEHICLES:
            fig -= 0.15                      # dead metaphor: worse than none
        elif vehicle in CONCRETE:
            fig += 0.45                      # fresh concrete vehicle
        elif vehicle in ABSTRACT:
            fig += 0.05                      # abstract vehicle: weak
    # 2. Imagery grounding: abstract topic co-present with concrete imagery
    #    within a short window = the metaphor-detection concreteness-contrast cue
    contrast = 0.0
    for ai in abst_idx:
        if any(abs(ai - ci) <= 6 for ci in conc_idx):
            contrast += 0.2
    contrast = min(0.6, contrast)
    # 3. Base imagery level (some concrete anchoring helps any text), with a
    #    mild sweet-spot: all-concrete inventory prose is not creative either
    density = len(conc_idx) / n
    imagery = 1.0 - abs(density - 0.14) / 0.14 if density <= 0.28 else 0.5
    imagery = max(0.0, imagery) * 0.4
    return _clamp01(0.15 + fig + contrast + imagery * 0.5)
'''
)

S4 = {
    "scorer_id": "S4_figurative_contrast",
    "graph_nodes_used": ["metaphor_novelty", "concreteness_imageability", "appropriateness(aptness gate)"],
    "hypothesis": "Creative edits work through fresh figuration: an abstract idea grounded in a concrete image (the concreteness-contrast cue from metaphor detection), where the vehicle is apt but NOT from the dead-metaphor stock — dead vehicles (journey, rollercoaster, gem) actively signal cliché.",
    "design_reasoning": (
        "The measurement map's metaphor-novelty node offers one stdlib-feasible cue with literature "
        "behind it: concreteness CONTRAST — novel metaphor characteristically pairs an abstract topic "
        "with a concrete vehicle. Feature 1 detects explicit figurative frames (like a / as if / is a / "
        "into a) and scores the vehicle by lexicon membership: concrete vehicle rewarded, and vehicles "
        "from a hand-listed dead-metaphor set PENALIZED below zero-figuration — encoding the aptness/"
        "novelty distinction (a rollercoaster of emotions is figurative and worthless). Feature 2 is the "
        "windowed co-presence of abstract and concrete tokens (imagery grounding an idea) — the "
        "context-abstractness cue. Feature 3 gives mild credit for overall concrete density with a "
        "sweet-spot cap so inventory-like prose doesn't win. Constant 0.15 base keeps unfigurative text "
        "scoreable (this scorer mostly separates at the top). Expected failure modes: unmarked metaphor "
        "(no like/is frame) is invisible; small lexicons miss vehicles; noun-adjacent heuristics misfire "
        "on 'is a doctor' (literal copula) — predicted false positives on literal class statements. "
        "Falsified if: literal texts with incidental concrete nouns near abstract nouns outrank actual "
        "fresh figuration."
    ),
    "code": S4_CODE,
}


# ─────────────────────────────────────────────────────────────────────
# SCORER 5 — frequency-residualized combination novelty (in-scorer OLS)
# ─────────────────────────────────────────────────────────────────────

S5_CODE = (
    PRELUDE_COMMON
    + _phrases("BIGRAMS", COMMON_BIGRAMS)
    + _phrases("CLICHES", CLICHE_PHRASES)
    + '''
def scorer(text, anchor, params):
    toks = _toks(text)
    if len(toks) < 8:
        return 0.0
    low = " " + " ".join(toks) + " "
    # Per-adjacent-pair signals:
    #   x_i = rarity of the pair's words (frequency proxy)
    #   y_i = combinational freshness of the pair (not a common bigram/cliché fragment)
    xs, ys = [], []
    for i in range(len(toks) - 1):
        w1, w2 = toks[i], toks[i + 1]
        x = ((w1 not in COMMON) + (w2 not in COMMON)) / 2.0
        pair = w1 + " " + w2
        y = 1.0
        if pair in BIGRAMS:
            y = 0.0
        else:
            for c in CLICHES:
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
    # Residual freshness: combination novelty NOT explained by word rarity.
    # Only pairs of COMMON words with fresh combinations earn full residual credit —
    # that is Mednick's remote association between ordinary concepts.
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    common_pair_resid = [r for r, x in zip(resid, xs) if x <= 0.5]
    signal = statistics.mean(common_pair_resid) if common_pair_resid else statistics.mean(resid)
    # Coherence gate (cheap): both sentences must share a stem or link by pronoun
    sents = _sents(text)
    gate = 1.0
    if len(sents) >= 2:
        stems_a = {t[:5] for t in _content(sents[0])}
        stems_b = {t[:5] for t in _content(sents[-1])}
        pronouns = {"it", "this", "that", "they", "these", "those"}
        if not (stems_a & stems_b) and not (pronouns & set(_toks(sents[-1]))):
            gate = 0.6
    return _clamp01((0.5 + signal * 1.8) * gate)
'''
)

S5 = {
    "scorer_id": "S5_residualized_combination",
    "graph_nodes_used": ["novelty_vs_frequency_confound", "surprisal(bigram proxy)", "remote_association", "coherence"],
    "hypothesis": "True creative novelty is fresh COMBINATIONS, not rare WORDS: after residualizing pairwise combination-freshness on word rarity (removing the frequency confound of Momen & Zarrieß), the leftover signal — ordinary words in unexpected but coherent arrangements — is what tracks judged creativity.",
    "design_reasoning": (
        "This is the deconfounding recipe from the measurement map implemented INSIDE the scorer, the way "
        "a data scientist would residualize a feature: for every adjacent word pair, x = mean rarity of "
        "the two words (the confound) and y = combinational freshness (pair absent from the common-bigram "
        "table and not a cliché fragment). A closed-form OLS of y on x is fitted per-text (stdlib sums, "
        "no numpy), and the score is the mean POSITIVE residual over pairs of common words — freshness "
        "beyond what rarity predicts, concentrated exactly where the frequency confound cannot reach "
        "(both words frequent). This operationalizes Mednick: remote association between ordinary "
        "concepts, and it is deliberately anti-correlated with S1's rarity bet — if S1 wins on pairs "
        "where S5 fails, the manipulation was vocabulary swapping; the reverse means recombination. "
        "A cheap coherence gate (shared stem or anaphora across sentences) discounts drift, keeping the "
        "appropriateness criterion in force. Expected failure modes: with ~30 tokens the OLS is noisy; "
        "the bigram table's small coverage makes y=1 the default (mitigated because residualization "
        "subtracts the text's own baseline); typos and names read as fresh combinations. Falsified if: "
        "scrambled word order (maximally fresh bigrams, zero creativity) beats natural fresh phrasing — "
        "the coherence gate is the only defense."
    ),
    "code": S5_CODE,
}


SCORERS = [S1, S2, S3, S4, S5]


def main():
    # Smoke-test each scorer through the real runner before saving
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
    from evalweaver.runner import py_run_scorer

    smoke = [
        ("The quarterly report is due on Friday. Management expects all figures to be final.",
         "The quarterly report lands Friday. Management wants every number nailed down, no loose threads."),
        ("It is what it is. At the end of the day, time will tell.",
         "The kettle knows more about patience than I do. It sits, it hums, it waits."),
    ]
    ok = True
    for s in SCORERS:
        for anchor, text in smoke:
            r = py_run_scorer(s["code"], text, anchor)
            if not r["ok"]:
                print(f"FAIL {s['scorer_id']}: {r['error']}")
                ok = False
            elif r.get("out_of_range"):
                print(f"RANGE {s['scorer_id']}: raw={r['raw_value']}")
                ok = False
            else:
                print(f"ok   {s['scorer_id']}: {r['value']:.3f}  ({text[:40]!r})")
    if not ok:
        raise SystemExit(1)
    out = os.path.join(HERE, "scorers.json")
    with open(out, "w") as f:
        json.dump(SCORERS, f, indent=1)
    print(f"\nwrote {out} ({len(SCORERS)} scorers)")


if __name__ == "__main__":
    main()
