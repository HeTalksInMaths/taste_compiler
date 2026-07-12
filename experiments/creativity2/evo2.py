"""EVO2 — deterministic orchestrator for agentic scorer discovery.

See DESIGN.md. Commands:
    python evo2.py init                 # split evals, build+eval seed population
    python evo2.py prepare             # eval population, select, write gen contexts
    python evo2.py apply-scorers F.json
    python evo2.py apply-pairs   F.json
    python evo2.py report

Fitness = SEP = mean(s_pos) - mean(s_neg) on TRAIN, both distributions reported.
All scorers return floats in [0,1] (hard-validated). Agents never see heldout.
"""

import ast
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CR1 = os.path.abspath(os.path.join(HERE, "..", "creativity"))
sys.path.insert(0, CR1)
sys.path.insert(0, HERE)

from wordfreq import zipf_frequency, top_n_list, word_frequency  # noqa: E402

STATE = os.path.join(HERE, os.environ.get("EVO2_STATE", "state.json"))
PREFIX = os.environ.get("EVO2_PREFIX", "")
ADV_KEEP = int(os.environ.get("EVO2_ADV_KEEP", "6"))
POP_MAX, N_FIT_KEEP, N_NOVEL_KEEP = 10, 6, 2
NOVELTY_R_MAX = 0.6
LEAK_ZIPF, LEAK_MAX_HITS, MAX_CONTENT_TOKENS = 3.5, 3, 40


# ── seed scorers (normalized [0,1], reference-calibrated — no eval fitting) ──

SEED_CODE = '''
"""Seed scorers: the session's discovered real metrics, normalized to [0,1].
Reference scales come from wordfreq's own lexicon (token-weighted surprisal
mean/SD), never from eval pairs."""
import math
import re
import numpy as np
from wordfreq import word_frequency, top_n_list
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_W = re.compile(r"[a-zA-Z']+")
STOP = set(("a an the and or but if then else of to in on at by for with from as is are was were "
    "be been being it its this that these those i you he she we they me him her us them my your "
    "his their our not no so do does did have has had will would can could should may might must "
    "about into over under out up down off than too very just also").split())

def _toks(s):
    return [t for t in _W.findall((s or "").lower())]

def _content(s):
    return [t for t in _toks(s) if t not in STOP and len(t) > 1]

def _ref_stats():
    """Token-weighted mean/SD of word surprisal under the unigram distribution,
    from wordfreq's top-50k lexicon. A fixed reference, independent of any eval."""
    words = top_n_list("en", 50000)
    ps = np.array([word_frequency(w, "en") for w in words])
    ps = ps[ps > 0]
    ps = ps / ps.sum()
    sur = -np.log2(ps)
    mu = float((ps * sur).sum())
    sd = float(math.sqrt((ps * (sur - mu) ** 2).sum()))
    return mu, sd

_MU, _SD = _ref_stats()

def _mean_surprisal(text):
    toks = _content(text)
    if not toks:
        return _MU
    vals = []
    for w in toks:
        p = word_frequency(w, "en")
        vals.append(-math.log2(p) if p > 0 else 24.0)
    return float(np.mean(vals))

def lex_rarity_norm(text, anchor):
    """Lexical novelty: logistic of text mean surprisal vs the lexicon reference."""
    return 1.0 / (1.0 + math.exp(-(_mean_surprisal(text) - _MU) / _SD))

def combinational_novelty(text, anchor):
    """Word-bigram/trigram TF-IDF divergence from anchor (already in [0,1])."""
    if not (text and anchor):
        return 0.0
    try:
        v = TfidfVectorizer(analyzer="word", ngram_range=(2, 3), token_pattern=r"[a-zA-Z']+")
        m = v.fit_transform([anchor, text])
        return float(max(0.0, min(1.0, 1.0 - cosine_similarity(m[0], m[1])[0, 0])))
    except ValueError:
        return 0.0

def appropriateness_gate(text, anchor):
    """Inverted-U: 1 while the rewrite's surprisal stays within one lexicon-SD
    above its anchor; harmonic decay on the quadratic overshoot beyond."""
    excess = _mean_surprisal(text) - _mean_surprisal(anchor) - _SD
    if excess <= 0:
        return 1.0
    return 1.0 / (1.0 + excess * excess)

def conjunctive_creativity(text, anchor):
    """Novelty x appropriateness, multiplicative (conjunctive by construction)."""
    nov = 0.5 * lex_rarity_norm(text, anchor) + 0.5 * combinational_novelty(text, anchor)
    return nov * appropriateness_gate(text, anchor)

METRICS = {
    "lex_rarity_norm": lex_rarity_norm,
    "combinational_novelty": combinational_novelty,
    "appropriateness_gate": appropriateness_gate,
    "conjunctive_creativity": conjunctive_creativity,
}
'''

