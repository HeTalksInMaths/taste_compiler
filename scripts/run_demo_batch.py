#!/usr/bin/env python3
"""Run 6 quality targets through the full 8-stage pipeline via the live API.
Saves each run's output locally for debugging and demo purposes."""

import json
import os
import time
import urllib.request
import urllib.error

BASE_URL = "https://taste-compiler.vercel.app/api/stages"
OUT_DIR = "demo_runs"
os.makedirs(OUT_DIR, exist_ok=True)

# 6 quality targets with reference texts that are deliberately mediocre
# (so the scorer has something to improve)
RUNS = [
    {
        "target": "human",
        "ref_text": "We help teams turn rough product ideas into validated scorer functions. Our platform uses advanced AI to analyze your writing and provide actionable feedback.",
    },
    {
        "target": "persuasive",
        "ref_text": "Join thousands of founders who have transformed their pitch decks. Our data shows a 3x improvement in investor response rates within the first week of using our tool.",
    },
    {
        "target": "concise",
        "ref_text": "The comprehensive integration of multi-modal analytics with our proprietary machine learning algorithms enables unprecedented insights into user behavior patterns across platforms.",
    },
    {
        "target": "empathetic",
        "ref_text": "Your subscription has been cancelled. Please note that all data will be permanently deleted after 30 days. Contact support if you have questions.",
    },
    {
        "target": "data-driven",
        "ref_text": "Our product is really great and customers love it. We have had amazing growth and our team is super passionate about solving this problem for everyone.",
    },
    {
        "target": "professional",
        "ref_text": "hey so basically we need to push back the deadline cuz things are taking longer than expected lol. ill update u when i know more k?",
    },
]


def call_stage(target, stage, previous_output=None, all_outputs=None):
    """Call one stage of the pipeline."""
    body = {"target_variable": target, "stage": stage}
    if previous_output is not None:
        body["previous_output"] = previous_output
    if all_outputs is not None:
        body["all_outputs"] = all_outputs

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "error" in result:
                return None, result["error"]
            return result.get("result"), None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            err = json.loads(error_body)
            return None, err.get("error", f"HTTP {e.code}")
        except Exception:
            return None, f"HTTP {e.code}: {error_body[:200]}"
    except Exception as e:
        return None, str(e)


def run_pipeline(target, ref_text):
    """Run all 8 stages for a target variable."""
    print(f"\n{'='*60}")
    print(f"  Target: {target}")
    print(f"  Ref: {ref_text[:60]}...")
    print(f"{'='*60}")

    all_outputs = {}
    prev_output = None
    results = {"target": target, "ref_text": ref_text, "stages": {}}

    for stage in range(1, 9):
        print(f"  Stage {stage}...", end=" ", flush=True)
        t0 = time.time()

        result, error = call_stage(target, stage, prev_output, all_outputs)

        elapsed = time.time() - t0
        if error:
            print(f"ERROR ({elapsed:.1f}s): {error[:80]}")
            results["stages"][f"stage{stage}"] = {"error": error}
            break

        print(f"OK ({elapsed:.1f}s)")
        results["stages"][f"stage{stage}"] = result
        all_outputs[f"stage{stage}"] = result
        prev_output = result

    # Save
    out_path = os.path.join(OUT_DIR, f"{target}_full.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  → Saved: {out_path}")

    # Print evaluation summary if stage 6 completed
    s6 = results["stages"].get("stage6", {})
    if isinstance(s6, dict) and "scorer_evaluations" in s6:
        print(f"\n  Evaluation Summary:")
        for ev in s6["scorer_evaluations"]:
            pareto = "★" if ev.get("pareto_member") else " "
            print(f"    {pareto} {ev['scorer_id']}: acc={ev['heldout_accuracy']:.0%} gap={ev['heldout_mean_gap']:.2f} {'eligible' if ev['eligible'] else 'FAIL'}")

    return results


if __name__ == "__main__":
    print("Running 6 quality targets through 8-stage pipeline...")
    print(f"API: {BASE_URL}")
    print(f"Output: {OUT_DIR}/")

    all_results = {}
    for run in RUNS:
        result = run_pipeline(run["target"], run["ref_text"])
        all_results[run["target"]] = result
        time.sleep(1)  # Brief pause between runs

    # Save combined summary
    summary_path = os.path.join(OUT_DIR, "batch_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"All runs complete. Results in {OUT_DIR}/")
    print(f"Summary: {summary_path}")

    # Print final scoreboard
    print(f"\n{'='*60}")
    print("SCOREBOARD — Best separators per target:")
    print(f"{'='*60}")
    for target, res in all_results.items():
        s6 = res.get("stages", {}).get("stage6", {})
        if isinstance(s6, dict) and "scorer_evaluations" in s6:
            best = max(s6["scorer_evaluations"], key=lambda e: e.get("heldout_mean_gap", 0))
            print(f"  {target:14s} → {best['scorer_id']} (acc={best['heldout_accuracy']:.0%}, gap={best['heldout_mean_gap']:.2f})")
        else:
            print(f"  {target:14s} → no evaluation data")
