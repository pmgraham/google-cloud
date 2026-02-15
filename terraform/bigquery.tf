# --- Datasets ---

resource "google_bigquery_dataset" "bronze" {
  dataset_id    = "bronze"
  friendly_name = "Bronze"
  description   = "Iceberg tables via BigLake Metastore — agent-cleaned data"
  location      = var.bq_location
  project       = google_project.pipeline.project_id

  depends_on = [google_project_service.required_apis]
}

resource "google_bigquery_dataset" "silver" {
  dataset_id    = "silver"
  friendly_name = "Silver"
  description   = "Iceberg tables — conformed, typed, business logic applied"
  location      = var.bq_location
  project       = google_project.pipeline.project_id

  depends_on = [google_project_service.required_apis]
}

resource "google_bigquery_dataset" "gold" {
  dataset_id    = "gold"
  friendly_name = "Gold"
  description   = "Iceberg tables — aggregated, business-ready, modeled"
  location      = var.bq_location
  project       = google_project.pipeline.project_id

  depends_on = [google_project_service.required_apis]
}
