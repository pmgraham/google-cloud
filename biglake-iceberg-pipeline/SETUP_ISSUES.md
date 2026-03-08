# Setup Issues Log (Corrected but still things to watch out for if errors occur)

This document tracks issues encountered during the setup of the BigLake Iceberg Pipeline project.

## Issues

### 1. Missing Configuration Values
- **Date**: 2026-02-16
- **Description**: `pipeline.env` and `terraform/terraform.tfvars` were missing. Created from examples, but they contain placeholders.
- **Action Required**: User must provide GCP Project ID, Billing Account ID, and optionally Org/Folder ID.

### 2. Terraform Backend
- **Date**: 2026-02-16
- **Description**: `terraform/main.tf` contained an unconfigured `backend "gcs"` block, causing `terraform init` to fail.
- **Action Taken**: Commented out the backend block to use local state for initial setup.

### 3. Project ID Conflict
- **Date**: 2026-02-16
- **Description**: The Project ID `biglake-iceberg-datalake` specified in `.env` is globally unique and already taken by another user.
- **Action Required**: User must provide a globally unique Project ID.

### 4. Eventarc Service Agent Permission
- **Date**: 2026-02-16
- **Description**: `terraform apply` failed with "Permission denied while using the Eventarc Service Agent". This is a known issue where the service agent needs time to propagate.
- **Action Taken**: Retried `terraform apply` after a delay.

### 5. Deployment Permission Error
- **Date**: 2026-02-16
- **Description**: `deploy.sh` failed with `Error 403: ...-compute@developer.gserviceaccount.com does not have storage.objects.get access`. The default Compute Engine SA needs read access to the source code bucket used by Cloud Build.
- **Action Taken**: Granted `roles/storage.objectViewer` to the Compute Engine default service account.

### 6. Invalid Dependency Versions
- **Date**: 2026-02-16
- **Description**: Cloud Run deployment failed. `services/loader/requirements.txt` and `services/logger/requirements.txt` requested `gunicorn==23.*`, but the current latest version is 23.0.0 (Wait, checking... no, it is likely lower, typically 22.x or 21.x. 23.0.0 does not exist yet).
- **Action Required**: Migrate to `uv` and correct dependency versions.

### 7. Organizational Permission Restrictions
- **Date**: 2026-02-16
- **Description**: Cloud Run deployments via `gcloud run deploy --source` (which uses Cloud Build) failed consistently due to restricted default permissions in the Altostrat organization environment.
- **Root Cause**: The default Compute Engine service account (used as the Cloud Build service agent) was missing critical roles that are often present by default in personal projects:
    - `roles/logging.logWriter`: Prevented build logs from being visible.
    - `roles/artifactregistry.writer`: Prevented pushing built images to Artifact Registry.
    - `roles/run.admin`: Prevented creating/updating Cloud Run services.
    - `roles/iam.serviceAccountUser`: Prevented Cloud Build from acting as the service identities for the deployed services.
- **Action Taken**: Manually granted the above roles to the Compute Engine default service account (`673514950316-compute@developer.gserviceaccount.com`) using `gcloud projects add-iam-policy-binding`.

### 8. Local Environment Python & UV
- **Date**: 2026-02-16
- **Description**: `seed.py` failed to run with `python` (missing from PATH) and required manual virtual env setup.
- **Action Taken**: Replaced `python` commands with `python3` and used `uv venv` to manage the local environment for data seeding.

### 9. File Loader Non-Idempotency
- **Date**: 2026-02-16
- **Description**: The `file-loader` service reported failure when Pub/Sub redelivered a message for a successfully processed file.
- **Root Cause**: The service successfully loaded data, archived the source, and deleted the staging parquet on the first attempt. On retry, it failed to find the source files and emitted a `LOADER_BIGQUERY_FAILED` event, overwriting the earlier success status in Firestore.
- **Action Taken**: Implemented an idempotency check in `file-loader` to verify if a file is already archived/deleted before attempting another load.
