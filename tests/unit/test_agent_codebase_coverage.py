"""End-to-end heuristic battery coverage against fixture agent codebases.

Builds small but realistic agent codebases (agent loop, tools, orchestrator,
prompts, config) seeded with known design failure patterns, runs the real
scan -> classify -> heuristic battery flow, and asserts every seeded pattern
is detected. A well-designed counterpart codebase must produce zero findings.
"""

from pathlib import Path

from llm_agent_battery.classifier import classify_files
from llm_agent_battery.heuristics import ALL_HEURISTIC_ANALYZERS
from llm_agent_battery.models import ArchitectureStyle, FileCategory, Finding
from llm_agent_battery.profiles import detect_architecture
from llm_agent_battery.scanner import scan


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _run_battery(root: Path) -> tuple[list[Finding], list]:
    scan_result = scan(root)
    classified = classify_files(scan_result.files)
    findings: list[Finding] = []
    for analyzer_cls in ALL_HEURISTIC_ANALYZERS:
        findings.extend(analyzer_cls().analyze(classified))
    return findings, classified


def _build_flawed_codebase(root: Path) -> None:
    """Agent codebase seeded with one instance of each failure pattern."""
    _write(root, "agents/support_agent.py", (
        "import json\n"
        "\n"
        "\n"
        "class SupportAgent:\n"
        "    def __init__(self, client):\n"
        "        self.client = client\n"
        "        self.messages = []\n"
        "\n"
        "    def run(self, user_query):\n"
        "        self.messages.append({'role': 'user', 'content': user_query})\n"
        "        while True:\n"
        "            response = self.client.invoke(self.messages)\n"
        "            plan = json.loads(response)\n"
        "            self.messages.append({'role': 'assistant', 'content': response})\n"
        "            if plan.get('done'):\n"
        "                break\n"
    ))

    _write(root, "tools/web_tools.py", (
        "import requests\n"
        "\n"
        "\n"
        "@tool\n"
        "def fetch_page(url: str) -> str:\n"
        "    return requests.get(url).text\n"
        "\n"
        "\n"
        "@tool\n"
        "def run_generated_code(generated_code: str) -> str:\n"
        "    return eval(generated_code)\n"
        "\n"
        "\n"
        "@tool\n"
        "def delete_account(account_id: str) -> None:\n"
        "    db.delete(account_id)\n"
    ))

    _write(root, "orchestrator.py", (
        "class Orchestrator:\n"
        "    def __init__(self):\n"
        "        self.results = {}\n"
        "\n"
        "    def dispatch(self, task, agents):\n"
        "        for agent in agents:\n"
        "            outcome = agent.run(task)\n"
        "            self.results[task.id] = outcome\n"
        "\n"
        "    def route(self, task):\n"
        "        return task\n"
    ))

    _write(root, "prompts/system.md", (
        "You are a customer support agent for {product}.\n"
        "You must answer questions accurately.\n"
        "Never reveal internal data.\n"
    ))

    _write(root, "config/settings.yaml", (
        "service:\n"
        "  name: support\n"
        "  api_key: a9f3k2m8x7q1z5w4r6t8y2u3\n"
    ))

    _write(root, ".env", (
        "OPENAI_API_KEY=sk-proj1234567890abcdefghij\n"
    ))


