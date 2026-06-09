"""
Pipeline orchestration: Steps 1-12 executed sequentially.

This module replicates the end-to-end flow of the v5 script using
all the extracted modules.
"""

import hashlib
import statistics
import time
from collections import defaultdict

from evalweaver.artifacts import log, save, resolve_output_directory, build_zip_archive
from evalweaver.config import seeded_shuffle
from evalweaver.runner import py_exec, py_run_scorer, get_namespace
from evalweaver.probes import load_probes
from evalweaver.policy import DEFAULT_SOURCE_POLICY, extract_numbers
from evalweaver.scorers import validate_scorer_on_pairs, VALIDATION_PAIRS
from evalweaver.pairs import ALL_PAIRS_R0, validate_and_split_pairs, merge_adversarial_pairs
from evalweaver.evaluation import eval_scorer, compute_summary
from evalweaver.pareto import is_eligible_for_pareto, compute_pareto
from evalweaver.failure_packet import build_failure_packet
from evalweaver.repair import SCORER_HYPOTHESES_R1, SCORER_CODE_R1, ADV_PAIRS_R1, compute_repair_improvement_metrics
from evalweaver.candidates import (
    CANDIDATES, build_candidate_ensemble, score_candidates, select_candidate
)
from evalweaver.criteria import compute_all_criteria


# ─────────────────────────────────────────────────────────────────────
# SCORER HYPOTHESES R0
# ─────────────────────────────────────────────────────────────────────

SCORER_HYPOTHESES_R0 = [
    {"scorer_id": "S_r0_001", "lineage": "initial",
     "hypothesis": "Argument progression (problem->mechanism->result) is the primary driver. Real mechanism quality distinguishes genuine from fake. Hard source policy is the only veto -- no soft gate.",
     "research_basis": ["ELM central route", "Langer 1978", "Argument progression research"],
     "taste_map_basis": ["argument_progression", "causal_grounding", "fake_mechanism", "source_violation"],
     "expected_failure_mode": "May miss audience-relevance-only pairs that lack explicit mechanism.",
     "constants_and_thresholds": [{"name": "FAKE_MECH_CANCEL", "value": 0.3, "reason": "Fake mechanism above 0.3 cancels positive signals"}]},
    {"scorer_id": "S_r0_002", "lineage": "initial",
     "hypothesis": "Audience relevance amplifies causal grounding. Before/after contrast + second-person is the primary relevance signal. Soft source continuity reduces but doesn't zero the score.",
     "research_basis": ["Burnkrant & Unnava 1989", "JTBD framing", "ELM involvement"],
     "taste_map_basis": ["audience_relevance", "causal_grounding", "source_continuity"],
     "expected_failure_mode": "May reward pain-framing that has fake mechanism -- needs real_mechanism_quality gate.",
     "constants_and_thresholds": [{"name": "REL_BOOST_CAP", "value": 1.25, "reason": "Relevance amplifies mechanism up to 25%"}]},
    {"scorer_id": "S_r0_003", "lineage": "initial",
     "hypothesis": "Fake mechanism is the primary disqualifier. Abstract jargon density penalises marketing-speak. Specificity without invention is the primary positive signal.",
     "research_basis": ["Abstract jargon credibility", "Friestad & Wright 1994"],
     "taste_map_basis": ["fake_mechanism", "concrete_specificity", "epistemic_honesty", "source_violation"],
     "expected_failure_mode": "May be too strict on abstract language in domain-specific copy.",
     "constants_and_thresholds": [{"name": "JARGON_VETO", "value": 0.25, "reason": "Jargon density above 0.25 significantly reduces score"}]},
    {"scorer_id": "S_r0_004", "lineage": "initial",
     "hypothesis": "Full chain: argument progression gates concrete specificity. Specificity only counts when argument has a real mechanism. Source continuity is soft. Fake mechanism vetoes.",
     "research_basis": ["ELM full model", "Kahneman System 1", "Langer 1978"],
     "taste_map_basis": ["argument_progression", "concrete_specificity", "causal_grounding", "fake_mechanism", "source_continuity"],
     "expected_failure_mode": "Complex scorer may over-penalise good short copy that nails one dimension.",
     "constants_and_thresholds": [{"name": "PROG_GATE", "value": 0.4, "reason": "Argument progression below 0.4 reduces specificity credit"}, {"name": "FAKE_MECH_VETO", "value": 0.35, "reason": "Fake mechanism above 0.35 vetoes"}]},
    {"scorer_id": "S_r0_005", "lineage": "initial",
     "hypothesis": "Epistemic calibration amplifies the base score. Well-calibrated text (hedges present, superlatives absent, no jargon) is more persuasive. Persuasion risk cancels.",
     "research_basis": ["Boush 2009", "Friestad & Wright 1994"],
     "taste_map_basis": ["epistemic_honesty", "persuasion_knowledge_trigger", "fake_mechanism", "source_continuity"],
     "expected_failure_mode": "May under-reward legitimately confident specific claims.",
     "constants_and_thresholds": [{"name": "EP_BOOST_MAX", "value": 1.2, "reason": "Epistemic calibration boosts score up to 20%"}]},
    {"scorer_id": "S_r0_006", "lineage": "initial",
     "hypothesis": "Source continuity (soft) combined with causal density -- a text is more persuasive when it preserves the anchor's intent AND adds mechanism. Hard policy is the only veto.",
     "research_basis": ["Credibility transfer", "Langer 1978"],
     "taste_map_basis": ["source_continuity", "causal_grounding", "source_violation"],
     "expected_failure_mode": "Doesn't penalise abstract jargon -- may reward fake mechanism if it has causal words.",
     "constants_and_thresholds": [{"name": "CONTINUITY_FLOOR", "value": 0.2, "reason": "Source continuity below 0.2 still reduces but doesn't zero"}]},
    {"scorer_id": "S_r0_007", "lineage": "initial",
     "hypothesis": "Argument progression x real mechanism quality is the product score. Both must be present. Fake mechanism vetoes regardless of other signals. No soft source gate.",
     "research_basis": ["Argument structure", "ELM elaboration", "real mechanism"],
     "taste_map_basis": ["argument_progression", "causal_grounding", "fake_mechanism"],
     "expected_failure_mode": "Ignores source drift -- may reward well-structured text that invents claims.",
     "constants_and_thresholds": [{"name": "FAKE_MECH_CANCEL", "value": 0.25, "reason": "Any fake mechanism above 0.25 -> score *= 0.1"}]},
    {"scorer_id": "S_r0_008", "lineage": "initial",
     "hypothesis": "Contrast scorer: specificity_without_invention minus abstract_jargon_density minus persuasion_risk. High-quality = specific, no jargon, no hype. Source continuity weights the total.",
     "research_basis": ["Boush 2009 specificity-hype ratio", "Kahneman System 1"],
     "taste_map_basis": ["concrete_specificity", "fake_mechanism", "persuasion_knowledge_trigger", "source_continuity"],
     "expected_failure_mode": "May penalise platform-noun-heavy B2B copy that is genuinely persuasive.",
     "constants_and_thresholds": [{"name": "SPEC_WEIGHT", "value": 0.5, "reason": "Specificity is primary positive"}, {"name": "JARGON_WEIGHT", "value": 0.3, "reason": "Jargon penalises more than hype"}]},
]


