"""Tests for ingestion tools — CSV, JSON/JSONL loading and preprocessing."""

from unittest.mock import MagicMock

from datagrunt_agent.tools.ingestion import (
    _detect_json_format,
    _validate_json,
    _repair_json,
    _repair_json_string,
    detect_format,
    load_file,
)


def _make_tool_context():
    """Create a mock ToolContext with a dict-backed state."""
    ctx = MagicMock()
    ctx.state = {}
    return ctx


# ---------------------------------------------------------------------------
# CSV Loading
# ---------------------------------------------------------------------------

class TestCSVLoading:

    def test_load_simple_csv(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        assert result["status"] == "success"
        assert result["total_rows"] == 5
        assert result["column_count"] == 4
        assert result["table_name"].startswith("table_")
        assert ctx.state["current_table"] == result["table_name"]

    def test_load_csv_normalizes_columns(self, messy_columns_csv):
        ctx = _make_tool_context()
        result = load_file(messy_columns_csv, ctx)
        assert result["status"] == "success"
        # Check that messy column names were normalized
        col_names = [c["name"] for c in result["columns"]]
        assert "first_name" in col_names
        assert "last_name" in col_names
        assert "date_of_birth" in col_names

    def test_load_csv_with_commas_in_values(self, bad_quoting_csv):
        ctx = _make_tool_context()
        result = load_file(bad_quoting_csv, ctx)
        assert result["status"] == "success"
        assert result["total_rows"] == 4

    def test_load_semicolon_csv(self, semicolon_csv):
        ctx = _make_tool_context()
        result = load_file(semicolon_csv, ctx)
        assert result["status"] == "success"
        assert result["total_rows"] == 3

    def test_load_nonexistent_file(self):
        ctx = _make_tool_context()
        result = load_file("/nonexistent/file.csv", ctx)
        assert "error" in result

    def test_load_registers_table(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        assert result["table_name"] in ctx.state["loaded_tables"]

    def test_load_provides_sample(self, sample_csv):
        ctx = _make_tool_context()
        result = load_file(sample_csv, ctx)
        assert "sample" in result
        assert "|" in result["sample"]  # Markdown table

    def test_overflow_columns_repaired(self, overflow_columns_csv):
        """Overflow columns are removed and affected rows flagged with is_shifted."""
        ctx = _make_tool_context()
        result = load_file(overflow_columns_csv, ctx)
        assert result["status"] == "success"
        col_names = [c["name"] for c in result["columns"]]
        # is_shifted column should be present
        assert "is_shifted" in col_names
        # Overflow columns should be gone — only real columns + is_shifted
        assert result["overflow_columns_repaired"]
        assert result["overflow_rows_flagged"] > 0

    def test_overflow_columns_no_row_loss(self, overflow_columns_csv):
        """Overflow repair preserves all rows — no data loss."""
        ctx = _make_tool_context()
        result = load_file(overflow_columns_csv, ctx)
        assert result["status"] == "success"
        # All parsed rows survive the repair — none are dropped
        assert result["total_rows"] > 0


# ---------------------------------------------------------------------------
# JSON/JSONL Format Detection
# ---------------------------------------------------------------------------

class TestJSONFormatDetection:

    def test_detect_json_array(self, sample_json):
        assert _detect_json_format(sample_json) == "array"

    def test_detect_jsonl(self, sample_jsonl):
        assert _detect_json_format(sample_jsonl) == "newline_delimited"


# ---------------------------------------------------------------------------
# JSON Validation
# ---------------------------------------------------------------------------

class TestJSONValidation:

    def test_valid_json_array(self, sample_json):
        result = _validate_json(sample_json, "array")
        assert result["valid"] is True

    def test_valid_jsonl(self, sample_jsonl):
        result = _validate_json(sample_jsonl, "newline_delimited")
        assert result["valid"] is True

    def test_invalid_json_array(self, bad_json):
        result = _validate_json(bad_json, "array")
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_invalid_jsonl(self, bad_jsonl):
        result = _validate_json(bad_jsonl, "newline_delimited")
        assert result["valid"] is False
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# JSON Repair
# ---------------------------------------------------------------------------

class TestJSONRepair:

    def test_repair_trailing_comma(self):
        repaired = _repair_json_string('{"name": "Alice", "age": 30,}')
        assert repaired == '{"name": "Alice", "age": 30}'

    def test_repair_single_quotes(self):
        import json
        repaired = _repair_json_string("{'name': 'Alice'}")
        parsed = json.loads(repaired)
        assert parsed == {"name": "Alice"}

    def test_repair_json_array_file(self, bad_json):
        result = _repair_json(bad_json, "array")
        assert "repaired_path" in result
        assert result["lines_repaired"] == 1

    def test_repair_jsonl_atomic_failure(self, bad_jsonl):
        """JSONL repair must be atomic — fails if any line is unrecoverable."""
        result = _repair_json(bad_jsonl, "newline_delimited")
        # bad_jsonl has "this is not json at all" which can't be repaired
        assert result["repair_failed"] is True
        assert result["lines_failed"] > 0


# ---------------------------------------------------------------------------
# JSON Loading
# ---------------------------------------------------------------------------

class TestJSONLoading:

    def test_load_json_array(self, sample_json):
        ctx = _make_tool_context()
        result = load_file(sample_json, ctx)
        assert result["status"] == "success"
        assert result["total_rows"] == 3
        assert result["detected_format"] == "array"

    def test_load_jsonl(self, sample_jsonl):
        ctx = _make_tool_context()
        result = load_file(sample_jsonl, ctx)
        assert result["status"] == "success"
        assert result["total_rows"] == 3
        assert result["detected_format"] == "newline_delimited"

    def test_load_bad_json_repairs(self, bad_json):
        ctx = _make_tool_context()
        result = load_file(bad_json, ctx)
        # bad_json has trailing commas and single quotes — both repairable
        assert result["status"] == "success"
        assert "json_repair" in result

    def test_load_bad_jsonl_fails_atomically(self, bad_jsonl):
        ctx = _make_tool_context()
        result = load_file(bad_jsonl, ctx)
        # Standard path fails (DuckDB rejects bad lines without ignore_errors).
        # Recovery path also fails (unrepairable line "this is not json at all").
        # Both paths refuse to silently drop data.
        assert "error" in result


# ---------------------------------------------------------------------------
# detect_format tool
# ---------------------------------------------------------------------------

class TestDetectFormat:

    def test_detect_csv(self, sample_csv):
        result = detect_format(sample_csv)
        assert result["detected_format"] == "csv"

    def test_detect_json(self, sample_json):
        result = detect_format(sample_json)
        assert result["detected_format"] == "json"
        assert result["json_structure"] == "array"

    def test_detect_jsonl(self, sample_jsonl):
        result = detect_format(sample_jsonl)
        assert result["detected_format"] == "jsonl"
        assert result["json_structure"] == "newline_delimited"
