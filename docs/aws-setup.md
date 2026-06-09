# AWS Setup for EvalWeaver

## Prerequisites

- AWS account with Bedrock model access enabled
- AWS CLI v2 installed
- Python boto3 (`pip install 'evalweaver[aws]'`)

## Configure Credentials

### Option A: SSO (recommended for orgs)
```bash
aws configure sso
# Follow prompts to set up SSO profile
export AWS_PROFILE=next-sandbox
export AWS_REGION=us-east-1
```

### Option B: Named profile
```bash
aws configure --profile next-sandbox
export AWS_PROFILE=next-sandbox
export AWS_REGION=us-east-1
```

### Validate
```bash
aws sts get-caller-identity
# Should show your account, ARN, and user ID
```

## Enable Bedrock Models

1. Go to AWS Console → Amazon Bedrock → Model access
2. Enable the models you want to use (e.g., Claude 3 Sonnet, Claude 3 Haiku)
3. Wait for access to be granted (usually instant)

## Run Smoke Test

```bash
python scripts/check_aws.py
```

This validates credentials and makes a tiny Bedrock Converse call.

## Usage

```bash
# Local (no AWS needed)
python -m evalweaver run --config configs/persuasive.yaml --provider mock

# With Bedrock
python -m evalweaver run --config configs/persuasive.yaml --provider bedrock --model-id anthropic.claude-3-sonnet-20240229-v1:0
```

## Security Rules

**Never commit:**
- AWS access keys or secret keys
- `.env` files with credentials
- `~/.aws/credentials` content
- Bedrock API keys
- Any live service keys

Credentials are read from the environment via boto3's credential chain:
1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
2. AWS_PROFILE → ~/.aws/config
3. SSO session
4. IAM instance role (ECS/Lambda)

## Troubleshooting

| Error | Fix |
|-------|-----|
| NoCredentialsError | Run `aws configure sso` or set AWS_PROFILE |
| AccessDeniedException | Enable model in Bedrock console |
| ExpiredTokenException | Run `aws sso login` to refresh |
| Region not set | `export AWS_REGION=us-east-1` |
