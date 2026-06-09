"""CLI entry point: python -m evalweaver run --config configs/persuasive.yaml"""

import argparse
import sys

from evalweaver.config import load_config
from evalweaver.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        prog="evalweaver",
        description="EvalWeaver v5.1 -- Automated quality scorer discovery and evolution.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── run subcommand ──
    run_parser = subparsers.add_parser("run", help="Run the full evaluation pipeline")
    run_parser.add_argument(
        "--config", "-c",
        type=str,
        default="configs/persuasive.yaml",
        help="Path to YAML config file (default: configs/persuasive.yaml)",
    )
    run_parser.add_argument(
        "--provider",
        type=str,
        choices=["mock", "bedrock"],
        default="mock",
        help="LLM provider to use (default: mock)",
    )
    run_parser.add_argument(
        "--model-id",
        type=str,
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        help="Model ID for the provider (default: anthropic.claude-3-sonnet-20240229-v1:0)",
    )

    # ── experiment subcommand ──
    exp_parser = subparsers.add_parser(
        "experiment", help="Run multi-seed experiment for a single topic"
    )
    exp_parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML config file",
    )
    exp_parser.add_argument(
        "--seeds",
        type=int,
        default=5,
        help="Number of seeds to run (default: 5)",
    )
    exp_parser.add_argument(
        "--scorers",
        type=int,
        default=None,
        help="Override n_init_scorers (optional)",
    )
    exp_parser.add_argument(
        "--pairs",
        type=int,
        default=None,
        help="Override n_init_pairs (optional)",
    )
    exp_parser.add_argument(
        "--provider",
        type=str,
        choices=["mock", "bedrock"],
        default="mock",
        help="LLM provider to use (default: mock)",
    )
    exp_parser.add_argument(
        "--model-id",
        type=str,
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        help="Model ID for the provider (default: anthropic.claude-3-sonnet-20240229-v1:0)",
    )

    # ── batch subcommand ──
    batch_parser = subparsers.add_parser(
        "batch", help="Run experiments across multiple topics"
    )
    batch_parser.add_argument(
        "--configs",
        type=str,
        nargs="+",
        required=True,
        help="Paths to YAML config files",
    )
    batch_parser.add_argument(
        "--seeds",
        type=int,
        default=1,
        help="Number of seeds per topic (default: 1)",
    )

    args = parser.parse_args()

    if args.command == "run":
        config = load_config(args.config)
        config["provider_name"] = args.provider
        config["model_id"] = args.model_id
        result = run_pipeline(config)
        if result.get("success"):
            print(f"\nPipeline complete. Output: {result.get('output_dir', 'unknown')}")
            sys.exit(0)
        else:
            print(f"\nPipeline failed: {result.get('error', 'unknown error')}")
            sys.exit(1)

    elif args.command == "experiment":
        from evalweaver.experiment import run_experiment
        summary = run_experiment(
            config_path=args.config,
            seeds=args.seeds,
            scorers=args.scorers,
            pairs=args.pairs,
            provider_name=args.provider,
            model_id=args.model_id,
        )
        success_rate = summary["summary"]["success_rate"]
        if success_rate == 1.0:
            print(f"\nExperiment complete. All {summary['seeds']} seeds succeeded.")
            sys.exit(0)
        else:
            print(f"\nExperiment complete. Success rate: {success_rate:.0%}")
            sys.exit(0 if success_rate > 0 else 1)

    elif args.command == "batch":
        from evalweaver.experiment import run_batch
        batch_summary = run_batch(
            config_paths=args.configs,
            seeds=args.seeds,
        )
        total = batch_summary["topics"]
        passed = sum(1 for r in batch_summary["per_topic_results"] if r["success"])
        print(f"\nBatch complete. {passed}/{total} topics succeeded.")
        sys.exit(0 if passed == total else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
