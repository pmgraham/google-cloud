# Configuration Guide

Complete reference for all environment variables and configuration settings for the Data Insights Agent.

## Table of Contents

1. [Backend Configuration](#backend-configuration)
2. [Frontend Configuration](#frontend-configuration)
3. [Docker Configuration](#docker-configuration)
4. [GCP Configuration](#gcp-configuration)
5. [Development vs Production](#development-vs-production)
6. [Configuration Validation](#configuration-validation)

---

## Backend Configuration

The backend uses Pydantic Settings for environment variable management with automatic validation and type checking.

### Configuration File Locations

**Priority Order** (highest to lowest):
1. System environment variables
2. `.env` file in `backend/` directory
3. Default values (defined in `backend/agent/config.py`)

### Environment Variables Reference

#### Google Cloud Platform

##### `GOOGLE_CLOUD_PROJECT` (Required)

**Description**: GCP project ID containing BigQuery datasets and Vertex AI resources

**Type**: String

**Required**: ✅ Yes

**Default**: None

**Examples**:
```bash
GOOGLE_CLOUD_PROJECT=my-analytics-project
GOOGLE_CLOUD_PROJECT=production-data-insights
```

**Usage**:
- BigQuery API calls (project context)
- Vertex AI model access (project billing)
- Application Default Credentials (ADC) authentication scope

**Validation**: Must be a valid GCP project ID (lowercase letters, numbers, hyphens)

**Troubleshooting**:
- Error: `Field required` → Set this variable in `.env` or environment
- Error: `Project not found` → Verify project exists and you have access
- Error: `Permission denied` → Check IAM permissions for the service account/user

---

##### `GOOGLE_CLOUD_REGION` (Optional)

**Description**: GCP region for Vertex AI API calls

**Type**: String

**Required**: No

**Default**: `us-central1`

**Recommended**: `global` (for `gemini-2.0-flash-preview` model availability)

**Examples**:
```bash
GOOGLE_CLOUD_REGION=global
GOOGLE_CLOUD_REGION=us-central1
GOOGLE_CLOUD_REGION=europe-west1
```

**Usage**:
- Vertex AI model endpoint selection
- Affects model availability and latency

**Important Notes**:
- **README suggests `global`** but code defaults to `us-central1`
- `gemini-2.0-flash-preview` is available in `global` region
- Region must support Gemini models (see [Vertex AI regions](https://cloud.google.com/vertex-ai/docs/general/locations))

**Troubleshooting**:
- Error: `Model not found` → Try changing to `global`
- Error: `Region not supported` → Check Vertex AI region availability

---

#### BigQuery

##### `BIGQUERY_DATASET` (Required)

**Description**: Default BigQuery dataset to query

**Type**: String

**Required**: ✅ Yes

**Default**: None

**Examples**:
```bash
BIGQUERY_DATASET=analytics
BIGQUERY_DATASET=public_data
BIGQUERY_DATASET=sales_data
```

**Usage**:
- Default dataset for all BigQuery queries
- Agent tools (` get_available_tables`, `get_table_schema`, etc.)
- SQL queries use fully qualified names: `{project}.{dataset}.{table}`

**Validation**: Must be a valid BigQuery dataset name (letters, numbers, underscores)

**Troubleshooting**:
- Error: `Dataset not found` → Verify dataset exists in your project
- Error: `Access denied` → Check BigQuery IAM permissions (`bigquery.dataViewer`, `bigquery.jobUser`)

---

#### Server

##### `HOST` (Optional)

**Description**: Server bind address

**Type**: String

**Required**: No

**Default**: `0.0.0.0`

**Examples**:
```bash
HOST=0.0.0.0      # All interfaces (Docker, production)
HOST=127.0.0.1    # Localhost only (local development)
HOST=localhost    # Localhost only (alternative)
```

**Usage**:
- Uvicorn server bind address
- Determines which network interfaces accept connections

**When to use each**:
- `0.0.0.0`: Docker containers, production (required for external access)
- `127.0.0.1`/`localhost`: Local development only (security)

**Troubleshooting**:
- Cannot access from Docker → Use `0.0.0.0`
- Security concern → Use `127.0.0.1` for local-only access

---

##### `PORT` (Optional)

**Description**: Server port for FastAPI application

**Type**: Integer

**Required**: No

**Default**: `8000`

**Common Values**:
```bash
PORT=8000    # Default
PORT=8088    # README examples use this
PORT=5000    # Alternative
```

**Usage**:
- Uvicorn server port
- API base URL: `http://localhost:{PORT}/api`

**Important Notes**:
- **README examples use `8088`** but code defaults to `8000`
- Set `PORT=8088` in `.env` to match README instructions
- Docker Compose maps `8000` → `8000` by default

**Troubleshooting**:
- Error: `Address already in use` → Change port or kill process using it
  ```bash
  # Find process using port 8088
  lsof -i :8088
  # Kill process
  kill -9 <PID>
  ```

---

##### `DEBUG` (Optional)

**Description**: Enable debug mode with auto-reload

**Type**: Boolean

**Required**: No

**Default**: `false`

**Examples**:
```bash
DEBUG=true     # Development
DEBUG=false    # Production
DEBUG=1        # Also works (truthy)
DEBUG=0        # Also works (falsy)
```

**Usage**:
- Uvicorn auto-reload on code changes
- Verbose logging
- Development features

**Effects When Enabled**:
- ✅ Auto-reload on file changes (convenient for development)
- ✅ Detailed error messages with stack traces
- ❌ Performance overhead (slower)
- ❌ Security risk (exposes internals)

**Recommendations**:
- **Development**: `DEBUG=true`
- **Production**: `DEBUG=false` (NEVER enable in production)

**Troubleshooting**:
- Server not reloading → Check `DEBUG=true` and save files
- Performance slow → Set `DEBUG=false`

---

#### CORS (Cross-Origin Resource Sharing)

##### `CORS_ORIGINS` (Optional)

**Description**: Comma-separated list of allowed CORS origins

**Type**: String (comma-separated)

**Required**: No

**Default**: `http://localhost:5173,http://localhost:3000`

**Examples**:
```bash
# Development (Vite + React dev servers)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Production (custom domain)
CORS_ORIGINS=https://myapp.com,https://www.myapp.com

# Docker Compose (frontend container name)
CORS_ORIGINS=http://localhost,http://localhost:80,http://frontend

# Multiple environments
CORS_ORIGINS=http://localhost:5173,https://staging.myapp.com,https://myapp.com
```

**Usage**:
- FastAPI CORS middleware configuration
- Determines which frontend domains can call the API
- Parsed into list via `settings.cors_origins_list` property

**Important Notes**:
- Wildcards (`*`) are NOT supported for security reasons
- Each origin must include protocol (`http://` or `https://`)
- Trailing slashes are optional
- Whitespace is automatically trimmed

**Troubleshooting**:
- Error: `CORS policy: No 'Access-Control-Allow-Origin' header` → Add frontend URL to CORS_ORIGINS
- Frontend can't connect → Verify protocol (http vs https) matches
- Docker network issues → Add container name (e.g., `http://frontend`)

---

### Backend `.env` Example

**Development** (`backend/.env`):
```bash
# Google Cloud Platform
GOOGLE_CLOUD_PROJECT=my-dev-project
GOOGLE_CLOUD_REGION=global
BIGQUERY_DATASET=dev_analytics

# Server
HOST=0.0.0.0
PORT=8088
DEBUG=true

# CORS (allow local dev servers)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Production** (Cloud Run environment variables):
```bash
# Google Cloud Platform
GOOGLE_CLOUD_PROJECT=my-prod-project
GOOGLE_CLOUD_REGION=global
BIGQUERY_DATASET=prod_analytics

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# CORS (production frontend URL)
CORS_ORIGINS=https://app.mycompany.com
```

---

## Frontend Configuration

The frontend uses Vite for build tooling with environment variable support.

### Environment Variable Prefix

Vite requires variables to be prefixed with `VITE_` to be exposed to client-side code.

### Environment Variables Reference

#### `VITE_API_URL` (Optional)

**Description**: Backend API base URL

**Type**: String (URL)

**Required**: No

**Default**: `/api` (relative path, assumes same origin)

**Examples**:
```bash
# Development (separate backend server)
VITE_API_URL=http://localhost:8088/api

# Production (Cloud Run backend)
VITE_API_URL=https://data-insights-backend-xyz.a.run.app/api

# Same origin (reverse proxy)
VITE_API_URL=/api
```

**Usage**:
- API client base URL (`frontend/src/services/api.ts`)
- All API requests prepended with this URL

**When to use each**:
- `/api`: Production with reverse proxy or same-origin deployment
- `http://localhost:8088/api`: Local development with separate backend
- `https://...`: Production with separate backend domain

**Troubleshooting**:
- Error: `Network Error` → Verify backend URL is accessible
- Error: `CORS policy` → Check backend `CORS_ORIGINS` setting
- 404 on API calls → Ensure `/api` path is included

---

### Frontend `.env` Files

Vite supports multiple `.env` files:

**Priority order** (highest to lowest):
1. `.env.local` (gitignored, local overrides)
2. `.env.production` (production build)
3. `.env.development` (development mode)
4. `.env` (all modes)

**Development** (`.env.development`):
```bash
VITE_API_URL=http://localhost:8088/api
```

**Production** (`.env.production`):
```bash
VITE_API_URL=https://data-insights-backend-xyz.a.run.app/api
```

**Local override** (`.env.local`, gitignored):
```bash
# Override for your local machine only
VITE_API_URL=http://192.168.1.100:8088/api
```

---

## Docker Configuration

### Docker Compose Environment Variables

**Root `.env` file** (used by `docker-compose.yml`):

```bash
# Google Cloud Platform
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=global
BIGQUERY_DATASET=your-dataset

# Optional: Override credential path
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
```

**Variable Substitution in docker-compose.yml**:

```yaml
environment:
  - GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
  - GOOGLE_CLOUD_REGION=${GOOGLE_CLOUD_REGION:-global}  # Default: global
  - BIGQUERY_DATASET=${BIGQUERY_DATASET}
```

Syntax:
- `${VAR}`: Required variable (fails if not set)
- `${VAR:-default}`: Optional with default value

### Credential Mounting

**`GOOGLE_APPLICATION_CREDENTIALS` (Optional)**:

```bash
# Default path (Linux/macOS)
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

# Custom path
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json

# Windows
GOOGLE_APPLICATION_CREDENTIALS=%APPDATA%/gcloud/application_default_credentials.json
```

**How it works**:
1. Docker Compose reads this variable from `.env`
2. Mounts the file into container at `/app/credentials.json`
3. Container sets `GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json`

**Troubleshooting**:
- Error: `No such file` → Run `gcloud auth application-default login`
- Error: `Permission denied` → Check file permissions (should be readable)
- Credentials not working → Verify file path is absolute

---

## GCP Configuration

### Cloud Run Environment Variables

Set via `gcloud run deploy` command:

```bash
gcloud run deploy data-insights-backend \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=your-project,BIGQUERY_DATASET=your-dataset,GOOGLE_CLOUD_REGION=global"
```

**Update existing deployment**:

```bash
gcloud run services update data-insights-backend \
  --region=us-central1 \
  --update-env-vars="DEBUG=false,PORT=8000"
```

### Secret Manager Integration

**Store sensitive values in Secret Manager**:

```bash
# Create secret
echo -n "your-secret-value" | gcloud secrets create my-secret --data-file=-

# Grant access to service account
gcloud secrets add-iam-policy-binding my-secret \
  --member="serviceAccount:your-sa@project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Mount in Cloud Run**:

```bash
gcloud run deploy data-insights-backend \
  --set-secrets="GOOGLE_CLOUD_PROJECT=google-cloud-project:latest" \
  --set-secrets="BIGQUERY_DATASET=bigquery-dataset:latest"
```

**Benefits**:
- ✅ Secrets not visible in environment variable list
- ✅ Automatic rotation support
- ✅ Audit logging of access
- ✅ Versioning (`:latest`, `:1`, `:2`, etc.)

---

## Development vs Production

### Development Configuration

**Goals**:
- Fast iteration (auto-reload, debug mode)
- Detailed logging
- Separate credentials (dev project)

**Backend** (`backend/.env`):
```bash
GOOGLE_CLOUD_PROJECT=dev-project
GOOGLE_CLOUD_REGION=global
BIGQUERY_DATASET=dev_data
PORT=8088
DEBUG=true
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Frontend** (`frontend/.env.development`):
```bash
VITE_API_URL=http://localhost:8088/api
```

**Run Commands**:
```bash
# Backend with auto-reload
cd backend && python run.py

# Frontend with HMR (Hot Module Replacement)
cd frontend && npm run dev
```

---

### Production Configuration

**Goals**:
- Security (no debug mode, minimal logging)
- Performance (optimized builds, caching)
- Scalability (proper CORS, health checks)

**Backend** (Cloud Run env vars):
```bash
GOOGLE_CLOUD_PROJECT=prod-project
GOOGLE_CLOUD_REGION=global
BIGQUERY_DATASET=prod_analytics
HOST=0.0.0.0
PORT=8000
DEBUG=false  # CRITICAL
CORS_ORIGINS=https://app.mycompany.com
```

**Frontend** (`.env.production`):
```bash
VITE_API_URL=https://data-insights-backend-xyz.a.run.app/api
```

**Build Commands**:
```bash
# Backend Docker build
docker build -t backend:prod ./backend

# Frontend production build
cd frontend && npm run build
```

**Production Checklist**:
- [ ] `DEBUG=false` (security)
- [ ] CORS set to production frontend URL only
- [ ] Secrets in Secret Manager (not env vars)
- [ ] Service account with least-privilege IAM roles
- [ ] Health checks enabled
- [ ] Monitoring and alerting configured

---

## Configuration Validation

### Backend Validation

The backend automatically validates configuration on startup via Pydantic:

**Validation Rules**:
- Required fields must be set (`GOOGLE_CLOUD_PROJECT`, `BIGQUERY_DATASET`)
- Types must match (e.g., `PORT` must be integer)
- Values must be non-empty strings

**Example Error**:
```
pydantic.error_wrappers.ValidationError: 2 validation errors for Settings
GOOGLE_CLOUD_PROJECT
  field required (type=value_error.missing)
BIGQUERY_DATASET
  field required (type=value_error.missing)
```

**Fix**: Add missing variables to `.env` file

**Test Configuration**:

```bash
cd backend

# Test configuration without starting server
python -c "from agent.config import settings; print(f'Project: {settings.google_cloud_project}')"
```

### Frontend Validation

Vite validates environment variables at build time:

**Test Configuration**:

```bash
cd frontend

# Check environment variables
npm run build -- --mode development

# Output shows loaded env vars:
# VITE_API_URL: http://localhost:8088/api
```

**Common Issues**:
- Variables not prefixed with `VITE_` are ignored
- Typos in variable names cause `undefined` values
- Different `.env` files for dev vs prod

---

## Configuration Management Best Practices

### Security

1. **Never commit `.env` files** to version control
   - Add to `.gitignore`
   - Use `.env.example` as template (with placeholder values)

2. **Use Secret Manager** for production
   - API keys, database passwords
   - GCP project IDs are OK in env vars (not sensitive)

3. **Rotate credentials regularly**
   - Service account keys: Quarterly
   - Secrets: Based on sensitivity

### Organization

1. **Use consistent naming** across environments
   - Prefix environment-specific values: `dev-project`, `prod-project`
   - Suffix datasets: `analytics_dev`, `analytics_prod`

2. **Document all variables**
   - Keep `.env.example` updated
   - Add comments explaining usage

3. **Separate credentials** per environment
   - Dev service account ≠ Prod service account
   - Different GCP projects recommended

### Validation

1. **Test configuration changes**
   - Backend: `python -c "from agent.config import settings; print(settings)"`
   - Frontend: `npm run build -- --mode development`

2. **Verify in deployment**
   - Cloud Run: Check "Variables & Secrets" tab in console
   - Docker: `docker-compose config` (shows resolved values)

---

## Quick Reference Tables

### Backend Required Variables

| Variable | Example | Where to Set |
|----------|---------|--------------|
| `GOOGLE_CLOUD_PROJECT` | `my-project-123` | `.env` or Cloud Run |
| `BIGQUERY_DATASET` | `analytics` | `.env` or Cloud Run |

### Backend Optional Variables

| Variable | Default | Recommended |
|----------|---------|-------------|
| `GOOGLE_CLOUD_REGION` | `us-central1` | `global` |
| `HOST` | `0.0.0.0` | Keep default |
| `PORT` | `8000` | `8088` (README) |
| `DEBUG` | `false` | `true` (dev), `false` (prod) |
| `CORS_ORIGINS` | `localhost:5173,localhost:3000` | Frontend URL |

### Frontend Variables

| Variable | Example | When to Set |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8088/api` | Different backend domain |

---

## Troubleshooting Configuration Issues

See [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) for detailed troubleshooting.

**Quick Diagnostics**:

```bash
# Backend: Print all settings
cd backend
python -c "from agent.config import settings; import json; print(json.dumps(settings.dict(), indent=2))"

# Docker Compose: Show resolved environment variables
docker-compose config

# Cloud Run: Get environment variables
gcloud run services describe data-insights-backend \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)"
```

---

*Last updated: February 2026*
