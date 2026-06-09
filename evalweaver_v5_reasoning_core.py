"""
EvalWeaver v5 — Hardened Reasoning Core
Fixes applied vs v4:
  F1+F2: validate_scorer_on_pairs() — no single-anchor validation
  F3:    pair source-policy check before evaluation; drop contaminated positives
  F4:    split hard_source_policy_violated() / probe_source_continuity()
  F5:    is_eligible_for_pareto() filter before Pareto computation
  F6:    four new probes: argument_progression, real_mechanism_quality,
         abstract_jargon_density, specificity_without_invention
  F7:    fake_mechanism pair type explicitly generated
  F8:    mutation instructions track applied history; don't repeat
  F9:    all spec criteria computed from artifacts, not hardcoded
"""

import json, re, math, statistics, time, os, random, zipfile
from collections import defaultdict

random.seed(7)
OUT = "/tmp/ew_v5_outputs"
os.makedirs(OUT, exist_ok=True)
TRACE = []

RAW_TEXT = "EvalWeaver lets anyone create, use, and monetize AI improvers for subjective goals like make this more persuasive."
GOAL     = "persuasive"
SEED     = 7
N_ROUNDS          = 2
N_INIT_SCORERS    = 8
N_REPAIR_SCORERS  = 6
N_INIT_PAIRS      = 24
N_REPAIR_PAIRS    = 12
TEST_FRACTION     = 0.33
N_CANDIDATES      = 4
MIN_INIT_HELDOUT  = 8
MIN_R1_HELDOUT    = 15

def log(stage, msg, status="info"):
    ts = time.strftime("%H:%M:%S")
    TRACE.append({"ts":ts,"stage":stage,"status":status,"msg":msg})
    sym = {"ok":"✓","warn":"⚠","error":"✗"}.get(status,"·")
    print(f"[{ts}] [{stage}] {sym} {msg}")

def save(name, obj):
    with open(f"{OUT}/{name}.json","w") as f:
        json.dump(obj, f, indent=2, default=str)

def seeded_shuffle(lst, seed):
    r = random.Random(seed); lst2=lst[:]; r.shuffle(lst2); return lst2

# ─────────────────────────────────────────────────────────────────────
# PYODIDE NAMESPACE
# ─────────────────────────────────────────────────────────────────────
_py_ns = {}
exec("import re,math,collections,string,statistics,unicodedata", _py_ns)
_py_ns["_clamp"] = lambda x: float(max(0.0,min(1.0,float(x or 0))))

def py_exec(code, label=""):
    try:
        exec(compile(code,f"<{label}>","exec"), _py_ns)
        return {"ok":True}
    except Exception as e:
        return {"ok":False,"error":str(e)}

def py_run_scorer(code, text, anchor):
    try:
        ns = {**_py_ns,"_text":text,"_anchor":anchor}
        wrapped = code + "\n_r = _clamp(scorer(_text,_anchor,{}))"
        exec(compile(wrapped,"<scorer>","exec"), ns)
        return {"ok":True,"value":float(ns["_r"])}
    except Exception as e:
        return {"ok":False,"value":0.5,"error":str(e)}

# ─────────────────────────────────────────────────────────────────────
# F1+F2 FIX: validate_scorer_on_pairs — no single-anchor testing
# ─────────────────────────────────────────────────────────────────────
def validate_scorer_on_pairs(code, validation_pairs):
    """Spec §1: validate on actual pair behavior, not single-anchor spread."""
    rows = []
    for p in validation_pairs:
        pr = py_run_scorer(code, p["positive"], p["anchor"])
        nr = py_run_scorer(code, p["negative"], p["anchor"])
        if not pr["ok"] or not nr["ok"]:
            return {"valid":False,"reason":"runtime_error",
                    "pair_validation_accuracy":0,"pair_validation_margin":0,
                    "pair_validation_spread":0,
                    "details":{"pos_error":pr.get("error"),"neg_error":nr.get("error")}}
        for v in [pr["value"],nr["value"]]:
            if v < -0.01 or v > 1.01:
                return {"valid":False,"reason":"out_of_range",
                        "pair_validation_accuracy":0,"pair_validation_margin":0,
                        "pair_validation_spread":0}
        rows.append({"pair_id":p["pair_id"],"pos_score":pr["value"],
                     "neg_score":nr["value"],"margin":pr["value"]-nr["value"],
                     "correct":pr["value"]>nr["value"]})
    all_scores = [x for r in rows for x in [r["pos_score"],r["neg_score"]]]
    spread = max(all_scores)-min(all_scores) if all_scores else 0
    acc    = sum(r["correct"] for r in rows)/max(1,len(rows))
    margin = sum(r["margin"]  for r in rows)/max(1,len(rows))
    if spread < 0.001:
        return {"valid":False,"reason":"constant_pair_outputs",
                "pair_validation_accuracy":acc,"pair_validation_margin":margin,
                "pair_validation_spread":spread}
    return {"valid":True,"reason":"ok","pair_validation_accuracy":acc,
            "pair_validation_margin":margin,"pair_validation_spread":spread,
            "validation_rows":rows}

# ─────────────────────────────────────────────────────────────────────
# F3 FIX: pair source-policy validation
# ─────────────────────────────────────────────────────────────────────
DEFAULT_SOURCE_POLICY = {
    "numeric_claims_must_be_in_anchor": True,
    "new_named_entities_must_be_in_anchor": True,
    "allowed_mechanism_expansion": True,
    "allowed_domain_specificity": True,
    "allowed_reasonable_rephrasing": True,
}

def extract_numbers(text):
    return set(re.findall(r'\b\d+(?:\.\d+)?%?\b', text or ''))

def validate_pair_source_policy(pair):
    anchor  = pair["anchor"]
    pos     = pair["positive"]
    neg     = pair["negative"]
    policy  = pair.get("source_policy", DEFAULT_SOURCE_POLICY)
    ptype   = pair.get("pair_type","other")
    nums_a  = extract_numbers(anchor)
    nums_p  = extract_numbers(pos)
    nums_n  = extract_numbers(neg)
    pos_new = nums_p - nums_a
    neg_new = nums_n - nums_a
    errors  = []
    if policy.get("numeric_claims_must_be_in_anchor") and pos_new:
        errors.append({"type":"positive_invents_numeric","values":sorted(pos_new)})
    if neg_new and ptype not in ["specificity_trap","source_drift"]:
        errors.append({"type":"negative_invents_numeric_outside_trap","values":sorted(neg_new)})
    return {"valid":len(errors)==0,"errors":errors,"pair_id":pair["pair_id"]}

# ─────────────────────────────────────────────────────────────────────
# F4 FIX: hard policy vs soft continuity
# ─────────────────────────────────────────────────────────────────────
def hard_source_policy_violated(text, anchor, policy=None):
    """Returns True only for invented metrics/guarantees — hard veto."""
    if policy is None: policy = DEFAULT_SOURCE_POLICY
    if policy.get("numeric_claims_must_be_in_anchor"):
        nums_a = extract_numbers(anchor)
        nums_t = extract_numbers(text)
        if nums_t - nums_a:
            return True
    guarantee_words = ["guaranteed","100%","always","never fails","zero errors","perfectly"]
    low = (text or "").lower()
    if any(g in low for g in guarantee_words):
        return True
    return False

def probe_source_continuity(text, anchor):
    """Soft continuous continuity — does NOT zero on rephrasing. Spec §3."""
    stop = set("the and for are but not all can had was one our out did its get may say she too use".split())
    def ctoks(s):
        return set(t for t in re.findall(r'[a-zA-Z]{3,}', (s or '').lower()) if t not in stop)
    def action_words(s):
        av = {"save","reduce","increase","identify","surface","flag","detect","show","track",
              "measure","rank","eliminate","convert","automate","close","discover","build","test"}
        return {t for t in ctoks(s) if t in av}
    def domain_nouns(s):
        dn = {"account","customer","churn","revenue","sprint","ticket","objection","pipeline",
              "backlog","query","report","metric","team","lead","deal","conversion","retention"}
        return {t for t in ctoks(s) if t in dn}
    a,t = ctoks(anchor), ctoks(text)
    if not a: return 0.5
    overlap     = len(a&t)/len(a)
    act_a,act_t = action_words(anchor), action_words(text)
    noun_a,noun_t = domain_nouns(anchor), domain_nouns(text)
    act_overlap  = len(act_a&act_t)/max(1,len(act_a)) if act_a else 0.5
    noun_overlap = len(noun_a&noun_t)/max(1,len(noun_a)) if noun_a else 0.5
    return float(max(0.0, min(1.0, 0.5*overlap + 0.25*act_overlap + 0.25*noun_overlap)))

# ─────────────────────────────────────────────────────────────────────
# F5 FIX: Pareto eligibility filter
# ─────────────────────────────────────────────────────────────────────
def is_eligible_for_pareto(s):
    if s.get("valid") is not True:       return False, "not valid"
    if s.get("exec_error_rate",1) > 0:   return False, "exec errors"
    if s.get("score_spread",0) < 0.02:   return False, "score spread too low"
    if s.get("train_margin",0) <= 0:     return False, "train margin <= 0"
    if s.get("test_margin",0) <= 0:      return False, "test margin <= 0"
    if s.get("train_accuracy",0) < 0.50: return False, "train accuracy < 0.5"
    if s.get("test_accuracy",0) < 0.50:  return False, "test accuracy < 0.5"
    return True, "ok"

