"""LLM-mutation evolution harness (Sonnet writes the new scorers).

The mutation operator is an LLM: each generation Sonnet reads the summary stats
of the previous run (per-scorer separation, margins, and the pairs the current
best scorer fails) and WRITES new self-contained scorer functions. The harness
only validates/evaluates them and grows the adversarial set.

State files (in this dir):
  population.json   list of {scorer_id, lineage, gen_added, hypothesis, code}
  eval_state.json   {gen, used_adv: [pair_ids]}
  history.json      per-generation summary records

Commands:
  init                     seed population with the 5 scorers, empty adversarial
  prepare                  evaluate population on current eval set, record best,
                           grow adversarial (pairs the best separates worst),
                           write gen{gen}_context.json for Sonnet
  apply <sonnet.json>      validate+evaluate Sonnet's new scorers, add to
                           population, advance the generation counter
  report                   print the full separation trajectory
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from evalweaver.runner import py_run_scorer  # noqa: E402

ADV_PER_GEN = 3
POP = os.path.join(HERE, "population.json")
STATE = os.path.join(HERE, "eval_state.json")
HIST = os.path.join(HERE, "history.json")


def load(name):
    return json.load(open(os.path.join(HERE, name)))


def jload(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def jsave(path, obj):
    json.dump(obj, open(path, "w"), indent=1)


def sep(code, pairs):
    """(accuracy more>less, mean margin) for a scorer on pairs; None if it errors."""
    if not pairs:
        return None, None
    c = 0
    margin = 0.0
    for p in pairs:
        m = py_run_scorer(code, p["more_creative"], p["anchor"])
        l = py_run_scorer(code, p["less_creative"], p["anchor"])
        if not (m["ok"] and l["ok"]):
            return None, None
        if m["value"] > l["value"] + 1e-9:
            c += 1
        margin += (m["value"] - l["value"])
    return c / len(pairs), margin / len(pairs)


def eval_set(state, orig, adv_pool):
    adv_by_id = {p["pair_id"]: p for p in adv_pool}
    used = [adv_by_id[i] for i in state["used_adv"] if i in adv_by_id]
    return orig, used


def cmd_init():
    scorers = load("scorers.json")
    pop = [{"scorer_id": s["scorer_id"], "lineage": "initial", "gen_added": 0,
            "hypothesis": s["hypothesis"][:200], "code": s["code"]} for s in scorers]
    jsave(POP, pop)
    jsave(STATE, {"gen": 0, "used_adv": []})
    jsave(HIST, [])
    print(f"init: {len(pop)} scorers, gen 0, adversarial set empty")


def cmd_prepare():
    pop = jload(POP, [])
    state = jload(STATE, {"gen": 0, "used_adv": []})
    hist = jload(HIST, [])
    orig = load("eval_pairs.json")
    adv_pool = load("adversarial_pairs.json")
    gen = state["gen"]
    o_pairs, a_pairs = eval_set(state, orig, adv_pool)
    cur = o_pairs + a_pairs

    rows = []
    for m in pop:
        ao, mo = sep(m["code"], o_pairs)
        aa, ma = sep(m["code"], a_pairs) if a_pairs else (None, None)
        ac, mc = sep(m["code"], cur)
        rows.append({"scorer_id": m["scorer_id"], "lineage": m["lineage"],
                     "acc_all": ac, "margin_all": mc,
                     "acc_orig": ao, "acc_adv": aa})
    rows_ok = [r for r in rows if r["acc_all"] is not None]
    rows_ok.sort(key=lambda r: (r["acc_all"], r["margin_all"]), reverse=True)
    best = rows_ok[0]
    best_code = next(m["code"] for m in pop if m["scorer_id"] == best["scorer_id"])

    print(f"\n=== GEN {gen}: {len(pop)} scorers on {len(cur)} pairs "
          f"({len(o_pairs)} orig + {len(a_pairs)} adversarial) ===")
    print(f"{'scorer':>30} {'lineage':>14} {'acc_all':>7} {'acc_orig':>8} {'acc_adv':>7}")
    for r in rows_ok:
        aadv = f"{r['acc_adv']:.3f}" if r["acc_adv"] is not None else "  -"
        print(f"{r['scorer_id']:>30} {r['lineage']:>14} {r['acc_all']:>7.3f} "
              f"{r['acc_orig']:>8.3f} {aadv:>7}")

    hist.append({"gen": gen, "n_pairs": len(cur), "n_orig": len(o_pairs), "n_adv": len(a_pairs),
                 "n_scorers": len(pop), "best_id": best["scorer_id"], "best_lineage": best["lineage"],
                 "best_acc_all": round(best["acc_all"], 3), "best_acc_orig": round(best["acc_orig"], 3),
                 "best_acc_adv": (round(best["acc_adv"], 3) if best["acc_adv"] is not None else None),
                 "all_scores": [{"id": r["scorer_id"], "lineage": r["lineage"],
                                 "acc_all": round(r["acc_all"], 3)} for r in rows_ok]})
    jsave(HIST, hist)

    # grow adversarial: add pairs the current best separates worst
    remaining = [p for p in adv_pool if p["pair_id"] not in state["used_adv"]]
    added = []
    if remaining:
        def margin(p):
            m = py_run_scorer(best_code, p["more_creative"], p["anchor"])["value"]
            l = py_run_scorer(best_code, p["less_creative"], p["anchor"])["value"]
            return m - l
        remaining.sort(key=margin)
        added = remaining[:ADV_PER_GEN]
        state["used_adv"] += [p["pair_id"] for p in added]
        jsave(STATE, state)

    # failed pairs for the best scorer, prioritizing the newly added adversarial
    fail_pool = added + a_pairs + o_pairs
    fails = []
    for p in fail_pool:
        mv = py_run_scorer(best_code, p["more_creative"], p["anchor"])["value"]
        lv = py_run_scorer(best_code, p["less_creative"], p["anchor"])["value"]
        if mv <= lv + 1e-9:
            fails.append({"pair_id": p["pair_id"], "anchor": p["anchor"],
                          "more_creative": p["more_creative"], "less_creative": p["less_creative"],
                          "best_scored_more": round(mv, 3), "best_scored_less": round(lv, 3)})
        if len(fails) >= 6:
            break

    context = {
        "goal": "Score how creative a 2-sentence text is, higher = more creative. A scorer is CORRECT on a pair when it gives more_creative a higher score than less_creative (same factual content, only freshness differs).",
        "generation": gen + 1,
        "summary_stats": rows_ok,
        "best_scorer": {"scorer_id": best["scorer_id"], "code": best_code,
                        "acc_all": best["acc_all"]},
        "pairs_the_best_scorer_fails": fails,
        "n_new_scorers_wanted": 3,
        "contract": (
            "Write self-contained functions: def scorer(text, anchor, params) -> float in [0.0,1.0]. "
            "The namespace already provides: re, math, collections, string, statistics, unicodedata, and _clamp(x). "
            "NO import statements. Deterministic. Non-constant across texts. Embedded Python word lists/sets are allowed and encouraged. "
            "Return _clamp(...) of your expression. anchor is the original statement; text is the variant being scored."
        ),
        "instruction": (
            "You are the mutation engine. Read the summary_stats (which scorers separate well vs at chance) "
            "and the pairs_the_best_scorer_fails. REASON about WHY the best scorer fails those pairs and what "
            "DIFFERENT signal could catch them, then write 3 NEW, diverse scorer functions that target the gap. "
            "Do not just re-tune the best scorer. Each must be genuinely different in what it measures."
        ),
    }
    ctx_path = os.path.join(HERE, f"gen{gen + 1}_context.json")
    jsave(ctx_path, context)
    print(f"\ngrew adversarial by {len(added)} (worst-separated by best); "
          f"best fails {len(fails)} shown; wrote {ctx_path}")


def cmd_apply(sonnet_path):
    pop = jload(POP, [])
    state = jload(STATE, {"gen": 0, "used_adv": []})
    orig = load("eval_pairs.json")
    adv_pool = load("adversarial_pairs.json")
    gen = state["gen"]
    o_pairs, a_pairs = eval_set(state, orig, adv_pool)
    cur = o_pairs + a_pairs

    raw = open(sonnet_path).read().strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    proposals = json.loads(raw)
    if isinstance(proposals, dict) and "scorers" in proposals:
        proposals = proposals["scorers"]

    added = 0
    for i, p in enumerate(proposals):
        code = (p.get("code") or "").strip()
        sid = f"S_g{gen + 1}_llm{i + 1:02d}"
        if "def scorer" not in code:
            print(f"  reject {sid}: no def scorer")
            continue
        # validity: runs, in range, non-constant on the current eval set
        vals = []
        ok = True
        for pr in cur:
            r = py_run_scorer(code, pr["more_creative"], pr["anchor"])
            if not r["ok"] or r["out_of_range"]:
                print(f"  reject {sid}: {r.get('error') or 'out_of_range'}")
                ok = False
                break
            vals.append(r["value"])
        if not ok:
            continue
        if max(vals) - min(vals) < 1e-6:
            print(f"  reject {sid}: constant output")
            continue
        acc, mrg = sep(code, cur)
        pop.append({"scorer_id": sid, "lineage": f"llm_gen{gen + 1}", "gen_added": gen + 1,
                    "hypothesis": p.get("hypothesis", "")[:300],
                    "reasoning": p.get("reasoning", p.get("design_reasoning", ""))[:600],
                    "code": code})
        added += 1
        print(f"  accept {sid}: acc_all={acc:.3f} margin={mrg:+.4f}  {p.get('hypothesis','')[:70]}")

    state["gen"] = gen + 1
    jsave(STATE, state)
    jsave(POP, pop)
    print(f"apply: added {added}/{len(proposals)} scorers; advanced to gen {gen + 1}")


def cmd_report():
    hist = jload(HIST, [])
    print("\n=== SEPARATION TRAJECTORY (LLM-mutation evolution) ===")
    print(f"{'gen':>3} {'pairs':>6} {'scorers':>7} {'best_all':>8} {'best_orig':>9} "
          f"{'best_adv':>8} {'best_id':>16} {'lineage':>12}")
    for h in hist:
        badv = f"{h['best_acc_adv']:.3f}" if h["best_acc_adv"] is not None else "  -"
        print(f"{h['gen']:>3} {h['n_pairs']:>6} {h['n_scorers']:>7} {h['best_acc_all']:>8.3f} "
              f"{h['best_acc_orig']:>9.3f} {badv:>8} {h['best_id']:>16} {h['best_lineage']:>12}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "init":
        cmd_init()
    elif cmd == "prepare":
        cmd_prepare()
    elif cmd == "apply":
        cmd_apply(sys.argv[2])
    elif cmd == "report":
        cmd_report()
