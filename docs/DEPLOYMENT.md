# Deployment Guide

This guide covers deployment procedures for the Data Insights Agent in local development and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Google Cloud Platform Deployment](#google-cloud-platform-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Health Checks and Monitoring](#health-checks-and-monitoring)
7. [Scaling and Performance](#scaling-and-performance)

---

## Prerequisites

### Required Software

**Local Development**:
- Python 3.11+ ([Download](https://www.python.org/downloads/))
- Node.js 20+ ([Download](https://nodejs.org/))
- npm or yarn package manager
- Git

**Docker Deployment**:
- Docker 24.0+ ([Install](https://docs.docker.com/get-docker/))
- Docker Compose 2.0+ (included with Docker Desktop)

**GCP Deployment**:
- Google Cloud SDK (gcloud CLI) ([Install](https://cloud.google.com/sdk/docs/install))
- Docker (for building container images)
- Active GCP project with billing enabled

### Required GCP Services

Enable the following APIs in your GCP project:

```bash
gcloud services enable \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com
```

### Authentication

**Application Default Credentials (ADC)**:

For local development and Docker, authenticate with:

```bash
gcloud auth application-default login
```

This creates credentials at `~/.config/gcloud/application_default_credentials.json` that are mounted into the Docker container.

**Service Accounts** (for production):

Create a service account with appropriate permissions:

```bash
gcloud iam service-accounts create data-insights-agent \
  --display-name="Data Insights Agent" \
  --description="Service account for Data Insights Agent application"
```

Grant required roles (see [IAM Configuration](#iam-configuration)).

---

## Local Development Setup

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env

# Edit .env with your configuration
nano .env  # Or use your preferred editor
```

**Required `.env` variables**:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
BIGQUERY_DATASET=your-dataset-name
GOOGLE_CLOUD_REGION=global
PORT=8088
DEBUG=true
```

**Run the backend**:
```bash
python run.py
```

Backend will be available at `http://localhost:8088`.

**Verify**:
```bash
curl http://localhost:8088/api/health
# Expected: {"status":"healthy","version":"1.0.0",...}
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file (if needed for custom API URL)
echo "VITE_API_URL=http://localhost:8088/api" > .env

# Run development server
npm run dev
```

Frontend will be available at `http://localhost:5173`.

---

## Docker Compose Deployment

Docker Compose orchestrates both backend and frontend services with proper networking and health checks.

### Quick Start

**1. Set environment variables**:

Create a `.env` file in the project root:

```bash
# Required GCP Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
BIGQUERY_DATASET=your-dataset-name
GOOGLE_CLOUD_REGION=global

# Optional: Override default credentials path
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
```

**2. Build and start services**:

```bash
docker-compose up --build
```

This will:
- Build backend and frontend Docker images
- Start both services with health checks
- Expose backend on port `8000` and frontend on port `80`
- Mount GCP credentials into the backend container

**3. Verify deployment**:

```bash
# Check health
curl http://localhost:8000/api/health

# Access frontend
open http://localhost
```

### Docker Compose Architecture

```yaml
services:
  backend:
    - Runs FastAPI application on port 8000
    - Mounts GCP credentials from host
    - Health check: GET /api/health every 30s
    - Restarts automatically on failure

  frontend:
    - Builds React app and serves with nginx on port 80
    - Depends on backend health check before starting
    - Health check: wget / every 30s
    - Restarts automatically on failure
```

### Environment Variables in Docker Compose

The `docker-compose.yml` passes environment variables to the backend:

```yaml
environment:
  - GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
  - GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_REGION:-global}
  - BIGQUERY_DATASET=${BIGQUERY_DATASET}
  - HOST=0.0.0.0
  - PORT=8000
  - DEBUG=false
  - CORS_ORIGINS=http://localhost,http://localhost:80,http://frontend
```

**Note**: Frontend container is named `frontend`, allowing backend to accept CORS requests from `http://frontend`.

### Managing Docker Compose Services

**Start in detached mode**:
```bash
docker-compose up -d
```

**View logs**:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

**Stop services**:
```bash
docker-compose down
```

**Rebuild after code changes**:
```bash
docker-compose up --build
```

**Check service health**:
```bash
docker-compose ps
```

Example output:
```
NAME                       STATUS                    PORTS
data-insights-backend      Up 5 minutes (healthy)    0.0.0.0:8000->8000/tcp
data-insights-frontend     Up 5 minutes (healthy)    0.0.0.0:80->80/tcp
```

### Credential Mounting

The backend container mounts Google Cloud credentials from the host:

```yaml
volumes:
  - ${GOOGLE_APPLICATION_CREDENTIALS:-~/.config/gcloud/application_default_credentials.json}:/app/credentials.json:ro
```

**Credential Resolution**:
1. If `GOOGLE_APPLICATION_CREDENTIALS` env var is set, use that path
2. Otherwise, use default ADC path (`~/.config/gcloud/application_default_credentials.json`)
3. Mounted as **read-only** (`:ro`) for security

**Troubleshooting Credentials**:

If you see authentication errors:

```bash
# Verify credentials file exists
ls -l ~/.config/gcloud/application_default_credentials.json

# Re-authenticate if needed
gcloud auth application-default login

# Restart containers
docker-compose restart backend
```

---

## Google Cloud Platform Deployment

Deploy to GCP Cloud Run for production-grade, serverless hosting with auto-scaling.

### Architecture Overview

```
Internet → Cloud Load Balancer → Cloud Run (Backend) → BigQuery
                                       ↓
                                 Cloud Run (Frontend) → Nginx → Static Assets
```

**Benefits of Cloud Run**:
- ✅ Auto-scaling (0 to N instances based on traffic)
- ✅ Pay-per-use pricing (only when serving requests)
- ✅ Managed infrastructure (no server maintenance)
- ✅ Built-in HTTPS certificates
- ✅ Easy rollbacks and blue/green deployments

### Step 1: Configure GCP Project

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Set default region
gcloud config set run/region us-central1
```

### Step 2: Create Artifact Registry Repository

Store Docker images in Artifact Registry:

```bash
# Create repository
gcloud artifacts repositories create data-insights-repo \
  --repository-format=docker \
  --location=us-central1 \
  --description="Data Insights Agent container images"

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Step 3: Build and Push Backend Image

```bash
cd backend

# Build image
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/backend:latest .

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/backend:latest
```

### Step 4: Build and Push Frontend Image

```bash
cd frontend

# Build image
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/frontend:latest .

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/frontend:latest
```

### Step 5: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create data-insights-sa \
  --display-name="Data Insights Agent Service Account"

# Store service account email
export SA_EMAIL="data-insights-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

### Step 6: Grant IAM Permissions

Grant required permissions for BigQuery and Vertex AI:

```bash
# BigQuery Data Viewer (read access to datasets)
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataViewer"

# BigQuery Job User (run queries)
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.jobUser"

# Vertex AI User (access Gemini models)
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user"

# Secret Manager Secret Accessor (read secrets)
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 7: Store Secrets in Secret Manager (Optional)

For sensitive configuration, use Secret Manager instead of environment variables:

```bash
# Create secrets
echo -n "your-project-id" | gcloud secrets create google-cloud-project --data-file=-
echo -n "your-dataset" | gcloud secrets create bigquery-dataset --data-file=-

# Grant access to service account (already done in Step 6)
```

### Step 8: Deploy Backend to Cloud Run

```bash
gcloud run deploy data-insights-backend \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/backend:latest \
  --service-account=$SA_EMAIL \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --port=8000 \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,BIGQUERY_DATASET=YOUR_DATASET,GOOGLE_CLOUD_REGION=global,HOST=0.0.0.0,PORT=8000,DEBUG=false" \
  --set-env-vars="CORS_ORIGINS=https://YOUR_FRONTEND_URL"
```

**Alternative: Using Secret Manager for environment variables**:

```bash
gcloud run deploy data-insights-backend \
  --image=... \
  --service-account=$SA_EMAIL \
  ... \
  --set-secrets="GOOGLE_CLOUD_PROJECT=google-cloud-project:latest" \
  --set-secrets="BIGQUERY_DATASET=bigquery-dataset:latest" \
  --set-env-vars="GOOGLE_CLOUD_REGION=global,HOST=0.0.0.0,PORT=8000,DEBUG=false"
```

**Deployment Output**:
```
Service [data-insights-backend] revision [data-insights-backend-00001-abc] has been deployed
and is serving 100 percent of traffic.
Service URL: https://data-insights-backend-xyz-uc.a.run.app
```

**Save the backend URL** for frontend configuration.

### Step 9: Deploy Frontend to Cloud Run

Update frontend environment to point to backend URL:

**Option A: Build-time configuration** (Recommended)

Edit `frontend/.env.production`:
```bash
VITE_API_URL=https://data-insights-backend-xyz-uc.a.run.app/api
```

Rebuild and push:
```bash
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/frontend:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/frontend:latest
```

Deploy:
```bash
gcloud run deploy data-insights-frontend \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/frontend:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --port=80 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=5
```

**Option B: Runtime configuration with nginx**

Configure nginx to proxy API requests to backend (requires custom nginx.conf).

### Step 10: Update Backend CORS

Update backend deployment with frontend URL:

```bash
gcloud run services update data-insights-backend \
  --region=us-central1 \
  --update-env-vars="CORS_ORIGINS=https://data-insights-frontend-xyz-uc.a.run.app"
```

### Step 11: Verify Deployment

```bash
# Test backend health
curl https://data-insights-backend-xyz-uc.a.run.app/api/health

# Test frontend (open in browser)
echo "Frontend: https://data-insights-frontend-xyz-uc.a.run.app"
```

### IAM Configuration

**Minimum Required Roles**:

| Role | Purpose | Scope |
|------|---------|-------|
| `roles/bigquery.dataViewer` | Read BigQuery tables | Project or Dataset |
| `roles/bigquery.jobUser` | Execute BigQuery queries | Project |
| `roles/aiplatform.user` | Access Vertex AI (Gemini models) | Project |
| `roles/secretmanager.secretAccessor` | Read secrets (if used) | Project or Secret |

**Optional Roles**:

| Role | Purpose |
|------|---------|
| `roles/logging.logWriter` | Write application logs to Cloud Logging |
| `roles/monitoring.metricWriter` | Write custom metrics to Cloud Monitoring |

**Verify Service Account Permissions**:

```bash
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:$SA_EMAIL"
```

### Custom Domain Setup (Optional)

Map a custom domain to Cloud Run services:

**1. Verify domain ownership**:
```bash
gcloud domains verify YOUR_DOMAIN.com
```

**2. Map domain to service**:
```bash
gcloud run domain-mappings create \
  --service=data-insights-frontend \
  --domain=app.YOUR_DOMAIN.com \
  --region=us-central1
```

**3. Update DNS records** as instructed by the command output.

**4. Update backend CORS**:
```bash
gcloud run services update data-insights-backend \
  --update-env-vars="CORS_ORIGINS=https://app.YOUR_DOMAIN.com"
```

---

## Environment Configuration

See [`CONFIGURATION.md`](./CONFIGURATION.md) for detailed environment variable reference.

**Quick Reference**:

### Backend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | ✅ Yes | - | GCP project ID |
| `BIGQUERY_DATASET` | ✅ Yes | - | BigQuery dataset name |
| `GOOGLE_CLOUD_REGION` | No | `us-central1` | Vertex AI region (use `global` for Gemini) |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server port |
| `DEBUG` | No | `false` | Enable debug mode |
| `CORS_ORIGINS` | No | `localhost:5173,localhost:3000` | Allowed CORS origins |

### Frontend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_URL` | No | `/api` | Backend API base URL |

---

## Health Checks and Monitoring

### Health Check Endpoints

**Backend**:
```bash
curl https://your-backend-url/api/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-02-06T23:00:00.000Z"
}
```

**Frontend**:
```bash
curl https://your-frontend-url/
```

Response: HTTP 200 with HTML content

### Cloud Run Health Checks

Cloud Run automatically health checks based on:
- **Startup probe**: Container must respond to HTTP requests within startup timeout
- **Liveness probe**: Container must continue responding to requests
- **Default path**: `/` (root path)

**Custom health check** (backend already implements `/api/health`):

Update Cloud Run service to use custom path:
```bash
gcloud run services update data-insights-backend \
  --region=us-central1 \
  --health-check-path=/api/health
```

### Logging

**View Cloud Run logs**:

```bash
# Stream logs in real-time
gcloud run services logs tail data-insights-backend --region=us-central1

# Filter by severity
gcloud run services logs read data-insights-backend \
  --region=us-central1 \
  --filter="severity>=ERROR" \
  --limit=50
```

**Application logs** are automatically captured from stdout/stderr.

**Example log output**:
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Monitoring Metrics

**Cloud Run built-in metrics**:
- Request count
- Request latency
- Instance count
- CPU utilization
- Memory utilization
- Error rate

**View in Console**:
1. Navigate to Cloud Run → Select service
2. Click "Metrics" tab
3. View request count, latency, and instance metrics

**Alerts** (recommended for production):

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="High Error Rate - Backend" \
  --condition-display-name="Error rate > 5%" \
  --condition-threshold-value=5 \
  --condition-threshold-duration=300s \
  --condition-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="data-insights-backend" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class="5xx"'
```

---

## Scaling and Performance

### Cloud Run Scaling Configuration

**Auto-scaling parameters**:

```bash
gcloud run services update data-insights-backend \
  --region=us-central1 \
  --min-instances=1 \        # Keep 1 instance warm (avoid cold starts)
  --max-instances=100 \       # Scale up to 100 instances
  --concurrency=80 \          # 80 requests per instance
  --cpu=4 \                   # 4 vCPUs per instance
  --memory=4Gi                # 4GB RAM per instance
```

**Scaling Trade-offs**:

| Configuration | Cold Start | Cost | Responsiveness |
|---------------|------------|------|----------------|
| `min-instances=0` | Slow (2-5s) | Low | Variable |
| `min-instances=1` | Fast (<100ms) | Medium | Consistent |
| `min-instances=5` | Instant | High | Excellent |

**Recommendations**:
- **Development**: `min-instances=0` to minimize costs
- **Production**: `min-instances=1-2` for balance
- **High-traffic**: `min-instances=5+` with load balancing

### Performance Optimization

**Backend Optimizations**:

1. **Schema Caching**: Already implemented in `backend/agent/tools.py`
   - Cache never expires (manual clear via `clear_schema_cache()`)
   - Reduces BigQuery API calls

2. **Query Result Limits**: Add LIMIT clause to queries
   ```python
   # Automatically adds LIMIT 1000 in execute_query_with_metadata
   ```

3. **Connection Pooling**: BigQuery client reuses connections

**Frontend Optimizations**:

1. **Code Splitting**: Vite automatically splits code by route
2. **Asset Optimization**: Production build minifies JS/CSS
3. **Static Asset Caching**: Nginx caches assets with long TTL

**Database Optimizations**:

1. **BigQuery Partitioning**: Use partitioned tables for large datasets
2. **Clustering**: Cluster tables on frequently queried columns
3. **Query Caching**: BigQuery automatically caches recent query results

### Cost Optimization

**Cloud Run Pricing** (as of 2024):
- vCPU: $0.00002400 per vCPU-second
- Memory: $0.00000250 per GiB-second
- Requests: $0.40 per million requests
- Free tier: 2 million requests/month, 360,000 vCPU-seconds, 180,000 GiB-seconds

**Estimate Monthly Cost**:

Example: 100,000 requests/month, avg 2s response time, 2 vCPU, 2GB RAM:
```
vCPU:     100,000 * 2s * 2 vCPU * $0.000024 = $9.60
Memory:   100,000 * 2s * 2 GB * $0.0000025 = $1.00
Requests: 100,000 * $0.40/1M = $0.04
Total:    $10.64/month (minus free tier)
```

**Cost Reduction Tips**:
- Set `min-instances=0` for low-traffic services
- Use smaller instance sizes (1 vCPU, 512MB) when possible
- Enable request timeout to prevent runaway queries
- Use BigQuery slot reservations for predictable costs

---

## Troubleshooting

See [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) for detailed troubleshooting guide.

**Quick Fixes**:

**Container fails to start**:
```bash
# Check logs
docker-compose logs backend

# Common issues:
# - Missing environment variables → Check .env file
# - Port already in use → Change PORT in .env or docker-compose.yml
# - Credentials not mounted → Run `gcloud auth application-default login`
```

**Cloud Run deployment fails**:
```bash
# Check service status
gcloud run services describe data-insights-backend --region=us-central1

# Common issues:
# - Image not found → Verify image was pushed to Artifact Registry
# - Permission denied → Check service account IAM roles
# - Health check failing → Verify /api/health endpoint works locally
```

**API returns 500 errors**:
```bash
# Check Cloud Run logs
gcloud run services logs tail data-insights-backend --region=us-central1

# Common causes:
# - BigQuery authentication failure → Check service account permissions
# - Invalid dataset name → Verify BIGQUERY_DATASET env var
# - Model region mismatch → Use GOOGLE_CLOUD_REGION=global for Gemini
```

---

## Rollback and Disaster Recovery

### Rollback to Previous Revision

Cloud Run keeps previous revisions for easy rollback:

```bash
# List revisions
gcloud run revisions list --service=data-insights-backend --region=us-central1

# Rollback to specific revision
gcloud run services update-traffic data-insights-backend \
  --region=us-central1 \
  --to-revisions=data-insights-backend-00005=100
```

### Blue/Green Deployment

Deploy new version without switching traffic:

```bash
# Deploy new revision with --no-traffic
gcloud run deploy data-insights-backend \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/data-insights-repo/backend:v2 \
  --region=us-central1 \
  --no-traffic

# Test new revision (find URL in output)
curl https://data-insights-backend-00006-xyz.a.run.app/api/health

# Gradually shift traffic (50/50 split)
gcloud run services update-traffic data-insights-backend \
  --region=us-central1 \
  --to-revisions=data-insights-backend-00006=50,data-insights-backend-00005=50

# Full cutover
gcloud run services update-traffic data-insights-backend \
  --region=us-central1 \
  --to-latest
```

### Backup and Restore

**Session Data**: Currently in-memory (lost on restart)
- For production, implement persistent session storage (Redis, Firestore)

**Configuration**: Environment variables and secrets stored in Secret Manager
- Export secrets for backup:
```bash
gcloud secrets versions access latest --secret=google-cloud-project > backup/secrets.txt
```

---

## Security Best Practices

1. **Never commit secrets** to version control
   - Use `.env` files (gitignored)
   - Use Secret Manager for production

2. **Principle of least privilege**
   - Grant minimum required IAM roles
   - Use separate service accounts per environment

3. **Network security**
   - Use VPC connectors for private BigQuery datasets
   - Enable Cloud Armor for DDoS protection

4. **Authentication** (future enhancement)
   - Implement Identity-Aware Proxy (IAP) for Cloud Run
   - Add user authentication (OAuth, JWT)

5. **Secrets rotation**
   - Rotate service account keys quarterly
   - Use Secret Manager auto-rotation for sensitive values

---

## Next Steps

After deployment:

1. **Configure monitoring and alerts** ([Monitoring Metrics](#monitoring-metrics))
2. **Set up custom domain** ([Custom Domain Setup](#custom-domain-setup-optional))
3. **Implement CI/CD pipeline** (GitHub Actions, Cloud Build)
4. **Configure backups** ([Backup and Restore](#backup-and-restore))
5. **Review security hardening** ([Security Best Practices](#security-best-practices))

---

*Last updated: February 2026*
