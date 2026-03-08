"""Universal file ingestion tools.

Loads CSV, TSV, JSON, JSONL, Parquet, and Excel files into DuckDB.
Follows a fast-path-first strategy: standard DuckDB auto-detect loads
are attempted first. If the standard load fails, a recovery path
engages encoding detection, multi-strategy parsing, and JSON repair.

Every successful load stamps records with processed_at and auto-exports
to Parquet as the canonical pipeline output format. Quality scanning
is NOT run inline — the agent delegates that to the Quality Analyst
after the load returns.
"""

import csv
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.adk.tools import ToolContext

from datagrunt_agent.core.column_normalizer import normalize_column_name
from datagrunt_agent.core.delimiter_detector import (
    count_source_lines,
    detect_delimiter,
    read_raw_lines,
)
from datagrunt_agent.core.duckdb_session import (
    DuckDBSession,
    TableMetadata,
    validate_path,
)
from datagrunt_agent.core.file_detector import (
    FileFormat,
    detect_format as detect_file_format,
    ensure_utf8,
    is_blank_file,
    is_empty_file,
)
from datagrunt_agent.core.sql_loader import load_sql


# ---------------------------------------------------------------------------
# Output directory for Parquet files
# ---------------------------------------------------------------------------

_DEFAULT_OUTPUT_DIR = "/tmp/datagrunt"


def _get_output_dir(output_dir: str = "") -> str:
    """Resolve the output directory for Parquet files.

    Priority: output_dir param > DATAGRUNT_OUTPUT_DIR env > /tmp/datagrunt
    """
    resolved = output_dir or os.getenv("DATAGRUNT_OUTPUT_DIR", _DEFAULT_OUTPUT_DIR)
    os.makedirs(resolved, exist_ok=True)
    return resolved


# ---------------------------------------------------------------------------
# Header Detection
# ---------------------------------------------------------------------------

