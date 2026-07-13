"""EVO3 — blind compositional discovery of NON-INTUITIVE creativity scorers.

Inverts EVO2's theory-first pipeline: instead of asking an LLM to write a
scorer from a named mechanism, we (1) build a typed PRIMITIVE library (per-token
series distilled from everything the agents built: surprisal, zipf, word length,
edit-alignment opcodes, position), (2) run a seeded genetic-programming search
over compositions of those primitives — tens of thousands of programs no one
would think to write, (3) keep only programs that BOTH separate (SEP on train)
AND are behaviorally decorrelated (|r| < 0.5) from every known scorer and every
other archive member, and (4) hand survivors to an LLM for POST-HOC explanation,
which is accepted only if its predictions hold on fresh probe pairs (tested
separately).

Fitness/eval identical to EVO2: SEP = mean(score_pos) - mean(score_neg), train
for search, frozen heldout + stationary core for honest reporting.
"""

import json
import math
import os
import random
import sys
import difflib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CR1 = os.path.abspath(os.path.join(HERE, "..", "creativity"))
sys.path.insert(0, CR1)
sys.path.insert(0, HERE)

from wordfreq import word_frequency, zipf_frequency  # noqa: E402
import re  # noqa: E402

STOP = set(
    "a an the and or but if then else of to in on at by for with from as is are was were "
    "be been being it its this that these those i you he she we they me him her us them my "
    "your his their our not no so do does did have has had will would can could should may "
    "might must about into over under out up down off than too very just also".split()
)
_W = re.compile(r"[a-zA-Z']+")


def toks(s):
    return _W.findall((s or "").lower())


# ── Primitive extraction: per-(text, anchor) feature bundle ────────────
_CACHE = {}


def bundle(text, anchor):
    key = (text, anchor)
    if key in _CACHE:
        return _CACHE[key]
    t = toks(text)
    a = toks(anchor)
    n = max(1, len(t))
    sur = np.array([min(24.0, -math.log2(word_frequency(w, "en") or 2 ** -24)) for w in t])
    zf = np.array([zipf_frequency(w, "en") for w in t])
    wlen = np.array([float(len(w)) for w in t])
    content = np.array([1.0 if (w not in STOP and len(w) > 1) else 0.0 for w in t])
    pos = np.arange(n) / n
    # edit alignment vs anchor: 0 = kept, 1 = replaced, 2 = inserted
    op = np.zeros(n)
    sm = difflib.SequenceMatcher(a=a, b=t, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            op[j1:j2] = 1.0
        elif tag == "insert":
            op[j1:j2] = 2.0
    # sentence index (0/1) via punctuation split on the raw text
    sents = [p for p in re.split(r"[.!?]+", text or "") if p.strip()]
    first_len = len(toks(sents[0])) if sents else n
    sent = (np.arange(n) >= first_len).astype(float)
    b = {"sur": sur, "zipf": zf, "wlen": wlen, "content": content,
         "pos": pos, "op": op, "sent": sent, "n": n,
         "changed": (op > 0).astype(float)}
    _CACHE[key] = b
    return b


# ── Typed grammar ──────────────────────────────────────────────────────
SERIES = ["sur", "zipf", "wlen", "content", "pos", "op", "sent", "changed"]
MASKS = ["content", "changed", "sent", "none"]      # boolean masks over tokens

def _gini(v):
    v = np.sort(np.clip(v, 0, None))
    s = v.sum()
    if s <= 1e-12 or len(v) < 2:
        return 0.0
    n = len(v)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(v) / (n * s))

REDUCERS = {
    "mean": lambda v: float(np.mean(v)) if len(v) else 0.0,
    "std": lambda v: float(np.std(v)) if len(v) else 0.0,
    "gini": _gini,
    "max_share": lambda v: float(np.max(v) / (np.sum(v) + 1e-9)) if len(v) and np.sum(v) > 1e-9 else 0.0,
    "slope": lambda v: float(np.corrcoef(v, np.arange(len(v)))[0, 1]) if len(v) > 2 and np.std(v) > 1e-9 else 0.0,
    "lag1": lambda v: float(np.corrcoef(v[:-1], v[1:])[0, 1]) if len(v) > 3 and np.std(v[:-1]) > 1e-9 and np.std(v[1:]) > 1e-9 else 0.0,
    "frac_hi": lambda v: float(np.mean(v > (np.mean(v) + np.std(v)))) if len(v) else 0.0,
}