SEED_META = {
    "lex_rarity_norm": ("seed", "lexical_rarity/surprisal", "token surprisal vs lexicon reference (logistic)"),
    "combinational_novelty": ("seed", "semantic_distance(collocational)", "word n-gram TF-IDF divergence from anchor"),
    "appropriateness_gate": ("seed", "appropriateness(inverted-U)", "Wundt-curve overshoot decay"),
    "conjunctive_creativity": ("seed", "novelty*appropriateness", "conjunctive product of the above"),
}


# ── state ──────────────────────────────────────────────────────────────

def load_state():
    return json.load(open(STATE))


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def compile_metrics(code, wanted=None):
    ns = {"__name__": "evo2_scorer"}
    exec(code, ns)
    mets = ns["METRICS"]
    return {k: v for k, v in mets.items() if (wanted is None or k in wanted)}


# ── evaluation / fitness ───────────────────────────────────────────────

def score_pairs(fn, pairs):
    rows = []
    for p in pairs:
        sp = float(fn(p["more_creative"], p["anchor"]))
        sn = float(fn(p["less_creative"], p["anchor"]))
        rows.append((p["pair_id"], sp, sn))
    return rows


def stats(rows):
    sp = np.array([r[1] for r in rows]); sn = np.array([r[2] for r in rows])
    m = sp - sn
    pooled = math.sqrt((sp.var() + sn.var()) / 2) or 1e-9
    return {"SEP": float(sp.mean() - sn.mean()), "acc": float((m > 1e-12).mean()),
            "mean_pos": float(sp.mean()), "sd_pos": float(sp.std()),
            "mean_neg": float(sn.mean()), "sd_neg": float(sn.std()),
            "effect_d": float((sp.mean() - sn.mean()) / pooled),
            "worst_margin": float(m.min()), "sd_margin": float(m.std())}


def validate(fn, pairs):
    vals = []
    for p in pairs[:6]:
        for t in (p["more_creative"], p["less_creative"], p["anchor"]):
            a = float(fn(t, p["anchor"])); b = float(fn(t, p["anchor"]))
            if a != b:
                return False, "non-deterministic"
            if not (0.0 <= a <= 1.0):
                return False, f"out of [0,1]: {a:.3f}"
            vals.append(a)
    allv = [v for p in pairs for v in (fn(p["more_creative"], p["anchor"]), fn(p["less_creative"], p["anchor"]))]
    if any(not (0.0 <= v <= 1.0) for v in allv):
        return False, "out of [0,1] on eval"
    if max(allv) - min(allv) < 0.05:
        return False, "spread<0.05 (near-constant)"
    return True, "ok"


# ── leakage check (AST literals vs train pair text) ────────────────────