def _detect_header(file_path: str, delimiter: str) -> bool:
    """Detect whether a CSV file has column headers using an LLM.

    Sends only the first 3 rows (sample data) to Gemini for classification.
    The LLM never sees bulk data — just enough rows to determine whether
    the first row contains field names or data values.

    Falls back to True (assume headers) on any error.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh, delimiter=delimiter)
            rows = []
            for i, row in enumerate(reader):
                if i >= 3:
                    break
                rows.append(row)
    except Exception:
        return True

    if not rows:
        return True

    sample = "\n".join(delimiter.join(values) for values in rows)

    prompt = (
        "Look at the following CSV rows:\n\n"
        f"{sample}\n\n"
        "Does the FIRST row contain column headers (field names), "
        "or is it data like the other rows?\n\n"
        "Reply with exactly one word: HEADERS or DATA"
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=True)
        response = client.models.generate_content(
            model=os.getenv("HEADER_DETECTION_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0),
        )
        answer = response.text.strip().upper()
        return "HEADER" in answer
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Post-Load Helpers (processed_at, Parquet export)
# ---------------------------------------------------------------------------

def _stamp_processed_at(session: DuckDBSession, table_name: str) -> str:
    """Add processed_at timestamp to all rows in the table.

    DuckDB owns the timestamp via current_timestamp. Python reads it back
    so there is a single source of truth.

    Returns the ISO-formatted timestamp that was applied.
    """
    sql = load_sql("ingestion", "add_processed_at", table_name=table_name)
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            session.execute(stmt)
    sql = load_sql("ingestion", "get_processed_at", table_name=table_name)
    row = session.execute(sql).fetchone()
    if row and row[0]:
        ts = row[0].replace(tzinfo=timezone.utc)
        return ts.isoformat()
    return datetime.now(timezone.utc).isoformat()


def _export_parquet(
    session: DuckDBSession,
    table_name: str,
    source_path: str,
    output_dir: str = "",
) -> dict[str, Any]:
    """Export table to Parquet and return output metadata.

    Returns dict with parquet_path and size_bytes.
    """
    resolved_dir = _get_output_dir(output_dir)
    stem = Path(source_path).stem
    parquet_path = os.path.join(resolved_dir, f"{stem}.parquet")

    sql = load_sql(
        "export", "to_parquet",
        table_name=table_name,
        output_path=parquet_path,
    )
    session.execute(sql)

    size_bytes = os.path.getsize(parquet_path)
    return {"parquet_path": parquet_path, "size_bytes": size_bytes}




# ---------------------------------------------------------------------------
# Module-level session (shared across tool calls within an agent session)
# ---------------------------------------------------------------------------

_session: DuckDBSession | None = None


def _get_session() -> DuckDBSession:
    """Get or create the module-level DuckDB session."""
    global _session
    if _session is None:
        _session = DuckDBSession()
    return _session


# ---------------------------------------------------------------------------
# CSV Helpers — Multi-Strategy Parsing (from datagrunt-ai)
# ---------------------------------------------------------------------------

def _try_load_csv(
    session: DuckDBSession,
    file_path: str,
    table_name: str,
    delimiter: str,
    quote_char: str = '"',
    escape_char: str = '"',
    has_header: bool = True,
) -> bool:
    """Try loading a CSV with specific quote/escape params. Returns True on success."""
    try:
        if quote_char:
            template = "load_csv" if has_header else "load_csv_no_header"
            sql = load_sql(
                "ingestion", template,
                table_name=table_name,
                file_path=file_path,
                delimiter=delimiter,
                quote_char=quote_char,
                escape_char=escape_char,
            )
        else:
            template = "load_csv_lenient" if has_header else "load_csv_lenient_no_header"
            sql = load_sql(
                "ingestion", template,
                table_name=table_name,
                file_path=file_path,
                delimiter=delimiter,
            )
        session.execute(sql)
        return True
    except Exception:
        return False


def _check_overflow_columns(session: DuckDBSession, table_name: str) -> list[str]:
    """Detect overflow columns (>80% NULL trailing columns).

    Column overflow occurs when unquoted delimiters in field values cause
    data to spill into extra columns. These phantom columns appear at the
    end of the table and are mostly NULL.
    """
    columns = session.get_column_names(table_name)
    total_rows = session.get_row_count(table_name)
    if total_rows == 0:
        return []

    sparse_threshold = total_rows * 0.8
    overflow_cols = []

    for col in reversed(columns):
        sql = load_sql("common", "null_count", table_name=table_name, column_name=col)
        null_count = session.execute(sql).fetchone()[0]
        if null_count >= sparse_threshold:
            overflow_cols.insert(0, col)
        else:
            break

    return overflow_cols


def _repair_overflow_columns(
    session: DuckDBSession, table_name: str, overflow_cols: list[str]
) -> dict[str, Any]:
    """Repair overflow columns by dropping them and flagging affected rows.

    Overflow columns are structural artifacts from broken quoting. Rather than
    silently dropping data, this rebuilds the table with only the real columns
    and adds an ``is_shifted`` boolean that marks rows where data spilled into
    overflow columns. Downstream pipelines can filter or inspect flagged rows.

    Returns metadata about the repair: columns removed and rows flagged.
    """
    columns = session.get_column_names(table_name)
    first_overflow_idx = columns.index(overflow_cols[0])
    real_columns = columns[:first_overflow_idx]

    real_cols_select = ", ".join([f'"{col}"' for col in real_columns])
    overflow_check_expr = " OR ".join(
        [
            f'("{col}" IS NOT NULL AND TRIM(CAST("{col}" AS VARCHAR)) != \'\')'
            for col in overflow_cols
        ]
    )

    # Count affected rows before rebuild
    count_sql = (
        f"SELECT COUNT(*) FROM {table_name} WHERE {overflow_check_expr}"
    )
    rows_flagged = session.execute(count_sql).fetchone()[0]

    # Rebuild table: real columns + is_shifted flag
    repair_sql = load_sql(
        "ingestion", "repair_overflow",
        table_name=table_name,
        real_columns=real_cols_select,
        overflow_check_expr=overflow_check_expr,
    )
    session.execute(repair_sql)

    # Swap repaired table into place
    session.execute(f"DROP TABLE IF EXISTS {table_name}")
    session.execute(
        f"ALTER TABLE {table_name}_repaired RENAME TO {table_name}"
    )

    return {
        "overflow_columns_repaired": overflow_cols,
        "overflow_rows_flagged": rows_flagged,
    }


def _normalize_column_names_in_table(session: DuckDBSession, table_name: str) -> dict[str, str]:
    """Normalize all column names in a DuckDB table to lowercase snake_case.

    Returns the mapping of old->new names for columns that were renamed.
    """
    columns = session.get_column_names(table_name)
    renames = {}

    for col in columns:
        new_name = normalize_column_name(col)
        if new_name != col:
            renames[col] = new_name

    # Check for conflicts before renaming
    seen: dict[str, int] = {}
    deduped = {}
    for col in columns:
        target = renames.get(col, col)
        if target in seen:
            seen[target] += 1
            deduped[col] = f"{target}_{seen[target]}"
        else:
            seen[target] = 0
            if col in renames:
                deduped[col] = target

    renames = deduped

    for old_name, new_name in renames.items():
        try:
            sql = load_sql(
                "ingestion", "rename_column",
                table_name=table_name, old_name=old_name, new_name=new_name,
            )
            session.execute(sql)
        except Exception:
            pass

    return renames


def _remove_empty_rows(session: DuckDBSession, table_name: str) -> int:
    """Remove rows where every column is NULL. Returns count of removed rows."""
    columns = session.get_column_names(table_name)
    null_conditions = " AND ".join([f'"{col}" IS NULL' for col in columns])

    sql = load_sql(
        "ingestion", "count_empty_rows",
        table_name=table_name, null_conditions=null_conditions,
    )
    empty_count = session.execute(sql).fetchone()[0]

    if empty_count > 0:
        sql = load_sql(
            "ingestion", "delete_empty_rows",
            table_name=table_name, null_conditions=null_conditions,
        )
        session.execute(sql)

    return empty_count


def _coerce_types(session: DuckDBSession, table_name: str) -> dict[str, str]:
    """Safely cast VARCHAR columns to tighter types where no data is lost.

    Loads all VARCHAR data, checks each column for safe castability
    (integer, float, boolean), and skips any column with leading zeros
    to protect zip codes, phone numbers, etc.

    Returns:
        Dict mapping column name → new type for columns that were cast.
    """
    columns = session.get_column_types(table_name)
    varchar_cols = [name for name, ctype in columns.items() if ctype == "VARCHAR"]

    if not varchar_cols:
        return {}

    # Build UNPIVOT query to analyze all VARCHAR columns in one pass
    col_list = ", ".join([f'"{c}"' for c in varchar_cols])
    unpivot_query = (
        f"SELECT column_name, value FROM ("
        f"SELECT {col_list} FROM {table_name}"
        f") UNPIVOT (value FOR column_name IN ({col_list}))"
    )

    analysis_sql = load_sql("ingestion", "safe_type_coercion", unpivot_query=unpivot_query)
    recommendations = session.execute(analysis_sql).pl().to_dicts()

    coerced = {}
    for rec in recommendations:
        col = rec["column_name"]
        new_type = rec["recommended_type"]
        try:
            sql = load_sql(
                "ingestion", "alter_column_type",
                table_name=table_name, column_name=col, new_type=new_type,
            )
            session.execute(sql)
            coerced[col] = new_type
        except Exception:
            # Cast failed for some edge case — leave as VARCHAR
            pass

    return coerced


def _load_csv_standard(
    session: DuckDBSession,
    file_path: str,
    table_name: str,
    delimiter: str,
) -> dict[str, Any]:
    """Standard CSV load — DuckDB auto-detect with double-quote config.

    Fast path: no LLM header detection, no multi-strategy parsing,
    no type coercion. Just load the file and normalize column names.
    Raises on failure so load_file can fall through to recovery.
    """
    sql = load_sql(
        "ingestion", "load_csv",
        table_name=table_name,
        file_path=file_path,
        delimiter=delimiter,
        quote_char='"',
        escape_char='"',
    )
    session.execute(sql)

    renames = _normalize_column_names_in_table(session, table_name)
    empty_rows_removed = _remove_empty_rows(session, table_name)

    # Overflow check — repair by flagging affected rows with is_shifted
    overflow = _check_overflow_columns(session, table_name)
    overflow_repair: dict[str, Any] = {}
    if overflow:
        overflow_repair = _repair_overflow_columns(session, table_name, overflow)

    # Gather results (after any overflow repair)
    total_rows = session.get_row_count(table_name)
    columns = session.get_column_types(table_name)
    sample = session.execute(
        load_sql("common", "sample_rows", table_name=table_name, limit="5"),
    ).pl()

    result: dict[str, Any] = {
        "status": "success",
        "table_name": table_name,
        "total_rows": total_rows,
        "column_count": len(columns),
        "columns": [
            {"name": name, "type": col_type} for name, col_type in columns.items()
        ],
        "sample": session.to_markdown(sample),
        "parse_strategy": "standard",
    }

    if renames:
        result["columns_renamed"] = renames
    if empty_rows_removed > 0:
        result["empty_rows_removed"] = empty_rows_removed
    if overflow_repair:
        result.update(overflow_repair)

    return result


def _load_csv_robust(
    session: DuckDBSession,
    file_path: str,
    table_name: str,
    delimiter: str,
) -> dict[str, Any]:
    """Load CSV with multi-strategy parsing to handle bad quoting/overflow.

    Detects whether column headers are present. Tries multiple quote/escape
    configurations and picks the one that produces the fewest overflow columns.
    Then normalizes column names and removes fully empty rows.
    """
    source_line_count = count_source_lines(file_path)
    has_header = _detect_header(file_path, delimiter)

    parse_configs = [
        {"quote": '"', "escape": '"', "name": "double-quote"},
        {"quote": '"', "escape": "\\", "name": "backslash-escape"},
        {"quote": "'", "escape": "'", "name": "single-quote"},
        {"quote": "", "escape": "", "name": "auto-detect"},
    ]

    best_config = None
    best_overflow_count = float("inf")

    for config in parse_configs:
        if not _try_load_csv(
            session, file_path, table_name, delimiter,
            config["quote"], config["escape"], has_header,
        ):
            continue

        overflow_cols = _check_overflow_columns(session, table_name)

        if len(overflow_cols) < best_overflow_count:
            best_overflow_count = len(overflow_cols)
            best_config = config

            if len(overflow_cols) == 0:
                break

    # Reload best config if it wasn't the last one tested
    if best_config and best_config != parse_configs[-1]:
        _try_load_csv(
            session, file_path, table_name, delimiter,
            best_config["quote"], best_config["escape"], has_header,
        )

    # Normalize column names
    renames = _normalize_column_names_in_table(session, table_name)

    # Remove completely empty rows
    empty_rows_removed = _remove_empty_rows(session, table_name)

    # Safe type coercion: cast VARCHAR → BIGINT/DOUBLE/BOOLEAN where lossless
    coerced_types = _coerce_types(session, table_name)

    # Final overflow check — repair by dropping overflow columns and flagging
    # affected rows with is_shifted so no data is silently lost.
    final_overflow = _check_overflow_columns(session, table_name)
    overflow_repair: dict[str, Any] = {}
    if final_overflow:
        overflow_repair = _repair_overflow_columns(
            session, table_name, final_overflow,
        )

    # Gather results (after any overflow repair)
    total_rows = session.get_row_count(table_name)
    columns = session.get_column_types(table_name)
    sql = load_sql("common", "sample_rows", table_name=table_name, limit="5")
    sample = session.execute(sql).pl()
    rows_lost = source_line_count - total_rows - empty_rows_removed

    # ATOMIC: If rows were lost during parsing, fail the entire load.
    # Partial data is untrustworthy — all or nothing.
    if rows_lost > 0:
        return {
            "error": (
                f"ATOMIC LOAD FAILED: {rows_lost} of {source_line_count} rows were "
                f"lost during parsing ({total_rows} loaded, {empty_rows_removed} empty "
                "rows removed). Partial loads are not allowed."
            ),
            "source_rows": source_line_count,
            "loaded_rows": total_rows,
            "empty_rows_removed": empty_rows_removed,
            "rows_lost": rows_lost,
            "parse_strategy": best_config["name"] if best_config else "unknown",
            "suggestion": (
                "Use inspect_raw_file to diagnose the issue. Common causes: "
                "wrong delimiter, encoding issues, or malformed rows."
            ),
        }

    result: dict[str, Any] = {
        "status": "success",
        "table_name": table_name,
        "total_rows": total_rows,
        "source_rows": source_line_count,
        "column_count": len(columns),
        "columns": [
            {"name": name, "type": col_type} for name, col_type in columns.items()
        ],
        "sample": session.to_markdown(sample),
        "header_detected": has_header,
    }

    if not has_header:
        result["note"] = (
            "No column headers detected. Columns assigned as column0, column1, etc."
        )

    if best_config:
        result["parse_strategy"] = best_config["name"]

    if renames:
        result["columns_renamed"] = renames

    if overflow_repair:
        result.update(overflow_repair)

    if empty_rows_removed > 0:
        result["empty_rows_removed"] = empty_rows_removed

    if coerced_types:
        result["types_coerced"] = coerced_types

    return result


# ---------------------------------------------------------------------------
# JSON Helpers — Validation and Repair
# ---------------------------------------------------------------------------

def _detect_json_format(file_path: str) -> str:
    """Detect whether a file is JSON array or JSON Lines (JSONL).

    Returns:
        'array' for JSON arrays, 'newline_delimited' for JSONL.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("["):
                return "array"
            if line.startswith("{"):
                return "newline_delimited"
            break
    return "auto"


