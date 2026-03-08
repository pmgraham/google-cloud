"""Cleaning report builder — structured JSON report for cleaning operations.

Follows the same pattern as report.py (quality report builder).
Generates a self-contained JSON report covering source metadata,
before/after metrics, per-operation details, PII flags, identifier
columns, and numeric precision observations.
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


def _generate_report_id() -> str:
    return f"dcr_{uuid.uuid4().hex[:12]}"


def build_cleaning_report(
    cleaning_result: dict,
    quality_findings: list[dict],
    source_file_path: str,
    output_dir: str,
) -> dict[str, Any]:
    """Build a comprehensive cleaning report and persist to JSON.

    Args:
        cleaning_result: The result dict from clean_table().
        quality_findings: The original quality findings that drove cleaning.
        source_file_path: Original source file path.
        output_dir: Directory to write the report JSON.

    Returns:
        The full report dict. Includes internal '_persisted_path' key.
    """
    report: dict[str, Any] = {
        "report_id": _generate_report_id(),
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Source metadata
    report["source"] = {
        "file_path": source_file_path,
        "file_name": Path(source_file_path).name if source_file_path else "",
        "table_name": cleaning_result.get("table_name", ""),
    }

    # Summary
    report["summary"] = {
        "before_rows": cleaning_result.get("before_rows", 0),
        "after_rows": cleaning_result.get("after_rows", 0),
        "before_columns": cleaning_result.get("before_columns", 0),
        "after_columns": cleaning_result.get("after_columns", 0),
        "columns_added": cleaning_result.get("columns_added", 0),
        "columns_removed": cleaning_result.get("columns_removed", 0),
        "operations_applied": len(cleaning_result.get("operations", [])),
    }

    # Per-operation results
    report["operations"] = cleaning_result.get("operations", [])

    # PII detection
    pii = cleaning_result.get("pii_detection", [])
    report["pii_detection"] = [
        {
            "column": item.get("column", ""),
            "pii_type": item.get("pii_type", "unknown"),
            "confidence": item.get("confidence", 0.0),
            "recommendation": f"Review column for {item.get('pii_type', 'PII')} data before sharing.",
        }
        for item in pii
    ]

    # Identifier columns preserved
    report["identifier_columns"] = [
        {
            "column": item.get("column", ""),
            "pattern": item.get("pattern", "unknown"),
            "preserved_as": item.get("preserved_as", "VARCHAR"),
        }
        for item in cleaning_result.get("identifier_columns", [])
    ]

    # Numeric precision flags
    report["numeric_precision_flags"] = cleaning_result.get(
        "numeric_precision_flags", [],
    )

    # Quality findings input count
    report["quality_findings_input"] = len(quality_findings)

    # Overall status
    operations = cleaning_result.get("operations", [])
    if operations:
        report["overall_status"] = "cleaned"
    else:
        report["overall_status"] = "no_action_needed"

    # Persist to disk
    os.makedirs(output_dir, exist_ok=True)
    stem = Path(source_file_path).stem if source_file_path else "unknown"
    report_path = os.path.join(output_dir, f"{stem}_cleaning_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    report["_persisted_path"] = report_path
    return report


def export_cleaning_report(
    table_name: str,
    output_path: str = "",
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Export the cleaning report as a JSON file.

    If a report was already generated during clean_table, re-exports it.
    Otherwise returns an error indicating no cleaning has been run.

    Args:
        table_name: The DuckDB table the cleaning was performed on.
        output_path: Destination file path. Defaults to output_dir/{table_name}_cleaning_report.json.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found. Load a file first."}

    # Check for existing report in session state
    existing_report = None
    if tool_context and tool_context.state.get("cleaning_report"):
        existing = tool_context.state["cleaning_report"]
        if existing.get("source", {}).get("table_name") == table_name:
            existing_report = existing

    if not existing_report:
        return {
            "error": (
                f"No cleaning report found for table '{table_name}'. "
                "Run clean_table first."
            ),
        }

    if not output_path:
        from datagrunt_agent.tools.ingestion import _get_output_dir
        output_dir = _get_output_dir()
        output_path = os.path.join(output_dir, f"{table_name}_cleaning_report.json")

    # Re-persist existing report to requested path
    report = {k: v for k, v in existing_report.items() if not k.startswith("_")}
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    return {
        "status": "success",
        "output_path": output_path,
        "format": "json",
        "overall_status": existing_report.get("overall_status"),
    }
