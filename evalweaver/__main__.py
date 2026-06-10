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
        "--live-canary",
        action="store_true",
        default=False,
        help="Run all reasoning steps live via Bedrock (research, taste_map, pairs, candidates). Scorer code remains static.",
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

    # ── stages subcommand (Stages 1–4 reasoning pipeline) ──
    stages_parser = subparsers.add_parser(
        "stages", help="Run Stages 1–4 reasoning pipeline (live Bedrock)"
    )
    stages_parser.add_argument(
        "--config", "-c", type=str, default="configs/trustworthy.yaml",
        help="Path to YAML config file (default: configs/trustworthy.yaml)",
    )
    stages_parser.add_argument(
        "--model-id", type=str, default="us.anthropic.claude-sonnet-4-6",
        help="Model ID for Bedrock (default: us.anthropic.claude-sonnet-4-6)",
    )
    stages_parser.add_argument(
        "--target-variable", type=str, default=None,
        help="Override target variable from config",
    )
    stages_parser.add_argument(
        "--temperature", type=float, default=1.0,
        help="Temperature for LLM calls (default: 1.0)",
    )
    stages_parser.add_argument(
        "--max-tokens", type=int, default=16384,
        help="Max tokens for LLM responses (default: 16384)",
    )
    stages_parser.add_argument(
        "--resume-from", type=int, default=None, choices=[2, 3, 4],
        help="Resume from a specific stage (uses existing artifacts for previous stages)",
    )
    stages_parser.add_argument(
        "--run-label", type=str, default=None,
        help="Label for this run (used in output subdirectory)",
    )

    # ── stages-5-8 subcommand ──
    s58_parser = subparsers.add_parser(
        "stages-5-8", help="Run Stages 5–8 reasoning pipeline (requires Stage 1–4 artifacts)"
    )
    s58_parser.add_argument(
        "--config", "-c", type=str, default="configs/trustworthy.yaml",
        help="Path to YAML config file (default: configs/trustworthy.yaml)",
    )
    s58_parser.add_argument(
        "--artifacts-dir", type=str, required=True,
        help="Directory containing Stage 1–4 artifacts (stage2_parsed_json.json, etc.)",
    )
    s58_parser.add_argument(
        "--model-id", type=str, default="us.anthropic.claude-sonnet-4-6",
        help="Model ID for Bedrock (default: us.anthropic.claude-sonnet-4-6)",
    )
    s58_parser.add_argument(
        "--target-variable", type=str, default=None,
        help="Override target variable from config",
    )
    s58_parser.add_argument(
        "--temperature", type=float, default=1.0,
        help="Temperature for LLM calls (default: 1.0)",
    )
    s58_parser.add_argument(
        "--max-tokens", type=int, default=16384,
        help="Max tokens for LLM responses (default: 16384)",
    )

    args = parser.parse_args()

    if args.command == "run":
        config = load_config(args.config)

        # --live-canary implies --provider bedrock
        if args.live_canary:
            if args.provider == "mock":
                # If user explicitly passed --provider mock with --live-canary, error
                # But if it's just the default, override to bedrock
                if "--provider" in sys.argv and "mock" in sys.argv:
                    print("ERROR: --live-canary cannot be used with --provider mock")
                    sys.exit(1)
            args.provider = "bedrock"

        config["provider_name"] = args.provider
        config["model_id"] = args.model_id
        config["aws_region"] = os.environ.get("AWS_REGION", "us-east-1")
        config["generate_step"] = args.generate_step
        config["artifact_store"] = args.artifact_store
        config["s3_bucket"] = args.s3_bucket or os.environ.get("TASTE_COMPILER_ARTIFACT_BUCKET")
        config["live_canary"] = args.live_canary

        # --live-canary: enable multi-step live generation
        if args.live_canary:
            config["provider_generation_enabled"] = True
            config["generate_steps"] = ["research", "taste_map", "pairs", "candidates"]

        # Bedrock provider: validate credentials and print honest status
        if args.provider == "bedrock":
            region = config["aws_region"]
            validation = _validate_bedrock(args.model_id, region)
            config["bedrock_validation_passed"] = validation["passed"]

            if validation["passed"]:
                print(f"Bedrock credentials valid: account={validation['account']} region={region}")
            else:
                print(f"WARNING: Bedrock validation failed: {validation['error']}")

            if args.live_canary:
                if not validation["passed"]:
                    print("ERROR: --live-canary requires valid Bedrock credentials.")
                    sys.exit(1)
                print(f"Live canary mode: steps={config['generate_steps']}")
            elif args.generate_step:
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

        try:
            result = run_pipeline(config)
        except RuntimeError as e:
            print(f"\nPipeline failed (live step error): {e}")
            # In canary mode, failure_points.md is already written by the pipeline
            sys.exit(1)

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

    elif args.command == "stages":
        config = load_config(args.config)
        region = os.environ.get("AWS_REGION", "us-east-1")
        model_id = args.model_id

        # Override target variable if provided
        if args.target_variable:
            config["goal"] = args.target_variable

        # Validate Bedrock credentials
        validation = _validate_bedrock(model_id, region)
        if not validation["passed"]:
            print(f"ERROR: Bedrock credential validation failed: {validation['error']}")
            sys.exit(1)
        print(f"Bedrock credentials valid: account={validation['account']} region={region}")
        print(f"Model: {model_id}")
        print(f"Target variable: {config.get('goal', 'trustworthy')}")

        # Run Stages 1–4
        from evalweaver.providers.bedrock_claude_provider import BedrockClaudeProvider
        from evalweaver.stages import StageOrchestrator
        from evalweaver.artifacts import resolve_output_directory

        provider = BedrockClaudeProvider(
            model_id=model_id,
            aws_region=region,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        out_dir = resolve_output_directory()
        orchestrator = StageOrchestrator(provider=provider, config=config, out_dir=out_dir)

        result = orchestrator.run(resume_from=args.resume_from)

        if result.get("success"):
            print(f"\nStages 1–4 PASSED. Output: {out_dir}")
            sys.exit(0)
        else:
            print(f"\nStages pipeline FAILED at Stage {result.get('failed_stage', '?')}. Output: {out_dir}")
            sys.exit(1)

    elif args.command == "stages-5-8":
        import json as _json
        config = load_config(args.config)
        region = os.environ.get("AWS_REGION", "us-east-1")
        model_id = args.model_id

        if args.target_variable:
            config["goal"] = args.target_variable

        # Validate Bedrock credentials
        validation = _validate_bedrock(model_id, region)
        if not validation["passed"]:
            print(f"ERROR: Bedrock credential validation failed: {validation['error']}")
            sys.exit(1)
        print(f"Bedrock credentials valid: account={validation['account']} region={region}")
        print(f"Model: {model_id}")
        print(f"Target variable: {config.get('goal', 'trustworthy')}")

        # Load Stage 1–4 artifacts
        artifacts_dir = args.artifacts_dir
        with open(os.path.join(artifacts_dir, "stage2_parsed_json.json")) as f:
            stage2_output = _json.load(f)
        with open(os.path.join(artifacts_dir, "stage3_parsed_json.json")) as f:
            stage3_output = _json.load(f)

        # Load scorers (prefer parallel working scorers if available)
        scorers_path = os.path.join(artifacts_dir, "stage4_parallel_working_scorers.json")
        if not os.path.exists(scorers_path):
            scorers_path = os.path.join(artifacts_dir, "stage4_parsed_json.json")
        with open(scorers_path) as f:
            scorers_data = _json.load(f)
        if isinstance(scorers_data, list):
            stage4_output = {"scorers": scorers_data, "target_variable": config.get("goal", "trustworthy")}
        else:
            stage4_output = scorers_data

        print(f"Loaded artifacts from: {artifacts_dir}")
        print(f"  Stage 2 nodes: {len(stage2_output.get('causal_nodes', []))}")
        print(f"  Stage 3 items: {len(stage3_output.get('measurement_research', []))}")
        print(f"  Stage 4 scorers: {len(stage4_output.get('scorers', []))}")

        # Run Stages 5–8
        from evalweaver.providers.bedrock_claude_provider import BedrockClaudeProvider
        from evalweaver.stages_5_8 import Stage5to8Orchestrator

        provider = BedrockClaudeProvider(
            model_id=model_id,
            aws_region=region,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )

        orchestrator = Stage5to8Orchestrator(
            provider=provider,
            config=config,
            out_dir=artifacts_dir,
            stage2_output=stage2_output,
            stage3_output=stage3_output,
            stage4_output=stage4_output,
        )

        result = orchestrator.run()

        if result.get("success"):
            print(f"\nStages 5–8 PASSED. Output: {artifacts_dir}")
            sys.exit(0)
        else:
            print(f"\nStages 5–8 FAILED at Stage {result.get('failed_stage', '?')}. Output: {artifacts_dir}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