def _validate_json(file_path: str, json_format: str) -> dict[str, Any]:
    """Validate a JSON/JSONL file and return error details if invalid.

    Returns:
        Dict with 'valid' bool, and 'errors' list if invalid.
    """
    errors = []

    if json_format == "array":
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                json.load(fh)
            return {"valid": True, "errors": []}
        except json.JSONDecodeError as exc:
            errors.append({
                "line": exc.lineno,
                "column": exc.colno,
                "message": exc.msg,
            })
    else:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            for line_num, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append({
                        "line": line_num,
                        "column": exc.colno,
                        "message": exc.msg,
                    })
                    if len(errors) >= 20:
                        break

    return {"valid": len(errors) == 0, "errors": errors}


def _repair_json(file_path: str, json_format: str) -> dict[str, Any]:
    """Attempt to repair invalid JSON/JSONL and write to a temp file.

    This is an ATOMIC operation — all records must be repaired or the entire
    repair fails. We never skip records because partial data is untrustworthy.

    Repair strategies:
    - Strip BOM and control characters
    - Fix trailing commas before ] or }
    - Fix single-quoted strings (replace with double quotes)

    Returns:
        Dict with 'repaired_path' and 'lines_repaired' on success,
        or 'repair_failed' with 'unrecoverable_errors' on failure.
    """
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as fh:
        raw_content = fh.read()

    if json_format == "array":
        repaired_content = _repair_json_string(raw_content)
        try:
            json.loads(repaired_content)
        except json.JSONDecodeError as exc:
            return {
                "repair_failed": True,
                "unrecoverable_errors": [{
                    "line": exc.lineno,
                    "column": exc.colno,
                    "message": exc.msg,
                }],
                "message": (
                    "JSON repair failed. The file has structural issues that "
                    "could not be automatically fixed. Manual intervention required."
                ),
            }

        suffix = ".json"
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        )
        tmp.write(repaired_content)
        tmp.close()
        return {"repaired_path": tmp.name, "lines_repaired": 1}

    # JSONL — atomic: every line must parse or the whole thing fails
    repaired_lines = []
    lines_repaired = 0
    unrecoverable = []

    for line_num, line in enumerate(raw_content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            repaired_lines.append(line)
        except json.JSONDecodeError:
            repaired = _repair_json_string(line)
            try:
                json.loads(repaired)
                repaired_lines.append(repaired)
                lines_repaired += 1
            except json.JSONDecodeError as exc:
                unrecoverable.append({
                    "line": line_num,
                    "column": exc.colno,
                    "message": exc.msg,
                    "content_preview": line[:100],
                })

    if unrecoverable:
        return {
            "repair_failed": True,
            "unrecoverable_errors": unrecoverable,
            "total_lines": len(repaired_lines) + len(unrecoverable),
            "lines_failed": len(unrecoverable),
            "message": (
                f"{len(unrecoverable)} line(s) could not be repaired. "
                "All records must be valid — no partial loads allowed. "
                "Fix the source file manually at the reported line numbers."
            ),
        }

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    for line in repaired_lines:
        tmp.write(line + "\n")
    tmp.close()

    return {"repaired_path": tmp.name, "lines_repaired": lines_repaired}


def _repair_json_string(s: str) -> str:
    """Apply common JSON repair heuristics to a string."""
    # Strip BOM
    s = s.lstrip("\ufeff")

    # Remove control characters (except \n, \r, \t)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)

    # Fix trailing commas: ,] -> ] and ,} -> }
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # Fix single-quoted strings to double-quoted.
    # Handles mixed files with both single and double-quoted strings.
    # Replaces single-quoted JSON tokens: 'key' or 'value'
    if "'" in s:
        s = re.sub(
            r"(?<=[:,\[\{])\s*'([^']*)'",
            r'"\1"',
            s,
        )
        # Handle single-quoted keys right after { with optional whitespace
        s = re.sub(r"(\{)\s*'([^']*)'", r'\1"\2"', s)

    return s


def _load_json_standard(
    session: DuckDBSession,
    file_path: str,
    table_name: str,
) -> dict[str, Any]:
    """Standard JSON load — DuckDB auto-detect, no validation/repair.

    Fast path: lets DuckDB handle the file directly with auto-detect.
    Raises on failure so load_file can fall through to recovery.
    """
    json_format = _detect_json_format(file_path)
    duckdb_format = json_format if json_format != "auto" else "auto"

    sql = load_sql(
        "ingestion", "load_json",
        table_name=table_name,
        file_path=file_path,
        json_format=duckdb_format,
    )
    session.execute(sql)

    renames = _normalize_column_names_in_table(session, table_name)

    total_rows = session.get_row_count(table_name)
    columns = session.get_column_types(table_name)
    sample = session.execute(
        load_sql("common", "sample_rows", table_name=table_name, limit="5"),
    ).pl()

    result: dict[str, Any] = {
        "status": "success",
        "table_name": table_name,
        "total_rows": total_rows,
        "column_count": len(columns),
        "detected_format": json_format,
        "columns": [
            {"name": name, "type": col_type} for name, col_type in columns.items()
        ],
        "sample": session.to_markdown(sample),
    }

    if renames:
        result["columns_renamed"] = renames

    return result


def _load_json_robust(
    session: DuckDBSession,
    file_path: str,
    table_name: str,
) -> dict[str, Any]:
    """Load JSON/JSONL with validation and auto-repair on failure."""
    json_format = _detect_json_format(file_path)
    duckdb_format = json_format if json_format != "auto" else "auto"

    validation = _validate_json(file_path, json_format)
    load_path = file_path
    repair_info = None

    if not validation["valid"]:
        repair_result = _repair_json(file_path, json_format)

        # ATOMIC: If repair failed, do not proceed with partial data
        if repair_result.get("repair_failed"):
            return {
                "error": "ATOMIC LOAD FAILED: JSON file has unrecoverable errors.",
                "original_errors": validation["errors"][:5],
                "unrecoverable_errors": repair_result["unrecoverable_errors"],
                "message": repair_result["message"],
                "suggestion": (
                    "Fix the source file at the reported line numbers. "
                    "All records must be valid — no partial loads allowed."
                ),
            }

        repair_info = {
            "original_errors": validation["errors"][:5],
            "lines_repaired": repair_result["lines_repaired"],
        }
        load_path = repair_result["repaired_path"]

    # Load into DuckDB
    sql = load_sql(
        "ingestion", "load_json",
        table_name=table_name,
        file_path=load_path,
        json_format=duckdb_format,
    )
    session.execute(sql)

    # Normalize column names
    renames = _normalize_column_names_in_table(session, table_name)

    total_rows = session.get_row_count(table_name)
    columns = session.get_column_types(table_name)
    sample = session.execute(load_sql("common", "sample_rows", table_name=table_name, limit="5")).pl()

    # Cleanup temp file if we repaired
    if load_path != file_path:
        try:
            os.unlink(load_path)
        except OSError:
            pass

    result: dict[str, Any] = {
        "status": "success",
        "table_name": table_name,
        "total_rows": total_rows,
        "column_count": len(columns),
        "detected_format": json_format,
        "columns": [
            {"name": name, "type": col_type} for name, col_type in columns.items()
        ],
        "sample": session.to_markdown(sample),
    }

    if renames:
        result["columns_renamed"] = renames

    if repair_info:
        result["json_repair"] = repair_info

    return result


# ---------------------------------------------------------------------------
# Public Tool Functions
# ---------------------------------------------------------------------------

def load_file(
    file_path: str,
    tool_context: ToolContext,
    output_dir: str = "",
) -> dict[str, Any]:
    """Load a file into DuckDB, stamp with processed_at, and export to Parquet.

    Supports CSV, TSV, JSON, JSONL, Parquet, and Excel files.

    Uses a fast-path-first strategy:
    1. Try standard DuckDB auto-detect load (no encoding detection, no
       LLM header check, no multi-strategy parsing).
    2. If standard load fails, fall back to recovery: encoding detection,
       multi-strategy CSV parsing, JSON validation/repair.

    Post-load pipeline (all formats):
    1. Stamp every row with processed_at (UTC timestamp)
    2. Export to Parquet as canonical pipeline output

    Quality scanning is NOT run inline. The agent delegates quality
    analysis to the Quality Analyst after the load returns.

    Args:
        file_path: Absolute path to the file to load.
        output_dir: Optional output directory for Parquet file.
            Defaults to DATAGRUNT_OUTPUT_DIR env var or /tmp/datagrunt.

    Returns:
        Dict with table_name, row/column counts, schema, sample data,
        processed_at timestamp, and Parquet output path.
    """
    try:
        file_path = validate_path(file_path)
    except ValueError as exc:
        return {"error": str(exc)}

    if is_empty_file(file_path):
        return {"error": f"File is empty (0 bytes): {file_path}"}

    if is_blank_file(file_path):
        return {"error": f"File contains only whitespace: {file_path}"}

    session = _get_session()
    fmt = detect_file_format(file_path)
    table_name = session.generate_table_name(file_path)

    # --- Phase 1: Standard load (fast path) ---
    result = None
    delimiter = None

    try:
        if fmt in (FileFormat.CSV, FileFormat.TSV):
            delimiter = detect_delimiter(file_path)
            result = _load_csv_standard(session, file_path, table_name, delimiter)

        elif fmt in (FileFormat.JSON, FileFormat.JSONL):
            result = _load_json_standard(session, file_path, table_name)

        elif fmt == FileFormat.PARQUET:
            sql = load_sql(
                "ingestion", "load_parquet",
                table_name=table_name,
                file_path=file_path,
            )
            session.execute(sql)
            _normalize_column_names_in_table(session, table_name)

            total_rows = session.get_row_count(table_name)
            columns = session.get_column_types(table_name)
            sample = session.execute(
                load_sql("common", "sample_rows", table_name=table_name, limit="5"),
            ).pl()

            result = {
                "status": "success",
                "table_name": table_name,
                "total_rows": total_rows,
                "column_count": len(columns),
                "columns": [
                    {"name": name, "type": col_type}
                    for name, col_type in columns.items()
                ],
                "sample": session.to_markdown(sample),
            }

        elif fmt == FileFormat.EXCEL:
            sql = load_sql(
                "ingestion", "load_excel",
                table_name=table_name,
                file_path=file_path,
            )
            session.execute(sql)
            _normalize_column_names_in_table(session, table_name)

            total_rows = session.get_row_count(table_name)
            columns = session.get_column_types(table_name)
            sample = session.execute(
                load_sql("common", "sample_rows", table_name=table_name, limit="5"),
            ).pl()

            result = {
                "status": "success",
                "table_name": table_name,
                "total_rows": total_rows,
                "column_count": len(columns),
                "columns": [
                    {"name": name, "type": col_type}
                    for name, col_type in columns.items()
                ],
                "sample": session.to_markdown(sample),
            }

        else:
            return {
                "error": f"Unsupported file format: {fmt.value}",
                "file_path": file_path,
                "detected_format": fmt.value,
            }

    except Exception:
        result = None  # Fall through to recovery

    # --- Phase 2: Recovery (only if Phase 1 failed) ---
    if result is None:
        load_path = file_path
        detected_encoding = None
        is_lossy_transcode = False

        try:
            load_path, detected_encoding, is_lossy_transcode = ensure_utf8(
                file_path, fmt,
            )
        except Exception:
            pass

        try:
            if fmt in (FileFormat.CSV, FileFormat.TSV):
                delimiter = detect_delimiter(load_path)
                result = _load_csv_robust(session, load_path, table_name, delimiter)

            elif fmt in (FileFormat.JSON, FileFormat.JSONL):
                result = _load_json_robust(session, load_path, table_name)

            else:
                result = {
                    "error": f"Recovery not available for format: {fmt.value}",
                    "file_path": file_path,
                    "detected_format": fmt.value,
                }
        except Exception as exc:
            result = {
                "error": f"Failed to load file: {exc}",
                "file_path": file_path,
                "detected_format": fmt.value,
                "suggestion": "Try inspect_raw_file to diagnose the issue.",
            }
        finally:
            if load_path != file_path:
                try:
                    os.unlink(load_path)
                except OSError:
                    pass

        if result and "error" not in result:
            if detected_encoding:
                result["detected_encoding"] = detected_encoding
            if is_lossy_transcode:
                result["is_lossy_transcode"] = True
            result["recovery_used"] = True

    # Propagate errors
    if result is None:
        return {"error": "Unknown load failure", "file_path": file_path}

    if "error" in result:
        return result

    # Attach delimiter for CSV/TSV
    if fmt in (FileFormat.CSV, FileFormat.TSV) and delimiter:
        result["delimiter"] = delimiter

    # --- Post-load pipeline (fast) ---
    # Store state for other tools
    tool_context.state["current_file"] = file_path
    tool_context.state["current_table"] = table_name
    tool_context.state["file_format"] = fmt.value

    loaded_tables = tool_context.state.get("loaded_tables", {})

    # 1. Stamp processed_at (required — fail fast if this breaks)
    try:
        processed_at = _stamp_processed_at(session, table_name)
        result["processed_at"] = processed_at
    except Exception as exc:
        return {
            "error": f"Post-load pipeline failed: could not stamp processed_at: {exc}",
            "table_name": table_name,
            "file_path": file_path,
        }

    # 2. Export to Parquet (required — the canonical pipeline output)
    try:
        parquet_output = _export_parquet(session, table_name, file_path, output_dir)
        result["output"] = parquet_output
    except Exception as exc:
        return {
            "error": f"Post-load pipeline failed: Parquet export failed: {exc}",
            "table_name": table_name,
            "file_path": file_path,
        }

    # Quality scanning is NOT run inline.
    # The agent delegates to the Quality Analyst after load returns.

    # Register in table registry and session state
    metadata = TableMetadata(
        table_name=table_name,
        source_path=file_path,
        source_format=fmt.value,
        row_count=result["total_rows"],
        column_count=result["column_count"],
        source_row_count=result.get("source_rows", result["total_rows"]),
    )
    session.register_table(metadata)
    loaded_tables[table_name] = {
        "source_path": file_path,
        "format": fmt.value,
        "rows": result["total_rows"],
        "columns": result["column_count"],
    }
    tool_context.state["loaded_tables"] = loaded_tables

    return result


def detect_format(file_path: str) -> dict[str, Any]:
    """Detect the format of a file without loading it.

    Returns the detected format, file size, and whether DuckDB can load it
    directly.

    Args:
        file_path: Absolute path to the file.
    """
    try:
        file_path = validate_path(file_path)
    except ValueError as exc:
        return {"error": str(exc)}

    from datagrunt_agent.core.file_detector import (
        get_file_size_mb,
        is_duckdb_native,
    )

    fmt = detect_file_format(file_path)
    size_mb = get_file_size_mb(file_path)

    result: dict[str, Any] = {
        "file_path": file_path,
        "detected_format": fmt.value,
        "size_mb": round(size_mb, 2),
        "duckdb_native": is_duckdb_native(fmt),
    }

    if fmt in (FileFormat.JSON, FileFormat.JSONL):
        json_format = _detect_json_format(file_path)
        result["json_structure"] = json_format

    return result


def list_tables(tool_context: ToolContext) -> dict[str, Any]:
    """List all tables currently loaded in the DuckDB session.

    Returns table names, source files, row counts, and column counts.
    """
    session = _get_session()
    registry = session.table_registry

    if not registry:
        return {
            "tables": [],
            "message": "No tables loaded. Use load_file to load a data file.",
        }

    tables = []
    for name, meta in registry.items():
        tables.append({
            "table_name": name,
            "source_path": meta.source_path,
            "source_format": meta.source_format,
            "row_count": meta.row_count,
            "column_count": meta.column_count,
        })

    return {"tables": tables, "total_tables": len(tables)}


def inspect_raw_file(file_path: str, tool_context: ToolContext) -> dict[str, Any]:
    """Read the first 15 lines of a raw file to diagnose loading issues.

    Use this when load_file fails. Helps identify delimiter problems,
    encoding issues, or unusual headers.

    Args:
        file_path: Absolute path to the file. If empty, uses the last loaded file.
    """
    if not file_path:
        file_path = tool_context.state.get("current_file", "")

    if not file_path or not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    lines = read_raw_lines(file_path, n=15)

    return {
        "file_path": file_path,
        "raw_lines": lines,
        "message": (
            "Inspect these lines to determine the correct delimiter, "
            "encoding, or if there is a header issue."
        ),
    }
