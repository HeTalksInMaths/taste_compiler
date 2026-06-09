"""Scanner module - walks target repo and discovers files."""

from __future__ import annotations

import time
from pathlib import Path

from agentbattery.exceptions import ScanError
from agentbattery.models import DiscoveredFile, ScanResult

DEFAULT_INCLUDE_GLOBS: list[str] = [
    "*.py",
    "*.md",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.jsonl",
    "*.toml",
]

DEFAULT_EXCLUDE_GLOBS: list[str] = [
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    "*.egg-info",
    ".agentbattery",
    ".mypy_cache",
    ".pytest_cache",
]


def _matches_any_glob(path: Path, globs: list[str]) -> bool:
    """Check if a path matches any of the given glob patterns."""
    for glob in globs:
        if path.match(glob):
            return True
    return False


def _is_excluded(path: Path, target_dir: Path, exclude_globs: list[str]) -> bool:
    """Check if a path or any of its parent directories match exclude globs."""
    rel = path.relative_to(target_dir)
    # Check each part of the relative path against exclude globs
    for part in rel.parts:
        part_path = Path(part)
        if _matches_any_glob(part_path, exclude_globs):
            return True
    return False


def scan(
    target_dir: Path,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> ScanResult:
    """Recursively walk target_dir, apply glob filters, return DiscoveredFile list.

    Args:
        target_dir: The directory to scan.
        include_globs: File patterns to include. Defaults to common agent file types.
        exclude_globs: Directory/file patterns to exclude. Defaults to common non-source dirs.

    Returns:
        ScanResult with discovered files, count, and elapsed time.

    Raises:
        ScanError: If target_dir does not exist or is not a directory.
    """
    if not target_dir.exists():
        raise ScanError(f"Target path does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise ScanError(f"Target path is not a directory: {target_dir}")

    includes = include_globs if include_globs is not None else DEFAULT_INCLUDE_GLOBS
    excludes = exclude_globs if exclude_globs is not None else DEFAULT_EXCLUDE_GLOBS

    start_time = time.monotonic()
    files: list[DiscoveredFile] = []

    for item in sorted(target_dir.rglob("*")):
        if not item.is_file():
            continue

        # Check exclusions on the full relative path
        if _is_excluded(item, target_dir, excludes):
            continue

        # Check inclusions on the filename
        if not _matches_any_glob(item, includes):
            continue

        files.append(
            DiscoveredFile(
                path=item,
                relative_path=str(item.relative_to(target_dir)),
                size_bytes=item.stat().st_size,
            )
        )

    elapsed = time.monotonic() - start_time

    return ScanResult(
        files=files,
        total_count=len(files),
        elapsed_seconds=elapsed,
    )