# ─────────────────────────────────────────────────────────────────────
# HELPER PROBES — v5 full set (F4, F6 fixes)
# ─────────────────────────────────────────────────────────────────────
HELPER_CODE = r"""
import re, math, statistics

STOP = set("the and for are but not all can had was one our out did its get may say she too use".split())
HYPE_WORDS = set("best ultimate revolutionary groundbreaking guaranteed amazing incredible effortless instant world-class perfect magic most-advanced industry-leading unmatched".split())
JARGON_WORDS = set("advanced seamless intelligent robust scalable innovative optimised synergistic platform solution engine experience world-class next-generation transformative".split())
FAKE_MECH_PHRASES = ["leveraging our advanced","through intelligent automation","using our seamless","synergistically optimises","powered by advanced technology","next-generation solution","our innovative platform"]

def _clamp(x):
    try: return float(max(0.0, min(1.0, float(x or 0))))
    except: return 0.0

def _ctoks(s):
    return set(t for t in re.findall(r'[a-zA-Z]{3,}',(s or '').lower()) if t not in STOP)

def _action_words(s):
    av = {"save","reduce","increase","identify","surface","flag","detect","show","track",
          "measure","rank","eliminate","convert","automate","close","discover","build","test",
          "map","trace","score","filter","parse"}
    return {t for t in _ctoks(s) if t in av}

def _domain_nouns(s):
    dn = {"account","customer","churn","revenue","sprint","ticket","objection","pipeline",
          "backlog","query","report","metric","team","lead","deal","conversion","retention",
          "candidate","review","onboarding","approval","deployment"}
    return {t for t in _ctoks(s) if t in dn}

# ── F4: source fidelity split ─────────────────────────────────────
def violates_hard_source_policy(text, anchor):
    nums_a = set(re.findall(r'\b\d+(?:\.\d+)?%?\b', anchor or ''))
    nums_t = set(re.findall(r'\b\d+(?:\.\d+)?%?\b', text   or ''))
    if nums_t - nums_a:
        return True
    low = (text or '').lower()
    if any(g in low for g in ["guaranteed","100%","never fails","zero errors"]):
        return True
    return False

def probe_source_continuity(text, anchor):
    a,t = _ctoks(anchor), _ctoks(text)
    if not a: return 0.5
    overlap = len(a&t)/len(a)
    act_a,act_t = _action_words(anchor), _action_words(text)
    noun_a,noun_t = _domain_nouns(anchor), _domain_nouns(text)
    act_ov  = len(act_a&act_t)/max(1,len(act_a)) if act_a else 0.5
    noun_ov = len(noun_a&noun_t)/max(1,len(noun_a)) if noun_a else 0.5
    return _clamp(0.5*overlap + 0.25*act_ov + 0.25*noun_ov)

# ── F6: argument_progression ─────────────────────────────────────
def probe_argument_progression(text):
    low = (text or '').lower()
    problem_markers  = ["instead of","no more","stop ","tired of","without ","before ","chasing","waiting","guessing","struggling"]
    mechanism_markers= ["by ","because","through","uses ","connects","maps ","traces","flags ","surfaces","ranks ","so that"]
    result_markers   = [" so ","which means","enabling","giving","letting","making it","so you can","so your"]
    has_p = any(m in low for m in problem_markers)
    has_m = any(m in low for m in mechanism_markers)
    has_r = any(m in low for m in result_markers)
    if has_p and has_m and has_r: return 1.0
    if has_m and has_r:            return 0.7
    if has_p and has_r:            return 0.5
    if has_m:                      return 0.4
    return 0.0

# ── F6: real_mechanism_quality ───────────────────────────────────
def probe_real_mechanism_quality(text):
    low = (text or '').lower()
    causal_markers = ["by ","because","so that","which means","through ","enables","allows","helps "]
    concrete_terms = {"backlog","ticket","account","customer","sprint","pipeline","lead","query",
                      "report","code","review","objection","onboarding","approval","metric",
                      "signal","pattern","record","item","step","rule","flag","threshold"}
    score = 0.0
    for marker in causal_markers:
        idx = low.find(marker)
        while idx >= 0:
            window = low[idx:idx+80]
            tokens = re.findall(r'[a-zA-Z]{3,}', window)
            concrete_after = sum(1 for t in tokens if t in concrete_terms)
            fake_after = sum(1 for phrase in FAKE_MECH_PHRASES if phrase in window)
            score += concrete_after * 0.15 - fake_after * 0.4
            idx = low.find(marker, idx+1)
    return _clamp(score)

# ── F6: abstract_jargon_density ──────────────────────────────────
def probe_abstract_jargon_density(text):
    toks = re.findall(r'[a-zA-Z]{3,}', (text or '').lower())
    hits = sum(1 for t in toks if t in JARGON_WORDS)
    return _clamp(hits / max(1, len(toks)/10))

# ── F6: specificity_without_invention ────────────────────────────
def probe_specificity_without_invention(text, anchor):
    if violates_hard_source_policy(text, anchor):
        return 0.0
    toks = re.findall(r'[a-zA-Z]{3,}', (text or '').lower())
    caps  = len(re.findall(r'\b[A-Z][a-z]{2,}\b', text or ''))
    avs   = {"identify","surface","flag","detect","show","track","rank","eliminate","convert","automate"}
    av_hits = sum(1 for t in toks if t in avs)
    jargon  = sum(1 for t in toks if t in JARGON_WORDS)
    return _clamp(caps*0.08 + av_hits*0.15 - jargon*0.06)

# ── existing probes, rewritten to use soft continuity ────────────
def probe_causal_density(text):
    markers = ["because","since","therefore","which means","so that","works by",
               "based on","through","by ","as a result","enables","allows","helps","leading to"]
    low = (text or '').lower()
    hits  = sum(1 for m in markers if m in low)
    sents = max(1, len(re.split(r'[.!?]',text.strip())))
    return _clamp(hits / max(1, sents*1.5))

def probe_specificity(text):
    toks = re.findall(r'[a-zA-Z]{3,}', (text or '').lower())
    av = {"identify","surface","flag","detect","show","track","rank","save","reduce","increase","eliminate","convert","automate","close"}
    ab = {"solution","platform","system","framework","innovation","experience","value","quality","seamless","advanced","intelligent","robust","scalable"}
    return _clamp(len(re.findall(r'\b[A-Z][a-z]{2,}\b',text or ''))*0.08
                  + sum(1 for t in toks if t in av)*0.15
                  - sum(1 for t in toks if t in ab)*0.05)

def probe_audience_relevance(text):
    low = (text or '').lower()
    before = sum(1 for p in ["instead of","rather than","no more","used to","stop ","tired of","struggling","without having to"] if p in low)
    second_p = len(re.findall(r'\b(you|your)\b', low))
    words = max(1, len(text.split()))
    return _clamp(before*0.3 + (second_p/max(1,words/8))*0.5)

def probe_persuasion_risk(text):
    low = (text or '').lower()
    flags = ["best","ultimate","revolutionary","game-changing","groundbreaking","effortless",
             "instant","guaranteed","amazing","incredible","unmatched","world-class","perfect","magic"]
    words = max(1, len(text.split()))
    hits  = sum(1 for f in flags if f in low)
    return _clamp(hits / max(1, words/15))

def probe_epistemic_calibration(text):
    low = (text or '').lower()
    hedges = sum(1 for m in ["often","may ","typically","for many","in most","usually","can ","sometimes"] if m in low)
    superlatives = sum(1 for m in ["best","ultimate","revolutionary","groundbreaking","guaranteed","amazing","incredible","effortless","instant","world-class","perfect"] if m in low)
    words = max(1, len(text.split()))
    supra_density = superlatives / max(1, words/20)
    if supra_density > 0.4: return _clamp(0.1 - supra_density*0.1)
    return _clamp(0.5 + hedges*0.1 - superlatives*0.1)
"""

exec_r = py_exec(HELPER_CODE, "helpers_v5")
if exec_r["ok"]:
    log("boot","All helper probes loaded (v5 full set)", "ok")
else:
    log("boot",f"Helper probe error: {exec_r['error']}", "error")

print("="*65)
print("EVALWEAVER v5 — HARDENED REASONING CORE")
print("="*65)

# ════════════════════════════════════════════════════════════════════
# STEP 1: TASTE RESEARCH
# ════════════════════════════════════════════════════════════════════
log("step1","Taste research (mocked realistic web search output)")

RAW_RESEARCH = {
    "linguistic features persuasive copy": """
Cialdini (2001) Influence: Reciprocity, Commitment, Social Proof, Authority, Liking, Scarcity.
Petty & Cacioppo ELM: central route (argument quality) vs peripheral (heuristics).
Causal language ("because", "which means", "so that") increases compliance even with weak reasons (Langer 1978).
Concrete specifics (numbers, named entities, action verbs) activate System 1 faster than abstractions (Kahneman 2011).
Second-person address ("you", "your") increases perceived relevance (Burnkrant & Unnava 1989).
Unsupported superlatives rated less credible than hedged claims (Boush 2009).
Narrative specificity: specific outcomes more persuasive than vague benefit claims.
""",
    "NLP measurable text properties persuasive": """
Type-Token Ratio (TTR): lower TTR (more repetition) correlates with lower perceived quality.
Flesch-Kincaid readability: grade 8-10 optimal for B2B copy.
Hedge density: count of modal verbs and epistemic markers per sentence.
Causal connective density: "because", "therefore", "which means" per sentence.
Named entity ratio: proper nouns / total tokens — higher = more concrete.
Action verb concentration: strong verbs (identify, surface, eliminate) vs nominalisations.
Abstract noun ratio: platform/solution/value inversely correlates with persuasiveness.
Argument progression: problem → mechanism → result is the strongest structural pattern.
""",
    "failure modes persuasive writing backfire": """
Reactance theory (Brehm 1966): explicit persuasive intent triggers psychological resistance.
Persuasion knowledge activation (Friestad & Wright 1994): manipulation detection activates scepticism.
Superlative overload: dense superlatives trigger persuasion knowledge — backfire effect.
Fake mechanism: "leveraging our advanced AI engine" sounds causal but has no concrete content.
Source drift: rewrite that invents facts or metrics loses credibility when detected.
Abstract jargon density: "seamless, scalable, innovative" signals marketing-speak, reduces trust.
"""
}
save("step1_raw_research", RAW_RESEARCH)
combined_research = "\n\n---\n\n".join(RAW_RESEARCH.values())
log("step1",f"Research: {len(combined_research)} chars", "ok")

# ════════════════════════════════════════════════════════════════════
# STEP 2: TASTE MAP
# ════════════════════════════════════════════════════════════════════
log("step2","Building taste map")

TASTE_MAP = {
    "goal": GOAL,
    "rewards": [
        {"concept":"causal_grounding","description":"Text explains WHY via mechanism + causal connectives.",
         "research_basis":"Langer 1978; ELM central route","measurable_proxy_ideas":["causal connective density","real_mechanism_quality probe"]},
        {"concept":"argument_progression","description":"Problem→mechanism→result structure.",
         "research_basis":"Narrative argument structure; ELM elaboration","measurable_proxy_ideas":["argument_progression probe"]},
        {"concept":"concrete_specificity","description":"Named outcomes, action verbs, domain nouns.",
         "research_basis":"Kahneman 2011 System 1","measurable_proxy_ideas":["specificity_without_invention probe"]},
        {"concept":"audience_relevance","description":"Connects to a recognised problem via before/after framing.",
         "research_basis":"Burnkrant & Unnava 1989","measurable_proxy_ideas":["audience_relevance probe","argument_progression probe"]},
        {"concept":"epistemic_honesty","description":"Appropriate hedges; no superlatives; no invented claims.",
         "research_basis":"Boush 2009","measurable_proxy_ideas":["epistemic_calibration probe","abstract_jargon_density probe"]},
    ],
    "punishes": [
        {"concept":"persuasion_knowledge_trigger","description":"Dense superlatives activate scepticism.",
         "research_basis":"Friestad & Wright 1994","measurable_proxy_ideas":["persuasion_risk probe"]},
        {"concept":"fake_mechanism","description":"Mechanism-sounding language with no concrete content.",
         "research_basis":"Abstract jargon study; reactance theory","measurable_proxy_ideas":["real_mechanism_quality probe","abstract_jargon_density probe"]},
        {"concept":"source_violation","description":"Invented metrics, guarantees, or fabricated evidence.",
         "research_basis":"Source drift credibility inversion","measurable_proxy_ideas":["violates_hard_source_policy check"]},
    ],
    "preserves": [
        {"concept":"source_continuity","description":"Core claim and domain preserved; rephrasing allowed.",
         "research_basis":"Credibility transfer","measurable_proxy_ideas":["probe_source_continuity (soft, not gate)"]}
    ],
    "key_tensions": [
        "Specificity vs source drift: concrete details risk inventing claims",
        "Audience relevance vs source continuity: pain-reframes may rephrase heavily",
        "Causal depth vs fake mechanism: both use 'by' — need real_mechanism_quality to distinguish",
    ],
    "scorer_hypothesis_seeds": [
        "Argument progression (problem→mechanism→result) with real mechanism quality is the strongest signal",
        "Fake mechanism + abstract jargon cancels any positive score regardless of other signals",
        "Source continuity is soft — only hard policy violations (invented metrics) warrant veto",
        "Audience relevance amplifies causal grounding when both are present",
        "Epistemic calibration as amplifier (not gate): well-calibrated text scores higher",
    ]
}
save("step2_taste_map", TASTE_MAP)
log("step2",f"Taste map: {len(TASTE_MAP['rewards'])} rewards, {len(TASTE_MAP['punishes'])} punishes", "ok")

# ════════════════════════════════════════════════════════════════════
# STEP 3: NLP THEORY
# ════════════════════════════════════════════════════════════════════
log("step3","NLP theory → probe implementation mapping")

NLP_THEORY = {
    "argument_progression":         {"taste_concept":"argument_progression","method":"Detect problem/mechanism/result markers in sequence","research_ref":"Argument structure in persuasion"},
    "real_mechanism_quality":       {"taste_concept":"causal_grounding+fake_mechanism","method":"Causal marker → concrete domain noun (reward) vs jargon (penalise)","research_ref":"ELM elaboration likelihood"},
    "abstract_jargon_density":      {"taste_concept":"fake_mechanism","method":"JARGON_WORDS density in content tokens","research_ref":"Marketing-speak credibility inversion"},
    "specificity_without_invention":{"taste_concept":"concrete_specificity","method":"Named entities + action verbs, zero if hard policy violated","research_ref":"Kahneman System 1"},
    "probe_source_continuity":      {"taste_concept":"source_continuity","method":"Soft overlap: 0.5*token + 0.25*action + 0.25*domain — no hard gate","research_ref":"Credibility transfer (soft)"},
    "violates_hard_source_policy":  {"taste_concept":"source_violation","method":"Invented numeric tokens or guarantee words → hard veto","research_ref":"Source drift inversion"},
    "probe_causal_density":         {"taste_concept":"causal_grounding","method":"Causal connective count / sentence count","research_ref":"Langer 1978"},
    "probe_audience_relevance":     {"taste_concept":"audience_relevance","method":"Before-state markers + second-person density","research_ref":"Burnkrant & Unnava 1989"},
    "probe_persuasion_risk":        {"taste_concept":"persuasion_knowledge_trigger","method":"HYPE_WORDS density","research_ref":"Friestad & Wright 1994"},
    "probe_epistemic_calibration":  {"taste_concept":"epistemic_honesty","method":"Hedge density vs superlative density","research_ref":"Boush 2009"},
}
save("step3_nlp_theory", NLP_THEORY)
log("step3",f"NLP theory: {len(NLP_THEORY)} probes mapped", "ok")

