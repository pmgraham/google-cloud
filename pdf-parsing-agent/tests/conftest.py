import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture_path(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    if not os.path.exists(path):
        pytest.skip(f"Fixture missing: {name} (run: python tests/generate_fixtures.py)")
    return path


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_text_pdf():
    return _fixture_path("sample_text.pdf")


@pytest.fixture
def sample_table_pdf():
    return _fixture_path("sample_table.pdf")


@pytest.fixture
def sample_scanned_pdf():
    return _fixture_path("sample_scanned.pdf")


@pytest.fixture
def sample_mixed_pdf():
    return _fixture_path("sample_mixed.pdf")
