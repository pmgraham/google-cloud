# --- Inbox Bucket (raw file uploads — Eventarc watches this bucket) ---

resource "google_storage_bucket" "inbox" {
  name     = var.inbox_bucket_name
  location = var.region
  project  = google_project.pipeline.project_id

  uniform_bucket_level_access = true
  force_destroy               = true

  depends_on = [google_project_service.required_apis]
}

# --- Staging Bucket (agent parquet output + reports — auto-delete after 1 day) ---

resource "google_storage_bucket" "staging" {
  name     = var.staging_bucket_name
  location = var.region
  project  = google_project.pipeline.project_id

  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required_apis]
}

# --- Iceberg Bucket (BigQuery Iceberg table data) ---

resource "google_storage_bucket" "iceberg" {
  name     = var.iceberg_bucket_name
  location = var.region
  project  = google_project.pipeline.project_id

  uniform_bucket_level_access = true
  force_destroy               = true
  versioning {
    enabled = true
  }

  depends_on = [google_project_service.required_apis]
}

# --- Archive Bucket (original files after processing) ---

resource "google_storage_bucket" "archive" {
  name     = var.archive_bucket_name
  location = var.region
  project  = google_project.pipeline.project_id

  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  depends_on = [google_project_service.required_apis]
}
