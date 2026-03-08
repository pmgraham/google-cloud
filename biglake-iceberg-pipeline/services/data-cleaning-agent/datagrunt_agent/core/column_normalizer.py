"""Column name normalization to lowercase snake_case.

Ported from datagrunt/core/csv_io/csvcomponents.py CSVColumnNameNormalizer.
Works on any format, not just CSV.
"""

import re


SPECIAL_CHARS_PATTERN = re.compile(r"[^a-z0-9]+")
MULTI_UNDERSCORE_PATTERN = re.compile(r"_+")
CAMEL_CASE_BOUNDARY = re.compile(r"(.)([A-Z][a-z]+)")
CAMEL_CASE_LOWER_UPPER = re.compile(r"([a-z0-9])([A-Z])")


def normalize_column_name(name: str) -> str:
    """Normalize a single column name to lowercase snake_case.

    Steps:
    1. Expand camelCase boundaries (e.g., 'firstName' -> 'first_name')
    2. Lowercase
    3. Replace special characters and spaces with underscores
    4. Collapse multiple underscores
    5. Strip leading/trailing underscores
    6. Prefix with underscore if starts with a digit
    """
    # Expand camelCase to snake_case
    result = CAMEL_CASE_BOUNDARY.sub(r"\1_\2", name)
    result = CAMEL_CASE_LOWER_UPPER.sub(r"\1_\2", result)

    result = result.lower()
    result = SPECIAL_CHARS_PATTERN.sub("_", result)
    result = result.strip("_")
    result = MULTI_UNDERSCORE_PATTERN.sub("_", result)

    if not result:
        return "unnamed"
    if result[0].isdigit():
        return f"_{result}"
    return result


def normalize_column_names(columns: list[str]) -> list[str]:
    """Normalize a list of column names, ensuring uniqueness.

    Duplicate names get a numeric suffix (_1, _2, etc.).
    """
    normalized = [normalize_column_name(col) for col in columns]
    return make_unique(normalized)


def make_unique(names: list[str]) -> list[str]:
    """Ensure all names are unique by appending numeric suffixes to duplicates."""
    seen: dict[str, int] = {}
    result = []
    for name in names:
        if name in seen:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            result.append(name)
    return result


def build_rename_mapping(original: list[str]) -> dict[str, str]:
    """Build a mapping of original column names to normalized names.

    Only includes entries where the name actually changes.
    """
    normalized = normalize_column_names(original)
    return {
        old: new for old, new in zip(original, normalized) if old != new
    }
