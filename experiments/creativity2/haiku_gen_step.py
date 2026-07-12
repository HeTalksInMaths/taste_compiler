"""One-command generation step for the Haiku arm.

Usage: EVO2_STATE=haiku_state.json EVO2_PREFIX=h_ EVO2_ADV_KEEP=10 \
           python haiku_gen_step.py <gen_number>

Merges haiku_run/gen{N}_eng*.json and gen{N}_red*.json (sanitizing HTML
entities and code fences), runs apply-scorers, apply-pairs, prepare.
"""

import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "haiku_run")


def sanitize(s):
    if not isinstance(s, str):
        return s
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
             .replace("\\u003c", "<").replace("\\u003e", ">"))


def load_merge(pattern, dedup_key):
    items, seen = [], set()
    for path in sorted(glob.glob(os.path.join(RUN, pattern))):
        try:
            raw = open(path).read().strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
        except Exception as e:
            print(f"  skip {os.path.basename(path)}: {e}")
            continue
        if isinstance(data, dict):
            data = data.get("scorers") or data.get("pairs") or []
        for it in data:
            if not isinstance(it, dict):
                continue
            it = {k: sanitize(v) for k, v in it.items()}
            key = it.get(dedup_key, "")
            if key and key not in seen:
                seen.add(key)
                items.append(it)
    return items


def main():
    gen = int(sys.argv[1])
    env = dict(os.environ)

    scorers = load_merge(f"gen{gen}_eng*.json", "name")
    pairs = load_merge(f"gen{gen}_red*.json", "pair_id")
    print(f"gen {gen}: merged {len(scorers)} scorer proposals, {len(pairs)} pair candidates")

    sf = os.path.join(RUN, f"gen{gen}_scorers_merged.json")
    pf = os.path.join(RUN, f"gen{gen}_pairs_merged.json")
    json.dump(scorers, open(sf, "w"), indent=1)
    json.dump(pairs, open(pf, "w"), indent=1)

    def run(cmd):
        r = subprocess.run([sys.executable, os.path.join(HERE, "evo2.py")] + cmd,
                           env=env, capture_output=True, text=True)
        print(r.stdout)
        if r.returncode != 0:
            print(r.stderr[-2000:])

    if scorers:
        run(["apply-scorers", sf])
    if pairs:
        run(["apply-pairs", pf])
    run(["prepare"])


if __name__ == "__main__":
    main()
