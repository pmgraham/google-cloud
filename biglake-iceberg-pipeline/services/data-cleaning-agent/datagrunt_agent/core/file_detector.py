"""Detect file format and encoding from extension, magic bytes, and byte analysis."""

import enum
import tempfile
from pathlib import Path


class FileFormat(enum.Enum):
    """Supported file formats."""
    CSV = "csv"
    TSV = "tsv"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    EXCEL = "excel"
    UNKNOWN = "unknown"


EXTENSION_MAP = {
    ".csv": FileFormat.CSV,
    ".tsv": FileFormat.TSV,
    ".json": FileFormat.JSON,
    ".jsonl": FileFormat.JSONL,
    ".ndjson": FileFormat.JSONL,
    ".parquet": FileFormat.PARQUET,
    ".pq": FileFormat.PARQUET,
    ".xlsx": FileFormat.EXCEL,
    ".xls": FileFormat.EXCEL,
    ".xlsm": FileFormat.EXCEL,
    ".xltx": FileFormat.EXCEL,
}

# Magic bytes for format detection when extension is ambiguous
MAGIC_BYTES = {
    b"PAR1": FileFormat.PARQUET,
    b"PK\x03\x04": FileFormat.EXCEL,  # ZIP archive (xlsx is a zip)
}

# Formats that DuckDB can load directly
DUCKDB_NATIVE_FORMATS = {
    FileFormat.CSV,
    FileFormat.TSV,
    FileFormat.JSON,
    FileFormat.JSONL,
    FileFormat.PARQUET,
    FileFormat.EXCEL,
}


def detect_format(file_path: str) -> FileFormat:
    """Detect the file format from extension, falling back to magic bytes.

    Args:
        file_path: Path to the file.

    Returns:
        The detected FileFormat.
    """
    path = Path(file_path)

    # Try extension first
    ext = path.suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]

    # Fall back to magic bytes
    try:
        with open(path, "rb") as fh:
            header = fh.read(8)
        for magic, fmt in MAGIC_BYTES.items():
            if header.startswith(magic):
                return fmt
    except (OSError, IOError):
        pass

    return FileFormat.UNKNOWN


def is_duckdb_native(fmt: FileFormat) -> bool:
    """Check if a format can be loaded directly by DuckDB."""
    return fmt in DUCKDB_NATIVE_FORMATS


def get_file_size_mb(file_path: str) -> float:
    """Return file size in megabytes."""
    return Path(file_path).stat().st_size / (1024 * 1024)


def is_empty_file(file_path: str) -> bool:
    """Check if a file is empty (0 bytes)."""
    return Path(file_path).stat().st_size == 0


_BINARY_FORMATS = {FileFormat.PARQUET, FileFormat.EXCEL}
_ENCODING_SAMPLE_BYTES = 65536  # 64KB sample for detection


def detect_encoding(file_path: str, fmt: FileFormat | None = None) -> str | None:
    """Detect the character encoding of a text file.

    Uses charset_normalizer to analyze the first 64KB.

    Args:
        file_path: Path to the file.
        fmt: Optional pre-detected format. Binary formats return None.

    Returns:
        Encoding name (e.g., "utf-8", "windows-1252") or None for binary formats.
    """
    if fmt in _BINARY_FORMATS:
        return None

    try:
        from charset_normalizer import from_bytes

        with open(file_path, "rb") as fh:
            sample = fh.read(_ENCODING_SAMPLE_BYTES)

        result = from_bytes(sample).best()
        if result is None:
            return "utf-8"
        return result.encoding
    except Exception:
        return "utf-8"


def ensure_utf8(file_path: str, fmt: FileFormat | None = None) -> tuple[str, str | None, bool]:
    """Ensure a file is UTF-8 encoded, transcoding if necessary.

    Args:
        file_path: Path to the source file.
        fmt: Optional pre-detected format. Binary formats skip transcoding.

    Returns:
        Tuple of (load_path, detected_encoding, is_lossy):
        - load_path: Path to use for loading (original or temp transcoded file).
        - detected_encoding: The detected encoding name, or None for binary.
        - is_lossy: True if transcoding had to use replacement characters.
    """
    encoding = detect_encoding(file_path, fmt)

    if encoding is None:
        return file_path, None, False

    if encoding.lower().replace("-", "") in ("utf8", "ascii"):
        return file_path, encoding, False

    # Transcode to UTF-8
    is_lossy = False
    try:
        with open(file_path, "r", encoding=encoding, errors="strict") as src:
            content = src.read()
    except (UnicodeDecodeError, LookupError):
        with open(file_path, "r", encoding=encoding, errors="replace") as src:
            content = src.read()
        is_lossy = True

    suffix = Path(file_path).suffix
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8",
    )
    tmp.write(content)
    tmp.close()

    return tmp.name, encoding, is_lossy


def is_blank_file(file_path: str, size_threshold_mb: float = 10.0) -> bool:
    """Check if a file contains only whitespace.

    Skips the check for files larger than size_threshold_mb as they are
    very unlikely to be blank.
    """
    path = Path(file_path)
    if path.stat().st_size / (1024 * 1024) >= size_threshold_mb:
        return False
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read().strip()
    return not content