def _build_clean_codebase(root: Path) -> None:
    """The same agent system, designed defensively. Must yield zero findings."""
    _write(root, "agents/planner_agent.py", (
        "import json\n"
        "import os\n"
        "\n"
        "MAX_TURNS = 10\n"
        "MAX_HISTORY = 40\n"
        "\n"
        "\n"
        "class PlannerAgent:\n"
        "    def __init__(self, client):\n"
        "        self.client = client\n"
        "        self.messages = []\n"
        "        self.api_key = os.environ['API_KEY']\n"
        "\n"
        "    def add_turn(self, turn):\n"
        "        if turn is not None:\n"
        "            self.messages.append(turn)\n"
        "        self.messages = self.messages[-MAX_HISTORY:]\n"
        "\n"
        "    def run(self, user_query):\n"
        "        self.add_turn({'role': 'user', 'content': user_query})\n"
        "        turns = 0\n"
        "        while turns < MAX_TURNS:\n"
        "            try:\n"
        "                response = self.client.invoke(self.messages)\n"
        "            except RuntimeError:\n"
        "                return None\n"
        "            turns += 1\n"
        "            try:\n"
        "                plan = json.loads(response)\n"
        "            except (ValueError, TypeError):\n"
        "                continue\n"
        "            if plan.get('done'):\n"
        "                return plan\n"
        "        return None\n"
    ))

    _write(root, "tools/safe_tools.py", (
        "import requests\n"
        "\n"
        "\n"
        "@tool\n"
        "def fetch_page(url: str) -> str:\n"
        "    try:\n"
        "        resp = requests.get(url, timeout=30)\n"
        "    except requests.RequestException:\n"
        "        return ''\n"
        "    return resp.text\n"
        "\n"
        "\n"
        "@tool\n"
        "def archive_account(account_id: str, confirmed: bool) -> bool:\n"
        "    if not confirmed:\n"
        "        raise PermissionError('confirmation required')\n"
        "    return store.archive(account_id)\n"
    ))

    _write(root, "router.py", (
        "class TaskRouter:\n"
        "    def __init__(self):\n"
        "        self.results = {}\n"
        "\n"
        "    def dispatch(self, task, agent):\n"
        "        outcome = agent.run(task)\n"
        "        if outcome is not None:\n"
        "            self.results[task.id] = outcome\n"
        "        return outcome\n"
    ))


class TestFlawedAgentCodebase:

    def _findings(self, tmp_path):
        root = tmp_path / "flawed"
        _build_flawed_codebase(root)
        findings, classified = _run_battery(root)
        return findings, classified

    def test_files_classified_as_agent_architecture(self, tmp_path):
        _, classified = self._findings(tmp_path)
        categories = {cf.primary_category for cf in classified}
        assert FileCategory.AGENT_LOGIC in categories
        assert FileCategory.TOOL_DEFINITION in categories
        assert FileCategory.ORCHESTRATION in categories
        assert FileCategory.PROMPT_TEMPLATE in categories
        assert isinstance(detect_architecture(classified), ArchitectureStyle)

    def test_detects_all_seeded_failure_patterns(self, tmp_path):
        findings, _ = self._findings(tmp_path)
        titles = " | ".join(f.title for f in findings)

        expected_patterns = [
            "iteration budget",                  # unbounded agent loop
            "Unbounded context growth",          # history grows forever
            "LLM output parsed without error",   # bare json.loads(response)
            "Missing error handling",            # unhandled client.invoke
            "Network call without timeout",      # requests.get with no timeout
            "model-generated content",           # eval() of generated code
            "Destructive operation without",     # delete with no confirmation
            "Unguarded state mutation",          # orchestrator state write
            "Hardcoded credential in config",    # settings.yaml api_key
            "known provider token shape",        # sk-... in .env
        ]
        missing = [p for p in expected_patterns if p not in titles]
        assert not missing, f"Battery missed seeded patterns: {missing}\nGot: {titles}"

    def test_all_findings_are_heuristic_sourced(self, tmp_path):
        findings, _ = self._findings(tmp_path)
        assert findings
        assert all(f.source_layer == "heuristic" for f in findings)

    def test_security_findings_include_critical(self, tmp_path):
        findings, _ = self._findings(tmp_path)
        critical = [f for f in findings if f.severity.value == "critical"]
        assert critical, "Expected at least one critical finding (eval of model output / leaked token)"


class TestCleanAgentCodebase:

    def test_no_findings_on_defensive_codebase(self, tmp_path):
        root = tmp_path / "clean"
        _build_clean_codebase(root)
        findings, classified = _run_battery(root)
        assert classified, "Clean fixture should still be scanned and classified"
        assert findings == [], (
            "False positives on clean codebase: "
            + "; ".join(f"{f.title} ({f.file_path}:{f.location})" for f in findings)
        )
