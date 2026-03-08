"""Data cleaning tools — in-place table modification based on quality findings.

Executes a strict cleaning protocol in a fixed order:
1. Unknown character replacement (U+FFFD, mojibake)
2. Whitespace trimming
3. Empty string → NULL normalization
4. Null-like string normalization (sentinels → NULL)
5. Date standardization (YYYY-MM-DD)
6. Type coercion (VARCHAR → tighter types, skip identifiers)
7. Mixed-case normalization (low-cardinality categoricals → lowercase)
8. Soft dedup (add is_duplicate flag, never delete rows)
9. High-null column removal (>90% null rate)
10. Constant column removal (cardinality of 1)
11. PII detection (LLM-assisted, informational)
12. Numeric precision validation (informational)

Uses session.execute() (not execute_safe) because ALTER TABLE ADD/DROP
COLUMN is required. TRY_CAST is used for type coercion so non-castable
values become NULL instead of erroring.
"""

import json
import os
from typing import Any

from google.adk.tools import ToolContext

from datagrunt_agent.core.sql_loader import load_sql
from datagrunt_agent.tools.ingestion import _get_session

# Null-like sentinel values — must match quality.py
_NULL_LIKE_SENTINELS = (
    "'null'", "'none'", "'n/a'", "'na'", "'-'", "''",
    "'#n/a'", "'nan'", "'missing'",
)
_SENTINEL_LIST = ", ".join(_NULL_LIKE_SENTINELS)

# Common mojibake replacements (Windows-1252 -> UTF-8 misinterpretation)
# Keys are the mojibake sequences, values are the correct UTF-8 characters.
_MOJIBAKE_MAP = {
    "\u00c3\u00a9": "\u00e9",   # Ã© -> é
    "\u00c3\u00a1": "\u00e1",   # Ã¡ -> á
    "\u00c3\u00ad": "\u00ed",   # Ã­ -> í
    "\u00c3\u00b3": "\u00f3",   # Ã³ -> ó
    "\u00c3\u00ba": "\u00fa",   # Ãº -> ú
    "\u00c3\u00b1": "\u00f1",   # Ã± -> ñ
    "\u00c3\u00bc": "\u00fc",   # Ã¼ -> ü
    "\u00c3\u00b6": "\u00f6",   # Ã¶ -> ö
    "\u00c3\u00a4": "\u00e4",   # Ã¤ -> ä
    "\u00c3\u00ab": "\u00eb",   # Ã« -> ë
    "\u00c3\u00af": "\u00ef",   # Ã¯ -> ï
    "\u00c3\u00a7": "\u00e7",   # Ã§ -> ç
    "\u00c2\u00b0": "\u00b0",   # Â° -> °
    "\u00c2\u00a3": "\u00a3",   # Â£ -> £
    "\u00c2\u00a9": "\u00a9",   # Â© -> ©
}

# Protected columns that should never be dropped or modified by cleaning
_PROTECTED_COLUMNS = {"processed_at", "is_duplicate"}


