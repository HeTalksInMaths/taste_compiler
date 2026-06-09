"""File scanner module — recursively discovers files with glob filtering."""

from __future__ import annotations

import logging
import time
from fnmatch import fnmatch
from pathlib import Path

from llm_agent_battery.models import DiscoveredFile, ScanConfig, ScanResult, ScanWarning

logger = logging.getLogger(__name__)


def _matches_any(name: str, patterns: list[str]) -> bool:
    """Check if a name matches any of the given fnmatch patterns."""
    return any(fnmatch(name, pattern) for pattern in patterns)


def scan(target_dir: Path, config: ScanConfig | None = None) -> ScanResult:
    """Recursively discover files matching include/exclude globs.

    Walks the directory tree rooted at target_dir, applies include/exclude
    filtering, skips oversized files with a warning, and returns relative paths.

    Args:
        target_dir: Root directory to scan.
        config: ScanConfig with include_globs, exclude_globs, and max_file_size_bytes.
                If None, uses default ScanConfig.

    Returns:
        ScanResult containing discovered files, warnings, count, and timing.

    Raises:
        FileNotFoundError: If target_dir does not exist.
        NotADirectoryError: If target_dir is not a directory.
    """
    if not target_dir.exists():
        raise FileNotFoundError(f"Target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_dir}")

    if config is None:
        config = ScanConfig()

    start = time.time()
    files: list[DiscoveredFile] = []
    warnings: list[ScanWarning] = []

    for dirpath, dirnames, filenames in sorted_walk(target_dir):
        # Filter out excluded directories in-place to prevent descending into them
        dirnames[:] = sorted(
            d for d in dirnames
            if not _matches_any(d, config.exclude_globs)
        )

        for filename in sorted(filenames):
            # Skip files matching exclude patterns
            if _matches_any(filename, config.exclude_globs):
                continue

            # Only include files matching at least one include pattern
            if not _matches_any(filename, config.include_globs):
                continue

            filepath = Path(dirpath) / filename
            relative_path = filepath.relative_to(target_dir)

            # Check if any parent directory part matches an exclude pattern
            parts_excluded = any(
                _matches_any(part, config.exclude_globs)
                for part in relative_path.parts[:-1]
            )
            if parts_excluded:
                continue

            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            # Skip oversized files with a warning
            if size > config.max_file_size_bytes:
                warnings.append(ScanWarning(
                    file_path=str(relative_path),
                    reason=f"File exceeds max size ({size} bytes > {config.max_file_size_bytes} bytes)",
                ))
                logger.warning(
                    "Skipping oversized file: %s (%d bytes > %d bytes)",
                    relative_path,
                    size,
                    config.max_file_size_bytes,
                )
                continue

            files.append(DiscoveredFile(
                path=filepath.resolve(),
                relative_path=str(relative_path),
                size_bytes=size,
            ))

    elapsed = time.time() - start

    return ScanResult(
        files=files,
        warnings=warnings,
        total_count=len(files),
        elapsed_seconds=elapsed,
    )


def sorted_walk(target_dir: Path):
    """Walk directory tree with sorted directory names for deterministic output."""
    import os

    for dirpath, dirnames, filenames in os.walk(target_dir):
        # Sort dirnames in-place so os.walk visits them in order
        dirnames.sort()
        yield dirpath, dirnames, filenames