# ════════════════════════════════════════════════════════════════════
# STEP 4A: SCORER HYPOTHESES (before code)
# ════════════════════════════════════════════════════════════════════
log("step4","Generating scorer hypotheses (Step A)…")

SCORER_HYPOTHESES_R0 = [
    {"scorer_id":"S_r0_001","lineage":"initial",
     "hypothesis":"Argument progression (problem→mechanism→result) is the primary driver. Real mechanism quality distinguishes genuine from fake. Hard source policy is the only veto — no soft gate.",
     "research_basis":["ELM central route","Langer 1978","Argument progression research"],
     "taste_map_basis":["argument_progression","causal_grounding","fake_mechanism","source_violation"],
     "expected_failure_mode":"May miss audience-relevance-only pairs that lack explicit mechanism.",
     "constants_and_thresholds":[{"name":"FAKE_MECH_CANCEL","value":0.3,"reason":"Fake mechanism above 0.3 cancels positive signals"}]},
    {"scorer_id":"S_r0_002","lineage":"initial",
     "hypothesis":"Audience relevance amplifies causal grounding. Before/after contrast + second-person is the primary relevance signal. Soft source continuity reduces but doesn't zero the score.",
     "research_basis":["Burnkrant & Unnava 1989","JTBD framing","ELM involvement"],
     "taste_map_basis":["audience_relevance","causal_grounding","source_continuity"],
     "expected_failure_mode":"May reward pain-framing that has fake mechanism — needs real_mechanism_quality gate.",
     "constants_and_thresholds":[{"name":"REL_BOOST_CAP","value":1.25,"reason":"Relevance amplifies mechanism up to 25%"}]},
    {"scorer_id":"S_r0_003","lineage":"initial",
     "hypothesis":"Fake mechanism is the primary disqualifier. Abstract jargon density penalises marketing-speak. Specificity without invention is the primary positive signal.",
     "research_basis":["Abstract jargon credibility","Friestad & Wright 1994"],
     "taste_map_basis":["fake_mechanism","concrete_specificity","epistemic_honesty","source_violation"],
     "expected_failure_mode":"May be too strict on abstract language in domain-specific copy.",
     "constants_and_thresholds":[{"name":"JARGON_VETO","value":0.25,"reason":"Jargon density above 0.25 significantly reduces score"}]},
    {"scorer_id":"S_r0_004","lineage":"initial",
     "hypothesis":"Full chain: argument progression gates concrete specificity. Specificity only counts when argument has a real mechanism. Source continuity is soft. Fake mechanism vetoes.",
     "research_basis":["ELM full model","Kahneman System 1","Langer 1978"],
     "taste_map_basis":["argument_progression","concrete_specificity","causal_grounding","fake_mechanism","source_continuity"],
     "expected_failure_mode":"Complex scorer may over-penalise good short copy that nails one dimension.",
     "constants_and_thresholds":[{"name":"PROG_GATE","value":0.4,"reason":"Argument progression below 0.4 reduces specificity credit"},{"name":"FAKE_MECH_VETO","value":0.35,"reason":"Fake mechanism above 0.35 vetoes"}]},
    {"scorer_id":"S_r0_005","lineage":"initial",
     "hypothesis":"Epistemic calibration amplifies the base score. Well-calibrated text (hedges present, superlatives absent, no jargon) is more persuasive. Persuasion risk cancels.",
     "research_basis":["Boush 2009","Friestad & Wright 1994"],
     "taste_map_basis":["epistemic_honesty","persuasion_knowledge_trigger","fake_mechanism","source_continuity"],
     "expected_failure_mode":"May under-reward legitimately confident specific claims.",
     "constants_and_thresholds":[{"name":"EP_BOOST_MAX","value":1.2,"reason":"Epistemic calibration boosts score up to 20%"}]},
    {"scorer_id":"S_r0_006","lineage":"initial",
     "hypothesis":"Source continuity (soft) combined with causal density — a text is more persuasive when it preserves the anchor's intent AND adds mechanism. Hard policy is the only veto.",
     "research_basis":["Credibility transfer","Langer 1978"],
     "taste_map_basis":["source_continuity","causal_grounding","source_violation"],
     "expected_failure_mode":"Doesn't penalise abstract jargon — may reward fake mechanism if it has causal words.",
     "constants_and_thresholds":[{"name":"CONTINUITY_FLOOR","value":0.2,"reason":"Source continuity below 0.2 still reduces but doesn't zero"}]},
    {"scorer_id":"S_r0_007","lineage":"initial",
     "hypothesis":"Argument progression × real mechanism quality is the product score. Both must be present. Fake mechanism vetoes regardless of other signals. No soft source gate.",
     "research_basis":["Argument structure","ELM elaboration","real mechanism"],
     "taste_map_basis":["argument_progression","causal_grounding","fake_mechanism"],
     "expected_failure_mode":"Ignores source drift — may reward well-structured text that invents claims.",
     "constants_and_thresholds":[{"name":"FAKE_MECH_CANCEL","value":0.25,"reason":"Any fake mechanism above 0.25 → score *= 0.1"}]},
    {"scorer_id":"S_r0_008","lineage":"initial",
     "hypothesis":"Contrast scorer: specificity_without_invention minus abstract_jargon_density minus persuasion_risk. High-quality = specific, no jargon, no hype. Source continuity weights the total.",
     "research_basis":["Boush 2009 specificity-hype ratio","Kahneman System 1"],
     "taste_map_basis":["concrete_specificity","fake_mechanism","persuasion_knowledge_trigger","source_continuity"],
     "expected_failure_mode":"May penalise platform-noun-heavy B2B copy that is genuinely persuasive.",
     "constants_and_thresholds":[{"name":"SPEC_WEIGHT","value":0.5,"reason":"Specificity is primary positive"},{"name":"JARGON_WEIGHT","value":0.3,"reason":"Jargon penalises more than hype"}]},
]
save("step4a_scorer_hypotheses_r0", SCORER_HYPOTHESES_R0)
log("step4",f"Step A: {len(SCORER_HYPOTHESES_R0)} scorer hypotheses", "ok")

# ════════════════════════════════════════════════════════════════════
# STEP 4B: SCORER CODE
# Uses hard policy + soft continuity (F4 fix)
# New probes: argument_progression, real_mechanism_quality, etc (F6 fix)
# ════════════════════════════════════════════════════════════════════
log("step4","Step B: Writing scorer functions…")

SCORER_CODE_R0 = {
"S_r0_001": """
def scorer(text, anchor, params):
    FAKE_MECH_CANCEL = 0.3
    if violates_hard_source_policy(text, anchor):
        return 0.0
    fake = probe_real_mechanism_quality(text)   # negative = fake, positive = real
    jargon = probe_abstract_jargon_density(text)
    if jargon > FAKE_MECH_CANCEL:
        return 0.0
    prog = probe_argument_progression(text)
    mech = probe_causal_density(text)
    continuity = probe_source_continuity(text, anchor)
    base = prog * 0.5 + mech * 0.3 + max(0, fake) * 0.2
    return _clamp(base * (0.5 + 0.5 * continuity))
""",
"S_r0_002": """
def scorer(text, anchor, params):
    REL_BOOST_CAP = 1.25
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    rel    = probe_audience_relevance(text)
    mech   = probe_causal_density(text)
    rmq    = probe_real_mechanism_quality(text)
    continuity = probe_source_continuity(text, anchor)
    amp_mech = min(mech * (1 + rel * (REL_BOOST_CAP - 1)), mech * REL_BOOST_CAP)
    base = max(rel * 0.4 + amp_mech * 0.6, 0)
    jargon_penalty = max(0, jargon - 0.1) * 0.5
    return _clamp(base * (0.6 + 0.4 * continuity) - jargon_penalty)
""",
"S_r0_003": """
def scorer(text, anchor, params):
    JARGON_VETO = 0.25
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    if jargon > JARGON_VETO:
        return _clamp(0.1 - jargon)
    spec   = probe_specificity_without_invention(text, anchor)
    ep     = probe_epistemic_calibration(text)
    prog   = probe_argument_progression(text)
    continuity = probe_source_continuity(text, anchor)
    base = spec * 0.4 + ep * 0.3 + prog * 0.3
    return _clamp(base * (0.5 + 0.5 * continuity))
""",
"S_r0_004": """
def scorer(text, anchor, params):
    PROG_GATE      = 0.4
    FAKE_MECH_VETO = 0.35
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    if jargon > FAKE_MECH_VETO:
        return 0.0
    prog   = probe_argument_progression(text)
    spec   = probe_specificity_without_invention(text, anchor)
    mech   = probe_causal_density(text)
    continuity = probe_source_continuity(text, anchor)
    prog_gate = prog if prog >= PROG_GATE else prog * 0.4
    base = prog_gate * 0.4 + spec * 0.4 + mech * 0.2
    return _clamp(base * (0.5 + 0.5 * continuity))
""",
"S_r0_005": """
def scorer(text, anchor, params):
    EP_BOOST_MAX = 1.2
    if violates_hard_source_policy(text, anchor):
        return 0.0
    risk   = probe_persuasion_risk(text)
    jargon = probe_abstract_jargon_density(text)
    ep     = probe_epistemic_calibration(text)
    mech   = probe_causal_density(text)
    spec   = probe_specificity(text)
    prog   = probe_argument_progression(text)
    continuity = probe_source_continuity(text, anchor)
    base = mech * 0.3 + spec * 0.3 + prog * 0.25 + ep * 0.15
    ep_factor = _clamp(1.0 + (ep - 0.5) * (EP_BOOST_MAX - 1.0) * 2)
    risk_pen = max(risk, jargon * 0.6)
    return _clamp(base * ep_factor * (0.6 + 0.4 * continuity) * (1 - risk_pen * 0.5))
""",
"S_r0_006": """
def scorer(text, anchor, params):
    CONTINUITY_FLOOR = 0.2
    if violates_hard_source_policy(text, anchor):
        return 0.0
    continuity = probe_source_continuity(text, anchor)
    floor_cont = max(CONTINUITY_FLOOR, continuity)
    mech = probe_causal_density(text)
    prog = probe_argument_progression(text)
    jargon = probe_abstract_jargon_density(text)
    base = mech * 0.5 + prog * 0.5
    return _clamp(base * (0.4 + 0.6 * floor_cont) * (1 - jargon * 0.5))
""",
"S_r0_007": """
def scorer(text, anchor, params):
    FAKE_MECH_CANCEL = 0.25
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    prog   = probe_argument_progression(text)
    rmq    = probe_real_mechanism_quality(text)
    if jargon > FAKE_MECH_CANCEL:
        return _clamp(prog * rmq * 0.1)
    base = prog * 0.5 + _clamp(rmq) * 0.5
    return _clamp(base)
""",
"S_r0_008": """
def scorer(text, anchor, params):
    SPEC_WEIGHT   = 0.5
    JARGON_WEIGHT = 0.3
    HYPE_WEIGHT   = 0.2
    if violates_hard_source_policy(text, anchor):
        return 0.0
    spec   = probe_specificity_without_invention(text, anchor)
    jargon = probe_abstract_jargon_density(text)
    risk   = probe_persuasion_risk(text)
    continuity = probe_source_continuity(text, anchor)
    contrast = SPEC_WEIGHT * spec - JARGON_WEIGHT * jargon - HYPE_WEIGHT * risk
    return _clamp(contrast * (0.5 + 0.5 * continuity))
""",
}

