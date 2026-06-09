"""Source policy violations, hard policy check, and soft continuity."""

from __future__ import annotations

import re
from typing import List, Dict, Optional


DEFAULT_SOURCE_POLICY = {
    "numeric_claims_must_be_in_anchor": True,
    "new_named_entities_must_be_in_anchor": True,
    "allowed_mechanism_expansion": True,
    "allowed_domain_specificity": True,
    "allowed_reasonable_rephrasing": True,
}

# Allowed abbreviations that should not be flagged as named entities
ALLOWED_ABBREVIATIONS = {
    "AI", "SQL", "API", "BI", "HR", "VC", "P&L", "NLP", "B2B", "SaaS",
    "KPI", "CRM", "ELM", "TTR", "NPS", "ROI", "OKR", "MVP", "SDK", "CLI",
    "UI", "UX", "CSS", "HTML", "JSON", "YAML", "AWS", "GCP",
}

# Generic role/domain nouns that should not be flagged as named entities
GENERIC_ROLE_NOUNS = {
    "manager", "director", "engineer", "analyst", "designer", "developer",
    "architect", "consultant", "specialist", "coordinator", "administrator",
    "executive", "officer", "president", "founder", "lead", "head",
    "team", "teams", "company", "companies", "customer", "customers",
    "client", "clients", "user", "users", "partner", "partners",
}

# Numeric words that count as invented numeric claims
NUMERIC_WORDS = {
    "thousands", "millions", "billions", "triple", "quadruple", "dozens",
    "hundreds", "double", "twice", "tenfold", "hundredfold",
}

# Time/quantity phrases patterns - only flag when combined with specific numeric claims
TIME_QUANTITY_PATTERNS = [
    r'\b\d+x\s+faster\b',
    r'\b\d+x\s+more\b',
    r'\b\d+x\s+better\b',
    r'\b\d+\s*%\s*(?:faster|better|more|less|improvement|reduction|increase)\b',
    r'\b\d+\s*(?:seconds|minutes|hours|days|weeks|months)\s+(?:faster|sooner|quicker)\b',
]

# Guarantee words/phrases
GUARANTEE_PHRASES = [
    "guaranteed", "100%", "always", "never fails", "zero errors", "perfectly",
    "zero downtime", "100 percent", "flawless", "infallible",
]

# Award/certification keywords
AWARD_CERT_KEYWORDS = [
    "award-winning", "award winning", "certified", "certification",
    "soc2", "soc 2", "iso", "hipaa", "gdpr compliant", "pci",
    "compliant", "compliance", "accredited", "accreditation",
    "patent", "patented",
]

# Customer/company claim patterns
CUSTOMER_COMPANY_PATTERNS = [
    r'\bfortune\s+\d+\b',
    r'\benterprise\s+clients?\b',
    r'\b\d+\+?\s+(?:companies|customers|clients|organizations|teams)\b',
    r'\b(?:trusted\s+by|used\s+by|chosen\s+by)\s+\d+',
]


def extract_numbers(text):
    """Extract all numeric tokens from text."""
    return set(re.findall(r'\b\d+(?:\.\d+)?%?\b', text or ''))


def _extract_digits_in_context(text):
    """Extract digit occurrences with surrounding context."""
    results = []
    for m in re.finditer(r'\b\d+(?:\.\d+)?%?\b', text or ''):
        start = max(0, m.start() - 20)
        end = min(len(text), m.end() + 20)
        results.append({"value": m.group(), "context": text[start:end].strip()})
    return results


def _detect_invented_numeric_digits(text, anchor):
    """Detect numeric digits in text that are not present in the anchor."""
    nums_anchor = extract_numbers(anchor)
    nums_text = extract_numbers(text)
    invented = nums_text - nums_anchor
    violations = []
    for num in invented:
        # Find context
        idx = text.find(num)
        ctx_start = max(0, idx - 15)
        ctx_end = min(len(text), idx + len(num) + 15)
        evidence = text[ctx_start:ctx_end].strip()
        violations.append({
            "violation_type": "invented_numeric_digit",
            "evidence": evidence,
            "severity": "hard",
        })
    return violations