def leakage_check(code, train_pairs):
    train_text = " ".join(t.lower() for p in train_pairs
                          for t in (p["anchor"], p["more_creative"], p["less_creative"]))
    train_words = set(re.findall(r"[a-z']+", train_text))
    # Only scan literals that can encode WORD LISTS: elements of list/set/tuple
    # displays and strings that are the receiver of .split(). Docstrings, regex
    # patterns, and message strings are not word lists and are exempt.
    literals = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
            for e in node.elts:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    literals.append(e.value)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == "split"
              and isinstance(node.func.value, ast.Constant)
              and isinstance(node.func.value.value, str)):
            literals.append(node.func.value.value)
    tokens = set()
    for s in literals:
        tokens |= {t for t in re.findall(r"[a-zA-Z']{3,}", s.lower())}
    content = {t for t in tokens if zipf_frequency(t, "en") < 5.0}
    lifted = {t for t in content if zipf_frequency(t, "en") < LEAK_ZIPF and t in train_words}
    if len(lifted) >= LEAK_MAX_HITS:
        return False, f"lifted rare train tokens: {sorted(lifted)[:6]}"
    if len(content) > MAX_CONTENT_TOKENS:
        return False, f"hardcoded content wordlist too large ({len(content)}>{MAX_CONTENT_TOKENS})"
    return True, f"clean ({len(content)} content tokens, {len(lifted)} lifted)"


# ── behavioral novelty ─────────────────────────────────────────────────

def margin_vector(rows):
    return np.array([r[1] - r[2] for r in rows])


def max_abs_corr(vec, others):
    best = 0.0
    for o in others:
        if np.std(vec) < 1e-12 or np.std(o) < 1e-12:
            continue
        best = max(best, abs(float(np.corrcoef(vec, o)[0, 1])))
    return best


# ── commands ───────────────────────────────────────────────────────────

def cmd_init():
    sets = [("O", json.load(open(os.path.join(CR1, "eval_pairs.json")))),
            ("A1", json.load(open(os.path.join(CR1, "adversarial_pairs.json")))),
            ("A2", json.load(open(os.path.join(CR1, "adversarial_pairs_r2.json"))))]
    train, heldout, core = [], [], []
    for tag, pairs in sets:
        for i, p in enumerate(sorted(pairs, key=lambda x: x["pair_id"])):
            q = {k: p[k] for k in ("pair_id", "anchor", "more_creative", "less_creative")}
            q["origin"] = tag
            if i % 3 == 2:
                heldout.append(q)
                if tag == "O":
                    core.append(q["pair_id"])
            else:
                train.append(q)
    pop = [{"id": name, "lineage": SEED_META[name][0], "causal_node": SEED_META[name][1],
            "mechanism": SEED_META[name][2], "gen": 0, "code": SEED_CODE, "metric_key": name}
           for name in SEED_META]
    save_state({"gen": 0, "train": train, "heldout": heldout, "core_ids": core,
                "population": pop, "history": [], "trap_axes_used":
                ["cliche/idiom decoupling (adv-1)", "purple prose: novelty without appropriateness (adv-2)"]})
    print(f"init: train={len(train)} heldout={len(heldout)} (core={len(core)}), seeds={len(pop)}")


def evaluate_population(s):
    rows_by_id, st_by_id = {}, {}
    for m in s["population"]:
        fn = compile_metrics(m["code"], [m["metric_key"]])[m["metric_key"]]
        rows = score_pairs(fn, s["train"])
        rows_by_id[m["id"]] = rows
        st = stats(rows)
        st["heldout_SEP"] = stats(score_pairs(fn, s["heldout"]))["SEP"]
        st["core_SEP"] = stats(score_pairs(fn, [p for p in s["heldout"] if p["pair_id"] in s["core_ids"]]))["SEP"]
        st_by_id[m["id"]] = st
    return rows_by_id, st_by_id


