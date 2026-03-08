# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Data Insights Agent is an AI-powered data analysis tool built with Google ADK (Agent Development Kit), FastAPI, React, and Apache ECharts. It enables natural language querying of BigQuery data with automatic SQL generation, data enrichment via Google Search, and interactive visualizations.

**Status**: Early stage development - APIs and features may change significantly.

## Development Setup

### Backend

```bash
cd backend

# Create .env from template
cp .env.example .env
# Edit .env with your GOOGLE_CLOUD_PROJECT and BIGQUERY_DATASET

# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Using pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the backend server (note: must use api.main:app, not main:app)
uvicorn api.main:app --host 0.0.0.0 --port 8088 --reload

# Or use the run script (recommended)
python run.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Development server on port 5173
npm run build        # TypeScript compile + Vite build
npm run lint         # ESLint check
```

### Authentication

Google Cloud authentication via Application Default Credentials (ADC):
```bash
gcloud auth application-default login
```

Required GCP APIs: BigQuery API, Vertex AI API

## Architecture

### Agent System (Google ADK)

The application uses a **two-agent architecture**:

1. **Main Agent** (`backend/agent/agent.py`): Handles user queries, SQL generation, and query execution
   - Model: `gemini-3-flash-preview` via Vertex AI
   - Tools: `get_available_tables`, `get_table_schema`, `validate_sql_query`, `execute_query_with_metadata`, `add_calculated_column`, `request_enrichment`
   - Sub-agents: `enrichment_agent`

2. **Enrichment Sub-Agent** (`backend/agent/enrichment/agent.py`): Augments query results with real-time data from Google Search
   - Model: `gemini-3-flash-preview`
   - Tools: `GoogleSearchTool` (with `bypass_multi_tools_limit=True`), `apply_enrichment`
   - Called via `request_enrichment` tool from main agent

**Key Agent Workflow**:
- User asks question → Main agent generates SQL → Executes via `execute_query_with_metadata`
- If enrichment requested → Main agent calls `request_enrichment` → Transfers to enrichment agent
- Enrichment agent searches Google → Calls `apply_enrichment` to merge data → Returns to main agent
- Main agent can then call `add_calculated_column` to derive values from enriched data

### Session Management

- **ADK Sessions** (`backend/api/routes.py`): Uses `InMemorySessionService` for Google ADK agent state
  - Session IDs prefixed with `adk_` (e.g., `adk_<session_id>`)
  - Maintains conversation context across agent invocations

- **App Sessions** (`backend/services/session_service.py`): Manages chat history and UI state
  - Stores messages, query results, insights, clarifying questions
  - Provides conversation context to ADK runner

### Data Flow

```
User Message → FastAPI (/api/chat)
  → SessionService (add user message)
  → ADK Runner (with conversation context)
  → Agent executes tools (query BigQuery, enrich data, calculate columns)
  → Tool responses captured in event stream
  → QueryResult extracted from function_response events
  → SessionService (add assistant message with QueryResult)
  → ChatResponse returned to frontend
```

### Tool System

Tools are Python functions in `backend/agent/tools.py` that the agent can call:

- **Schema Tools**: `get_available_tables`, `get_table_schema` (with caching in `_schema_cache`)
- **Query Tools**: `validate_sql_query` (dry run), `execute_query_with_metadata` (stores in `_last_query_result`)
- **Enrichment Tools**: `apply_enrichment` (merges enrichment data into `_last_query_result`)
- **Calculation Tools**: `add_calculated_column` (adds derived columns without re-running query)

**Important**: `_last_query_result` is a global variable that stores the most recent query result for enrichment and calculation operations.

### Frontend Architecture

- **State Management**: React hooks (`useChat`, `useChartConfig`, `useWebSocket`)
- **Components**: Organized by feature (Chat/, Results/, Layout/)
- **Data Visualization**: Apache ECharts with dynamic chart configuration
- **API Communication**: Centralized in `services/api.ts`

Key hooks:
- `useChat`: Manages messages, session state, and API calls
- `useChartConfig`: Generates ECharts configurations from QueryResult data
- `useWebSocket`: (Placeholder for future streaming support)

### Environment Variables

Backend (`backend/.env`):
- `GOOGLE_CLOUD_PROJECT`: GCP project ID (required)
- `BIGQUERY_DATASET`: Default BigQuery dataset (required)
- `GOOGLE_CLOUD_REGION`: Vertex AI region (default: `global`, note: `us-central1` in config.py)
- `PORT`: Server port (default: 8088)
- `DEBUG`: Enable debug mode (default: false)
- `CORS_ORIGINS`: Comma-separated allowed origins (default: localhost:5173,localhost:3000)

**Note**: The README says `GOOGLE_CLOUD_REGION=global` but `config.py` defaults to `us-central1`. Use `global` for `gemini-3-flash-preview` model.