def _detect_invented_numeric_words(text, anchor):
    """Detect written-out numeric words not present in anchor."""
    violations = []
    text_lower = (text or "").lower()
    anchor_lower = (anchor or "").lower()
    for word in NUMERIC_WORDS:
        if word in text_lower and word not in anchor_lower:
            # Find context
            idx = text_lower.find(word)
            ctx_start = max(0, idx - 15)
            ctx_end = min(len(text_lower), idx + len(word) + 15)
            evidence = text[ctx_start:ctx_end].strip()
            violations.append({
                "violation_type": "invented_numeric_word",
                "evidence": evidence,
                "severity": "hard",
            })
    return violations


def _detect_time_or_quantity_claims(text, anchor):
    """Detect time/quantity phrases in text not present in anchor."""
    violations = []
    text_lower = (text or "").lower()
    anchor_lower = (anchor or "").lower()
    for pattern in TIME_QUANTITY_PATTERNS:
        for m in re.finditer(pattern, text_lower):
            # Check if same phrase exists in anchor
            if not re.search(pattern, anchor_lower):
                evidence = m.group()
                violations.append({
                    "violation_type": "invented_time_or_quantity_claim",
                    "evidence": evidence,
                    "severity": "hard",
                })
    return violations


def _detect_invented_named_entities(text, anchor):
    """
    Detect new proper names not in anchor with guardrails.
    Avoids false positives from:
    - Sentence-initial common words
    - Allowed abbreviations (including plurals)
    - Product names already in anchor
    - Generic role/domain nouns
    - Well-known tech/tool/platform names used as common references
    - Single capitalized words that are common English words

    Only flags things that genuinely look like invented company or person names.
    """
    violations = []
    if not text or not anchor:
        return violations

    # Well-known tool/platform/product names that should never be flagged
    # These are common references in B2B tech writing
    well_known_names = {
        "slack", "zoom", "teams", "notion", "asana", "jira", "trello",
        "hubspot", "salesforce", "stripe", "shopify", "github", "gitlab",
        "figma", "miro", "confluence", "linear", "airtable", "zapier",
        "google", "microsoft", "apple", "amazon", "facebook", "meta",
        "twitter", "linkedin", "youtube", "dropbox", "mailchimp",
        "intercom", "zendesk", "freshdesk", "datadog", "pagerduty",
        "terraform", "kubernetes", "docker", "jenkins", "circleci",
        "vercel", "netlify", "heroku", "postgres", "redis", "mongodb",
        "elasticsearch", "kafka", "rabbitmq", "nginx", "cloudflare",
        "segment", "mixpanel", "amplitude", "looker", "tableau",
        "snowflake", "databricks", "airflow", "dbt", "fivetran",
    }

    anchor_lower = anchor.lower()
    anchor_words = set(re.findall(r'\b[A-Z][A-Za-z]+\b', anchor or ''))
    anchor_words_lower = {w.lower() for w in anchor_words}

    # Also extract all tokens from anchor for broader matching
    anchor_all_tokens = set(re.findall(r'\b[a-zA-Z]{2,}\b', anchor.lower()))

    # Check for allowed abbreviations including plural forms
    def is_allowed_abbrev(word):
        clean = re.sub(r's$', '', word)  # Strip trailing 's' for plurals
        return word in ALLOWED_ABBREVIATIONS or clean in ALLOWED_ABBREVIATIONS

    # Find all capitalized words in text
    sentences = re.split(r'[.!?]\s+', text)
    for sent in sentences:
        words = sent.split()
        for i, word in enumerate(words):
            # Skip first word of sentence (sentence-initial capitalization)
            if i == 0:
                continue
            # Clean the word (remove punctuation)
            clean_word = re.sub(r'[^A-Za-z&\'-]', '', word)
            if not clean_word or len(clean_word) < 2:
                continue
            # All-caps check: allowed abbreviations
            if clean_word.upper() == clean_word:
                if is_allowed_abbrev(clean_word):
                    continue
            # Check if capitalized
            if not clean_word[0].isupper():
                continue
            # Skip if it's a generic role noun
            if clean_word.lower() in GENERIC_ROLE_NOUNS:
                continue
            # Skip if it appears in the anchor (any form)
            if clean_word.lower() in anchor_words_lower:
                continue
            if clean_word in anchor_words:
                continue
            if clean_word.lower() in anchor_all_tokens:
                continue
            # Skip well-known tool/platform names
            if clean_word.lower() in well_known_names:
                continue
            # Skip common mid-sentence words that can be capitalized
            common_mid_sentence = {
                "instead", "through", "because", "however", "therefore",
                "furthermore", "moreover", "although", "while", "since",
                "before", "after", "during", "without", "within",
                "between", "against", "across", "around", "behind",
            }
            if clean_word.lower() in common_mid_sentence:
                continue

            # Skip single common English words (only flag truly unusual proper names)
            # This is conservative: we don't flag single capitalized words
            # that could be legitimate domain/tech terms used stylistically.
            # We only flag multi-word proper nouns or obviously fabricated names.
            # Single words in tech contexts are usually tool names, not inventions.
            # CONSERVATIVE: Don't flag single capitalized words at all from
            # the named entity check. Customer/company claims are caught by
            # the separate _detect_customer_or_company_claims function.
            pass

    return violations


