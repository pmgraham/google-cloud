"""Tests for agent.tools — agent tool functions with BigQuery mocked out."""

import copy
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import agent.tools as tools_mod
from agent.tools import (
    get_table_schema,
    execute_query_with_metadata,
    add_calculated_column,
    apply_enrichment,
    clear_schema_cache,
    report_insight,
    get_and_clear_pending_insights,
    set_active_session,
    _set_last_query_result,
    _get_last_query_result,
    _session_query_results,
    _session_pending_insights,
)


# ───────────────────────── Table name validation ─────────────────────────


class TestTableNameValidation:
    def test_valid_simple_name(self):
        # Exercises the regex guard; BigQuery call will be mocked away
        with patch("agent.tools.bigquery") as mock_bq:
            mock_client = MagicMock()
            mock_bq.Client.return_value = mock_client
            mock_table = MagicMock()
            mock_table.schema = []
            mock_table.description = ""
            mock_table.num_rows = 0
            mock_client.get_table.return_value = mock_table
            mock_client.query.return_value.result.return_value = []
            result = get_table_schema("my_table")
        assert result["status"] == "success"

    def test_injection_attempt_blocked(self):
        result = get_table_schema("table; DROP TABLE foo")
        assert result["status"] == "error"
        assert "Invalid table name" in result["error"]

    def test_special_chars_blocked(self):
        result = get_table_schema("table$(whoami)")
        assert result["status"] == "error"

    def test_qualified_name_allowed(self):
        with patch("agent.tools.bigquery") as mock_bq:
            mock_client = MagicMock()
            mock_bq.Client.return_value = mock_client
            mock_table = MagicMock()
            mock_table.schema = []
            mock_table.description = ""
            mock_table.num_rows = 0
            mock_client.get_table.return_value = mock_table
            mock_client.query.return_value.result.return_value = []
            result = get_table_schema("project.dataset.table_name")
        assert result["status"] == "success"


# ───────────────────────── execute_query_with_metadata ─────────────────────────


class TestExecuteQuery:
    def _make_mock_row(self, data: dict):
        """Create a mock BigQuery Row that supports .items()."""
        row = MagicMock()
        row.items.return_value = data.items()
        return row

    @patch("agent.tools.bigquery")
    def test_basic_result_structure(self, mock_bq):
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client

        # Set up mock schema
        field1 = MagicMock()
        field1.name = "state"
        field1.field_type = "STRING"
        field2 = MagicMock()
        field2.name = "count"
        field2.field_type = "INTEGER"

        mock_results = MagicMock()
        mock_results.schema = [field1, field2]
        mock_results.__iter__ = lambda self: iter([
            self._rows[0], self._rows[1]
        ])
        mock_results._rows = [
            self._make_mock_row({"state": "CA", "count": 10}),
            self._make_mock_row({"state": "TX", "count": 8}),
        ]
        mock_results.__iter__ = lambda s: iter(s._rows)
        mock_client.query.return_value.result.return_value = mock_results

        set_active_session("test-exec")
        try:
            result = execute_query_with_metadata("SELECT state, count FROM t")
            assert result["status"] == "success"
            assert len(result["columns"]) == 2
            assert len(result["rows"]) == 2
            assert result["rows"][0]["state"] == "CA"
            assert "query_time_ms" in result
            assert "sql" in result
        finally:
            _session_query_results.pop("test-exec", None)

    @patch("agent.tools.bigquery")
    def test_limit_clause_injected(self, mock_bq):
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_results = MagicMock()
        mock_results.schema = []
        mock_results.__iter__ = lambda s: iter([])
        mock_client.query.return_value.result.return_value = mock_results

        set_active_session("test-limit")
        try:
            result = execute_query_with_metadata("SELECT * FROM t", max_rows=50)
            called_sql = mock_client.query.call_args[0][0]
            assert "LIMIT 50" in called_sql
        finally:
            _session_query_results.pop("test-limit", None)

    @patch("agent.tools.bigquery")
    def test_existing_limit_not_doubled(self, mock_bq):
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_results = MagicMock()
        mock_results.schema = []
        mock_results.__iter__ = lambda s: iter([])
        mock_client.query.return_value.result.return_value = mock_results

        set_active_session("test-limit2")
        try:
            execute_query_with_metadata("SELECT * FROM t LIMIT 10", max_rows=50)
            called_sql = mock_client.query.call_args[0][0]
            assert called_sql.count("LIMIT") == 1
        finally:
            _session_query_results.pop("test-limit2", None)

    @patch("agent.tools.bigquery")
    def test_type_conversions(self, mock_bq):
        """Date, bytes, Decimal values are converted to serializable types."""
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client

        field = MagicMock()
        field.name = "val"
        field.field_type = "STRING"

        mock_results = MagicMock()
        mock_results.schema = [field]

        d = date(2024, 1, 15)
        row_date = self._make_mock_row({"val": d})
        row_bytes = self._make_mock_row({"val": b"hello"})
        row_decimal = self._make_mock_row({"val": Decimal("3.14")})
        mock_results.__iter__ = lambda s: iter([row_date, row_bytes, row_decimal])
        mock_client.query.return_value.result.return_value = mock_results

        set_active_session("test-types")
        try:
            result = execute_query_with_metadata("SELECT val FROM t")
            assert result["rows"][0]["val"] == "2024-01-15"  # isoformat
            assert result["rows"][1]["val"] == "hello"       # decoded bytes
            assert result["rows"][2]["val"] == 3.14          # Decimal→float
        finally:
            _session_query_results.pop("test-types", None)

    @patch("agent.tools.bigquery")
    def test_stores_result_in_session(self, mock_bq):
        mock_client = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_results = MagicMock()
        mock_results.schema = []
        mock_results.__iter__ = lambda s: iter([])
        mock_client.query.return_value.result.return_value = mock_results

        set_active_session("test-store")
        try:
            execute_query_with_metadata("SELECT 1")
            stored = _session_query_results.get("test-store")
            assert stored is not None
            assert stored["status"] == "success"
        finally:
            _session_query_results.pop("test-store", None)


