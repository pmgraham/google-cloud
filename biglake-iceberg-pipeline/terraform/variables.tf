variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "billing_account" {
  description = "GCP billing account ID"
  type        = string
}

variable "org_id" {
  description = "GCP organization ID (used if folder_id is not set)"
  type        = string
  default     = ""
}

variable "folder_id" {
  description = "GCP folder ID to create the project under (takes precedence over org_id)"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment label (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "GCP region for compute resources (Cloud Run, connections, etc.)"
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery dataset location (multi-region recommended, e.g. US or EU)"
  type        = string
  default     = "US"
}

variable "inbox_bucket_name" {
  description = "GCS bucket name for raw file uploads (Eventarc trigger watches this bucket)"
  type        = string
}

variable "staging_bucket_name" {
  description = "GCS bucket name for agent parquet output and reports (auto-deleted after 1 day)"
  type        = string
}

variable "iceberg_bucket_name" {
  description = "GCS bucket name for BigQuery Iceberg table data"
  type        = string
}

variable "archive_bucket_name" {
  description = "GCS bucket name for archived original files"
  type        = string
}

variable "iceberg_catalog_name" {
  description = "BigLake Metastore catalog name"
  type        = string
  default     = "data_pipeline_catalog"
}

variable "agent_image" {
  description = "Container image URI for the data-cleaning-agent Cloud Run service (deploy from services/data-cleaning-agent/)"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/placeholder"
}

variable "agent_memory" {
  description = "Memory allocation for the data agent"
  type        = string
  default     = "4Gi"
}

variable "agent_cpu" {
  description = "CPU allocation for the data agent"
  type        = string
  default     = "2"
}

variable "agent_timeout" {
  description = "Request timeout in seconds for the data agent"
  type        = number
  default     = 900
}

variable "agent_max_instances" {
  description = "Maximum number of data agent instances"
  type        = number
  default     = 10
}

variable "loader_memory" {
  description = "Memory allocation for the file loader"
  type        = string
  default     = "2Gi"
}

variable "logger_memory" {
  description = "Memory allocation for the pipeline logger"
  type        = string
  default     = "512Mi"
}

variable "biglake_connection_id" {
  description = "BigQuery connection ID for BigLake Iceberg tables"
  type        = string
  default     = "biglake-iceberg"
}

variable "vertex_ai_connection_id" {
  description = "BigQuery remote connection ID for Vertex AI model serving"
  type        = string
  default     = "vertex-ai-remote"
}

variable "spark_connection_id" {
  description = "BigQuery Spark connection ID for PySpark stored procedures"
  type        = string
  default     = "spark-proc"
}

variable "firestore_database_name" {
  description = "Firestore database name for pipeline state"
  type        = string
  default     = "pipeline-state"
}
