output "project_id" {
  description = "GCP project ID (Terraform-managed)"
  value       = google_project.pipeline.project_id
}

output "region" {
  description = "GCP region for compute resources"
  value       = var.region
}

output "inbox_bucket_name" {
  description = "Inbox GCS bucket name (Eventarc trigger)"
  value       = google_storage_bucket.inbox.name
}

output "staging_bucket_name" {
  description = "Staging GCS bucket name (agent parquet output)"
  value       = google_storage_bucket.staging.name
}

output "iceberg_bucket_name" {
  description = "Iceberg GCS bucket name (BigQuery Iceberg table data)"
  value       = google_storage_bucket.iceberg.name
}

output "archive_bucket_name" {
  description = "Archive GCS bucket name (processed originals)"
  value       = google_storage_bucket.archive.name
}

output "agent_url" {
  description = "Data agent Cloud Run service URL"
  value       = google_cloud_run_v2_service.data_agent.uri
}

output "loader_url" {
  description = "File loader Cloud Run service URL"
  value       = google_cloud_run_v2_service.file_loader.uri
}

output "logger_url" {
  description = "Pipeline logger Cloud Run service URL"
  value       = google_cloud_run_v2_service.pipeline_logger.uri
}

output "biglake_catalog" {
  description = "BigLake Metastore catalog name"
  value       = google_biglake_catalog.pipeline.name
}

output "biglake_connection_id" {
  description = "BigQuery connection ID for BigLake Iceberg"
  value       = google_bigquery_connection.biglake_iceberg.connection_id
}

output "agent_service_account" {
  description = "Data agent service account email"
  value       = google_service_account.data_agent.email
}

output "loader_service_account" {
  description = "File loader service account email"
  value       = google_service_account.file_loader.email
}

output "logger_service_account" {
  description = "Pipeline logger service account email"
  value       = google_service_account.pipeline_logger.email
}


output "vertex_ai_connection_id" {
  description = "BigQuery remote connection ID for Vertex AI"
  value       = google_bigquery_connection.vertex_ai.connection_id
}
