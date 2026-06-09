"""Unit tests for the file classifier module."""

from pathlib import Path

import pytest

from llm_agent_battery.classifier import classify_file, classify_files
from llm_agent_battery.models import ClassifiedFile, ClassifyConfig, DiscoveredFile, FileCategory


def _make_file(tmp_path: Path, name: str, content: str = "") -> DiscoveredFile:
    """Helper to create a DiscoveredFile backed by a real file on disk."""
    filepath = tmp_path / name
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content)
    return DiscoveredFile(
        path=filepath.resolve(),
        relative_path=name,
        size_bytes=len(content.encode()),
    )


class TestContentBasedAgentLogic:
    """Content-based detection of AGENT_LOGIC files."""

    def test_agent_class_pattern(self, tmp_path: Path) -> None:
        """Files with class XAgent are classified as AGENT_LOGIC."""
        f = _make_file(tmp_path, "my_agent.py", "class MyAgent:\n    pass\n")
        result = classify_file(f)
        assert result.primary_category == FileCategory.AGENT_LOGIC

    def test_bot_class_pattern(self, tmp_path: Path) -> None:
        """Files with class XBot are classified as AGENT_LOGIC."""
        f = _make_file(tmp_path, "chatbot.py", "class ChatBot:\n    pass\n")
        result = classify_file(f)
        assert result.primary_category == FileCategory.AGENT_LOGIC

    def test_langchain_import(self, tmp_path: Path) -> None:
        """Files importing langchain are classified as AGENT_LOGIC."""
        content = "from langchain.agents import AgentExecutor\n"
        f = _make_file(tmp_path, "chain.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.AGENT_LOGIC

    def test_autogen_import(self, tmp_path: Path) -> None:
        """Files importing autogen are classified as AGENT_LOGIC."""
        content = "import autogen\n\nconfig = autogen.Config()\n"
        f = _make_file(tmp_path, "multi.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.AGENT_LOGIC

    def test_crewai_import(self, tmp_path: Path) -> None:
        """Files importing crewai are classified as AGENT_LOGIC."""
        content = "from crewai import Agent, Task\n"
        f = _make_file(tmp_path, "crew.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.AGENT_LOGIC


class TestContentBasedToolDefinition:
    """Content-based detection of TOOL_DEFINITION files."""

    def test_tool_decorator(self, tmp_path: Path) -> None:
        """Files with @tool decorator are classified as TOOL_DEFINITION."""
        content = "@tool\ndef search(query: str) -> str:\n    pass\n"
        f = _make_file(tmp_path, "search_tool.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TOOL_DEFINITION

    def test_function_tool_decorator(self, tmp_path: Path) -> None:
        """Files with @function_tool decorator are classified as TOOL_DEFINITION."""
        content = "@function_tool\ndef calc(x: int) -> int:\n    return x * 2\n"
        f = _make_file(tmp_path, "calc.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TOOL_DEFINITION

    def test_tool_class(self, tmp_path: Path) -> None:
        """Files with Tool class definition are classified as TOOL_DEFINITION."""
        content = "class SearchTool:\n    def run(self): pass\n"
        f = _make_file(tmp_path, "tools.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TOOL_DEFINITION

    def test_base_tool_inheritance(self, tmp_path: Path) -> None:
        """Files inheriting BaseTool are classified as TOOL_DEFINITION."""
        content = "class MyTool(BaseTool):\n    name = 'my_tool'\n"
        f = _make_file(tmp_path, "custom.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TOOL_DEFINITION


class TestContentBasedOrchestration:
    """Content-based detection of ORCHESTRATION files."""

    def test_orchestrator_class(self, tmp_path: Path) -> None:
        """Files with Orchestrator class are classified as ORCHESTRATION."""
        content = "class AgentOrchestrator:\n    def run(self): pass\n"
        f = _make_file(tmp_path, "orch.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.ORCHESTRATION

    def test_router_class(self, tmp_path: Path) -> None:
        """Files with Router class are classified as ORCHESTRATION."""
        content = "class TaskRouter:\n    def route(self, task): pass\n"
        f = _make_file(tmp_path, "router.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.ORCHESTRATION

    def test_multiple_orchestration_keywords(self, tmp_path: Path) -> None:
        """Files with multiple orchestration keywords are classified as ORCHESTRATION."""
        content = "def dispatch_task(task):\n    route = find_route(task)\n    delegate(route)\n"
        f = _make_file(tmp_path, "flow.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.ORCHESTRATION


class TestContentBasedStateManagement:
    """Content-based detection of STATE_MANAGEMENT files."""

    def test_state_class(self, tmp_path: Path) -> None:
        """Files with State class are classified as STATE_MANAGEMENT."""
        content = "class ConversationState:\n    messages: list = []\n"
        f = _make_file(tmp_path, "state.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.STATE_MANAGEMENT

    def test_state_machine(self, tmp_path: Path) -> None:
        """Files with StateMachine pattern are classified as STATE_MANAGEMENT."""
        content = "from transitions import StateMachine\n\nsm = StateMachine()\n"
        f = _make_file(tmp_path, "fsm.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.STATE_MANAGEMENT


class TestContentBasedPromptTemplate:
    """Content-based detection of PROMPT_TEMPLATE files."""

    def test_markdown_with_template_vars(self, tmp_path: Path) -> None:
        """Markdown files with {var} patterns are classified as PROMPT_TEMPLATE."""
        content = "You are a {role} agent.\nPlease help the user with {task}.\n"
        f = _make_file(tmp_path, "system.md", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.PROMPT_TEMPLATE

    def test_python_prompt_variable(self, tmp_path: Path) -> None:
        """Python files with prompt template strings are classified as PROMPT_TEMPLATE."""
        content = 'system_prompt = "You are a {role} assistant. Help with {task}."\n'
        f = _make_file(tmp_path, "prompts.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.PROMPT_TEMPLATE


class TestContentBasedTest:
    """Content-based detection of TEST files."""

    def test_pytest_import(self, tmp_path: Path) -> None:
        """Files importing pytest are classified as TEST."""
        content = "import pytest\n\ndef test_hello():\n    assert True\n"
        f = _make_file(tmp_path, "test_main.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TEST

    def test_unittest_import(self, tmp_path: Path) -> None:
        """Files importing unittest are classified as TEST."""
        content = "import unittest\n\nclass TestFoo(unittest.TestCase):\n    pass\n"
        f = _make_file(tmp_path, "tests.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TEST

    def test_test_function_pattern(self, tmp_path: Path) -> None:
        """Files with test_ functions are classified as TEST."""
        content = "def test_addition():\n    assert 1 + 1 == 2\n"
        f = _make_file(tmp_path, "checks.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TEST


class TestContentBasedConfiguration:
    """Content-based detection of CONFIGURATION files."""

    def test_yaml_file(self, tmp_path: Path) -> None:
        """YAML files are classified as CONFIGURATION."""
        f = _make_file(tmp_path, "settings.yaml", "debug: true\nport: 8080\n")
        result = classify_file(f)
        assert result.primary_category == FileCategory.CONFIGURATION

    def test_json_file(self, tmp_path: Path) -> None:
        """JSON files are classified as CONFIGURATION."""
        f = _make_file(tmp_path, "package.json", '{"name": "app"}')
        result = classify_file(f)
        assert result.primary_category == FileCategory.CONFIGURATION

    def test_toml_file(self, tmp_path: Path) -> None:
        """TOML files are classified as CONFIGURATION."""
        f = _make_file(tmp_path, "pyproject.toml", "[tool.pytest]\n")
        result = classify_file(f)
        assert result.primary_category == FileCategory.CONFIGURATION

    def test_python_config_class(self, tmp_path: Path) -> None:
        """Python files with Config class are classified as CONFIGURATION."""
        content = "class AppConfig:\n    debug = True\n    port = 8080\n"
        f = _make_file(tmp_path, "config.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.CONFIGURATION


class TestContentBasedInfrastructure:
    """Content-based detection of INFRASTRUCTURE files."""

    def test_dockerfile(self, tmp_path: Path) -> None:
        """Dockerfiles are classified as INFRASTRUCTURE."""
        f = _make_file(tmp_path, "Dockerfile", "FROM python:3.11\nCOPY . /app\n")
        result = classify_file(f)
        assert result.primary_category == FileCategory.INFRASTRUCTURE

    def test_docker_compose(self, tmp_path: Path) -> None:
        """docker-compose.yml is classified as INFRASTRUCTURE."""
        content = "version: '3'\nservices:\n  app:\n    build: .\n"
        f = _make_file(tmp_path, "docker-compose.yml", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.INFRASTRUCTURE


class TestPathBasedFallback:
    """Path-based heuristic fallback when content heuristics don't match."""

    def test_tests_directory(self, tmp_path: Path) -> None:
        """Files in tests/ directory fall back to TEST category."""
        content = "def helper(): return 42\n"
        f = _make_file(tmp_path, "tests/conftest.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TEST

    def test_prompts_directory(self, tmp_path: Path) -> None:
        """Files in prompts/ directory fall back to PROMPT_TEMPLATE."""
        content = "Some plain text instructions.\n"
        f = _make_file(tmp_path, "prompts/intro.txt", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.PROMPT_TEMPLATE

    def test_tools_directory(self, tmp_path: Path) -> None:
        """Files in tools/ directory fall back to TOOL_DEFINITION."""
        content = "def do_something(): pass\n"
        f = _make_file(tmp_path, "tools/helper.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TOOL_DEFINITION

    def test_config_directory(self, tmp_path: Path) -> None:
        """Files in config/ directory fall back to CONFIGURATION."""
        content = "# some config\nDEBUG = True\n"
        f = _make_file(tmp_path, "config/env.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.CONFIGURATION


class TestContentOverPathPriority:
    """Content-based heuristics take priority over path-based."""

    def test_agent_in_tools_dir(self, tmp_path: Path) -> None:
        """A file in tools/ with agent class is classified by content as AGENT_LOGIC."""
        content = "from langchain.agents import AgentExecutor\nclass MyAgent: pass\n"
        f = _make_file(tmp_path, "tools/agent_helper.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.AGENT_LOGIC

    def test_test_file_in_config_dir(self, tmp_path: Path) -> None:
        """A test file in config/ is classified by content as TEST."""
        content = "import pytest\n\ndef test_config_load():\n    assert True\n"
        f = _make_file(tmp_path, "config/test_settings.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.TEST


class TestUnknownCategory:
    """Files that don't match any heuristic get UNKNOWN."""

    def test_plain_python_file(self, tmp_path: Path) -> None:
        """A plain Python file with no signals is UNKNOWN."""
        content = "x = 42\ny = x + 1\n"
        f = _make_file(tmp_path, "misc.py", content)
        result = classify_file(f)
        assert result.primary_category == FileCategory.UNKNOWN


class TestSecondaryCategories:
    """Files can have secondary categories."""

    def test_agent_with_tool_decorator(self, tmp_path: Path) -> None:
        """A file with both agent and tool patterns gets secondary categories."""
        content = "from langchain.agents import AgentExecutor\n\n@tool\ndef search(): pass\n"
        f = _make_file(tmp_path, "agent_tools.py", content)
        result = classify_file(f)
        # Primary should be the first matching (TEST checks first, then INFRA, then AGENT_LOGIC)
        assert result.primary_category == FileCategory.AGENT_LOGIC
        assert FileCategory.TOOL_DEFINITION in result.secondary_categories


class TestClassifyFiles:
    """Tests for the batch classify_files function."""

    def test_classify_multiple_files(self, tmp_path: Path) -> None:
        """classify_files processes a list of DiscoveredFiles."""
        files = [
            _make_file(tmp_path, "agent.py", "class ChatAgent: pass\n"),
            _make_file(tmp_path, "config.yaml", "key: val\n"),
        ]
        results = classify_files(files)
        assert len(results) == 2
        assert results[0].primary_category == FileCategory.AGENT_LOGIC
        assert results[1].primary_category == FileCategory.CONFIGURATION

    def test_classify_files_with_config(self, tmp_path: Path) -> None:
        """classify_files accepts a ClassifyConfig."""
        files = [_make_file(tmp_path, "app.py", "x = 1\n")]
        config = ClassifyConfig(fast_mode=True)
        results = classify_files(files, config=config)
        assert len(results) == 1
        assert results[0].primary_category == FileCategory.UNKNOWN

    def test_classify_empty_list(self) -> None:
        """classify_files handles empty input."""
        results = classify_files([])
        assert results == []


class TestClassifyConfig:
    """Tests for ClassifyConfig behavior."""

    def test_fast_mode_skips_llm(self, tmp_path: Path) -> None:
        """Fast mode still classifies using heuristics (no LLM needed)."""
        content = "import pytest\ndef test_x(): pass\n"
        f = _make_file(tmp_path, "test_foo.py", content)
        config = ClassifyConfig(fast_mode=True)
        result = classify_file(f, config)
        # Even in fast mode, content heuristics still work
        assert result.primary_category == FileCategory.TEST

    def test_default_config_none(self, tmp_path: Path) -> None:
        """When config is None, default ClassifyConfig is used."""
        f = _make_file(tmp_path, "agent.py", "class MyBot: pass\n")
        result = classify_file(f, config=None)
        assert result.primary_category == FileCategory.AGENT_LOGIC
