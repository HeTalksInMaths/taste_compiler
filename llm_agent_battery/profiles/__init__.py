"""Review profile loading and architecture auto-detection."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from llm_agent_battery.models import (
    ArchitectureStyle,
    ClassifiedFile,
    FileCategory,
    ReviewProfile,
)

logger = logging.getLogger(__name__)

_PROFILES_DIR = Path(__file__).parent


def load_profile(name: str) -> ReviewProfile:
    """Load a review profile by name.

    Looks for a YAML file in the built-in profiles directory first,
    then checks if `name` is a path to a custom YAML file.

    Args:
        name: Profile name (e.g. 'single-agent') or path to a custom YAML file.

    Returns:
        A validated ReviewProfile instance.

    Raises:
        FileNotFoundError: If no matching profile is found.
        ValueError: If the YAML is invalid or missing required fields.
    """
    # Try built-in profile first
    builtin_path = _PROFILES_DIR / f"{name}.yaml"
    if builtin_path.exists():
        return _load_yaml_profile(builtin_path)

    # Try as a direct file path
    custom_path = Path(name)
    if custom_path.exists() and custom_path.suffix in (".yaml", ".yml"):
        return _load_yaml_profile(custom_path)

    available = [p.stem for p in _PROFILES_DIR.glob("*.yaml")]
    raise FileNotFoundError(
        f"Profile '{name}' not found. Available built-in profiles: {available}"
    )


def _load_yaml_profile(path: Path) -> ReviewProfile:
    """Parse a YAML file into a ReviewProfile model."""
    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError(f"Profile YAML at {path} must be a mapping, got {type(data).__name__}")

    required_fields = ("name", "architecture_style", "system_prompt_template", "focus_areas", "anti_patterns")
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Profile YAML at {path} missing required fields: {missing}")

    return ReviewProfile(
        name=data["name"],
        architecture_style=ArchitectureStyle(data["architecture_style"]),
        system_prompt_template=data["system_prompt_template"],
        focus_areas=data["focus_areas"],
        anti_patterns=data["anti_patterns"],
    )


def detect_architecture(files: list[ClassifiedFile]) -> ArchitectureStyle:
    """Detect the most likely architecture style from classified files.

    Heuristics:
    - Multiple ORCHESTRATION files → multi-agent
    - Sequential function call / pipeline patterns → pipeline-sequential
    - Event-driven patterns → reactive
    - Default → single-agent

    Args:
        files: List of classified source files.

    Returns:
        The detected ArchitectureStyle.
    """
    orchestration_count = 0
    has_pipeline_pattern = False
    has_reactive_pattern = False

    for f in files:
        categories = [f.primary_category] + f.secondary_categories

        if FileCategory.ORCHESTRATION in categories:
            orchestration_count += 1

        # Check content for pipeline/reactive signals via path heuristics
        rel_lower = f.relative_path.lower()
        if any(kw in rel_lower for kw in ("pipeline", "stage", "step", "chain")):
            has_pipeline_pattern = True
        if any(kw in rel_lower for kw in ("event", "handler", "listener", "subscriber", "reactive")):
            has_reactive_pattern = True

    # Also inspect content of agent logic / orchestration files for patterns
    for f in files:
        categories = [f.primary_category] + f.secondary_categories
        if FileCategory.AGENT_LOGIC in categories or FileCategory.ORCHESTRATION in categories:
            content = _safe_read(f.path)
            if content:
                if _has_pipeline_signals(content):
                    has_pipeline_pattern = True
                if _has_reactive_signals(content):
                    has_reactive_pattern = True

    # Decision logic
    if orchestration_count >= 2:
        return ArchitectureStyle.MULTI_AGENT
    if has_reactive_pattern:
        return ArchitectureStyle.REACTIVE_EVENT_DRIVEN
    if has_pipeline_pattern:
        return ArchitectureStyle.PIPELINE_SEQUENTIAL
    return ArchitectureStyle.SINGLE_AGENT


def _safe_read(path: Path, max_bytes: int = 64 * 1024) -> str | None:
    """Read file content, returning None on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except (OSError, UnicodeDecodeError):
        return None


def _has_pipeline_signals(content: str) -> bool:
    """Detect sequential pipeline patterns in source content."""
    import re

    # Look for sequential function calls chained together
    pipeline_patterns = [
        r"\.pipe\(",
        r"\.then\(",
        r"pipeline\s*=\s*\[",
        r"stages?\s*=\s*\[",
        r"steps?\s*=\s*\[",
        r"chain\s*\(",
    ]
    matches = sum(1 for p in pipeline_patterns if re.search(p, content, re.IGNORECASE))
    return matches >= 1


def _has_reactive_signals(content: str) -> bool:
    """Detect event-driven / reactive patterns in source content."""
    import re

    reactive_patterns = [
        r"@on_event\b",
        r"@event_handler\b",
        r"\.on\(\s*['\"]",
        r"\.subscribe\(",
        r"\.emit\(",
        r"EventEmitter",
        r"event_bus",
        r"async\s+def\s+on_\w+",
    ]
    matches = sum(1 for p in reactive_patterns if re.search(p, content, re.IGNORECASE))
    return matches >= 1
