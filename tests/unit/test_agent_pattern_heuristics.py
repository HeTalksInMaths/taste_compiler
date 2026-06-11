"""Unit tests for llm_agent_battery.heuristics.agent_patterns analyzers."""

from pathlib import Path

from llm_agent_battery.heuristics import (
    ALL_HEURISTIC_ANALYZERS,
    HardcodedCredentialsAnalyzer,
    MissingTimeoutAnalyzer,
    UnboundedAgentLoopAnalyzer,
    UnboundedContextGrowthAnalyzer,
    UnsafeCodeExecutionAnalyzer,
    UnvalidatedLLMOutputAnalyzer,
)
from llm_agent_battery.models import ClassifiedFile, FileCategory


def _make_file(
    tmp_path: Path,
    content: str,
    name: str = "code.py",
    category: FileCategory = FileCategory.AGENT_LOGIC,
) -> ClassifiedFile:
    """Write content to a temp file and wrap it in a ClassifiedFile."""
    path = tmp_path / name
    path.write_text(content)
    return ClassifiedFile(
        path=path,
        relative_path=name,
        size_bytes=len(content),
        primary_category=category,
    )


class TestUnboundedAgentLoopAnalyzer:

    def test_detects_loop_with_no_exit(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run_agent():\n"
            "    while True:\n"
            "        response = llm.complete('next step')\n"
            "        print(response)\n"
        ))
        findings = UnboundedAgentLoopAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert "no exit path" in findings[0].title

    def test_detects_llm_loop_without_budget(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run_agent():\n"
            "    while True:\n"
            "        response = client.invoke('next step')\n"
            "        if response == 'done':\n"
            "            break\n"
        ))
        findings = UnboundedAgentLoopAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert "iteration budget" in findings[0].title

    def test_no_finding_with_iteration_budget(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run_agent(max_steps=10):\n"
            "    steps = 0\n"
            "    while True:\n"
            "        response = client.invoke('next step')\n"
            "        steps += 1\n"
            "        if response == 'done' or steps >= max_steps:\n"
            "            break\n"
        ))
        findings = UnboundedAgentLoopAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_ignores_bounded_while_loops(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run_agent(items):\n"
            "    while items:\n"
            "        response = client.invoke(items.pop())\n"
        ))
        findings = UnboundedAgentLoopAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_ignores_non_agent_files(self, tmp_path):
        cf = _make_file(
            tmp_path,
            "def run():\n    while True:\n        client.invoke('x')\n",
            category=FileCategory.CONFIGURATION,
        )
        findings = UnboundedAgentLoopAnalyzer().analyze([cf])
        assert len(findings) == 0


class TestMissingTimeoutAnalyzer:

    def test_detects_requests_without_timeout(self, tmp_path):
        cf = _make_file(
            tmp_path,
            "def fetch(url):\n    return requests.get(url)\n",
            category=FileCategory.TOOL_DEFINITION,
        )
        findings = MissingTimeoutAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert "requests.get" in findings[0].title

    def test_no_finding_with_timeout(self, tmp_path):
        cf = _make_file(
            tmp_path,
            "def fetch(url):\n    return requests.get(url, timeout=30)\n",
            category=FileCategory.TOOL_DEFINITION,
        )
        findings = MissingTimeoutAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_no_finding_with_kwargs_splat(self, tmp_path):
        cf = _make_file(
            tmp_path,
            "def fetch(url, **kw):\n    return requests.get(url, **kw)\n",
            category=FileCategory.TOOL_DEFINITION,
        )
        findings = MissingTimeoutAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_detects_urlopen_without_timeout(self, tmp_path):
        cf = _make_file(
            tmp_path,
            "def fetch(url):\n    return urllib.request.urlopen(url)\n",
            category=FileCategory.TOOL_DEFINITION,
        )
        findings = MissingTimeoutAnalyzer().analyze([cf])
        assert len(findings) == 1


class TestUnsafeCodeExecutionAnalyzer:

    def test_detects_eval_of_llm_output(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run(llm_response):\n"
            "    return eval(llm_response)\n"
        ))
        findings = UnsafeCodeExecutionAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert findings[0].severity.value == "critical"
        assert "model-generated" in findings[0].title

    def test_detects_exec_of_dynamic_value(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run(snippet):\n"
            "    exec(snippet)\n"
        ))
        findings = UnsafeCodeExecutionAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert findings[0].severity.value == "high"

    def test_detects_subprocess_shell_true(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run(cmd):\n"
            "    subprocess.run(cmd, shell=True)\n"
        ))
        findings = UnsafeCodeExecutionAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert "Shell execution" in findings[0].title

    def test_detects_os_system_dynamic(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run(cmd):\n"
            "    os.system(cmd)\n"
        ))
        findings = UnsafeCodeExecutionAnalyzer().analyze([cf])
        assert len(findings) == 1

    def test_no_finding_for_static_commands(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def run():\n"
            "    subprocess.run('ls -la', shell=True)\n"
            "    eval('1 + 1')\n"
        ))
        findings = UnsafeCodeExecutionAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_skips_test_files(self, tmp_path):
        cf = _make_file(
            tmp_path,
            "def run(cmd):\n    eval(cmd)\n",
            category=FileCategory.TEST,
        )
        findings = UnsafeCodeExecutionAnalyzer().analyze([cf])
        assert len(findings) == 0


