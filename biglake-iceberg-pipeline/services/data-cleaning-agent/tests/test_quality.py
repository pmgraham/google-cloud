"""Tests for quality reporting tools."""

from unittest.mock import MagicMock

from datagrunt_agent.tools.ingestion import _get_session, load_file
from datagrunt_agent.tools.quality import quality_report


def _make_tool_context():
    ctx = MagicMock()
    ctx.state = {}
    return ctx


class TestProcessedAt:
    """Test that processed_at timestamp is added to every load."""

    def test_processed_at_in_result(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        assert result["status"] == "success"
        assert "processed_at" in result

    def test_processed_at_is_iso_format(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        ts = result["processed_at"]
        # Should be ISO format like 2024-01-15T10:30:00+00:00
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_processed_at_column_in_table(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()
        table_name = result["table_name"]
        columns = session.get_column_names(table_name)
        assert "processed_at" in columns


class TestParquetExport:
    """Test that Parquet auto-export works after load."""

    def test_parquet_output_in_result(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        assert result["status"] == "success"
        assert "output" in result
        assert "parquet_path" in result["output"]
        assert "size_bytes" in result["output"]

    def test_parquet_file_exists(self, sample_csv):
        import os
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        parquet_path = result["output"]["parquet_path"]
        assert os.path.exists(parquet_path)
        # Cleanup
        os.unlink(parquet_path)

    def test_parquet_path_matches_source_name(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        parquet_path = result["output"]["parquet_path"]
        assert parquet_path.endswith("sample.parquet")
        # Cleanup
        import os
        os.unlink(parquet_path)

    def test_custom_output_dir(self, sample_csv):
        import os
        import shutil
        import tempfile
        custom_dir = tempfile.mkdtemp()
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx, output_dir=custom_dir)
        parquet_path = result["output"]["parquet_path"]
        assert parquet_path.startswith(custom_dir)
        assert os.path.exists(parquet_path)
        # Cleanup
        shutil.rmtree(custom_dir)


class TestQualityReport:
    """Test the full quality_report tool."""

    def test_quality_report_on_loaded_table(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        assert result["status"] == "success"

        table_name = result["table_name"]
        report = quality_report(table_name, ctx)
        assert "findings" in report
        assert "severity_counts" in report
        assert report["table_name"] == table_name
        assert report["total_rows"] == result["total_rows"]

    def test_quality_report_nonexistent_table(self):
        ctx = _make_tool_context()
        result = quality_report("nonexistent_table", ctx)
        assert "error" in result

    def test_quality_report_finds_whitespace(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        table_name = result["table_name"]

        report = quality_report(table_name, ctx)
        whitespace_findings = [
            f for f in report["findings"] if f["category"] == "whitespace"
        ]
        # quality_data.csv has whitespace issues in name and notes columns
        assert len(whitespace_findings) > 0

    def test_quality_report_finds_null_like_strings(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        table_name = result["table_name"]

        report = quality_report(table_name, ctx)
        null_like_findings = [
            f for f in report["findings"] if f["category"] == "null_like_strings"
        ]
        # quality_data.csv has NULL, N/A, None, n/a values
        assert len(null_like_findings) > 0

    def test_quality_report_finds_leading_zeros(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        table_name = result["table_name"]

        report = quality_report(table_name, ctx)
        type_findings = [
            f for f in report["findings"]
            if f["category"] == "type_analysis" and f.get("leading_zero_count", 0) > 0
        ]
        # quality_data.csv has zip codes with leading zeros (07102, 08901, etc.)
        assert len(type_findings) > 0

    def test_quality_report_finds_constant_columns(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        table_name = result["table_name"]

        report = quality_report(table_name, ctx)
        constant_findings = [
            f for f in report["findings"] if f["category"] == "constant_columns"
        ]
        # quality_data.csv has "status" column with all "active" values
        assert len(constant_findings) > 0
        # "status" should be in the constant columns list
        for f in constant_findings:
            assert "status" in f["columns"]

    def test_quality_report_severity_counts(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        table_name = result["table_name"]

        report = quality_report(table_name, ctx)
        counts = report["severity_counts"]
        assert "info" in counts
        assert "warning" in counts
        assert "critical" in counts
        total = counts["info"] + counts["warning"] + counts["critical"]
        assert total == len(report["findings"])
