"""Shared test fixtures and configuration for agentbattery tests."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary directory to act as a target repo."""
    return tmp_path
