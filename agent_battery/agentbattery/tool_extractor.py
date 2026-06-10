"""Tool extractor module - extracts tool definitions from source and schemas."""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path

import yaml

from agentbattery.models import ClassifiedFile, ToolArtifact, ToolParameter

logger = logging.getLogger(__name__)

# Decorator names that indicate a function is a tool
_TOOL_DECORATORS = {"tool", "function_tool"}

# Patterns for undecorated functions that look like tools
_TOOL_FUNCTION_PATTERN = re.compile(
    r"^(send_\w+|delete_\w+|create_\w+|update_\w+|remove_\w+|"
    r"post_\w+|publish_\w+|submit_\w+|execute_\w+|deploy_\w+|"
    r"transfer_\w+|write_\w+|drop_\w+|terminate_\w+|revoke_\w+|"
    r"send_email|read_inbox|lookup_\w+|fetch_\w+|search_\w+|"
    r"get_\w+|list_\w+|query_\w+|issue_\w+|check_\w+|"
    r"refund_\w+|approve_\w+|cancel_\w+|"
    r"notify_\w+|log_\w+|cache_\w+|tag_\w+|mark_\w+)$"
)

# Keywords that suggest preconditions in docstrings
_PRECONDITION_KEYWORDS = re.compile(
    r"\b(confirm|confirmed|approved|verified|permission|"
    r"requires?\s+(?:confirmation|approval|verification|permission)|"
    r"must\s+(?:confirm|approve|verify)|"
    r"before\s+(?:sending|executing|deleting|removing))\b",
    re.IGNORECASE,
)


def _read_file_content(path: Path) -> str | None:
    """Read file content, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logger.warning("Failed to read file %s: %s", path, e)
        return None


def _is_tool_decorator(node: ast.expr) -> bool:
    """Check if a decorator node matches a tool decorator pattern."""
    # @tool or @function_tool
    if isinstance(node, ast.Name) and node.id in _TOOL_DECORATORS:
        return True
    # @tool(...) or @function_tool(...)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _TOOL_DECORATORS:
            return True
        # @agent.tool or @agent.tool(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "tool":
            return True
    # @agent.tool (without call)
    if isinstance(node, ast.Attribute) and node.attr == "tool":
        return True
    return False


def _extract_parameters_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ToolParameter]:
    """Extract parameters from a function definition's annotations."""
    params: list[ToolParameter] = []

    for arg in node.args.args:
        if arg.arg == "self":
            continue

        param_type = "Any"
        if arg.annotation:
            param_type = ast.unparse(arg.annotation)

        params.append(
            ToolParameter(
                name=arg.arg,
                type=param_type,
                required=True,
                description="",
            )
        )

    # Mark parameters with defaults as not required
    num_defaults = len(node.args.defaults)
    if num_defaults > 0:
        for param in params[-num_defaults:]:
            param.required = False

    return params


