import json
import logging
import uuid
from datetime import datetime, timezone

from google.cloud import pubsub_v1

from config import Config

logger = logging.getLogger(__name__)

_publisher = pubsub_v1.PublisherClient()
_event_topic = f"projects/{Config.GCP_PROJECT}/topics/{Config.EVENT_TOPIC}"


def publish_event(payload: dict):
    payload["message_id"] = str(uuid.uuid4())
    payload["published_at"] = datetime.now(timezone.utc).isoformat()

    data = json.dumps(payload).encode("utf-8")
    future = _publisher.publish(_event_topic, data)
    message_id = future.result()

    logger.info(
        "Published %s to %s (msg_id: %s)",
        payload.get("type"),
        Config.EVENT_TOPIC,
        message_id,
    )
