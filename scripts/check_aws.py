#!/usr/bin/env python3
"""Validate AWS credentials and Bedrock model access."""
import sys


def main():
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3")
        sys.exit(1)

    # Check STS identity
    print("Checking AWS credentials...")
    try:
        session = boto3.Session()
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"  Account: {identity['Account']}")
        print(f"  ARN:     {identity['Arn']}")
        print(f"  Region:  {session.region_name}")
        print("  \u2713 AWS credentials valid\n")
    except Exception as e:
        print(f"  \u2717 AWS credential error: {e}")
        print("\n  Setup:")
        print("    aws configure sso")
        print("    export AWS_PROFILE=next-sandbox")
        print("    export AWS_REGION=us-east-1")
        sys.exit(1)

    # Check Bedrock access with a tiny Converse call
    print("Testing Bedrock Converse API...")
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"  # Cheapest model for smoke test
    try:
        bedrock = session.client("bedrock-runtime", region_name=session.region_name or "us-east-1")
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
    print(f"  python -m evalweaver run --config configs/persuasive.yaml --provider bedrock --model-id {model_id}")


if __name__ == "__main__":
    main()
