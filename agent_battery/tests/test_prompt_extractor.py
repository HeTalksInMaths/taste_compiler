"""Unit tests for the prompt extractor module."""

from pathlib import Path

from agentbattery.models import ClassifiedFile, FileCategory
from agentbattery.prompt_extractor import extract_prompts


def _make_classified_file(
    path: Path, relative_path: str, category: FileCategory = FileCategory.PROMPT
) -> ClassifiedFile:
    """Helper to create a ClassifiedFile for testing."""
    size = path.stat().st_size if path.exists() else 0
    return ClassifiedFile(
        path=path,
        relative_path=relative_path,
        size_bytes=size,
        primary_category=category,
    )


class TestMarkdownExtraction:
    """Tests for Markdown file prompt extraction."""

    def test_extracts_full_markdown_content(self, tmp_path: Path):
        """Markdown files should have their full text content extracted."""
        md_file = tmp_path / "system_prompt.md"
        md_file.write_text("You are a helpful assistant.\nAlways be polite.")

        file = _make_classified_file(md_file, "system_prompt.md")
        results = extract_prompts([file])

        assert len(results) == 1
        assert results[0].text == "You are a helpful assistant.\nAlways be polite."
        assert results[0].source_path == "system_prompt.md"
        assert results[0].metadata["format"] == "markdown"

    def test_empty_markdown_returns_no_artifacts(self, tmp_path: Path):
        """An empty Markdown file should produce no artifacts."""
        md_file = tmp_path / "empty.md"
        md_file.write_text("")

        file = _make_classified_file(md_file, "empty.md")
        results = extract_prompts([file])

        assert len(results) == 0


class TestYamlExtraction:
    """Tests for YAML file prompt extraction."""

    def test_extracts_system_prompt_key(self, tmp_path: Path):
        """YAML files should extract content from system_prompt key."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "system_prompt: You are a customer service agent.\n"
            "model: gpt-4\n"
        )

        file = _make_classified_file(yaml_file, "config.yaml")
        results = extract_prompts([file])

        assert len(results) == 1
        assert results[0].text == "You are a customer service agent."
        assert results[0].metadata["key"] == "system_prompt"

    def test_extracts_multiple_prompt_keys(self, tmp_path: Path):
        """YAML files should extract from all known prompt keys."""
        yaml_file = tmp_path / "prompts.yml"
        yaml_file.write_text(
            "system_prompt: Be helpful.\n"
            "instructions: Follow these rules.\n"
            "unrelated_key: ignore this\n"
        )

        file = _make_classified_file(yaml_file, "prompts.yml")
        results = extract_prompts([file])

        assert len(results) == 2
        texts = {r.text for r in results}
        assert "Be helpful." in texts
        assert "Follow these rules." in texts

    def test_skips_non_string_values(self, tmp_path: Path):
        """YAML keys with non-string values should be skipped."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("prompt:\n  - item1\n  - item2\ncontent: Real prompt.\n")

        file = _make_classified_file(yaml_file, "config.yaml")
        results = extract_prompts([file])

        assert len(results) == 1
        assert results[0].text == "Real prompt."

    def test_invalid_yaml_is_skipped(self, tmp_path: Path):
        """Invalid YAML files should be skipped without crashing."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("{{invalid: yaml: content: [")

        file = _make_classified_file(yaml_file, "bad.yaml")
        results = extract_prompts([file])

        assert len(results) == 0


class TestPythonExtraction:
    """Tests for Python file prompt extraction."""

    def test_extracts_system_prompt_variable(self, tmp_path: Path):
        """Python files should extract from SYSTEM_PROMPT variables."""
        py_file = tmp_path / "prompts.py"
        py_file.write_text(
            'SYSTEM_PROMPT = """You are an AI assistant."""\n'
        )

        file = _make_classified_file(py_file, "prompts.py")
        results = extract_prompts([file])

        assert len(results) == 1
        assert results[0].text == "You are an AI assistant."
        assert results[0].metadata["variable"] == "SYSTEM_PROMPT"

    def test_extracts_prompt_function_docstring(self, tmp_path: Path):
        """Python files should extract docstrings from prompt-named functions."""
        py_file = tmp_path / "agent.py"
        py_file.write_text(
            "def get_system_prompt():\n"
            '    """You are a helpful agent. Always confirm before acting."""\n'
            "    return None\n"
        )

        file = _make_classified_file(py_file, "agent.py")
        results = extract_prompts([file])

        assert len(results) == 1
        assert "helpful agent" in results[0].text
        assert results[0].metadata["function"] == "get_system_prompt"

    def test_syntax_error_is_skipped(self, tmp_path: Path):
        """Python files with syntax errors should be skipped without crashing."""
        py_file = tmp_path / "bad.py"
        py_file.write_text("def broken(:\n    pass\n")

        file = _make_classified_file(py_file, "bad.py")
        results = extract_prompts([file])

        assert len(results) == 0


class TestResiliency:
    """Tests for extraction resilience."""

    def test_unreadable_file_is_skipped(self, tmp_path: Path):
        """Files that cannot be read should be skipped without crashing."""
        nonexistent = tmp_path / "does_not_exist.md"

        file = _make_classified_file(nonexistent, "does_not_exist.md")
        results = extract_prompts([file])

        assert len(results) == 0

    def test_mixed_files_with_failures(self, tmp_path: Path):
        """Mixed valid and invalid files should process valid ones."""
        good_file = tmp_path / "good.md"
        good_file.write_text("Valid prompt content.")

        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{{invalid yaml")

        files = [
            _make_classified_file(good_file, "good.md"),
            _make_classified_file(bad_file, "bad.yaml"),
        ]
        results = extract_prompts(files)

        assert len(results) == 1
        assert results[0].text == "Valid prompt content."