## Code Patterns

### Adding New Agent Tools

1. Define function in `backend/agent/tools.py` with type hints and docstring
2. Add to `CUSTOM_TOOLS` list at bottom of file
3. Document in `backend/agent/prompts.py` SYSTEM_INSTRUCTION
4. Test by sending natural language query that triggers the tool

### Enrichment Workflow

Enrichment adds real-time data from Google Search to query results:

1. Main agent executes base query with `execute_query_with_metadata`
2. User asks to enrich (e.g., "add state capitals")
3. Main agent calls `request_enrichment(column_name, unique_values, fields_to_add, data_type)`
4. If valid, transfers to enrichment_agent
5. Enrichment agent searches Google and calls `apply_enrichment(source_column, enrichment_data)`
6. `apply_enrichment` merges enriched columns (prefixed with `_enriched_`) into `_last_query_result`
7. Control returns to main agent with enriched data
8. Frontend displays enriched columns with metadata (source, confidence, freshness, warnings)

**Enrichment Guardrails**:
- Max 20 unique values per request
- Max 5 fields per request
- All enriched data includes source attribution
- Enriched columns marked with `is_enriched: True` flag

### Calculated Columns

Add derived values without re-running queries:

```python
add_calculated_column(
    column_name="residents_per_store",
    expression="_enriched_population / store_count",
    format_type="integer"  # Options: number, integer, percent, currency
)
```

- Uses Python `eval()` with restricted namespace for safety
- Can reference enriched columns (automatically extracts `.value` from enriched objects)
- Results include `is_calculated: True` flag

### Frontend QueryResult Handling

QueryResult format from backend:
```typescript
{
  columns: { name: string, type: string, is_enriched?: boolean, is_calculated?: boolean }[]
  rows: Record<string, any>[]  // Values can be primitives or {value, source, confidence, freshness, warning}
  total_rows: number
  query_time_ms: number
  sql: string
  enrichment_metadata?: { source_column, enriched_fields, warnings, ... }
  calculation_metadata?: { calculated_columns: [{name, expression, format_type}], warnings }
}
```

Frontend extracts numeric values for charts using `extractNumericValue()` helper to handle both primitive values and enriched/calculated objects.

## API Endpoints

- `GET /api/health`: Health check
- `POST /api/chat`: Send message to agent (main endpoint)
- `GET /api/sessions`: List all sessions
- `POST /api/sessions`: Create new session
- `GET /api/sessions/{id}`: Get session info
- `DELETE /api/sessions/{id}`: Delete session
- `GET /api/sessions/{id}/messages`: Get session messages
- `GET /api/schema/tables`: List BigQuery tables
- `GET /api/schema/tables/{name}`: Get table schema

## Testing

Currently no test suite is present in the repository. See [docs/TESTING.md](docs/TESTING.md) for the testing strategy and example tests covering:
- Backend: pytest for FastAPI routes, agent tools, session service, and Pydantic models
- Frontend: Vitest with React Testing Library for components, hooks, and API services

## Documentation

The `docs/` directory contains detailed project documentation:

- [User Guide](docs/USER_GUIDE.md) -- End-user guide for analysts
- [Architecture](docs/ARCHITECTURE.md) -- System design, data flow, diagrams
- [API Reference](docs/API.md) -- Complete endpoint documentation
- [Configuration](docs/CONFIGURATION.md) -- Environment variable reference
- [Development](docs/DEVELOPMENT.md) -- How-to guides for extending the system
- [Deployment](docs/DEPLOYMENT.md) -- Local, Docker, and Cloud Run deployment
- [Testing](docs/TESTING.md) -- Testing strategy and examples
- [Security](docs/SECURITY.md) -- Security considerations and known limitations
- [Troubleshooting](docs/TROUBLESHOOTING.md) -- Common issues and solutions
- [Contributing](CONTRIBUTING.md) -- Code style, Git workflow, PR process

## Common Gotchas

1. **Model region mismatch**: README suggests `GOOGLE_CLOUD_REGION=global` but code defaults to `us-central1`. Use `global` for `gemini-3-flash-preview`.

2. **ADK session persistence**: `InMemorySessionService` loses state on server restart. For production, use persistent session service.

3. **Schema caching**: `_schema_cache` never expires. Use `clear_schema_cache()` tool if table structures change.

4. **Global state in tools.py**: `_last_query_result` is global and shared across sessions. Not thread-safe for concurrent requests.

5. **Enrichment tool visibility**: `apply_enrichment` is NOT in main agent's tools list - only enrichment_agent can call it. Main agent uses `request_enrichment` to trigger enrichment workflow.

6. **Chart data extraction**: Frontend must use `extractNumericValue()` to handle enriched/calculated column values that are objects with metadata.

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