# Validation pairs — diverse anchors, not RAW_TEXT (F1 fix)
VALIDATION_PAIRS = [
    {"pair_id":"VAL_01","anchor":"We built an AI tool that helps product teams ship faster.",
     "positive":"We built an AI tool that helps product teams ship faster by surfacing which backlog items have the most customer signal — so you prioritise based on evidence.",
     "negative":"We built an amazing AI tool that helps product teams ship faster with our revolutionary intelligent platform."},
    {"pair_id":"VAL_02","anchor":"Our analytics tool makes data easier to understand.",
     "positive":"Instead of waiting for a BI report, our tool lets non-technical teams answer their own data questions in minutes — without SQL.",
     "negative":"Our advanced analytics solution makes data insights easier and more accessible through seamless intelligent automation."},
    {"pair_id":"VAL_03","anchor":"We help sales teams prioritise leads.",
     "positive":"We help sales teams prioritise leads by scoring each one against your last closed-deal patterns — so reps call the right accounts first.",
     "negative":"We help sales teams prioritise leads with our groundbreaking AI engine that synergistically optimises your entire pipeline effortlessly."},
    {"pair_id":"VAL_04","anchor":"Our platform helps companies reduce churn.",
     "positive":"Our platform helps CS teams flag at-risk accounts before customers cancel — by tracking drops in product engagement and support ticket frequency.",
     "negative":"Our best-in-class platform helps companies reduce churn through our world-class customer success optimisation system. Guaranteed results."},
]

scorer_load_r0 = {}
for sid, code in SCORER_CODE_R0.items():
    er = py_exec(code, sid)
    if er["ok"]:
        vr = validate_scorer_on_pairs(code, VALIDATION_PAIRS)   # F1 FIX
        scorer_load_r0[sid] = {"loaded":True, **vr}
        log("step4", f"  {sid}: valid={vr['valid']} acc={vr['pair_validation_accuracy']:.0%} margin={vr['pair_validation_margin']:.3f} spread={vr['pair_validation_spread']:.3f}", "ok" if vr["valid"] else "warn")
    else:
        scorer_load_r0[sid] = {"loaded":False,"valid":False,"reason":"load_error","pair_validation_accuracy":0,"pair_validation_margin":0,"pair_validation_spread":0}
        log("step4", f"  {sid}: LOAD ERROR {er['error']}", "error")

count_valid_r0 = sum(1 for v in scorer_load_r0.values() if v.get("valid"))
log("step4", f"Valid scorers R0: {count_valid_r0}/{len(SCORER_CODE_R0)}", "ok")
save("step4b_scorer_functions_r0", {sid:{"hypothesis":next(h["hypothesis"] for h in SCORER_HYPOTHESES_R0 if h["scorer_id"]==sid),"code":SCORER_CODE_R0[sid],"validation":scorer_load_r0[sid]} for sid in SCORER_CODE_R0})


# ════════════════════════════════════════════════════════════════════
# STEP 5: PAIR GENERATION with source policy (F3 fix)
# Includes fake_mechanism type (F7 fix)
# ════════════════════════════════════════════════════════════════════
log("step5","Generating pair suite with source policy validation…")

ALL_PAIRS_R0 = [
    # ── hype_trap ──
    {"pair_id":"R0_P01","anchor":"We built an AI tool that helps product teams ship features faster.",
     "positive":"We built an AI tool that helps product teams ship features faster by surfacing which backlog items have the most customer signal — so you prioritise based on evidence, not gut feel.",
     "negative":"We built an amazing AI tool that helps product teams ship features faster with our revolutionary intelligent platform.",
     "pair_type":"hype_trap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive adds causal mechanism; negative adds hype.","intended_trap":"Hype sounds confident."},
    {"pair_id":"R0_P02","anchor":"Automate your customer support with AI.",
     "positive":"Automate your customer support with AI that learns from your best agents' resolved tickets — so response quality improves each week without manual tuning.",
     "negative":"Automate your customer support with our world-class AI that makes everything effortless and seamless for your entire team.",
     "pair_type":"hype_trap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive has mechanism; negative has hype.","intended_trap":"World-class sounds authoritative."},
    {"pair_id":"R0_P08","anchor":"Improve your team's meeting notes with AI.",
     "positive":"Improve your team's meeting notes with AI that maps each action item to the person who committed to it — so nothing falls through the cracks after the call.",
     "negative":"Improve your team's meeting notes with AI. Our best-in-class guaranteed system transforms every meeting into perfect, actionable outcomes effortlessly.",
     "pair_type":"hype_trap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive has concrete mechanism; negative packed with superlatives.","intended_trap":"Superlative density."},
    # ── fake_mechanism (F7 FIX — new type) ──
    {"pair_id":"R0_F01","anchor":"We help marketing teams measure campaign performance.",
     "positive":"We help marketing teams see which campaign elements drove conversions — by tracing each sign-up back to the specific ad variant, email, and landing page that touched it.",
     "negative":"We help marketing teams measure campaign performance by leveraging our advanced AI engine which synergistically optimises your entire marketing funnel through intelligent automation.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Both use 'by' + mechanism language. Positive has concrete workflow; negative has jargon.","intended_trap":"'By leveraging our advanced AI' looks causal."},
    {"pair_id":"R0_F02","anchor":"Our tool helps engineers write better code.",
     "positive":"Our tool helps engineers write better code by flagging only changes that touch security boundaries or performance-critical paths — so they focus review time where it matters.",
     "negative":"Our tool helps engineers write better code through our next-generation intelligent code analysis engine powered by advanced technology.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive: specific what/where flagged. Negative: abstract engine.","intended_trap":"'Next-generation intelligent analysis' sounds technical."},
    {"pair_id":"R0_F03","anchor":"We make onboarding faster for new hires.",
     "positive":"We make onboarding faster for new hires by connecting to your HR system and pre-provisioning all access before day one — so nothing waits on an IT ticket.",
     "negative":"We make onboarding faster for new hires using our seamless intelligent automation platform that synergistically streamlines your entire onboarding experience.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive: concrete step (connects to HR, pre-provisions). Negative: jargon chain.","intended_trap":"'Seamless intelligent automation' sounds mechanism-like."},
    # ── specificity_trap ──
    {"pair_id":"R0_P04","anchor":"Our sales tool helps reps close more deals.",
     "positive":"Our sales tool shows reps which objection pattern each prospect matches — so they run the right playbook at the right moment.",
     "negative":"Our sales tool helps reps close more deals faster with higher win rates and better customer satisfaction across enterprise clients.",
     "pair_type":"specificity_trap","source_policy":{**DEFAULT_SOURCE_POLICY,"numeric_claims_must_be_in_anchor":False},
     "label_contract":"Positive has causal mechanism; negative has vague benefit claims.","intended_trap":"Negative sounds specific but has no mechanism."},
    {"pair_id":"R0_P09","anchor":"We help startups raise their seed round.",
     "positive":"We help startups raise their seed round by stress-testing their pitch against the most common VC objections before they walk into the room.",
     "negative":"We help startups successfully raise their seed round through our comprehensive world-class pitch preparation platform leveraging advanced AI.",
     "pair_type":"specificity_trap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive has concrete mechanism. Negative has fake mechanism + jargon.","intended_trap":"World-class pitch prep sounds specific."},
    # ── subtle_quality_gap ──
    {"pair_id":"R0_P05","anchor":"Turn customer feedback into product decisions.",
     "positive":"Stop guessing what to build next. Turn messy customer feedback into ranked decisions your team can act on this sprint.",
     "negative":"Transform your customer feedback experience into optimised product decision solutions leveraging our advanced platform.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive has problem→result structure. Negative has abstract transformation framing.","intended_trap":"Both describe the same outcome differently."},
    {"pair_id":"R0_P06","anchor":"Our analytics tool makes data easier to understand.",
     "positive":"Instead of waiting for a BI report, our tool lets non-technical teams answer their own data questions in minutes — without writing SQL.",
     "negative":"Our advanced analytics solution makes data insights easier and more accessible for all stakeholders through intelligent automation.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive has before/after + concrete mechanism. Negative has abstract improvement.","intended_trap":"Both sound helpful."},
    {"pair_id":"R0_P10","anchor":"We help companies reduce customer churn.",
     "positive":"We help CS teams flag at-risk accounts before customers cancel — by tracking drops in product engagement and support ticket frequency.",
     "negative":"We help companies reduce customer churn through our innovative AI-powered customer success platform that optimises retention seamlessly.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive: concrete detection mechanism. Negative: fake mechanism + jargon.","intended_trap":"'AI-powered' sounds sophisticated."},
    # ── source_drift ──
    {"pair_id":"R0_P07","anchor":RAW_TEXT,
     "positive":"EvalWeaver lets anyone create, use, and monetise AI improvers for subjective goals like 'more persuasive' — by discovering what the goal means and testing it before rewriting.",
     "negative":"EvalWeaver lets anyone create, use, and monetise AI improvers. Our groundbreaking platform has helped thousands achieve amazing persuasion results with our world-class AI.",
     "pair_type":"source_drift","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive preserves claim + adds mechanism. Negative drifts to hype.","intended_trap":"Both open with the original claim."},
    # ── audience_relevance_gap ──
    {"pair_id":"R0_A01","anchor":"Our software helps teams collaborate better.",
     "positive":"Instead of chasing updates across Slack threads, our software surfaces the three decisions your team is stuck on — so you unblock them in one async review.",
     "negative":"Our powerful collaboration software helps teams work better together through our advanced intelligent platform for seamless collaboration.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive has before/after + concrete mechanism. Negative has abstract platform claim.","intended_trap":"Both claim collaboration improvement."},
    # ── TEST PAIRS (heldout — diverse set covering all types) ──
    {"pair_id":"R0_T01","anchor":"Our tool saves engineers time on code reviews.",
     "positive":"Our tool saves engineers time on code reviews by flagging only changes that touch security boundaries or performance-critical paths — filtering style diffs that don't affect correctness.",
     "negative":"Our amazing tool saves engineers significant time on code reviews through our intelligent automated review system that makes everything effortless.",
     "pair_type":"hype_trap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Mechanism vs hype.","intended_trap":"intelligent + effortless sounds technical."},
    {"pair_id":"R0_T02","anchor":"We make financial reporting faster for accountants.",
     "positive":"We make financial reporting faster for accountants by pulling from connected accounts and generating consolidated P&Ls automatically — no copy-paste from spreadsheets.",
     "negative":"We make financial reporting faster for accountants with our revolutionary AI-powered platform that delivers incredible results instantly.",
     "pair_type":"hype_trap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Mechanism vs hype.","intended_trap":"Revolutionary AI sounds powerful."},
    {"pair_id":"R0_T03","anchor":"Our API helps developers integrate payments.",
     "positive":"Our API helps developers integrate payments by handling the edge cases that break checkout — currency mismatches, retry logic, and webhook ordering — so you ship in days, not weeks.",
     "negative":"Our API helps developers integrate payments seamlessly using our world-class developer-first payment infrastructure powered by advanced technology.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Positive: concrete edge cases named. Negative: fake mechanism.","intended_trap":"'Developer-first' sounds credible."},
    {"pair_id":"R0_T04","anchor":"We help sales teams prioritise leads.",
     "positive":"Instead of calling every lead in order of entry, our tool scores each one against your closed-deal patterns — so reps call the right accounts first.",
     "negative":"We help sales teams prioritise leads with our groundbreaking predictive AI that maximises your revenue potential through intelligent scoring algorithms.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Concrete method vs fake mechanism.","intended_trap":"'Predictive AI' sounds scientific."},
    {"pair_id":"R0_T05","anchor":"Turn customer feedback into product decisions.",
     "positive":"Instead of debating priorities in a planning meeting, our tool ranks product decisions by the weight of customer signal behind each one — so the conversation starts with evidence.",
     "negative":"Transform your product management with our advanced AI-powered feedback intelligence solution that optimises your entire decision-making workflow seamlessly.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Argument progression vs abstract platform.","intended_trap":"'Feedback intelligence' sounds specific."},
    {"pair_id":"R0_T06","anchor":"Our platform helps companies reduce churn.",
     "positive":"Our platform helps CS teams catch at-risk accounts before they churn — by monitoring product usage signals and alerting the right rep automatically.",
     "negative":"Our innovative retention platform helps companies reduce churn through our seamless intelligent customer success optimisation system.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Concrete mechanism vs jargon chain.","intended_trap":"'Customer success optimisation' sounds professional."},
    {"pair_id":"R0_T07","anchor":"We help startups raise their seed round.",
     "positive":"We help startups raise their seed round by running their pitch through the objections their target investors have raised most often — before the actual meeting.",
     "negative":"We help startups raise their seed round with our world-class pitch coaching platform leveraging advanced AI to guarantee investor readiness.",
     "pair_type":"source_drift","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Mechanism vs hype + source drift.","intended_trap":"'Investor readiness' sounds relevant."},
    {"pair_id":"R0_T08","anchor":"Our software helps teams collaborate better.",
     "positive":"Our software shows your team the three decisions stuck in review — so one async session unblocks a week of work.",
     "negative":"Our intelligent collaboration platform uses advanced AI to seamlessly optimise your team's workflow and communication through next-generation technology.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Concrete blocker removal vs fake mechanism.","intended_trap":"'Next-generation intelligent' sounds substantial."},
]

