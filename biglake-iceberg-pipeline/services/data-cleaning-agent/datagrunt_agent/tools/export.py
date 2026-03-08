"""Export tools for saving DuckDB tables to various file formats."""

import os
from typing import Any

from google.adk.tools import ToolContext

from datagrunt_agent.core.sql_loader import load_sql
from datagrunt_agent.tools.ingestion import _get_session


def _resolve_output_path(table_name: str, output_path: str, extension: str) -> str:
    """Resolve the output file path, generating a default if not provided."""
    if output_path:
        return os.path.abspath(output_path)
    return os.path.abspath(f"{table_name}_export{extension}")


def export_csv(
    table_name: str,
    output_path: str = "",
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Export a DuckDB table to a CSV file.

    Args:
        table_name: The DuckDB table to export.
        output_path: Destination file path. If empty, uses table_name_export.csv.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found."}

    output_path = _resolve_output_path(table_name, output_path, ".csv")
    sql = load_sql("export", "to_csv", table_name=table_name, output_path=output_path)
    session.execute(sql)

    row_count = session.get_row_count(table_name)
    return {
        "status": "success",
        "output_path": output_path,
        "format": "csv",
        "rows_exported": row_count,
    }


def export_parquet(
    table_name: str,
    output_path: str = "",
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Export a DuckDB table to a Parquet file.

    Args:
        table_name: The DuckDB table to export.
        output_path: Destination file path. If empty, uses table_name_export.parquet.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found."}

    output_path = _resolve_output_path(table_name, output_path, ".parquet")
    sql = load_sql("export", "to_parquet", table_name=table_name, output_path=output_path)
    session.execute(sql)

    row_count = session.get_row_count(table_name)
    return {
        "status": "success",
        "output_path": output_path,
        "format": "parquet",
        "rows_exported": row_count,
    }


def export_json(
    table_name: str,
    output_path: str = "",
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Export a DuckDB table to a JSON file (array format).

    Args:
        table_name: The DuckDB table to export.
        output_path: Destination file path. If empty, uses table_name_export.json.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found."}

    output_path = _resolve_output_path(table_name, output_path, ".json")
    sql = load_sql("export", "to_json", table_name=table_name, output_path=output_path)
    session.execute(sql)

    row_count = session.get_row_count(table_name)
    return {
        "status": "success",
        "output_path": output_path,
        "format": "json",
        "rows_exported": row_count,
    }


def export_jsonl(
    table_name: str,
    output_path: str = "",
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Export a DuckDB table to a JSONL file (newline-delimited JSON).

    Args:
        table_name: The DuckDB table to export.
        output_path: Destination file path. If empty, uses table_name_export.jsonl.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found."}

    output_path = _resolve_output_path(table_name, output_path, ".jsonl")
    sql = load_sql("export", "to_jsonl", table_name=table_name, output_path=output_path)
    session.execute(sql)

    row_count = session.get_row_count(table_name)
    return {
        "status": "success",
        "output_path": output_path,
        "format": "jsonl",
        "rows_exported": row_count,
    }


def export_excel(
    table_name: str,
    output_path: str = "",
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Export a DuckDB table to an Excel (.xlsx) file.

    Requires the DuckDB spatial extension.

    Args:
        table_name: The DuckDB table to export.
        output_path: Destination file path. If empty, uses table_name_export.xlsx.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found."}

    output_path = _resolve_output_path(table_name, output_path, ".xlsx")
    sql = load_sql("export", "to_excel", table_name=table_name, output_path=output_path)

    try:
        session.execute(sql)
    except Exception as exc:
        return {
            "error": f"Excel export failed: {exc}",
            "suggestion": "Ensure the DuckDB spatial extension is available.",
        }

    row_count = session.get_row_count(table_name)
    return {
        "status": "success",
        "output_path": output_path,
        "format": "xlsx",
        "rows_exported": row_count,
    }