COMBINE = {
    "sub": lambda x, y: x - y,
    "ratio": lambda x, y: x / (abs(y) + 0.25),
    "prod": lambda x, y: x * y,
    "gate": lambda x, y: x * (1.0 / (1.0 + math.exp(-4.0 * y))),
    "min": lambda x, y: min(x, y),
    "absdiff": lambda x, y: abs(x - y),
}

# Program encoding:
#   ("leaf", series, mask, reducer, rel)      rel: 0 = on text, 1 = text-minus-anchor
#   ("comb", op, p1, p2)


def gen_leaf(rng):
    return ("leaf", rng.choice(SERIES), rng.choice(MASKS),
            rng.choice(list(REDUCERS)), rng.random() < 0.5)


def gen_prog(rng, depth=0):
    if depth >= 2 or rng.random() < 0.45:
        return gen_leaf(rng)
    return ("comb", rng.choice(list(COMBINE)),
            gen_prog(rng, depth + 1), gen_prog(rng, depth + 1))


def mutate(p, rng, depth=0):
    if rng.random() < 0.3:
        return gen_prog(rng, depth)
    if p[0] == "leaf":
        f = list(p)
        i = rng.randint(1, 4)
        if i == 1:
            f[1] = rng.choice(SERIES)
        elif i == 2:
            f[2] = rng.choice(MASKS)
        elif i == 3:
            f[3] = rng.choice(list(REDUCERS))
        else:
            f[4] = not f[4]
        return tuple(f)
    which = rng.random()
    if which < 0.2:
        return ("comb", rng.choice(list(COMBINE)), p[2], p[3])
    if which < 0.6:
        return ("comb", p[1], mutate(p[2], rng, depth + 1), p[3])
    return ("comb", p[1], p[2], mutate(p[3], rng, depth + 1))


def eval_leaf(leaf, text, anchor):
    _, series, mask, reducer, rel = leaf

    def val(t, a):
        b = bundle(t, a)
        v = b[series]
        if mask != "none":
            m = b[mask] > 0
            v = v[m]
        return REDUCERS[reducer](v)

    x = val(text, anchor)
    if rel:
        x -= val(anchor, anchor)
    return x


def eval_prog(p, text, anchor):
    if p[0] == "leaf":
        return eval_leaf(p, text, anchor)
    _, op, p1, p2 = p
    return COMBINE[op](eval_prog(p1, text, anchor), eval_prog(p2, text, anchor))


def prog_str(p):
    if p[0] == "leaf":
        rel = "Δanchor" if p[4] else "text"
        m = "" if p[2] == "none" else f"[{p[2]}]"
        return f"{p[3]}({p[1]}{m}, {rel})"
    return f"{p[1]}({prog_str(p[2])}, {prog_str(p[3])})"


# ── Search ─────────────────────────────────────────────────────────────
def margins(p, pairs):
    out = []
    for pr in pairs:
        try:
            m = eval_prog(p, pr["more_creative"], pr["anchor"]) - \
                eval_prog(p, pr["less_creative"], pr["anchor"])
        except Exception:
            return None
        if not np.isfinite(m):
            return None
        out.append(m)
    return np.array(out)


def sep_stats(p, pairs):
    sp, sn = [], []
    for pr in pairs:
        sp.append(eval_prog(p, pr["more_creative"], pr["anchor"]))
        sn.append(eval_prog(p, pr["less_creative"], pr["anchor"]))
    sp, sn = np.array(sp), np.array(sn)
    scale = np.std(np.concatenate([sp, sn])) or 1e-9
    return {"SEP_raw": float(sp.mean() - sn.mean()),
            "SEP_std": float((sp.mean() - sn.mean()) / scale),
            "acc": float(np.mean(sp > sn))}


