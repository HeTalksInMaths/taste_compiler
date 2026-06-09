"""CLI entry point: python -m evalweaver run --config configs/persuasive.yaml"""

import argparse
import os
import sys

from evalweaver.config import load_config
from evalweaver.pipeline import run_pipeline


def _validate_bedrock(model_id, region):
    """Validate Bedrock credentials before run. Returns validation dict."""
    try:
        import boto3
    except ImportError:
        return {"passed": False, "error": "boto3 not installed. Run: python3 -m pip install boto3"}

    try:
        session = boto3.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return {
            "passed": True,
            "account": identity["Account"],
            "arn": identity["Arn"],
            "region": region,
            "model_id": model_id,
        }
    except Exception as e:
        return {"passed": False, "error": str(e)}


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
        help="LLM provider (default: mock). Bedrock validates credentials but uses static artifacts unless --generate-step is specified.",
    )
    run_parser.add_argument(
        "--model-id",
        type=str,
        default="us.anthropic.claude-sonnet-4-6",
        help="Model ID for the provider (default: us.anthropic.claude-sonnet-4-6)",
    )
    run_parser.add_argument(
        "--generate-step",
        type=str,
        choices=["research", "taste_map", "scorer_hypotheses", "pairs", "candidates"],
        default=None,
        help="Run ONE real Bedrock generation for the specified step (requires --provider bedrock)",
    )
    run_parser.add_argument(
        "--artifact-store",
        type=str,
        choices=["local", "s3"],
        default="local",
        help="Where to store output artifacts (default: local)",
    )
    run_parser.add_argument(
        "--s3-bucket",
        type=str,
        default=os.environ.get("TASTE_COMPILER_ARTIFACT_BUCKET"),
        help="S3 bucket for artifact upload (default: TASTE_COMPILER_ARTIFACT_BUCKET env)",
    )

    # ── experiment subcommand ──
    exp_parser = subparsers.add_parser(
        "experiment", help="Run multi-seed experiment for a single topic"
    )
    exp_parser.add_argument("--config", "-c", type=str, required=True)
    exp_parser.add_argument("--seeds", type=int, default=5)
    exp_parser.add_argument("--scorers", type=int, default=None)
    exp_parser.add_argument("--pairs", type=int, default=None)
    exp_parser.add_argument("--provider", type=str, choices=["mock", "bedrock"], default="mock")
    exp_parser.add_argument("--model-id", type=str, default="us.anthropic.claude-sonnet-4-6")

    # ── batch subcommand ──
    batch_parser = subparsers.add_parser("batch", help="Run experiments across multiple topics")
    batch_parser.add_argument("--configs", type=str, nargs="+", required=True)
    batch_parser.add_argument("--seeds", type=int, default=1)

    args = parser.parse_args()

    if args.command == "run":
        config = load_config(args.config)
        config["provider_name"] = args.provider
        config["model_id"] = args.model_id
        config["aws_region"] = os.environ.get("AWS_REGION", "us-east-1")
        config["generate_step"] = args.generate_step
        config["artifact_store"] = args.artifact_store
        config["s3_bucket"] = args.s3_bucket or os.environ.get("TASTE_COMPILER_ARTIFACT_BUCKET")

        # Bedrock provider: validate credentials and print honest status
        if args.provider == "bedrock":
            region = config["aws_region"]
            validation = _validate_bedrock(args.model_id, region)
            config["bedrock_validation_passed"] = validation["passed"]

            if validation["passed"]:
                print(f"Bedrock credentials valid: account={validation['account']} region={region}")
            else:
                print(f"WARNING: Bedrock validation failed: {validation['error']}")

            if args.generate_step:
                if not validation["passed"]:
                    print("ERROR: Cannot use --generate-step without valid credentials.")
                    sys.exit(1)
                config["provider_generation_enabled"] = True
                print(f"Live generation enabled for step: {args.generate_step}")
            else:
                config["provider_generation_enabled"] = False
                print(
                    "Bedrock provider selected as metadata only; "
                    "provider_generation_enabled=false; static artifacts are still used."
                )
                print("Use --generate-step <step> to make a real Bedrock call.")
        else:
            config["provider_generation_enabled"] = False
            config["bedrock_validation_passed"] = None

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
        batch_summary = run_batch(config_paths=args.configs, seeds=args.seeds)
        total = batch_summary["topics"]
        passed = sum(1 for r in batch_summary["per_topic_results"] if r["success"])
        print(f"\nBatch complete. {passed}/{total} topics succeeded.")
        sys.exit(0 if passed == total else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
