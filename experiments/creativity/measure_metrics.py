"""Parameter-free measurement of each real NLP metric's separation.

No weights, no fitting, no train/test tuning — each metric returns one principled
quantity and we report how often it ranks more_creative > less_creative. This is
a measurement study, not a trained model. Extra metric modules (e.g. LLM-written
metrics_genN.py) are auto-discovered and measured alongside the base library.
"""

import json
import os
import sys
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def sep(fn, pairs):
    c = t = 0
    for p in pairs:
        try:
            mv = fn(p["more_creative"], p["anchor"])
            lv = fn(p["less_creative"], p["anchor"])
        except Exception:
            return None, None
        if mv > lv + 1e-12:
            c += 1
        elif abs(mv - lv) < 1e-12:
            t += 1
    return c / len(pairs), t


def collect_metrics():
    metrics = {}
    base = importlib.import_module("creativity_metrics")
    for name, (fn, na, hi) in base.METRICS.items():
        metrics[name] = fn
    # auto-discover metrics_gen*.py modules exposing METRICS = {name: fn}
    for f in sorted(os.listdir(HERE)):
        if f.startswith("metrics_gen") and f.endswith(".py"):
            mod = importlib.import_module(f[:-3])
            for name, fn in getattr(mod, "METRICS", {}).items():
                metrics[f"{f[:-3]}:{name}"] = fn
    return metrics


def main():
    orig = json.load(open(os.path.join(HERE, "eval_pairs.json")))
    adv = json.load(open(os.path.join(HERE, "adversarial_pairs.json")))
    allp = orig + adv
    metrics = collect_metrics()

    rows = []
    for name, fn in metrics.items():
        ao, _ = sep(fn, orig)
        aa, _ = sep(fn, adv)
        ac, tc = sep(fn, allp)
        if ac is None:
            rows.append((name, None, None, None, None))
        else:
            rows.append((name, ao, aa, ac, tc))

    print(f"{'metric':>28} {'orig(20)':>9} {'adv(12)':>9} {'all(32)':>9} {'ties':>5}")
    for name, ao, aa, ac, tc in sorted(rows, key=lambda r: -(r[3] or -1)):
        if ac is None:
            print(f"{name:>28} {'ERROR':>9}")
        else:
            print(f"{name:>28} {ao:>9.3f} {aa:>9.3f} {ac:>9.3f} {tc:>5}")

    out = {"n_orig": len(orig), "n_adv": len(adv),
           "results": [{"metric": n, "orig": ao, "adv": aa, "all": ac, "ties": tc}
                       for n, ao, aa, ac, tc in rows if ac is not None]}
    json.dump(out, open(os.path.join(HERE, "metric_measurement.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
