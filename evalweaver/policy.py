"""Source policy violations, hard policy check, and soft continuity."""

import re


DEFAULT_SOURCE_POLICY = {
    "numeric_claims_must_be_in_anchor": True,
    "new_named_entities_must_be_in_anchor": True,
    "allowed_mechanism_expansion": True,
    "allowed_domain_specificity": True,
    "allowed_reasonable_rephrasing": True,
}


def extract_numbers(text):
    """Extract all numeric tokens from text."""
    return set(re.findall(r'\b\d+(?:\.\d+)?%?\b', text or ''))


def validate_pair_source_policy(pair):
    """
    Validate a pair against source policy.
    Returns {valid, errors, pair_id}.
    Drops pair if positive invents numeric claims not in anchor.
    """
    anchor = pair["anchor"]
    pos = pair["positive"]
    neg = pair["negative"]
    policy = pair.get("source_policy", DEFAULT_SOURCE_POLICY)
    ptype = pair.get("pair_type", "other")
    nums_a = extract_numbers(anchor)
    nums_p = extract_numbers(pos)
    nums_n = extract_numbers(neg)
    pos_new = nums_p - nums_a
    neg_new = nums_n - nums_a
    errors = []
    if policy.get("numeric_claims_must_be_in_anchor") and pos_new:
        errors.append({"type": "positive_invents_numeric", "values": sorted(pos_new)})
    if neg_new and ptype not in ["specificity_trap", "source_drift"]:
        errors.append({"type": "negative_invents_numeric_outside_trap", "values": sorted(neg_new)})
    return {"valid": len(errors) == 0, "errors": errors, "pair_id": pair["pair_id"]}


def hard_source_policy_violated(text, anchor, policy=None):
    """
    Returns True only for invented metrics/guarantees — hard veto.
    This is the gate that zeros a scorer output or vetoes a candidate.
    """
    if policy is None:
        policy = DEFAULT_SOURCE_POLICY
    if policy.get("numeric_claims_must_be_in_anchor"):
        nums_a = extract_numbers(anchor)
        nums_t = extract_numbers(text)
        if nums_t - nums_a:
            return True
    guarantee_words = ["guaranteed", "100%", "always", "never fails", "zero errors", "perfectly"]
    low = (text or "").lower()
    if any(g in low for g in guarantee_words):
        return True
    return False


def probe_source_continuity(text, anchor):
    """
    Soft continuous continuity — does NOT zero on rephrasing. Spec §3.
    Returns a float in [0, 1] measuring how well text preserves anchor intent.
    """
    stop = set("the and for are but not all can had was one our out did its get may say she too use".split())

    def ctoks(s):
        return set(t for t in re.findall(r'[a-zA-Z]{3,}', (s or '').lower()) if t not in stop)

    def action_words(s):
        av = {"save", "reduce", "increase", "identify", "surface", "flag", "detect", "show", "track",
              "measure", "rank", "eliminate", "convert", "automate", "close", "discover", "build", "test"}
        return {t for t in ctoks(s) if t in av}

    def domain_nouns(s):
        dn = {"account", "customer", "churn", "revenue", "sprint", "ticket", "objection", "pipeline",
              "backlog", "query", "report", "metric", "team", "lead", "deal", "conversion", "retention"}
        return {t for t in ctoks(s) if t in dn}

    a, t = ctoks(anchor), ctoks(text)
    if not a:
        return 0.5
    overlap = len(a & t) / len(a)
    act_a, act_t = action_words(anchor), action_words(text)
    noun_a, noun_t = domain_nouns(anchor), domain_nouns(text)
    act_overlap = len(act_a & act_t) / max(1, len(act_a)) if act_a else 0.5
    noun_overlap = len(noun_a & noun_t) / max(1, len(noun_a)) if noun_a else 0.5
    return float(max(0.0, min(1.0, 0.5 * overlap + 0.25 * act_overlap + 0.25 * noun_overlap)))
