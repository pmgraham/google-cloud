# Security Guide

Security considerations, known limitations, and best practices for the Data Insights Agent.

> **Note**: This project is in early stage development and is not production-ready. This document describes the current security posture and areas that need hardening before any production deployment.

## Table of Contents

1. [Authentication and Authorization](#authentication-and-authorization)
2. [Data Security](#data-security)
3. [Network Security](#network-security)
4. [Application Security](#application-security)
5. [Known Limitations](#known-limitations)
6. [Production Hardening Checklist](#production-hardening-checklist)
7. [Vulnerability Reporting](#vulnerability-reporting)

---

## Authentication and Authorization

### Current State

The application **does not implement user authentication or authorization**. All API endpoints are publicly accessible to anyone who can reach the server. This is acceptable for local development but must be addressed before any deployment beyond a single-user environment.

### Google Cloud Authentication

The backend authenticates to Google Cloud services (BigQuery, Vertex AI) using **Application Default Credentials (ADC)**:

```bash
gcloud auth application-default login
```

**How credentials are used**:
- BigQuery API calls use ADC to authenticate queries
- Vertex AI API calls use ADC to access Gemini models
- In Docker, credentials are mounted as a read-only volume at `/app/credentials.json`
- In Cloud Run, the service account attached to the service provides credentials

**Credential security**:
- Never commit credential files (`*.json` keys) to version control
- The `.gitignore` already excludes `.env` files and credential files
- For production, use Cloud Run's attached service account rather than key files
- Apply least-privilege IAM roles (see [IAM Roles](#iam-roles) below)

### IAM Roles

The service account or user running the application needs these minimum roles:

| Role | Purpose | Scope |
|------|---------|-------|
| `roles/bigquery.dataViewer` | Read table data and metadata | Project or dataset level |
| `roles/bigquery.jobUser` | Run BigQuery queries | Project level |
| `roles/aiplatform.user` | Access Vertex AI models | Project level |

**Principle of least privilege**:
- Grant roles at the dataset level rather than project level when possible
- Do not grant `bigquery.dataEditor` or `bigquery.admin` -- the agent only needs read access
- Use separate service accounts for development and production

---

## Data Security

### BigQuery Data Access

**Read-only by design**: The agent tools only execute `SELECT` queries. The `validate_sql_query` tool performs a BigQuery dry run that rejects non-SELECT statements. However, this is enforced at the application level, not at the IAM level.

**Defense in depth**: To prevent accidental data modification even if a bug bypasses application-level checks:
- Grant only `bigquery.dataViewer` (not `dataEditor` or `dataOwner`)
- Use BigQuery authorized views to restrict which tables are queryable
- Consider BigQuery column-level security for sensitive fields

### Query Result Storage

Query results are stored in a **module-level global variable** (`_last_query_result` in `backend/agent/tools.py`):

- Results are held in server memory only -- not persisted to disk
- Results are overwritten each time a new query executes
- **Not session-isolated**: In a concurrent multi-user scenario, one user's query results could be overwritten by another user's query (see [Known Limitations](#known-limitations))

### Session Data

Sessions are stored using `InMemorySessionService`:

- All conversation history lives in server memory
- Sessions are lost on server restart
- No session data is written to disk or external storage
- Session IDs are UUIDs -- not guessable, but not cryptographically secured either

### Enrichment Data

The enrichment feature sends query result values to Google Search:

- **Data exposure**: Column values from query results (e.g., state names, company names) are sent to Google's search API
- **Sensitive data risk**: If query results contain PII or sensitive values, those values will be sent to Google Search
- **Mitigation**: The enrichment agent limits requests to 20 unique values per enrichment call
- **Recommendation**: Do not use enrichment on columns containing PII, financial data, or other sensitive information

### CSV Export

- Exported CSV files contain the full query result set including enriched and calculated values
- Enriched metadata (source, confidence) is stripped in the export -- only plain values are included
- No encryption is applied to exported files
- Users are responsible for handling exported data according to their organization's data policies

---

## Network Security

### CORS Configuration

Cross-Origin Resource Sharing is configured via the `CORS_ORIGINS` environment variable:

```bash
# Development (default)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Production -- restrict to your domain only
CORS_ORIGINS=https://app.yourcompany.com
```

**Best practices**:
- Never use wildcard (`*`) origins in production
- List only the specific frontend domains that should access the API
- Include the protocol (`http://` or `https://`) in each origin
- Review CORS settings when deploying to new environments

### Cloud Run Security

When deployed to Cloud Run:

- **HTTPS by default**: Cloud Run provides TLS termination automatically
- **Ingress control**: Configure ingress to limit traffic sources
  ```bash
  gcloud run services update SERVICE_NAME \
    --ingress=internal-and-cloud-load-balancing
  ```
- **Authentication**: Consider enabling Cloud Run authentication for non-public services
  ```bash
  gcloud run services update SERVICE_NAME --no-allow-unauthenticated
  ```

### Docker Security

- Credential files are mounted as **read-only** (`:ro` flag in docker-compose.yml)
- The container runs as a non-root user (when configured in the Dockerfile)
- Environment variables containing secrets should use Docker secrets or `.env` files, not command-line arguments

---

## Application Security

### SQL Injection Prevention

The agent generates SQL from natural language, which creates an inherent SQL injection surface:

**Current protections**:
- `validate_sql_query` performs a BigQuery dry run before execution -- BigQuery rejects malformed or unauthorized queries
- The `BIGQUERY_DATASET` setting scopes queries to a specific dataset
- BigQuery IAM roles restrict what the service account can access
- The agent's system prompt instructs it to only generate SELECT queries

**Residual risks**:
- The LLM could be prompt-injected via user messages to generate harmful queries
- BigQuery dry run validates syntax but does not prevent data exfiltration within the allowed dataset
- No query allow-listing or pattern matching is applied beyond the dry run

**Recommendations for production**:
- Use BigQuery authorized views to expose only approved tables/columns
- Implement query logging and auditing
- Add a query complexity/cost limit using BigQuery's `maximumBytesBilled` parameter
- Consider a query review step before execution for sensitive datasets

### Calculated Column Expression Safety

The `add_calculated_column` tool uses Python's `eval()` to execute arithmetic expressions:

**Current protections**:
- The `eval()` namespace is restricted to math operations and column data only
- Built-in functions are not exposed (`{"__builtins__": {}}`)
- Only numeric operations are supported (addition, subtraction, multiplication, division)

**Residual risks**:
- `eval()` is inherently dangerous even with namespace restrictions
- Creative payloads could potentially escape the restricted namespace
- No expression complexity limit exists

**Recommendations for production**:
- Replace `eval()` with a safe expression parser (e.g., `asteval`, `simpleeval`, or a custom AST parser)
- Validate expressions against an allow-list of operators
- Add expression length limits
- Log all evaluated expressions for auditing

### Agent Prompt Injection

The application accepts arbitrary user input and passes it to an LLM:

**Current protections**:
- The system prompt provides behavioral boundaries for the agent
- Tool functions validate their inputs independently of the LLM
- BigQuery dry run provides a safety net for invalid SQL

**Residual risks**:
- Users can attempt to override system instructions via prompt injection
- The agent could be manipulated into revealing system prompt contents
- Multi-turn conversations could gradually shift agent behavior

**Recommendations for production**:
- Implement input sanitization and length limits
- Add output filtering to prevent system prompt leakage
- Log all agent interactions for review
- Consider rate limiting per session/user

### Dependency Security

- **Backend**: Dependencies are pinned in `requirements.txt`
- **Frontend**: Dependencies are managed via `package.json` with `package-lock.json`
- No automated dependency scanning (e.g., Dependabot, Snyk) is currently configured

**Recommendations**:
- Enable automated dependency vulnerability scanning
- Regularly update dependencies to patch known vulnerabilities
- Audit new dependencies before adding them

---

## Known Limitations

These are security-relevant limitations in the current implementation:

| Limitation | Risk | Severity | Mitigation |
|-----------|------|----------|------------|
| No user authentication | Any network user can access all endpoints | High | Deploy behind VPN or add auth layer |
| Global `_last_query_result` | Cross-session data leakage in concurrent use | High | Single-user only; refactor for production |
| `InMemorySessionService` | No session persistence; no session expiry | Medium | Acceptable for development |
| `eval()` in calculated columns | Potential code execution via crafted expressions | Medium | Restricted namespace; replace for production |
| No rate limiting | API abuse, resource exhaustion | Medium | Add rate limiting middleware |
| No input validation on message length | Large payloads could cause memory issues | Low | Add request size limits |
| Schema cache never expires | Stale schema data after table changes | Low | Manual clear available via tool |
| No audit logging | Cannot trace who queried what | Medium | Add structured logging |

---

## Production Hardening Checklist

Before deploying to a production or multi-user environment:

### Authentication and Authorization
- [ ] Add user authentication (OAuth 2.0, OIDC, or API keys)
- [ ] Implement per-user session isolation
- [ ] Add role-based access control for sensitive datasets

### Data Protection
- [ ] Replace global `_last_query_result` with session-scoped storage
- [ ] Add query result TTL (auto-expire cached results)
- [ ] Implement data classification and PII detection for enrichment filtering
- [ ] Enable audit logging for all queries and data access

### Network Security
- [ ] Restrict CORS origins to production frontend domain only
- [ ] Enable Cloud Run authentication (`--no-allow-unauthenticated`)
- [ ] Configure ingress rules to limit traffic sources
- [ ] Enable Cloud Armor WAF for DDoS protection

### Application Security
- [ ] Replace `eval()` with a safe expression parser
- [ ] Add request rate limiting
- [ ] Add request size limits
- [ ] Implement input sanitization
- [ ] Add output filtering to prevent prompt/data leakage
- [ ] Enable automated dependency scanning

### Infrastructure
- [ ] Use Secret Manager for all sensitive configuration
- [ ] Enable Cloud Audit Logs
- [ ] Configure alerting for suspicious activity
- [ ] Use separate GCP projects for development and production
- [ ] Apply least-privilege IAM roles at dataset level

---

## Vulnerability Reporting

If you discover a security vulnerability in this project:

1. **Do not open a public issue** -- security vulnerabilities should not be disclosed publicly before a fix is available

2. **Contact the maintainers privately** with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if you have one)

3. **Allow reasonable time** for the maintainers to address the issue before any public disclosure

Since this project is in early stage development and not intended for production use, please still report issues so they can be tracked and addressed as the project matures.

---

## Related Documentation

- [Architecture Guide](./ARCHITECTURE.md) -- System design and data flow
- [Configuration Guide](./CONFIGURATION.md) -- Environment variable reference
- [Deployment Guide](./DEPLOYMENT.md) -- Deployment procedures including Cloud Run
- [Troubleshooting Guide](./TROUBLESHOOTING.md) -- Common issues and solutions

---

*Last updated: February 2026*