def cmd_prepare():
    s = load_state()
    rows_by_id, st_by_id = evaluate_population(s)
    ranked = sorted(s["population"], key=lambda m: (st_by_id[m["id"]]["SEP"],
                    st_by_id[m["id"]]["acc"], -st_by_id[m["id"]]["sd_margin"]), reverse=True)

    # selection: top-6 fitness + 2 novelty-niche + newest
    kept = ranked[:N_FIT_KEEP]
    kept_ids = {m["id"] for m in kept}
    rest = [m for m in ranked[N_FIT_KEEP:]]
    rest.sort(key=lambda m: max_abs_corr(margin_vector(rows_by_id[m["id"]]),
              [margin_vector(rows_by_id[k]) for k in kept_ids]))
    for m in rest[:N_NOVEL_KEEP]:
        kept.append(m); kept_ids.add(m["id"])
    for m in sorted(rest, key=lambda x: -x.get("gen", 0)):
        if len(kept) >= POP_MAX:
            break
        if m["id"] not in kept_ids:
            kept.append(m); kept_ids.add(m["id"])
    s["population"] = kept
    champ = ranked[0]
    cst = st_by_id[champ["id"]]

    print(f"\n=== GEN {s['gen']} | train={len(s['train'])} heldout={len(s['heldout'])} ===")
    print(f"{'id':>26} {'gen':>3} {'node':>28} {'SEP':>7} {'acc':>5} {'pos':>10} {'neg':>10} {'hSEP':>6}")
    for m in ranked:
        st = st_by_id[m["id"]]
        print(f"{m['id']:>26} {m.get('gen',0):>3} {m['causal_node'][:28]:>28} {st['SEP']:>7.3f} "
              f"{st['acc']:>5.2f} {st['mean_pos']:.2f}±{st['sd_pos']:.2f} "
              f"{st['mean_neg']:.2f}±{st['sd_neg']:.2f} {st['heldout_SEP']:>6.3f}")

    # correlation matrix (train margins) for the engineer context
    ids = [m["id"] for m in s["population"]]
    corr = {}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            va, vb = margin_vector(rows_by_id[a]), margin_vector(rows_by_id[b])
            if np.std(va) > 1e-12 and np.std(vb) > 1e-12:
                corr[f"{a}|{b}"] = round(float(np.corrcoef(va, vb)[0, 1]), 2)

    champ_fn = compile_metrics(champ["code"], [champ["metric_key"]])[champ["metric_key"]]
    fails = []
    for p in s["train"]:
        sp = champ_fn(p["more_creative"], p["anchor"]); sn = champ_fn(p["less_creative"], p["anchor"])
        if sp <= sn + 1e-12:
            fails.append({**{k: p[k] for k in ("pair_id", "anchor", "more_creative", "less_creative")},
                          "champion_scored_more": round(sp, 3), "champion_scored_less": round(sn, 3)})
    causal = json.load(open(os.path.join(CR1, "causal_graph.json")))
    covered = sorted({m["causal_node"] for m in s["population"]})
    all_nodes = [n["id"] for n in causal["nodes"] if n.get("text_observable")]
    uncovered = [n for n in all_nodes if not any(n.split("(")[0] in c for c in covered)]

    eng_ctx = {
        "goal": "Score creativity of a 2-sentence rewrite vs its anchor. scorer(text, anchor) -> float in [0,1]. Correct on a pair when score(more_creative) > score(less_creative).",
        "fitness": "SEP = mean(score over positives) - mean(score over negatives) on train; both distributions reported; selection (SEP, acc, -sd_margin).",
        "contract": ("Complete importable Python module exposing METRICS={name:fn}. Deterministic, values ALWAYS in [0,1] "
                     "via principled squashing calibrated on REFERENCE stats (e.g. wordfreq lexicon), never on eval pairs. "
                     "Allowed imports: wordfreq, numpy, scipy, sklearn, re, math, collections, statistics. Downloads BLOCKED. "
                     "NO hand-typed content word lists (max 40 content tokens in literals; >=3 rare train-text tokens = auto-reject)."),
        "novelty_criteria": ("Accepted as NOVEL only if: (1) |pearson r| of per-pair margin vector vs EVERY incumbent < 0.6; "
                             "(2) it measures an uncovered/weakly-covered causal node with a real named mechanism; (3) leakage-clean."),
        "causal_graph": {"nodes": [{"id": n["id"], "definition": n.get("definition", "")}
                                    for n in causal["nodes"]], "edges": causal["edges"],
                         "load_bearing_paths": causal.get("load_bearing_paths", [])},
        "node_coverage": {"covered_by_population": covered, "uncovered_text_observable": uncovered},
        "population_stats": [{"id": m["id"], "gen": m.get("gen", 0), "causal_node": m["causal_node"],
                              "mechanism": m["mechanism"], **{k: round(v, 3) for k, v in st_by_id[m["id"]].items()}}
                             for m in ranked],
        "margin_correlations": corr,
        "champion": {"id": champ["id"], "code": champ["code"], "metric_key": champ["metric_key"],
                     "train_failures": fails[:8]},
        "n_scorers_wanted": 3,
        "output_schema": '[{"name": str, "causal_node": str, "mechanism": "named theory/paper", "reasoning": str, "code": "full module source"}] x3',
    }
    json.dump(eng_ctx, open(os.path.join(HERE, f"gen{s['gen']+1}_engineer_context.json"), "w"), indent=1)

    red_ctx = {
        "goal": "Write adversarial pairs (anchor + more_creative + less_creative, 2 sentences each, same factual content) that DECOUPLE the champion scorer's measured axis from true creativity.",
        "champion": {"axis": f"{champ['causal_node']} — {champ['mechanism']}", "code": champ["code"]},
        "trap_axes_already_used": s["trap_axes_used"],
        "requirement": ("Pick a NEW decoupling axis not in trap_axes_already_used. Include BOTH directions: "
                        "champion-signal-high-but-genuinely-less-creative negatives AND champion-signal-low-but-genuinely-more-creative positives. "
                        "Subtle, natural English; a thoughtful human must still rank more_creative > less_creative on freshness. "
                        "8 candidates; ids R3_01..R3_08."),
        "causal_graph_nodes": [n["id"] for n in causal["nodes"]],
        "output_schema": '[{"pair_id": str, "trap": str, "anchor": str, "more_creative": str, "less_creative": str, "design_note": str, "predicted_champion_behavior": str}] x8',
    }
    json.dump(red_ctx, open(os.path.join(HERE, f"{PREFIX}gen{s['gen']+1}_redteam_context.json"), "w"), indent=1)

    s["history"].append({"gen": s["gen"], "champion": champ["id"],
                         "champion_stats": {k: round(v, 4) for k, v in cst.items()},
                         "n_train": len(s["train"]), "n_heldout": len(s["heldout"]),
                         "population": [{"id": m["id"], "SEP": round(st_by_id[m["id"]]["SEP"], 3)} for m in ranked]})
    save_state(s)
    print(f"\nchampion: {champ['id']} SEP={cst['SEP']:.3f} heldout_SEP={cst['heldout_SEP']:.3f} core_SEP={cst['core_SEP']:.3f}")
    print(f"uncovered causal nodes: {uncovered}")
    print(f"wrote {PREFIX}gen{s['gen']+1}_engineer_context.json and {PREFIX}gen{s['gen']+1}_redteam_context.json")


