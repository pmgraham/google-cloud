# Data Agent — Required Changes for Pipeline Integration

> **Agent source**: The datagrunt-agent has been copied into this repo at
> `services/data-cleaning-agent/`. All new files and changes described below
> should be made in that directory.

This document specifies all changes needed to integrate the data-cleaning-agent with the event-driven pipeline.

## Overview

The agent currently runs as a local ADK web server. It needs to be wrapped in a FastAPI service that:
1. Receives Eventarc HTTP POST triggers from GCS file uploads
2. Downloads files from GCS, processes them, uploads results back to GCS
3. Publishes Pub/Sub messages for the loader and logger
4. Checks Firestore for duplicate files before processing

## New Files

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### `requirements.txt`

Add to existing dependencies (or create standalone for Docker build):
```
fastapi
uvicorn
google-cloud-storage
google-cloud-pubsub
google-cloud-firestore
google-adk>=1.5.0
duckdb>=1.4.0
polars>=1.7.1
pandas
pyarrow
python-dotenv
```

### `src/main.py` — FastAPI Entrypoint

Single POST route at `/`. Receives Eventarc CloudEvent HTTP payload.

```python
from fastapi import FastAPI, Request
from src.event_handler import handle_eventarc

app = FastAPI()

@app.post("/")
async def root(request: Request):
    body = await request.json()
    result = handle_eventarc(body)
    return result  # Always 200
```

Returns `{"status": "success", "file_hash": "..."}` on success.
Returns `{"status": "failed", "error": "..."}` on failure.
**Never returns 500** — prevents Eventarc retry loops.

### `src/config.py` — Configuration

```python
import os

class Config:
    GCP_PROJECT = os.environ["GCP_PROJECT"]
    GCS_BUCKET = os.environ["GCS_BUCKET"]
    LOAD_TOPIC = os.environ["LOAD_TOPIC"]
    EVENT_TOPIC = os.environ["EVENT_TOPIC"]
    TEMP_DIR = "/tmp/agent_work"
```

### `src/event_handler.py` — Main Orchestrator

Responsibilities:
1. Parse Eventarc payload → extract `bucket`, `name` (object path), `size`
2. Derive `target_table` from folder path: `inbox/{target_table}/{filename}`
   - Validate subfolder exists (error if file uploaded directly to `inbox/`)
3. Download file from GCS to `TEMP_DIR`
4. Compute SHA-256 hash of downloaded file
5. Check Firestore for duplicate (skip if hash exists with terminal success status)
6. Run the ADK agent: quality assessment → cleaning → Parquet export
7. Upload outputs to GCS:
   - Parquet → `gs://{bucket}/staging/{target_table}/{filename}.parquet`
   - Quality report → `gs://{bucket}/reports/quality/{target_table}/{filename}_quality.json`
   - Cleaning report → `gs://{bucket}/reports/cleaning/{target_table}/{filename}_cleaning.json`
8. Publish LOAD_REQUEST to Topic A (file-load-requests)
9. Publish AGENT_CLEANING_COMPLETE to Topic B (pipeline-events)
10. On failure: publish AGENT_CLEANING_FAILED to Topic B instead

Full try/except — failures are published, not raised.

### `src/file_manager.py` — GCS Operations

```python
def download(gcs_uri: str) -> str:
    """Download from GCS to /tmp. Returns local path."""

def upload_parquet(local_path: str, target_table: str, filename: str) -> str:
    """Upload Parquet to staging/. Returns GCS URI."""

def upload_json(data: dict, gcs_path: str) -> str:
    """Upload JSON dict to GCS. Returns GCS URI."""
```

### `src/publisher.py` — Pub/Sub Publishing

```python
def publish_load_request(payload: dict):
    """Publish to Topic A (LOAD_TOPIC). Auto-adds message_id and published_at."""

def publish_event(payload: dict):
    """Publish to Topic B (EVENT_TOPIC). Auto-adds message_id and published_at."""
```

### `src/hash_utils.py` — File Hashing

```python
def compute_hash(file_path: str) -> str:
    """Compute SHA-256 hex digest. Reads in 8KB chunks for memory efficiency."""
```

### `src/duplicate_checker.py` — Firestore Duplicate Check

```python
def is_duplicate(file_hash: str) -> bool:
    """
    Check Firestore file_registry by document ID (hash).
    Returns False if:
      - Document doesn't exist
      - Status is AGENT_CLEANING_FAILED
      - Status is LOADER_BIGQUERY_FAILED
    Returns True if:
      - Status is AGENT_CLEANING_COMPLETE
      - Status is LOADER_BIGQUERY_COMPLETE
    """
```

Uses Firestore database `pipeline-state`, collection `file_registry`.

## Existing File Modifications

### Agent Pipeline Changes

The existing ADK agent pipeline (load → quality → clean → export) needs to be callable programmatically, not just via ADK web UI.

**`src/agent/data_agent.py`** — New wrapper that:
1. Accepts `file_path`, `file_type`, `file_name`
2. Invokes `load_file()` → `quality_report()` → `clean_table()` → `export_parquet()`
3. Returns a result object:
   ```python
   {
       "cleaned_df": pa.Table,       # or path to Parquet
       "quality_report": dict,
       "cleaning_report": dict,
       "row_count_raw": int,
       "row_count_cleaned": int,
       "columns_detected": list[str],
   }
   ```

