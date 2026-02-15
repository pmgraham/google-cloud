"""Cloud Run entry point for the data-cleaning agent.

Receives Eventarc CloudEvents (GCS object.finalized) and runs the
deterministic pipeline: load → quality → clean → export → publish.

The LLM coordinator is bypassed — tool functions are called directly
since the pipeline flow is fixed.
"""

import hashlib
import json
import logging
import os
import time
from unittest.mock import MagicMock

import functions_framework
from cloudevents.http import CloudEvent
from google.cloud import pubsub_v1, storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (env vars set by Terraform cloud_run_agent.tf)
# ---------------------------------------------------------------------------
GCP_PROJECT = os.environ["GCP_PROJECT"]
INBOX_BUCKET = os.environ["INBOX_BUCKET"]
STAGING_BUCKET = os.environ["STAGING_BUCKET"]
LOAD_TOPIC = os.environ["LOAD_TOPIC"]
EVENT_TOPIC = os.environ["EVENT_TOPIC"]

_storage_client = storage.Client(project=GCP_PROJECT)
_publisher = pubsub_v1.PublisherClient()
_load_topic_path = f"projects/{GCP_PROJECT}/topics/{LOAD_TOPIC}"
_event_topic_path = f"projects/{GCP_PROJECT}/topics/{EVENT_TOPIC}"

WORK_DIR = "/tmp/datagrunt"

# ---------------------------------------------------------------------------
# Pipeline tools (imported from the agent package)
# ---------------------------------------------------------------------------
from datagrunt_agent.tools.ingestion import load_file  # noqa: E402
from datagrunt_agent.tools.quality import quality_report  # noqa: E402
from datagrunt_agent.tools.cleaning import clean_table  # noqa: E402
from datagrunt_agent.tools.export import export_parquet  # noqa: E402
from datagrunt_agent.tools.report import export_quality_report  # noqa: E402
from datagrunt_agent.tools.cleaning_report import export_cleaning_report  # noqa: E402


def _make_tool_context() -> MagicMock:
    """Create a mock ToolContext with a shared state dict."""
    ctx = MagicMock()
    ctx.state = {}
    return ctx


def _file_hash(bucket: str, name: str) -> str:
    """Deterministic hash for a GCS object (used as Firestore doc ID)."""
    return hashlib.sha256(f"gs://{bucket}/{name}".encode()).hexdigest()


def _upload_to_gcs(local_path: str, gcs_path: str) -> str:
    """Upload a local file to the staging bucket. Returns gs:// URI."""
    bucket = _storage_client.bucket(STAGING_BUCKET)
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(local_path)
    uri = f"gs://{STAGING_BUCKET}/{gcs_path}"
    logger.info("Uploaded %s → %s", local_path, uri)
    return uri


def _publish(topic_path: str, payload: dict):
    """Publish a JSON message to a Pub/Sub topic."""
    data = json.dumps(payload).encode("utf-8")
    future = _publisher.publish(topic_path, data)
    msg_id = future.result()
    logger.info("Published %s → %s (msg: %s)", payload.get("type"), topic_path, msg_id)


def _derive_table_name(object_name: str) -> str:
    """Derive the target table name from the GCS object path.

    Convention: gs://inbox-bucket/{table_name}/file.csv
    """
    parts = object_name.strip("/").split("/")
    if len(parts) >= 2:
        return parts[0]
    # Fallback: use filename stem
    return os.path.splitext(parts[-1])[0]