def clean_table(table_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """Execute the full cleaning protocol on a loaded table.

    Reads quality findings from tool_context.state["quality_findings"]
    and applies cleaning operations in strict order.

    Args:
        table_name: The DuckDB table to clean. Must already be loaded.

    Returns:
        Dict with status, before/after metrics, per-operation results,
        PII detection flags, identifier columns, and cleaning_report_path.
    """
    session = _get_session()

    if not session.table_exists(table_name):
        return {"error": f"Table '{table_name}' not found. Load a file first."}

    findings = tool_context.state.get("quality_findings", [])
    source_file = tool_context.state.get("current_file", "")

    # Snapshot before-state
    before_rows = session.get_row_count(table_name)
    before_types = session.get_column_types(table_name)
    before_columns = len([c for c in before_types if c != "processed_at"])

    # Collect column metadata
    column_types = session.get_column_types(table_name)
    all_columns = [c for c in column_types if c != "processed_at"]
    varchar_cols = [c for c in all_columns if column_types[c] == "VARCHAR"]

    # Run cleaning operations in strict order
    operations = []

    # 1. Unknown character replacement
    op = _clean_unknown_chars(session, table_name, varchar_cols)
    if op:
        operations.append(op)

    # 2. Whitespace trimming
    op = _clean_whitespace(session, table_name, varchar_cols, findings)
    if op:
        operations.append(op)

    # 3. Empty string → NULL
    op = _clean_empty_strings(session, table_name, varchar_cols)
    if op:
        operations.append(op)

    # 4. Null-like string normalization
    op = _clean_null_like_strings(session, table_name, findings)
    if op:
        operations.append(op)

    # 5. Date standardization
    op = _standardize_dates(session, table_name, findings)
    if op:
        operations.append(op)

    # 6. Type coercion
    identifier_columns = []
    op, identifiers = _clean_type_coercion(session, table_name, findings)
    identifier_columns = identifiers
    if op:
        operations.append(op)

    # 7. Mixed-case normalization (refresh column types after coercion)
    column_types = session.get_column_types(table_name)
    varchar_cols_post = [
        c for c in column_types
        if column_types[c] == "VARCHAR" and c not in _PROTECTED_COLUMNS
    ]
    op = _normalize_case(session, table_name, varchar_cols_post)
    if op:
        operations.append(op)

    # 8. Soft dedup
    op = _flag_duplicates(session, table_name, findings)
    if op:
        operations.append(op)

    # 9. High-null column removal
    op = _clean_high_null_columns(session, table_name, findings)
    if op:
        operations.append(op)

    # 10. Constant column removal
    op = _clean_constant_columns(session, table_name, findings)
    if op:
        operations.append(op)

    # 11. PII detection (informational — LLM-assisted)
    pii_detection = _detect_pii(session, table_name)

    # 12. Numeric precision validation (informational)
    numeric_precision_flags = _validate_numeric_precision(session, table_name)

    # Snapshot after-state
    after_rows = session.get_row_count(table_name)
    after_types = session.get_column_types(table_name)
    after_columns = len([c for c in after_types if c != "processed_at"])

    columns_added = max(0, after_columns - before_columns)
    columns_removed = max(0, before_columns - after_columns + columns_added)

    result = {
        "status": "success",
        "table_name": table_name,
        "before_rows": before_rows,
        "after_rows": after_rows,
        "before_columns": before_columns,
        "after_columns": after_columns,
        "columns_added": columns_added,
        "columns_removed": columns_removed,
        "operations": operations,
        "pii_detection": pii_detection,
        "identifier_columns": identifier_columns,
        "numeric_precision_flags": numeric_precision_flags,
    }

    # Build and persist cleaning report
    from datagrunt_agent.tools.cleaning_report import build_cleaning_report

    from datagrunt_agent.tools.ingestion import _get_output_dir
    output_dir = _get_output_dir()

    report = build_cleaning_report(
        cleaning_result=result,
        quality_findings=findings,
        source_file_path=source_file,
        output_dir=output_dir,
    )
    result["cleaning_report_path"] = report.get("_persisted_path", "")

    # Store in session state for downstream access
    tool_context.state["cleaning_result"] = result
    tool_context.state["cleaning_report"] = report

    return result


# ---------------------------------------------------------------------------
# Cleaning Operation Helpers
# ---------------------------------------------------------------------------


def _clean_unknown_chars(
    session, table_name: str, varchar_cols: list[str],
) -> dict | None:
    """Replace U+FFFD and common mojibake patterns in VARCHAR columns."""
    if not varchar_cols:
        return None

    columns_cleaned = []
    total_replacements = 0

    for col in varchar_cols:
        # Check for U+FFFD replacement character
        count_sql = (
            f'SELECT COUNT(*) FROM {table_name} '
            f'WHERE "{col}" LIKE \'%\ufffd%\''
        )
        count = session.execute(count_sql).fetchone()[0]

        if count > 0:
            sql = load_sql(
                "cleaning", "replace_unknown_chars",
                table_name=table_name, column_name=col,
            )
            session.execute(sql)
            total_replacements += count
            if col not in columns_cleaned:
                columns_cleaned.append(col)

        # Check for common mojibake patterns
        for bad, good in _MOJIBAKE_MAP.items():
            check_sql = (
                f'SELECT COUNT(*) FROM {table_name} '
                f"WHERE \"{col}\" LIKE '%{bad}%'"
            )
            try:
                mc = session.execute(check_sql).fetchone()[0]
            except Exception:
                continue
            if mc > 0:
                update_sql = (
                    f'UPDATE {table_name} '
                    f"SET \"{col}\" = REPLACE(\"{col}\", '{bad}', '{good}') "
                    f"WHERE \"{col}\" LIKE '%{bad}%'"
                )
                session.execute(update_sql)
                total_replacements += mc
                if col not in columns_cleaned:
                    columns_cleaned.append(col)

    if not columns_cleaned:
        return None

    return {
        "operation": "unknown_char_replacement",
        "columns_cleaned": columns_cleaned,
        "replacements": total_replacements,
    }


def _clean_whitespace(
    session, table_name: str, varchar_cols: list[str],
    findings: list[dict],
) -> dict | None:
    """Trim leading/trailing whitespace from VARCHAR columns with issues."""
    # Get columns flagged by quality scan
    flagged = {
        f["column"]
        for f in findings
        if f.get("category") == "whitespace"
    }

    # Also trim all VARCHAR columns (whitespace may exist beyond what was flagged)
    targets = list(set(varchar_cols) | flagged)
    if not targets:
        return None

    columns_cleaned = []
    total_affected = 0

    for col in targets:
        if col in _PROTECTED_COLUMNS:
            continue

        # Count rows with whitespace before cleaning
        count_sql = (
            f'SELECT COUNT(*) FROM {table_name} '
            f'WHERE "{col}" IS NOT NULL AND "{col}" != TRIM("{col}")'
        )
        count = session.execute(count_sql).fetchone()[0]

        if count > 0:
            sql = load_sql(
                "cleaning", "trim_whitespace",
                table_name=table_name, column_name=col,
            )
            session.execute(sql)
            columns_cleaned.append(col)
            total_affected += count

    if not columns_cleaned:
        return None

    return {
        "operation": "whitespace_trimming",
        "columns_cleaned": columns_cleaned,
        "rows_affected": total_affected,
    }


def _clean_empty_strings(
    session, table_name: str, varchar_cols: list[str],
) -> dict | None:
    """Convert empty/whitespace-only strings to NULL."""
    if not varchar_cols:
        return None

    columns_cleaned = []
    total_affected = 0

    for col in varchar_cols:
        if col in _PROTECTED_COLUMNS:
            continue
        # Count empties before cleaning
        count_sql = (
            f'SELECT COUNT(*) FROM {table_name} '
            f"WHERE TRIM(\"{col}\") = ''"
        )
        count = session.execute(count_sql).fetchone()[0]

        if count > 0:
            sql = load_sql(
                "cleaning", "normalize_empty_strings",
                table_name=table_name, column_name=col,
            )
            session.execute(sql)
            columns_cleaned.append(col)
            total_affected += count

    if not columns_cleaned:
        return None

    return {
        "operation": "empty_string_normalization",
        "columns_cleaned": columns_cleaned,
        "rows_affected": total_affected,
    }


def _clean_null_like_strings(
    session, table_name: str, findings: list[dict],
) -> dict | None:
    """Convert null-like sentinel strings to actual NULL."""
    flagged = [
        f for f in findings
        if f.get("category") == "null_like_strings"
    ]

    if not flagged:
        return None

    columns_cleaned = []
    total_affected = 0

    for finding in flagged:
        col = finding["column"]
        if col in _PROTECTED_COLUMNS:
            continue

        count_sql = (
            f'SELECT COUNT(*) FROM {table_name} '
            f'WHERE LOWER(TRIM("{col}"::VARCHAR)) IN ({_SENTINEL_LIST})'
        )
        count = session.execute(count_sql).fetchone()[0]

        if count > 0:
            sql = load_sql(
                "cleaning", "normalize_null_like",
                table_name=table_name,
                column_name=col,
                sentinel_list=_SENTINEL_LIST,
            )
            session.execute(sql)
            columns_cleaned.append(col)
            total_affected += count

    if not columns_cleaned:
        return None

    return {
        "operation": "null_like_normalization",
        "columns_cleaned": columns_cleaned,
        "rows_affected": total_affected,
    }


def _standardize_dates(
    session, table_name: str, findings: list[dict],
) -> dict | None:
    """Standardize DATE-castable VARCHAR columns to YYYY-MM-DD format."""
    date_cols = [
        f["column"]
        for f in findings
        if f.get("category") == "type_analysis"
        and f.get("date_castable_rate", 0) > 0.9
    ]

    if not date_cols:
        return None

    columns_standardized = []

    for col in date_cols:
        if col in _PROTECTED_COLUMNS:
            continue
        try:
            sql = load_sql(
                "cleaning", "standardize_date",
                table_name=table_name, column_name=col,
            )
            session.execute(sql)
            columns_standardized.append(col)
        except Exception:
            pass

    if not columns_standardized:
        return None

    return {
        "operation": "date_standardization",
        "columns_standardized": columns_standardized,
        "format": "YYYY-MM-DD",
    }


def _clean_type_coercion(
    session, table_name: str, findings: list[dict],
) -> tuple[dict | None, list[dict]]:
    """Coerce VARCHAR columns to tighter types, preserving identifiers.

    Returns:
        Tuple of (operation_result, identifier_columns).
    """
    type_findings = [
        f for f in findings
        if f.get("category") == "type_analysis"
        and (f.get("suggested_cast") or f.get("leading_zero_count", 0) > 0)
    ]

    if not type_findings:
        return None, []

    columns_coerced = {}
    coercion_failures = []
    identifier_columns = []

    for finding in type_findings:
        col = finding["column"]
        if col in _PROTECTED_COLUMNS:
            continue

        suggested = finding.get("suggested_cast")
        leading_zeros = finding.get("leading_zero_count", 0)

        # Skip identifiers with leading zeros
        if leading_zeros > 0:
            identifier_columns.append({
                "column": col,
                "pattern": "leading_zeros",
                "preserved_as": "VARCHAR",
            })
            continue

        # Skip if no suggested cast (only came in for identifier detection)
        if not suggested:
            continue

        # Skip date-castable columns (handled by _standardize_dates)
        if suggested == "DATE":
            continue

        try:
            sql = load_sql(
                "cleaning", "cast_column_type",
                table_name=table_name,
                column_name=col,
                new_type=suggested,
            )
            session.execute(sql)
            columns_coerced[col] = suggested
        except Exception as exc:
            coercion_failures.append({
                "column": col,
                "target_type": suggested,
                "error": str(exc),
            })

    if not columns_coerced and not coercion_failures:
        return None, identifier_columns

    result = {
        "operation": "type_coercion",
        "columns_coerced": columns_coerced,
    }
    if coercion_failures:
        result["coercion_failures"] = coercion_failures

    return result, identifier_columns


def _normalize_case(
    session, table_name: str, varchar_cols: list[str],
) -> dict | None:
    """Normalize low-cardinality VARCHAR columns to lowercase.

    Only targets columns with < 50 unique values (categoricals).
    """
    if not varchar_cols:
        return None

    columns_normalized = []

    for col in varchar_cols:
        if col in _PROTECTED_COLUMNS:
            continue

        # Check cardinality
        card_sql = f'SELECT COUNT(DISTINCT "{col}") FROM {table_name} WHERE "{col}" IS NOT NULL'
        cardinality = session.execute(card_sql).fetchone()[0]

        if cardinality >= 50:
            continue

        # Check if any values have mixed case (not already lowercase)
        mixed_sql = (
            f'SELECT COUNT(*) FROM {table_name} '
            f'WHERE "{col}" IS NOT NULL AND "{col}" != LOWER("{col}")'
        )
        mixed_count = session.execute(mixed_sql).fetchone()[0]

        if mixed_count > 0:
            sql = load_sql(
                "cleaning", "normalize_case",
                table_name=table_name, column_name=col,
            )
            session.execute(sql)
            columns_normalized.append(col)

    if not columns_normalized:
        return None

    return {
        "operation": "mixed_case_normalization",
        "columns_normalized": columns_normalized,
        "target_case": "lower",
    }


def _flag_duplicates(
    session, table_name: str, findings: list[dict],
) -> dict | None:
    """Add is_duplicate boolean column to flag duplicate rows.

    Flags all-but-first occurrence. Never deletes rows.
    """
    dup_findings = [
        f for f in findings
        if f.get("category") == "duplicates"
        and f.get("approximate_count", 0) > 0
    ]

    if not dup_findings:
        return None

    columns = session.get_column_names(table_name)
    check_columns = [
        c for c in columns
        if c not in _PROTECTED_COLUMNS
    ]

    if not check_columns:
        return None

    column_list = ", ".join(f'"{c}"' for c in check_columns)

    sql = load_sql(
        "cleaning", "flag_duplicates",
        table_name=table_name, column_list=column_list,
    )

    # Execute each statement separately (ADD COLUMN + UPDATE)
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            session.execute(stmt)

    # Count flagged duplicates
    count_sql = (
        f"SELECT COUNT(*) FROM {table_name} WHERE is_duplicate = true"
    )
    flagged_count = session.execute(count_sql).fetchone()[0]

    return {
        "operation": "soft_dedup",
        "duplicates_flagged": flagged_count,
        "column_added": "is_duplicate",
    }


def _clean_high_null_columns(
    session, table_name: str, findings: list[dict],
) -> dict | None:
    """Drop columns with >90% null rate."""
    high_null = [
        f for f in findings
        if f.get("category") == "null_analysis"
        and f.get("null_rate", 0) > 0.9
    ]

    if not high_null:
        return None

    columns_dropped = []

    for finding in high_null:
        col = finding["column"]
        if col in _PROTECTED_COLUMNS:
            continue

        sql = load_sql(
            "cleaning", "drop_column",
            table_name=table_name, column_name=col,
        )
        try:
            session.execute(sql)
            columns_dropped.append(col)
        except Exception:
            pass

    if not columns_dropped:
        return None

    return {
        "operation": "high_null_column_removal",
        "columns_dropped": columns_dropped,
    }


def _clean_constant_columns(
    session, table_name: str, findings: list[dict],
) -> dict | None:
    """Drop columns with cardinality of 1 (single unique value)."""
    constant_findings = [
        f for f in findings
        if f.get("category") == "constant_columns"
    ]

    if not constant_findings:
        return None

    columns_dropped = []

    for finding in constant_findings:
        cols = finding.get("columns", [])
        for col in cols:
            if col in _PROTECTED_COLUMNS:
                continue

            sql = load_sql(
                "cleaning", "drop_column",
                table_name=table_name, column_name=col,
            )
            try:
                session.execute(sql)
                columns_dropped.append(col)
            except Exception:
                pass

    if not columns_dropped:
        return None

    return {
        "operation": "constant_column_removal",
        "columns_dropped": columns_dropped,
    }


def _detect_pii(session, table_name: str) -> list[dict]:
    """Detect PII in columns using LLM-assisted analysis.

    Samples first 5 non-null distinct values per column + column name,
    sends a single Gemini call for all columns.

    Returns list of per-column PII flags.
    """
    columns = session.get_column_names(table_name)
    check_columns = [c for c in columns if c not in _PROTECTED_COLUMNS]

    if not check_columns:
        return []

    # Gather samples
    column_samples = {}
    for col in check_columns:
        sample_sql = (
            f'SELECT DISTINCT "{col}" FROM {table_name} '
            f'WHERE "{col}" IS NOT NULL LIMIT 5'
        )
        try:
            rows = session.execute(sample_sql).fetchall()
            values = [str(r[0]) for r in rows if r[0] is not None]
            column_samples[col] = values
        except Exception:
            column_samples[col] = []

    # Build prompt for LLM
    sample_text = ""
    for col, values in column_samples.items():
        sample_text += f"Column: {col}\nSample values: {values}\n\n"

    prompt = (
        "Analyze the following database columns and their sample values. "
        "For each column, determine if it contains Personally Identifiable "
        "Information (PII). PII includes: email addresses, phone numbers, "
        "social security numbers, names, physical addresses, IP addresses, "
        "credit card numbers, dates of birth, and similar sensitive data.\n\n"
        f"{sample_text}"
        "Respond with a JSON array. Each element should have:\n"
        '- "column": the column name\n'
        '- "is_pii": true or false\n'
        '- "pii_type": the type of PII (e.g., "email", "phone", "name", '
        '"address", "ssn", "none")\n'
        '- "confidence": a float between 0.0 and 1.0\n\n'
        "Only include columns where is_pii is true. "
        "Return an empty array [] if no PII is detected.\n"
        "Respond with ONLY the JSON array, no other text."
    )

    try:
        import importlib
        genai = importlib.import_module("google.genai")
        types = importlib.import_module("google.genai.types")

        client = genai.Client(vertexai=True)
        response = client.models.generate_content(
            model=os.getenv("PII_DETECTION_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0),
        )

        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3].strip()

        pii_results = json.loads(text)

        return [
            {
                "column": item["column"],
                "pii_type": item.get("pii_type", "unknown"),
                "confidence": item.get("confidence", 0.5),
            }
            for item in pii_results
            if item.get("is_pii")
        ]
    except Exception:
        return []


def _validate_numeric_precision(session, table_name: str) -> list[dict]:
    """Flag numeric columns with inconsistent decimal precision.

    Informational only — does not modify data.
    """
    column_types = session.get_column_types(table_name)
    numeric_cols = [
        c for c in column_types
        if column_types[c] in ("DOUBLE", "FLOAT", "DECIMAL")
        and c not in _PROTECTED_COLUMNS
    ]

    if not numeric_cols:
        return []

    flags = []

    for col in numeric_cols:
        # Count distinct decimal places
        precision_sql = (
            f'SELECT '
            f'MIN(LENGTH(SPLIT_PART(CAST("{col}" AS VARCHAR), \'.\', 2))) AS min_dec, '
            f'MAX(LENGTH(SPLIT_PART(CAST("{col}" AS VARCHAR), \'.\', 2))) AS max_dec '
            f'FROM {table_name} '
            f'WHERE "{col}" IS NOT NULL '
            f"AND CAST(\"{col}\" AS VARCHAR) LIKE '%.%'"
        )
        try:
            row = session.execute(precision_sql).fetchone()
            if row and row[0] is not None and row[1] is not None:
                min_dec = row[0]
                max_dec = row[1]
                if min_dec != max_dec:
                    flags.append({
                        "column": col,
                        "min_decimals": min_dec,
                        "max_decimals": max_dec,
                        "recommendation": (
                            f"Inconsistent decimal precision ({min_dec}-{max_dec} places). "
                            "Consider standardizing for currency or measurement data."
                        ),
                    })
        except Exception:
            pass

    return flags
