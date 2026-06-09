"""Unit tests for llm_agent_battery.heuristics module."""

import tempfile
from pathlib import Path

from llm_agent_battery.heuristics import (
    MissingConfirmationGateAnalyzer,
    MissingErrorHandlingAnalyzer,
    PromptInjectionAnalyzer,
    UnguardedMutationAnalyzer,
)
from llm_agent_battery.models import ClassifiedFile, FileCategory


def _make_file(content: str, name: str = "code.py", category: FileCategory = FileCategory.AGENT_LOGIC):
    """Helper to create a temp file and ClassifiedFile."""
    import tempfile as tf
    tmp = tf.NamedTemporaryFile(suffix=".py", mode="w", delete=False, prefix=name.replace(".", "_"))
    tmp.write(content)
    tmp.flush()
    return ClassifiedFile(
        path=Path(tmp.name),
        relative_path=name,
        size_bytes=len(content),
        primary_category=category,
    )


class TestMissingErrorHandlingAnalyzer:
    """Tests for MissingErrorHandlingAnalyzer."""

    def test_detects_unhandled_client_call(self):
        cf = _make_file(
            "def process():\n    result = client.invoke('tool')\n    return result\n",
            category=FileCategory.AGENT_LOGIC,
        )
        analyzer = MissingErrorHandlingAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) >= 1
        assert "client.invoke" in findings[0].title

    def test_no_findings_when_wrapped_in_try(self):
        cf = _make_file(
            "def process():\n    try:\n        result = client.invoke('tool')\n    except Exception:\n        pass\n",
            category=FileCategory.AGENT_LOGIC,
        )
        analyzer = MissingErrorHandlingAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0

    def test_ignores_non_external_calls(self):
        cf = _make_file(
            "def process():\n    x = len([1, 2, 3])\n    return x\n",
            category=FileCategory.AGENT_LOGIC,
        )
        analyzer = MissingErrorHandlingAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0

    def test_ignores_test_files(self):
        cf = _make_file(
            "def process():\n    result = client.invoke('tool')\n",
            category=FileCategory.TEST,
        )
        analyzer = MissingErrorHandlingAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0


class TestUnguardedMutationAnalyzer:
    """Tests for UnguardedMutationAnalyzer."""

    def test_detects_unguarded_append(self):
        cf = _make_file(
            "class State:\n    def add(self):\n        self.items.append('x')\n",
            category=FileCategory.STATE_MANAGEMENT,
        )
        analyzer = UnguardedMutationAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) >= 1
        assert "self.items.append()" in findings[0].title

    def test_no_finding_when_guarded(self):
        cf = _make_file(
            "class State:\n    def add(self, x):\n        if x is not None:\n            self.items.append(x)\n",
            category=FileCategory.STATE_MANAGEMENT,
        )
        analyzer = UnguardedMutationAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0

    def test_detects_subscript_assignment(self):
        cf = _make_file(
            "class State:\n    def set(self):\n        self.data['key'] = 'value'\n",
            category=FileCategory.STATE_MANAGEMENT,
        )
        analyzer = UnguardedMutationAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) >= 1


class TestMissingConfirmationGateAnalyzer:
    """Tests for MissingConfirmationGateAnalyzer."""

    def test_detects_destructive_without_confirm(self):
        cf = _make_file(
            "def cleanup():\n    delete_records()\n    remove_files()\n",
            category=FileCategory.AGENT_LOGIC,
        )
        analyzer = MissingConfirmationGateAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) >= 1
        assert findings[0].category.value == "security"

    def test_no_finding_with_confirmation(self):
        cf = _make_file(
            "def cleanup():\n    if confirm('sure?'):\n        delete_records()\n",
            category=FileCategory.AGENT_LOGIC,
        )
        analyzer = MissingConfirmationGateAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0

    def test_skips_test_files(self):
        cf = _make_file(
            "def test_cleanup():\n    delete_records()\n",
            category=FileCategory.TEST,
        )
        analyzer = MissingConfirmationGateAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0


class TestPromptInjectionAnalyzer:
    """Tests for PromptInjectionAnalyzer."""

    def test_detects_fstring_injection(self):
        cf = _make_file(
            'def build(user_input):\n    prompt = f"Act as: {user_input}"\n    return prompt\n',
            category=FileCategory.AGENT_LOGIC,
        )
        analyzer = PromptInjectionAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) >= 1
        assert "injection" in findings[0].title.lower()

    def test_no_finding_without_user_input(self):
        cf = _make_file(
            'def build():\n    prompt = f"Hello {name}"\n    return prompt\n',
            category=FileCategory.AGENT_LOGIC,
        )
        analyzer = PromptInjectionAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0

    def test_ignores_non_prompt_files(self):
        cf = _make_file(
            'def build(user_input):\n    prompt = f"Act as: {user_input}"\n',
            category=FileCategory.CONFIGURATION,
        )
        analyzer = PromptInjectionAnalyzer()
        findings = analyzer.analyze([cf])
        assert len(findings) == 0
