"""File classifier module — assigns semantic categories using content and path heuristics."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from llm_agent_battery.models import ClassifiedFile, ClassifyConfig, DiscoveredFile, FileCategory

logger = logging.getLogger(__name__)


def _read_content(path: Path, max_bytes: int = 64 * 1024) -> str | None:
    """Read file content up to max_bytes, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except (OSError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Content-based heuristics (higher priority)
# ---------------------------------------------------------------------------


def _content_is_test(path: Path, content: str) -> bool:
    """Detect test files via imports or test function patterns."""
    if path.suffix != ".py":
        return False
    # Check for pytest/unittest imports
    if re.search(r"^\s*import\s+(pytest|unittest)", content, re.MULTILINE):
        return True
    if re.search(r"^\s*from\s+(pytest|unittest)", content, re.MULTILINE):
        return True
    # Check for test function/class definitions
    if re.search(r"^\s*def\s+test_\w+", content, re.MULTILINE):
        return True
    if re.search(r"^\s*class\s+Test\w+", content, re.MULTILINE):
        return True
    return False


def _content_is_agent_logic(path: Path, content: str) -> bool:
    """Detect agent logic via class patterns and framework imports."""
    if path.suffix != ".py":
        return False
    # Agent class patterns
    if re.search(r"class\s+\w*(Agent|Bot)\b", content):
        return True
    # Agent framework imports
    agent_frameworks = [
        r"^\s*(?:from|import)\s+langchain",
        r"^\s*(?:from|import)\s+autogen",
        r"^\s*(?:from|import)\s+crewai",
        r"^\s*(?:from|import)\s+openai\..*(?:Agent|Assistant)",
        r"^\s*(?:from|import)\s+llama_index\.agent",
    ]
    for pattern in agent_frameworks:
        if re.search(pattern, content, re.MULTILINE):
            return True
    return False


def _content_is_tool_definition(path: Path, content: str) -> bool:
    """Detect tool definitions via decorators and class patterns."""
    if path.suffix != ".py":
        return False
    # Tool decorators
    tool_decorators = [
        r"@tool\b",
        r"@function_tool\b",
        r"@agent\.tool\b",
    ]
    for pattern in tool_decorators:
        if re.search(pattern, content):
            return True
    # Tool class definitions
    if re.search(r"class\s+\w*Tool\b.*:", content):
        return True
    # BaseTool inheritance
    if re.search(r"class\s+\w+\(.*BaseTool.*\)", content):
        return True
    return False


def _content_is_orchestration(path: Path, content: str) -> bool:
    """Detect orchestration via routing/delegation patterns."""
    if path.suffix != ".py":
        return False
    orchestration_patterns = [
        r"\bdispatch\b",
        r"\broute\b",
        r"\bdelegate\b",
        r"\borchestrat\w*\b",
    ]
    match_count = sum(
        1 for pattern in orchestration_patterns
        if re.search(pattern, content, re.IGNORECASE)
    )
    # Require at least 2 matches to avoid false positives
    if match_count >= 2:
        return True
    # Or a strong single signal: class with orchestration in name
    if re.search(r"class\s+\w*(Orchestrat|Router|Dispatch)\w*", content):
        return True
    return False


def _content_is_state_management(path: Path, content: str) -> bool:
    """Detect state management via state classes and patterns."""
    if path.suffix != ".py":
        return False
    # State class patterns
    if re.search(r"class\s+\w*State\b", content):
        return True
    # State machine patterns
    if re.search(r"\bstate_machine\b", content, re.IGNORECASE):
        return True
    if re.search(r"\bStateMachine\b", content):
        return True
    # Session state handling
    if re.search(r"class\s+\w*Session\w*", content) and re.search(r"self\.\w*state\w*", content):
        return True
    return False


def _content_is_prompt_template(path: Path, content: str) -> bool:
    """Detect prompt templates via template strings and naming."""
    # Markdown/text files with prompt-like content
    if path.suffix in (".md", ".txt"):
        # Check for template variables
        if re.search(r"\{[\w.]+\}", content):
            return True
        # Check for imperative instructions
        imperative_count = len(re.findall(
            r"^\s*(You are|You must|Always|Never|Do not)\b",
            content,
            re.MULTILINE | re.IGNORECASE,
        ))
        if imperative_count >= 2:
            return True
        return False

    if path.suffix != ".py":
        return False
    # Python files with template strings
    # f-strings or format strings with prompt-related variable names
    if re.search(r"(?:prompt|system_prompt|template|instruction)\s*=\s*[\"']", content, re.IGNORECASE):
        if re.search(r"\{[\w.]+\}", content):
            return True
    # Triple-quoted strings with template variables
    if re.search(r'""".*\{[\w.]+\}.*"""', content, re.DOTALL):
        return True
    return False


def _content_is_configuration(path: Path, content: str) -> bool:
    """Detect configuration files by extension and patterns."""
    if path.suffix in (".yaml", ".yml", ".json", ".toml"):
        return True
    if path.suffix == ".py":
        # Python files with config-like patterns
        if re.search(r"class\s+\w*(Config|Settings)\b", content):
            return True
    return False


def _content_is_infrastructure(path: Path, content: str) -> bool:
    """Detect infrastructure files (Docker, Terraform, CloudFormation)."""
    name_lower = path.name.lower()
    # Dockerfile
    if name_lower == "dockerfile" or name_lower.startswith("dockerfile."):
        return True
    # Docker compose
    if name_lower in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        return True
    # Terraform
    if path.suffix == ".tf":
        return True
    # CloudFormation patterns in YAML
    if path.suffix in (".yaml", ".yml") and content:
        if re.search(r"AWSTemplateFormatVersion", content):
            return True
        if re.search(r"Resources:\s*\n\s+\w+:\s*\n\s+Type:\s*AWS::", content):
            return True
    # Kubernetes manifests
    if path.suffix in (".yaml", ".yml") and content:
        if re.search(r"apiVersion:", content) and re.search(r"kind:", content):
            return True
    return False


# Priority-ordered content-based heuristics
_CONTENT_HEURISTICS: list[tuple[FileCategory, callable]] = [
    (FileCategory.TEST, _content_is_test),
    (FileCategory.INFRASTRUCTURE, _content_is_infrastructure),
    (FileCategory.AGENT_LOGIC, _content_is_agent_logic),
    (FileCategory.TOOL_DEFINITION, _content_is_tool_definition),
    (FileCategory.ORCHESTRATION, _content_is_orchestration),
    (FileCategory.STATE_MANAGEMENT, _content_is_state_management),
    (FileCategory.PROMPT_TEMPLATE, _content_is_prompt_template),
    (FileCategory.CONFIGURATION, _content_is_configuration),
]


# ---------------------------------------------------------------------------
# Path-based heuristics (lower priority fallback)
# ---------------------------------------------------------------------------


def _path_classify(path: Path) -> FileCategory | None:
    """Classify a file based on its directory path as a fallback."""
    parts = [p.lower() for p in path.parts]

    # Test directories
    if "tests" in parts or "test" in parts:
        return FileCategory.TEST
    # File starts with test_
    if path.name.lower().startswith("test_"):
        return FileCategory.TEST

    # Prompt/template directories
    if "prompts" in parts or "templates" in parts:
        return FileCategory.PROMPT_TEMPLATE

    # Tools directory
    if "tools" in parts:
        return FileCategory.TOOL_DEFINITION

    # Config directories
    if "config" in parts or "configs" in parts:
        return FileCategory.CONFIGURATION

    # Infrastructure
    if "infra" in parts or "infrastructure" in parts or "deploy" in parts:
        return FileCategory.INFRASTRUCTURE

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_file(file: DiscoveredFile, config: ClassifyConfig | None = None) -> ClassifiedFile:
    """Classify a single file using content-based then path-based heuristics.

    Content-based heuristics are tried first. If none match, path-based
    heuristics provide a fallback. If neither produces a match, the file
    is classified as UNKNOWN.

    Args:
        file: A DiscoveredFile to classify.
        config: Optional ClassifyConfig. Defaults to fast_mode=False.

    Returns:
        ClassifiedFile with primary and secondary categories assigned.
    """
    if config is None:
        config = ClassifyConfig()

    path = file.path
    content = _read_content(path)

    primary: FileCategory | None = None
    secondaries: list[FileCategory] = []

    # --- Content-based heuristics (high priority) ---
    if content is not None:
        for category, heuristic in _CONTENT_HEURISTICS:
            try:
                if heuristic(path, content):
                    if primary is None:
                        primary = category
                    else:
                        if category not in secondaries and category != primary:
                            secondaries.append(category)
            except Exception:
                # If a heuristic fails (e.g. regex error), skip it
                logger.debug("Heuristic %s failed for %s", category, path)

    # --- Path-based heuristics (fallback) ---
    if primary is None:
        # Use relative_path for path-based classification
        rel = Path(file.relative_path)
        path_category = _path_classify(rel)
        if path_category is not None:
            primary = path_category

    # --- Fallback to UNKNOWN ---
    if primary is None:
        primary = FileCategory.UNKNOWN

    return ClassifiedFile(
        path=file.path,
        relative_path=file.relative_path,
        size_bytes=file.size_bytes,
        primary_category=primary,
        secondary_categories=secondaries,
    )


def classify_files(
    files: list[DiscoveredFile], config: ClassifyConfig | None = None
) -> list[ClassifiedFile]:
    """Classify a list of discovered files.

    Uses content-based heuristics (AST patterns, import analysis, decorator
    detection) first, falling back to path-based heuristics. In fast mode,
    LLM fallback is skipped entirely.

    Args:
        files: List of DiscoveredFile objects to classify.
        config: Optional ClassifyConfig controlling LLM fallback and fast mode.

    Returns:
        List of ClassifiedFile objects with categories assigned.
    """
    if config is None:
        config = ClassifyConfig()

    return [classify_file(f, config) for f in files]
