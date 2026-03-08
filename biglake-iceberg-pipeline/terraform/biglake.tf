# BigLake Metastore catalog
resource "google_biglake_catalog" "pipeline" {
  provider = google-beta
  name     = var.iceberg_catalog_name
  location = var.bq_location

  depends_on = [google_project_service.required_apis]
}

# BigQuery connection for BigLake Iceberg tables
resource "google_bigquery_connection" "biglake_iceberg" {
  provider      = google-beta
  connection_id = var.biglake_connection_id
  location      = var.bq_location
  project       = google_project.pipeline.project_id

  cloud_resource {}

  depends_on = [google_project_service.required_apis]
}

# Grant the connection's service account access to GCS
resource "google_project_iam_member" "biglake_connection_storage" {
  project = google_project.pipeline.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_bigquery_connection.biglake_iceberg.cloud_resource[0].service_account_id}"
}

# BigQuery remote connection for Vertex AI model serving
resource "google_bigquery_connection" "vertex_ai" {
  provider      = google-beta
  connection_id = var.vertex_ai_connection_id
  location      = var.bq_location
  project       = google_project.pipeline.project_id

  cloud_resource {}

  depends_on = [google_project_service.required_apis]
}

# Grant the Vertex AI connection's service account Vertex AI User role
resource "google_project_iam_member" "vertex_ai_connection_user" {
  project = google_project.pipeline.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_bigquery_connection.vertex_ai.cloud_resource[0].service_account_id}"
}

# BigQuery Spark connection for PySpark stored procedures
resource "google_bigquery_connection" "spark_proc" {
  provider      = google-beta
  connection_id = var.spark_connection_id
  location      = var.bq_location
  project       = google_project.pipeline.project_id

  spark {}

  depends_on = [google_project_service.required_apis]
}

# IAM bindings for the Spark connection's service account
resource "google_project_iam_member" "spark_proc_storage" {
  project = google_project.pipeline.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_bigquery_connection.spark_proc.spark[0].service_account_id}"
}

resource "google_project_iam_member" "spark_proc_bq_data_editor" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_bigquery_connection.spark_proc.spark[0].service_account_id}"
}

resource "google_project_iam_member" "spark_proc_bq_connection_user" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.connectionUser"
  member  = "serviceAccount:${google_bigquery_connection.spark_proc.spark[0].service_account_id}"
}

resource "google_project_iam_member" "spark_proc_bq_data_viewer" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_bigquery_connection.spark_proc.spark[0].service_account_id}"
}

resource "google_project_iam_member" "spark_proc_bq_job_user" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_bigquery_connection.spark_proc.spark[0].service_account_id}"
}

resource "google_project_iam_member" "spark_proc_bq_read_session" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.readSessionUser"
  member  = "serviceAccount:${google_bigquery_connection.spark_proc.spark[0].service_account_id}"
}

resource "google_project_iam_member" "spark_proc_biglake_admin" {
  project = google_project.pipeline.project_id
  role    = "roles/biglake.admin"
  member  = "serviceAccount:${google_bigquery_connection.spark_proc.spark[0].service_account_id}"
}