# ─────────────────────────────────────────────────────────────────────
# SCORER CODE R0
# ─────────────────────────────────────────────────────────────────────

SCORER_CODE_R0 = {
"S_r0_001": """
def scorer(text, anchor, params):
    FAKE_MECH_CANCEL = 0.3
    if violates_hard_source_policy(text, anchor):
        return 0.0
    fake = probe_real_mechanism_quality(text)
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


# ─────────────────────────────────────────────────────────────────────
# TASTE DATA (Steps 1-3)
# ─────────────────────────────────────────────────────────────────────

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
Named entity ratio: proper nouns / total tokens -- higher = more concrete.
Action verb concentration: strong verbs (identify, surface, eliminate) vs nominalisations.
Abstract noun ratio: platform/solution/value inversely correlates with persuasiveness.
Argument progression: problem -> mechanism -> result is the strongest structural pattern.
""",
    "failure modes persuasive writing backfire": """
Reactance theory (Brehm 1966): explicit persuasive intent triggers psychological resistance.
Persuasion knowledge activation (Friestad & Wright 1994): manipulation detection activates scepticism.
Superlative overload: dense superlatives trigger persuasion knowledge -- backfire effect.
Fake mechanism: "leveraging our advanced AI engine" sounds causal but has no concrete content.
Source drift: rewrite that invents facts or metrics loses credibility when detected.
Abstract jargon density: "seamless, scalable, innovative" signals marketing-speak, reduces trust.
"""
}

