import base64
import json
import logging
import os
import time

from flask import Flask, request as flask_request

import bigquery_manager
import cleanup
import publisher
from message_parser import parse_load_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/", methods=["POST"])
def handle_pubsub():
    """Handle Pub/Sub push messages (standard wrapper format)."""
    envelope = flask_request.get_json(silent=True) or {}

    if "message" in envelope:
        raw = base64.b64decode(envelope["message"]["data"])
        message = json.loads(raw)
    else:
        message = envelope

    start = time.time()
    request = None

    try:
        request = parse_load_request(message)

        namespace = request["target_namespace"]
        table_name = request["target_table"]
        parquet_uri = request["parquet_uri"]
        write_mode = request["write_mode"]

        logger.info(
            "Loading %s into %s.%s (mode: %s)",
            parquet_uri,
            namespace,
            table_name,
            write_mode,
        )

        if bigquery_manager.table_exists(namespace, table_name):
            if write_mode == "UPSERT":
                load_id = bigquery_manager.upsert_data(
                    namespace=namespace,
                    table_name=table_name,
                    parquet_uri=parquet_uri,
                    upsert_keys=request.get("upsert_keys", []),
                )
            else:
                load_id = bigquery_manager.load_data(
                    namespace=namespace,
                    table_name=table_name,
                    parquet_uri=parquet_uri,
                    write_mode=write_mode,
                )
        else:
            load_id = bigquery_manager.create_iceberg_table(
                namespace=namespace,
                table_name=table_name,
                parquet_uri=parquet_uri,
            )

        archive_uri = cleanup.archive_original(
            request["original_file_uri"],
            table_name,
        )
        cleanup.delete_staging_parquet(parquet_uri)

        duration = time.time() - start

        publisher.publish_event({
            "type": "LOADER_BIGQUERY_COMPLETE",
            "file_hash": request["file_hash"],
            "target_namespace": namespace,
            "target_table": table_name,
            "iceberg_snapshot_id": load_id,
            "write_mode": write_mode,
            "row_count_loaded": request.get("row_count", 0),
            "original_file_uri": request["original_file_uri"],
            "archive_uri": archive_uri,
            "load_duration_seconds": round(duration, 1),
        })

        logger.info(
            "Successfully loaded into %s.%s in %.1fs (job: %s)",
            namespace,
            table_name,
            duration,
            load_id,
        )

        return ("OK", 200)

    except Exception as e:
        duration = time.time() - start

        error_payload = {
            "type": "LOADER_BIGQUERY_FAILED",
            "file_hash": request["file_hash"] if request else message.get("file_hash", "unknown"),
            "target_namespace": request["target_namespace"] if request else message.get("target_namespace", ""),
            "target_table": request["target_table"] if request else message.get("target_table", ""),
            "parquet_uri": request["parquet_uri"] if request else message.get("parquet_uri", ""),
            "error_message": str(e),
            "error_code": type(e).__name__,
            "retry_count": 0,
            "load_duration_seconds": round(duration, 1),
        }

        publisher.publish_event(error_payload)
        logger.exception("Load failed for %s", message.get("file_hash", "unknown"))
        return (str(e), 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
