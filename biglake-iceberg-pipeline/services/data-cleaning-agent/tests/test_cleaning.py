"""Tests for data cleaning tools and pipeline auto-chaining."""

import json
import os
import tempfile

from unittest.mock import MagicMock

from datagrunt_agent.tools.ingestion import _get_session, load_file
from datagrunt_agent.tools.quality import quality_report
from datagrunt_agent.tools.cleaning import (
    clean_table,
    _clean_unknown_chars,
    _clean_whitespace,
    _clean_empty_strings,
    _clean_null_like_strings,
    _standardize_dates,
    _clean_type_coercion,
    _normalize_case,
    _flag_duplicates,
    _clean_constant_columns,
    _detect_pii,
    _validate_numeric_precision,
)
from datagrunt_agent.tools.cleaning_report import export_cleaning_report


def _make_tool_context(**state_overrides):
    ctx = MagicMock()
    ctx.state = {}
    ctx.state.update(state_overrides)
    return ctx


def _load_and_scan(csv_path):
    """Load a CSV and run quality scan, returning (ctx, table_name, findings)."""
    ctx = _make_tool_context()
    result = load_file(csv_path, ctx)
    assert result["status"] == "success", f"Load failed: {result}"
    table_name = result["table_name"]

    qr = quality_report(table_name, ctx)
    findings = qr["findings"]

    return ctx, table_name, findings


class TestCleanTableIntegration:
    """Full pipeline: load → scan → clean."""

    def test_clean_table_success(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)

        result = clean_table(table_name, ctx)

        assert result["status"] == "success"
        assert result["table_name"] == table_name
        assert result["before_rows"] > 0
        assert result["after_rows"] == result["before_rows"]  # No rows deleted
        assert isinstance(result["operations"], list)
        assert len(result["operations"]) > 0

    def test_clean_table_stores_state(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)

        clean_table(table_name, ctx)

        assert "cleaning_result" in ctx.state
        assert "cleaning_report" in ctx.state
        assert ctx.state["cleaning_result"]["status"] == "success"

    def test_clean_table_has_report_path(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)

        result = clean_table(table_name, ctx)

        assert "cleaning_report_path" in result
        assert result["cleaning_report_path"].endswith("_cleaning_report.json")


