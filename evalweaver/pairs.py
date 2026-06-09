"""Pair generation, source policy validation, and train/heldout splitting."""

from evalweaver.policy import DEFAULT_SOURCE_POLICY, validate_pair_source_policy
from evalweaver.config import seeded_shuffle
from evalweaver.artifacts import log


# ─────────────────────────────────────────────────────────────────────
# PAIR TYPE CONSTANTS
# ─────────────────────────────────────────────────────────────────────

PAIR_TYPE_HYPE_TRAP = "hype_trap"
PAIR_TYPE_FAKE_MECHANISM = "fake_mechanism"
PAIR_TYPE_SPECIFICITY_TRAP = "specificity_trap"
PAIR_TYPE_SUBTLE_QUALITY_GAP = "subtle_quality_gap"
PAIR_TYPE_SOURCE_DRIFT = "source_drift"


# ─────────────────────────────────────────────────────────────────────
# RAW_TEXT constant (used in pairs that reference it)
# ─────────────────────────────────────────────────────────────────────

RAW_TEXT = "EvalWeaver lets anyone create, use, and monetize AI improvers for subjective goals like make this more persuasive."


# ─────────────────────────────────────────────────────────────────────
# ALL ROUND 0 PAIRS
# ─────────────────────────────────────────────────────────────────────

