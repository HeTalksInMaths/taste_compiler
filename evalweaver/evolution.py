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


def _llm_offspring(provider, failure_packet, n, gen_idx):
    """Optional live LLM mutation via the Bedrock provider. Any failure falls
    back silently to the deterministic genome operators."""
    if provider is None or n <= 0:
        return []
    members = []
    try:
        mutations = provider.generate_mutations(failure_packet, n) or []
        for i, m in enumerate(mutations[:n]):
            code = m.get("code") or provider.generate_scorer_code(m)
            if not code or "def scorer" not in code:
                continue
            members.append({
                "scorer_id": f"S_g{gen_idx}_llm{i + 1:02d}",
                "genome": None,
                "code": code,
                "hypothesis": m.get("hypothesis", "LLM-proposed mutation from failure packet."),
                "lineage": "llm_mutation",
                "parents": [],
            })
    except Exception as e:
        log("evolve", f"LLM mutation skipped ({e}); using genome operators", "warn")
    return members


def breed(parents, rng, gen_idx, gap_probes, n_offspring, provider=None, failure_packet=None):
    """Produce the next generation's offspring: mutations of strong parents,
    crossovers, gap-biased immigrants, and optional LLM proposals."""
    offspring = []
    counter = 0

    def next_id():
        nonlocal counter
        counter += 1
        return f"S_g{gen_idx}_{counter:03d}"

    n_llm = min(2, n_offspring // 4) if provider is not None else 0
    offspring.extend(_llm_offspring(provider, failure_packet, n_llm, gen_idx))

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
# MAIN LOOP
# ─────────────────────────────────────────────────────────────────────

def run_evolution(config, provider=None):
    """Run the evolutionary scorer-discovery loop. Returns a result dict."""
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

    history = []
    prior_instructions = []
    best_fitness, stale = float("-inf"), 0
    summaries, pareto = [], []

    for gen in range(n_generations):
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
            break
        if stale >= patience:
            log("evolve", f"Early stop: no fitness improvement for {patience} generations", "warn")
            break

        # ── Failure analysis on the frontier ──
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

        # ── Adversarial pair generation exploiting frontier coverage gaps ──
        frontier_code = {s["scorer_id"]: code_map[s["scorer_id"]] for s in pareto[:3]}
        if not frontier_code and ranked:
            frontier_code = {ranked[0]["scorer_id"]: code_map[ranked[0]["scorer_id"]]}
        candidates = synthesize_candidate_pairs(anchors, dict(gap_counts), rng, n_cand)
        new_pairs = select_adversarial_pairs(candidates, frontier_code, gen + 1, n_adv, rng)
        if new_pairs:
            suite, _, _, _, _ = merge_adversarial_pairs(
                suite, new_pairs, seed + gen + 1, prefix_test=f"G{gen + 1}_T")
        save(f"gen{gen:02d}_new_pairs", new_pairs, out_dir)
        log("evolve", f"Gen {gen}: added {len(new_pairs)} adversarial pairs "
                      f"(frontier mean margin on them: "
                      f"{round(sum(p['frontier_margin_at_creation'] for p in new_pairs) / max(1, len(new_pairs)), 4)})",
            "ok")

        # ── Breed next generation ──
        ranked_members = [by_id[s["scorer_id"]] for s in ranked if s["scorer_id"] in by_id]
        offspring = breed(ranked_members or population, rng, gen + 1, gap_probes,
                          pop_size, provider=provider, failure_packet=fp)
        existing_codes = {m["code"] for m in population}
        population += [m for m in offspring if m["code"] not in existing_codes]

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
        "goal": goal,
        "seed": seed,
        "generations_run": len(history),
        "final_pareto_size": len(pareto),
        "final_n_pairs": history[-1]["n_pairs"] if history else 0,
        "best_fitness": round(best_fitness, 4),
        "output_dir": out_dir,
    }
    save("evolve_history", history, out_dir)
    save("evolve_best_scorers", best, out_dir)
    save("evolve_result", result, out_dir)
    log("evolve", f"Done: {len(history)} generations, best fitness {result['best_fitness']}, "
                  f"artifacts in {out_dir}", "ok")
    return result