def cmd_apply_scorers(path):
    s = load_state()
    props = json.load(open(path))
    gen = s["gen"] + 1
    incumbent_vecs = []
    for m in s["population"]:
        fn = compile_metrics(m["code"], [m["metric_key"]])[m["metric_key"]]
        incumbent_vecs.append(margin_vector(score_pairs(fn, s["train"])))
    med = float(np.median([stats(score_pairs(compile_metrics(m["code"], [m["metric_key"]])[m["metric_key"]],
                s["train"]))["SEP"] for m in s["population"]]))
    for i, p in enumerate(props):
        sid = f"S_g{gen}_{i+1:02d}_{p['name'][:24]}"
        try:
            mets = compile_metrics(p["code"])
        except Exception as e:
            print(f"  reject {sid}: import error: {e}"); continue
        if len(mets) != 1:
            key = list(mets)[0]
        else:
            key = list(mets)[0]
        fn = mets[key]
        ok, why = validate(fn, s["train"])
        if not ok:
            print(f"  reject {sid}: {why}"); continue
        ok, why = leakage_check(p["code"], s["train"])
        if not ok:
            print(f"  reject {sid}: LEAKAGE: {why}"); continue
        rows = score_pairs(fn, s["train"]); st = stats(rows)
        r = max_abs_corr(margin_vector(rows), incumbent_vecs)
        novel = r < NOVELTY_R_MAX
        accept = st["SEP"] > med or (novel and st["SEP"] > 0)
        tag = "NOVEL" if novel else f"corr={r:.2f}"
        if not accept:
            print(f"  reject {sid}: SEP={st['SEP']:.3f} <= median {med:.3f} and not novel ({tag})"); continue
        s["population"].append({"id": sid, "lineage": f"llm_gen{gen}", "gen": gen,
                                "causal_node": p.get("causal_node", "?"), "mechanism": p.get("mechanism", "?"),
                                "code": p["code"], "metric_key": key, "novel": bool(novel)})
        incumbent_vecs.append(margin_vector(rows))
        print(f"  accept {sid}: SEP={st['SEP']:.3f} acc={st['acc']:.2f} pos={st['mean_pos']:.2f} neg={st['mean_neg']:.2f} [{tag}] ({why})")
    save_state(s)


