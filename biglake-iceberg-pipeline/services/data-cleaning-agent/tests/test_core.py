"""Tests for core infrastructure modules."""

import pytest

from datagrunt_agent.core.column_normalizer import (
    build_rename_mapping,
    normalize_column_name,
    normalize_column_names,
)
from datagrunt_agent.core.delimiter_detector import (
    count_source_lines,
    detect_delimiter,
    read_raw_lines,
)
from datagrunt_agent.core.duckdb_session import (
    DuckDBSession,
    reject_destructive,
    validate_path,
)
from datagrunt_agent.core.file_detector import FileFormat, detect_format
from datagrunt_agent.core.sql_loader import load_sql, render_template


# ---------------------------------------------------------------------------
# Column Normalizer
# ---------------------------------------------------------------------------

class TestColumnNormalizer:

    def test_simple_name(self):
        assert normalize_column_name("name") == "name"

    def test_camel_case(self):
        assert normalize_column_name("firstName") == "first_name"

    def test_pascal_case(self):
        assert normalize_column_name("FirstName") == "first_name"

    def test_spaces_and_special_chars(self):
        assert normalize_column_name("Annual Salary ($)") == "annual_salary"

    def test_leading_digit(self):
        assert normalize_column_name("2024_Revenue") == "_2024_revenue"

    def test_empty_string(self):
        assert normalize_column_name("") == "unnamed"

    def test_duplicate_handling(self):
        result = normalize_column_names(["Name", "name", "NAME"])
        assert result == ["name", "name_1", "name_2"]

    def test_build_rename_mapping(self):
        mapping = build_rename_mapping(["First Name", "age", "Date Of Birth"])
        assert "First Name" in mapping
        assert mapping["First Name"] == "first_name"
        assert "age" not in mapping  # Already normalized
        assert mapping["Date Of Birth"] == "date_of_birth"


# ---------------------------------------------------------------------------
# Delimiter Detector
# ---------------------------------------------------------------------------

class TestDelimiterDetector:

    def test_comma_csv(self, sample_csv):
        assert detect_delimiter(sample_csv) == ","

    def test_semicolon_csv(self, semicolon_csv):
        assert detect_delimiter(semicolon_csv) == ";"

    def test_count_source_lines(self, sample_csv):
        count = count_source_lines(sample_csv)
        assert count == 5  # 5 data rows (header excluded)

    def test_read_raw_lines(self, sample_csv):
        lines = read_raw_lines(sample_csv, n=3)
        assert len(lines) == 3
        assert "Name" in lines[0]


# ---------------------------------------------------------------------------
# File Detector
# ---------------------------------------------------------------------------

class TestFileDetector:

    def test_csv_detection(self, sample_csv):
        assert detect_format(sample_csv) == FileFormat.CSV

    def test_json_detection(self, sample_json):
        assert detect_format(sample_json) == FileFormat.JSON

    def test_jsonl_detection(self, sample_jsonl):
        assert detect_format(sample_jsonl) == FileFormat.JSONL


# ---------------------------------------------------------------------------
# DuckDB Session
# ---------------------------------------------------------------------------

class TestDuckDBSession:

    def test_create_session(self):
        session = DuckDBSession()
        assert session.connection is not None
        session.close()

    def test_generate_table_name(self):
        session = DuckDBSession()
        name = session.generate_table_name("/data/my-file.csv")
        assert name == "table_my_file"
        session.close()

    def test_generate_table_name_leading_digit(self):
        session = DuckDBSession()
        name = session.generate_table_name("/data/2024_data.csv")
        assert name == "table_t_2024_data"
        session.close()

    def test_table_exists_false(self):
        session = DuckDBSession()
        assert session.table_exists("nonexistent") is False
        session.close()

    def test_execute_and_query(self):
        session = DuckDBSession()
        session.execute("CREATE TABLE test_tbl (id INTEGER, name VARCHAR)")
        session.execute("INSERT INTO test_tbl VALUES (1, 'Alice'), (2, 'Bob')")
        assert session.table_exists("test_tbl")
        assert session.get_row_count("test_tbl") == 2
        assert session.get_column_names("test_tbl") == ["id", "name"]
        session.close()

    def test_reject_destructive(self):
        result = reject_destructive("DELETE FROM test")
        assert result is not None
        assert "error" in result

    def test_reject_destructive_safe(self):
        result = reject_destructive("SELECT * FROM test")
        assert result is None

    def test_validate_path_nonexistent(self):
        with pytest.raises(ValueError, match="File not found"):
            validate_path("/nonexistent/file.csv")

    def test_validate_path_empty(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_path("")

    def test_to_markdown(self):
        import polars as pl
        session = DuckDBSession()
        df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        md = session.to_markdown(df)
        assert "| a | b |" in md
        assert "| 1 | x |" in md
        session.close()


# ---------------------------------------------------------------------------
# SQL Loader
# ---------------------------------------------------------------------------

class TestSQLLoader:

    def test_render_template(self):
        result = render_template(
            "SELECT * FROM {{ table_name }} WHERE id = {{ id }}",
            table_name="users",
            id="42",
        )
        assert result == "SELECT * FROM users WHERE id = 42"

    def test_render_template_missing_param(self):
        with pytest.raises(KeyError, match="Missing SQL template parameter"):
            render_template("SELECT * FROM {{ table_name }}")

    def test_load_sql_ingestion_csv(self):
        sql = load_sql(
            "ingestion", "load_csv",
            table_name="test",
            file_path="/data/test.csv",
            delimiter=",",
            quote_char='"',
            escape_char='"',
        )
        assert "CREATE OR REPLACE TABLE test" in sql
        assert "/data/test.csv" in sql

    def test_load_sql_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_sql("nonexistent", "fake_query", table_name="test")
