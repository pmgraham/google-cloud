import base64
import json
import logging
import os

from flask import Flask, request as flask_request
from google.cloud import firestore

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATUS_RANK = {
    "AGENT_CLEANING_FAILED": 0,
    "AGENT_CLEANING_COMPLETE": 1,
    "LOADER_BIGQUERY_COMPLETE": 2,
    "LOADER_BIGQUERY_FAILED": 3,
}

_AGENT_COMPLETE_FIELDS = [
    "file_name",
    "file_path",
    "file_type",
    "file_size_bytes",
    "target_namespace",
    "target_table",
    "parquet_uri",
    "quality_report_uri",
    "cleaning_report_uri",
    "row_count_raw",
    "row_count_cleaned",
    "columns_detected",
    "processing_duration_seconds",
]

_AGENT_FAILED_FIELDS = [
    "file_name",
    "file_path",
    "file_type",
    "file_size_bytes",
    "target_namespace",
    "target_table",
    "quality_report_uri",
    "error_message",
    "error_code",
    "error_stage",
    "retry_count",
    "processing_duration_seconds",
]

_LOADER_COMPLETE_FIELDS = [
    "target_namespace",
    "target_table",
    "iceberg_snapshot_id",
    "write_mode",
    "row_count_loaded",
    "original_file_uri",
    "archive_uri",
    "load_duration_seconds",
]

_LOADER_FAILED_FIELDS = [
    "target_namespace",
    "target_table",
    "parquet_uri",
    "error_message",
    "error_code",
    "retry_count",
    "load_duration_seconds",
]

_FIELD_MAP = {
    "AGENT_CLEANING_COMPLETE": _AGENT_COMPLETE_FIELDS,
    "AGENT_CLEANING_FAILED": _AGENT_FAILED_FIELDS,
    "LOADER_BIGQUERY_COMPLETE": _LOADER_COMPLETE_FIELDS,
    "LOADER_BIGQUERY_FAILED": _LOADER_FAILED_FIELDS,
}

_TIMESTAMP_MAP = {
    "AGENT_CLEANING_COMPLETE": "cleaned_at",
    "LOADER_BIGQUERY_COMPLETE": "last_loaded_at",
}

db = firestore.Client(
    project=Config.GCP_PROJECT,
    database=Config.FIRESTORE_DATABASE,
)

app = Flask(__name__)


@app.route("/", methods=["POST"])
def handle_pipeline_event():
    """Handle Pub/Sub push messages (standard wrapper format)."""
    envelope = flask_request.get_json(silent=True) or {}

    if "message" in envelope:
        raw = base64.b64decode(envelope["message"]["data"])
        message = json.loads(raw)
    else:
        message = envelope

    message_type = message.get("type")
    file_hash = message.get("file_hash")

    if not message_type or not file_hash:
        logger.error("Missing type or file_hash in message: %s", message)
        return ("Missing required fields", 400)

    if message_type not in STATUS_RANK:
        logger.error("Unknown message type: %s", message_type)
        return ("Unknown message type", 400)

    logger.info("Processing %s for hash %s", message_type, file_hash[:12])

    allowed_fields = _FIELD_MAP[message_type]
    doc_data = {k: v for k, v in message.items() if k in allowed_fields and v is not None}

    now = firestore.SERVER_TIMESTAMP
    doc_data["updated_at"] = now

    timestamp_field = _TIMESTAMP_MAP.get(message_type)
    if timestamp_field:
        doc_data[timestamp_field] = now

    doc_ref = db.collection(Config.FILE_REGISTRY_COLLECTION).document(file_hash)

    @firestore.transactional
    def update_in_transaction(transaction):
        snapshot = doc_ref.get(transaction=transaction)

        if snapshot.exists:
            current_status = snapshot.get("status") or ""
            current_rank = STATUS_RANK.get(current_status, -1)
            new_rank = STATUS_RANK[message_type]

            if new_rank > current_rank:
                doc_data["status"] = message_type
        else:
            doc_data["status"] = message_type
            doc_data["created_at"] = now

        transaction.set(doc_ref, doc_data, merge=True)

    transaction = db.transaction()
    update_in_transaction(transaction)

    logger.info("Updated file_registry for hash %s — status: %s", file_hash[:12], message_type)

    if message_type == "LOADER_BIGQUERY_COMPLETE":
        _update_table_routing(message)

    return ("OK", 200)


def _update_table_routing(message):
    namespace = message.get("target_namespace", "bronze")
    table = message.get("target_table")
    if not table:
        return

    doc_id = f"{namespace}.{table}"
    doc_ref = db.collection(Config.TABLE_ROUTING_COLLECTION).document(doc_id)

    now = firestore.SERVER_TIMESTAMP
    row_count = message.get("row_count_loaded", 0)

    update_data = {
        "target_namespace": namespace,
        "target_table": table,
        "last_loaded_at": now,
        "last_loaded_file": message.get("original_file_uri"),
        "last_loaded_hash": message.get("file_hash"),
        "total_files_loaded": firestore.Increment(1),
        "total_rows_loaded": firestore.Increment(row_count),
        "updated_at": now,
    }

    snapshot = doc_ref.get()
    if not snapshot.exists:
        update_data["first_loaded_at"] = now
        update_data["auto_create_table"] = True
        update_data["enabled"] = True
        update_data["source_folder"] = f"gs://{Config.INBOX_BUCKET}/{table}/"
        update_data["write_mode"] = message.get("write_mode", "APPEND")

    doc_ref.set(update_data, merge=True)

    logger.info("Updated table_routing for %s", doc_id)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
