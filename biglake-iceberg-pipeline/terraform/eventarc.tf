resource "google_eventarc_trigger" "gcs_file_upload" {
  name     = "gcs-file-upload-trigger"
  location = var.region
  project  = google_project.pipeline.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.inbox.name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.data_agent.name
      region  = var.region
      path    = "/"
    }
  }

  service_account = google_service_account.eventarc_trigger.email

  depends_on = [
    google_project_service.required_apis,
    google_project_iam_member.eventarc_run_invoker,
    google_project_iam_member.eventarc_receiver,
    google_project_iam_member.gcs_pubsub_publisher,
  ]
}
