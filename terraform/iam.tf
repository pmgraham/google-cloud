# --- Service Accounts ---

resource "google_service_account" "data_agent" {
  account_id   = "data-agent"
  display_name = "Data Agent"
  description  = "Service account for the data agent Cloud Run service"
  project      = google_project.pipeline.project_id
}

resource "google_service_account" "file_loader" {
  account_id   = "file-loader"
  display_name = "File Loader"
  description  = "Service account for the file loader Cloud Run function"
  project      = google_project.pipeline.project_id
}

resource "google_service_account" "pipeline_logger" {
  account_id   = "pipeline-logger"
  display_name = "Pipeline Logger"
  description  = "Service account for the pipeline logger Cloud Run function"
  project      = google_project.pipeline.project_id
}

resource "google_service_account" "eventarc_trigger" {
  account_id   = "eventarc-trigger"
  display_name = "Eventarc Trigger"
  description  = "Service account for Eventarc triggers and Pub/Sub push auth"
  project      = google_project.pipeline.project_id
}

# --- Data Agent Roles ---

resource "google_project_iam_member" "agent_storage" {
  project = google_project.pipeline.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.data_agent.email}"
}

resource "google_project_iam_member" "agent_pubsub" {
  project = google_project.pipeline.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.data_agent.email}"
}

resource "google_project_iam_member" "agent_firestore" {
  project = google_project.pipeline.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.data_agent.email}"
}

resource "google_project_iam_member" "agent_vertex_ai" {
  project = google_project.pipeline.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.data_agent.email}"
}

# --- File Loader Roles ---

resource "google_project_iam_member" "loader_storage" {
  project = google_project.pipeline.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.file_loader.email}"
}

resource "google_project_iam_member" "loader_pubsub" {
  project = google_project.pipeline.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.file_loader.email}"
}

resource "google_project_iam_member" "loader_bigquery" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.file_loader.email}"
}

resource "google_project_iam_member" "loader_bigquery_job_user" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.file_loader.email}"
}

resource "google_project_iam_member" "loader_biglake" {
  project = google_project.pipeline.project_id
  role    = "roles/biglake.admin"
  member  = "serviceAccount:${google_service_account.file_loader.email}"
}

resource "google_project_iam_member" "loader_bigquery_connection_admin" {
  project = google_project.pipeline.project_id
  role    = "roles/bigquery.connectionAdmin"
  member  = "serviceAccount:${google_service_account.file_loader.email}"
}

resource "google_project_iam_member" "loader_dataplex" {
  project = google_project.pipeline.project_id
  role    = "roles/dataplex.developer"
  member  = "serviceAccount:${google_service_account.file_loader.email}"
}

# --- Pipeline Logger Roles ---

resource "google_project_iam_member" "logger_firestore" {
  project = google_project.pipeline.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.pipeline_logger.email}"
}

# --- Eventarc Trigger Roles ---

resource "google_project_iam_member" "eventarc_run_invoker" {
  project = google_project.pipeline.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.eventarc_trigger.email}"
}

resource "google_project_iam_member" "eventarc_receiver" {
  project = google_project.pipeline.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.eventarc_trigger.email}"
}

# --- GCS Service Agent (required for Eventarc GCS triggers) ---

# Get current project data to access project number
data "google_project" "current" {
  project_id = google_project.pipeline.project_id
}

# The GCS service agent (service-PROJECT_NUM@gs-project-accounts) is lazily
# provisioned. On a brand-new project it may not exist yet when Terraform
# tries to grant it IAM roles. We force its creation by provisioning the
# storage service identity first, then add a delay for propagation.

resource "google_project_service_identity" "gcs_agent" {
  provider = google-beta
  project  = google_project.pipeline.project_id
  service  = "storage.googleapis.com"

  depends_on = [google_project_service.required_apis]
}

resource "time_sleep" "wait_for_gcs_agent" {
  create_duration = "30s"

  depends_on = [
    google_project_service_identity.gcs_agent,
    google_storage_bucket.inbox,
    google_storage_bucket.staging,
    google_storage_bucket.iceberg,
    google_storage_bucket.archive,
  ]
}

resource "google_project_iam_member" "gcs_pubsub_publisher" {
  project = google_project.pipeline.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"

  depends_on = [time_sleep.wait_for_gcs_agent]
}

# --- Deployment Roles (required for Org environments) ---
# When using 'gcloud run deploy --source', Cloud Build uses the Compute Engine 
# default service account by default. In many organizations, these SAs are 
# stripped of their default broad permissions.

locals {
  deploy_roles = [
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/storage.objectViewer",
  ]
}

resource "google_project_iam_member" "compute_sa_deploy_roles" {
  for_each = toset(local.deploy_roles)
  project  = google_project.pipeline.project_id
  role     = each.value
  member   = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"

  depends_on = [google_project_service.required_apis]
}
