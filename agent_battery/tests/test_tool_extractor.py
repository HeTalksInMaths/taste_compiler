"""Unit tests for the tool extractor module."""

import json
from pathlib import Path

from agentbattery.models import ClassifiedFile, FileCategory
from agentbattery.tool_extractor import extract_tools


def _make_classified_file(
    path: Path,
    relative_path: str,
    category: FileCategory = FileCategory.TOOL_SOURCE,
) -> ClassifiedFile:
    """Helper to create a ClassifiedFile for testing."""
    size = path.stat().st_size if path.exists() else 0
    return ClassifiedFile(
        path=path,
        relative_path=relative_path,
        size_bytes=size,
        primary_category=category,
    )


class TestPythonDecoratedTools:
    """Tests for Python AST-based tool extraction with decorators."""

    def test_finds_tool_decorated_function(self, tmp_path: Path):
        """Functions with @tool decorator should be extracted."""
        py_file = tmp_path / "tools.py"
        py_file.write_text(
            "from some_lib import tool\n\n"
            "@tool\n"
            "def send_email(to: str, subject: str, body: str) -> bool:\n"
            '    """Send an email to a recipient."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "tools.py")
        results = extract_tools([file])

        assert len(results) == 1
        assert results[0].name == "send_email"
        assert results[0].description == "Send an email to a recipient."
        assert len(results[0].parameters) == 3
        assert results[0].parameters[0].name == "to"
        assert results[0].parameters[0].type == "str"
        assert results[0].return_type == "bool"

    def test_finds_function_tool_decorator(self, tmp_path: Path):
        """Functions with @function_tool decorator should be extracted."""
        py_file = tmp_path / "tools.py"
        py_file.write_text(
            "@function_tool\n"
            "def delete_record(record_id: int) -> None:\n"
            '    """Delete a record by ID."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "tools.py")
        results = extract_tools([file])

        assert len(results) == 1
        assert results[0].name == "delete_record"

    def test_finds_agent_tool_decorator(self, tmp_path: Path):
        """Functions with @agent.tool decorator should be extracted."""
        py_file = tmp_path / "agent_tools.py"
        py_file.write_text(
            "class Agent:\n"
            "    pass\n\n"
            "agent = Agent()\n\n"
            "@agent.tool\n"
            "def create_task(title: str, priority: int = 1) -> dict:\n"
            '    """Create a new task."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "agent_tools.py")
        results = extract_tools([file])

        assert len(results) == 1
        assert results[0].name == "create_task"
        assert results[0].parameters[1].required is False


class TestPythonUndecoratedTools:
    """Tests for undecorated tool-like function detection."""

    def test_finds_send_email_function(self, tmp_path: Path):
        """Functions named send_email should be detected as tools."""
        py_file = tmp_path / "email.py"
        py_file.write_text(
            "def send_email(recipient: str, message: str) -> bool:\n"
            '    """Send an email. Requires confirmation before sending."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "email.py")
        results = extract_tools([file])

        assert len(results) == 1
        assert results[0].name == "send_email"
        assert "confirmation" in results[0].preconditions[0].lower()

    def test_finds_delete_prefixed_functions(self, tmp_path: Path):
        """Functions with delete_ prefix should be detected as tools."""
        py_file = tmp_path / "ops.py"
        py_file.write_text(
            "def delete_user(user_id: int) -> None:\n"
            '    """Delete a user account permanently."""\n'
            "    pass\n\n"
            "def delete_file(path: str) -> bool:\n"
            '    """Delete a file from storage."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "ops.py")
        results = extract_tools([file])

        assert len(results) == 2
        names = {r.name for r in results}
        assert "delete_user" in names
        assert "delete_file" in names

    def test_non_tool_functions_ignored(self, tmp_path: Path):
        """Regular functions that don't match patterns should be ignored."""
        py_file = tmp_path / "utils.py"
        py_file.write_text(
            "def helper_function(x: int) -> int:\n"
            '    """A helper."""\n'
            "    return x * 2\n\n"
            "def process_data(data: list) -> list:\n"
            '    """Process some data."""\n'
            "    return data\n"
        )

        file = _make_classified_file(py_file, "utils.py")
        results = extract_tools([file])

        assert len(results) == 0


class TestJsonSchemaExtraction:
    """Tests for JSON schema-based tool extraction."""

    def test_parses_openai_style_schema(self, tmp_path: Path):
        """OpenAI-style function schemas should be parsed correctly."""
        schema = {
            "functions": [
                {
                    "name": "send_message",
                    "description": "Send a message to a user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "Target user ID",
                            },
                            "text": {
                                "type": "string",
                                "description": "Message content",
                                "minLength": 1,
                            },
                        },
                        "required": ["user_id", "text"],
                    },
                }
            ]
        }

        json_file = tmp_path / "tools.json"
        json_file.write_text(json.dumps(schema))

        file = _make_classified_file(
            json_file, "tools.json", FileCategory.TOOL_SCHEMA
        )
        results = extract_tools([file])

        assert len(results) == 1
        assert results[0].name == "send_message"
        assert results[0].description == "Send a message to a user."
        assert len(results[0].parameters) == 2
        assert results[0].parameters[0].name == "user_id"
        assert results[0].parameters[0].required is True
        assert results[0].parameters[1].constraints == {"minLength": 1}

    def test_parses_anthropic_style_schema(self, tmp_path: Path):
        """Anthropic-style tool schemas should be parsed correctly."""
        schema = {
            "tools": [
                {
                    "name": "web_search",
                    "description": "Search the web for information.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Max results to return",
                            },
                        },
                        "required": ["query"],
                    },
                }
            ]
        }

        json_file = tmp_path / "anthropic_tools.json"
        json_file.write_text(json.dumps(schema))

        file = _make_classified_file(
            json_file, "anthropic_tools.json", FileCategory.TOOL_SCHEMA
        )
        results = extract_tools([file])

        assert len(results) == 1
        assert results[0].name == "web_search"
        assert results[0].parameters[0].required is True
        assert results[0].parameters[1].required is False

    def test_invalid_json_is_skipped(self, tmp_path: Path):
        """Invalid JSON files should be skipped without crashing."""
        json_file = tmp_path / "bad.json"
        json_file.write_text("{invalid json content")

        file = _make_classified_file(
            json_file, "bad.json", FileCategory.TOOL_SCHEMA
        )
        results = extract_tools([file])

        assert len(results) == 0


