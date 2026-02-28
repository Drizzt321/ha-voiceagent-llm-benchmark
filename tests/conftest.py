"""Shared pytest fixtures for ha-voice-bench tests."""

import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SAMPLE_DATA_DIR = REPO_ROOT / "sample_test_data"


@pytest.fixture
def sample_data_dir() -> Path:
    return SAMPLE_DATA_DIR


@pytest.fixture
def sample_cases_path() -> Path:
    return SAMPLE_DATA_DIR / "sample_test_cases.ndjson"


@pytest.fixture
def sample_inventory_path() -> Path:
    return SAMPLE_DATA_DIR / "sample_inventory.yaml"
