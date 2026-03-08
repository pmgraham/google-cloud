"""Shared test fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_csv(fixtures_dir):
    return str(fixtures_dir / "sample.csv")


@pytest.fixture
def bad_quoting_csv(fixtures_dir):
    return str(fixtures_dir / "bad_quoting.csv")


@pytest.fixture
def semicolon_csv(fixtures_dir):
    return str(fixtures_dir / "semicolon.csv")


@pytest.fixture
def messy_columns_csv(fixtures_dir):
    return str(fixtures_dir / "messy_columns.csv")


@pytest.fixture
def sample_json(fixtures_dir):
    return str(fixtures_dir / "sample.json")


@pytest.fixture
def sample_jsonl(fixtures_dir):
    return str(fixtures_dir / "sample.jsonl")


@pytest.fixture
def bad_json(fixtures_dir):
    return str(fixtures_dir / "bad_json.json")


@pytest.fixture
def bad_jsonl(fixtures_dir):
    return str(fixtures_dir / "bad_jsonl.jsonl")


@pytest.fixture
def overflow_columns_csv(fixtures_dir):
    return str(fixtures_dir / "overflow_columns.csv")


@pytest.fixture
def no_header_csv(fixtures_dir):
    return str(fixtures_dir / "no_header.csv")


@pytest.fixture
def quality_data_csv(fixtures_dir):
    return str(fixtures_dir / "quality_data.csv")


@pytest.fixture(autouse=True)
def reset_session():
    """Reset the module-level DuckDB session between tests."""
    import datagrunt_agent.tools.ingestion as ingestion_module
    ingestion_module._session = None
    yield
    if ingestion_module._session is not None:
        ingestion_module._session.close()
        ingestion_module._session = None


@pytest.fixture(autouse=True)
def mock_genai_for_header_detection():
    """Auto-mock the google.genai module to avoid real LLM calls in tests.

    Returns "HEADERS" by default. Tests that need specific LLM responses
    can override by applying their own sys.modules patch within the test.
    """
    mock_genai = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "HEADERS"
    mock_genai.Client.return_value.models.generate_content.return_value = mock_response

    # Save originals
    saved_genai = sys.modules.get("google.genai")
    saved_types = sys.modules.get("google.genai.types")

    sys.modules["google.genai"] = mock_genai
    sys.modules["google.genai.types"] = MagicMock()

    yield mock_genai

    # Restore
    if saved_genai is not None:
        sys.modules["google.genai"] = saved_genai
    else:
        sys.modules.pop("google.genai", None)
    if saved_types is not None:
        sys.modules["google.genai.types"] = saved_types
    else:
        sys.modules.pop("google.genai.types", None)
