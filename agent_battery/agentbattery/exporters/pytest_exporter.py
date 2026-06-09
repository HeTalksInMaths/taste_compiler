"""pytest exporter - renders tests as pytest functions."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from agentbattery.models import GeneratedTest

logger = logging.getLogger(__name__)

_PYTEST_HEADER = '''"""Auto-generated test file from agentbattery findings.

These tests verify that agent safety gaps have been addressed.
Implement the AgentAdapter class to connect these tests to your agent.
"""

import pytest


class AgentAdapter:
    """Placeholder adapter - implement this to connect to your agent.

    Override methods to provide actual agent interaction:
    - run_scenario(setup): Execute a test scenario and return the trace
    - assert_tool_called(trace, tool_name): Verify a tool was called
    - assert_tool_not_called(trace, tool_name): Verify a tool was NOT called
    """

    def run_scenario(self, setup: dict) -> dict:
        """Run a test scenario and return the execution trace."""
        raise NotImplementedError("Implement AgentAdapter.run_scenario()")

    def assert_tool_called(self, trace: dict, tool_name: str) -> None:
        """Assert that a tool was called in the trace."""
        raise NotImplementedError("Implement AgentAdapter.assert_tool_called()")

    def assert_tool_not_called(self, trace: dict, tool_name: str) -> None:
        """Assert that a tool was NOT called in the trace."""
        raise NotImplementedError("Implement AgentAdapter.assert_tool_not_called()")


@pytest.fixture
def adapter():
    """Provide the agent adapter fixture."""
    return AgentAdapter()

'''


def _sanitize_function_name(test_id: str) -> str:
    """Convert a test ID to a valid Python function name."""
    # Replace non-alphanumeric chars with underscore
    name = re.sub(r"[^a-zA-Z0-9_]", "_", test_id)
    # Ensure it starts with test_
    if not name.startswith("test_"):
        name = f"test_{name}"
    return name


def _generate_test_function(test: GeneratedTest) -> str:
    """Generate a single pytest test function string."""
    func_name = _sanitize_function_name(test.id)
    lines: list[str] = []

    # Function definition with docstring
    lines.append(f"def {func_name}(adapter):")
    lines.append(f'    """Test: {test.title}')
    lines.append(f"")
    lines.append(f"    {test.description[:200]}")
    lines.append(f"    Finding ID: {test.finding_id}")
    lines.append(f"    Tags: {', '.join(test.tags)}")
    lines.append(f'    """')

    # Setup
    lines.append(f"    setup = {{")
    for key, value in test.setup.items():
        lines.append(f"        {key!r}: {value!r},")
    lines.append(f"    }}")
    lines.append(f"")

    # Run scenario
    lines.append(f"    trace = adapter.run_scenario(setup)")
    lines.append(f"")

    # Assertions
    for assertion in test.assertions:
        if assertion.startswith("must_call:"):
            tool_ref = assertion.split(":", 1)[1].strip()
            lines.append(f'    adapter.assert_tool_called(trace, {tool_ref!r})')
        elif assertion.startswith("must_not_call:"):
            tool_ref = assertion.split(":", 1)[1].strip()
            lines.append(f'    adapter.assert_tool_not_called(trace, {tool_ref!r})')
        else:
            lines.append(f"    # Assertion: {assertion}")

    lines.append(f"")
    lines.append(f"")
    return "\n".join(lines)


def export_pytest(tests: list[GeneratedTest], output_dir: Path) -> list[Path]:
    """Generate a single test_generated.py file with pytest test functions.

    Includes adapter imports and a placeholder adapter class.

    Args:
        tests: List of GeneratedTest objects to export.
        output_dir: Directory to write the test file to.

    Returns:
        List containing the single path to the generated test file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / "test_generated.py"

    content = _PYTEST_HEADER

    for test in tests:
        content += _generate_test_function(test)

    with open(file_path, "w") as f:
        f.write(content)

    logger.debug(f"Exported pytest tests: {file_path}")
    return [file_path]
