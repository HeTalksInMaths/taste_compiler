"""Multi-generation evolutionary loop for scorer discovery.

Closes the loop left open by the 2-round pipeline (R0 + R1 repair):

- Scorers are interpretable *genomes* — weighted compositions of the NLP
  probes — rendered to plain Python code, so every survivor is a readable
  scoring function, not a black box.
- Each generation, candidate adversarial pairs are synthesized from social
  media post anchors (Exa search when EXA_API_KEY is set, a built-in bank
  otherwise) and the pairs that the current Pareto frontier separates WORST
  are added to the suite — directly exploiting the best scorers' coverage
  gaps.
- New scorers are bred via mutation, crossover, and gap-biased immigrants
  (plus optional live LLM proposals via the Bedrock provider), validated,
  and selected by heldout fitness with Pareto-frontier elitism.

The whole loop is deterministic offline (mock mode, no API keys needed);
Exa anchors and LLM mutation are graceful upgrades when credentials exist.
"""

import json
import os
import random
from collections import defaultdict

from evalweaver.artifacts import log, save, resolve_output_directory
from evalweaver.runner import get_namespace
from evalweaver.probes import load_probes
from evalweaver.policy import DEFAULT_SOURCE_POLICY, validate_pair_source_policy
from evalweaver.pairs import ALL_PAIRS_R0, validate_and_split_pairs, merge_adversarial_pairs
from evalweaver.scorers import validate_scorer_on_pairs
from evalweaver.evaluation import eval_scorer, compute_summary
from evalweaver.pareto import compute_pareto
from evalweaver.failure_packet import build_failure_packet
from evalweaver.runner import py_run_scorer


# ─────────────────────────────────────────────────────────────────────
# EVOLUTION DEFAULTS (overridable via config / CLI)
# ─────────────────────────────────────────────────────────────────────

EVOLVE_DEFAULTS = {
    "n_generations": 5,
    "population_size": 12,
    "n_adv_per_gen": 6,          # adversarial pairs added per generation
    "n_adv_candidates": 48,      # synthesized candidates to select the hardest from
    "patience": 3,               # generations without fitness improvement before stopping
    "n_elite": 3,                # Pareto elites always retained
}


# ─────────────────────────────────────────────────────────────────────
# PROBE REGISTRY — the gene alphabet
# ─────────────────────────────────────────────────────────────────────

PROBE_CALLS = {
    "argument_progression": "probe_argument_progression(text)",
    "real_mechanism_quality": "_clamp(probe_real_mechanism_quality(text))",
    "mechanism_result_alignment": "probe_mechanism_result_alignment(text)",
    "causal_density": "probe_causal_density(text)",
    "specificity_without_invention": "probe_specificity_without_invention(text, anchor)",
    "specificity": "probe_specificity(text)",
    "audience_relevance": "probe_audience_relevance(text)",
    "epistemic_calibration": "probe_epistemic_calibration(text)",
    "abstract_jargon_density": "probe_abstract_jargon_density(text)",
    "persuasion_risk": "probe_persuasion_risk(text)",
}

PENALTY_PROBES = {"abstract_jargon_density", "persuasion_risk"}
REWARD_PROBES = [p for p in PROBE_CALLS if p not in PENALTY_PROBES]

# One-line semantics for each probe — passed to the LLM mutation context so
# proposals are grounded in what each gene actually measures, not just names.
PROBE_SEMANTICS = {
    "argument_progression": "Detects problem→mechanism→result structure (1.0 = all three present).",
    "real_mechanism_quality": "Causal markers followed by concrete objects score up; fake-mechanism jargon after 'by/through' scores down.",
    "mechanism_result_alignment": "Mechanism clauses with concrete action+object, result clauses with concrete consequence; jargon-only clauses penalised.",
    "causal_density": "Causal connective density per sentence — counts markers regardless of what follows them.",
    "specificity_without_invention": "Concrete specificity (caps, action verbs) minus jargon; zeroes if hard source policy violated.",
    "specificity": "General specificity: action verbs and named entities vs abstractions.",
    "audience_relevance": "Before-state markers plus second-person pronoun density.",
    "epistemic_calibration": "Hedge density vs superlative density — calibrated claims score higher.",
    "abstract_jargon_density": "PENALTY: density of abstract jargon words (seamless, intelligent, platform...).",
    "persuasion_risk": "PENALTY: hype/superlative density that triggers persuasion-knowledge backfire.",
}

SCORER_CONTRACT = (
    "def scorer(text, anchor, params) returning float in [0.0, 1.0] via _clamp(); "
    "call only the registered probe functions, violates_hard_source_policy, "
    "probe_source_continuity, and _clamp; no imports; deterministic; "
    "non-constant output across texts; typically veto with 'return 0.0' when "
    "violates_hard_source_policy(text, anchor) is true."
)

# Which probes plausibly close a coverage gap on each pair type — used to
# bias mutation and immigrant genomes toward the frontier's failure modes.
GAP_PROBES = {
    "fake_mechanism": ["real_mechanism_quality", "mechanism_result_alignment", "abstract_jargon_density"],
    "hype_trap": ["persuasion_risk", "epistemic_calibration"],
    "subtle_quality_gap": ["argument_progression", "specificity_without_invention", "mechanism_result_alignment"],
    "specificity_trap": ["specificity_without_invention", "real_mechanism_quality"],
    "source_drift": ["epistemic_calibration", "persuasion_risk"],
}


# ─────────────────────────────────────────────────────────────────────
# GENOME → CODE / HYPOTHESIS
# ─────────────────────────────────────────────────────────────────────

