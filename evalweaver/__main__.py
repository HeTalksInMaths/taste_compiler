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

    run_parser = subparsers.add_parser("run", help="Run the full evaluation pipeline")
    run_parser.add_argument(
        "--config", "-c",
        type=str,
        default="configs/persuasive.yaml",
        help="Path to YAML config file (default: configs/persuasive.yaml)",
    )

    args = parser.parse_args()

    if args.command == "run":
        config = load_config(args.config)
        result = run_pipeline(config)
        if result.get("success"):
            print(f"\nPipeline complete. Output: {result.get('output_dir', 'unknown')}")
            sys.exit(0)
        else:
            print(f"\nPipeline failed: {result.get('error', 'unknown error')}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
