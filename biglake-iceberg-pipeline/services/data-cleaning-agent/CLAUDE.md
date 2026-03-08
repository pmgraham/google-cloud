# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DataGrunt is a Google ADK agent that loads structured/semi-structured files (CSV, TSV, JSON, JSONL, Parquet, Excel) into DuckDB, stamps them with `processed_at`, auto-exports to Parquet, and reports data quality findings. It does NOT transform, coerce, clean, or modify data values — that is the downstream pipeline's job.

## Commands

```bash
# Run ADK web server (from project root)
adk web datagrunt_agent

# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/test_ingestion.py -v

# Run single test
pytest tests/test_core.py::TestColumnNormalizer::test_camel_case

# Lint / format
ruff check datagrunt_agent tests
ruff format datagrunt_agent tests
```

Python 3.12+. Package manager: `uv`. Install: `uv sync`.

## Architecture

### Agent Hierarchy

```
root_agent (Coordinator) — datagrunt_agent/agent.py
├── Profiler Agent          → profiling tools (profile_columns, profile_table, sample_data)
├── SchemaArchitect Agent   → placeholder, no tools yet
├── QualityAnalyst Agent    → quality_report (observational only, never modifies data)
└── Direct Tools
    ├── Ingestion: load_file, detect_format, list_tables, inspect_raw_file
    └── Export: export_csv, export_parquet, export_json, export_jsonl, export_excel
```

### Module Layout

- **`agent.py`** — ADK entry point, wires agents to tools. `root_agent` is the ADK discovery export.
- **`tools/`** — ADK FunctionTool implementations. Each function takes `ToolContext` for session state.
- **`core/`** — Infrastructure: DuckDB session management, SQL template loading, delimiter/format detection, column normalization.
- **`prompts/`** — System instructions for each agent (coordinator, profiler, quality_analyst, schema_architect).
- **`sql/`** — Externalized SQL templates organized by category (`ingestion/`, `export/`, `profiling/`, `quality/`, `schema/`). Loaded via `load_sql(category, name, **params)` which does `{{ variable }}` substitution.

### Key Design Decisions

- **All SQL is externalized** in `sql/` directory, never inlined in Python. Use `load_sql("category", "name", key=value)`.
- **CSV loads use `all_varchar = true`** to prevent data loss (leading zeros in zip codes, etc.). Post-load type coercion (`_coerce_types`) safely casts VARCHAR → BIGINT/DOUBLE/BOOLEAN only when lossless.
- **LLM-based header detection** — sends first 3 rows to Gemini to classify whether row 1 is headers or data. Mocked in tests via `conftest.py` autouse fixture.
- **Multi-strategy CSV parsing** — tries 4 quote/escape configurations, picks the one with fewest overflow columns.
- **Module-level DuckDB session singleton** (`_get_session()` in ingestion.py) — shared across tool calls within an agent session. Reset between tests via conftest autouse fixture.
- **Post-load pipeline** runs on every successful load: normalize column names → stamp `processed_at` → export Parquet → run quality summary → register table.
- **Atomic loads** — if rows are lost during CSV parsing, the entire load fails. No partial data.

### Data Flow

```
User file → load_file() → detect format → format-specific loader → DuckDB table
  → normalize columns → coerce types → stamp processed_at → export Parquet
  → quality summary → return result dict
```

## Testing Patterns

- Mock `ToolContext` with `ctx = MagicMock(); ctx.state = {}`.
- Genai (Gemini) calls are auto-mocked in conftest to avoid real API calls. Tests that need specific LLM responses use `patch.dict(sys.modules, {...})` to inject mock `google.genai`.
- Test fixtures are CSV/JSON files in `tests/fixtures/`.
- `conftest.py` resets the module-level DuckDB session between tests.

## Environment

Vertex AI config in `datagrunt_agent/.env` (gitignored):
```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOCATION=us-central1
```

Or use API key mode via `.env` in project root (see `.env.example`).