# ───────────────────────── add_calculated_column ─────────────────────────


class TestAddCalculatedColumn:
    def test_simple_arithmetic(self, active_session):
        result = add_calculated_column("doubled", "store_count * 2", "integer")
        assert result["status"] == "success"
        # CA: 100 * 2 = 200
        assert result["rows"][0]["doubled"]["value"] == 200
        assert result["rows"][0]["doubled"]["is_calculated"] is True

    def test_division_by_zero(self, active_session):
        # Put a zero in one row
        last = _get_last_query_result()
        last["rows"][0]["store_count"] = 0
        _set_last_query_result(last)

        result = add_calculated_column("inverse", "1 / store_count")
        assert result["rows"][0]["inverse"]["value"] is None
        assert result["rows"][0]["inverse"]["warning"] == "Division by zero"

    def test_missing_column(self, active_session):
        result = add_calculated_column("bad", "nonexistent_col * 2")
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_format_types(self, active_session):
        result = add_calculated_column("pct", "store_count / 1000", "percent")
        val = result["rows"][0]["pct"]["value"]
        # 100 / 1000 = 0.1 — percent format rounds to 2 decimals
        assert val == 0.1

    def test_enriched_column_value_extraction(self, active_session):
        """add_calculated_column extracts .value from enriched dict columns."""
        last = _get_last_query_result()
        # Add an enriched column to the result
        last["columns"].append({"name": "_enriched_pop", "type": "STRING", "is_enriched": True})
        for row in last["rows"]:
            row["_enriched_pop"] = {"value": 1000, "source": "Census", "confidence": "high", "freshness": "current", "warning": None}
        _set_last_query_result(last)

        result = add_calculated_column("per_store", "_enriched_pop / store_count")
        # CA: 1000 / 100 = 10
        assert result["rows"][0]["per_store"]["value"] == 10

    def test_no_prior_query(self):
        """Returns error when there is no query result stored."""
        set_active_session("empty-session")
        try:
            result = add_calculated_column("x", "a + b")
            assert result["status"] == "error"
            assert "No query result" in result["error"]
        finally:
            _session_query_results.pop("empty-session", None)

    def test_simpleeval_no_builtins(self, active_session):
        """Expressions cannot access Python builtins."""
        result = add_calculated_column("hack", "__import__('os').system('echo pwned')")
        # Should error on missing columns or simpleeval blocking it
        assert result["status"] == "error" or all(
            row["hack"]["value"] is None for row in result.get("rows", [])
        )

    def test_idempotent(self, active_session):
        """Calling twice with the same column name doesn't duplicate it."""
        add_calculated_column("doubled", "store_count * 2", "integer")
        result = add_calculated_column("doubled", "store_count * 2", "integer")
        col_names = [c["name"] for c in result["columns"]]
        assert col_names.count("doubled") == 1


