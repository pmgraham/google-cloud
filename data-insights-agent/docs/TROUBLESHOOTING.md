# Troubleshooting Guide

Common issues and solutions for the Data Insights Agent.

## Table of Contents

1. [Setup Errors](#setup-errors)
2. [Runtime Errors](#runtime-errors)
3. [Performance Issues](#performance-issues)
4. [Docker Issues](#docker-issues)
5. [Cloud Run Issues](#cloud-run-issues)
6. [API Errors](#api-errors)
7. [Frontend Issues](#frontend-issues)
8. [BigQuery Errors](#bigquery-errors)

---

## Setup Errors

### Backend Won't Start

#### Error: `Field required` (Pydantic ValidationError)

**Symptom**:
```
pydantic.error_wrappers.ValidationError: 2 validation errors for Settings
GOOGLE_CLOUD_PROJECT
  field required (type=value_error.missing)
BIGQUERY_DATASET
  field required (type=value_error.missing)
```

**Cause**: Missing required environment variables

**Solution**:
```bash
# Create .env file from example
cd backend
cp .env.example .env

# Edit with your values
nano .env
```

Add:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id
BIGQUERY_DATASET=your-dataset-name
```

**Verify**:
```bash
python -c "from agent.config import settings; print(f'Project: {settings.google_cloud_project}')"
```

---

#### Error: `Address already in use`

**Symptom**:
```
OSError: [Errno 48] Address already in use
```

**Cause**: Port 8088 (or configured PORT) is already in use by another process

**Solution 1 - Change port**:
```bash
# Edit .env
PORT=8089
```

**Solution 2 - Kill existing process**:
```bash
# Find process using port 8088
lsof -i :8088

# Kill the process
kill -9 <PID>

# Or use killall
killall -9 python
```

**Solution 3 - Use different port temporarily**:
```bash
PORT=9000 python run.py
```

---

#### Error: `google.auth.exceptions.DefaultCredentialsError`

**Symptom**:
```
google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials.
```

**Cause**: Google Cloud credentials not configured

**Solution**:
```bash
# Authenticate with Application Default Credentials
gcloud auth application-default login

# Verify credentials file exists
ls -l ~/.config/gcloud/application_default_credentials.json
```

**Alternative** (Service Account):
```bash
# Download service account key
gcloud iam service-accounts keys create key.json \
  --iam-account=your-sa@project.iam.gserviceaccount.com

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

**Verify**:
```bash
python -c "from google.auth import default; creds, project = default(); print(f'Authenticated as project: {project}')"
```

---

### Frontend Won't Start

#### Error: `ENOENT: no such file or directory, open 'package.json'`

**Symptom**:
```
Error: ENOENT: no such file or directory, open 'package.json'
```

**Cause**: Running npm commands from wrong directory

**Solution**:
```bash
cd frontend
npm install
npm run dev
```

---

#### Error: `npm ERR! Missing script: "dev"`

**Symptom**:
```
npm ERR! Missing script: "dev"
```

**Cause**: Dependencies not installed or corrupted `node_modules`

**Solution**:
```bash
# Delete node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
npm run dev
```

---

#### Error: Frontend builds but shows blank page

**Symptom**: Browser shows blank white page, no errors in terminal

**Cause**: API connection issue or routing problem

**Solution**:

1. **Check browser console** (F12):
   - Look for CORS errors
   - Check for 404 on API calls

2. **Verify API URL**:
   ```bash
   # Check .env.development
   cat frontend/.env.development
   # Should have: VITE_API_URL=http://localhost:8088/api
   ```

3. **Test backend is running**:
   ```bash
   curl http://localhost:8088/api/health
   ```

4. **Check CORS configuration**:
   ```bash
   # Backend .env should include frontend URL
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000
   ```

---

## Runtime Errors

### Session Loss

#### Issue: Sessions lost after server restart

**Symptom**: Users lose chat history when backend restarts

**Cause**: `InMemorySessionService` stores sessions in memory (not persistent)

**Explanation**: This is a known limitation documented in `ARCHITECTURE.md:367`

**Temporary Solution**: Don't restart the backend during active sessions

**Permanent Solution** (requires code changes):

1. **Option A: Redis-backed sessions**:
   - Install Redis: `pip install redis`
   - Implement `RedisSessionService`
   - Store sessions with TTL

2. **Option B: Firestore sessions**:
   - Use Firestore for persistent storage
   - Implement `FirestoreSessionService`
   - Query sessions by user ID

3. **Option C: PostgreSQL sessions**:
   - Store sessions in database table
   - Implement `DatabaseSessionService`

**Example Redis implementation**:
```python
# backend/services/redis_session_service.py
import redis
import json

class RedisSessionService:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379, db=0)

    def save_session(self, session_id, data):
        self.redis.setex(
            f"session:{session_id}",
            86400,  # 24 hour TTL
            json.dumps(data)
        )
```

---

### API Timeouts

#### Error: `TimeoutError` or `504 Gateway Timeout`

**Symptom**:
```
httpx.TimeoutException: Read timeout
```

**Cause**: BigQuery query taking too long

**Solution 1 - Increase timeout** (Cloud Run):
```bash
gcloud run services update data-insights-backend \
  --region=us-central1 \
  --timeout=600  # 10 minutes (max)
```

**Solution 2 - Optimize query**:
- Add LIMIT clause: `SELECT * FROM table LIMIT 1000`
- Use partitioned tables
- Add table clustering
- Review query plan in BigQuery console

**Solution 3 - Implement async processing**:
- Return immediately with query ID
- Poll for results
- Use Cloud Tasks for long-running queries

---

### Agent Not Responding

#### Issue: Agent returns empty response or "couldn't generate response"

**Symptom**:
```json
{
  "content": "I apologize, but I couldn't generate a response. Please try rephrasing your question."
}
```

**Cause**: Vertex AI model error or timeout

**Debugging Steps**:

1. **Check logs**:
   ```bash
   # Local
   tail -f backend/logs/app.log

   # Cloud Run
   gcloud run services logs tail data-insights-backend --region=us-central1
   ```

2. **Look for**:
   - `Model not found` → Check `GOOGLE_CLOUD_REGION=global`
   - `Quota exceeded` → Check Vertex AI quotas
   - `Permission denied` → Check service account has `aiplatform.user` role

3. **Test model access**:
   ```bash
   python -c "from google.genai import Client; client = Client(); print(client.models.generate_content('gemini-2.0-flash-preview', 'Hello'))"
   ```

**Solution**:
- Ensure `GOOGLE_CLOUD_REGION=global`
- Verify Vertex AI API is enabled
- Check service account IAM roles
- Check Vertex AI quotas in GCP Console

---

## Performance Issues

### Slow Query Execution

#### Issue: Queries take >10 seconds to return

**Cause**: Large dataset, missing indexes, or unoptimized query

**Diagnosis**:

1. **Check query time in response**:
   ```json
   {
     "query_result": {
       "query_time_ms": 25000,  // 25 seconds!
       ...
     }
   }
   ```

2. **View query plan** in BigQuery Console:
   - Open BigQuery in GCP Console
   - Go to "Job History"
   - Find your query
   - Click "Execution Details"

**Solutions**:

1. **Add LIMIT clause** (automatically added):
   ```sql
   SELECT * FROM large_table LIMIT 1000
   ```

2. **Use partitioning**:
   ```sql
   -- Create partitioned table
   CREATE TABLE dataset.partitioned_table
   PARTITION BY DATE(timestamp)
   AS SELECT * FROM dataset.source_table
   ```

3. **Add clustering**:
   ```sql
   CREATE TABLE dataset.clustered_table
   PARTITION BY DATE(timestamp)
   CLUSTER BY state, city
   AS SELECT * FROM dataset.source_table
   ```

4. **Filter early**:
   ```sql
   -- Good: Filter before GROUP BY
   SELECT state, COUNT(*) FROM sales
   WHERE date >= '2024-01-01'
   GROUP BY state

   -- Bad: Filter after GROUP BY
   SELECT state, cnt FROM (
     SELECT state, COUNT(*) as cnt FROM sales GROUP BY state
   ) WHERE date >= '2024-01-01'
   ```

---

### Frontend Rendering Lag

#### Issue: UI freezes when displaying large result sets

**Symptom**: Browser becomes unresponsive when showing 1000+ rows

**Cause**: Rendering all rows at once overwhelms the DOM

**Solution 1 - Pagination** (requires backend changes):
```typescript
// Add pagination to DataTable
const [page, setPage] = useState(0);
const rowsPerPage = 100;
const paginatedRows = rows.slice(page * rowsPerPage, (page + 1) * rowsPerPage);
```

**Solution 2 - Virtual scrolling** (use library):
```bash
npm install react-window
```

```typescript
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={rows.length}
  itemSize={50}
  width="100%"
>
  {({ index, style }) => (
    <div style={style}>{/* Render row */}</div>
  )}
</FixedSizeList>
```

**Solution 3 - Limit results**:
- Request user to narrow query scope
- Add default LIMIT in agent prompt

---

### Memory Issues (Docker)

#### Error: `Container killed (OOMKilled)`

**Symptom**:
```
data-insights-backend exited with code 137
```

**Cause**: Container ran out of memory

**Solution 1 - Increase Docker memory**:

Docker Desktop:
- Settings → Resources → Memory
- Increase to 4GB+ (default is often 2GB)

**Solution 2 - Limit query result size**:
```python
# backend/agent/tools.py
# Add stricter LIMIT
MAX_ROWS = 500  # Reduce from 1000
```

**Solution 3 - Add memory limit to docker-compose**:
```yaml
services:
  backend:
    mem_limit: 2g
    mem_reservation: 1g
```

---

## Docker Issues

### Container Won't Start

#### Error: `Cannot connect to the Docker daemon`

**Symptom**:
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock.
Is the docker daemon running?
```

**Solution**:
```bash
# macOS/Windows: Start Docker Desktop
open -a Docker  # macOS
# Windows: Start "Docker Desktop" from Start menu

# Linux: Start Docker service
sudo systemctl start docker

# Verify
docker ps
```

---

#### Error: `port is already allocated`

**Symptom**:
```
Error starting userland proxy: listen tcp4 0.0.0.0:8000: bind: address already in use
```

**Cause**: Another container or process using the port

**Solution 1 - Stop conflicting container**:
```bash
docker ps  # Find container using port
docker stop <container_id>
```

**Solution 2 - Change port mapping**:
```yaml
# docker-compose.yml
ports:
  - "8001:8000"  # Map to different host port
```

**Solution 3 - Kill process**:
```bash
# Find process
lsof -i :8000
# Kill it
kill -9 <PID>
```

---

### Credential Mounting Issues

#### Error: `No such file or directory` (credentials)

**Symptom**:
```
Error: open /app/credentials.json: no such file or directory
```

**Cause**: Credentials file not found at expected path

**Solution**:

1. **Verify credentials exist**:
   ```bash
   ls -l ~/.config/gcloud/application_default_credentials.json
   ```

2. **If missing, create them**:
   ```bash
   gcloud auth application-default login
   ```

3. **Check docker-compose.yml volume**:
   ```yaml
   volumes:
     - ${GOOGLE_APPLICATION_CREDENTIALS:-~/.config/gcloud/application_default_credentials.json}:/app/credentials.json:ro
   ```

4. **Set explicit path** (if needed):
   ```bash
   # In .env file
   GOOGLE_APPLICATION_CREDENTIALS=/full/path/to/credentials.json
   ```

5. **Rebuild containers**:
   ```bash
   docker-compose down
   docker-compose up --build
   ```

---

## Cloud Run Issues

### Deployment Failures

#### Error: `Image not found`

**Symptom**:
```
ERROR: Image 'us-central1-docker.pkg.dev/project/repo/backend:latest' not found
```

**Solution**:

1. **Verify image was pushed**:
   ```bash
   gcloud artifacts docker images list us-central1-docker.pkg.dev/PROJECT_ID/REPO_NAME
   ```

2. **If missing, build and push**:
   ```bash
   cd backend
   docker build -t us-central1-docker.pkg.dev/PROJECT_ID/REPO/backend:latest .
   docker push us-central1-docker.pkg.dev/PROJECT_ID/REPO/backend:latest
   ```

3. **Check repository exists**:
   ```bash
   gcloud artifacts repositories list --location=us-central1
   ```

---

#### Error: `Permission denied` (Service Account)

**Symptom**:
```
ERROR: (gcloud.run.deploy) User [service-account@project.iam.gserviceaccount.com] does not have permission to act as [service-account@project.iam.gserviceaccount.com]
```

**Solution**:

Grant `iam.serviceAccountUser` role:
```bash
gcloud iam service-accounts add-iam-policy-binding SERVICE_ACCOUNT_EMAIL \
  --member="user:YOUR_EMAIL" \
  --role="roles/iam.serviceAccountUser"
```

---

### Runtime Failures

#### Error: `Health check failed`

**Symptom**: Cloud Run service shows "Unhealthy" status

**Diagnosis**:
```bash
# Check logs for startup errors
gcloud run services logs tail data-insights-backend --region=us-central1
```

**Common Causes**:

1. **Port mismatch**:
   ```bash
   # Ensure PORT matches container EXPOSE
   --port=8000  # Must match Dockerfile EXPOSE
   ```

2. **Missing /api/health endpoint**:
   ```bash
   # Test locally first
   docker run -p 8000:8000 backend:latest
   curl http://localhost:8000/api/health
   ```

3. **Startup timeout**:
   ```bash
   # Increase startup timeout
   gcloud run services update data-insights-backend \
     --region=us-central1 \
     --timeout=300
   ```

---

## API Errors

### 422 Unprocessable Entity

**Symptom**:
```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Cause**: Request body doesn't match Pydantic model

**Solution**:

Check request payload matches schema:
```bash
# Correct
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me sales by state"}'

# Incorrect (missing message field)
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me sales"}'  # Wrong field name!
```

**Verify schema** in `/docs`:
```
http://localhost:8088/docs#/default/chat_api_chat_post
```

---

### 404 Not Found (Session)

**Symptom**:
```json
{
  "detail": "Session not found"
}
```

**Cause**: Invalid or expired session ID

**Solution**:

1. **Create new session**:
   ```bash
   curl -X POST http://localhost:8088/api/sessions \
     -H "Content-Type: application/json" \
     -d '{"name": "New Session"}'
   ```

2. **Use returned session_id**:
   ```bash
   SESSION_ID="session_xyz123"
   curl -X POST http://localhost:8088/api/chat \
     -H "Content-Type: application/json" \
     -d "{\"message\": \"Test\", \"session_id\": \"$SESSION_ID\"}"
   ```

3. **Or omit session_id** (creates new session):
   ```bash
   curl -X POST http://localhost:8088/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Test"}'
   ```

---

## Frontend Issues

### CORS Errors

**Symptom** (Browser console):
```
Access to fetch at 'http://localhost:8088/api/health' from origin 'http://localhost:5173'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present.
```

**Cause**: Backend CORS_ORIGINS doesn't include frontend URL

**Solution**:

1. **Update backend .env**:
   ```bash
   # backend/.env
   CORS_ORIGINS=http://localhost:5173,http://localhost:3000
   ```

2. **Restart backend**:
   ```bash
   cd backend
   python run.py
   ```

3. **For Cloud Run**:
   ```bash
   gcloud run services update data-insights-backend \
     --region=us-central1 \
     --update-env-vars="CORS_ORIGINS=https://your-frontend-url.com"
   ```

---

### API Connection Refused

**Symptom**:
```
Error: connect ECONNREFUSED 127.0.0.1:8088
```

**Cause**: Backend not running or wrong URL

**Solution**:

1. **Check backend is running**:
   ```bash
   curl http://localhost:8088/api/health
   ```

2. **If not running, start it**:
   ```bash
   cd backend
   python run.py
   ```

3. **Verify frontend API URL**:
   ```bash
   # Check .env.development
   cat frontend/.env.development
   # Should match backend URL
   VITE_API_URL=http://localhost:8088/api
   ```

4. **Restart frontend**:
   ```bash
   npm run dev
   ```

---

## BigQuery Errors

### Permission Denied

**Symptom**:
```
google.api_core.exceptions.Forbidden: 403 User does not have bigquery.tables.get permission for table
```

**Cause**: Service account lacks BigQuery permissions

**Solution**:

Grant required roles:
```bash
# BigQuery Data Viewer
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/bigquery.dataViewer"

# BigQuery Job User
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/bigquery.jobUser"
```

**Verify roles**:
```bash
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:SA_EMAIL"
```

---

### Table Not Found

**Symptom**:
```
google.api_core.exceptions.NotFound: 404 Table project.dataset.table not found
```

**Cause**: Table doesn't exist or incorrect name

**Solution**:

1. **List tables in dataset**:
   ```bash
   bq ls PROJECT_ID:DATASET_NAME
   ```

2. **Check table name spelling**:
   - Table names are case-sensitive in BigQuery
   - Use backticks for reserved words: `` `table` ``

3. **Verify dataset**:
   ```bash
   # Check BIGQUERY_DATASET in .env
   echo $BIGQUERY_DATASET
   ```

4. **Test query**:
   ```bash
   bq query --use_legacy_sql=false \
     'SELECT * FROM `project.dataset.table` LIMIT 1'
   ```

---

### Quota Exceeded

**Symptom**:
```
google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded: Your project exceeded quota for free query bytes scanned.
```

**Cause**: Exceeded BigQuery free tier (1 TB/month) or quota limits

**Solution**:

1. **Check current usage**:
   - GCP Console → BigQuery → "Reservations"
   - View "Bytes processed" chart

2. **Reduce query size**:
   - Add WHERE filters
   - Use partitioned tables
   - Add LIMIT clauses

3. **Purchase slots** (if consistent high usage):
   ```bash
   # Set up slot reservation
   bq mk --reservation --project_id=PROJECT_ID \
     --location=us-central1 \
     reservation_name \
     --slots=100
   ```

---

## Getting Help

### Enable Debug Logging

**Backend**:
```bash
# In .env
DEBUG=true

# View detailed logs
python run.py
```

**Cloud Run**:
```bash
# Stream logs with all levels
gcloud run services logs tail data-insights-backend \
  --region=us-central1 \
  --log-filter="severity>=DEBUG"
```

### Diagnostic Commands

**Check configuration**:
```bash
# Backend settings
cd backend
python -c "from agent.config import settings; print(settings.dict())"

# Docker Compose config
docker-compose config

# Cloud Run service details
gcloud run services describe data-insights-backend \
  --region=us-central1 \
  --format=yaml
```

**Test connections**:
```bash
# BigQuery connectivity
bq ls PROJECT_ID:DATASET_NAME

# Vertex AI model access
gcloud ai models list --region=global
```

### Report Issues

If you can't resolve the issue:

1. **Gather information**:
   - Error message (full stack trace)
   - Configuration (sanitized, no secrets)
   - Steps to reproduce
   - Environment (local, Docker, Cloud Run)

2. **Check logs**:
   ```bash
   # Local
   cat backend/logs/app.log

   # Docker
   docker-compose logs backend > logs.txt

   # Cloud Run
   gcloud run services logs read data-insights-backend \
     --region=us-central1 \
     --limit=100 > logs.txt
   ```

3. **Create GitHub issue**: [github.com/yourrepo/data-insights-agent/issues](https://github.com)

---

## Related Documentation

- [`DEPLOYMENT.md`](./DEPLOYMENT.md) - Deployment procedures
- [`CONFIGURATION.md`](./CONFIGURATION.md) - Environment variable reference
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) - System architecture and design decisions
- [`API.md`](./API.md) - API endpoint reference

---

*Last updated: February 2026*
