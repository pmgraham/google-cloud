import os


class Config:
    GCP_PROJECT: str = os.environ["GCP_PROJECT"]
    INBOX_BUCKET: str = os.environ["INBOX_BUCKET"]
    FIRESTORE_DATABASE: str = os.environ.get("FIRESTORE_DATABASE", "pipeline-state")
    FILE_REGISTRY_COLLECTION: str = "file_registry"
    TABLE_ROUTING_COLLECTION: str = "table_routing"
