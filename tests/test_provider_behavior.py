"""Tests for provider behavior honesty and S3 upload."""
import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from evalweaver.config import load_config
from evalweaver.pipeline import run_pipeline
from evalweaver.artifacts import reset_trace, upload_to_s3


class TestProviderHonesty:
    """Provider mode produces correct metadata."""

    def test_metadata_only_makes_zero_bedrock_calls(self):
        """--provider bedrock without --generate-step makes 0 calls."""
        reset_trace()
        config = load_config("configs/persuasive.yaml")
        config["provider_name"] = "bedrock"
        config["model_id"] = "us.anthropic.claude-sonnet-4-6"
        config["provider_generation_enabled"] = False
        config["bedrock_validation_passed"] = True

        out_dir = tempfile.mkdtemp(prefix="ew_test_")
        os.environ["EVALWEAVER_OUTPUT_DIR"] = out_dir
        try:
            result = run_pipeline(config)
            with open(os.path.join(out_dir, "run_summary_v5.json")) as f:
                summary = json.load(f)
            meta = summary["run_metadata"]
            assert meta["provider_generation_enabled"] is False
            assert meta["bedrock_calls_made"] == 0
            assert meta["generated_steps"] == []
        finally:
            os.environ.pop("EVALWEAVER_OUTPUT_DIR", None)
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_live_bedrock_failure_does_not_silently_fallback(self):
        """If --generate-step research fails, pipeline raises, not fallback to mock."""
        reset_trace()
        config = load_config("configs/persuasive.yaml")
        config["provider_name"] = "bedrock"
        config["model_id"] = "us.anthropic.claude-sonnet-4-6"
        config["provider_generation_enabled"] = True
        config["generate_step"] = "research"
        config["bedrock_validation_passed"] = True

        out_dir = tempfile.mkdtemp(prefix="ew_test_")
        os.environ["EVALWEAVER_OUTPUT_DIR"] = out_dir
        try:
            # Mock the provider to raise an error
            with patch("evalweaver.providers.bedrock_claude_provider.BedrockClaudeProvider") as MockProvider:
                instance = MockProvider.return_value
                instance.generate_research.side_effect = RuntimeError("Bedrock unavailable")
                instance._last_call_meta = None
                with pytest.raises(RuntimeError, match="Bedrock generation failed"):
                    run_pipeline(config)
        finally:
            os.environ.pop("EVALWEAVER_OUTPUT_DIR", None)
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)


class TestS3Upload:
    """S3 upload writes expected artifact keys."""

    def test_s3_upload_calls_with_correct_keys(self):
        """upload_to_s3 uploads all files with correct prefix."""
        # Create a fake output dir with some files
        out_dir = tempfile.mkdtemp(prefix="ew_s3_test_")
        try:
            # Create fake artifacts
            for name in ["step1_raw_research.json", "run_summary_v5.json", "evalweaver_v51_outputs.zip"]:
                with open(os.path.join(out_dir, name), "w") as f:
                    f.write("{}")

            with patch("boto3.Session") as MockSession:
                mock_s3 = MagicMock()
                MockSession.return_value.client.return_value = mock_s3

                result = upload_to_s3(out_dir, "my-bucket", "persuasive-20250610-abc12345", "us-east-1")

                assert result["bucket"] == "my-bucket"
                assert result["prefix"] == "runs/persuasive-20250610-abc12345"
                assert result["zip_s3_key"] == "runs/persuasive-20250610-abc12345/evalweaver_outputs.zip"
                assert result["uploaded_count"] >= 3

                # Verify upload_file was called
                assert mock_s3.upload_file.call_count >= 3
        finally:
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)