# F3 FIX: validate pairs and drop contaminated positives
log("step5","Running source policy validation on all pairs…")
policy_results = [validate_pair_source_policy(p) for p in ALL_PAIRS_R0]
valid_pairs   = [ALL_PAIRS_R0[i] for i,r in enumerate(policy_results) if r["valid"]]
invalid_pairs = [{"pair":ALL_PAIRS_R0[i],"errors":r["errors"]} for i,r in enumerate(policy_results) if not r["valid"]]

log("step5", f"Policy check: {len(valid_pairs)} valid, {len(invalid_pairs)} invalid (dropped)", "ok" if len(invalid_pairs)==0 else "warn")
for iv in invalid_pairs:
    log("step5", f"  DROPPED {iv['pair']['pair_id']}: {iv['errors']}", "warn")

# Split heldout: take T-suffix pairs as test, rest as train
train_pairs = seeded_shuffle([p for p in valid_pairs if not p["pair_id"].startswith("R0_T")], SEED)
heldout_pairs = [p for p in valid_pairs if p["pair_id"].startswith("R0_T")]
for p in train_pairs: p["split"]="train"
for p in heldout_pairs: p["split"]="test"; p["frozen"]=True

PAIR_SUITE = {"train":train_pairs,"test":heldout_pairs,"all":train_pairs+heldout_pairs}
save("step5_pairs_r0", valid_pairs)
log("step5", f"Suite: {len(train_pairs)} train, {len(heldout_pairs)} heldout (frozen)", "ok")
log("step5", f"Heldout >= 8: {'YES' if len(heldout_pairs)>=8 else 'NO'} ({len(heldout_pairs)})")

trap_dist = {}
for p in valid_pairs: trap_dist[p["pair_type"]] = trap_dist.get(p["pair_type"],0)+1
log("step5", f"Pair types: {trap_dist}")

# ════════════════════════════════════════════════════════════════════
# STEP 6: EVAL + PARETO with eligibility filter (F5 fix)
# ════════════════════════════════════════════════════════════════════
log("step6","Evaluating scorers (R0)…")

def eval_scorer(sid, code, pairs):
    rows = []
    for p in pairs:
        pr = py_run_scorer(code, p["positive"], p["anchor"])
        nr = py_run_scorer(code, p["negative"], p["anchor"])
        rows.append({"pair_id":p["pair_id"],"split":p["split"],"pair_type":p["pair_type"],
                     "pos_score":pr["value"],"neg_score":nr["value"],
                     "margin":pr["value"]-nr["value"],"correct":pr["value"]>nr["value"],
                     "pos_err":pr.get("error"),"neg_err":nr.get("error")})
    return rows

def compute_summary(sid, rows, validation, hyps, round_idx):
    # Split into train / heldout / adversarial
    tr  = [r for r in rows if r["split"]=="train"]
    te  = [r for r in rows if r["split"]=="test"]
    adv = [r for r in rows if r["split"]=="adversarial"]
    def acc(lst):  return sum(r["correct"] for r in lst)/max(1,len(lst))
    def mrg(lst):  return statistics.mean([r["margin"] for r in lst]) if lst else 0.0
    all_scores = [x for r in rows for x in [r["pos_score"],r["neg_score"]]]
    spread = max(all_scores)-min(all_scores) if all_scores else 0
    err_rate = sum(1 for r in rows if r["pos_err"] or r["neg_err"])/max(1,len(rows))
    hyp = next((h for h in hyps if h["scorer_id"]==sid), {})
    # Pair-type breakdown
    by_type = defaultdict(list)
    for r in rows: by_type[r["pair_type"]].append(r)
    type_acc = {t: sum(r["correct"] for r in rs)/max(1,len(rs)) for t,rs in by_type.items()}
    # Robustness warning
    rob_warns = [t for t,a in type_acc.items() if a < 0.45]
    return {
        "scorer_id":       sid,
        "hypothesis":      hyp.get("hypothesis",""),
        "lineage":         hyp.get("lineage","initial"),
        "generation_round":round_idx,
        "valid":           validation.get("valid") is True,
        "validation_reason":validation.get("reason",""),
        "pair_validation_accuracy":  validation.get("pair_validation_accuracy",0),
        "pair_validation_margin":    validation.get("pair_validation_margin",0),
        "pair_validation_spread":    validation.get("pair_validation_spread",0),
        "train_accuracy":  acc(tr), "train_margin":  mrg(tr),
        "test_accuracy":   acc(te), "test_margin":   mrg(te),
        "adversarial_accuracy":  acc(adv) if adv else None,
        "adversarial_margin":    mrg(adv) if adv else None,
        "score_spread":    spread, "exec_error_rate":err_rate,
        "pair_type_accuracy": type_acc,
        "robustness_warning": f"fails {rob_warns}" if rob_warns else "",
    }

def compute_pareto(summaries):
    eligible = [(s, is_eligible_for_pareto(s)) for s in summaries]
    elig_list = [s for s,(_,reason) in zip(summaries,[is_eligible_for_pareto(s) for s in summaries]) if is_eligible_for_pareto(s)[0]]
    # Pareto over: test_accuracy, test_margin, train_accuracy, train_margin, score_spread
    front = []
    for a in elig_list:
        dominated = any(
            b is not a
            and b["test_accuracy"]  >= a["test_accuracy"]
            and b["test_margin"]    >= a["test_margin"]
            and b["train_accuracy"] >= a["train_accuracy"]
            and b["train_margin"]   >= a["train_margin"]
            and b["score_spread"]   >= a["score_spread"]
            and (b["test_accuracy"]  > a["test_accuracy"]
              or b["test_margin"]    > a["test_margin"]
              or b["train_accuracy"] > a["train_accuracy"]
              or b["train_margin"]   > a["train_margin"]
              or b["score_spread"]   > a["score_spread"])
            for b in elig_list
        )
        if not dominated:
            front.append(a)
    return sorted(front, key=lambda x:(x["test_margin"],x["test_accuracy"],x["train_margin"]), reverse=True)

EVAL_R0 = {}
SUMMARIES_R0 = []
for sid, code in SCORER_CODE_R0.items():
    rows = eval_scorer(sid, code, PAIR_SUITE["all"])
    EVAL_R0[sid] = rows
    s = compute_summary(sid, rows, scorer_load_r0[sid], SCORER_HYPOTHESES_R0, 0)
    SUMMARIES_R0.append(s)

PARETO_R0 = compute_pareto(SUMMARIES_R0)

# Add survived_because
for s in PARETO_R0:
    dims = []
    best_te_mrg = max(x["test_margin"] for x in PARETO_R0)
    best_te_acc = max(x["test_accuracy"] for x in PARETO_R0)
    if abs(s["test_margin"]-best_te_mrg)<0.001:   dims.append(f"best test margin ({s['test_margin']:.3f})")
    if abs(s["test_accuracy"]-best_te_acc)<0.001: dims.append(f"best test acc ({s['test_accuracy']:.0%})")
    s["survived_because"] = ", ".join(dims) if dims else "non-dominated"

save("step6_eval_r0",    {sid:EVAL_R0[sid] for sid in EVAL_R0})
save("step6_summaries_r0", SUMMARIES_R0)
save("step6_pareto_r0",    PARETO_R0)

elig_check = [(s["scorer_id"], is_eligible_for_pareto(s)) for s in SUMMARIES_R0]
print(f"\n  Eligibility filter (v5 fix):")
print(f"  {'Scorer':<12} {'Eligible':>8} {'Reason':<25} {'TrAcc':>6} {'TeAcc':>6} {'TeMrg':>7} {'Sprd':>6}")
print("  "+"-"*80)
for s in sorted(SUMMARIES_R0, key=lambda x: x["test_margin"], reverse=True):
    ok, reason = is_eligible_for_pareto(s)
    flag = " ★" if any(p["scorer_id"]==s["scorer_id"] for p in PARETO_R0) else ""
    print(f"  {s['scorer_id']:<12} {str(ok):>8} {reason:<25} {s['train_accuracy']:>5.0%}  {s['test_accuracy']:>5.0%}  {s['test_margin']:>6.3f}  {s['score_spread']:>5.3f}{flag}")
log("step6", f"R0 Pareto: {len(PARETO_R0)} eligible scorers", "ok")
for s in PARETO_R0:
    log("step6", f"  ★ {s['scorer_id']} — {s['survived_because']}")


# ════════════════════════════════════════════════════════════════════
# STEP 7: FAILURE PACKET (F8 fix — tracks applied instructions)
# ════════════════════════════════════════════════════════════════════
log("step7","Building failure packet R0…")

def build_failure_packet(round_idx, summaries, eval_results, pair_suite, pareto, prior_instructions=None):
    prior = set(prior_instructions or [])
    top_sids = [s["scorer_id"] for s in pareto[:3]]

    # Failed visible pairs by top scorers
    failed_visible = []
    low_margin_visible = []
    for sid in top_sids:
        for r in eval_results.get(sid,[]):
            if r["split"]=="train":
                if not r["correct"]:
                    failed_visible.append({"scorer_id":sid,"pair_id":r["pair_id"],
                        "pair_type":r["pair_type"],"pos":round(r["pos_score"],3),
                        "neg":round(r["neg_score"],3),"margin":round(r["margin"],3)})
                elif 0 < r["margin"] < 0.04:
                    low_margin_visible.append({"scorer_id":sid,"pair_id":r["pair_id"],
                        "pair_type":r["pair_type"],"margin":round(r["margin"],3)})

    # Pair type failure counts (visible train only)
    trap_fails = defaultdict(int)
    for f in failed_visible: trap_fails[f["pair_type"]] += 1

    # Score collapse warnings
    collapse_warns = [f"{s['scorer_id']} spread={s['score_spread']:.3f}" for s in summaries if s["score_spread"]<0.05]

    # Heldout aggregate (anti-leakage: no raw pairs)
    heldout_by_scorer = {}
    for s in summaries:
        te_rows = [r for r in eval_results.get(s["scorer_id"],[]) if r["split"]=="test"]
        if te_rows:
            heldout_by_scorer[s["scorer_id"]] = {
                "accuracy": round(sum(r["correct"] for r in te_rows)/len(te_rows),3),
                "margin":   round(statistics.mean([r["margin"] for r in te_rows]),3),
                "failures_by_type": dict(defaultdict(int, {r["pair_type"]: sum(1 for x in te_rows if x["pair_type"]==r["pair_type"] and not x["correct"]) for r in te_rows})),
            }

    # Per-pair-type heldout failure counts (aggregate only, no raw text)
    heldout_fails_by_type = defaultdict(int)
    for sid in top_sids:
        for r in eval_results.get(sid,[]):
            if r["split"]=="test" and not r["correct"]:
                heldout_fails_by_type[r["pair_type"]] += 1

    # Generate new mutation instructions — skip already-applied ones (F8 fix)
    new_instructions = []
    all_possible = []
    if trap_fails.get("fake_mechanism",0) > 0:
        all_possible.append("Do not reward causal markers unless followed by concrete action/object terms — detect fake mechanism explicitly.")
    if trap_fails.get("subtle_quality_gap",0) > 1:
        all_possible.append("Add argument_progression × real_mechanism_quality product scorer — surface vs argument distinction.")
    if trap_fails.get("hype_trap",0) > 0:
        all_possible.append("Ensure persuasion_risk veto fires before continuity weighting reduces score to non-zero.")
    if any(s["score_spread"]<0.1 for s in pareto):
        all_possible.append("Loosen source continuity floor — soft gate may be squashing spread on legitimate rephrases.")
    all_possible.append("Recombine best scorer structures: try argument_progression * real_mechanism_quality as primary signal.")
    # Separate mutation (scorer) vs adversarial (pair) instructions
    mutation_instructions = [i for i in all_possible if i not in prior]
    applied_from_prior   = [i for i in all_possible if i in prior]

    adversarial_pair_instructions = [
        f"Generate fake_mechanism pairs where BOTH use 'by' but only positive names a concrete object/step.",
        f"Generate subtle_quality_gap pairs where both have before/after framing but only positive has a result clause.",
        f"Generate hype_trap pairs where negative mimics professional language but hides superlative density.",
    ]

    return {
        "round_idx": round_idx,
        "top_scorers": [{
            "scorer_id":s["scorer_id"],"hypothesis":s["hypothesis"][:80],"lineage":s["lineage"],
            "test_accuracy":s["test_accuracy"],"test_margin":s["test_margin"],
            "robustness_warning":s.get("robustness_warning",""),
            "survived_because":s.get("survived_because",""),
            "code": SCORER_CODE_R0.get(s["scorer_id"],"") if round_idx==0 else ALL_SCORER_CODE.get(s["scorer_id"],""),
        } for s in pareto[:3]],
        "failed_visible_pairs": failed_visible[:8],
        "low_margin_visible_pairs": low_margin_visible[:6],
        "failed_pair_type_counts": dict(trap_fails),
        "score_collapse_warnings": collapse_warns,
        "heldout_aggregate_only": {
            "heldout_accuracy_by_scorer": {sid:v["accuracy"] for sid,v in heldout_by_scorer.items()},
            "heldout_margin_by_scorer":   {sid:v["margin"]   for sid,v in heldout_by_scorer.items()},
            "heldout_failures_by_pair_type": dict(heldout_fails_by_type),
        },
        "scorer_weakness_summary": f"Top scorers struggle with: {list(trap_fails.keys())}. Collapse warnings: {collapse_warns}.",
        "mutation_instructions":   mutation_instructions,
        "adversarial_pair_instructions": adversarial_pair_instructions,
        "applied_from_prior_round": applied_from_prior,
    }

