"""Scorer mutation/repair: Round 1 hypotheses, code, and adversarial pairs."""

from evalweaver.policy import DEFAULT_SOURCE_POLICY


# ─────────────────────────────────────────────────────────────────────
# ROUND 1 SCORER HYPOTHESES
# ─────────────────────────────────────────────────────────────────────

SCORER_HYPOTHESES_R1 = [
    {"scorer_id": "S_r1_001", "lineage": "mutation",
     "hypothesis": "Mutation of S_r0_001: adds explicit fake-mechanism detection. Argument progression x real_mechanism_quality product \u2014 if real mechanism is negative (fake), score collapses. Addresses fake_mechanism trap failures.",
     "research_basis": ["ELM elaboration quality", "Fake mechanism credibility inversion"],
     "taste_map_basis": ["argument_progression", "causal_grounding", "fake_mechanism"],
     "expected_failure_mode": "May over-penalise short copy with brief mechanism phrases.",
     "constants_and_thresholds": [{"name": "FAKE_VETO", "value": 0.25, "reason": "Jargon density above 0.25 reduces score by 80%"}]},
    {"scorer_id": "S_r1_002", "lineage": "mutation",
     "hypothesis": "Mutation of S_r0_002: adds real_mechanism_quality gate on audience relevance amplification. Relevance only amplifies if mechanism is genuine. Addresses subtle_quality_gap where both have before/after but differ in mechanism quality.",
     "research_basis": ["Burnkrant & Unnava 1989", "ELM involvement + argument quality"],
     "taste_map_basis": ["audience_relevance", "causal_grounding", "fake_mechanism", "source_continuity"],
     "expected_failure_mode": "May penalise good audience-relevance copy that lacks explicit mechanism.",
     "constants_and_thresholds": [{"name": "REL_BOOST_CAP", "value": 1.3, "reason": "Slightly higher cap \u2014 relevance is underweighted currently"}]},
    {"scorer_id": "S_r1_003", "lineage": "blind_node_repair",
     "hypothesis": "Targets subtle_quality_gap blind spot: argument_progression x specificity_without_invention. Both must be above threshold. Abstract jargon density vetoes. Source continuity is soft floor only.",
     "research_basis": ["Argument structure", "Kahneman specificity", "Abstract jargon penalty"],
     "taste_map_basis": ["argument_progression", "concrete_specificity", "fake_mechanism", "source_continuity"],
     "expected_failure_mode": "May miss good hype-free copy that is specific but lacks explicit before/after.",
     "constants_and_thresholds": [{"name": "PROG_THRESHOLD", "value": 0.4, "reason": "Both progression and specificity must clear 0.4 to get full score"}]},
    {"scorer_id": "S_r1_004", "lineage": "recombination",
     "hypothesis": "Recombination of S_r0_001 and S_r0_003: argument_progression x real_mechanism_quality (from S_r0_001) gated by jargon check (from S_r0_003). Hard policy only veto. Soft continuity weights the total.",
     "research_basis": ["ELM central route", "Abstract jargon credibility", "Friestad & Wright"],
     "taste_map_basis": ["argument_progression", "fake_mechanism", "concrete_specificity", "source_continuity"],
     "expected_failure_mode": "Jargon gate may be too strict for domain-specific technical copy.",
     "constants_and_thresholds": [{"name": "JARGON_THRESHOLD", "value": 0.2, "reason": "Stricter than S_r0_003 \u2014 fake_mechanism failures require tighter jargon gate"}]},
    {"scorer_id": "S_r1_005", "lineage": "novel_composition",
     "hypothesis": "Novel: full argument quality score = progression + real mechanism quality + specificity_without_invention \u2014 abstract_jargon. Epistemic calibration multiplies the total. Hard policy is the only gate.",
     "research_basis": ["Full ELM model", "Boush 2009 calibration", "All taste map rewards"],
     "taste_map_basis": ["argument_progression", "causal_grounding", "concrete_specificity", "epistemic_honesty", "fake_mechanism"],
     "expected_failure_mode": "Complex \u2014 may be dominated by simpler scorers that do one thing well.",
     "constants_and_thresholds": [{"name": "EP_BOOST", "value": 1.15, "reason": "Calibration amplifies argument quality up to 15%"}]},
    {"scorer_id": "S_r1_006", "lineage": "novel_composition",
     "hypothesis": "Novel: treats source continuity as the primary signal, amplified by argument quality. A text that preserves the intent AND adds a real mechanism is maximally persuasive. No soft gate zeros.",
     "research_basis": ["Credibility transfer", "Langer 1978", "ELM"],
     "taste_map_basis": ["source_continuity", "causal_grounding", "argument_progression", "source_violation"],
     "expected_failure_mode": "May reward source-preserving text that adds only shallow mechanism.",
     "constants_and_thresholds": [{"name": "CONTINUITY_WEIGHT", "value": 0.4, "reason": "Continuity x quality \u2014 neither alone is enough"}]},
]


