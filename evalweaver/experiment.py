"""Experiment runner: multi-seed single-topic and cross-topic batch experiments."""

import json
import os
import statistics
import copy
from pathlib import Path

from evalweaver.config import load_config
from evalweaver.pipeline import run_pipeline
from evalweaver.artifacts import reset_trace


def run_experiment(config_path, seeds=5, scorers=None, pairs=None, provider_name=None, model_id=None):
    """
    Run multiple seeds of the pipeline with optional larger scorer/pair counts.

    Args:
        config_path: Path to YAML config file.
        seeds: Number of seeds to run (0 to seeds-1).
        scorers: Override n_init_scorers if provided.
        pairs: Override n_init_pairs if provided.
        provider_name: LLM provider name (e.g., 'mock', 'bedrock').
        model_id: Model ID for the provider.

    Returns:
        dict with per-seed results and summary statistics.
    """
    base_config = load_config(config_path)
    goal = base_config.get("goal", "unknown")

    if scorers is not None:
        base_config["n_init_scorers"] = scorers
    if pairs is not None:
        base_config["n_init_pairs"] = pairs
    if provider_name is not None:
        base_config["provider_name"] = provider_name
    if model_id is not None:
        base_config["model_id"] = model_id

    # Create experiment output directory
    exp_dir = os.path.join("experiments", f"{goal}_experiment")
    os.makedirs(exp_dir, exist_ok=True)

    per_seed_results = []

    for seed_idx in range(seeds):
        print(f"\n{'='*65}")
        print(f"EXPERIMENT: {goal} -- seed {seed_idx}/{seeds-1}")
        print(f"{'='*65}\n")

        # Reset trace between runs
        reset_trace()

        # Override seed and output directory for this run
        config = copy.deepcopy(base_config)
        config["seed"] = seed_idx

        # Set per-seed output directory via env var
        seed_out_dir = os.path.join(exp_dir, f"seed_{seed_idx}")
        os.makedirs(seed_out_dir, exist_ok=True)
        old_env = os.environ.get("EVALWEAVER_OUTPUT_DIR")
        os.environ["EVALWEAVER_OUTPUT_DIR"] = seed_out_dir

        try:
            result = run_pipeline(config)
            seed_result = _extract_seed_result(seed_idx, result)
        except Exception as e:
            seed_result = {
                "seed": seed_idx,
                "success": False,
                "error": str(e),
                "pareto_size": 0,
                "best_test_margin": 0.0,
                "selected_candidate": None,
                "criteria_pass": False,
            }
        finally:
            # Restore env var
            if old_env is None:
                os.environ.pop("EVALWEAVER_OUTPUT_DIR", None)
            else:
                os.environ["EVALWEAVER_OUTPUT_DIR"] = old_env

        per_seed_results.append(seed_result)

    # Produce summary
    summary = _build_experiment_summary(goal, per_seed_results, config_path)

    # Save summary JSON
    summary_path = os.path.join("experiments", f"{goal}_experiment_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Print console table
    _print_experiment_table(per_seed_results, summary)

    return summary


def _extract_seed_result(seed_idx, result):
    """Extract relevant metrics from a pipeline result."""
    pareto = result.get("pareto_r1", [])
    selected = result.get("selected_candidate")
    criteria = result.get("computed_criteria", [])
    fail_count = result.get("fail_count", 0)

    best_margin = max((s["test_margin"] for s in pareto), default=0.0)

    return {
        "seed": seed_idx,
        "success": result.get("success", False),
        "pareto_size": len(pareto),
        "best_test_margin": best_margin,
        "selected_candidate": selected["candidate_id"] if selected else None,
        "criteria_pass": fail_count == 0,
        "output_dir": result.get("output_dir", ""),
    }


def _build_experiment_summary(goal, per_seed_results, config_path):
    """Build summary statistics from per-seed results."""
    margins = [r["best_test_margin"] for r in per_seed_results if r["success"]]
    candidates = [r["selected_candidate"] for r in per_seed_results if r["selected_candidate"]]

    # Count candidate wins
    candidate_counts = {}
    for c in candidates:
        candidate_counts[c] = candidate_counts.get(c, 0) + 1

    most_frequent = max(candidate_counts, key=candidate_counts.get) if candidate_counts else None

    mean_margin = statistics.mean(margins) if margins else 0.0
    std_margin = statistics.stdev(margins) if len(margins) > 1 else 0.0

    return {
        "goal": goal,
        "config_path": str(config_path),
        "seeds": len(per_seed_results),
        "per_seed_results": per_seed_results,
        "summary": {
            "mean_test_margin": mean_margin,
            "std_test_margin": std_margin,
            "most_frequent_winner": most_frequent,
            "candidate_win_counts": candidate_counts,
            "all_criteria_pass": all(r["criteria_pass"] for r in per_seed_results if r["success"]),
            "success_rate": sum(1 for r in per_seed_results if r["success"]) / len(per_seed_results),
        },
    }


def _print_experiment_table(per_seed_results, summary):
    """Print a console table of experiment results."""
    print(f"\n{'='*65}")
    print("EXPERIMENT SUMMARY")
    print(f"{'='*65}")
    print(f"{'seed':<6}{'pareto_size':<14}{'best_test_margin':<18}{'selected_candidate':<22}{'criteria_pass'}")
    print("-" * 65)
    for r in per_seed_results:
        print(
            f"{r['seed']:<6}"
            f"{r['pareto_size']:<14}"
            f"{r['best_test_margin']:<18.4f}"
            f"{(r['selected_candidate'] or 'N/A'):<22}"
            f"{'PASS' if r['criteria_pass'] else 'FAIL'}"
        )
    print("-" * 65)

    s = summary["summary"]
    print(f"\nMean test margin: {s['mean_test_margin']:.4f} (std: {s['std_test_margin']:.4f})")
    print(f"Most frequent winner: {s['most_frequent_winner']}")
    print(f"Candidate win counts: {s['candidate_win_counts']}")
    print(f"All criteria pass: {s['all_criteria_pass']}")
    print(f"Success rate: {s['success_rate']:.0%}")


def run_batch(config_paths, seeds=1):
    """
    Run experiments across multiple topics.

    Args:
        config_paths: List of paths to YAML config files.
        seeds: Number of seeds per topic (default 1 for speed).

    Returns:
        dict with per-topic results and cross-topic comparison.
    """
    per_topic_results = []

    for config_path in config_paths:
        config = load_config(config_path)
        goal = config.get("goal", "unknown")

        print(f"\n{'#'*65}")
        print(f"BATCH: Running topic '{goal}' from {config_path}")
        print(f"{'#'*65}\n")

        # Reset trace between topics
        reset_trace()

        # Set output directory for this topic
        topic_out_dir = os.path.join("experiments", "batch", goal)
        os.makedirs(topic_out_dir, exist_ok=True)
        old_env = os.environ.get("EVALWEAVER_OUTPUT_DIR")
        os.environ["EVALWEAVER_OUTPUT_DIR"] = topic_out_dir

        try:
            result = run_pipeline(config)
            topic_result = {
                "topic": goal,
                "config_path": str(config_path),
                "success": result.get("success", False),
                "pareto_size": len(result.get("pareto_r1", [])),
                "best_margin": max(
                    (s["test_margin"] for s in result.get("pareto_r1", [])),
                    default=0.0,
                ),
                "selected": (
                    result["selected_candidate"]["candidate_id"]
                    if result.get("selected_candidate")
                    else None
                ),
                "criteria_pass": result.get("fail_count", 0) == 0,
                "output_dir": topic_out_dir,
            }
        except Exception as e:
            topic_result = {
                "topic": goal,
                "config_path": str(config_path),
                "success": False,
                "error": str(e),
                "pareto_size": 0,
                "best_margin": 0.0,
                "selected": None,
                "criteria_pass": False,
            }
        finally:
            if old_env is None:
                os.environ.pop("EVALWEAVER_OUTPUT_DIR", None)
            else:
                os.environ["EVALWEAVER_OUTPUT_DIR"] = old_env

        per_topic_results.append(topic_result)

    # Save batch comparison
    batch_summary = {
        "topics": len(per_topic_results),
        "seeds_per_topic": seeds,
        "per_topic_results": per_topic_results,
    }

    batch_path = os.path.join("experiments", "batch_comparison.json")
    os.makedirs(os.path.dirname(batch_path), exist_ok=True)
    with open(batch_path, "w") as f:
        json.dump(batch_summary, f, indent=2, default=str)

    # Print cross-topic comparison table
    _print_batch_table(per_topic_results)

    return batch_summary


def _print_batch_table(per_topic_results):
    """Print a console table of cross-topic batch results."""
    print(f"\n{'='*65}")
    print("BATCH COMPARISON (cross-topic)")
    print(f"{'='*65}")
    print(f"{'topic':<22}{'pareto_size':<14}{'best_margin':<14}{'selected':<14}{'criteria'}")
    print("-" * 65)
    for r in per_topic_results:
        print(
            f"{r['topic']:<22}"
            f"{r['pareto_size']:<14}"
            f"{r['best_margin']:<14.4f}"
            f"{(r.get('selected') or 'N/A'):<14}"
            f"{'PASS' if r['criteria_pass'] else 'FAIL'}"
        )
    print("-" * 65)