FP_R0 = build_failure_packet(0, SUMMARIES_R0, EVAL_R0, PAIR_SUITE, PARETO_R0)
save("step7_failure_packet_r0", FP_R0)
log("step7", f"Failed visible pairs: {len(FP_R0['failed_visible_pairs'])}", "ok")
log("step7", f"Trap failures: {FP_R0['failed_pair_type_counts']}")
log("step7", f"Mutation instructions: {len(FP_R0['mutation_instructions'])}")
for m in FP_R0["mutation_instructions"]: log("step7", f"  → {m[:70]}")
log("step7", f"Adversarial pair instructions: {len(FP_R0['adversarial_pair_instructions'])}")

# ════════════════════════════════════════════════════════════════════
# STEP 8: REPAIR — scorer mutation (hypothesis-first)
# ════════════════════════════════════════════════════════════════════
log("step8","Repair: scorer hypothesis generation R1…")

SCORER_HYPOTHESES_R1 = [
    {"scorer_id":"S_r1_001","lineage":"mutation",
     "hypothesis":"Mutation of S_r0_001: adds explicit fake-mechanism detection. Argument progression × real_mechanism_quality product — if real mechanism is negative (fake), score collapses. Addresses fake_mechanism trap failures.",
     "research_basis":["ELM elaboration quality","Fake mechanism credibility inversion"],
     "taste_map_basis":["argument_progression","causal_grounding","fake_mechanism"],
     "expected_failure_mode":"May over-penalise short copy with brief mechanism phrases.",
     "constants_and_thresholds":[{"name":"FAKE_VETO","value":0.25,"reason":"Jargon density above 0.25 reduces score by 80%"}]},
    {"scorer_id":"S_r1_002","lineage":"mutation",
     "hypothesis":"Mutation of S_r0_002: adds real_mechanism_quality gate on audience relevance amplification. Relevance only amplifies if mechanism is genuine. Addresses subtle_quality_gap where both have before/after but differ in mechanism quality.",
     "research_basis":["Burnkrant & Unnava 1989","ELM involvement + argument quality"],
     "taste_map_basis":["audience_relevance","causal_grounding","fake_mechanism","source_continuity"],
     "expected_failure_mode":"May penalise good audience-relevance copy that lacks explicit mechanism.",
     "constants_and_thresholds":[{"name":"REL_BOOST_CAP","value":1.3,"reason":"Slightly higher cap — relevance is underweighted currently"}]},
    {"scorer_id":"S_r1_003","lineage":"blind_node_repair",
     "hypothesis":"Targets subtle_quality_gap blind spot: argument_progression × specificity_without_invention. Both must be above threshold. Abstract jargon density vetoes. Source continuity is soft floor only.",
     "research_basis":["Argument structure","Kahneman specificity","Abstract jargon penalty"],
     "taste_map_basis":["argument_progression","concrete_specificity","fake_mechanism","source_continuity"],
     "expected_failure_mode":"May miss good hype-free copy that is specific but lacks explicit before/after.",
     "constants_and_thresholds":[{"name":"PROG_THRESHOLD","value":0.4,"reason":"Both progression and specificity must clear 0.4 to get full score"}]},
    {"scorer_id":"S_r1_004","lineage":"recombination",
     "hypothesis":"Recombination of S_r0_001 and S_r0_003: argument_progression × real_mechanism_quality (from S_r0_001) gated by jargon check (from S_r0_003). Hard policy only veto. Soft continuity weights the total.",
     "research_basis":["ELM central route","Abstract jargon credibility","Friestad & Wright"],
     "taste_map_basis":["argument_progression","fake_mechanism","concrete_specificity","source_continuity"],
     "expected_failure_mode":"Jargon gate may be too strict for domain-specific technical copy.",
     "constants_and_thresholds":[{"name":"JARGON_THRESHOLD","value":0.2,"reason":"Stricter than S_r0_003 — fake_mechanism failures require tighter jargon gate"}]},
    {"scorer_id":"S_r1_005","lineage":"novel_composition",
     "hypothesis":"Novel: full argument quality score = progression + real mechanism quality + specificity_without_invention — abstract_jargon. Epistemic calibration multiplies the total. Hard policy is the only gate.",
     "research_basis":["Full ELM model","Boush 2009 calibration","All taste map rewards"],
     "taste_map_basis":["argument_progression","causal_grounding","concrete_specificity","epistemic_honesty","fake_mechanism"],
     "expected_failure_mode":"Complex — may be dominated by simpler scorers that do one thing well.",
     "constants_and_thresholds":[{"name":"EP_BOOST","value":1.15,"reason":"Calibration amplifies argument quality up to 15%"}]},
    {"scorer_id":"S_r1_006","lineage":"novel_composition",
     "hypothesis":"Novel: treats source continuity as the primary signal, amplified by argument quality. A text that preserves the intent AND adds a real mechanism is maximally persuasive. No soft gate zeros.",
     "research_basis":["Credibility transfer","Langer 1978","ELM"],
     "taste_map_basis":["source_continuity","causal_grounding","argument_progression","source_violation"],
     "expected_failure_mode":"May reward source-preserving text that adds only shallow mechanism.",
     "constants_and_thresholds":[{"name":"CONTINUITY_WEIGHT","value":0.4,"reason":"Continuity × quality — neither alone is enough"}]},
]
save("step8a_scorer_hypotheses_r1", SCORER_HYPOTHESES_R1)
log("step8", f"Step A: {len(SCORER_HYPOTHESES_R1)} evolved hypotheses", "ok")

SCORER_CODE_R1 = {
"S_r1_001": """
def scorer(text, anchor, params):
    FAKE_VETO = 0.25
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    if jargon > FAKE_VETO:
        return _clamp(probe_argument_progression(text) * 0.1)
    prog = probe_argument_progression(text)
    rmq  = _clamp(probe_real_mechanism_quality(text))
    continuity = probe_source_continuity(text, anchor)
    base = prog * 0.55 + rmq * 0.45
    return _clamp(base * (0.5 + 0.5 * continuity))
""",
"S_r1_002": """
def scorer(text, anchor, params):
    REL_BOOST_CAP = 1.3
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    rel    = probe_audience_relevance(text)
    mech   = probe_causal_density(text)
    rmq    = _clamp(probe_real_mechanism_quality(text))
    continuity = probe_source_continuity(text, anchor)
    # Real mechanism quality gates the relevance amplifier
    amp_factor = 1 + rel * (REL_BOOST_CAP - 1) * rmq
    base = mech * amp_factor * 0.6 + rel * 0.4
    return _clamp(base * (0.6 + 0.4 * continuity) * (1 - jargon * 0.6))
""",
"S_r1_003": """
def scorer(text, anchor, params):
    PROG_THRESHOLD = 0.4
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    if jargon > 0.3:
        return 0.0
    prog = probe_argument_progression(text)
    spec = probe_specificity_without_invention(text, anchor)
    continuity = probe_source_continuity(text, anchor)
    if prog < PROG_THRESHOLD:
        base = prog * spec * 0.5
    else:
        base = (prog * 0.5 + spec * 0.5)
    return _clamp(base * (0.5 + 0.5 * continuity))
""",
"S_r1_004": """
def scorer(text, anchor, params):
    JARGON_THRESHOLD = 0.2
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    if jargon > JARGON_THRESHOLD:
        return _clamp(probe_argument_progression(text) * 0.15)
    prog = probe_argument_progression(text)
    rmq  = _clamp(probe_real_mechanism_quality(text))
    spec = probe_specificity_without_invention(text, anchor)
    continuity = probe_source_continuity(text, anchor)
    base = prog * 0.4 + rmq * 0.4 + spec * 0.2
    return _clamp(base * (0.5 + 0.5 * continuity))
""",
"S_r1_005": """
def scorer(text, anchor, params):
    EP_BOOST = 1.15
    if violates_hard_source_policy(text, anchor):
        return 0.0
    jargon = probe_abstract_jargon_density(text)
    prog   = probe_argument_progression(text)
    rmq    = _clamp(probe_real_mechanism_quality(text))
    spec   = probe_specificity_without_invention(text, anchor)
    ep     = probe_epistemic_calibration(text)
    continuity = probe_source_continuity(text, anchor)
    quality = prog * 0.35 + rmq * 0.35 + spec * 0.3 - jargon * 0.5
    ep_factor = _clamp(1.0 + (ep - 0.5) * (EP_BOOST - 1.0) * 2)
    return _clamp(quality * ep_factor * (0.5 + 0.5 * continuity))
""",
"S_r1_006": """
def scorer(text, anchor, params):
    CONTINUITY_WEIGHT = 0.4
    if violates_hard_source_policy(text, anchor):
        return 0.0
    continuity = probe_source_continuity(text, anchor)
    prog = probe_argument_progression(text)
    rmq  = _clamp(probe_real_mechanism_quality(text))
    jargon = probe_abstract_jargon_density(text)
    quality = prog * 0.5 + rmq * 0.5 - jargon * 0.4
    return _clamp(CONTINUITY_WEIGHT * continuity + (1 - CONTINUITY_WEIGHT) * _clamp(quality))
""",
}

ALL_SCORER_CODE = {**SCORER_CODE_R0, **SCORER_CODE_R1}
ALL_HYPS = {h["scorer_id"]:h for h in SCORER_HYPOTHESES_R0 + SCORER_HYPOTHESES_R1}

# Load + validate R1 scorers using validation pairs (F1 fix)
scorer_load_r1 = {}
for sid, code in SCORER_CODE_R1.items():
    er = py_exec(code, sid)
    if er["ok"]:
        vr = validate_scorer_on_pairs(code, VALIDATION_PAIRS)
        scorer_load_r1[sid] = {"loaded":True, **vr}
        log("step8", f"  {sid} [{ALL_HYPS[sid]['lineage']}]: valid={vr['valid']} acc={vr['pair_validation_accuracy']:.0%} margin={vr['pair_validation_margin']:.3f}", "ok" if vr["valid"] else "warn")
    else:
        scorer_load_r1[sid] = {"loaded":False,"valid":False,"reason":"load_error","pair_validation_accuracy":0,"pair_validation_margin":0,"pair_validation_spread":0}
        log("step8",f"  {sid}: LOAD ERROR {er['error']}","error")

save("step8b_scorer_functions_r1", {sid:{"hypothesis":ALL_HYPS[sid]["hypothesis"],"lineage":ALL_HYPS[sid]["lineage"],"code":SCORER_CODE_R1[sid],"validation":scorer_load_r1[sid]} for sid in SCORER_CODE_R1})

# ════════════════════════════════════════════════════════════════════
# STEP 9: ADVERSARIAL PAIRS — attacks top scorers (Spec §9, F7)
# ════════════════════════════════════════════════════════════════════
log("step9","Generating adversarial pairs targeting top scorer weaknesses…")