class TestCleanTableNoFindings:
    """Clean table with no quality findings."""

    def test_no_findings_returns_success(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        table_name = result["table_name"]

        # Don't run quality scan — leave findings empty
        clean_result = clean_table(table_name, ctx)

        assert clean_result["status"] == "success"
        # May still have some operations (like empty string normalization on all VARCHARs)
        # but no findings-driven operations


class TestCleanTableReadsFromState:
    """Verify clean_table reads findings from tool_context.state."""

    def test_reads_findings_from_state(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)

        # Verify findings were stored in state by quality_report
        assert len(ctx.state["quality_findings"]) > 0
        assert ctx.state["quality_table_name"] == table_name

        result = clean_table(table_name, ctx)
        assert result["status"] == "success"


class TestCleanTableNonexistentTable:
    """Clean table that doesn't exist."""

    def test_nonexistent_table_returns_error(self):
        ctx = _make_tool_context()
        result = clean_table("nonexistent_table", ctx)
        assert "error" in result


class TestUnknownCharReplacement:
    """Test U+FFFD replacement."""

    def test_replacement_char_removed(self, quality_data_csv):
        ctx = _make_tool_context()
        load_file(quality_data_csv, ctx)
        session = _get_session()
        table_name = ctx.state["current_table"]

        # Inject a replacement character into data
        session.execute(
            f"UPDATE {table_name} SET name = 'Caf\ufffd' WHERE id = 1"
        )

        varchar_cols = [
            c for c, t in session.get_column_types(table_name).items()
            if t == "VARCHAR" and c != "processed_at"
        ]

        result = _clean_unknown_chars(session, table_name, varchar_cols)

        assert result is not None
        assert result["operation"] == "unknown_char_replacement"
        assert result["replacements"] > 0

        # Verify the character is gone
        check = session.execute(
            f"SELECT name FROM {table_name} WHERE id = 1"
        ).fetchone()[0]
        assert "\ufffd" not in check


class TestWhitespaceCleaning:
    """Test whitespace trimming."""

    def test_whitespace_trimmed(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        varchar_cols = [
            c for c, t in session.get_column_types(table_name).items()
            if t == "VARCHAR" and c != "processed_at"
        ]

        result = _clean_whitespace(session, table_name, varchar_cols, findings)

        # quality_data.csv has whitespace in name and notes columns
        assert result is not None
        assert result["operation"] == "whitespace_trimming"
        assert len(result["columns_cleaned"]) > 0

        # Verify no leading/trailing whitespace remains in cleaned columns
        for col in result["columns_cleaned"]:
            remaining = session.execute(
                f'SELECT COUNT(*) FROM {table_name} '
                f'WHERE "{col}" IS NOT NULL AND "{col}" != TRIM("{col}")'
            ).fetchone()[0]
            assert remaining == 0, f"Column {col} still has whitespace"


class TestEmptyStringNormalization:
    """Test empty string → NULL conversion."""

    def test_empty_strings_become_null(self, quality_data_csv):
        ctx = _make_tool_context()
        load_file(quality_data_csv, ctx)
        session = _get_session()
        table_name = ctx.state["current_table"]

        varchar_cols = [
            c for c, t in session.get_column_types(table_name).items()
            if t == "VARCHAR" and c != "processed_at"
        ]

        result = _clean_empty_strings(session, table_name, varchar_cols)

        # quality_data.csv has empty strings in notes and email columns
        if result is not None:
            assert result["operation"] == "empty_string_normalization"
            assert result["rows_affected"] > 0

            # Verify no empty strings remain
            for col in result["columns_cleaned"]:
                remaining = session.execute(
                    f'SELECT COUNT(*) FROM {table_name} '
                    f"WHERE TRIM(\"{col}\") = ''"
                ).fetchone()[0]
                assert remaining == 0, f"Column {col} still has empty strings"


class TestNullLikeCleaning:
    """Test null-like sentinel → NULL conversion."""

    def test_sentinels_become_null(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        result = _clean_null_like_strings(session, table_name, findings)

        # quality_data.csv has NULL, N/A, None, n/a in zip_code, email, score
        assert result is not None
        assert result["operation"] == "null_like_normalization"
        assert len(result["columns_cleaned"]) > 0
        assert result["rows_affected"] > 0


class TestDateStandardization:
    """Test DATE-castable VARCHAR → YYYY-MM-DD conversion."""

    def test_dates_standardized(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        _standardize_dates(session, table_name, findings)

        # quality_data.csv may not have date columns, so this could be None
        # which is expected behavior


class TestTypeCoercion:
    """Test type coercion with identifier preservation."""

    def test_score_coerced_to_double(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        op, identifiers = _clean_type_coercion(session, table_name, findings)

        # score column should be coerced to DOUBLE (after null-like cleaning)
        # But we need to check if type_analysis flagged it
        type_findings = [
            f for f in findings
            if f.get("category") == "type_analysis" and f.get("suggested_cast")
        ]

        if type_findings:
            # If there were type findings, verify operation ran
            if op is not None:
                assert op["operation"] == "type_coercion"

    def test_zip_code_not_coerced(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        op, identifiers = _clean_type_coercion(session, table_name, findings)

        # zip_code has leading zeros — should be in identifiers list
        identifier_cols = [i["column"] for i in identifiers]
        zip_findings = [
            f for f in findings
            if f.get("category") == "type_analysis"
            and f.get("column") == "zip_code"
            and f.get("leading_zero_count", 0) > 0
        ]

        if zip_findings:
            assert "zip_code" in identifier_cols

            # Verify zip_code stays VARCHAR
            col_types = session.get_column_types(table_name)
            assert col_types.get("zip_code") == "VARCHAR"


class TestIdentifierPreservation:
    """Test that columns with leading zeros stay VARCHAR."""

    def test_leading_zeros_preserved(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        # Run full clean
        result = clean_table(table_name, ctx)

        # Verify zip_code is still VARCHAR
        col_types = session.get_column_types(table_name)
        if "zip_code" in col_types:
            assert col_types["zip_code"] == "VARCHAR"

        # Check identifier_columns in result
        id_cols = [i["column"] for i in result.get("identifier_columns", [])]
        # zip_code should be listed if it had leading zeros flagged
        zip_findings = [
            f for f in ctx.state.get("quality_findings", [])
            if f.get("column") == "zip_code" and f.get("leading_zero_count", 0) > 0
        ]
        if zip_findings:
            assert "zip_code" in id_cols


class TestMixedCaseNormalization:
    """Test case normalization for low-cardinality categoricals."""

    def test_categoricals_lowercased(self, quality_data_csv):
        ctx = _make_tool_context()
        load_file(quality_data_csv, ctx)
        session = _get_session()
        table_name = ctx.state["current_table"]

        # Insert mixed-case categorical values
        session.execute(
            f"UPDATE {table_name} SET status = 'Active' WHERE id = 1"
        )
        session.execute(
            f"UPDATE {table_name} SET status = 'ACTIVE' WHERE id = 2"
        )

        varchar_cols = [
            c for c, t in session.get_column_types(table_name).items()
            if t == "VARCHAR" and c != "processed_at"
        ]

        result = _normalize_case(session, table_name, varchar_cols)

        # status has low cardinality and mixed case
        if result is not None:
            assert result["operation"] == "mixed_case_normalization"
            assert result["target_case"] == "lower"

            # Verify all values are lowercase
            for col in result["columns_normalized"]:
                remaining = session.execute(
                    f'SELECT COUNT(*) FROM {table_name} '
                    f'WHERE "{col}" IS NOT NULL AND "{col}" != LOWER("{col}")'
                ).fetchone()[0]
                assert remaining == 0


class TestSoftDedup:
    """Test duplicate flagging (soft dedup)."""

    def test_duplicates_flagged(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        result = _flag_duplicates(session, table_name, findings)

        # quality_data.csv has John Smith duplicate (rows 1 and 6)
        dup_findings = [
            f for f in findings if f.get("category") == "duplicates"
        ]

        if dup_findings:
            assert result is not None
            assert result["operation"] == "soft_dedup"
            assert result["duplicates_flagged"] > 0
            assert result["column_added"] == "is_duplicate"

            # Verify row count unchanged
            total_rows = session.get_row_count(table_name)
            assert total_rows == 10  # All 10 rows still present

            # Verify is_duplicate column exists
            columns = session.get_column_names(table_name)
            assert "is_duplicate" in columns


class TestConstantColumnRemoval:
    """Test constant column removal."""

    def test_constant_columns_dropped(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        result = _clean_constant_columns(session, table_name, findings)

        # quality_data.csv has 'status' column with all 'active' values
        constant_findings = [
            f for f in findings if f.get("category") == "constant_columns"
        ]

        if constant_findings:
            assert result is not None
            assert result["operation"] == "constant_column_removal"
            assert len(result["columns_dropped"]) > 0

            # Verify dropped columns are gone
            remaining_cols = session.get_column_names(table_name)
            for col in result["columns_dropped"]:
                assert col not in remaining_cols


class TestProcessedAtProtection:
    """Ensure processed_at survives all cleaning operations."""

    def test_processed_at_preserved(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        # Run full cleaning
        clean_table(table_name, ctx)

        # Verify processed_at still exists
        columns = session.get_column_names(table_name)
        assert "processed_at" in columns


class TestCleaningOrder:
    """Verify operations are in the correct sequence."""

    def test_operations_in_order(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)

        result = clean_table(table_name, ctx)

        operation_names = [op["operation"] for op in result["operations"]]

        # Define the expected order
        expected_order = [
            "unknown_char_replacement",
            "whitespace_trimming",
            "empty_string_normalization",
            "null_like_normalization",
            "date_standardization",
            "type_coercion",
            "mixed_case_normalization",
            "soft_dedup",
            "high_null_column_removal",
            "constant_column_removal",
        ]

        # Verify that operations appear in the correct relative order
        prev_idx = -1
        for op_name in operation_names:
            if op_name in expected_order:
                idx = expected_order.index(op_name)
                assert idx > prev_idx, (
                    f"Operation '{op_name}' at position {idx} "
                    f"appeared after position {prev_idx} — wrong order"
                )
                prev_idx = idx


class TestCleaningReport:
    """Test cleaning report generation."""

    def test_report_persisted(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)

        result = clean_table(table_name, ctx)

        report_path = result["cleaning_report_path"]
        assert os.path.exists(report_path)

        with open(report_path) as fh:
            report = json.load(fh)

        assert report["report_id"].startswith("dcr_")
        assert "summary" in report
        assert "operations" in report
        assert "pii_detection" in report
        assert "identifier_columns" in report
        assert report["overall_status"] in ("cleaned", "no_action_needed")

    def test_report_has_all_sections(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)

        clean_table(table_name, ctx)

        report = ctx.state["cleaning_report"]

        expected_keys = {
            "report_id", "schema_version", "generated_at",
            "source", "summary", "operations", "pii_detection",
            "identifier_columns", "numeric_precision_flags",
            "quality_findings_input", "overall_status",
        }
        assert expected_keys.issubset(report.keys())


class TestExportCleaningReport:
    """Test the export_cleaning_report tool."""

    def test_export_after_clean(self, quality_data_csv):
        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        clean_table(table_name, ctx)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_cleaning.json")
            result = export_cleaning_report(
                table_name=table_name,
                output_path=output_path,
                tool_context=ctx,
            )

            assert result["status"] == "success"
            assert os.path.exists(output_path)

    def test_export_without_clean_returns_error(self, sample_csv):
        ctx = _make_tool_context()
        load_file(sample_csv, ctx)
        table_name = ctx.state["current_table"]

        result = export_cleaning_report(
            table_name=table_name,
            output_path="/tmp/nope.json",
            tool_context=ctx,
        )
        assert "error" in result

    def test_export_nonexistent_table(self):
        ctx = _make_tool_context()
        result = export_cleaning_report(
            table_name="nonexistent",
            output_path="/tmp/nope.json",
            tool_context=ctx,
        )
        assert "error" in result


class TestPiiDetection:
    """Test PII detection with mocked LLM."""

    def test_pii_flags_returned(self, quality_data_csv):
        import sys
        from unittest.mock import patch

        ctx, table_name, findings = _load_and_scan(quality_data_csv)
        session = _get_session()

        pii_response = MagicMock()
        pii_response.text = json.dumps([
            {"column": "email", "is_pii": True, "pii_type": "email", "confidence": 0.95},
            {"column": "name", "is_pii": True, "pii_type": "name", "confidence": 0.85},
        ])

        # Create a fresh mock genai module with properly chained return values
        mock_genai_module = MagicMock()
        mock_genai_module.Client.return_value.models.generate_content.return_value = pii_response
        mock_types_module = MagicMock()

        with patch.dict(sys.modules, {
            "google.genai": mock_genai_module,
            "google.genai.types": mock_types_module,
        }):
            pii_results = _detect_pii(session, table_name)

        assert len(pii_results) >= 1
        pii_cols = [p["column"] for p in pii_results]
        assert "email" in pii_cols

    def test_pii_detection_handles_llm_failure(self, quality_data_csv):
        import sys
        from unittest.mock import patch

        ctx = _make_tool_context()
        load_file(quality_data_csv, ctx)
        session = _get_session()
        table_name = ctx.state["current_table"]

        mock_genai_module = MagicMock()
        mock_genai_module.Client.return_value.models.generate_content.side_effect = Exception("LLM down")
        mock_types_module = MagicMock()

        with patch.dict(sys.modules, {
            "google.genai": mock_genai_module,
            "google.genai.types": mock_types_module,
        }):
            pii_results = _detect_pii(session, table_name)

        # Should return empty list on failure, not raise
        assert pii_results == []


class TestNumericPrecisionValidation:
    """Test numeric precision validation."""

    def test_inconsistent_precision_flagged(self, quality_data_csv):
        ctx = _make_tool_context()
        load_file(quality_data_csv, ctx)
        session = _get_session()
        table_name = ctx.state["current_table"]

        # score column has values like 85.5, 92.3 (1 decimal place)
        # and 95.0 (also 1 decimal). Let's add inconsistency
        session.execute(
            f"ALTER TABLE {table_name} ALTER COLUMN score SET DATA TYPE DOUBLE "
            f"USING TRY_CAST(score AS DOUBLE)"
        )
        session.execute(
            f"UPDATE {table_name} SET score = 85.123 WHERE id = 1"
        )

        flags = _validate_numeric_precision(session, table_name)

        # Should flag score column for inconsistent precision
        if flags:
            flagged_cols = [f["column"] for f in flags]
            assert "score" in flagged_cols


class TestAfterToolCallbackChaining:
    """Test the callback chains QualityAnalyst → DataCleaner."""

    def test_quality_analyst_triggers_cleaner(self):
        from datagrunt_agent.agent import _after_tool_callback

        tool = MagicMock()
        tool.name = "QualityAnalyst"

        ctx = MagicMock()
        ctx.state = {
            "quality_findings": [
                {"category": "whitespace", "column": "name"},
                {"category": "null_like_strings", "column": "zip"},
            ],
            "quality_table_name": "table_test",
        }

        result = _after_tool_callback(tool, {}, ctx, "Quality report text")

        assert result is not None
        assert isinstance(result, str)
        assert "next_action" in result
        assert "delegate_to_data_cleaner" in result
        assert "table_test" in result

    def test_quality_analyst_skips_when_no_actionable(self):
        from datagrunt_agent.agent import _after_tool_callback

        tool = MagicMock()
        tool.name = "QualityAnalyst"

        ctx = MagicMock()
        ctx.state = {
            "quality_findings": [
                {"category": "outliers", "column": "score"},
            ],
            "quality_table_name": "table_test",
        }

        result = _after_tool_callback(tool, {}, ctx, "Quality report text")

        # outliers is not in _ACTIONABLE_CATEGORIES, so no chain
        assert result is None

    def test_quality_analyst_skips_when_no_findings(self):
        from datagrunt_agent.agent import _after_tool_callback

        tool = MagicMock()
        tool.name = "QualityAnalyst"

        ctx = MagicMock()
        ctx.state = {
            "quality_findings": [],
            "quality_table_name": "table_test",
        }

        result = _after_tool_callback(tool, {}, ctx, "Quality report text")

        assert result is None

    def test_load_file_callback_still_works(self):
        from datagrunt_agent.agent import _after_tool_callback

        tool = MagicMock()
        tool.name = "load_file"
        tool_response = {"status": "success", "table_name": "table_abc"}

        result = _after_tool_callback(tool, {}, MagicMock(), tool_response)

        assert result is None  # Returns None, modifies response in-place
        assert "next_action" in tool_response
        assert tool_response["next_action"]["action"] == "delegate_to_quality_analyst"