class TestPreconditionInference:
    """Tests for precondition inference from docstrings."""

    def test_infers_confirmation_precondition(self, tmp_path: Path):
        """Docstrings mentioning confirmation should produce preconditions."""
        py_file = tmp_path / "tools.py"
        py_file.write_text(
            "@tool\n"
            "def send_payment(amount: float, recipient: str) -> bool:\n"
            '    """Send payment. Requires confirmation from user before executing."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "tools.py")
        results = extract_tools([file])

        assert len(results) == 1
        assert len(results[0].preconditions) > 0

    def test_infers_approval_precondition(self, tmp_path: Path):
        """Docstrings mentioning approval should produce preconditions."""
        py_file = tmp_path / "tools.py"
        py_file.write_text(
            "@tool\n"
            "def deploy_service(env: str) -> bool:\n"
            '    """Deploy to environment. Must be approved by team lead."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "tools.py")
        results = extract_tools([file])

        assert len(results) == 1
        assert len(results[0].preconditions) > 0

    def test_no_preconditions_for_simple_tools(self, tmp_path: Path):
        """Simple tools without precondition language should have empty preconditions."""
        py_file = tmp_path / "tools.py"
        py_file.write_text(
            "@tool\n"
            "def get_weather(city: str) -> str:\n"
            '    """Get the current weather for a city."""\n'
            "    pass\n"
        )

        file = _make_classified_file(py_file, "tools.py")
        results = extract_tools([file])

        assert len(results) == 1
        assert len(results[0].preconditions) == 0


class TestResiliency:
    """Tests for extraction resilience."""

    def test_python_syntax_error_skipped(self, tmp_path: Path):
        """Python files with syntax errors should be skipped."""
        py_file = tmp_path / "broken.py"
        py_file.write_text("@tool\ndef broken(:\n    pass\n")

        file = _make_classified_file(py_file, "broken.py")
        results = extract_tools([file])

        assert len(results) == 0

    def test_nonexistent_file_skipped(self, tmp_path: Path):
        """Nonexistent files should be skipped."""
        missing = tmp_path / "missing.py"

        file = _make_classified_file(missing, "missing.py")
        results = extract_tools([file])

        assert len(results) == 0