This may require refactoring the existing tools to work outside the ADK `ToolContext` — or running the ADK agent programmatically via `Runner`.

### DuckDB GCS Support

The DuckDB session needs the `httpfs` extension configured for GCS reads (Phase 3 in ROADMAP.md). This may be needed if files are read directly from GCS rather than downloaded first. If we download to `/tmp` first (recommended for Cloud Run), this isn't needed immediately.

**Recommendation**: Download to `/tmp` first. Simpler, avoids httpfs config, works within Cloud Run's `/tmp` volume.

## Environment Variables

New variables needed on Cloud Run:

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_PROJECT` | GCP project ID | `my-project-123` |
| `GCS_BUCKET` | Pipeline GCS bucket | `my-pipeline-bucket` |
| `LOAD_TOPIC` | Pub/Sub Topic A name | `file-load-requests` |
| `EVENT_TOPIC` | Pub/Sub Topic B name | `pipeline-events` |

Existing variables that still apply:
- `GOOGLE_GENAI_USE_VERTEXAI=TRUE` (Cloud Run uses ADC, not API key)
- `GOOGLE_CLOUD_PROJECT` (same as GCP_PROJECT)
- `GOOGLE_CLOUD_LOCATION=us-central1`
- Model override vars (`DEFAULT_MODEL`, etc.)

**Remove**: `GOOGLE_API_KEY` — Cloud Run uses Application Default Credentials via Vertex AI.

## Pub/Sub Message Schemas

### LOAD_REQUEST (→ Topic A)

```json
{
    "message_id": "uuid-v4",
    "type": "LOAD_REQUEST",
    "file_hash": "{sha256}",
    "original_file_name": "sales_data_2026_01.csv",
    "original_file_uri": "gs://bucket/inbox/sales_data/sales_data_2026_01.csv",
    "parquet_uri": "gs://bucket/staging/sales_data/sales_data_2026_01.parquet",
    "target_namespace": "bronze",
    "target_table": "sales_data",
    "write_mode": "APPEND",
    "row_count": 15420,
    "schema": [
        {"name": "order_id", "type": "string"},
        {"name": "customer", "type": "string"},
        {"name": "amount", "type": "float64"},
        {"name": "date", "type": "date"}
    ],
    "partition_spec": [
        {"field": "date", "transform": "month"}
    ],
    "upsert_keys": [],
    "published_at": "2026-02-14T10:30:00Z"
}
```

### AGENT_CLEANING_COMPLETE (→ Topic B)

```json
{
    "message_id": "uuid-v4",
    "type": "AGENT_CLEANING_COMPLETE",
    "file_hash": "{sha256}",
    "file_name": "sales_data_2026_01.csv",
    "file_path": "gs://bucket/inbox/sales_data/sales_data_2026_01.csv",
    "file_type": "csv",
    "file_size_bytes": 1048576,
    "target_namespace": "bronze",
    "target_table": "sales_data",
    "parquet_uri": "gs://bucket/staging/sales_data/sales_data_2026_01.parquet",
    "quality_report_uri": "gs://bucket/reports/quality/sales_data/..._quality.json",
    "cleaning_report_uri": "gs://bucket/reports/cleaning/sales_data/..._cleaning.json",
    "row_count_raw": 15832,
    "row_count_cleaned": 15420,
    "columns_detected": ["order_id", "customer", "amount", "date"],
    "processing_duration_seconds": 42.7,
    "published_at": "2026-02-14T10:30:00Z"
}
```

### AGENT_CLEANING_FAILED (→ Topic B)

```json
{
    "message_id": "uuid-v4",
    "type": "AGENT_CLEANING_FAILED",
    "file_hash": "{sha256}",
    "file_name": "sales_data_2026_01.csv",
    "file_path": "gs://bucket/inbox/sales_data/sales_data_2026_01.csv",
    "file_type": "csv",
    "file_size_bytes": 1048576,
    "target_namespace": "bronze",
    "target_table": "sales_data",
    "quality_report_uri": null,
    "error_message": "File contains no parseable rows after header detection",
    "error_code": "EMPTY_DATASET",
    "error_stage": "PARSING",
    "retry_count": 0,
    "processing_duration_seconds": 3.1,
    "published_at": "2026-02-14T10:30:03Z"
}
```

## Cloud Run Settings

These are defined in Terraform (`cloud_run_agent.tf`) but documented here for reference:

- Memory: 4Gi
- CPU: 2
- Timeout: 900s (15 min)
- Concurrency: 1 (one file per instance)
- Min instances: 0
- Max instances: 10
- Service account: `data-agent@{project}.iam.gserviceaccount.com`

## Implementation Priority

1. `Dockerfile` + `requirements.txt`
2. `src/config.py`
3. `src/hash_utils.py`
4. `src/file_manager.py`
5. `src/duplicate_checker.py`
6. `src/publisher.py`
7. `src/agent/data_agent.py` (programmatic agent wrapper)
8. `src/event_handler.py` (orchestrator)
9. `src/main.py` (FastAPI entrypoint)
10. Tests