# ─────────────────────────────────────────────────────────────────────
# ROUND 1 SCORER CODE
# ─────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────
# ADVERSARIAL PAIRS (Round 1) -- attacks top scorer weaknesses
# ─────────────────────────────────────────────────────────────────────

ADV_PAIRS_R1 = [
    # -- attacks fake_mechanism weakness --
    {"pair_id": "R1_A01", "anchor": "We help marketing teams measure campaign performance.",
     "positive": "We help marketing teams see which campaign elements drove conversions \u2014 by tracing each sign-up back to the specific ad variant, email, and landing page that touched it.",
     "negative": "We help marketing teams measure campaign performance by leveraging our advanced AI engine which synergistically optimises your entire marketing funnel through intelligent automation.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids": ["S_r0_001", "S_r0_004"],
     "attacked_shortcut": "causal_density rewards 'by' regardless of what follows",
     "label_contract": "Both use 'by' \u2014 positive names concrete steps, negative uses jargon.",
     "intended_trap": "'By leveraging our advanced AI engine' has high causal_density score."},
    {"pair_id": "R1_A02", "anchor": "Our tool saves engineers time on code reviews.",
     "positive": "Our tool saves engineers time on code reviews by flagging only changes that touch security or performance boundaries \u2014 so they spend review time on code that actually matters.",
     "negative": "Our tool saves engineers time on code reviews through our next-generation intelligent analysis engine powered by advanced machine learning technology.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids": ["S_r0_006"],
     "attacked_shortcut": "source_continuity + causal_density doesn't penalise abstract mechanism",
     "label_contract": "Positive: concrete what-is-flagged. Negative: abstract engine.",
     "intended_trap": "'Through our intelligent analysis engine' passes causal_density."},
    # -- attacks subtle_quality_gap weakness --
    {"pair_id": "R1_A03", "anchor": "Our software helps teams collaborate better.",
     "positive": "Instead of chasing updates across five Slack threads, our software shows the three decisions stuck in review \u2014 so one async session unblocks a week of work.",
     "negative": "Instead of the old way of working, our software helps teams collaborate better through a seamless, advanced platform that makes everything more efficient.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids": ["S_r0_002"],
     "attacked_shortcut": "audience_relevance probe fires on 'Instead of' in both",
     "label_contract": "Both have before-state. Only positive has concrete mechanism + result.",
     "intended_trap": "Negative mimics before/after but collapses into jargon."},
    {"pair_id": "R1_A04", "anchor": "Turn customer feedback into product decisions.",
     "positive": "Instead of debating priorities in planning, rank your product decisions by the weight of customer signal behind each \u2014 so the meeting starts with evidence, not opinion.",
     "negative": "Instead of struggling with product prioritisation, our advanced AI transforms your customer feedback into optimised decision-making solutions seamlessly.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids": ["S_r0_002", "S_r0_001"],
     "attacked_shortcut": "Both have 'Instead of' + problem-state language",
     "label_contract": "Positive completes problem\u2192mechanism\u2192result. Negative has fake mechanism.",
     "intended_trap": "'Instead of struggling' + 'advanced AI transforms' looks like full argument."},
    # -- attacks source-drift borderline --
    {"pair_id": "R1_A05", "anchor": "We help companies reduce customer churn.",
     "positive": "We help CS teams flag accounts before they churn \u2014 by detecting drops in feature usage and surfacing them to the right rep automatically.",
     "negative": "We help companies reduce customer churn through our world-class intelligent customer success platform that guarantees retention improvement.",
     "pair_type": "source_drift", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "attacks_scorer_ids": ["S_r0_006"],
     "attacked_shortcut": "source_continuity doesn't catch guarantee words",
     "label_contract": "Positive: concrete detection + action. Negative: hype + guarantee word.",
     "intended_trap": "'Guarantee' should trigger hard source policy veto."},
    # -- NEW heldout test pairs (never seen in repair) --
    {"pair_id": "R1_T01", "anchor": "We help engineering teams deploy faster.",
     "positive": "We help engineering teams deploy faster by running automated smoke tests against your staging environment and blocking deploys that fail \u2014 before they reach production.",
     "negative": "We help engineering teams deploy faster through our revolutionary DevOps intelligence platform powered by advanced AI for seamless deployment automation.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Concrete gate mechanism vs fake mechanism.",
     "intended_trap": "'DevOps intelligence platform' sounds technical."},
    {"pair_id": "R1_T02", "anchor": "Our platform helps companies reduce churn.",
     "positive": "Our platform alerts CS managers when at-risk accounts drop below their engagement threshold \u2014 so the team intervenes before the cancellation window closes.",
     "negative": "Our innovative retention platform helps companies reduce churn through our seamless intelligent customer success optimisation suite.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Alert + threshold + intervention vs jargon chain.",
     "intended_trap": "'Customer success optimisation suite' sounds professional."},
    {"pair_id": "R1_T03", "anchor": "We help startups raise their seed round.",
     "positive": "We help startups raise their seed round by running their pitch through the objections their target investors raise most often \u2014 so they walk in prepared for the actual conversation.",
     "negative": "We help startups raise their seed round leveraging our groundbreaking pitch optimisation platform that maximises your investor readiness through advanced AI.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Concrete test (objections) vs fake mechanism + hype.",
     "intended_trap": "'Maximises investor readiness' sounds outcome-focused."},
    {"pair_id": "R1_T04", "anchor": "Our analytics tool makes data easier to understand.",
     "positive": "Instead of a BI request and a three-day wait, our tool lets anyone on the team answer their own data questions in minutes \u2014 by pulling from connected sources and letting them filter without SQL.",
     "negative": "Our advanced analytics solution makes data insights easier through our intelligent self-service platform that optimises your entire data workflow seamlessly.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Full argument progression vs abstract platform claim.",
     "intended_trap": "'Self-service platform' + 'intelligent' sounds concrete."},
    {"pair_id": "R1_T05", "anchor": "Automate your customer support with AI.",
     "positive": "Automate your customer support with AI that drafts responses from your best-resolved tickets \u2014 so quality improves each week without anyone reviewing every reply.",
     "negative": "Automate your customer support with our world-class AI that delivers guaranteed effortless support automation through our advanced intelligent platform.",
     "pair_type": "hype_trap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Mechanism + improvement loop vs hype density.",
     "intended_trap": "'Guaranteed effortless' should hard-veto."},
    {"pair_id": "R1_T06", "anchor": "We built an AI tool that helps product teams ship faster.",
     "positive": "We built an AI tool that helps product teams ship faster by ranking each backlog item by customer-signal weight \u2014 so sprint planning starts with evidence rather than opinion.",
     "negative": "We built an amazing AI tool that helps product teams ship faster through our synergistic product intelligence engine that seamlessly optimises your entire delivery pipeline.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Ranking mechanism (concrete) vs synergistic engine (fake).",
     "intended_trap": "'Optimises your entire delivery pipeline' sounds comprehensive."},
    {"pair_id": "R1_T07", "anchor": "We make financial reporting faster for accountants.",
     "positive": "We make financial reporting faster for accountants by pulling from connected accounts and generating consolidated P&Ls automatically \u2014 no copy-paste, no manual reconciliation.",
     "negative": "We make financial reporting faster for accountants through our world-class intelligent financial automation platform that revolutionises your reporting workflow.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Concrete steps (pull, generate, no copy-paste) vs fake mechanism.",
     "intended_trap": "'Revolutionises your reporting' sounds transformative."},
]