def render_scorer_code(genome):
    """Render a genome as a readable scorer function (same shape as R0/R1 code)."""
    lines = [
        "def scorer(text, anchor, params):",
        "    if violates_hard_source_policy(text, anchor):",
        "        return 0.0",
    ]
    gate = genome.get("jargon_gate")
    if gate is not None:
        lines += [
            f"    if probe_abstract_jargon_density(text) > {gate:.2f}:",
            "        return _clamp(probe_argument_progression(text) * 0.1)",
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


def genome_hypothesis(genome):
    """Human-readable hypothesis string derived from the genome structure."""
    parts = []
    for t in genome["terms"]:
        sign = "−" if t["probe"] in PENALTY_PROBES else "+"
        parts.append(f"{sign}{t['weight']:.2f}·{t['probe']}")
    desc = "Weighted blend: " + " ".join(parts)
    if genome.get("product"):
        a, b = genome["product"]
        desc += f"; interaction {genome['product_weight']:.2f}·{a}×{b}"
    if genome.get("jargon_gate") is not None:
        desc += f"; jargon gate at {genome['jargon_gate']:.2f}"
    cb = genome.get("continuity_blend", 0.0)
    if cb > 0.01:
        desc += f"; source continuity blend {cb:.2f}"
    desc += "; hard policy veto."
    return desc


# ─────────────────────────────────────────────────────────────────────
# GENOME OPERATORS
# ─────────────────────────────────────────────────────────────────────

def _w(rng, lo=0.2, hi=0.6):
    return round(rng.uniform(lo, hi), 2)


def random_genome(rng, gap_probes=None):
    """Random genome, optionally biased toward gap-closing probes."""
    pool = list(REWARD_PROBES)
    terms = []
    if gap_probes:
        biased = [p for p in gap_probes if p not in PENALTY_PROBES]
        if biased:
            terms.append({"probe": rng.choice(biased), "weight": _w(rng, 0.3, 0.6)})
    n_terms = rng.randint(2, 3)
    while len(terms) < n_terms:
        p = rng.choice(pool)
        if all(t["probe"] != p for t in terms):
            terms.append({"probe": p, "weight": _w(rng)})
    if rng.random() < 0.6:
        pen = rng.choice(sorted(PENALTY_PROBES))
        terms.append({"probe": pen, "weight": _w(rng, 0.15, 0.45)})
    genome = {
        "terms": terms,
        "jargon_gate": round(rng.uniform(0.18, 0.35), 2) if rng.random() < 0.5 else None,
        "product": None,
        "product_weight": 0.0,
        "continuity_blend": round(rng.uniform(0.2, 0.6), 2),
    }
    if rng.random() < 0.5:
        a, b = rng.sample(REWARD_PROBES, 2)
        genome["product"] = [a, b]
        genome["product_weight"] = _w(rng, 0.2, 0.5)
    return genome


def mutate_genome(genome, rng, gap_probes=None):
    """Apply 1-2 structural/weight mutations; gap probes are favoured for new terms."""
    g = {
        "terms": [dict(t) for t in genome["terms"]],
        "jargon_gate": genome.get("jargon_gate"),
        "product": list(genome["product"]) if genome.get("product") else None,
        "product_weight": genome.get("product_weight", 0.0),
        "continuity_blend": genome.get("continuity_blend", 0.0),
    }
    ops = ["jitter", "add_term", "drop_term", "swap_probe", "gate", "blend", "product"]
    for _ in range(rng.randint(1, 2)):
        op = rng.choice(ops)
        if op == "jitter" and g["terms"]:
            t = rng.choice(g["terms"])
            t["weight"] = round(max(0.05, min(0.8, t["weight"] + rng.uniform(-0.15, 0.15))), 2)
        elif op == "add_term" and len(g["terms"]) < 4:
            pool = [p for p in (gap_probes or []) if all(t["probe"] != p for t in g["terms"])]
            if not pool:
                pool = [p for p in PROBE_CALLS if all(t["probe"] != p for t in g["terms"])]
            if pool:
                p = rng.choice(pool)
                lo, hi = (0.15, 0.45) if p in PENALTY_PROBES else (0.2, 0.6)
                g["terms"].append({"probe": p, "weight": _w(rng, lo, hi)})
        elif op == "drop_term" and len(g["terms"]) > 1:
            g["terms"].pop(rng.randrange(len(g["terms"])))
        elif op == "swap_probe" and g["terms"]:
            t = rng.choice(g["terms"])
            same_kind = sorted(PENALTY_PROBES) if t["probe"] in PENALTY_PROBES else REWARD_PROBES
            choices = [p for p in same_kind if all(x["probe"] != p for x in g["terms"])]
            if choices:
                t["probe"] = rng.choice(choices)
        elif op == "gate":
            if g["jargon_gate"] is None:
                g["jargon_gate"] = round(rng.uniform(0.18, 0.35), 2)
            elif rng.random() < 0.3:
                g["jargon_gate"] = None
            else:
                g["jargon_gate"] = round(max(0.1, min(0.45, g["jargon_gate"] + rng.uniform(-0.08, 0.08))), 2)
        elif op == "blend":
            g["continuity_blend"] = round(max(0.0, min(0.7, g["continuity_blend"] + rng.uniform(-0.15, 0.15))), 2)
        elif op == "product":
            if g["product"] is None:
                a, b = rng.sample(REWARD_PROBES, 2)
                g["product"], g["product_weight"] = [a, b], _w(rng, 0.2, 0.5)
            elif rng.random() < 0.3:
                g["product"], g["product_weight"] = None, 0.0
            else:
                g["product_weight"] = round(max(0.1, min(0.7, g["product_weight"] + rng.uniform(-0.15, 0.15))), 2)
    return g


def crossover_genomes(ga, gb, rng):
    """Recombine two parent genomes: union of terms (sampled), gates from either."""
    by_probe = {}
    for t in ga["terms"] + gb["terms"]:
        if t["probe"] in by_probe:
            by_probe[t["probe"]] = round((by_probe[t["probe"]] + t["weight"]) / 2, 2)
        else:
            by_probe[t["probe"]] = t["weight"]
    probes = list(by_probe)
    rng.shuffle(probes)
    terms = [{"probe": p, "weight": by_probe[p]} for p in probes[:4]]
    src = ga if rng.random() < 0.5 else gb
    other = gb if src is ga else ga
    return {
        "terms": terms,
        "jargon_gate": src.get("jargon_gate"),
        "product": list(src["product"]) if src.get("product") else (list(other["product"]) if other.get("product") else None),
        "product_weight": src.get("product_weight") or other.get("product_weight", 0.0),
        "continuity_blend": round((ga.get("continuity_blend", 0) + gb.get("continuity_blend", 0)) / 2, 2),
    }


# ─────────────────────────────────────────────────────────────────────
# ANCHOR COLLECTION (Exa social search with offline fallback)
# ─────────────────────────────────────────────────────────────────────

FALLBACK_SOCIAL_POSTS = [
    "We just launched a tool that helps recruiters screen candidates faster.",
    "Excited to share what we have been building: an assistant that drafts your weekly investor update.",
    "Our new feature lets support teams see which tickets are about to breach their response target.",
    "After months of work, our platform now helps product managers turn user interviews into a ranked backlog.",
    "We help agencies report campaign results to clients without spreadsheet gymnastics.",
    "Today we are releasing a dashboard that shows founders where their pipeline is leaking.",
    "Our integration now connects your CRM to your billing system so renewals never surprise you.",
    "We built a writing assistant for sales teams that drafts follow-up emails from call notes.",
    "Thrilled to announce our tool that helps engineering managers spot review bottlenecks.",
    "We help compliance teams check marketing copy before it goes out the door.",
    "Our scheduling tool finds the meeting time that protects everyone's focus blocks.",
    "We just shipped alerts that tell CS teams when a key account goes quiet.",
]


def collect_social_anchors(config, out_dir):
    """Collect social media post anchors. Tries Exa when enabled; falls back
    to the built-in bank so the loop always runs offline."""
    goal = config.get("goal", "persuasive")
    anchors = []
    source = "fallback_bank"
    if config.get("use_exa_search"):
        try:
            from evalweaver.providers.exa_search import search_social_content
            results = search_social_content(
                channel=config.get("channel", "LinkedIn"),
                topic=config.get("topic", "B2B SaaS product launch"),
                audience=config.get("audience", "founders"),
                num_results=15,
            )
            for r in results:
                text = (r.get("snippet") or r.get("title") or "").strip()
                if len(text) >= 40:
                    anchors.append({"anchor": text[:280], "url": r.get("url", ""), "source": "exa"})
            if anchors:
                source = "exa"
        except Exception as e:
            log("evolve", f"Exa anchor collection unavailable ({e}); using fallback bank", "warn")
    if not anchors:
        anchors = [{"anchor": p, "url": "", "source": "fallback_bank"} for p in FALLBACK_SOCIAL_POSTS]
    save("evolve_anchors", {"goal": goal, "source": source, "anchors": anchors}, out_dir)
    log("evolve", f"Collected {len(anchors)} social anchors (source={source})", "ok")
    return anchors


# ─────────────────────────────────────────────────────────────────────
# ADVERSARIAL PAIR SYNTHESIS
# ─────────────────────────────────────────────────────────────────────

# Positive clauses stay policy-safe: no numbers, no new named entities,
# no guarantees — concrete lowercase mechanisms and results only.
MECH_CLAUSES = [
    "by flagging the accounts whose product usage dropped and routing them to the owning rep",
    "by tracing each reply back to the exact template and send time that produced it",
    "by ranking the backlog by how many support tickets reference each item",
    "by checking every draft against the objections your audience raises most often",
    "by mapping each action item to the person who committed to it during the call",
    "by pulling the queries your team runs most and turning them into shared reports",
    "by surfacing the review comments that block a merge and filtering the style noise",
    "by matching each lead against the patterns from your closed deals",
    "by tracking which approvals sit idle and alerting the owner before the deadline slips",
]

RESULT_CLAUSES = [
    "so the team spends its time where the evidence points",
    "so nothing falls through the cracks after the meeting",
    "so you start the conversation with evidence instead of guesswork",
    "so the next sprint is planned from signal, not opinion",
    "so reps call the right accounts first",
    "so review time goes to the changes that matter",
]

NEG_CLAUSES = {
    "hype_trap": [
        "with our revolutionary, world-class platform that delivers amazing results effortlessly",
        "using our groundbreaking best-in-class system, guaranteed to transform your results instantly",
        "with the ultimate intelligent solution that makes everything perfect and effortless",
    ],
    "fake_mechanism": [
        "by leveraging our advanced intelligent engine that synergistically optimises your entire workflow through intelligent automation",
        "through our next-generation platform powered by advanced technology and seamless intelligent automation",
        "by using our seamless intelligent optimisation engine built on a transformative scalable architecture",
    ],
    "subtle_quality_gap": [
        "and transforms your entire experience into optimised outcomes through our intelligent solution",
        "while elevating your workflow with a seamless, robust and scalable experience",
        "and unlocks transformative value across your entire organisation through innovation",
    ],
    "specificity_trap": [
        "with better outcomes, stronger results, and improved satisfaction across your entire organisation",
        "delivering faster results, higher quality, and greater impact for every stakeholder",
    ],
    "source_drift": [
        ". Our groundbreaking platform has helped countless companies achieve incredible results with world-class AI",
        ". Thousands of teams trust our revolutionary engine to guarantee amazing outcomes",
    ],
}


def _anchor_stem(anchor):
    stem = anchor.strip().split(". ")[0].strip()
    return stem.rstrip(".!?")


def synthesize_candidate_pairs(anchors, gap_type_weights, rng, n_candidates):
    """Synthesize candidate adversarial pairs from social anchors. Pair types
    are sampled proportionally to the frontier's failure counts (coverage gaps)."""
    types = sorted(NEG_CLAUSES)
    weights = [1 + gap_type_weights.get(t, 0) * 3 for t in types]
    candidates, seen = [], set()
    attempts = 0
    while len(candidates) < n_candidates and attempts < n_candidates * 4:
        attempts += 1
        a = rng.choice(anchors)
        ptype = rng.choices(types, weights=weights, k=1)[0]
        stem = _anchor_stem(a["anchor"])
        if len(stem) < 25:
            continue
        mech = rng.choice(MECH_CLAUSES)
        result = rng.choice(RESULT_CLAUSES)
        neg = rng.choice(NEG_CLAUSES[ptype])
        positive = f"{stem} — {mech}, {result}."
        if ptype == "source_drift":
            negative = f"{stem}{neg}."
        else:
            negative = f"{stem} {neg}."
        key = (stem, mech, neg)
        if key in seen:
            continue
        seen.add(key)
        pair = {
            "anchor": a["anchor"],
            "anchor_url": a.get("url", ""),
            "positive": positive,
            "negative": negative,
            "pair_type": ptype,
            "source_policy": {**DEFAULT_SOURCE_POLICY},
            "label_contract": "Positive appends concrete mechanism + result to the post; negative appends the trap clause.",
            "intended_trap": f"Synthesized {ptype} targeting current frontier coverage gaps.",
        }
        if validate_pair_source_policy({**pair, "pair_id": "CAND"})["valid"]:
            candidates.append(pair)
    return candidates


def _llm_candidate_pairs(provider, llm_context, anchors, rng, n):
    """Optional LLM-generated adversarial candidates. They enter the same
    policy validation + frontier-margin selection as template candidates, so
    a bad generation can only waste a call, never corrupt the suite."""
    if provider is None or not hasattr(provider, "propose_adversarial_pairs"):
        return []
    try:
        context = {**llm_context,
                   "anchors": [a["anchor"] for a in rng.sample(anchors, min(6, len(anchors)))]}
        proposals = provider.propose_adversarial_pairs(context, n) or []
    except Exception as e:
        log("evolve", f"LLM pair generation skipped ({e}); using templates", "warn")
        return []
    valid = []
    for p in proposals[:n]:
        if not all(p.get(k) for k in ("anchor", "positive", "negative", "pair_type")):
            continue
        pair = {
            "anchor": p["anchor"],
            "positive": p["positive"],
            "negative": p["negative"],
            "pair_type": p["pair_type"],
            "source_policy": {**DEFAULT_SOURCE_POLICY},
            "label_contract": p.get("label_contract", "LLM-generated adversarial pair."),
            "intended_trap": p.get("intended_trap", "LLM-targeted frontier coverage gap."),
            "generator": "llm",
        }
        if validate_pair_source_policy({**pair, "pair_id": "CAND"})["valid"]:
            valid.append(pair)
    if proposals:
        log("evolve", f"LLM pairs: {len(valid)}/{len(proposals)} passed source policy", "ok")
    return valid


def select_adversarial_pairs(candidates, frontier_code, gen_idx, n_keep, rng):
    """Adversarial selection: keep the candidate pairs that the current Pareto
    frontier separates worst (lowest mean margin) — the coverage gap exploit."""
    scored = []
    for pair in candidates:
        margins = []
        for code in frontier_code.values():
            pr = py_run_scorer(code, pair["positive"], pair["anchor"])
            nr = py_run_scorer(code, pair["negative"], pair["anchor"])
            margins.append(pr["value"] - nr["value"])
        mean_margin = sum(margins) / max(1, len(margins))
        scored.append((mean_margin, pair))
    scored.sort(key=lambda x: x[0])
    selected = []
    for i, (margin, pair) in enumerate(scored[:n_keep]):
        # every 3rd hardest pair grows the frozen heldout set
        role = "T" if i % 3 == 2 else "A"
        pair = dict(pair)
        pair["pair_id"] = f"G{gen_idx}_{role}{i + 1:02d}"
        pair["frontier_margin_at_creation"] = round(margin, 4)
        pair["attacks_scorer_ids"] = list(frontier_code)
        selected.append(pair)
    return selected


# ─────────────────────────────────────────────────────────────────────
# POPULATION HELPERS
# ─────────────────────────────────────────────────────────────────────

def _make_member(sid, genome, lineage, parents):
    code = render_scorer_code(genome)
    return {
        "scorer_id": sid,
        "genome": genome,
        "code": code,
        "hypothesis": genome_hypothesis(genome),
        "lineage": lineage,
        "parents": parents,
    }


def fitness(summary):
    """Scalar fitness: heldout separation first, train and adversarial as support."""
    if not summary.get("execution_valid"):
        return -1.0
    adv = summary.get("adversarial_accuracy")
    return (
        2.0 * summary["test_accuracy"]
        + 3.0 * summary["test_margin"]
        + 0.5 * summary["train_accuracy"]
        + 1.0 * summary["train_margin"]
        + (1.0 * adv if adv is not None else 0.0)
    )


def build_mutation_context(goal, failure_packet, pareto, code_map, summaries):
    """Compact, purpose-built context for LLM scorer proposals.

    Carries exactly what a proposer needs — probe registry with semantics,
    the frontier's code and per-pair-type coverage map, failed visible pairs,
    accumulated mutation instructions, and the validity contract — instead of
    dumping whole artifacts. Heldout pair text is never included (anti-leakage:
    only aggregate heldout failure counts pass through the failure packet).
    """
    by_id = {s["scorer_id"]: s for s in summaries}
    frontier = []
    for p in pareto[:3]:
        s = by_id.get(p["scorer_id"], p)
        frontier.append({
            "scorer_id": p["scorer_id"],
            "hypothesis": s.get("hypothesis", ""),
            "test_accuracy": s.get("test_accuracy"),
            "test_margin": round(s.get("test_margin", 0), 4),
            "pair_type_accuracy": s.get("pair_type_accuracy", {}),
            "code": code_map.get(p["scorer_id"], ""),
        })
    return {
        "goal": goal,
        "scorer_contract": SCORER_CONTRACT,
        "probe_registry": [
            {"name": name, "call": PROBE_CALLS[name],
             "semantics": PROBE_SEMANTICS.get(name, "")}
            for name in PROBE_CALLS
        ],
        "frontier_scorers": frontier,
        "coverage_gaps": {
            "failed_pair_type_counts_train": failure_packet["failed_pair_type_counts"],
            "heldout_failures_by_pair_type": failure_packet["heldout_aggregate_only"]["heldout_failures_by_pair_type"],
        },
        "failed_visible_pairs": failure_packet["failed_visible_pairs"],
        "mutation_instructions": failure_packet["mutation_instructions"],
        "score_collapse_warnings": failure_packet["score_collapse_warnings"],
    }


def _llm_offspring(provider, llm_context, n, gen_idx):
    """Optional live LLM mutation. Prefers the structured propose_scorers tool
    call (one call, schema-validated output); falls back to the legacy
    generate_mutations chain, and to the deterministic genome operators on any
    failure. Every proposal must pass scorer validation before joining the
    population — invalid code is logged and dropped, never evaluated."""
    if provider is None or n <= 0 or llm_context is None:
        return []
    proposals = []
    try:
        if hasattr(provider, "propose_scorers"):
            proposals = provider.propose_scorers(llm_context, n) or []
        else:
            for m in provider.generate_mutations(llm_context, n) or []:
                code = m.get("code") or provider.generate_scorer_code(m)
                proposals.append({**m, "code": code})
    except Exception as e:
        log("evolve", f"LLM mutation skipped ({e}); using genome operators", "warn")
        return []

    members = []
    for i, m in enumerate(proposals[:n]):
        code = (m.get("code") or "").strip()
        if "def scorer" not in code:
            continue
        validation = validate_scorer_on_pairs(code)
        if not validation["valid"]:
            log("evolve", f"LLM proposal {i + 1} rejected: {validation['reason']}", "warn")
            continue
        members.append({
            "scorer_id": f"S_g{gen_idx}_llm{i + 1:02d}",
            "genome": None,
            "code": code,
            "hypothesis": m.get("hypothesis", "LLM-proposed mutation from failure context."),
            "lineage": f"llm_{m.get('lineage', 'mutation')}",
            "parents": [],
        })
    return members


def breed(parents, rng, gen_idx, gap_probes, n_offspring, provider=None, llm_context=None):
    """Produce the next generation's offspring: mutations of strong parents,
    crossovers, gap-biased immigrants, and optional LLM proposals."""
    offspring = []
    counter = 0

    def next_id():
        nonlocal counter
        counter += 1
        return f"S_g{gen_idx}_{counter:03d}"

    n_llm = min(3, n_offspring // 3) if provider is not None else 0
    offspring.extend(_llm_offspring(provider, llm_context, n_llm, gen_idx))

    genome_parents = [p for p in parents if p.get("genome")]
    while len(offspring) < n_offspring:
        roll = rng.random()
        if roll < 0.5 and genome_parents:
            parent = rng.choice(genome_parents[:max(3, len(genome_parents) // 2)])
            child = mutate_genome(parent["genome"], rng, gap_probes)
            offspring.append(_make_member(next_id(), child, "mutation", [parent["scorer_id"]]))
        elif roll < 0.8 and len(genome_parents) >= 2:
            pa, pb = rng.sample(genome_parents[:max(2, min(4, len(genome_parents)))], 2)
            child = crossover_genomes(pa["genome"], pb["genome"], rng)
            offspring.append(_make_member(next_id(), child, "crossover", [pa["scorer_id"], pb["scorer_id"]]))
        else:
            child = random_genome(rng, gap_probes)
            offspring.append(_make_member(next_id(), child, "immigrant", []))

    # Dedupe identical phenotypes (code strings) within the brood
    seen, unique = set(), []
    for m in offspring:
        if m["code"] not in seen:
            seen.add(m["code"])
            unique.append(m)
    return unique


# ─────────────────────────────────────────────────────────────────────
# CHECKPOINT STATE (step / resume support)
# ─────────────────────────────────────────────────────────────────────

def _rng_state_to_json(rng):
    st = rng.getstate()
    return [st[0], list(st[1]), st[2]]


def _rng_state_from_json(s):
    return (s[0], tuple(s[1]), s[2])


def _save_state(out_dir, state):
    save("evolve_state", state, out_dir)


def _load_state(out_dir):
    path = os.path.join(out_dir, "evolve_state.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────

def run_evolution(config, provider=None, resume=False, step=False):
    """Run the evolutionary scorer-discovery loop.

    Per-generation order (pairs and offspring integrate at the START of a
    generation so that externally produced proposals — LLM tool calls or
    file-exchange responses written between stepped invocations — are
    consumed, not skipped):

        merge adversarial pairs → add offspring → evaluate → select →
        failure packet → write proposal requests → checkpoint

    Args:
        config: pipeline config dict (goal, seed, n_generations, ...).
        provider: optional LLM provider (propose_scorers /
            propose_adversarial_pairs / prepare_requests hooks).
        resume: continue from the checkpoint in the output directory.
        step: execute exactly one generation, checkpoint, and return
            (result has complete=False until the final generation runs).
    """
    goal = config.get("goal", "persuasive")
    seed = int(config.get("seed", 7))
    n_generations = int(config.get("n_generations", EVOLVE_DEFAULTS["n_generations"]))
    pop_size = int(config.get("population_size", EVOLVE_DEFAULTS["population_size"]))
    n_adv = int(config.get("n_adv_per_gen", EVOLVE_DEFAULTS["n_adv_per_gen"]))
    n_cand = int(config.get("n_adv_candidates", EVOLVE_DEFAULTS["n_adv_candidates"]))
    patience = int(config.get("patience", EVOLVE_DEFAULTS["patience"]))
    n_elite = int(config.get("n_elite", EVOLVE_DEFAULTS["n_elite"]))

    rng = random.Random(seed)
    base_dir = resolve_output_directory()
    out_dir = os.path.join(base_dir, f"evolve_{goal}_seed{seed}")
    os.makedirs(out_dir, exist_ok=True)
    load_probes(get_namespace())

    state = _load_state(out_dir) if resume else None
    if state is not None:
        rng.setstate(_rng_state_from_json(state["rng_state"]))
        population = state["population"]
        suite = {"train": state["suite_train"], "test": state["suite_test"]}
        suite["all"] = suite["train"] + suite["test"]
        history = state["history"]
        prior_instructions = state["prior_instructions"]
        best_fitness, stale = state["best_fitness"], state["stale"]
        anchors = state["anchors"]
        pending = state.get("pending")
        start_gen = state["next_gen"]
        if start_gen >= n_generations:
            log("evolve", f"Run already complete ({start_gen} generations); "
                          "raise n_generations to extend", "warn")
            result_path = os.path.join(out_dir, "evolve_result.json")
            if os.path.exists(result_path):
                with open(result_path) as f:
                    return json.load(f)
            return {"success": True, "complete": True, "output_dir": out_dir,
                    "generations_run": len(history), "goal": goal, "seed": seed}
        log("evolve", f"Resuming at generation {start_gen} "
                      f"(population={len(population)}, pairs={len(suite['all'])})", "ok")
    else:
        log("evolve", f"Evolutionary loop: goal={goal} seed={seed} "
                      f"generations={n_generations} population={pop_size}", "ok")
        save("evolve_config", {**{k: config.get(k) for k in (
            "goal", "seed", "use_exa_search")}, "n_generations": n_generations,
            "population_size": pop_size, "n_adv_per_gen": n_adv,
            "n_adv_candidates": n_cand, "patience": patience}, out_dir)

        # 1. Anchors: social media posts (Exa or fallback bank)
        anchors = collect_social_anchors(config, out_dir)

        # 2. Base pair suite (trap taxonomy) + an initial anchor-grounded batch
        suite, _, _, _ = validate_and_split_pairs([dict(p) for p in ALL_PAIRS_R0], seed)
        initial = synthesize_candidate_pairs(anchors, {}, rng, n_adv * 2)
        for i, p in enumerate(initial[:n_adv]):
            p["pair_id"] = f"G0_{'T' if i % 3 == 2 else 'A'}{i + 1:02d}"
        suite, _, _, _, _ = merge_adversarial_pairs(suite, initial[:n_adv], seed, prefix_test="G0_T")
        log("evolve", f"Initial suite: {len(suite['train'])} train / {len(suite['test'])} heldout "
                      f"(incl. {min(n_adv, len(initial))} anchor-grounded pairs)", "ok")

        # 3. Seed population
        population = [_make_member(f"S_g0_{i + 1:03d}", random_genome(rng), "seed", [])
                      for i in range(pop_size)]
        history, prior_instructions = [], []
        best_fitness, stale = float("-inf"), 0
        pending, start_gen = None, 0

    summaries, pareto = [], []
    done = False
    gen = start_gen

    for gen in range(start_gen, n_generations):
        # ── Start of generation: integrate pending pairs and offspring ──
        if pending:
            context = pending["context"]
            gap_probes = pending["gap_probes"]
            frontier_code = pending["frontier_code"]
            candidates = synthesize_candidate_pairs(anchors, pending["gap_counts"], rng, n_cand)
            candidates += _llm_candidate_pairs(provider, context, anchors, rng, n_adv * 2)
            new_pairs = select_adversarial_pairs(candidates, frontier_code, gen, n_adv, rng)
            if new_pairs:
                suite, _, _, _, _ = merge_adversarial_pairs(
                    suite, new_pairs, seed + gen, prefix_test=f"G{gen}_T")
            save(f"gen{gen:02d}_new_pairs", new_pairs, out_dir)
            log("evolve", f"Gen {gen}: added {len(new_pairs)} adversarial pairs "
                          f"(frontier mean margin on them: "
                          f"{round(sum(p['frontier_margin_at_creation'] for p in new_pairs) / max(1, len(new_pairs)), 4)})",
                "ok")
            offspring = breed(population, rng, gen, gap_probes, pop_size,
                              provider=provider, llm_context=context)
            existing_codes = {m["code"] for m in population}
            population += [m for m in offspring if m["code"] not in existing_codes]
            pending = None

        # ── Evaluate everyone on the current suite ──
        eval_results, summaries, code_map = {}, [], {}
        hyps = [{"scorer_id": m["scorer_id"], "hypothesis": m["hypothesis"],
                 "lineage": m["lineage"]} for m in population]
        for m in population:
            sid = m["scorer_id"]
            code_map[sid] = m["code"]
            validation = validate_scorer_on_pairs(m["code"])
            rows = eval_scorer(sid, m["code"], suite["all"])
            eval_results[sid] = rows
            summaries.append(compute_summary(sid, rows, validation, hyps, gen))

        pareto = compute_pareto(summaries)
        ranked = sorted(summaries, key=fitness, reverse=True)
        gen_best = fitness(ranked[0]) if ranked else float("-inf")

        # ── Survivor selection: Pareto elites + best by fitness ──
        elite_ids = [s["scorer_id"] for s in pareto[:n_elite]]
        survivor_ids = list(elite_ids)
        for s in ranked:
            if len(survivor_ids) >= pop_size:
                break
            if s["scorer_id"] not in survivor_ids and fitness(s) > 0:
                survivor_ids.append(s["scorer_id"])
        by_id = {m["scorer_id"]: m for m in population}
        population = [by_id[sid] for sid in survivor_ids if sid in by_id]

        entry = {
            "generation": gen,
            "n_pairs": len(suite["all"]),
            "n_heldout": len(suite["test"]),
            "population_evaluated": len(summaries),
            "survivors": len(population),
            "pareto_size": len(pareto),
            "best_fitness": round(gen_best, 4),
            "best_scorer_id": ranked[0]["scorer_id"] if ranked else None,
            "best_test_accuracy": ranked[0]["test_accuracy"] if ranked else None,
            "best_test_margin": round(ranked[0]["test_margin"], 4) if ranked else None,
            "best_hypothesis": ranked[0]["hypothesis"] if ranked else None,
            "best_lineage": ranked[0]["lineage"] if ranked else None,
        }
        history.append(entry)
        save(f"gen{gen:02d}_summaries", summaries, out_dir)
        save(f"gen{gen:02d}_pareto", pareto, out_dir)
        save(f"gen{gen:02d}_population", [{k: m[k] for k in (
            "scorer_id", "hypothesis", "lineage", "parents", "code", "genome")}
            for m in population], out_dir)
        log("evolve", f"Gen {gen}: best={entry['best_scorer_id']} "
                      f"fitness={entry['best_fitness']} test_acc={entry['best_test_accuracy']} "
                      f"pareto={entry['pareto_size']} pairs={entry['n_pairs']}", "ok")

        # ── Termination checks ──
        if gen_best > best_fitness + 1e-6:
            best_fitness, stale = gen_best, 0
        else:
            stale += 1
        if gen == n_generations - 1:
            done = True
            break
        if stale >= patience:
            log("evolve", f"Early stop: no fitness improvement for {patience} generations", "warn")
            done = True
            break

        # ── Failure analysis → context for the NEXT generation ──
        fp = build_failure_packet(gen, summaries, eval_results, suite, pareto,
                                  code_map, prior_instructions)
        prior_instructions.extend(fp["mutation_instructions"])
        save(f"gen{gen:02d}_failure_packet", fp, out_dir)

        gap_counts = defaultdict(int)
        for t, c in fp["failed_pair_type_counts"].items():
            gap_counts[t] += c
        for t, c in fp["heldout_aggregate_only"]["heldout_failures_by_pair_type"].items():
            gap_counts[t] += c
        gap_probes = []
        for t, _ in sorted(gap_counts.items(), key=lambda x: -x[1]):
            gap_probes.extend(GAP_PROBES.get(t, []))

        frontier_code = {s["scorer_id"]: code_map[s["scorer_id"]] for s in pareto[:3]}
        if not frontier_code and ranked:
            frontier_code = {ranked[0]["scorer_id"]: code_map[ranked[0]["scorer_id"]]}
        context = {**build_mutation_context(goal, fp, pareto, code_map, summaries),
                   "generation": gen + 1}
        pending = {"context": context, "gap_probes": gap_probes,
                   "gap_counts": dict(gap_counts), "frontier_code": frontier_code}

        # Materialize proposal requests for file-exchange providers
        if provider is not None and hasattr(provider, "prepare_requests"):
            try:
                provider.prepare_requests(gen + 1, context,
                                          n_scorers=max(3, pop_size // 3),
                                          n_pairs=n_adv * 2)
            except Exception as e:
                log("evolve", f"prepare_requests failed ({e})", "warn")

        _save_state(out_dir, {
            "next_gen": gen + 1,
            "complete": False,
            "rng_state": _rng_state_to_json(rng),
            "population": population,
            "suite_train": suite["train"],
            "suite_test": suite["test"],
            "history": history,
            "prior_instructions": prior_instructions,
            "best_fitness": best_fitness,
            "stale": stale,
            "anchors": anchors,
            "pending": pending,
        })
        if step:
            break

    # ── Final artifacts ──
    ranked = sorted(summaries, key=fitness, reverse=True)
    by_id = {m["scorer_id"]: m for m in population}
    best = []
    for s in ranked[:5]:
        m = by_id.get(s["scorer_id"], {})
        best.append({
            "scorer_id": s["scorer_id"],
            "hypothesis": s["hypothesis"],
            "lineage": s["lineage"],
            "parents": m.get("parents", []),
            "code": m.get("code", ""),
            "fitness": round(fitness(s), 4),
            "test_accuracy": s["test_accuracy"],
            "test_margin": round(s["test_margin"], 4),
            "train_accuracy": s["train_accuracy"],
            "adversarial_accuracy": s["adversarial_accuracy"],
            "pair_type_accuracy": s["pair_type_accuracy"],
            "on_pareto_frontier": s["scorer_id"] in {p["scorer_id"] for p in pareto},
        })
    result = {
        "success": True,
        "complete": done,
        "goal": goal,
        "seed": seed,
        "generations_run": len(history),
        "final_pareto_size": len(pareto),
        "final_n_pairs": history[-1]["n_pairs"] if history else 0,
        "best_fitness": round(best_fitness, 4) if history else None,
        "output_dir": out_dir,
    }
    save("evolve_history", history, out_dir)
    save("evolve_best_scorers", best, out_dir)
    save("evolve_result", result, out_dir)
    if done:
        _save_state(out_dir, {**(_load_state(out_dir) or {}),
                              "next_gen": gen + 1, "complete": True})
        log("evolve", f"Done: {len(history)} generations, best fitness {result['best_fitness']}, "
                      f"artifacts in {out_dir}", "ok")
    else:
        log("evolve", f"Stepped generation {gen} complete; resume with --resume --step "
                      f"(state in {out_dir})", "ok")
    return result


# ─────────────────────────────────────────────────────────────────────
# BATCH EXPERIMENTS (scale assessment across seeds × goals)
# ─────────────────────────────────────────────────────────────────────

def _batch_worker(job_config):
    """Run one evolution job and distill the metrics that matter for scale
    assessment. Module-level so ProcessPoolExecutor can pickle it."""
    result = run_evolution(job_config)
    out = result["output_dir"]
    with open(os.path.join(out, "evolve_history.json")) as f:
        history = json.load(f)
    with open(os.path.join(out, "evolve_best_scorers.json")) as f:
        best = json.load(f)
    top = best[0] if best else {}
    return {
        "goal": job_config.get("goal"),
        "seed": job_config.get("seed"),
        "generations": len(history),
        "initial_best_fitness": history[0]["best_fitness"],
        "final_best_fitness": history[-1]["best_fitness"],
        "improvement": round(history[-1]["best_fitness"] - history[0]["best_fitness"], 4),
        "winner_scorer_id": top.get("scorer_id"),
        "winner_lineage": top.get("lineage"),
        "winner_is_evolved": top.get("lineage") not in ("seed", None),
        "winner_test_accuracy": top.get("test_accuracy"),
        "winner_hypothesis": top.get("hypothesis", ""),
        "final_pareto_size": history[-1]["pareto_size"],
        "n_pairs_final": history[-1]["n_pairs"],
        "n_heldout_final": history[-1]["n_heldout"],
        "output_dir": out,
    }


def run_evolve_batch(base_config, seeds, goals=None, workers=1):
    """Run evolution across seeds × goals and aggregate scale statistics:
    how often evolution improves on the seed population, how often an evolved
    (non-seed-lineage) scorer wins, and the size of the gains."""
    import statistics
    from collections import Counter

    goals = goals or [base_config.get("goal", "persuasive")]
    jobs = []
    for goal in goals:
        for s in range(int(seeds)):
            cfg = dict(base_config)
            cfg["goal"] = goal
            cfg["seed"] = s
            jobs.append(cfg)

    log("evolve-batch", f"Running {len(jobs)} jobs "
                        f"({len(goals)} goals × {seeds} seeds, workers={workers})", "ok")
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as ex:
            records = list(ex.map(_batch_worker, jobs))
    else:
        records = [_batch_worker(j) for j in jobs]

    improvements = [r["improvement"] for r in records]
    accuracies = [r["winner_test_accuracy"] for r in records if r["winner_test_accuracy"] is not None]
    summary = {
        "runs": len(records),
        "goals": goals,
        "seeds_per_goal": int(seeds),
        "generations_per_run": records[0]["generations"] if records else 0,
        "improved_rate": round(sum(1 for r in records if r["improvement"] > 1e-6) / len(records), 3),
        "evolved_winner_rate": round(sum(1 for r in records if r["winner_is_evolved"]) / len(records), 3),
        "mean_improvement": round(statistics.mean(improvements), 4),
        "median_improvement": round(statistics.median(improvements), 4),
        "max_improvement": round(max(improvements), 4),
        "min_improvement": round(min(improvements), 4),
        "mean_winner_test_accuracy": round(statistics.mean(accuracies), 4) if accuracies else None,
        "min_winner_test_accuracy": round(min(accuracies), 4) if accuracies else None,
        "winner_lineage_histogram": dict(Counter(r["winner_lineage"] for r in records)),
        "mean_final_pareto_size": round(statistics.mean([r["final_pareto_size"] for r in records]), 2),
        "mean_final_pairs": round(statistics.mean([r["n_pairs_final"] for r in records]), 1),
        "per_run": records,
    }
    base_dir = resolve_output_directory()
    save("evolve_batch_summary", summary, base_dir)
    log("evolve-batch", f"Improved in {summary['improved_rate']:.0%} of runs; "
                        f"evolved scorer wins in {summary['evolved_winner_rate']:.0%}; "
                        f"mean fitness gain {summary['mean_improvement']}", "ok")
    return summary