@functions_framework.cloud_event
def handle_gcs_event(cloud_event: CloudEvent):
    """Handle GCS object.finalized events from Eventarc."""
    data = cloud_event.data
    bucket_name = data["bucket"]
    object_name = data["name"]
    file_size = int(data.get("size", 0))

    # Skip non-data files
    if object_name.endswith("/") or object_name.startswith("."):
        logger.info("Skipping non-data object: %s", object_name)
        return

    source_uri = f"gs://{bucket_name}/{object_name}"
    file_name = os.path.basename(object_name)
    target_table = _derive_table_name(object_name)
    fhash = _file_hash(bucket_name, object_name)

    logger.info(
        "Processing %s → table=%s hash=%s",
        source_uri, target_table, fhash[:12],
    )

    start = time.time()
    os.makedirs(WORK_DIR, exist_ok=True)
    local_path = os.path.join(WORK_DIR, file_name)

    try:
        # --- Download from inbox bucket ---
        inbox_bucket = _storage_client.bucket(bucket_name)
        blob = inbox_bucket.blob(object_name)
        blob.download_to_filename(local_path)
        logger.info("Downloaded %s (%d bytes)", source_uri, file_size)

        ctx = _make_tool_context()

        # --- Step 1: Load file ---
        load_result = load_file(local_path, ctx, output_dir=WORK_DIR)
        if load_result.get("error"):
            raise RuntimeError(f"load_file failed: {load_result['error']}")

        table_name = load_result["table_name"]
        raw_rows = load_result["total_rows"]
        columns = load_result.get("columns", [])
        logger.info("Loaded %s: %d rows, %d columns", table_name, raw_rows, len(columns))

        # --- Step 2: Quality report ---
        quality_result = quality_report(table_name, ctx)
        logger.info(
            "Quality report: %s findings (%s)",
            len(quality_result.get("findings", [])),
            quality_result.get("severity_counts", {}),
        )

        # --- Step 3: Clean table ---
        clean_result = clean_table(table_name, ctx)
        cleaned_rows = clean_result.get("after", {}).get("rows", raw_rows)
        logger.info("Cleaned: %d → %d rows", raw_rows, cleaned_rows)

        # --- Step 4: Export cleaned parquet ---
        parquet_local = os.path.join(WORK_DIR, f"{target_table}_cleaned.parquet")
        export_result = export_parquet(table_name, parquet_local, ctx)
        logger.info("Exported parquet: %s", parquet_local)

        # --- Step 5: Export reports ---
        quality_report_local = os.path.join(WORK_DIR, f"{target_table}_quality.json")
        export_quality_report(table_name, quality_report_local, ctx)

        cleaning_report_local = os.path.join(WORK_DIR, f"{target_table}_cleaning.json")
        export_cleaning_report(table_name, cleaning_report_local, ctx)

        # --- Step 6: Upload outputs to staging bucket ---
        parquet_uri = _upload_to_gcs(
            parquet_local,
            f"parquet/{target_table}/{file_name.rsplit('.', 1)[0]}.parquet",
        )
        quality_report_uri = _upload_to_gcs(
            quality_report_local,
            f"reports/quality/{target_table}/{file_name.rsplit('.', 1)[0]}_quality.json",
        )
        cleaning_report_uri = _upload_to_gcs(
            cleaning_report_local,
            f"reports/cleaning/{target_table}/{file_name.rsplit('.', 1)[0]}_cleaning.json",
        )

        duration = time.time() - start

        # --- Step 7: Publish LOAD_REQUEST for the file-loader ---
        _publish(_load_topic_path, {
            "type": "LOAD_REQUEST",
            "file_hash": fhash,
            "parquet_uri": parquet_uri,
            "target_namespace": "bronze",
            "target_table": target_table,
            "original_file_uri": source_uri,
            "write_mode": "APPEND",
            "row_count": cleaned_rows,
        })

        # --- Step 8: Publish AGENT_CLEANING_COMPLETE event ---
        _publish(_event_topic_path, {
            "type": "AGENT_CLEANING_COMPLETE",
            "file_hash": fhash,
            "file_name": file_name,
            "file_path": source_uri,
            "file_type": os.path.splitext(file_name)[1].lstrip("."),
            "file_size_bytes": file_size,
            "target_namespace": "bronze",
            "target_table": target_table,
            "parquet_uri": parquet_uri,
            "quality_report_uri": quality_report_uri,
            "cleaning_report_uri": cleaning_report_uri,
            "row_count_raw": raw_rows,
            "row_count_cleaned": cleaned_rows,
            "columns_detected": len(columns),
            "processing_duration_seconds": round(duration, 1),
        })

        logger.info(
            "Pipeline complete for %s → %s in %.1fs",
            source_uri, target_table, duration,
        )

    except Exception as exc:
        duration = time.time() - start
        logger.exception("Pipeline failed for %s", source_uri)

        _publish(_event_topic_path, {
            "type": "AGENT_CLEANING_FAILED",
            "file_hash": fhash,
            "file_name": file_name,
            "file_path": source_uri,
            "file_type": os.path.splitext(file_name)[1].lstrip("."),
            "file_size_bytes": file_size,
            "target_namespace": "bronze",
            "target_table": target_table,
            "quality_report_uri": "",
            "error_message": str(exc),
            "error_code": type(exc).__name__,
            "error_stage": "agent_pipeline",
            "retry_count": 0,
            "processing_duration_seconds": round(duration, 1),
        })
        raise

    finally:
        # Clean up local files
        for f in os.listdir(WORK_DIR):
            try:
                os.remove(os.path.join(WORK_DIR, f))
            except OSError:
                pass