def _extract_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract the return type annotation from a function."""
    if node.returns:
        return ast.unparse(node.returns)
    return "Any"


def _infer_preconditions(docstring: str | None) -> list[str]:
    """Infer preconditions from docstring content."""
    if not docstring:
        return []

    preconditions: list[str] = []
    matches = _PRECONDITION_KEYWORDS.findall(docstring)
    for match in matches:
        preconditions.append(match.strip())

    return preconditions


def _extract_tools_from_python(file: ClassifiedFile) -> list[ToolArtifact]:
    """Extract tool definitions from a Python file using AST parsing.

    Finds:
    - Functions with @tool, @function_tool, @agent.tool decorators
    - Undecorated functions that look like tools (send_email, delete_*, etc.)
    """
    content = _read_file_content(file.path)
    if not content:
        return []

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.warning("Failed to parse Python file %s: %s", file.path, e)
        return []

    artifacts: list[ToolArtifact] = []
    seen_names: set[str] = set()

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Skip private/internal functions
        if node.name.startswith("_"):
            continue

        is_decorated_tool = any(
            _is_tool_decorator(dec) for dec in node.decorator_list
        )
        is_tool_like = _TOOL_FUNCTION_PATTERN.match(node.name) is not None

        if not is_decorated_tool and not is_tool_like:
            continue

        if node.name in seen_names:
            continue
        seen_names.add(node.name)

        docstring = ast.get_docstring(node) or ""
        parameters = _extract_parameters_from_function(node)
        return_type = _extract_return_type(node)
        preconditions = _infer_preconditions(docstring)

        artifacts.append(
            ToolArtifact(
                name=node.name,
                description=docstring,
                parameters=parameters,
                return_type=return_type,
                source_path=file.relative_path,
                preconditions=preconditions,
            )
        )

    return artifacts


def _extract_tools_from_openai_schema(
    data: dict | list, source_path: str
) -> list[ToolArtifact]:
    """Extract tools from OpenAI-style function schema.

    Looks for structures like:
    - {"functions": [{"name": ..., "parameters": {...}}]}
    - [{"name": ..., "parameters": {...}}]  (list of functions)
    """
    artifacts: list[ToolArtifact] = []

    functions: list[dict] = []
    if isinstance(data, dict):
        functions = data.get("functions", [])
        if not functions:
            # Also check top-level tools list with function key
            tools = data.get("tools", [])
            for tool in tools:
                if isinstance(tool, dict) and "function" in tool:
                    functions.append(tool["function"])
    elif isinstance(data, list):
        functions = data

    for func in functions:
        if not isinstance(func, dict):
            continue
        if "name" not in func:
            continue
        if "parameters" not in func:
            continue

        name = func["name"]
        description = func.get("description", "")
        params_schema = func.get("parameters", {})
        parameters = _parse_json_schema_params(params_schema)
        preconditions = _infer_preconditions(description)

        artifacts.append(
            ToolArtifact(
                name=name,
                description=description,
                parameters=parameters,
                return_type="Any",
                source_path=source_path,
                preconditions=preconditions,
            )
        )

    return artifacts


def _extract_tools_from_anthropic_schema(
    data: dict | list, source_path: str
) -> list[ToolArtifact]:
    """Extract tools from Anthropic-style tool schema.

    Looks for structures like:
    - {"tools": [{"name": ..., "input_schema": {...}}]}
    """
    artifacts: list[ToolArtifact] = []

    tools: list[dict] = []
    if isinstance(data, dict):
        tools = data.get("tools", [])
    elif isinstance(data, list):
        tools = data

    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if "name" not in tool:
            continue
        if "input_schema" not in tool:
            continue

        name = tool["name"]
        description = tool.get("description", "")
        input_schema = tool.get("input_schema", {})
        parameters = _parse_json_schema_params(input_schema)
        preconditions = _infer_preconditions(description)

        artifacts.append(
            ToolArtifact(
                name=name,
                description=description,
                parameters=parameters,
                return_type="Any",
                source_path=source_path,
                preconditions=preconditions,
            )
        )

    return artifacts


def _parse_json_schema_params(schema: dict) -> list[ToolParameter]:
    """Parse JSON Schema properties into ToolParameter objects."""
    params: list[ToolParameter] = []

    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue

        param_type = prop.get("type", "Any")
        description = prop.get("description", "")
        is_required = name in required_fields

        # Collect constraints
        constraints: dict = {}
        for key in ("enum", "minLength", "maxLength", "minimum", "maximum", "pattern"):
            if key in prop:
                constraints[key] = prop[key]

        params.append(
            ToolParameter(
                name=name,
                type=param_type,
                required=is_required,
                description=description,
                constraints=constraints,
            )
        )

    return params


def _extract_tools_from_json(file: ClassifiedFile) -> list[ToolArtifact]:
    """Extract tool definitions from a JSON schema file."""
    content = _read_file_content(file.path)
    if not content:
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON file %s: %s", file.path, e)
        return []

    artifacts: list[ToolArtifact] = []

    # Try OpenAI-style first
    openai_tools = _extract_tools_from_openai_schema(data, file.relative_path)
    if openai_tools:
        artifacts.extend(openai_tools)

    # Try Anthropic-style
    anthropic_tools = _extract_tools_from_anthropic_schema(data, file.relative_path)
    if anthropic_tools:
        artifacts.extend(anthropic_tools)

    return artifacts


def _extract_tools_from_yaml(file: ClassifiedFile) -> list[ToolArtifact]:
    """Extract tool definitions from a YAML schema file."""
    content = _read_file_content(file.path)
    if not content:
        return []

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        logger.warning("Failed to parse YAML file %s: %s", file.path, e)
        return []

    if not isinstance(data, (dict, list)):
        return []

    artifacts: list[ToolArtifact] = []

    # Try OpenAI-style
    openai_tools = _extract_tools_from_openai_schema(data, file.relative_path)
    if openai_tools:
        artifacts.extend(openai_tools)

    # Try Anthropic-style
    anthropic_tools = _extract_tools_from_anthropic_schema(data, file.relative_path)
    if anthropic_tools:
        artifacts.extend(anthropic_tools)

    return artifacts


def extract_tools(files: list[ClassifiedFile]) -> list[ToolArtifact]:
    """Extract tool definitions from TOOL_SOURCE and TOOL_SCHEMA files.

    Handles:
    - Python files: AST parsing for decorated and tool-like functions
    - JSON files: OpenAI-style and Anthropic-style schema detection
    - YAML files: OpenAI-style and Anthropic-style schema detection

    Args:
        files: List of ClassifiedFile objects (filtered to TOOL_SOURCE and TOOL_SCHEMA).

    Returns:
        List of ToolArtifact objects with extracted tool definitions.
    """
    artifacts: list[ToolArtifact] = []

    for file in files:
        try:
            suffix = file.path.suffix.lower()

            if suffix == ".py":
                artifacts.extend(_extract_tools_from_python(file))
            elif suffix == ".json":
                artifacts.extend(_extract_tools_from_json(file))
            elif suffix in (".yaml", ".yml"):
                artifacts.extend(_extract_tools_from_yaml(file))
        except Exception as e:
            logger.warning(
                "Unexpected error extracting tools from %s: %s", file.path, e
            )
            continue

    return artifacts
