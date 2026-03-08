"""CSV delimiter auto-detection via character frequency analysis.

Ported from datagrunt/core/csv_io/csvcomponents.py CSVDelimiter.
"""

import re
from collections import Counter
from pathlib import Path


DELIMITER_REGEX_PATTERN = re.compile(r'[^0-9a-zA-Z_ "-]')
DEFAULT_DELIMITER = ","
TAB_DELIMITER = "\t"

TSV_EXTENSIONS = {".tsv", ".tab"}


def detect_delimiter(file_path: str) -> str:
    """Detect the delimiter of a CSV/TSV file.

    Strategy:
    1. If file extension is .tsv/.tab, return tab delimiter.
    2. Read the first line (header row).
    3. Count frequency of non-alphanumeric characters.
    4. Return the most common one as the delimiter.
    5. Fall back to comma if nothing found.

    Args:
        file_path: Path to the delimited file.

    Returns:
        The detected delimiter character.
    """
    path = Path(file_path)

    # TSV by extension
    if path.suffix.lower() in TSV_EXTENSIONS:
        return TAB_DELIMITER

    # Check for empty/blank file
    if path.stat().st_size == 0:
        return DEFAULT_DELIMITER

    # Read first line
    first_line = _read_first_line(file_path)
    if not first_line:
        return DEFAULT_DELIMITER

    # Frequency analysis on header row
    candidates = _get_delimiter_candidates(first_line)
    if not candidates:
        # No special characters found — could be space-delimited
        if " " in first_line:
            return " "
        return DEFAULT_DELIMITER

    return candidates[0][0]


def _read_first_line(file_path: str) -> str:
    """Read the first line of a file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.readline().strip()


def _get_delimiter_candidates(line: str) -> list[tuple[str, int]]:
    """Get the most common non-alphanumeric characters from a string.

    Returns:
        List of (character, count) tuples sorted by frequency descending.
    """
    line_no_spaces = line.replace(" ", "")
    chars = DELIMITER_REGEX_PATTERN.findall(line_no_spaces)
    counts = Counter(chars)
    return counts.most_common()


def read_raw_lines(file_path: str, n: int = 15) -> list[str]:
    """Read the first N lines of a file for diagnostic inspection.

    Useful when CSV parsing fails and we need to diagnose the format.
    """
    lines = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        for _ in range(n):
            line = fh.readline()
            if not line:
                break
            lines.append(line)
    return lines


def count_source_lines(file_path: str) -> int:
    """Count the number of data lines in a file (excluding header).

    Uses fast binary reading for performance on large files.
    """
    line_count = 0
    with open(file_path, "rb") as fh:
        while True:
            buf = fh.read(1024 * 1024)
            if not buf:
                break
            line_count += buf.count(b"\n")
    return max(line_count - 1, 0)
