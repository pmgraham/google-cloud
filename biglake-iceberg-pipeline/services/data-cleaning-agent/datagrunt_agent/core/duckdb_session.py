"""DuckDB session manager with table registry and safe SQL execution."""

import re
from pathlib import Path
from typing import Any

import duckdb
import polars as pl


_DESTRUCTIVE_PATTERN = re.compile(
    r"^\s*(DELETE\b|DROP\s+TABLE\b|TRUNCATE\b|DROP\s+DATABASE\b)",
    re.IGNORECASE,
)


class TableMetadata:
    """Metadata about a table loaded into the DuckDB session."""

    def __init__(
        self,
        table_name: str,
        source_path: str,
        source_format: str,
        row_count: int,
        column_count: int,
        source_row_count: int = 0,
    ):
        self.table_name = table_name
        self.source_path = source_path
        self.source_format = source_format
        self.row_count = row_count
        self.column_count = column_count
        self.source_row_count = source_row_count


class DuckDBSession:
    """Manages a single in-memory DuckDB connection for the agent session.

    Provides:
    - Connection lifecycle management
    - Table registry tracking loaded tables and their source files
    - Safe SQL execution with destructive query rejection
    - Helper methods for common operations
    """

    def __init__(self, threads: int = 16):
        self._connection = duckdb.connect(":memory:", config={"threads": threads})
        self._table_registry: dict[str, TableMetadata] = {}
        self._install_extensions()

    def _install_extensions(self):
        """Install commonly needed DuckDB extensions."""
        for ext in ("icu", "spatial"):
            try:
                self._connection.execute(f"INSTALL {ext}; LOAD {ext};")
            except Exception:
                pass

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._connection

    @property
    def table_registry(self) -> dict[str, TableMetadata]:
        return dict(self._table_registry)

    def register_table(self, metadata: TableMetadata):
        """Register a table in the session registry."""
        self._table_registry[metadata.table_name] = metadata

    def unregister_table(self, table_name: str):
        """Remove a table from the registry."""
        self._table_registry.pop(table_name, None)

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the DuckDB session."""
        try:
            self._connection.execute(f"SELECT 1 FROM {table_name} LIMIT 0")
            return True
        except Exception:
            return False

    def execute(self, sql: str) -> duckdb.DuckDBPyRelation:
        """Execute SQL against the session connection."""
        return self._connection.sql(sql)

    def execute_safe(self, sql: str) -> duckdb.DuckDBPyRelation:
        """Execute SQL with destructive query rejection.

        Raises:
            ValueError: If the SQL contains destructive operations.
        """
        rejection = reject_destructive(sql)
        if rejection:
            raise ValueError(rejection["error"])
        return self._connection.sql(sql)

    def execute_to_polars(self, sql: str) -> pl.DataFrame:
        """Execute SQL and return results as a Polars DataFrame."""
        return self._connection.sql(sql).pl()

    def execute_to_polars_safe(self, sql: str, table: str) -> pl.DataFrame:
        """Execute SQL safely, returning helpful errors on binder failures."""
        rejection = reject_destructive(sql)
        if rejection:
            raise ValueError(rejection["error"])
        try:
            return self._connection.sql(sql).pl()
        except duckdb.BinderException as exc:
            columns = self.get_column_names(table)
            raise duckdb.BinderException(
                f"{exc}\n\nAvailable columns in '{table}': {columns}"
            ) from None

    def get_column_names(self, table: str) -> list[str]:
        """Return column names for a table."""
        return [
            row["column_name"]
            for row in self._connection.sql(f"DESCRIBE {table}").pl().to_dicts()
        ]

    def get_column_types(self, table: str) -> dict[str, str]:
        """Return a mapping of column name to type for a table."""
        rows = self._connection.sql(f"DESCRIBE {table}").pl().to_dicts()
        return {row["column_name"]: row["column_type"] for row in rows}

    def get_row_count(self, table: str) -> int:
        """Return the row count for a table."""
        return self._connection.sql(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def generate_table_name(self, file_path: str) -> str:
        """Generate a safe DuckDB table name from a file path."""
        stem = Path(file_path).stem
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", stem).lower()
        safe_name = re.sub(r"_+", "_", safe_name).strip("_")
        if not safe_name or safe_name[0].isdigit():
            safe_name = f"t_{safe_name}"
        return f"table_{safe_name}"

    def to_markdown(
        self,
        frame: pl.DataFrame,
        exclude: list[str] | None = None,
        max_columns: int = 10,
        max_cell_width: int = 40,
    ) -> str:
        """Convert a Polars DataFrame to a markdown table string.

        Args:
            frame: The DataFrame to convert.
            exclude: Column names to exclude.
            max_columns: Maximum columns to display (default 10).
            max_cell_width: Truncate cell values longer than this (default 40).
        """
        if frame.is_empty():
            return "No rows."
        exclude = exclude or []
        all_cols = [c for c in frame.columns if c not in exclude]
        truncated = len(all_cols) > max_columns
        cols = all_cols[:max_columns]

        def _truncate(value: str) -> str:
            if len(value) > max_cell_width:
                return value[: max_cell_width - 3] + "..."
            return value

        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join("---" for _ in cols) + " |"
        rows = []
        for row in frame.to_dicts():
            row_str = "| " + " | ".join(_truncate(str(row[c])) for c in cols) + " |"
            rows.append(row_str)
        lines = [header, sep] + rows
        if truncated:
            lines.append(f"\n*(showing {len(cols)} of {len(all_cols)} columns)*")
        return "\n".join(lines)

    def close(self):
        """Close the DuckDB connection."""
        self._connection.close()


def reject_destructive(sql: str) -> dict[str, Any] | None:
    """Return an error dict if the SQL would destroy data, else None."""
    if _DESTRUCTIVE_PATTERN.search(sql):
        return {
            "error": (
                "DELETE, DROP TABLE, and TRUNCATE are not allowed. "
                "Rows must never be removed. Use UPDATE to fix values "
                "or add a flag column to mark problematic rows."
            ),
            "rejected_sql": sql,
        }
    return None


def validate_path(path: str) -> str:
    """Validate that the path exists and return the absolute path.

    Raises:
        ValueError: If path is empty or file does not exist.
    """
    if not path:
        raise ValueError("Path cannot be empty")
    abs_path = str(Path(path).resolve())
    if not Path(abs_path).exists():
        raise ValueError(f"File not found: {path}")
    return abs_path


def validate_column(column: str, table: str, session: "DuckDBSession") -> dict[str, Any] | None:
    """Return an error dict if column does not exist in table, else None."""
    columns = session.get_column_names(table)
    if column not in columns:
        return {
            "error": f"Column '{column}' does not exist.",
            "available_columns": columns,
            "table_name": table,
        }
    return None
