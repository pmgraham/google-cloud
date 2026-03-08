"""Data profiling tools for column-level and table-level analysis."""

from typing import Any

from google.adk.tools import ToolContext

from datagrunt_agent.core.sql_loader import load_sql
from datagrunt_agent.tools.ingestion import _get_session


def profile_columns(table_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Analyze schema and produce per-column statistics for a loaded table.

    Returns for each column: name, DuckDB type, approximate unique count,
    null percentage, min, max, and average. Also suggests type coercions
    (e.g., a VARCHAR column that looks like numbers or dates).

    This is a batch operation — profiles ALL columns in one call to minimize
    LLM round-trips.

    Args:
        table_name: The DuckDB table name (returned by load_file).
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found. Use load_file first."}

    # Column statistics via DuckDB SUMMARIZE
    sql = load_sql("profiling", "column_stats", table_name=table_name)
    stats = session.execute_to_polars(sql).to_dicts()

    columns = session.get_column_names(table_name)
    total_rows = session.get_row_count(table_name)

    # Type coercion suggestions for VARCHAR columns
    coercion_suggestions = []
    for col in columns:
        col_type = session.get_column_types(table_name).get(col, "")
        if "VARCHAR" not in col_type.upper():
            continue

        # Check number potential (strips $, %, commas)
        sql = load_sql("profiling", "number_potential", table_name=table_name, column_name=col)
        number_count = session.execute(sql).fetchone()[0]

        # Check date potential
        sql = load_sql("profiling", "date_potential", table_name=table_name, column_name=col)
        date_count = session.execute(sql).fetchone()[0]

        sql = load_sql("common", "non_null_count", table_name=table_name, column_name=col)
        non_null_count = session.execute(sql).fetchone()[0]

        suggestions = []
        if non_null_count > 0:
            if number_count / non_null_count > 0.9:
                suggestions.append("DOUBLE")
            if date_count / non_null_count > 0.9:
                suggestions.append("DATE")

        if suggestions:
            coercion_suggestions.append({
                "column": col,
                "suggested_types": suggestions,
            })

    return {
        "table_name": table_name,
        "total_rows": total_rows,
        "total_columns": len(columns),
        "column_stats": stats,
        "type_coercion_suggestions": coercion_suggestions,
    }


def profile_table(table_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Produce table-level summary statistics.

    Returns row count, column count, and estimated memory usage.

    Args:
        table_name: The DuckDB table name.
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found. Use load_file first."}

    total_rows = session.get_row_count(table_name)
    columns = session.get_column_types(table_name)

    # Null count per column
    null_summary = []
    for col in columns:
        sql = load_sql("common", "null_count", table_name=table_name, column_name=col)
        null_count = session.execute(sql).fetchone()[0]
        null_pct = round(null_count * 100.0 / total_rows, 2) if total_rows > 0 else 0
        null_summary.append({
            "column": col,
            "null_count": null_count,
            "null_percentage": null_pct,
        })

    return {
        "table_name": table_name,
        "total_rows": total_rows,
        "total_columns": len(columns),
        "schema": [
            {"name": name, "type": col_type} for name, col_type in columns.items()
        ],
        "null_summary": null_summary,
    }


def sample_data(
    table_name: str, n: int = 10, tool_context: ToolContext = None
) -> dict[str, Any]:
    """Return N sample rows from a table as a markdown table.

    Args:
        table_name: The DuckDB table name.
        n: Number of rows to sample (default 10, max 100).
    """
    session = _get_session()
    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found. Use load_file first."}

    n = min(max(1, n), 100)
    sql = load_sql("common", "sample_rows", table_name=table_name, limit=str(n))
    sample = session.execute(sql).pl()

    return {
        "table_name": table_name,
        "rows_returned": len(sample),
        "sample": session.to_markdown(sample),
    }