def maxcorr(v, others):
    best = 0.0
    for o in others:
        if np.std(v) < 1e-12 or np.std(o) < 1e-12:
            continue
        best = max(best, abs(float(np.corrcoef(v, o)[0, 1])))
    return best


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    n_random = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    rng = random.Random(seed)

    st = json.load(open(os.path.join(HERE, "haiku_state.json")))
    train, heldout, core_ids = st["train"], st["heldout"], st["core_ids"]
    core = [p for p in heldout if p["pair_id"] in core_ids]
    print(f"pairs: train={len(train)} heldout={len(heldout)} core={len(core)}")

    # incumbent fingerprints (all scorers in the final haiku population)
    from evo2 import compile_metrics
    incumbents = []
    for m in st["population"]:
        fn = compile_metrics(m["code"], [m["metric_key"]])[m["metric_key"]]
        v = np.array([fn(p["more_creative"], p["anchor"]) - fn(p["less_creative"], p["anchor"])
                      for p in train])
        incumbents.append(v)
    print(f"incumbent fingerprints: {len(incumbents)}")

    # warm the primitive cache
    for p in train + heldout:
        bundle(p["more_creative"], p["anchor"])
        bundle(p["less_creative"], p["anchor"])
        bundle(p["anchor"], p["anchor"])

    # phase 1: random sweep
    archive = []   # (SEP_std_train, prog, margin_vec)
    seen = set()
    cands = []
    for i in range(n_random):
        p = gen_prog(rng)
        s = prog_str(p)
        if s in seen:
            continue
        seen.add(s)
        mv = margins(p, train)
        if mv is None or np.std(mv) < 1e-9:
            continue
        st_ = sep_stats(p, train)
        if st_["SEP_std"] > 0.25:
            cands.append((st_["SEP_std"], p, mv))
        if (i + 1) % 5000 == 0:
            print(f"  swept {i+1}/{n_random}, candidates={len(cands)}")

    # phase 2: GP refinement of the top candidates
    cands.sort(key=lambda x: -x[0])
    pool = cands[:200]
    for gen in range(4):
        newpool = list(pool)
        for sc, p, mv in pool[:60]:
            for _ in range(4):
                q = mutate(p, rng)
                s = prog_str(q)
                if s in seen:
                    continue
                seen.add(s)
                mv2 = margins(q, train)
                if mv2 is None or np.std(mv2) < 1e-9:
                    continue
                st2 = sep_stats(q, train)
                newpool.append((st2["SEP_std"], q, mv2))
        newpool.sort(key=lambda x: -x[0])
        pool = newpool[:200]
        print(f"  GP gen {gen}: best SEP_std={pool[0][0]:.3f}")

    # phase 3: decorrelated archive (novelty is a HARD requirement)
    fps = list(incumbents)
    for sc, p, mv in pool:
        if maxcorr(mv, fps) < 0.5:
            archive.append((sc, p, mv))
            fps.append(mv)
        if len(archive) >= 6:
            break

    print(f"\n=== DECORRELATED DISCOVERIES (|r|<0.5 vs ALL {len(incumbents)} incumbents & each other) ===")
    results = []
    for sc, p, mv in archive:
        tr = sep_stats(p, train)
        ho = sep_stats(p, heldout)
        co = sep_stats(p, core)
        r_inc = maxcorr(mv, incumbents)
        print(f"\n  {prog_str(p)}")
        print(f"    train SEP_std={tr['SEP_std']:.3f} acc={tr['acc']:.2f} | "
              f"heldout SEP_std={ho['SEP_std']:.3f} acc={ho['acc']:.2f} | "
              f"core SEP_std={co['SEP_std']:.3f} acc={co['acc']:.2f} | max|r| vs incumbents={r_inc:.2f}")
        results.append({"program": prog_str(p), "tree": repr(p),
                        "train": tr, "heldout": ho, "core": co,
                        "max_corr_incumbents": round(r_inc, 3)})
    json.dump(results, open(os.path.join(HERE, "evo3_discoveries.json"), "w"), indent=1)
    print(f"\nwrote evo3_discoveries.json ({len(results)} programs)")


if __name__ == "__main__":
    main()
