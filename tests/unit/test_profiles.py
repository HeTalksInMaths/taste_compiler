"""Unit tests for llm_agent_battery.profiles module."""

import tempfile
from pathlib import Path

import pytest

from llm_agent_battery.models import ArchitectureStyle, ClassifiedFile, FileCategory
from llm_agent_battery.profiles import detect_architecture, load_profile


class TestLoadProfile:
    """Tests for load_profile function."""

    def test_load_single_agent(self):
        profile = load_profile("single-agent")
        assert profile.name == "single-agent"
        assert profile.architecture_style == ArchitectureStyle.SINGLE_AGENT
        assert len(profile.focus_areas) > 0
        assert len(profile.anti_patterns) > 0
        assert len(profile.system_prompt_template) > 0

    def test_load_multi_agent(self):
        profile = load_profile("multi-agent")
        assert profile.name == "multi-agent"
        assert profile.architecture_style == ArchitectureStyle.MULTI_AGENT

    def test_load_pipeline_sequential(self):
        profile = load_profile("pipeline-sequential")
        assert profile.name == "pipeline-sequential"
        assert profile.architecture_style == ArchitectureStyle.PIPELINE_SEQUENTIAL

    def test_load_reactive(self):
        profile = load_profile("reactive")
        assert profile.name == "reactive"
        assert profile.architecture_style == ArchitectureStyle.REACTIVE_EVENT_DRIVEN

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_profile("does-not-exist")

    def test_load_custom_yaml(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write(
                "name: custom\n"
                "architecture_style: single-agent\n"
                "system_prompt_template: 'Test prompt'\n"
                "focus_areas:\n  - area1\n"
                "anti_patterns:\n  - pattern1\n"
            )
            f.flush()
            profile = load_profile(f.name)
            assert profile.name == "custom"
            assert profile.architecture_style == ArchitectureStyle.SINGLE_AGENT

    def test_load_invalid_yaml_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("name: test\n")
            f.flush()
            with pytest.raises(ValueError, match="missing required fields"):
                load_profile(f.name)


class TestDetectArchitecture:
    """Tests for detect_architecture function."""

    def test_multiple_orchestration_files_yields_multi_agent(self):
        files = [
            ClassifiedFile(path=Path("/f/a.py"), relative_path="a.py", size_bytes=100, primary_category=FileCategory.ORCHESTRATION),
            ClassifiedFile(path=Path("/f/b.py"), relative_path="b.py", size_bytes=100, primary_category=FileCategory.ORCHESTRATION),
        ]
        assert detect_architecture(files) == ArchitectureStyle.MULTI_AGENT

    def test_default_is_single_agent(self):
        files = [
            ClassifiedFile(path=Path("/f/a.py"), relative_path="a.py", size_bytes=100, primary_category=FileCategory.AGENT_LOGIC),
        ]
        assert detect_architecture(files) == ArchitectureStyle.SINGLE_AGENT

    def test_empty_files_yields_single_agent(self):
        assert detect_architecture([]) == ArchitectureStyle.SINGLE_AGENT

    def test_pipeline_path_pattern(self):
        files = [
            ClassifiedFile(path=Path("/f/pipeline.py"), relative_path="pipeline.py", size_bytes=100, primary_category=FileCategory.AGENT_LOGIC),
        ]
        assert detect_architecture(files) == ArchitectureStyle.PIPELINE_SEQUENTIAL

    def test_reactive_path_pattern(self):
        files = [
            ClassifiedFile(path=Path("/f/event_handler.py"), relative_path="event_handler.py", size_bytes=100, primary_category=FileCategory.AGENT_LOGIC),
        ]
        assert detect_architecture(files) == ArchitectureStyle.REACTIVE_EVENT_DRIVEN