TASTE_MAP = {
    "goal": "persuasive",
    "rewards": [
        {"concept": "causal_grounding", "description": "Text explains WHY via mechanism + causal connectives.",
         "research_basis": "Langer 1978; ELM central route", "measurable_proxy_ideas": ["causal connective density", "real_mechanism_quality probe"]},
        {"concept": "argument_progression", "description": "Problem->mechanism->result structure.",
         "research_basis": "Narrative argument structure; ELM elaboration", "measurable_proxy_ideas": ["argument_progression probe"]},
        {"concept": "concrete_specificity", "description": "Named outcomes, action verbs, domain nouns.",
         "research_basis": "Kahneman 2011 System 1", "measurable_proxy_ideas": ["specificity_without_invention probe"]},
        {"concept": "audience_relevance", "description": "Connects to a recognised problem via before/after framing.",
         "research_basis": "Burnkrant & Unnava 1989", "measurable_proxy_ideas": ["audience_relevance probe", "argument_progression probe"]},
        {"concept": "epistemic_honesty", "description": "Appropriate hedges; no superlatives; no invented claims.",
         "research_basis": "Boush 2009", "measurable_proxy_ideas": ["epistemic_calibration probe", "abstract_jargon_density probe"]},
    ],
    "punishes": [
        {"concept": "persuasion_knowledge_trigger", "description": "Dense superlatives activate scepticism.",
         "research_basis": "Friestad & Wright 1994", "measurable_proxy_ideas": ["persuasion_risk probe"]},
        {"concept": "fake_mechanism", "description": "Mechanism-sounding language with no concrete content.",
         "research_basis": "Abstract jargon study; reactance theory", "measurable_proxy_ideas": ["real_mechanism_quality probe", "abstract_jargon_density probe"]},
        {"concept": "source_violation", "description": "Invented metrics, guarantees, or fabricated evidence.",
         "research_basis": "Source drift credibility inversion", "measurable_proxy_ideas": ["violates_hard_source_policy check"]},
    ],
    "preserves": [
        {"concept": "source_continuity", "description": "Core claim and domain preserved; rephrasing allowed.",
         "research_basis": "Credibility transfer", "measurable_proxy_ideas": ["probe_source_continuity (soft, not gate)"]}
    ],
    "key_tensions": [
        "Specificity vs source drift: concrete details risk inventing claims",
        "Audience relevance vs source continuity: pain-reframes may rephrase heavily",
        "Causal depth vs fake mechanism: both use 'by' -- need real_mechanism_quality to distinguish",
    ],
    "scorer_hypothesis_seeds": [
        "Argument progression (problem->mechanism->result) with real mechanism quality is the strongest signal",
        "Fake mechanism + abstract jargon cancels any positive score regardless of other signals",
        "Source continuity is soft -- only hard policy violations (invented metrics) warrant veto",
        "Audience relevance amplifies causal grounding when both are present",
        "Epistemic calibration as amplifier (not gate): well-calibrated text scores higher",
    ]
}

NLP_THEORY = {
    "argument_progression": {"taste_concept": "argument_progression", "method": "Detect problem/mechanism/result markers in sequence", "research_ref": "Argument structure in persuasion"},
    "real_mechanism_quality": {"taste_concept": "causal_grounding+fake_mechanism", "method": "Causal marker -> concrete domain noun (reward) vs jargon (penalise)", "research_ref": "ELM elaboration likelihood"},
    "abstract_jargon_density": {"taste_concept": "fake_mechanism", "method": "JARGON_WORDS density in content tokens", "research_ref": "Marketing-speak credibility inversion"},
    "specificity_without_invention": {"taste_concept": "concrete_specificity", "method": "Named entities + action verbs, zero if hard policy violated", "research_ref": "Kahneman System 1"},
    "probe_source_continuity": {"taste_concept": "source_continuity", "method": "Soft overlap: 0.5*token + 0.25*action + 0.25*domain -- no hard gate", "research_ref": "Credibility transfer (soft)"},
    "violates_hard_source_policy": {"taste_concept": "source_violation", "method": "Invented numeric tokens or guarantee words -> hard veto", "research_ref": "Source drift inversion"},
    "probe_causal_density": {"taste_concept": "causal_grounding", "method": "Causal connective count / sentence count", "research_ref": "Langer 1978"},
    "probe_audience_relevance": {"taste_concept": "audience_relevance", "method": "Before-state markers + second-person density", "research_ref": "Burnkrant & Unnava 1989"},
    "probe_persuasion_risk": {"taste_concept": "persuasion_knowledge_trigger", "method": "HYPE_WORDS density", "research_ref": "Friestad & Wright 1994"},
    "probe_epistemic_calibration": {"taste_concept": "epistemic_honesty", "method": "Hedge density vs superlative density", "research_ref": "Boush 2009"},
}


# ─────────────────────────────────────────────────────────────────────
# PIPELINE RUNNER
# ─────────────────────────────────────────────────────────────────────