class TestUnboundedContextGrowthAnalyzer:

    def test_detects_unbounded_history_append(self, tmp_path):
        cf = _make_file(tmp_path, (
            "class Agent:\n"
            "    def chat(self, msg):\n"
            "        self.messages.append({'role': 'user', 'content': msg})\n"
        ))
        findings = UnboundedContextGrowthAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert "messages" in findings[0].title

    def test_no_finding_with_truncation_strategy(self, tmp_path):
        cf = _make_file(tmp_path, (
            "MAX_HISTORY = 50\n"
            "class Agent:\n"
            "    def chat(self, msg):\n"
            "        self.messages.append({'role': 'user', 'content': msg})\n"
            "        self.messages = self.messages[-MAX_HISTORY:]\n"
        ))
        findings = UnboundedContextGrowthAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_detects_augassign_growth(self, tmp_path):
        cf = _make_file(tmp_path, (
            "class Agent:\n"
            "    def chat(self, turn):\n"
            "        self.history += [turn]\n"
        ))
        findings = UnboundedContextGrowthAnalyzer().analyze([cf])
        assert len(findings) == 1

    def test_ignores_non_context_lists(self, tmp_path):
        cf = _make_file(tmp_path, (
            "class Agent:\n"
            "    def record(self, item):\n"
            "        self.errors.append(item)\n"
        ))
        findings = UnboundedContextGrowthAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_dedupes_per_variable(self, tmp_path):
        cf = _make_file(tmp_path, (
            "class Agent:\n"
            "    def chat(self, msg):\n"
            "        self.messages.append(msg)\n"
            "    def reply(self, msg):\n"
            "        self.messages.append(msg)\n"
        ))
        findings = UnboundedContextGrowthAnalyzer().analyze([cf])
        assert len(findings) == 1


class TestHardcodedCredentialsAnalyzer:

    def test_detects_named_secret_assignment(self, tmp_path):
        cf = _make_file(
            tmp_path,
            'api_key = "a1b2c3d4e5f6g7h8i9j0"\n',
        )
        findings = HardcodedCredentialsAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert "api_key" in findings[0].title

    def test_detects_provider_token_shape(self, tmp_path):
        cf = _make_file(
            tmp_path,
            'KEY = "sk-abcdefghij1234567890ABCD"\n',
        )
        findings = HardcodedCredentialsAnalyzer().analyze([cf])
        assert any(f.severity.value == "critical" for f in findings)

    def test_detects_config_file_secret(self, tmp_path):
        cf = _make_file(
            tmp_path,
            "service:\n  api_key: a1b2c3d4e5f6g7h8i9j0\n",
            name="settings.yaml",
            category=FileCategory.CONFIGURATION,
        )
        findings = HardcodedCredentialsAnalyzer().analyze([cf])
        assert len(findings) == 1

    def test_ignores_placeholders_and_env_lookups(self, tmp_path):
        cf = _make_file(tmp_path, (
            'api_key = "${OPENAI_API_KEY}"\n'
            'secret = "your-secret-here-12345"\n'
            'token = os.environ["TOKEN"]\n'
        ))
        findings = HardcodedCredentialsAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_ignores_short_values(self, tmp_path):
        cf = _make_file(tmp_path, 'token_type = "Bearer"\n')
        findings = HardcodedCredentialsAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_skips_test_files(self, tmp_path):
        cf = _make_file(
            tmp_path,
            'api_key = "a1b2c3d4e5f6g7h8i9j0"\n',
            category=FileCategory.TEST,
        )
        findings = HardcodedCredentialsAnalyzer().analyze([cf])
        assert len(findings) == 0


class TestUnvalidatedLLMOutputAnalyzer:

    def test_detects_bare_json_loads_on_response(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def parse(response):\n"
            "    data = json.loads(response)\n"
            "    return data\n"
        ))
        findings = UnvalidatedLLMOutputAnalyzer().analyze([cf])
        assert len(findings) == 1
        assert "without error handling" in findings[0].title

    def test_no_finding_when_wrapped_in_try(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def parse(response):\n"
            "    try:\n"
            "        return json.loads(response)\n"
            "    except json.JSONDecodeError:\n"
            "        return None\n"
        ))
        findings = UnvalidatedLLMOutputAnalyzer().analyze([cf])
        assert len(findings) == 0

    def test_ignores_non_llm_values(self, tmp_path):
        cf = _make_file(tmp_path, (
            "def load(config_str):\n"
            "    return json.loads(config_str)\n"
        ))
        findings = UnvalidatedLLMOutputAnalyzer().analyze([cf])
        assert len(findings) == 0


class TestBatteryRegistry:

    def test_all_analyzers_registered(self):
        assert len(ALL_HEURISTIC_ANALYZERS) == 10

    def test_every_analyzer_runs_clean_on_empty_input(self):
        for analyzer_cls in ALL_HEURISTIC_ANALYZERS:
            assert analyzer_cls().analyze([]) == []