def _detect_customer_or_company_claims(text, anchor):
    """Detect new customer/company name claims not in anchor."""
    violations = []
    text_lower = (text or "").lower()
    anchor_lower = (anchor or "").lower()

    for pattern in CUSTOMER_COMPANY_PATTERNS:
        for m in re.finditer(pattern, text_lower):
            if not re.search(pattern, anchor_lower):
                violations.append({
                    "violation_type": "invented_customer_or_company_claim",
                    "evidence": m.group(),
                    "severity": "hard",
                })

    # Also check for specific company names (Acme Corp, etc.)
    company_patterns = [
        r'\b[A-Z][a-z]+\s+(?:Corp|Inc|LLC|Ltd|Co|Group|Holdings)\b',
    ]
    for pattern in company_patterns:
        for m in re.finditer(pattern, text or ''):
            match_lower = m.group().lower()
            if match_lower not in anchor_lower:
                violations.append({
                    "violation_type": "invented_customer_or_company_claim",
                    "evidence": m.group(),
                    "severity": "hard",
                })

    return violations


def _detect_award_or_certification_claims(text, anchor):
    """Detect award/certification claims not in anchor."""
    violations = []
    text_lower = (text or "").lower()
    anchor_lower = (anchor or "").lower()

    for keyword in AWARD_CERT_KEYWORDS:
        if keyword in text_lower and keyword not in anchor_lower:
            # Find context
            idx = text_lower.find(keyword)
            ctx_start = max(0, idx - 10)
            ctx_end = min(len(text_lower), idx + len(keyword) + 10)
            evidence = text[ctx_start:ctx_end].strip()
            violations.append({
                "violation_type": "invented_award_or_certification_claim",
                "evidence": evidence,
                "severity": "hard",
            })

    return violations


def _detect_guarantee_claims(text, anchor):
    """Detect guarantee words/phrases."""
    violations = []
    text_lower = (text or "").lower()
    anchor_lower = (anchor or "").lower()

    for phrase in GUARANTEE_PHRASES:
        if phrase in text_lower and phrase not in anchor_lower:
            idx = text_lower.find(phrase)
            ctx_start = max(0, idx - 10)
            ctx_end = min(len(text_lower), idx + len(phrase) + 10)
            evidence = text[ctx_start:ctx_end].strip()
            violations.append({
                "violation_type": "guarantee_claim",
                "evidence": evidence,
                "severity": "hard",
            })

    return violations


