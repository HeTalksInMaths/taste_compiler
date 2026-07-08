"""AWS Bedrock client with async support, retry logic, and token tracking.

Wraps the Bedrock Runtime Converse API following the pattern from
evalweaver/providers/bedrock_claude_provider.py, adapted for async usage.
Uses asyncio.to_thread for boto3 calls since boto3 isn't async-native.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from llm_agent_battery.models import ConcurrencyConfig, InferenceConfig, TokenUsage

logger = logging.getLogger(__name__)


# Error codes that should be retried with exponential backoff
_RETRYABLE_CODES = {"ThrottlingException", "TooManyRequestsException", "ServiceUnavailableException"}
_RETRYABLE_HTTP_CODES = {429, 500, 503}

# Error codes that should fail immediately without retry
_NON_RETRYABLE_HTTP_CODES = {400, 403}


class BedrockClient:
    """Async Bedrock Runtime client with retry, timeout, and token tracking.

    Usage:
        client = BedrockClient()
        client.validate_credentials()
        response = await client.converse("You are helpful.", "Analyze this code.")
    """

    def __init__(
        self,
        config: InferenceConfig | None = None,
        concurrency_config: ConcurrencyConfig | None = None,
    ):
        self._config = config or InferenceConfig()
        self._concurrency_config = concurrency_config or ConcurrencyConfig()
        self._client = None
        self._usage = TokenUsage()

    def _get_client(self):
        """Lazy-initialize the Bedrock Runtime client."""
        if self._client is None:
            import boto3

            session = boto3.Session(
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
                profile_name=os.environ.get("AWS_PROFILE"),
            )
            boto_config = BotoConfig(
                connect_timeout=self._config.connect_timeout,
                read_timeout=self._config.read_timeout,
                retries={"max_attempts": 0},  # We handle retries ourselves
            )
            self._client = session.client("bedrock-runtime", config=boto_config)
        return self._client

    def validate_credentials(self) -> dict:
        """Validate AWS credentials via STS. Returns caller identity dict.

        Raises:
            ImportError: If boto3 is not installed.
            RuntimeError: If credentials are invalid or not configured.
        """
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for BedrockClient.\n"
                "Install with: pip install boto3\n"
                "Then configure credentials:\n"
                "  aws configure sso\n"
                "  export AWS_PROFILE=your-profile\n"
                "  export AWS_REGION=us-east-1"
            )
        try:
            session = boto3.Session(
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
                profile_name=os.environ.get("AWS_PROFILE"),
            )
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            return {
                "account": identity["Account"],
                "arn": identity["Arn"],
                "user_id": identity["UserId"],
            }
        except Exception as e:
            raise RuntimeError(
                f"AWS credentials not configured or invalid.\n"
                f"Error: {e}\n\n"
                f"Setup instructions:\n"
                f"  aws configure sso\n"
                f"  export AWS_PROFILE=your-profile\n"
                f"  export AWS_REGION=us-east-1\n"
                f"  aws sts get-caller-identity\n"
            ) from e

    async def converse(self, system: str, user: str) -> str:
        """Send a message to Bedrock Converse API with retry logic.

        Args:
            system: System prompt text.
            user: User message text.

        Returns:
            The model's text response.

        Raises:
            RuntimeError: If all retries are exhausted or a non-retryable error occurs.
        """
        max_retries = self._concurrency_config.max_retries
        backoff_base = self._concurrency_config.backoff_base

        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(self._invoke_converse, system, user)
                self._track_usage(response)
                return self._extract_text(response)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                http_status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)

                if self._is_non_retryable(error_code, http_status):
                    raise RuntimeError(
                        f"Non-retryable Bedrock error (HTTP {http_status}, {error_code}): {e}"
                    ) from e

                if self._is_retryable(error_code, http_status):
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = backoff_base ** attempt
                        logger.warning(
                            f"Retryable error (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {delay:.1f}s: {error_code}"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Unknown error type — treat as non-retryable
                raise RuntimeError(
                    f"Bedrock API error (HTTP {http_status}, {error_code}): {e}"
                ) from e

            except (TimeoutError, OSError) as e:
                # Network-level transient errors — retryable
                last_error = e
                if attempt < max_retries - 1:
                    delay = backoff_base ** attempt
                    logger.warning(
                        f"Transient error (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s: {type(e).__name__}: {e}"
                    )
                    await asyncio.sleep(delay)
                    continue

        raise RuntimeError(
            f"All {max_retries} retry attempts exhausted. Last error: {last_error}"
        )

    def _invoke_converse(self, system: str, user: str) -> dict:
        """Synchronous Bedrock Converse API call (run in thread)."""
        client = self._get_client()
        return client.converse(
            modelId=self._config.model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": user}],
                }
            ],
            system=[{"text": system}],
            inferenceConfig={
                "maxTokens": self._config.max_tokens,
                "temperature": self._config.temperature,
            },
        )

    def _extract_text(self, response: dict) -> str:
        """Extract text content from the Converse API response."""
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        if content and content[0].get("text"):
            return content[0]["text"]
        return ""

    def _track_usage(self, response: dict) -> None:
        """Accumulate token usage from the response metadata."""
        usage = response.get("usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        self._usage.input_tokens += input_tokens
        self._usage.output_tokens += output_tokens
        self._usage.total_tokens = self._usage.input_tokens + self._usage.output_tokens

    @property
    def total_usage(self) -> TokenUsage:
        """Return accumulated token usage across all calls."""
        return self._usage

    @staticmethod
    def _is_retryable(error_code: str, http_status: int) -> bool:
        """Determine if an error is retryable."""
        if error_code in _RETRYABLE_CODES:
            return True
        if http_status in _RETRYABLE_HTTP_CODES:
            return True
        return False

    @staticmethod
    def _is_non_retryable(error_code: str, http_status: int) -> bool:
        """Determine if an error should fail immediately."""
        if http_status in _NON_RETRYABLE_HTTP_CODES:
            return True
        return False
