#!/usr/bin/env python3
"""Validate AWS credentials and Bedrock model access."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Check AWS credentials and Bedrock access")
    parser.add_argument(
        "--model-id",
        type=str,
        default="us.anthropic.claude-sonnet-4-6",
        help="Bedrock model ID to test (default: us.anthropic.claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="AWS region (default: from AWS_REGION env or us-east-1)",
    )
    args = parser.parse_args()

    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: python3 -m pip install boto3")
        sys.exit(1)

    import os
    region = args.region or os.environ.get("AWS_REGION", "us-east-1")

    # Check STS identity
    print("Checking AWS credentials...")
    try:
        session = boto3.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"  Account: {identity['Account']}")
        print(f"  ARN:     {identity['Arn']}")
        print(f"  Region:  {region}")
        print("  \u2713 AWS credentials valid\n")
    except Exception as e:
        print(f"  \u2717 AWS credential error: {e}")
        print("\n  Setup:")
        print("    aws configure sso")
        print("    export AWS_PROFILE=next-sandbox")
        print("    export AWS_REGION=us-east-1")
        sys.exit(1)

    # Check Bedrock access with a tiny Converse call
    model_id = args.model_id
    print(f"Testing Bedrock Converse API with {model_id}...")
    try:
        bedrock = session.client("bedrock-runtime", region_name=region)
        response = bedrock.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Say hello in exactly 3 words."}]}],
            inferenceConfig={"maxTokens": 20, "temperature": 0.0},
        )
        output_text = response["output"]["message"]["content"][0]["text"]
        print(f"  Model: {model_id}")
        print(f"  Response: {output_text}")
        print("  \u2713 Bedrock Converse API working\n")
    except Exception as e:
        print(f"  \u2717 Bedrock error: {e}")
        print(f"\n  Make sure model '{model_id}' is enabled in your AWS account.")
        print("  Go to: AWS Console > Amazon Bedrock > Model access")
        sys.exit(1)

    print("All checks passed. You can run:")
    print(f"  python3 -m evalweaver run --provider bedrock --model-id {model_id}")
    print(f"  python3 -m evalweaver run --provider bedrock --model-id {model_id} --generate-step research")


if __name__ == "__main__":
    main()
