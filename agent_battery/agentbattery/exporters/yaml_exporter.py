"""YAML exporter - serializes GeneratedTest list to YAML files."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from agentbattery.models import GeneratedTest

logger = logging.getLogger(__name__)


def export_yaml(tests: list[GeneratedTest], output_dir: Path) -> list[Path]:
    """Serialize each test as a YAML file in the output directory.

    Each file is named by test.id + ".yaml".

    Args:
        tests: List of GeneratedTest objects to export.
        output_dir: Directory to write YAML files to.

    Returns:
        List of paths to written YAML files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    for test in tests:
        file_path = output_dir / f"{test.id}.yaml"
        test_data = test.model_dump()
        with open(file_path, "w") as f:
            yaml.dump(test_data, f, default_flow_style=False, sort_keys=False)
        written_paths.append(file_path)
        logger.debug(f"Exported YAML test: {file_path}")

    return written_paths
