resource "google_cloud_run_v2_service" "file_loader" {
  name     = "file-loader"
  location = var.region
  project  = google_project.pipeline.project_id

  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.file_loader.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    max_instance_request_concurrency = 1
    timeout                          = "300s"

    vpc_access {
      network_interfaces {
        network    = google_compute_network.pipeline.id
        subnetwork = google_compute_subnetwork.us_central1.id
      }
      egress = "ALL_TRAFFIC"
    }

    containers {
      # Placeholder — replaced by `gcloud run deploy --source`
      image = "us-docker.pkg.dev/cloudrun/container/placeholder"

      resources {
        limits = {
          memory = var.loader_memory
          cpu    = "1"
        }
      }

      env {
        name  = "GCP_PROJECT"
        value = google_project.pipeline.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.region
      }
      env {
        name  = "INBOX_BUCKET"
        value = google_storage_bucket.inbox.name
      }
      env {
        name  = "STAGING_BUCKET"
        value = google_storage_bucket.staging.name
      }
      env {
        name  = "ICEBERG_BUCKET"
        value = google_storage_bucket.iceberg.name
      }
      env {
        name  = "ARCHIVE_BUCKET"
        value = google_storage_bucket.archive.name
      }
      env {
        name  = "EVENT_TOPIC"
        value = google_pubsub_topic.pipeline_events.name
      }
      env {
        name  = "BIGLAKE_CONNECTION"
        value = google_bigquery_connection.biglake_iceberg.connection_id
      }
      env {
        name  = "ICEBERG_BASE_PATH"
        value = "gs://${google_storage_bucket.iceberg.name}"
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.required_apis]
}
