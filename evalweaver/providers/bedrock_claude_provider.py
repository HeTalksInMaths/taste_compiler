"""AWS Bedrock Claude provider using boto3 Bedrock Runtime Converse API.

This provider calls Claude via AWS Bedrock to generate scorers, pairs,
candidates, and mutations. It is NOT required for local testing —
MockProvider is the default.

Requirements:
    pip install 'evalweaver[aws]'
    AWS credentials configured (env vars, profile, or IAM role)
"""

import json
import os
import time
from typing import Optional


class BedrockClaudeProvider:
    """
    AgentProvider implementation using AWS Bedrock Runtime Converse API.

    Usage:
        provider = BedrockClaudeProvider(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            aws_region="us-east-1",
        )
    """

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        aws_region: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        profile_name: Optional[str] = None,
    ):
        self._model_id = model_id
        self._aws_region = aws_region or os.environ.get("AWS_REGION", "us-east-1")
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._profile_name = profile_name
        self._client = None
        self._last_call_meta = None
        self._last_prompt = None
        self._last_raw_response = None

    @property
    def provider_name(self) -> str:
        return "bedrock-claude"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def aws_region(self) -> str:
        return self._aws_region

    @property
    def last_call_meta(self) -> Optional[dict]:
        """Return metadata from the last _converse call."""
        return self._last_call_meta

    @property
    def last_prompt(self) -> Optional[dict]:
        """Return the prompt from the last _converse call."""
        return self._last_prompt

    @property
    def last_raw_response(self) -> Optional[str]:
        """Return the raw text response from the last _converse call."""
        return self._last_raw_response

    def validate_credentials(self):
        """Validate AWS credentials are configured. Returns caller identity dict."""
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for BedrockClaudeProvider.\n"
                "Install with: pip install 'evalweaver[aws]'\n"
                "Then configure credentials:\n"
                "  aws configure sso\n"
                "  export AWS_PROFILE=next-sandbox\n"
                "  export AWS_REGION=us-east-1"
            )
        try:
            session = boto3.Session(
                profile_name=self._profile_name,
                region_name=self._aws_region,
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
                f"  # or\n"
                f"  aws configure --profile next-sandbox\n"
                f"  export AWS_PROFILE=next-sandbox\n"
                f"  export AWS_REGION=us-east-1\n"
                f"  aws sts get-caller-identity\n"
            ) from e

    def _get_client(self):
        """Lazy-init the Bedrock Runtime client with standard retry config."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError:
                raise ImportError(
                    "boto3 is required for BedrockClaudeProvider.\n"
                    "Install with: pip install 'evalweaver[aws]'\n"
                    "Then configure credentials:\n"
                    "  aws configure sso\n"
                    "  export AWS_PROFILE=next-sandbox\n"
                    "  export AWS_REGION=us-east-1"
                )
            session = boto3.Session(
                profile_name=self._profile_name,
                region_name=self._aws_region,
            )
            boto_config = Config(
                retries={"mode": "standard", "max_attempts": 5},
                connect_timeout=10,
                read_timeout=300,
            )
            self._client = session.client("bedrock-runtime", config=boto_config)
        return self._client

    def _converse(self, system_prompt: str, user_message: str) -> str:
        """
        Call Bedrock Runtime Converse API and return the text response.

        Uses the Converse API (not InvokeModel) for cross-model compatibility.
        Records call metadata (latency, retries) on self._last_call_meta.
        Stores prompt and raw response for artifact capture.
        """
        client = self._get_client()
        error_str = None
        self._last_prompt = {"system": system_prompt, "user": user_message}
        start_time = time.time()
        try:
            response = client.converse(
                modelId=self._model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_message}],
                    }
                ],
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "maxTokens": self._max_tokens,
                    "temperature": self._temperature,
                },
            )
        except Exception as e:
            end_time = time.time()
            latency_ms = round((end_time - start_time) * 1000, 1)
            error_str = str(e)
            self._last_call_meta = {
                "latency_ms": latency_ms,
                "retry_mode": "standard",
                "max_attempts": 5,
                "error": error_str,
            }
            self._last_raw_response = None
            raise
        end_time = time.time()
        latency_ms = round((end_time - start_time) * 1000, 1)
        self._last_call_meta = {
            "latency_ms": latency_ms,
            "retry_mode": "standard",
            "max_attempts": 5,
            "error": None,
        }
        # Extract text from response
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        if content and content[0].get("text"):
            response_text = content[0]["text"]
        else:
            response_text = ""
        self._last_raw_response = response_text
        return response_text

    def _parse_json_response(self, response_text: str) -> dict:
        """Extract JSON from a model response (handles markdown code blocks)."""
        text = response_text.strip()
        # Try to extract JSON from markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
            else:
                # No closing backticks (response may be truncated) - take everything after ```json
                text = text[start:].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
            else:
                text = text[start:].strip()
        return json.loads(text)

    def generate_research(self, goal: str, raw_text: str) -> dict:
        """Generate taste research via Bedrock Claude."""
        system = (
            "You are an NLP research assistant. Generate research on linguistic and "
            "psychological features related to the given text quality goal. "
            "Return a JSON object with 3 keys: linguistic features, NLP measurable "
            "properties, and failure modes. Each value is a multi-line research summary."
        )
        user = (
            f"Goal: {goal}\n"
            f"Raw text: {raw_text}\n\n"
            "Generate comprehensive research covering:\n"
            "1. Linguistic features associated with this quality goal\n"
            "2. NLP-measurable text properties for this goal\n"
            "3. Failure modes and backfire effects\n\n"
            "Return as JSON with 3 keys."
        )
        response = self._converse(system, user)
        return self._parse_json_response(response)

    def generate_taste_map(self, goal: str, research: dict) -> dict:
        """Generate taste map via Bedrock Claude."""
        system = (
            "You are an NLP research synthesizer. Create a structured taste map "
            "from the provided research. Return JSON with keys: goal, rewards (list), "
            "punishes (list), preserves (list), key_tensions (list of strings), "
            "scorer_hypothesis_seeds (list of strings)."
        )
        user = (
            f"Goal: {goal}\n"
            f"Research:\n{json.dumps(research, indent=2)}\n\n"
            "Synthesize into a taste map with rewards (>=3), punishes (>=1), "
            "preserves (>=1), key_tensions, and scorer_hypothesis_seeds."
        )
        response = self._converse(system, user)
        return self._parse_json_response(response)

    def generate_scorer_hypotheses(self, taste_map: dict, nlp_theory: dict, count: int) -> list:
        """Generate scorer hypotheses via Bedrock Claude."""
        system = (
            "You are a scorer designer. Generate scorer hypotheses that combine "
            "NLP probes to measure text quality. Each hypothesis should specify: "
            "scorer_id, lineage, hypothesis, research_basis, taste_map_basis, "
            "expected_failure_mode, constants_and_thresholds. Return as JSON array."
        )
        user = (
            f"Taste map:\n{json.dumps(taste_map, indent=2)}\n\n"
            f"NLP theory:\n{json.dumps(nlp_theory, indent=2)}\n\n"
            f"Generate {count} distinct scorer hypotheses as a JSON array."
        )
        response = self._converse(system, user)
        return self._parse_json_response(response)

    def generate_scorer_code(self, hypothesis: dict) -> str:
        """Generate scorer code via Bedrock Claude."""
        system = (
            "You are a Python code generator. Write a scorer function that implements "
            "the given hypothesis. The function must be named 'scorer' and accept "
            "(text, anchor, params). It should use the available probe functions and "
            "return a float in [0.0, 1.0]. Use _clamp() for output bounding."
        )
        user = (
            f"Hypothesis:\n{json.dumps(hypothesis, indent=2)}\n\n"
            "Write the Python scorer function. Available probes: "
            "violates_hard_source_policy, probe_source_continuity, "
            "probe_argument_progression, probe_real_mechanism_quality, "
            "probe_abstract_jargon_density, probe_specificity_without_invention, "
            "probe_causal_density, probe_specificity, probe_audience_relevance, "
            "probe_persuasion_risk, probe_epistemic_calibration, "
            "probe_mechanism_result_alignment.\n\n"
            "Return ONLY the Python code (no markdown, no explanation)."
        )
        response = self._converse(system, user)
        # Strip any markdown formatting
        code = response.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    def generate_pairs(self, taste_map: dict, scorer_weaknesses: dict, count: int) -> list:
        """Generate evaluation pairs via Bedrock Claude."""
        system = (
            "You are an evaluation pair designer. Generate text pairs for testing "
            "text quality scorers. Each pair has: pair_id, anchor, positive, negative, "
            "pair_type (hype_trap/fake_mechanism/specificity_trap/subtle_quality_gap/"
            "source_drift), source_policy, label_contract, intended_trap. "
            "Return as JSON array."
        )
        user = (
            f"Taste map:\n{json.dumps(taste_map, indent=2)}\n\n"
            f"Scorer weaknesses:\n{json.dumps(scorer_weaknesses, indent=2)}\n\n"
            f"Generate {count} diverse evaluation pairs as a JSON array."
        )
        # Pairs need more tokens due to verbose text content
        old_max = self._max_tokens
        self._max_tokens = max(old_max, 16384)
        try:
            response = self._converse(system, user)
        finally:
            self._max_tokens = old_max
        return self._parse_json_response(response)

    def generate_mutations(self, failure_packet: dict, count: int) -> list:
        """Generate evolved scorer hypotheses via Bedrock Claude."""
        system = (
            "You are a scorer evolution specialist. Given a failure analysis of "
            "existing scorers, generate evolved hypotheses that address the identified "
            "weaknesses. Use lineage types: mutation, blind_node_repair, recombination, "
            "novel_composition. Return as JSON array."
        )
        user = (
            f"Failure packet:\n{json.dumps(failure_packet, indent=2, default=str)}\n\n"
            f"Generate {count} evolved scorer hypotheses as a JSON array."
        )
        response = self._converse(system, user)
        return self._parse_json_response(response)

    def generate_candidates(self, goal: str, raw_text: str, taste_map: dict, count: int) -> list:
        """Generate candidate rewrites via Bedrock Claude."""
        system = (
            "You are a copywriter. Rewrite the given text to be better at the "
            "specified quality goal. Generate multiple distinct strategies. "
            "Each candidate: candidate_id, strategy, text. Return as JSON array."
        )
        user = (
            f"Goal: {goal}\n"
            f"Original text: {raw_text}\n"
            f"Taste map summary: {json.dumps(taste_map.get('rewards', []), indent=2)}\n\n"
            f"Generate {count} candidate rewrites with different strategies as JSON array."
        )
        response = self._converse(system, user)
        return self._parse_json_response(response)