def cmd_apply_pairs(path):
    s = load_state()
    cands = json.load(open(path))
    champ_id = s["history"][-1]["champion"]
    champ = next(m for m in s["population"] if m["id"] == champ_id)
    fn = compile_metrics(champ["code"], [champ["metric_key"]])[champ["metric_key"]]
    scored = []
    for p in cands:
        if not all(p.get(k) for k in ("pair_id", "anchor", "more_creative", "less_creative")):
            continue
        if len(p["more_creative"].split()) < 8 or len(p["less_creative"].split()) < 8:
            continue
        m = fn(p["more_creative"], p["anchor"]) - fn(p["less_creative"], p["anchor"])
        scored.append((m, p))
    scored.sort(key=lambda x: x[0])
    kept = scored[:ADV_KEEP]
    axis = kept[0][1].get("trap", "unknown") if kept else "none"
    for i, (m, p) in enumerate(kept):
        q = {"pair_id": p["pair_id"], "anchor": p["anchor"], "more_creative": p["more_creative"],
             "less_creative": p["less_creative"], "origin": f"R{s['gen']+1}", "trap": p.get("trap", "")}
        (s["heldout"] if i % 3 == 2 else s["train"]).append(q)
    s["trap_axes_used"].append(axis)
    s["gen"] += 1
    save_state(s)
    margins = [round(m, 3) for m, _ in kept]
    print(f"kept {len(kept)}/{len(cands)} hardest (champion margins {margins}); axis='{axis}'; advanced to gen {s['gen']}")


def cmd_report():
    s = load_state()
    print(f"\n=== EVO2 trajectory (train SEP fitness; heldout never shown to agents) ===")
    for h in s["history"]:
        c = h["champion_stats"]
        print(f"gen {h['gen']}: train={h['n_train']} heldout={h['n_heldout']} champ={h['champion']} "
              f"SEP={c['SEP']:.3f} acc={c['acc']:.2f} pos={c['mean_pos']:.2f} neg={c['mean_neg']:.2f} "
              f"heldoutSEP={c['heldout_SEP']:.3f} coreSEP={c['core_SEP']:.3f}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"init": cmd_init, "prepare": cmd_prepare, "report": cmd_report,
     "apply-scorers": lambda: cmd_apply_scorers(sys.argv[2]),
     "apply-pairs": lambda: cmd_apply_pairs(sys.argv[2])}[cmd]()
