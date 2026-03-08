"""Loads SQL templates from external .sql files.

All SQL queries are stored in datagrunt_agent/sql/ and loaded by logical name.
Supports simple {{ variable }} substitution for table names, file paths, etc.
"""

import re
from functools import lru_cache
from pathlib import Path


_SQL_DIR = Path(__file__).parent.parent / "sql"
_TEMPLATE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@lru_cache(maxsize=128)
def _read_sql_file(relative_path: str) -> str:
    """Read and cache a SQL file from the sql/ directory."""
    sql_path = _SQL_DIR / relative_path
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL template not found: {sql_path}")
    return sql_path.read_text(encoding="utf-8").strip()


def load_sql(category: str, name: str, **params: str) -> str:
    """Load a SQL template and substitute parameters.

    Args:
        category: The subdirectory (e.g., 'ingestion', 'profiling').
        name: The SQL file name without extension (e.g., 'load_csv').
        **params: Template variables to substitute (e.g., table_name='my_table').

    Returns:
        The rendered SQL string.

    Example:
        sql = load_sql('ingestion', 'load_csv', file_path='/data/test.csv', table_name='test')
    """
    relative_path = f"{category}/{name}.sql"
    template = _read_sql_file(relative_path)
    return render_template(template, **params)


def render_template(template: str, **params: str) -> str:
    """Substitute {{ variable }} placeholders in a SQL template."""
    def replacer(match):
        key = match.group(1)
        if key not in params:
            raise KeyError(
                f"Missing SQL template parameter: '{key}'. "
                f"Available: {list(params.keys())}"
            )
        return str(params[key])

    return _TEMPLATE_PATTERN.sub(replacer, template)
