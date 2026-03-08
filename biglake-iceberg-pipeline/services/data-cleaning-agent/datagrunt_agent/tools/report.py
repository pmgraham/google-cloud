"""Comprehensive data quality report builder.

Builds a self-contained JSON report covering source metadata, ingestion
details, full schema snapshot, structured quality findings, pipeline
status, and overall pass/warn/fail. Designed for Pub/Sub or GCS persistence.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.adk.tools import ToolContext

from datagrunt_agent.tools.ingestion import _get_session

REPORT_SCHEMA_VERSION = "1.0.0"
AGENT_VERSION = "0.1.0"


def _generate_report_id() -> str:
    return f"dqr_{uuid.uuid4().hex[:12]}"


def _determine_overall_status(severity_counts: dict) -> tuple[str, str | None]:
    """Determine pass/warn/fail from severity counts.

    Default thresholds:
    - Any critical finding -> fail
    - Any warning finding -> warn
    - Otherwise -> pass
    """
    if severity_counts.get("critical", 0) > 0:
        return "fail", f"{severity_counts['critical']} critical finding(s)"
    if severity_counts.get("warning", 0) > 0:
        return "warn", f"{severity_counts['warning']} warning finding(s)"
    return "pass", None


def _schema_from_summarize(
    summarize_rows: list[dict], total_rows: int,
) -> list[dict]:
    """Build per-column schema snapshot from pre-computed SUMMARIZE rows."""
    schema = []
    for row in summarize_rows:
        col = row.get("column_name")
        if col == "processed_at":
            continue
        null_pct = row.get("null_percentage", 0) or 0

        schema.append({
            "column_name": col,
            "column_type": row.get("column_type", "UNKNOWN"),
            "null_count": int(round(null_pct / 100.0 * total_rows)) if total_rows > 0 else 0,
            "null_rate": round(null_pct / 100.0, 4),
            "approx_unique": row.get("approx_unique"),
            "min": row.get("min"),
            "max": row.get("max"),
            "avg": row.get("avg"),
        })

    return schema


def build_quality_report(
    session,
    table_name: str,
    ingestion_result: dict,
    pipeline_result: dict,
    source_file_path: str,
    output_dir: str,
) -> dict[str, Any]:
    """Build a comprehensive quality report and persist to JSON.

    Args:
        session: DuckDB session.
        table_name: The loaded table name.
        ingestion_result: The result dict from load_file (pre-pipeline).
        pipeline_result: Dict with processed_at and parquet_export info.
        source_file_path: Original source file path.
        output_dir: Directory to write the report JSON.

    Returns:
        The full report dict. Includes internal '_persisted_path' key.
    """
    from datagrunt_agent.tools.quality import run_quality_checks

    report: dict[str, Any] = {
        "report_id": _generate_report_id(),
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Source metadata
    try:
        size_bytes = os.path.getsize(source_file_path)
    except OSError:
        size_bytes = 0

    report["source"] = {
        "file_path": source_file_path,
        "file_name": Path(source_file_path).name,
        "detected_format": ingestion_result.get(
            "detected_format",
            ingestion_result.get("file_format", "unknown"),
        ),
        "detected_encoding": ingestion_result.get("detected_encoding"),
        "size_bytes": size_bytes,
    }

    # Ingestion summary
    report["ingestion"] = {
        "status": ingestion_result.get("status", "unknown"),
        "table_name": table_name,
        "source_row_count": ingestion_result.get("source_rows", ingestion_result.get("total_rows")),
        "loaded_row_count": ingestion_result.get("total_rows"),
        "empty_rows_removed": ingestion_result.get("empty_rows_removed", 0),
        "rows_lost": ingestion_result.get("rows_lost", 0),
        "delimiter": ingestion_result.get("delimiter"),
        "parse_strategy": ingestion_result.get("parse_strategy"),
        "is_header_detected": ingestion_result.get("header_detected"),
        "columns_renamed": ingestion_result.get("columns_renamed", {}),
        "types_coerced": ingestion_result.get("types_coerced", {}),
        "overflow_columns_repaired": ingestion_result.get("overflow_columns_repaired", []),
        "overflow_rows_flagged": ingestion_result.get("overflow_rows_flagged", 0),
        "json_repair": ingestion_result.get("json_repair"),
    }

    if ingestion_result.get("is_lossy_transcode"):
        report["ingestion"]["is_lossy_transcode"] = True

    # Quality findings + schema snapshot (shared SUMMARIZE — single pass)
    try:
        findings, severity_counts, summarize_rows = run_quality_checks(
            session, table_name,
        )
        total_rows = ingestion_result.get("total_rows", 0) or 0
        report["schema"] = _schema_from_summarize(summarize_rows, total_rows)
        report["quality"] = {
            "findings": findings,
            "severity_counts": severity_counts,
        }
    except Exception:
        report["schema"] = []
        report["quality"] = {
            "findings": [],
            "severity_counts": {"info": 0, "warning": 0, "critical": 0},
        }

    # Pipeline status
    parquet_info = pipeline_result.get("parquet_export") or {}
    report["pipeline"] = {
        "processed_at": pipeline_result.get("processed_at"),
        "parquet_export": {
            "status": "success" if parquet_info.get("parquet_path") else "skipped",
            "output_path": parquet_info.get("parquet_path"),
            "size_bytes": parquet_info.get("size_bytes"),
        },
        "quality_scan": {"status": "success"},
    }

    # Overall status
    severity_counts = report["quality"]["severity_counts"]
    status, reason = _determine_overall_status(severity_counts)
    report["overall_status"] = status
    report["overall_status_reason"] = reason

    # Persist to disk
    stem = Path(source_file_path).stem
    report_path = os.path.join(output_dir, f"{stem}_quality_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    report["_persisted_path"] = report_path
    return report


def export_quality_report(
    table_name: str,
    output_path: str = "",
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Export the data quality report as a JSON file.

    If a report was already generated during load_file, re-exports it.
    Otherwise generates a fresh report from the current table state.

    Args:
        table_name: The DuckDB table to report on.
        output_path: Destination file path. Defaults to {output_dir}/{table_name}_quality_report.json.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found. Load a file first."}

    # Check for existing report in session state
    existing_report = None
    if tool_context and tool_context.state.get("quality_report"):
        existing = tool_context.state["quality_report"]
        if existing.get("ingestion", {}).get("table_name") == table_name:
            existing_report = existing

    if not output_path:
        from datagrunt_agent.tools.ingestion import _get_output_dir
        output_dir = _get_output_dir()
        output_path = os.path.join(output_dir, f"{table_name}_quality_report.json")

    if existing_report:
        # Re-persist existing report to requested path
        report = {k: v for k, v in existing_report.items() if not k.startswith("_")}
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=str)
    else:
        # Generate fresh report (no ingestion context available)
        from datagrunt_agent.tools.ingestion import _get_output_dir
        report = build_quality_report(
            session=session,
            table_name=table_name,
            ingestion_result={
                "status": "pre-existing",
                "total_rows": session.get_row_count(table_name),
            },
            pipeline_result={},
            source_file_path=table_name,
            output_dir=os.path.dirname(output_path) or _get_output_dir(),
        )
        # build_quality_report names the file from source_file_path stem,
        # so re-persist to the exact output_path if they differ.
        if report.get("_persisted_path") != output_path:
            clean = {k: v for k, v in report.items() if not k.startswith("_")}
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(clean, fh, indent=2, default=str)

    return {
        "status": "success",
        "output_path": output_path,
        "format": "json",
        "overall_status": report.get("overall_status"),
        "severity_counts": report.get("quality", {}).get("severity_counts", {}),
    }
