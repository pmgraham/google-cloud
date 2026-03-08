"""Observational data quality reporting tools.

Reports findings but never modifies data. Every finding is structured
for machine consumption (no prose message strings).

Performance: all checks use wide-SELECT with FILTER clauses so the
entire quality scan runs in ~4 queries regardless of column count.
"""

from typing import Any

from google.adk.tools import ToolContext

from datagrunt_agent.core.sql_loader import load_sql
from datagrunt_agent.tools.ingestion import _get_session

# Null-like sentinel values (lowercase) — must match the old per-column SQL
_NULL_LIKE_SENTINELS = (
    "'null'", "'none'", "'n/a'", "'na'", "'-'", "''", "'#n/a'", "'nan'", "'missing'"
)
_NULL_LIKE_IN_CLAUSE = ", ".join(_NULL_LIKE_SENTINELS)


def run_quality_checks(
    session, table_name: str,
) -> tuple[list[dict], dict, list[dict]]:
    """Run all quality checks on a table and return structured findings.

    Uses wide-SELECT with FILTER clauses for single-pass scans.

    Returns:
        Tuple of (findings, severity_counts, summarize_rows).
        summarize_rows can be reused by the report builder for schema snapshot.
    """
    columns = session.get_column_names(table_name)
    column_types = session.get_column_types(table_name)
    total_rows = session.get_row_count(table_name)

    check_columns = [c for c in columns if c != "processed_at"]
    findings: list[dict] = []

    varchar_cols = [c for c in check_columns if column_types.get(c) == "VARCHAR"]
    numeric_cols = [
        c for c in check_columns
        if column_types.get(c) in ("BIGINT", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL")
    ]

    # 1 query: SUMMARIZE → nulls, constant columns, schema snapshot
    summarize_rows = _run_summarize(session, table_name)
    _nulls_from_summarize(summarize_rows, total_rows, findings)
    _constants_from_summarize(summarize_rows, findings)

    all_numeric = list(numeric_cols)

    if total_rows > 0 and varchar_cols:
        # 1 query: type analysis (wide-SELECT with FILTER)
        type_results = _batch_type_analysis(
            session, table_name, varchar_cols, total_rows, findings,
        )

        # 1 query: null-like + whitespace combined (wide-SELECT with FILTER)
        _batch_null_like_and_whitespace(
            session, table_name, varchar_cols, total_rows, findings,
        )

        # Identify numeric-like VARCHAR cols from type_results
        for col, metrics in type_results.items():
            non_null = metrics["non_null"]
            if non_null > 0 and metrics["castable_double"] / non_null > 0.9:
                all_numeric.append(col)

    # 1 query: duplicates
    _check_duplicates(session, table_name, findings)

    # 1 query: outliers (wide-SELECT with CTE bounds)
    if all_numeric:
        _batch_outliers(session, table_name, all_numeric, findings)

    severity_counts = {"info": 0, "warning": 0, "critical": 0}
    for f in findings:
        severity_counts[f.get("severity", "info")] += 1

    return findings, severity_counts, summarize_rows


def quality_report(table_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Run a comprehensive observational quality audit on a loaded table.

    Reports findings across multiple dimensions but changes nothing.

    Args:
        table_name: The DuckDB table to audit. Must already be loaded.

    Returns:
        Dict with structured findings organized by category, each with
        severity level and typed metrics.
    """
    session = _get_session()

    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found. Load a file first."}

    total_rows = session.get_row_count(table_name)
    columns = session.get_column_names(table_name)
    check_columns = [c for c in columns if c != "processed_at"]

    findings, severity_counts, _summarize = run_quality_checks(session, table_name)

    # Store findings in session state for downstream agents (DataCleaner)
    tool_context.state["quality_findings"] = findings
    tool_context.state["quality_table_name"] = table_name

    return {
        "table_name": table_name,
        "total_rows": total_rows,
        "total_columns": len(check_columns),
        "findings": findings,
        "severity_counts": severity_counts,
    }


# ---------------------------------------------------------------------------
# Batched helpers — wide-SELECT with FILTER
# ---------------------------------------------------------------------------

def _run_summarize(session, table_name: str) -> list[dict]:
    """Run SUMMARIZE and return results as a list of dicts."""
    sql = load_sql("profiling", "column_stats", table_name=table_name)
    return session.execute_to_polars(sql).to_dicts()


def _nulls_from_summarize(
    summarize_rows: list[dict], total_rows: int, findings: list,
):
    """Extract null findings from SUMMARIZE results (null_percentage column)."""
    if total_rows == 0:
        return

    for row in summarize_rows:
        col = row.get("column_name")
        if col == "processed_at":
            continue
        null_pct = row.get("null_percentage", 0) or 0
        null_rate = null_pct / 100.0
        if null_rate > 0.5:
            null_count = int(round(null_rate * total_rows))
            severity = "critical" if null_rate > 0.9 else "warning"
            findings.append({
                "category": "null_analysis",
                "severity": severity,
                "column": col,
                "null_count": null_count,
                "null_rate": round(null_rate, 4),
            })


def _constants_from_summarize(summarize_rows: list[dict], findings: list):
    """Extract constant-column finding from SUMMARIZE results."""
    constant_cols = [
        row["column_name"]
        for row in summarize_rows
        if row.get("column_name") != "processed_at"
        and (row.get("approx_unique") or 0) <= 1
    ]
    if constant_cols:
        findings.append({
            "category": "constant_columns",
            "severity": "info",
            "columns": constant_cols,
        })


def _batch_type_analysis(
    session, table_name: str, varchar_cols: list[str],
    total_rows: int, findings: list,
) -> dict[str, dict]:
    """Run type castability analysis for all VARCHAR cols in one query.

    Returns dict mapping col -> {non_null, castable_double, castable_date,
    castable_boolean, leading_zeros} for downstream use (outlier pre-check).
    """
    if not varchar_cols:
        return {}

    # Build wide-SELECT with 5 FILTER expressions per column
    select_parts = []
    for col in varchar_cols:
        q = f'"{col}"'
        select_parts.extend([
            f'COUNT({q}) FILTER (WHERE {q} IS NOT NULL) AS "{col}__non_null"',
            f'COUNT(*) FILTER (WHERE TRY_CAST({q} AS DOUBLE) IS NOT NULL) AS "{col}__castable_double"',
            f'COUNT(*) FILTER (WHERE TRY_CAST({q} AS DATE) IS NOT NULL) AS "{col}__castable_date"',
            f"COUNT(*) FILTER (WHERE LOWER(TRIM({q})) IN ('true','false','0','1','yes','no')) "
            f'AS "{col}__castable_boolean"',
            f"COUNT(*) FILTER (WHERE {q} LIKE '0%' AND LENGTH({q}) > 1 "
            f'AND TRY_CAST({q} AS BIGINT) IS NOT NULL) AS "{col}__leading_zeros"',
        ])

    sql = f"SELECT {', '.join(select_parts)} FROM {table_name}"
    row = session.execute(sql).fetchone()

    # Parse the single result row back into per-column dicts
    results: dict[str, dict] = {}
    idx = 0
    for col in varchar_cols:
        non_null = row[idx] or 0
        castable_double = row[idx + 1] or 0
        castable_date = row[idx + 2] or 0
        castable_boolean = row[idx + 3] or 0
        leading_zeros = row[idx + 4] or 0
        idx += 5

        results[col] = {
            "non_null": non_null,
            "castable_double": castable_double,
            "castable_date": castable_date,
            "castable_boolean": castable_boolean,
            "leading_zeros": leading_zeros,
        }

        if non_null == 0:
            continue

        numeric_rate = round(castable_double / non_null, 4)
        date_rate = round(castable_date / non_null, 4)
        boolean_rate = round(castable_boolean / non_null, 4)

        has_notable = (
            leading_zeros > 0
            or numeric_rate > 0.9
            or date_rate > 0.9
            or boolean_rate > 0.9
        )
        if not has_notable:
            continue

        severity = "info"
        suggested_cast = None

        if leading_zeros > 0 and numeric_rate > 0.5:
            severity = "warning"
            suggested_cast = None
        elif boolean_rate > 0.9:
            suggested_cast = "BOOLEAN"
        elif date_rate > 0.9:
            suggested_cast = "DATE"
        elif numeric_rate > 0.9:
            suggested_cast = "DOUBLE"

        findings.append({
            "category": "type_analysis",
            "severity": severity,
            "column": col,
            "numeric_castable_rate": numeric_rate,
            "date_castable_rate": date_rate,
            "boolean_castable_rate": boolean_rate,
            "leading_zero_count": leading_zeros,
            "suggested_cast": suggested_cast,
        })

    return results


def _batch_null_like_and_whitespace(
    session, table_name: str, varchar_cols: list[str],
    total_rows: int, findings: list,
):
    """Run null-like value counts and whitespace checks in one query."""
    if not varchar_cols:
        return

    select_parts = []
    for col in varchar_cols:
        q = f'"{col}"'
        select_parts.append(
            f"COUNT(*) FILTER (WHERE LOWER(TRIM({q}::VARCHAR)) IN ({_NULL_LIKE_IN_CLAUSE})) "
            f'AS "{col}__null_like"'
        )
        select_parts.append(
            f"COUNT(*) FILTER (WHERE {q} IS NOT NULL AND {q} != TRIM({q})) "
            f'AS "{col}__whitespace"'
        )

    sql = f"SELECT {', '.join(select_parts)} FROM {table_name}"
    row = session.execute(sql).fetchone()

    idx = 0
    for col in varchar_cols:
        null_like_count = row[idx] or 0
        whitespace_count = row[idx + 1] or 0
        idx += 2

        if null_like_count > 0:
            # Fetch value breakdown for this column (lightweight — only flagged cols)
            breakdown_sql = load_sql(
                "quality", "null_like_values",
                table_name=table_name, column_name=col,
            )
            breakdown_rows = session.execute(breakdown_sql).fetchall()
            values = {str(r[0]): r[1] for r in breakdown_rows}

            findings.append({
                "category": "null_like_strings",
                "severity": "warning",
                "column": col,
                "total_count": null_like_count,
                "values": values,
            })

        if whitespace_count > 0:
            rate = whitespace_count / total_rows if total_rows > 0 else 0
            findings.append({
                "category": "whitespace",
                "severity": "warning",
                "column": col,
                "affected_count": whitespace_count,
                "affected_rate": round(rate, 4),
            })


def _check_duplicates(session, table_name: str, findings: list):
    """Check for approximate duplicate rows using hash-based approach."""
    try:
        sql = load_sql("quality", "approximate_duplicates", table_name=table_name)
        result = session.execute(sql).fetchone()
        if result and result[0] > 0:
            count = result[0]
            severity = "critical" if count > 100 else "warning"
            findings.append({
                "category": "duplicates",
                "severity": severity,
                "approximate_count": count,
            })
    except Exception:
        pass


def _batch_outliers(
    session, table_name: str, numeric_cols: list[str], findings: list,
):
    """Run IQR-based outlier detection for all numeric columns in one query."""
    if not numeric_cols:
        return

    # Build CTE for quantile bounds
    bounds_parts = []
    for col in numeric_cols:
        q = f'TRY_CAST("{col}" AS DOUBLE)'
        bounds_parts.append(f"approx_quantile({q}, 0.25) AS \"{col}__q1\"")
        bounds_parts.append(f"approx_quantile({q}, 0.75) AS \"{col}__q3\"")

    bounds_sql = f"SELECT {', '.join(bounds_parts)} FROM {table_name}"

    # Build main SELECT for outlier counts + bounds
    select_parts = []
    for col in numeric_cols:
        q = f'TRY_CAST("{col}" AS DOUBLE)'
        q1 = f'"{col}__q1"'
        q3 = f'"{col}__q3"'
        iqr = f"({q3} - {q1})"
        lower = f"({q1} - 1.5 * {iqr})"
        upper = f"({q3} + 1.5 * {iqr})"

        select_parts.append(
            f"COUNT(*) FILTER (WHERE {q} < {lower} OR {q} > {upper}) "
            f'AS "{col}__outlier_count"'
        )
        select_parts.append(f'{lower} AS "{col}__lower_bound"')
        select_parts.append(f'{upper} AS "{col}__upper_bound"')

    sql = (
        f"WITH bounds AS ({bounds_sql}) "
        f"SELECT {', '.join(select_parts)} FROM {table_name}, bounds"
    )

    try:
        row = session.execute(sql).fetchone()
    except Exception:
        return

    idx = 0
    for col in numeric_cols:
        outlier_count = row[idx] or 0
        lower_bound = row[idx + 1]
        upper_bound = row[idx + 2]
        idx += 3

        if outlier_count > 0:
            findings.append({
                "category": "outliers",
                "severity": "info",
                "column": col,
                "outlier_count": outlier_count,
                "lower_bound": float(lower_bound) if lower_bound is not None else None,
                "upper_bound": float(upper_bound) if upper_bound is not None else None,
            })