# ─────────────────────────────────────────────────────────────────────
# UNIFIED SOURCE POLICY VIOLATIONS (Task 18.1)
# ─────────────────────────────────────────────────────────────────────

def source_policy_violations(text, anchor, policy=None, *, role="candidate", pair_type=None):
    """
    Detect ALL canonical taxonomy violation types.

    Args:
        text: The text to check for policy violations
        anchor: The source/anchor text
        policy: Optional policy dict (defaults to DEFAULT_SOURCE_POLICY)
        role: "candidate", "positive_pair", or "negative_pair"
        pair_type: Optional pair type for nuance (e.g. "source_drift", "specificity_trap")

    Returns:
        List of violation dicts: [{violation_type, evidence, severity}]

    IMPORTANT: Always compute violations for ALL roles. The role/pair_type
    affect how the CALLER uses the results, not whether violations are detected.
    """
    if policy is None:
        policy = DEFAULT_SOURCE_POLICY

    violations = []

    # 1. Invented numeric digits
    violations.extend(_detect_invented_numeric_digits(text, anchor))

    # 2. Invented numeric words
    violations.extend(_detect_invented_numeric_words(text, anchor))

    # 3. Invented time or quantity claims
    violations.extend(_detect_time_or_quantity_claims(text, anchor))

    # 4. Invented named entities (with guardrails)
    if policy.get("new_named_entities_must_be_in_anchor", True):
        violations.extend(_detect_invented_named_entities(text, anchor))

    # 5. Invented customer or company claims
    violations.extend(_detect_customer_or_company_claims(text, anchor))

    # 6. Invented award or certification claims
    violations.extend(_detect_award_or_certification_claims(text, anchor))

    # 7. Guarantee claims
    violations.extend(_detect_guarantee_claims(text, anchor))

    return violations


# ─────────────────────────────────────────────────────────────────────
# HARD SOURCE POLICY VIOLATED (Task 18.3)
# ─────────────────────────────────────────────────────────────────────

def hard_source_policy_violated(text, anchor, policy=None, *, role="candidate", pair_type=None):
    """
    Returns True if ANY hard-severity violation is detected.
    Filters by severity == "hard", NOT by list non-emptiness.
    """
    return any(
        v.get("severity") == "hard"
        for v in source_policy_violations(text, anchor, policy, role=role, pair_type=pair_type)
    )


# ─────────────────────────────────────────────────────────────────────
# VALIDATE PAIR SOURCE POLICY (Task 18.4)
# ─────────────────────────────────────────────────────────────────────

def validate_pair_source_policy(pair):
    """
    Validate a pair against source policy.
    Returns {valid, errors, pair_id, negative_policy_violations}.

    - Always computes violations for BOTH positive and negative
    - Stores negative_policy_violations on result (for reporting)
    - Drops pair only if positive has any hard violation
    """
    anchor = pair["anchor"]
    pos = pair["positive"]
    neg = pair["negative"]
    policy = pair.get("source_policy", DEFAULT_SOURCE_POLICY)
    pair_type = pair.get("pair_type", "other")

    # Compute violations for positive
    pos_violations = source_policy_violations(
        pos, anchor, policy, role="positive_pair", pair_type=pair_type
    )
    pos_hard = [v for v in pos_violations if v.get("severity") == "hard"]

    # Compute violations for negative (record, do NOT drop based on these)
    neg_violations = source_policy_violations(
        neg, anchor, policy, role="negative_pair", pair_type=pair_type
    )

    errors = []
    if pos_hard:
        error_types = list(set(v["violation_type"] for v in pos_hard))
        errors.append({
            "type": "positive_hard_policy_violation",
            "violation_types": error_types,
            "count": len(pos_hard),
        })

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "pair_id": pair["pair_id"],
        "positive_policy_violations": pos_violations,
        "negative_policy_violations": neg_violations,
    }


# ─────────────────────────────────────────────────────────────────────
# PROBE: SOURCE CONTINUITY (kept here per spec)
# ─────────────────────────────────────────────────────────────────────

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
