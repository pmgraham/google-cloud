# Topic A: Agent -> Loader
resource "google_pubsub_topic" "file_load_requests" {
  name    = "file-load-requests"
  project = google_project.pipeline.project_id

  message_retention_duration = "86400s" # 24 hours

  depends_on = [google_project_service.required_apis]
}

# Topic B: Agent -> Logger, Loader -> Logger
resource "google_pubsub_topic" "pipeline_events" {
  name    = "pipeline-events"
  project = google_project.pipeline.project_id

  message_retention_duration = "86400s"

  depends_on = [google_project_service.required_apis]
}

# Dead letter topic for failed loader messages
resource "google_pubsub_topic" "file_load_dead_letter" {
  name    = "file-load-dead-letter"
  project = google_project.pipeline.project_id

  message_retention_duration = "604800s" # 7 days

  depends_on = [google_project_service.required_apis]
}

# Loader subscription (push to Cloud Run loader)
resource "google_pubsub_subscription" "loader_subscription" {
  name    = "file-loader-sub"
  project = google_project.pipeline.project_id
  topic   = google_pubsub_topic.file_load_requests.id

  push_config {
    push_endpoint = google_cloud_run_v2_service.file_loader.uri

    oidc_token {
      service_account_email = google_service_account.eventarc_trigger.email
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.file_load_dead_letter.id
    max_delivery_attempts = 5
  }

  ack_deadline_seconds = 300
}

# Logger subscription (push to Cloud Run logger)
resource "google_pubsub_subscription" "logger_subscription" {
  name    = "pipeline-logger-sub"
  project = google_project.pipeline.project_id
  topic   = google_pubsub_topic.pipeline_events.id

  push_config {
    push_endpoint = google_cloud_run_v2_service.pipeline_logger.uri

    oidc_token {
      service_account_email = google_service_account.eventarc_trigger.email
    }
  }

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "300s"
  }

  ack_deadline_seconds = 60
}

# Grant Pub/Sub permission to publish to dead letter topic
resource "google_pubsub_topic_iam_member" "dead_letter_publisher" {
  project = google_project.pipeline.project_id
  topic   = google_pubsub_topic.file_load_dead_letter.id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Grant Pub/Sub permission to acknowledge messages from the loader subscription
resource "google_pubsub_subscription_iam_member" "dead_letter_subscriber" {
  project      = google_project.pipeline.project_id
  subscription = google_pubsub_subscription.loader_subscription.id
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

data "google_project" "current" {
  project_id = google_project.pipeline.project_id
}
