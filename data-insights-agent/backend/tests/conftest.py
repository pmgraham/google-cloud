"""Shared fixtures for Data Insights Agent tests."""

import sys
import os

# Ensure backend/ is on sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import models directly to avoid circular import through api/__init__.py
from api.models import MessageRole  # noqa: E402

import pytest  # noqa: E402

import agent.tools as tools_mod  # noqa: E402
from agent.tools import (  # noqa: E402
    set_active_session,
    _set_last_query_result,
    _session_query_results,
    _session_pending_insights,
)


@pytest.fixture()
def sample_query_result():
    """A minimal successful query result matching execute_query_with_metadata output."""
    return {
        "status": "success",
        "columns": [
            {"name": "state", "type": "STRING"},
            {"name": "store_count", "type": "INTEGER"},
        ],
        "rows": [
            {"state": "CA", "store_count": 100},
            {"state": "TX", "store_count": 80},
            {"state": "NY", "store_count": 60},
        ],
        "total_rows": 3,
        "query_time_ms": 123.45,
        "sql": "SELECT state, store_count FROM stores GROUP BY state LIMIT 1000",
    }


@pytest.fixture()
def sample_enrichment_data():
    """Enrichment data list for apply_enrichment tests."""
    return [
        {
            "original_value": "CA",
            "enriched_fields": {
                "capital": {
                    "value": "Sacramento",
                    "source": "Wikipedia",
                    "confidence": "high",
                    "freshness": "static",
                    "warning": None,
                },
                "population": {
                    "value": 39500000,
                    "source": "Census",
                    "confidence": "medium",
                    "freshness": "current",
                    "warning": None,
                },
            },
        },
        {
            "original_value": "TX",
            "enriched_fields": {
                "capital": {
                    "value": "Austin",
                    "source": "Wikipedia",
                    "confidence": "high",
                    "freshness": "static",
                    "warning": None,
                },
                "population": {
                    "value": 29100000,
                    "source": "Census",
                    "confidence": "medium",
                    "freshness": "current",
                    "warning": None,
                },
            },
        },
    ]


@pytest.fixture()
def session_service():
    """Fresh SessionService instance per test (import inline to avoid circular import)."""
    from services.session_service import SessionService
    return SessionService()


@pytest.fixture()
def active_session(sample_query_result):
    """Set up an active session with a seeded query result. Cleans up after test."""
    sid = "test-session-id"
    set_active_session(sid)
    _set_last_query_result(sample_query_result)
    yield sid
    # Cleanup global state
    _session_query_results.pop(sid, None)
    _session_pending_insights.pop(sid, None)


@pytest.fixture(autouse=True)
def _clean_schema_cache():
    """Clear schema cache before every test to prevent cross-test pollution."""
    tools_mod._schema_cache = {}
    yield
    tools_mod._schema_cache = {}