# ───────────────────────── apply_enrichment ─────────────────────────


class TestApplyEnrichment:
    def test_basic_merge(self, active_session, sample_enrichment_data):
        result = apply_enrichment("state", sample_enrichment_data)
        assert result["status"] == "success"
        # Should have original 2 columns + 2 enriched columns
        col_names = [c["name"] for c in result["columns"]]
        assert "_enriched_capital" in col_names
        assert "_enriched_population" in col_names

    def test_column_prefixing(self, active_session, sample_enrichment_data):
        result = apply_enrichment("state", sample_enrichment_data)
        ca_row = result["rows"][0]
        assert ca_row["_enriched_capital"]["value"] == "Sacramento"
        assert ca_row["_enriched_capital"]["source"] == "Wikipedia"

    def test_partial_failure_warnings(self, active_session, sample_enrichment_data):
        """NY has no enrichment data → produces a warning."""
        result = apply_enrichment("state", sample_enrichment_data)
        meta = result["enrichment_metadata"]
        assert meta["partial_failure"] is True
        assert any("NY" in w for w in meta["warnings"])

    def test_idempotency(self, active_session, sample_enrichment_data):
        """Calling apply_enrichment twice with same data doesn't duplicate columns."""
        apply_enrichment("state", sample_enrichment_data)
        result = apply_enrichment("state", sample_enrichment_data)
        col_names = [c["name"] for c in result["columns"]]
        assert col_names.count("_enriched_capital") == 1

    def test_no_prior_query_error(self):
        set_active_session("no-query-session")
        try:
            result = apply_enrichment("state", [{"original_value": "CA", "enriched_fields": {}}])
            assert result["status"] == "error"
            assert "No query result" in result["error"]
        finally:
            _session_query_results.pop("no-query-session", None)

    def test_empty_enrichment_data(self, active_session):
        result = apply_enrichment("state", [])
        assert result["status"] == "error"
        assert "No enrichment data" in result["error"]


# ───────────────────────── report_insight / get_and_clear ─────────────────────────


class TestReportInsight:
    def test_valid_types(self):
        sid = "insight-test"
        set_active_session(sid)
        try:
            for t in ("trend", "anomaly", "comparison", "suggestion"):
                res = report_insight(t, f"msg-{t}")
                assert res["status"] == "recorded"
                assert res["type"] == t
            insights = get_and_clear_pending_insights(session_id=sid)
            assert len(insights) == 4
        finally:
            _session_pending_insights.pop(sid, None)

    def test_invalid_type_falls_back(self):
        sid = "insight-fallback"
        set_active_session(sid)
        try:
            res = report_insight("garbage", "msg")
            assert res["type"] == "suggestion"
        finally:
            _session_pending_insights.pop(sid, None)

    def test_session_scoped_accumulation_and_drain(self):
        sid = "insight-drain"
        set_active_session(sid)
        try:
            report_insight("trend", "one")
            report_insight("anomaly", "two")
            insights = get_and_clear_pending_insights(session_id=sid)
            assert len(insights) == 2
            # Second call should be empty (drained)
            assert get_and_clear_pending_insights(session_id=sid) == []
        finally:
            _session_pending_insights.pop(sid, None)


# ───────────────────────── clear_schema_cache ─────────────────────────


class TestClearSchemaCache:
    def test_clears_and_returns_count(self):
        # Use the module-level dict directly because clear_schema_cache()
        # reassigns the global with `global _schema_cache; _schema_cache = {}`.
        tools_mod._schema_cache["table1"] = {"name": "table1"}
        tools_mod._schema_cache["table2"] = {"name": "table2"}
        result = clear_schema_cache()
        assert result["status"] == "success"
        assert "2" in result["message"]
        assert len(tools_mod._schema_cache) == 0
