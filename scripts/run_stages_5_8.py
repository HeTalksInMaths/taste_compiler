#!/usr/bin/env python3
"""Run Stages 5–8 pipeline using existing Stage 1–4 artifacts from a prior run."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evalweaver.providers.bedrock_claude_provider import BedrockClaudeProvider
from evalweaver.stages_5_8 import Stage5to8Orchestrator
from evalweaver.artifacts import log


def main():
    # Load prior stage outputs
    artifacts_dir = "ew_v51_outputs"
    out_dir = "ew_v51_outputs"  # write stage 5-8 artifacts into the same run dir

    with open(os.path.join(artifacts_dir, "stage2_parsed_json.json")) as f:
        stage2_output = json.load(f)
    with open(os.path.join(artifacts_dir, "stage3_parsed_json.json")) as f:
        stage3_output = json.load(f)

    # Use working scorers from parallel Stage 4 as the scorer population
    with open(os.path.join(artifacts_dir, "stage4_parallel_working_scorers.json")) as f:
        working_scorers = json.load(f)

    stage4_output = {"scorers": working_scorers, "target_variable": "trustworthy"}

    # Config
    config = {
        "target_variable": "trustworthy",
        "raw_text": "",
        "heldout_count": 3,
        "source_policy": {
            "no_fabricated_evidence": True,
            "no_unsupported_numbers": True,
            "no_named_customers": True,
        },
    }

    # Create provider
    provider = BedrockClaudeProvider(
        model_id="us.anthropic.claude-sonnet-4-6",
        aws_region="us-east-1",
        max_tokens=16384,
        temperature=0.7,
    )

    # Run Stages 5–8
    orchestrator = Stage5to8Orchestrator(
        provider=provider,
        config=config,
        out_dir=out_dir,
        stage2_output=stage2_output,
        stage3_output=stage3_output,
        stage4_output=stage4_output,
    )

    result = orchestrator.run()

    print("\n" + "=" * 60)
    print("STAGES 5–8 PIPELINE RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))

    if result.get("success"):
        print("\n✓ All stages 5–8 passed!")
    else:
        print(f"\n✗ Pipeline failed at Stage {result.get('failed_stage')}")


if __name__ == "__main__":
    main()
