resource "google_firestore_database" "pipeline_state" {
  provider    = google-beta
  project     = google_project.pipeline.project_id
  name        = var.firestore_database_name
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.required_apis]
}

# Composite index: file_registry — status + updated_at
resource "google_firestore_index" "file_registry_status_updated" {
  provider   = google-beta
  project    = google_project.pipeline.project_id
  database   = google_firestore_database.pipeline_state.name
  collection = "file_registry"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "updated_at"
    order      = "DESCENDING"
  }
}

# Composite index: file_registry — target_table + created_at
resource "google_firestore_index" "file_registry_table_created" {
  provider   = google-beta
  project    = google_project.pipeline.project_id
  database   = google_firestore_database.pipeline_state.name
  collection = "file_registry"

  fields {
    field_path = "target_table"
    order      = "ASCENDING"
  }

  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
}

# Composite index: table_routing — last_loaded_at + enabled
resource "google_firestore_index" "table_routing_loaded_enabled" {
  provider   = google-beta
  project    = google_project.pipeline.project_id
  database   = google_firestore_database.pipeline_state.name
  collection = "table_routing"

  fields {
    field_path = "last_loaded_at"
    order      = "DESCENDING"
  }

  fields {
    field_path = "enabled"
    order      = "ASCENDING"
  }
}
