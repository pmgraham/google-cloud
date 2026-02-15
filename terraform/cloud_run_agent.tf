# Source: services/data-cleaning-agent/
# Deploy: gcloud run deploy data-agent --source services/data-cleaning-agent/ --region $REGION --project $PROJECT
resource "google_cloud_run_v2_service" "data_agent" {
  name     = "data-agent"
  location = var.region
  project  = google_project.pipeline.project_id

  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.data_agent.email

    scaling {
      min_instance_count = 0
      max_instance_count = var.agent_max_instances
    }

    max_instance_request_concurrency = 1
    timeout                          = "${var.agent_timeout}s"

    vpc_access {
      network_interfaces {
        network    = google_compute_network.pipeline.id
        subnetwork = google_compute_subnetwork.us_central1.id
      }
      egress = "ALL_TRAFFIC"
    }

    containers {
      image = var.agent_image

      resources {
        limits = {
          memory = var.agent_memory
          cpu    = var.agent_cpu
        }
      }

      env {
        name  = "GCP_PROJECT"
        value = google_project.pipeline.project_id
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
        name  = "LOAD_TOPIC"
        value = google_pubsub_topic.file_load_requests.name
      }
      env {
        name  = "EVENT_TOPIC"
        value = google_pubsub_topic.pipeline_events.name
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = google_project.pipeline.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
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