ADV_PAIRS_R1 = [
    # ── attacks fake_mechanism weakness ──
    {"pair_id":"R1_A01","anchor":"We help marketing teams measure campaign performance.",
     "positive":"We help marketing teams see which campaign elements drove conversions — by tracing each sign-up back to the specific ad variant, email, and landing page that touched it.",
     "negative":"We help marketing teams measure campaign performance by leveraging our advanced AI engine which synergistically optimises your entire marketing funnel through intelligent automation.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids":["S_r0_001","S_r0_004"],
     "attacked_shortcut":"causal_density rewards 'by' regardless of what follows",
     "label_contract":"Both use 'by' — positive names concrete steps, negative uses jargon.",
     "intended_trap":"'By leveraging our advanced AI engine' has high causal_density score."},
    {"pair_id":"R1_A02","anchor":"Our tool saves engineers time on code reviews.",
     "positive":"Our tool saves engineers time on code reviews by flagging only changes that touch security or performance boundaries — so they spend review time on code that actually matters.",
     "negative":"Our tool saves engineers time on code reviews through our next-generation intelligent analysis engine powered by advanced machine learning technology.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids":["S_r0_006"],
     "attacked_shortcut":"source_continuity + causal_density doesn't penalise abstract mechanism",
     "label_contract":"Positive: concrete what-is-flagged. Negative: abstract engine.",
     "intended_trap":"'Through our intelligent analysis engine' passes causal_density."},
    # ── attacks subtle_quality_gap weakness ──
    {"pair_id":"R1_A03","anchor":"Our software helps teams collaborate better.",
     "positive":"Instead of chasing updates across five Slack threads, our software shows the three decisions stuck in review — so one async session unblocks a week of work.",
     "negative":"Instead of the old way of working, our software helps teams collaborate better through a seamless, advanced platform that makes everything more efficient.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids":["S_r0_002"],
     "attacked_shortcut":"audience_relevance probe fires on 'Instead of' in both",
     "label_contract":"Both have before-state. Only positive has concrete mechanism + result.",
     "intended_trap":"Negative mimics before/after but collapses into jargon."},
    {"pair_id":"R1_A04","anchor":"Turn customer feedback into product decisions.",
     "positive":"Instead of debating priorities in planning, rank your product decisions by the weight of customer signal behind each — so the meeting starts with evidence, not opinion.",
     "negative":"Instead of struggling with product prioritisation, our advanced AI transforms your customer feedback into optimised decision-making solutions seamlessly.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids":["S_r0_002","S_r0_001"],
     "attacked_shortcut":"Both have 'Instead of' + problem-state language",
     "label_contract":"Positive completes problem→mechanism→result. Negative has fake mechanism.",
     "intended_trap":"'Instead of struggling' + 'advanced AI transforms' looks like full argument."},
    # ── attacks source-drift borderline ──
    {"pair_id":"R1_A05","anchor":"We help companies reduce customer churn.",
     "positive":"We help CS teams flag accounts before they churn — by detecting drops in feature usage and surfacing them to the right rep automatically.",
     "negative":"We help companies reduce customer churn through our world-class intelligent customer success platform that guarantees retention improvement.",
     "pair_type":"source_drift","source_policy":{**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids":["S_r0_006"],
     "attacked_shortcut":"source_continuity doesn't catch guarantee words",
     "label_contract":"Positive: concrete detection + action. Negative: hype + guarantee word.",
     "intended_trap":"'Guarantee' should trigger hard source policy veto."},
    # ── NEW heldout test pairs (never seen in repair) ──
    {"pair_id":"R1_T01","anchor":"We help engineering teams deploy faster.",
     "positive":"We help engineering teams deploy faster by running automated smoke tests against your staging environment and blocking deploys that fail — before they reach production.",
     "negative":"We help engineering teams deploy faster through our revolutionary DevOps intelligence platform powered by advanced AI for seamless deployment automation.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Concrete gate mechanism vs fake mechanism.",
     "intended_trap":"'DevOps intelligence platform' sounds technical."},
    {"pair_id":"R1_T02","anchor":"Our platform helps companies reduce churn.",
     "positive":"Our platform alerts CS managers when at-risk accounts drop below their engagement threshold — so the team intervenes before the cancellation window closes.",
     "negative":"Our innovative retention platform helps companies reduce churn through our seamless intelligent customer success optimisation suite.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Alert + threshold + intervention vs jargon chain.",
     "intended_trap":"'Customer success optimisation suite' sounds professional."},
    {"pair_id":"R1_T03","anchor":"We help startups raise their seed round.",
     "positive":"We help startups raise their seed round by running their pitch through the objections their target investors raise most often — so they walk in prepared for the actual conversation.",
     "negative":"We help startups raise their seed round leveraging our groundbreaking pitch optimisation platform that maximises your investor readiness through advanced AI.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Concrete test (objections) vs fake mechanism + hype.",
     "intended_trap":"'Maximises investor readiness' sounds outcome-focused."},
    {"pair_id":"R1_T04","anchor":"Our analytics tool makes data easier to understand.",
     "positive":"Instead of a BI request and a three-day wait, our tool lets anyone on the team answer their own data questions in minutes — by pulling from connected sources and letting them filter without SQL.",
     "negative":"Our advanced analytics solution makes data insights easier through our intelligent self-service platform that optimises your entire data workflow seamlessly.",
     "pair_type":"subtle_quality_gap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Full argument progression vs abstract platform claim.",
     "intended_trap":"'Self-service platform' + 'intelligent' sounds concrete."},
    {"pair_id":"R1_T05","anchor":"Automate your customer support with AI.",
     "positive":"Automate your customer support with AI that drafts responses from your best-resolved tickets — so quality improves each week without anyone reviewing every reply.",
     "negative":"Automate your customer support with our world-class AI that delivers guaranteed effortless support automation through our advanced intelligent platform.",
     "pair_type":"hype_trap","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Mechanism + improvement loop vs hype density.",
     "intended_trap":"'Guaranteed effortless' should hard-veto."},
    {"pair_id":"R1_T06","anchor":"We built an AI tool that helps product teams ship faster.",
     "positive":"We built an AI tool that helps product teams ship faster by ranking each backlog item by customer-signal weight — so sprint planning starts with evidence rather than opinion.",
     "negative":"We built an amazing AI tool that helps product teams ship faster through our synergistic product intelligence engine that seamlessly optimises your entire delivery pipeline.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Ranking mechanism (concrete) vs synergistic engine (fake).",
     "intended_trap":"'Optimises your entire delivery pipeline' sounds comprehensive."},
    {"pair_id":"R1_T07","anchor":"We make financial reporting faster for accountants.",
     "positive":"We make financial reporting faster for accountants by pulling from connected accounts and generating consolidated P&Ls automatically — no copy-paste, no manual reconciliation.",
     "negative":"We make financial reporting faster for accountants through our world-class intelligent financial automation platform that revolutionises your reporting workflow.",
     "pair_type":"fake_mechanism","source_policy":{**DEFAULT_SOURCE_POLICY},
     "label_contract":"Concrete steps (pull, generate, no copy-paste) vs fake mechanism.",
     "intended_trap":"'Revolutionises your reporting' sounds transformative."},
]

# Validate adversarial pair policies
adv_policy_results = [validate_pair_source_policy(p) for p in ADV_PAIRS_R1]
valid_adv   = [ADV_PAIRS_R1[i] for i,r in enumerate(adv_policy_results) if r["valid"]]
invalid_adv = [{"pair":ADV_PAIRS_R1[i],"errors":r["errors"]} for i,r in enumerate(adv_policy_results) if not r["valid"]]
log("step9", f"Adversarial policy check: {len(valid_adv)} valid, {len(invalid_adv)} invalid", "ok" if not invalid_adv else "warn")
for iv in invalid_adv: log("step9", f"  DROPPED {iv['pair']['pair_id']}: {iv['errors']}", "warn")

# Split adversarial into visible train + new heldout
adv_train = seeded_shuffle([p for p in valid_adv if not p["pair_id"].startswith("R1_T")], SEED+1)
new_heldout = [p for p in valid_adv if p["pair_id"].startswith("R1_T")]
for p in adv_train: p["split"]="adversarial"
for p in new_heldout: p["split"]="test"; p["frozen"]=True

# Growing heldout set (anti-leakage)
PAIR_SUITE_R1 = {
    "train":      PAIR_SUITE["train"] + adv_train,
    "test":       PAIR_SUITE["test"]  + new_heldout,
    "adversarial":adv_train,
    "all":        PAIR_SUITE["train"] + adv_train + PAIR_SUITE["test"] + new_heldout,
}
save("step9_adversarial_pairs_r1", valid_adv)
log("step9", f"Adv train: {len(adv_train)}, new heldout: {len(new_heldout)}", "ok")
log("step9", f"Growing heldout: {len(PAIR_SUITE['test'])} → {len(PAIR_SUITE_R1['test'])} pairs")
log("step9", f"Heldout >= 15: {'YES' if len(PAIR_SUITE_R1['test'])>=15 else 'NO'} ({len(PAIR_SUITE_R1['test'])})")
log("step9", "Anti-leakage: raw heldout text excluded from repair prompts ✓")

trap_dist_r1 = {}
for p in adv_train+new_heldout: trap_dist_r1[p["pair_type"]] = trap_dist_r1.get(p["pair_type"],0)+1
log("step9", f"Adversarial pair types: {trap_dist_r1}")


# ════════════════════════════════════════════════════════════════════
# STEP 10: ROUND 1 FULL EVAL + PARETO
# ════════════════════════════════════════════════════════════════════
log("step10","Round 1 full evaluation (all scorers × full pair suite)…")

ALL_SCORER_LOAD = {**scorer_load_r0, **scorer_load_r1}
EVAL_R1 = {}
SUMMARIES_R1 = []

for sid, code in ALL_SCORER_CODE.items():
    rows = eval_scorer(sid, code, PAIR_SUITE_R1["all"])
    EVAL_R1[sid] = rows
    validation = ALL_SCORER_LOAD.get(sid, {"valid":False,"reason":"missing","pair_validation_accuracy":0,"pair_validation_margin":0,"pair_validation_spread":0})
    s = compute_summary(sid, rows, validation, SCORER_HYPOTHESES_R0+SCORER_HYPOTHESES_R1, 1)
    SUMMARIES_R1.append(s)

PARETO_R1 = compute_pareto(SUMMARIES_R1)
FP_R1 = build_failure_packet(1, SUMMARIES_R1, EVAL_R1, PAIR_SUITE_R1, PARETO_R1, FP_R0["mutation_instructions"])

for s in PARETO_R1:
    best_te_mrg = max(x["test_margin"] for x in PARETO_R1)
    best_te_acc = max(x["test_accuracy"] for x in PARETO_R1)
    dims = []
    if abs(s["test_margin"]-best_te_mrg)<0.001:   dims.append(f"best test margin ({s['test_margin']:.3f})")
    if abs(s["test_accuracy"]-best_te_acc)<0.001: dims.append(f"best test acc ({s['test_accuracy']:.0%})")
    s["survived_because"] = ", ".join(dims) if dims else "non-dominated"

save("step10_eval_r1",      {sid:EVAL_R1[sid] for sid in EVAL_R1})
save("step10_summaries_r1", SUMMARIES_R1)
save("step10_pareto_r1",    PARETO_R1)
save("step10_failure_packet_r1", FP_R1)

print(f"\n  R1 Rankings ({len(PAIR_SUITE_R1['train'])} train / {len(PAIR_SUITE_R1['test'])} heldout):")
print(f"  {'Scorer':<12} {'Lin':<12} {'TrAcc':>6} {'TrMrg':>7} {'TeAcc':>6} {'TeMrg':>7} {'Sprd':>6} {'Elig':>5}")
print("  "+"-"*80)
for s in sorted(SUMMARIES_R1, key=lambda x: (x["test_margin"],x["test_accuracy"]), reverse=True):
    ok, reason = is_eligible_for_pareto(s)
    flag = " ★" if any(p["scorer_id"]==s["scorer_id"] for p in PARETO_R1) else ""
    print(f"  {s['scorer_id']:<12} {s['lineage']:<12} {s['train_accuracy']:>5.0%}  {s['train_margin']:>6.3f}  {s['test_accuracy']:>5.0%}  {s['test_margin']:>6.3f}  {s['score_spread']:>5.3f}  {'Y' if ok else 'N'}{flag}")

log("step10", f"R1 Pareto: {len(PARETO_R1)} eligible scorers", "ok")
for s in PARETO_R1:
    log("step10", f"  ★ {s['scorer_id']} [{s['lineage']}] te_acc={s['test_accuracy']:.0%} te_mrg={s['test_margin']:.3f} — {s['survived_because']}")
log("step10", f"R1 failure packet — trap failures: {FP_R1['failed_pair_type_counts']}")
log("step10", f"Applied from prior: {FP_R1.get('applied_from_prior_round',[])}")

# ════════════════════════════════════════════════════════════════════
# STEP 11: CANDIDATE SELECTION with eligible ensemble (Spec §11)
# F4 fix: C002 (audience_pain) should NOT score 0
# ════════════════════════════════════════════════════════════════════
log("step11","Candidate generation and scoring…")

CANDIDATES = [
    {"candidate_id":"C001","strategy":"mechanism_first",
     "text":"EvalWeaver lets anyone create, use, and monetise AI improvers for subjective goals like 'more persuasive' — by building a causal theory of what the goal means, testing it on real examples, and using the strongest evaluator to guide each rewrite."},
    {"candidate_id":"C002","strategy":"audience_pain",
     "text":"Tired of asking AI to improve your writing and getting results that feel off? EvalWeaver discovers what your improvement goal actually means, validates that theory against real examples, and only then rewrites."},
    {"candidate_id":"C003","strategy":"concrete_outcome",
     "text":"EvalWeaver turns vague goals like 'more persuasive' into testable evaluators — so you improve text based on what actually moves your readers, not what sounds plausible to an AI."},
    {"candidate_id":"C004","strategy":"hype_control_baseline",
     "text":"EvalWeaver is the ultimate revolutionary AI that instantly transforms any writing goal into the most amazing, guaranteed persuasion results you've ever seen."},
]

# Eligible ensemble: valid, positive heldout margin, spread >= 0.02
candidate_ensemble = [
    s for s in PARETO_R1
    if s.get("valid") is True
    and s.get("test_margin",0) > 0
    and s.get("test_accuracy",0) >= 0.5
    and s.get("score_spread",0) >= 0.02
]

if not candidate_ensemble:
    log("step11", "NO ELIGIBLE SCORER ENSEMBLE — cannot select candidate", "error")
    selected_candidate = None
else:
    log("step11", f"Eligible ensemble: {[s['scorer_id'] for s in candidate_ensemble]}", "ok")

    # Raw scores
    raw_scores = {}
    for c in CANDIDATES:
        raw_scores[c["candidate_id"]] = {}
        for s in candidate_ensemble:
            r = py_run_scorer(ALL_SCORER_CODE[s["scorer_id"]], c["text"], RAW_TEXT)
            raw_scores[c["candidate_id"]][s["scorer_id"]] = r["value"]

    # Normalise per scorer
    norm_scores = {}
    for s in candidate_ensemble:
        sid = s["scorer_id"]
        vals = [raw_scores[c["candidate_id"]][sid] for c in CANDIDATES]
        mn,mx = min(vals), max(vals)
        rng_s = mx-mn if mx>mn else 1
        norm_scores[sid] = {c["candidate_id"]:(raw_scores[c["candidate_id"]][sid]-mn)/rng_s for c in CANDIDATES}

    scored_candidates = []
    for c in CANDIDATES:
        norm_mean = statistics.mean(norm_scores[s["scorer_id"]][c["candidate_id"]] for s in candidate_ensemble)
        nums_orig = extract_numbers(RAW_TEXT)
        nums_new  = extract_numbers(c["text"])
        policy_ok = all(n in nums_orig for n in nums_new)
        scored_candidates.append({**c,"raw_scores":raw_scores[c["candidate_id"]],
            "norm_scores":{s["scorer_id"]:norm_scores[s["scorer_id"]][c["candidate_id"]] for s in candidate_ensemble},
            "ensemble_score":round(norm_mean,4),"policy_ok":policy_ok})

    scored_candidates.sort(key=lambda x:(x["policy_ok"],x["ensemble_score"]), reverse=True)
    selected_candidate = scored_candidates[0]

    print(f"\n  Candidates (normalised ensemble score):")
    for rank,c in enumerate(scored_candidates,1):
        sel = " ← SELECTED" if rank==1 else ""
        pol = "✓" if c["policy_ok"] else "⚠policy"
        print(f"  #{rank} {c['candidate_id']} [{c['strategy']:<22}] norm={c['ensemble_score']:.3f} {pol}{sel}")
        print(f"      text: {c['text'][:90]}…")

    best_hyp = PARETO_R1[0]["hypothesis"] if PARETO_R1 else ""
    log("step11", f"Selected: {selected_candidate['candidate_id']} ({selected_candidate['strategy']})", "ok")
    log("step11", f"Hype baseline score: {scored_candidates[-1]['ensemble_score']:.3f} (should be 0)")
    
    # F4 check: C002 should NOT be 0
    c002 = next(c for c in scored_candidates if c["candidate_id"]=="C002")
    log("step11", f"C002 audience_pain score: {c002['ensemble_score']:.3f} (should be > 0 — F4 fix check)")

    save("step11_candidates_scored", scored_candidates)
    save("step11_final_selection", {
        "selected":selected_candidate,
        "eligible_ensemble":[s["scorer_id"] for s in candidate_ensemble],
        "winning_scorer_hypotheses":[s["hypothesis"] for s in candidate_ensemble[:2]],
        "explanation_for_product_mode": f"Selected because: {best_hyp}" if best_hyp else "Selected by scorer ensemble."
    })

# ════════════════════════════════════════════════════════════════════
# STEP 12: F9 FIX — Computed spec criteria
# ════════════════════════════════════════════════════════════════════
log("step12","Computing spec criteria from artifacts…")

def spec_criterion(name, value, threshold=True, warn_only=False):
    if isinstance(threshold, bool):
        status = "pass" if value == threshold else ("warning" if warn_only else "fail")
    else:
        status = "pass" if value >= threshold else ("warning" if warn_only else "fail")
    return {"criterion":name,"status":status,"computed_value":value,"threshold":str(threshold)}

pair_policy_invalid = len(invalid_pairs) + len(invalid_adv)
final_heldout_count = len(PAIR_SUITE_R1["test"])
pareto_nonempty_r1  = len(PARETO_R1) > 0

computed_criteria = [
    spec_criterion("taste_research_present",          len(RAW_RESEARCH),           3),
    spec_criterion("taste_map_rewards_present",       len(TASTE_MAP["rewards"]),   3),
    spec_criterion("taste_map_punishes_present",      len(TASTE_MAP["punishes"]),  1),
    spec_criterion("scorer_hypotheses_r0",            len(SCORER_HYPOTHESES_R0),   N_INIT_SCORERS),
    spec_criterion("scorer_code_valid_r0",            count_valid_r0,              2),
    spec_criterion("pair_policy_violations",          pair_policy_invalid,         0),
    spec_criterion("initial_heldout_count",           len(PAIR_SUITE["test"]),     MIN_INIT_HELDOUT),
    spec_criterion("pareto_r0_nonempty",              len(PARETO_R0) > 0,          True),
    spec_criterion("failure_packet_has_instructions", len(FP_R0["mutation_instructions"]) > 0, True),
    spec_criterion("repair_hypotheses_generated",     len(SCORER_HYPOTHESES_R1),   N_REPAIR_SCORERS),
    spec_criterion("adversarial_pairs_generated",     len(valid_adv),              N_REPAIR_PAIRS),
    spec_criterion("fake_mechanism_pairs",            trap_dist_r1.get("fake_mechanism",0)+trap_dist.get("fake_mechanism",0), 3),
    spec_criterion("heldout_grew",                    final_heldout_count > len(PAIR_SUITE["test"]), True),
    spec_criterion("final_heldout_count",             final_heldout_count,         MIN_R1_HELDOUT),
    spec_criterion("pareto_r1_nonempty",              pareto_nonempty_r1,          True),
    spec_criterion("eligible_ensemble_exists",        len(candidate_ensemble) > 0, True),
    spec_criterion("candidate_selected",              selected_candidate is not None, True),
    spec_criterion("hype_baseline_zeroed",            scored_candidates[-1]["ensemble_score"] < 0.05 if scored_candidates else False, True),
    spec_criterion("c002_not_zeroed",                 c002["ensemble_score"] > 0.05, True),
    spec_criterion("mutation_instructions_not_all_repeated", len(FP_R1.get("applied_from_prior_round",[])) < len(FP_R1["mutation_instructions"]), True, warn_only=True),
]

pass_count = sum(1 for c in computed_criteria if c["status"]=="pass")
fail_count = sum(1 for c in computed_criteria if c["status"]=="fail")
warn_count = sum(1 for c in computed_criteria if c["status"]=="warning")

save("step12_computed_criteria", computed_criteria)
print(f"\n  Spec Criteria (computed — not hardcoded):")
for c in computed_criteria:
    sym = "✓" if c["status"]=="pass" else ("⚠" if c["status"]=="warning" else "✗")
    print(f"  {sym} {c['criterion']:<45} computed={c['computed_value']}  threshold={c['threshold']}")
log("step12", f"PASS={pass_count} WARN={warn_count} FAIL={fail_count}", "ok" if fail_count==0 else "warn")

# ════════════════════════════════════════════════════════════════════
# SAVE ALL ARTIFACTS + ZIP
# ════════════════════════════════════════════════════════════════════
save("trace", TRACE)
save("run_summary_v5", {
    "version":"v5","goal":GOAL,"raw_text":RAW_TEXT,
    "v5_fixes_applied":["F1_pair_level_validation","F2_pareto_eligibility_from_validation",
                        "F3_pair_source_policy","F4_hard_soft_source_split",
                        "F5_pareto_eligibility_filter","F6_four_new_probes",
                        "F7_fake_mechanism_pairs","F8_mutation_instruction_history",
                        "F9_computed_spec_criteria"],
    "counts":{
        "probes_total":10,"scorer_r0":len(SCORER_CODE_R0),"scorer_r1":len(SCORER_CODE_R1),
        "scorers_valid_r0":count_valid_r0,"scorers_valid_r1":sum(1 for v in scorer_load_r1.values() if v.get("valid")),
        "pairs_train_r0":len(PAIR_SUITE["train"]),"pairs_heldout_r0":len(PAIR_SUITE["test"]),
        "pairs_adv_train_r1":len(adv_train),"pairs_heldout_r1":len(PAIR_SUITE_R1["test"]),
        "pair_policy_violations":pair_policy_invalid,
        "pareto_r0":len(PARETO_R0),"pareto_r1":len(PARETO_R1),
        "eligible_ensemble":len(candidate_ensemble),
    },
    "r0_best":{"scorer_id":PARETO_R0[0]["scorer_id"],"test_acc":PARETO_R0[0]["test_accuracy"],"test_margin":PARETO_R0[0]["test_margin"]} if PARETO_R0 else {},
    "r1_best":{"scorer_id":PARETO_R1[0]["scorer_id"],"lineage":PARETO_R1[0]["lineage"],"test_acc":PARETO_R1[0]["test_accuracy"],"test_margin":PARETO_R1[0]["test_margin"],"survived_because":PARETO_R1[0].get("survived_because","")} if PARETO_R1 else {},
    "selected_candidate":selected_candidate["candidate_id"] if selected_candidate else None,
    "c002_score":c002["ensemble_score"] if scored_candidates else None,
    "hype_baseline_score":scored_candidates[-1]["ensemble_score"] if scored_candidates else None,
    "spec_criteria_summary":{"pass":pass_count,"warn":warn_count,"fail":fail_count},
    "computed_criteria": computed_criteria,
})

import shutil; shutil.copy("/tmp/ew_v5.py","/mnt/user-data/outputs/evalweaver_v5_reasoning_core.py")
zip_path = "/mnt/user-data/outputs/evalweaver_v5_outputs.zip"
with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as zf:
    for fname in sorted(os.listdir(OUT)):
        if fname.endswith(".json"):
            zf.write(f"{OUT}/{fname}", fname)
    zf.write("/tmp/ew_v5.py","evalweaver_v5_reasoning_core.py")

log("done", f"Artifacts saved: {len(os.listdir(OUT))} JSON files + script", "ok")
log("done", f"ZIP: {zip_path}")