ALL_PAIRS_R0 = [
    # -- hype_trap --
    {"pair_id": "R0_P01", "anchor": "We built an AI tool that helps product teams ship features faster.",
     "positive": "We built an AI tool that helps product teams ship features faster by surfacing which backlog items have the most customer signal \u2014 so you prioritise based on evidence, not gut feel.",
     "negative": "We built an amazing AI tool that helps product teams ship features faster with our revolutionary intelligent platform.",
     "pair_type": "hype_trap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive adds causal mechanism; negative adds hype.", "intended_trap": "Hype sounds confident."},
    {"pair_id": "R0_P02", "anchor": "Automate your customer support with AI.",
     "positive": "Automate your customer support with AI that learns from your best agents' resolved tickets \u2014 so response quality improves each week without manual tuning.",
     "negative": "Automate your customer support with our world-class AI that makes everything effortless and seamless for your entire team.",
     "pair_type": "hype_trap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive has mechanism; negative has hype.", "intended_trap": "World-class sounds authoritative."},
    {"pair_id": "R0_P08", "anchor": "Improve your team's meeting notes with AI.",
     "positive": "Improve your team's meeting notes with AI that maps each action item to the person who committed to it \u2014 so nothing falls through the cracks after the call.",
     "negative": "Improve your team's meeting notes with AI. Our best-in-class guaranteed system transforms every meeting into perfect, actionable outcomes effortlessly.",
     "pair_type": "hype_trap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive has concrete mechanism; negative packed with superlatives.", "intended_trap": "Superlative density."},
    # -- fake_mechanism (F7 FIX) --
    {"pair_id": "R0_F01", "anchor": "We help marketing teams measure campaign performance.",
     "positive": "We help marketing teams see which campaign elements drove conversions \u2014 by tracing each sign-up back to the specific ad variant, email, and landing page that touched it.",
     "negative": "We help marketing teams measure campaign performance by leveraging our advanced AI engine which synergistically optimises your entire marketing funnel through intelligent automation.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Both use 'by' + mechanism language. Positive has concrete workflow; negative has jargon.", "intended_trap": "'By leveraging our advanced AI' looks causal."},
    {"pair_id": "R0_F02", "anchor": "Our tool helps engineers write better code.",
     "positive": "Our tool helps engineers write better code by flagging only changes that touch security boundaries or performance-critical paths \u2014 so they focus review time where it matters.",
     "negative": "Our tool helps engineers write better code through our next-generation intelligent code analysis engine powered by advanced technology.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive: specific what/where flagged. Negative: abstract engine.", "intended_trap": "'Next-generation intelligent analysis' sounds technical."},
    {"pair_id": "R0_F03", "anchor": "We make onboarding faster for new hires.",
     "positive": "We make onboarding faster for new hires by connecting to your HR system and pre-provisioning all access before day one \u2014 so nothing waits on an IT ticket.",
     "negative": "We make onboarding faster for new hires using our seamless intelligent automation platform that synergistically streamlines your entire onboarding experience.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive: concrete step (connects to HR, pre-provisions). Negative: jargon chain.", "intended_trap": "'Seamless intelligent automation' sounds mechanism-like."},
    # -- specificity_trap --
    {"pair_id": "R0_P04", "anchor": "Our sales tool helps reps close more deals.",
     "positive": "Our sales tool shows reps which objection pattern each prospect matches \u2014 so they run the right playbook at the right moment.",
     "negative": "Our sales tool helps reps close more deals faster with higher win rates and better customer satisfaction across enterprise clients.",
     "pair_type": "specificity_trap", "source_policy": {**DEFAULT_SOURCE_POLICY, "numeric_claims_must_be_in_anchor": False},
     "label_contract": "Positive has causal mechanism; negative has vague benefit claims.", "intended_trap": "Negative sounds specific but has no mechanism."},
    {"pair_id": "R0_P09", "anchor": "We help startups raise their seed round.",
     "positive": "We help startups raise their seed round by stress-testing their pitch against the most common VC objections before they walk into the room.",
     "negative": "We help startups successfully raise their seed round through our comprehensive world-class pitch preparation platform leveraging advanced AI.",
     "pair_type": "specificity_trap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive has concrete mechanism. Negative has fake mechanism + jargon.", "intended_trap": "World-class pitch prep sounds specific."},
    # -- subtle_quality_gap --
    {"pair_id": "R0_P05", "anchor": "Turn customer feedback into product decisions.",
     "positive": "Stop guessing what to build next. Turn messy customer feedback into ranked decisions your team can act on this sprint.",
     "negative": "Transform your customer feedback experience into optimised product decision solutions leveraging our advanced platform.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive has problem\u2192result structure. Negative has abstract transformation framing.", "intended_trap": "Both describe the same outcome differently."},
    {"pair_id": "R0_P06", "anchor": "Our analytics tool makes data easier to understand.",
     "positive": "Instead of waiting for a BI report, our tool lets non-technical teams answer their own data questions in minutes \u2014 without writing SQL.",
     "negative": "Our advanced analytics solution makes data insights easier and more accessible for all stakeholders through intelligent automation.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive has before/after + concrete mechanism. Negative has abstract improvement.", "intended_trap": "Both sound helpful."},
    {"pair_id": "R0_P10", "anchor": "We help companies reduce customer churn.",
     "positive": "We help CS teams flag at-risk accounts before customers cancel \u2014 by tracking drops in product engagement and support ticket frequency.",
     "negative": "We help companies reduce customer churn through our innovative AI-powered customer success platform that optimises retention seamlessly.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive: concrete detection mechanism. Negative: fake mechanism + jargon.", "intended_trap": "'AI-powered' sounds sophisticated."},
    # -- source_drift --
    {"pair_id": "R0_P07", "anchor": RAW_TEXT,
     "positive": "EvalWeaver lets anyone create, use, and monetise AI improvers for subjective goals like 'more persuasive' \u2014 by discovering what the goal means and testing it before rewriting.",
     "negative": "EvalWeaver lets anyone create, use, and monetise AI improvers. Our groundbreaking platform has helped thousands achieve amazing persuasion results with our world-class AI.",
     "pair_type": "source_drift", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive preserves claim + adds mechanism. Negative drifts to hype.", "intended_trap": "Both open with the original claim."},
    # -- audience_relevance_gap --
    {"pair_id": "R0_A01", "anchor": "Our software helps teams collaborate better.",
     "positive": "Instead of chasing updates across Slack threads, our software surfaces the three decisions your team is stuck on \u2014 so you unblock them in one async review.",
     "negative": "Our powerful collaboration software helps teams work better together through our advanced intelligent platform for seamless collaboration.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive has before/after + concrete mechanism. Negative has abstract platform claim.", "intended_trap": "Both claim collaboration improvement."},
    # -- TEST PAIRS (heldout) --
    {"pair_id": "R0_T01", "anchor": "Our tool saves engineers time on code reviews.",
     "positive": "Our tool saves engineers time on code reviews by flagging only changes that touch security boundaries or performance-critical paths \u2014 filtering style diffs that don't affect correctness.",
     "negative": "Our amazing tool saves engineers significant time on code reviews through our intelligent automated review system that makes everything effortless.",
     "pair_type": "hype_trap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Mechanism vs hype.", "intended_trap": "intelligent + effortless sounds technical."},
    {"pair_id": "R0_T02", "anchor": "We make financial reporting faster for accountants.",
     "positive": "We make financial reporting faster for accountants by pulling from connected accounts and generating consolidated P&Ls automatically \u2014 no copy-paste from spreadsheets.",
     "negative": "We make financial reporting faster for accountants with our revolutionary AI-powered platform that delivers incredible results instantly.",
     "pair_type": "hype_trap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Mechanism vs hype.", "intended_trap": "Revolutionary AI sounds powerful."},
    {"pair_id": "R0_T03", "anchor": "Our API helps developers integrate payments.",
     "positive": "Our API helps developers integrate payments by handling the edge cases that break checkout \u2014 currency mismatches, retry logic, and webhook ordering \u2014 so you ship in days, not weeks.",
     "negative": "Our API helps developers integrate payments seamlessly using our world-class developer-first payment infrastructure powered by advanced technology.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Positive: concrete edge cases named. Negative: fake mechanism.", "intended_trap": "'Developer-first' sounds credible."},
    {"pair_id": "R0_T04", "anchor": "We help sales teams prioritise leads.",
     "positive": "Instead of calling every lead in order of entry, our tool scores each one against your closed-deal patterns \u2014 so reps call the right accounts first.",
     "negative": "We help sales teams prioritise leads with our groundbreaking predictive AI that maximises your revenue potential through intelligent scoring algorithms.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Concrete method vs fake mechanism.", "intended_trap": "'Predictive AI' sounds scientific."},
    {"pair_id": "R0_T05", "anchor": "Turn customer feedback into product decisions.",
     "positive": "Instead of debating priorities in a planning meeting, our tool ranks product decisions by the weight of customer signal behind each one \u2014 so the conversation starts with evidence.",
     "negative": "Transform your product management with our advanced AI-powered feedback intelligence solution that optimises your entire decision-making workflow seamlessly.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Argument progression vs abstract platform.", "intended_trap": "'Feedback intelligence' sounds specific."},
    {"pair_id": "R0_T06", "anchor": "Our platform helps companies reduce churn.",
     "positive": "Our platform helps CS teams catch at-risk accounts before they churn \u2014 by monitoring product usage signals and alerting the right rep automatically.",
     "negative": "Our innovative retention platform helps companies reduce churn through our seamless intelligent customer success optimisation system.",
     "pair_type": "subtle_quality_gap", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Concrete mechanism vs jargon chain.", "intended_trap": "'Customer success optimisation' sounds professional."},
    {"pair_id": "R0_T07", "anchor": "We help startups raise their seed round.",
     "positive": "We help startups raise their seed round by running their pitch through the objections their target investors have raised most often \u2014 before the actual meeting.",
     "negative": "We help startups raise their seed round with our world-class pitch coaching platform leveraging advanced AI to guarantee investor readiness.",
     "pair_type": "source_drift", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Mechanism vs hype + source drift.", "intended_trap": "'Investor readiness' sounds relevant."},
    {"pair_id": "R0_T08", "anchor": "Our software helps teams collaborate better.",
     "positive": "Our software shows your team the three decisions stuck in review \u2014 so one async session unblocks a week of work.",
     "negative": "Our intelligent collaboration platform uses advanced AI to seamlessly optimise your team's workflow and communication through next-generation technology.",
     "pair_type": "fake_mechanism", "source_policy": {**DEFAULT_SOURCE_POLICY},
     "label_contract": "Concrete blocker removal vs fake mechanism.", "intended_trap": "'Next-generation intelligent' sounds substantial."},
]


# ─────────────────────────────────────────────────────────────────────
# PAIR SPLITTING LOGIC
# ─────────────────────────────────────────────────────────────────────

def validate_and_split_pairs(all_pairs, seed, prefix_test="R0_T"):
    """
    Validate pair source policies and split into train/heldout.
    Returns (pair_suite, valid_pairs, invalid_pairs, policy_results).
    """
    policy_results = [validate_pair_source_policy(p) for p in all_pairs]
    valid_pairs = [all_pairs[i] for i, r in enumerate(policy_results) if r["valid"]]
    invalid_pairs = [{"pair": all_pairs[i], "errors": r["errors"]}
                     for i, r in enumerate(policy_results) if not r["valid"]]

    # Split heldout: take T-suffix pairs as test, rest as train
    train_pairs = seeded_shuffle(
        [p for p in valid_pairs if not p["pair_id"].startswith(prefix_test)], seed
    )
    heldout_pairs = [p for p in valid_pairs if p["pair_id"].startswith(prefix_test)]

    for p in train_pairs:
        p["split"] = "train"
    for p in heldout_pairs:
        p["split"] = "test"
        p["frozen"] = True

    pair_suite = {
        "train": train_pairs,
        "test": heldout_pairs,
        "all": train_pairs + heldout_pairs,
    }

    return pair_suite, valid_pairs, invalid_pairs, policy_results


def merge_adversarial_pairs(base_suite, adv_pairs, seed, prefix_test="R1_T"):
    """
    Merge adversarial pairs into the growing pair suite.
    Adversarial train pairs get split='adversarial', new heldout get split='test'.
    Returns (merged_suite, adv_train, new_heldout, valid_adv, invalid_adv).
    """
    adv_policy_results = [validate_pair_source_policy(p) for p in adv_pairs]
    valid_adv = [adv_pairs[i] for i, r in enumerate(adv_policy_results) if r["valid"]]
    invalid_adv = [{"pair": adv_pairs[i], "errors": r["errors"]}
                   for i, r in enumerate(adv_policy_results) if not r["valid"]]

    adv_train = seeded_shuffle(
        [p for p in valid_adv if not p["pair_id"].startswith(prefix_test)], seed
    )
    new_heldout = [p for p in valid_adv if p["pair_id"].startswith(prefix_test)]

    for p in adv_train:
        p["split"] = "adversarial"
    for p in new_heldout:
        p["split"] = "test"
        p["frozen"] = True

    merged_suite = {
        "train": base_suite["train"] + adv_train,
        "test": base_suite["test"] + new_heldout,
        "adversarial": adv_train,
        "all": base_suite["train"] + adv_train + base_suite["test"] + new_heldout,
    }

    return merged_suite, adv_train, new_heldout, valid_adv, invalid_adv
