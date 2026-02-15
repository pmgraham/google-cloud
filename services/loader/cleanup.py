import logging

from google.cloud import storage

from config import Config

logger = logging.getLogger(__name__)

_client = storage.Client(project=Config.GCP_PROJECT)
_inbox_bucket = _client.bucket(Config.INBOX_BUCKET)
_staging_bucket = _client.bucket(Config.STAGING_BUCKET)
_archive_bucket = _client.bucket(Config.ARCHIVE_BUCKET)


def archive_original(source_uri: str, target_table: str) -> str:
    """Move original file from inbox bucket to archive bucket."""
    source_path = source_uri.replace(f"gs://{Config.INBOX_BUCKET}/", "")
    filename = source_path.split("/")[-1]
    archive_path = f"{target_table}/{filename}"

    source_blob = _inbox_bucket.blob(source_path)
    _inbox_bucket.copy_blob(source_blob, _archive_bucket, archive_path)
    source_blob.delete()

    archive_uri = f"gs://{Config.ARCHIVE_BUCKET}/{archive_path}"
    logger.info("Archived %s → %s", source_uri, archive_uri)
    return archive_uri


def delete_staging_parquet(parquet_uri: str):
    parquet_path = parquet_uri.replace(f"gs://{Config.STAGING_BUCKET}/", "")
    blob = _staging_bucket.blob(parquet_path)
    blob.delete()
    logger.info("Deleted staging parquet: %s", parquet_uri)


def get_archive_uri(source_uri: str, target_table: str) -> str:
    source_path = source_uri.replace(f"gs://{Config.INBOX_BUCKET}/", "")
    filename = source_path.split("/")[-1]
    return f"gs://{Config.ARCHIVE_BUCKET}/{target_table}/{filename}"
