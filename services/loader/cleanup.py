import logging

from google.cloud import storage

from config import Config

logger = logging.getLogger(__name__)

_client = storage.Client(project=Config.GCP_PROJECT)
_inbox_bucket = _client.bucket(Config.INBOX_BUCKET)
_staging_bucket = _client.bucket(Config.STAGING_BUCKET)
_archive_bucket = _client.bucket(Config.ARCHIVE_BUCKET)


def archive_original(source_uri: str, target_table: str) -> str:
    """Move original file from inbox bucket to archive bucket.
    
    Returns the archive URI. If the file is already archived, returns the expected
    archive URI without erroring.
    """
    source_path = source_uri.replace(f"gs://{Config.INBOX_BUCKET}/", "")
    filename = source_path.split("/")[-1]
    archive_path = f"{target_table}/{filename}"
    archive_uri = f"gs://{Config.ARCHIVE_BUCKET}/{archive_path}"

    source_blob = _inbox_bucket.blob(source_path)
    if not source_blob.exists():
        logger.info("Source file already moved or missing: %s", source_uri)
        return archive_uri

    _inbox_bucket.copy_blob(source_blob, _archive_bucket, archive_path)
    source_blob.delete()

    logger.info("Archived %s → %s", source_uri, archive_uri)
    return archive_uri


def delete_staging_parquet(parquet_uri: str):
    """Delete staging parquet. Ignores if already deleted."""
    parquet_path = parquet_uri.replace(f"gs://{Config.STAGING_BUCKET}/", "")
    blob = _staging_bucket.blob(parquet_path)
    if blob.exists():
        blob.delete()
        logger.info("Deleted staging parquet: %s", parquet_uri)
    else:
        logger.info("Staging parquet already deleted: %s", parquet_uri)


def get_archive_uri(source_uri: str, target_table: str) -> str:
    source_path = source_uri.replace(f"gs://{Config.INBOX_BUCKET}/", "")
    filename = source_path.split("/")[-1]
    return f"gs://{Config.ARCHIVE_BUCKET}/{target_table}/{filename}"


def is_already_processed(parquet_uri: str, source_uri: str, target_table: str) -> bool:
    """Check if the staging parquet is gone and the original is already archived."""
    parquet_path = parquet_uri.replace(f"gs://{Config.STAGING_BUCKET}/", "")
    source_path = source_uri.replace(f"gs://{Config.INBOX_BUCKET}/", "")
    
    parquet_blob = _staging_bucket.blob(parquet_path)
    source_blob = _inbox_bucket.blob(source_path)
    
    # If parquet is gone AND source is gone from inbox, assume it's done
    if not parquet_blob.exists() and not source_blob.exists():
        archive_uri = get_archive_uri(source_uri, target_table)
        archive_blob = _archive_bucket.blob(archive_uri.replace(f"gs://{Config.ARCHIVE_BUCKET}/", ""))
        if archive_blob.exists():
            return True
            
    return False