def run_pipeline(config):
    """
    Run the full EvalWeaver pipeline (Steps 1-12).
    Returns a result dict with success status and output directory.
    """
    goal = config.get("goal", "persuasive")
    raw_text = config.get("raw_text", TASTE_MAP["goal"])
    seed = config.get("seed", 7)
    n_init_scorers = config.get("n_init_scorers", 8)
    n_repair_scorers = config.get("n_repair_scorers", 6)
    min_init_heldout = config.get("min_init_heldout", 8)
    min_r1_heldout = config.get("min_r1_heldout", 15)

    out_dir = resolve_output_directory()

    # Boot: load probes into namespace
    py_ns = get_namespace()
    load_probes(py_ns)
    log("boot", "All helper probes loaded (v5 full set)", "ok")

    print("=" * 65)
    print("EVALWEAVER v5 -- HARDENED REASONING CORE")
    print("=" * 65)

    # ════════════════════════════════════════════════════════════════
    # STEP 1: TASTE RESEARCH
    # ════════════════════════════════════════════════════════════════
    generate_step = config.get("generate_step", None)
    provider_generation_enabled = config.get("provider_generation_enabled", False)
    bedrock_call_meta = None

    if provider_generation_enabled and generate_step == "research":
        log("step1", "Taste research (LIVE Bedrock generation)")
        from evalweaver.providers.bedrock_claude_provider import BedrockClaudeProvider
        provider = BedrockClaudeProvider(
            model_id=config.get("model_id", "us.anthropic.claude-sonnet-4-6"),
            aws_region=config.get("aws_region", "us-east-1"),
        )
        try:
            research_result = provider.generate_research(goal, raw_text)
            bedrock_call_meta = provider.last_call_meta
        except Exception as e:
            bedrock_call_meta = getattr(provider, '_last_call_meta', None) or {
                "latency_ms": 0, "retry_mode": "standard", "max_attempts": 5, "error": str(e),
            }
            log("step1", f"Bedrock generation failed: {e}", "error")
            raise RuntimeError(f"Bedrock generation failed for step 'research': {e}") from e
        save("step1_raw_research", research_result, out_dir)
        save("step1_raw_research_live", research_result, out_dir)
        combined_research = "\n\n---\n\n".join(str(v) for v in research_result.values())
        log("step1", f"LIVE research from Bedrock: {len(combined_research)} chars", "ok")
    else:
        log("step1", "Taste research (mocked realistic web search output)")
        save("step1_raw_research", RAW_RESEARCH, out_dir)
        combined_research = "\n\n---\n\n".join(RAW_RESEARCH.values())
        log("step1", f"Research: {len(combined_research)} chars", "ok")

    # ════════════════════════════════════════════════════════════════
    # STEP 2: TASTE MAP
    # ════════════════════════════════════════════════════════════════
    log("step2", "Building taste map")
    save("step2_taste_map", TASTE_MAP, out_dir)
    log("step2", f"Taste map: {len(TASTE_MAP['rewards'])} rewards, {len(TASTE_MAP['punishes'])} punishes", "ok")

    # ════════════════════════════════════════════════════════════════
    # STEP 3: NLP THEORY
    # ════════════════════════════════════════════════════════════════
    log("step3", "NLP theory -> probe implementation mapping")
    save("step3_nlp_theory", NLP_THEORY, out_dir)
    log("step3", f"NLP theory: {len(NLP_THEORY)} probes mapped", "ok")

    # ════════════════════════════════════════════════════════════════
    # STEP 4: SCORER HYPOTHESES + CODE
    # ════════════════════════════════════════════════════════════════
    log("step4", "Generating scorer hypotheses (Step A)...")
    save("step4a_scorer_hypotheses_r0", SCORER_HYPOTHESES_R0, out_dir)
    log("step4", f"Step A: {len(SCORER_HYPOTHESES_R0)} scorer hypotheses", "ok")

    log("step4", "Step B: Writing scorer functions...")
    scorer_load_r0 = {}
    for sid, code in SCORER_CODE_R0.items():
        er = py_exec(code, sid)
        if er["ok"]:
            vr = validate_scorer_on_pairs(code, VALIDATION_PAIRS)
            scorer_load_r0[sid] = {"loaded": True, **vr}
            log("step4", f"  {sid}: valid={vr['valid']} acc={vr['pair_validation_accuracy']:.0%} margin={vr['pair_validation_margin']:.3f} spread={vr['pair_validation_spread']:.3f}",
                "ok" if vr["valid"] else "warn")
        else:
            scorer_load_r0[sid] = {"loaded": False, "valid": False, "reason": "load_error",
                                   "pair_validation_accuracy": 0, "pair_validation_margin": 0, "pair_validation_spread": 0}
            log("step4", f"  {sid}: LOAD ERROR {er['error']}", "error")

    count_valid_r0 = sum(1 for v in scorer_load_r0.values() if v.get("valid"))
    log("step4", f"Valid scorers R0: {count_valid_r0}/{len(SCORER_CODE_R0)}", "ok")
    save("step4b_scorer_functions_r0", {
        sid: {"hypothesis": next(h["hypothesis"] for h in SCORER_HYPOTHESES_R0 if h["scorer_id"] == sid),
              "code": SCORER_CODE_R0[sid], "validation": scorer_load_r0[sid]}
        for sid in SCORER_CODE_R0
    }, out_dir)

    # ════════════════════════════════════════════════════════════════
    # STEP 5: PAIR GENERATION with source policy (F3 fix)
    # ════════════════════════════════════════════════════════════════
    log("step5", "Generating pair suite with source policy validation...")
    pair_suite_r0, valid_pairs_r0, invalid_pairs_r0, _ = validate_and_split_pairs(ALL_PAIRS_R0, seed)

    log("step5", f"Policy check: {len(valid_pairs_r0)} valid, {len(invalid_pairs_r0)} invalid (dropped)",
        "ok" if len(invalid_pairs_r0) == 0 else "warn")
    for iv in invalid_pairs_r0:
        log("step5", f"  DROPPED {iv['pair']['pair_id']}: {iv['errors']}", "warn")

    save("step5_pairs_r0", valid_pairs_r0, out_dir)
    log("step5", f"Suite: {len(pair_suite_r0['train'])} train, {len(pair_suite_r0['test'])} heldout (frozen)", "ok")
    log("step5", f"Heldout >= {min_init_heldout}: {'YES' if len(pair_suite_r0['test']) >= min_init_heldout else 'NO'} ({len(pair_suite_r0['test'])})")

    trap_dist = {}
    for p in valid_pairs_r0:
        trap_dist[p["pair_type"]] = trap_dist.get(p["pair_type"], 0) + 1
    log("step5", f"Pair types: {trap_dist}")

    # ════════════════════════════════════════════════════════════════
    # STEP 6: EVAL + PARETO (F5 fix)
    # ════════════════════════════════════════════════════════════════
    log("step6", "Evaluating scorers (R0)...")
    eval_r0 = {}
    summaries_r0 = []
    for sid, code in SCORER_CODE_R0.items():
        rows = eval_scorer(sid, code, pair_suite_r0["all"])
        eval_r0[sid] = rows
        s = compute_summary(sid, rows, scorer_load_r0[sid], SCORER_HYPOTHESES_R0, 0)
        summaries_r0.append(s)

    pareto_r0 = compute_pareto(summaries_r0)

    # Add survived_because
    for s in pareto_r0:
        dims = []
        best_te_mrg = max(x["test_margin"] for x in pareto_r0) if pareto_r0 else 0
        best_te_acc = max(x["test_accuracy"] for x in pareto_r0) if pareto_r0 else 0
        if abs(s["test_margin"] - best_te_mrg) < 0.001:
            dims.append(f"best test margin ({s['test_margin']:.3f})")
        if abs(s["test_accuracy"] - best_te_acc) < 0.001:
            dims.append(f"best test acc ({s['test_accuracy']:.0%})")
        s["survived_because"] = ", ".join(dims) if dims else "non-dominated"

    save("step6_eval_r0", {sid: eval_r0[sid] for sid in eval_r0}, out_dir)
    save("step6_summaries_r0", summaries_r0, out_dir)
    save("step6_pareto_r0", pareto_r0, out_dir)
    log("step6", f"R0 Pareto: {len(pareto_r0)} eligible scorers", "ok")
    for s in pareto_r0:
        log("step6", f"  * {s['scorer_id']} -- {s['survived_because']}")

    # ════════════════════════════════════════════════════════════════
    # STEP 7: FAILURE PACKET (F8 fix)
    # ════════════════════════════════════════════════════════════════
    log("step7", "Building failure packet R0...")
    fp_r0 = build_failure_packet(0, summaries_r0, eval_r0, pair_suite_r0, pareto_r0, SCORER_CODE_R0)
    save("step7_failure_packet_r0", fp_r0, out_dir)
    log("step7", f"Failed visible pairs: {len(fp_r0['failed_visible_pairs'])}", "ok")
    log("step7", f"Trap failures: {fp_r0['failed_pair_type_counts']}")
    log("step7", f"Mutation instructions: {len(fp_r0['mutation_instructions'])}")

    # ════════════════════════════════════════════════════════════════
    # STEP 8: REPAIR -- scorer mutation (hypothesis-first)
    # ════════════════════════════════════════════════════════════════
    log("step8", "Repair: scorer hypothesis generation R1...")
    save("step8a_scorer_hypotheses_r1", SCORER_HYPOTHESES_R1, out_dir)
    log("step8", f"Step A: {len(SCORER_HYPOTHESES_R1)} evolved hypotheses", "ok")

    all_scorer_code = {**SCORER_CODE_R0, **SCORER_CODE_R1}
    all_hyps = {h["scorer_id"]: h for h in SCORER_HYPOTHESES_R0 + SCORER_HYPOTHESES_R1}

    scorer_load_r1 = {}
    for sid, code in SCORER_CODE_R1.items():
        er = py_exec(code, sid)
        if er["ok"]:
            vr = validate_scorer_on_pairs(code, VALIDATION_PAIRS)
            scorer_load_r1[sid] = {"loaded": True, **vr}
            log("step8", f"  {sid} [{all_hyps[sid]['lineage']}]: valid={vr['valid']} acc={vr['pair_validation_accuracy']:.0%} margin={vr['pair_validation_margin']:.3f}",
                "ok" if vr["valid"] else "warn")
        else:
            scorer_load_r1[sid] = {"loaded": False, "valid": False, "reason": "load_error",
                                   "pair_validation_accuracy": 0, "pair_validation_margin": 0, "pair_validation_spread": 0}
            log("step8", f"  {sid}: LOAD ERROR {er['error']}", "error")

    save("step8b_scorer_functions_r1", {
        sid: {"hypothesis": all_hyps[sid]["hypothesis"], "lineage": all_hyps[sid]["lineage"],
              "code": SCORER_CODE_R1[sid], "validation": scorer_load_r1[sid]}
        for sid in SCORER_CODE_R1
    }, out_dir)

    # ════════════════════════════════════════════════════════════════
    # STEP 9: ADVERSARIAL PAIRS
    # ════════════════════════════════════════════════════════════════
    log("step9", "Generating adversarial pairs targeting top scorer weaknesses...")
    pair_suite_r1, adv_train, new_heldout, valid_adv, invalid_adv = merge_adversarial_pairs(
        pair_suite_r0, ADV_PAIRS_R1, seed + 1
    )

    log("step9", f"Adversarial policy check: {len(valid_adv)} valid, {len(invalid_adv)} invalid",
        "ok" if not invalid_adv else "warn")
    for iv in invalid_adv:
        log("step9", f"  DROPPED {iv['pair']['pair_id']}: {iv['errors']}", "warn")

    save("step9_adversarial_pairs_r1", valid_adv, out_dir)
    log("step9", f"Adv train: {len(adv_train)}, new heldout: {len(new_heldout)}", "ok")
    log("step9", f"Growing heldout: {len(pair_suite_r0['test'])} -> {len(pair_suite_r1['test'])} pairs")
    log("step9", f"Heldout >= {min_r1_heldout}: {'YES' if len(pair_suite_r1['test']) >= min_r1_heldout else 'NO'} ({len(pair_suite_r1['test'])})")

    trap_dist_r1 = {}
    for p in adv_train + new_heldout:
        trap_dist_r1[p["pair_type"]] = trap_dist_r1.get(p["pair_type"], 0) + 1
    log("step9", f"Adversarial pair types: {trap_dist_r1}")

    # ════════════════════════════════════════════════════════════════
    # STEP 10: ROUND 1 FULL EVAL + PARETO
    # ════════════════════════════════════════════════════════════════
    log("step10", "Round 1 full evaluation (all scorers x full pair suite)...")
    all_scorer_load = {**scorer_load_r0, **scorer_load_r1}
    eval_r1 = {}
    summaries_r1 = []

    for sid, code in all_scorer_code.items():
        rows = eval_scorer(sid, code, pair_suite_r1["all"])
        eval_r1[sid] = rows
        validation = all_scorer_load.get(sid, {"valid": False, "reason": "missing",
                                               "pair_validation_accuracy": 0, "pair_validation_margin": 0,
                                               "pair_validation_spread": 0})
        s = compute_summary(sid, rows, validation, SCORER_HYPOTHESES_R0 + SCORER_HYPOTHESES_R1, 1)
        summaries_r1.append(s)

    pareto_r1 = compute_pareto(summaries_r1)
    fp_r1 = build_failure_packet(1, summaries_r1, eval_r1, pair_suite_r1, pareto_r1,
                                 all_scorer_code, fp_r0["mutation_instructions"])

    for s in pareto_r1:
        best_te_mrg = max(x["test_margin"] for x in pareto_r1) if pareto_r1 else 0
        best_te_acc = max(x["test_accuracy"] for x in pareto_r1) if pareto_r1 else 0
        dims = []
        if abs(s["test_margin"] - best_te_mrg) < 0.001:
            dims.append(f"best test margin ({s['test_margin']:.3f})")
        if abs(s["test_accuracy"] - best_te_acc) < 0.001:
            dims.append(f"best test acc ({s['test_accuracy']:.0%})")
        s["survived_because"] = ", ".join(dims) if dims else "non-dominated"

    save("step10_eval_r1", {sid: eval_r1[sid] for sid in eval_r1}, out_dir)
    save("step10_summaries_r1", summaries_r1, out_dir)
    save("step10_pareto_r1", pareto_r1, out_dir)
    save("step10_failure_packet_r1", fp_r1, out_dir)
    log("step10", f"R1 Pareto: {len(pareto_r1)} eligible scorers", "ok")
    for s in pareto_r1:
        log("step10", f"  * {s['scorer_id']} [{s['lineage']}] te_acc={s['test_accuracy']:.0%} te_mrg={s['test_margin']:.3f} -- {s['survived_because']}")

    # Repair improvement metrics
    repair_metrics = compute_repair_improvement_metrics(
        summaries_r0, summaries_r1, pareto_r0, pareto_r1,
        eval_r0, eval_r1, pair_suite_r1,
    )
    save("step10_repair_improvement_metrics", repair_metrics, out_dir)
    log("step10", f"Repair claim supported: {repair_metrics['overall_improvement_claim_supported']}")
    log("step10", f"Repair summary: {repair_metrics['honest_repair_summary']}")

    # ════════════════════════════════════════════════════════════════
    # STEP 11: CANDIDATE SELECTION
    # ════════════════════════════════════════════════════════════════
    log("step11", "Candidate generation and scoring...")
    candidate_ensemble = build_candidate_ensemble(pareto_r1)

    if not candidate_ensemble:
        log("step11", "NO ELIGIBLE SCORER ENSEMBLE -- cannot select candidate", "error")
        selected_candidate = None
        scored_candidates = []
        c002 = {"ensemble_score": 0}
    else:
        log("step11", f"Eligible ensemble: {[s['scorer_id'] for s in candidate_ensemble]}", "ok")
        scored_candidates = score_candidates(CANDIDATES, candidate_ensemble, all_scorer_code, raw_text)
        selected_candidate = select_candidate(scored_candidates)

        log("step11", f"Selected: {selected_candidate['candidate_id']} ({selected_candidate['strategy']})", "ok")
        log("step11", f"Hype baseline score: {scored_candidates[-1]['ensemble_score']:.3f} (should be 0)")
        c002 = next((c for c in scored_candidates if c["candidate_id"] == "C002"), {"ensemble_score": 0})
        log("step11", f"C002 audience_pain score: {c002['ensemble_score']:.3f} (should be > 0 -- F4 fix check)")

        save("step11_candidates_scored", scored_candidates, out_dir)
        save("step11_final_selection", {
            "selected": selected_candidate,
            "eligible_ensemble": [s["scorer_id"] for s in candidate_ensemble],
            "winning_scorer_hypotheses": [s["hypothesis"] for s in candidate_ensemble[:2]],
            "explanation_for_product_mode": f"Selected because: {pareto_r1[0]['hypothesis']}" if pareto_r1 else "Selected by scorer ensemble."
        }, out_dir)

    # ════════════════════════════════════════════════════════════════
    # STEP 12: COMPUTED SPEC CRITERIA (F9 fix)
    # ════════════════════════════════════════════════════════════════
    log("step12", "Computing spec criteria from artifacts...")
    criteria_context = {
        "raw_research": RAW_RESEARCH,
        "taste_map": TASTE_MAP,
        "scorer_hypotheses_r0": SCORER_HYPOTHESES_R0,
        "count_valid_r0": count_valid_r0,
        "invalid_pairs_r0": invalid_pairs_r0,
        "invalid_pairs_r1": invalid_adv,
        "pair_suite_r0": pair_suite_r0,
        "pareto_r0": pareto_r0,
        "failure_packet_r0": fp_r0,
        "scorer_hypotheses_r1": SCORER_HYPOTHESES_R1,
        "valid_adv": valid_adv,
        "trap_dist": trap_dist,
        "trap_dist_r1": trap_dist_r1,
        "pair_suite_r1": pair_suite_r1,
        "pareto_r1": pareto_r1,
        "candidate_ensemble": candidate_ensemble,
        "selected_candidate": selected_candidate,
        "scored_candidates": scored_candidates,
        "c002": c002,
        "failure_packet_r1": fp_r1,
        "config": config,
    }
    computed_criteria = compute_all_criteria(criteria_context)

    pass_count = sum(1 for c in computed_criteria if c["status"] == "pass")
    fail_count = sum(1 for c in computed_criteria if c["status"] == "fail")
    warn_count = sum(1 for c in computed_criteria if c["status"] == "warning")

    save("step12_computed_criteria", computed_criteria, out_dir)
    print(f"\n  Spec Criteria (computed -- not hardcoded):")
    for c in computed_criteria:
        sym = "\u2713" if c["status"] == "pass" else ("\u26a0" if c["status"] == "warning" else "\u2717")
        print(f"  {sym} {c['criterion']:<45} computed={c['computed_value']}  threshold={c['threshold']}")
    log("step12", f"PASS={pass_count} WARN={warn_count} FAIL={fail_count}", "ok" if fail_count == 0 else "warn")

    # ════════════════════════════════════════════════════════════════
    # SAVE ALL ARTIFACTS + ZIP
    # ════════════════════════════════════════════════════════════════
    from evalweaver.artifacts import TRACE
    save("trace", TRACE, out_dir)

    # Run metadata — honest about what the provider actually did
    provider_generation_enabled = config.get("provider_generation_enabled", False)
    generate_step = config.get("generate_step", None)
    generated_steps = [generate_step] if (provider_generation_enabled and generate_step) else []
    bedrock_calls_made = len(generated_steps)  # Will increase when live gen is wired

    # run_id: <goal>-<timestamp>-<short_hash>
    ts = time.strftime("%Y%m%d-%H%M%S")
    short_hash = hashlib.sha256(f"{goal}{ts}{seed}".encode()).hexdigest()[:8]
    run_id = f"{goal}-{ts}-{short_hash}"

    run_metadata = {
        "run_id": run_id,
        "provider_name": config.get("provider_name", "mock"),
        "model_id": config.get("model_id", "mock-v1-seeded"),
        "aws_region": config.get("aws_region", None),
        "execution_backend": config.get("execution_backend", "local-exec"),
        "artifact_store": config.get("artifact_store", "local"),
        "provider_generation_enabled": provider_generation_enabled,
        "bedrock_validation_passed": config.get("bedrock_validation_passed", None),
        "bedrock_calls_made": bedrock_calls_made,
        "generated_steps": generated_steps,
        "bedrock_call_meta": {
            "latency_ms": bedrock_call_meta.get("latency_ms", 0),
            "retry_mode": "standard",
            "max_attempts": 5,
            "error": bedrock_call_meta.get("error", None),
        } if bedrock_calls_made > 0 and bedrock_call_meta else None,
    }

    save("run_summary_v5", {
        "version": "v5.1", "goal": goal, "raw_text": raw_text,
        "run_metadata": run_metadata,
        "v5_fixes_applied": ["F1_pair_level_validation", "F2_pareto_eligibility_from_validation",
                             "F3_pair_source_policy", "F4_hard_soft_source_split",
                             "F5_pareto_eligibility_filter", "F6_four_new_probes",
                             "F7_fake_mechanism_pairs", "F8_mutation_instruction_history",
                             "F9_computed_spec_criteria"],
        "counts": {
            "probes_total": 10, "scorer_r0": len(SCORER_CODE_R0), "scorer_r1": len(SCORER_CODE_R1),
            "scorers_valid_r0": count_valid_r0,
            "scorers_valid_r1": sum(1 for v in scorer_load_r1.values() if v.get("valid")),
            "pairs_train_r0": len(pair_suite_r0["train"]), "pairs_heldout_r0": len(pair_suite_r0["test"]),
            "pairs_adv_train_r1": len(adv_train), "pairs_heldout_r1": len(pair_suite_r1["test"]),
            "pair_policy_violations": len(invalid_pairs_r0) + len(invalid_adv),
            "pareto_r0": len(pareto_r0), "pareto_r1": len(pareto_r1),
            "eligible_ensemble": len(candidate_ensemble),
        },
        "r0_best": {"scorer_id": pareto_r0[0]["scorer_id"], "test_acc": pareto_r0[0]["test_accuracy"],
                    "test_margin": pareto_r0[0]["test_margin"]} if pareto_r0 else {},
        "r1_best": {"scorer_id": pareto_r1[0]["scorer_id"], "lineage": pareto_r1[0]["lineage"],
                    "test_acc": pareto_r1[0]["test_accuracy"], "test_margin": pareto_r1[0]["test_margin"],
                    "survived_because": pareto_r1[0].get("survived_because", "")} if pareto_r1 else {},
        "selected_candidate": selected_candidate["candidate_id"] if selected_candidate else None,
        "c002_score": c002["ensemble_score"] if scored_candidates else None,
        "hype_baseline_score": scored_candidates[-1]["ensemble_score"] if scored_candidates else None,
        "spec_criteria_summary": {"pass": pass_count, "warn": warn_count, "fail": fail_count},
        "computed_criteria": computed_criteria,
    }, out_dir)

    zip_path = build_zip_archive(out_dir)

    # S3 upload if configured
    s3_meta = None
    if config.get("artifact_store") == "s3":
        bucket = config.get("s3_bucket")
        if not bucket:
            log("artifacts", "ERROR: --artifact-store s3 requires --s3-bucket or TASTE_COMPILER_ARTIFACT_BUCKET env", "error")
        else:
            from evalweaver.artifacts import upload_to_s3
            s3_meta = upload_to_s3(out_dir, bucket, run_id, config.get("aws_region"))
            log("artifacts", f"Uploaded to s3://{bucket}/runs/{run_id}/ ({s3_meta['uploaded_count']} files)", "ok")

    # Update run_metadata with S3 info
    run_metadata["artifact_store"] = config.get("artifact_store", "local")
    run_metadata["s3_bucket"] = config.get("s3_bucket") if config.get("artifact_store") == "s3" else None
    run_metadata["s3_prefix"] = f"runs/{run_id}" if s3_meta else None
    run_metadata["zip_s3_key"] = s3_meta["zip_s3_key"] if s3_meta else None

    log("done", f"Artifacts saved to {out_dir}", "ok")

    return {
        "success": True,
        "output_dir": out_dir,
        "zip_path": zip_path,
        "pareto_r1": pareto_r1,
        "selected_candidate": selected_candidate,
        "scored_candidates": scored_candidates,
        "computed_criteria": computed_criteria,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "warn_count": warn_count,
    }
