# --- VPC Network ---

resource "google_compute_network" "pipeline" {
  name                    = "pipeline-vpc"
  project                 = google_project.pipeline.project_id
  auto_create_subnetworks = false

  depends_on = [google_project_service.required_apis]
}

# --- Subnets ---

resource "google_compute_subnetwork" "us_central1" {
  name                     = "pipeline-us-central1"
  project                  = google_project.pipeline.project_id
  region                   = "us-central1"
  network                  = google_compute_network.pipeline.id
  ip_cidr_range            = "10.0.0.0/20"
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "us_east1" {
  name                     = "pipeline-us-east1"
  project                  = google_project.pipeline.project_id
  region                   = "us-east1"
  network                  = google_compute_network.pipeline.id
  ip_cidr_range            = "10.0.16.0/20"
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "us_west1" {
  name                     = "pipeline-us-west1"
  project                  = google_project.pipeline.project_id
  region                   = "us-west1"
  network                  = google_compute_network.pipeline.id
  ip_cidr_range            = "10.0.32.0/20"
  private_ip_google_access = true
}

# --- Cloud Router + NAT (for egress to internet if needed) ---

resource "google_compute_router" "pipeline" {
  name    = "pipeline-router"
  project = google_project.pipeline.project_id
  region  = var.region
  network = google_compute_network.pipeline.id
}

resource "google_compute_router_nat" "pipeline" {
  name                               = "pipeline-nat"
  project                            = google_project.pipeline.project_id
  region                             = var.region
  router                             = google_compute_router.pipeline.name
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# --- Private Service Connect for Google APIs ---

resource "google_compute_global_address" "google_apis" {
  name         = "google-apis-psc"
  project      = google_project.pipeline.project_id
  purpose      = "PRIVATE_SERVICE_CONNECT"
  address_type = "INTERNAL"
  network      = google_compute_network.pipeline.id
  address      = "10.0.48.1"
}

resource "google_compute_global_forwarding_rule" "google_apis" {
  name                  = "googleapispsc"
  project               = google_project.pipeline.project_id
  target                = "all-apis"
  network               = google_compute_network.pipeline.id
  ip_address            = google_compute_global_address.google_apis.id
  load_balancing_scheme = ""
}

# --- Firewall: allow internal traffic ---

resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal"
  project = google_project.pipeline.project_id
  network = google_compute_network.pipeline.id

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [
    "10.0.0.0/20",
    "10.0.16.0/20",
    "10.0.32.0/20",
  ]
}

# --- Firewall: deny all ingress from internet ---

resource "google_compute_firewall" "deny_ingress" {
  name     = "deny-all-ingress"
  project  = google_project.pipeline.project_id
  network  = google_compute_network.pipeline.id
  priority = 65534

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
}
