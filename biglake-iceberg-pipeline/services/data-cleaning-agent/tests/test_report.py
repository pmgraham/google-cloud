"""Tests for comprehensive quality report builder."""

import json
import os
import tempfile

from unittest.mock import MagicMock

from datagrunt_agent.tools.ingestion import _get_session, load_file
from datagrunt_agent.tools.report import (
    build_quality_report,
    export_quality_report,
    _determine_overall_status,
)


def _make_tool_context():
    ctx = MagicMock()
    ctx.state = {}
    return ctx


class TestDetermineOverallStatus:
    """Test the overall status logic."""

    def test_pass_when_no_findings(self):
        status, reason = _determine_overall_status(
            {"info": 0, "warning": 0, "critical": 0}
        )
        assert status == "pass"
        assert reason is None

    def test_pass_with_info_only(self):
        status, reason = _determine_overall_status(
            {"info": 5, "warning": 0, "critical": 0}
        )
        assert status == "pass"
        assert reason is None

    def test_warn_with_warnings(self):
        status, reason = _determine_overall_status(
            {"info": 2, "warning": 3, "critical": 0}
        )
        assert status == "warn"
        assert "3 warning" in reason

    def test_fail_with_critical(self):
        status, reason = _determine_overall_status(
            {"info": 1, "warning": 2, "critical": 1}
        )
        assert status == "fail"
        assert "1 critical" in reason


class TestBuildQualityReport:
    """Test the full report builder."""

    def test_report_has_all_sections(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()
        table_name = result["table_name"]

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=table_name,
                ingestion_result=result,
                pipeline_result={"processed_at": result.get("processed_at")},
                source_file_path=sample_csv,
                output_dir=tmpdir,
            )

        expected_keys = {
            "report_id", "schema_version", "generated_at",
            "source", "ingestion", "schema", "quality",
            "pipeline", "overall_status", "overall_status_reason",
        }
        assert expected_keys.issubset(report.keys())

    def test_report_id_format(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=result["table_name"],
                ingestion_result=result,
                pipeline_result={},
                source_file_path=sample_csv,
                output_dir=tmpdir,
            )

        assert report["report_id"].startswith("dqr_")
        assert len(report["report_id"]) == 16  # "dqr_" + 12 hex chars

    def test_report_schema_covers_all_columns(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()
        table_name = result["table_name"]

        columns = session.get_column_names(table_name)
        expected_cols = [c for c in columns if c != "processed_at"]

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=table_name,
                ingestion_result=result,
                pipeline_result={},
                source_file_path=sample_csv,
                output_dir=tmpdir,
            )

        schema_cols = [entry["column_name"] for entry in report["schema"]]
        assert set(schema_cols) == set(expected_cols)

    def test_report_findings_no_message_field(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        session = _get_session()

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=result["table_name"],
                ingestion_result=result,
                pipeline_result={},
                source_file_path=quality_data_csv,
                output_dir=tmpdir,
            )

        for finding in report["quality"]["findings"]:
            assert "message" not in finding, (
                f"Finding has prose 'message' field: {finding}"
            )

    def test_report_overall_status_pass(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=result["table_name"],
                ingestion_result=result,
                pipeline_result={},
                source_file_path=sample_csv,
                output_dir=tmpdir,
            )

        assert report["overall_status"] == "pass"

    def test_report_overall_status_warn(self, quality_data_csv):
        ctx = _make_tool_context()
        result = load_file(quality_data_csv, ctx)
        session = _get_session()

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=result["table_name"],
                ingestion_result=result,
                pipeline_result={},
                source_file_path=quality_data_csv,
                output_dir=tmpdir,
            )

        # quality_data.csv has whitespace, null-like strings, duplicates — at least warnings
        assert report["overall_status"] in ("warn", "fail")

    def test_report_persisted_to_disk(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=result["table_name"],
                ingestion_result=result,
                pipeline_result={},
                source_file_path=sample_csv,
                output_dir=tmpdir,
            )

            report_path = report["_persisted_path"]
            assert os.path.exists(report_path)

            with open(report_path) as fh:
                on_disk = json.load(fh)

            assert on_disk["report_id"] == report["report_id"]
            assert on_disk["overall_status"] == report["overall_status"]

    def test_report_source_metadata(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=result["table_name"],
                ingestion_result=result,
                pipeline_result={},
                source_file_path=sample_csv,
                output_dir=tmpdir,
            )

        source = report["source"]
        assert source["file_name"] == "sample.csv"
        assert source["size_bytes"] > 0

    def test_report_ingestion_section(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        session = _get_session()

        with tempfile.TemporaryDirectory() as tmpdir:
            report = build_quality_report(
                session=session,
                table_name=result["table_name"],
                ingestion_result=result,
                pipeline_result={},
                source_file_path=sample_csv,
                output_dir=tmpdir,
            )

        ingestion = report["ingestion"]
        assert ingestion["status"] == "success"
        assert ingestion["loaded_row_count"] == 5


class TestExportQualityReport:
    """Test the export_quality_report tool function."""

    def test_export_generates_report(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_report.json")
            export_result = export_quality_report(
                table_name=result["table_name"],
                output_path=output_path,
            )

            assert export_result["status"] == "success"
            assert export_result["output_path"] == output_path
            assert export_result["format"] == "json"
            assert "overall_status" in export_result
            assert os.path.exists(output_path)

    def test_export_nonexistent_table(self):
        result = export_quality_report(
            table_name="nonexistent_table",
            output_path="/tmp/nope.json",
        )
        assert "error" in result

    def test_export_generates_fresh_report(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)

        # Call export without passing tool_context (no cached report)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "fresh_report.json")
            export_result = export_quality_report(
                table_name=result["table_name"],
                output_path=output_path,
            )
            assert export_result["status"] == "success"
            assert os.path.exists(export_result["output_path"])


class TestLoadFileNoInlineQuality:
    """Test that load_file does NOT run quality scan inline."""

    def test_no_quality_summary_in_result(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        assert result["status"] == "success"
        assert "quality_summary" not in result

    def test_no_quality_report_in_state(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        assert result["status"] == "success"
        assert "quality_report" not in ctx.state


class TestAfterToolCallback:
    """Test the after_tool_callback that injects next_action."""

    def test_callback_injects_next_action_on_load_success(self):
        from datagrunt_agent.agent import _after_tool_callback

        tool = MagicMock()
        tool.name = "load_file"
        tool_response = {"status": "success", "table_name": "table_abc"}

        result = _after_tool_callback(tool, {}, MagicMock(), tool_response)

        assert result is None  # Returns None to keep original response
        assert "next_action" in tool_response
        assert tool_response["next_action"]["action"] == "delegate_to_quality_analyst"
        assert tool_response["next_action"]["table_name"] == "table_abc"

    def test_callback_skips_on_error(self):
        from datagrunt_agent.agent import _after_tool_callback

        tool = MagicMock()
        tool.name = "load_file"
        tool_response = {"error": "File not found"}

        _after_tool_callback(tool, {}, MagicMock(), tool_response)

        assert "next_action" not in tool_response

    def test_callback_skips_other_tools(self):
        from datagrunt_agent.agent import _after_tool_callback

        tool = MagicMock()
        tool.name = "detect_format"
        tool_response = {"status": "success", "table_name": "table_xyz"}

        _after_tool_callback(tool, {}, MagicMock(), tool_response)

        assert "next_action" not in tool_response
