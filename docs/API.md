# API Reference

Complete API reference for the Data Insights Agent REST API.

## Table of Contents

- [Base URL](#base-url)
- [Authentication](#authentication)
- [Interactive Documentation](#interactive-documentation)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
  - [Health Check](#health-check)
  - [Chat Interaction](#chat-interaction)
  - [Session Management](#session-management)
  - [Schema Metadata](#schema-metadata)

---

## Base URL

**Development**: `http://localhost:8088/api`

**Production**: Configure via environment variables (see [`README.md`](../README.md))

All endpoints are prefixed with `/api` (e.g., `/api/health`, `/api/chat`).

---

## Authentication

**Current**: No authentication required (early-stage development)

**Future**: Google Cloud authentication via Application Default Credentials (ADC) for BigQuery access. Frontend may implement session-based auth or OAuth.

---

## Interactive Documentation

FastAPI provides auto-generated interactive API documentation at two endpoints:

### Swagger UI (Recommended)

**URL**: `http://localhost:8088/docs`

**Features**:
- Interactive request testing (Try it out button)
- Request/response schema inspection
- Example payloads auto-populated
- Support for all HTTP methods

**Usage**:
1. Start the backend: `cd backend && python run.py`
2. Open browser to `http://localhost:8088/docs`
3. Expand an endpoint (e.g., `POST /api/chat`)
4. Click "Try it out"
5. Modify request body and click "Execute"

### ReDoc

**URL**: `http://localhost:8088/redoc`

**Features**:
- Clean, readable documentation layout
- Better for documentation browsing (not interactive testing)
- Search functionality
- Nested schema visualization

**Recommendation**: Use **Swagger UI** for testing, **ReDoc** for reference.

---

## Response Format

All endpoints return JSON responses with appropriate HTTP status codes.

### Success Responses

**HTTP 200 OK**: Successful operation
**HTTP 201 Created**: Resource created (sessions)

```json
{
  "status": "success",
  "data": { ... }
}
```

### Error Responses

**HTTP 400 Bad Request**: Invalid request payload
**HTTP 404 Not Found**: Resource not found (session, table)
**HTTP 422 Unprocessable Entity**: Validation error (Pydantic)
**HTTP 500 Internal Server Error**: Server error

Standard error format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

Validation errors (HTTP 422) include field-level details:
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

---

## Endpoints

### Health Check

Check if the API is running and healthy.

#### Request

```http
GET /api/health
```

**Headers**: None required

**Query Parameters**: None

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-02-06T21:45:00.000Z"
}
```

**Fields**:
- `status` (string): Health status (`"healthy"` or `"unhealthy"`)
- `version` (string): API version
- `timestamp` (string): Response timestamp (ISO 8601 UTC)

#### Status Codes

- `200 OK`: API is healthy

#### Example

```bash
curl http://localhost:8088/api/health
```

---

### Chat Interaction

Send a natural language query to the AI agent and receive structured responses with query results.

#### Request

```http
POST /api/chat
```

**Headers**:
```
Content-Type: application/json
```

**Body**:
```json
{
  "message": "Show me the top 10 states by population",
  "session_id": "session_abc123"
}
```

**Fields**:
- `message` (string, **required**): Natural language question or command
  - Min length: 1 character
  - Max length: 10,000 characters
  - Examples: `"Show me sales by state"`, `"What were Q4 revenues?"`

- `session_id` (string, **optional**): Session ID to continue existing conversation
  - If `null` or omitted, a new session is created
  - Use the `session_id` from previous responses to maintain context

#### Response

```json
{
  "session_id": "session_abc123",
  "message": {
    "id": "msg_xyz789",
    "role": "assistant",
    "content": "Here are the top 10 states by population. California leads with 39.5M residents, followed by Texas with 29.1M.",
    "timestamp": "2026-02-06T21:50:00.000Z",
    "query_result": {
      "columns": [
        {
          "name": "state",
          "type": "STRING",
          "is_enriched": false,
          "is_calculated": false
        },
        {
          "name": "population",
          "type": "INTEGER",
          "is_enriched": false,
          "is_calculated": false
        }
      ],
      "rows": [
        {"state": "California", "population": 39500000},
        {"state": "Texas", "population": 29100000},
        {"state": "Florida", "population": 21500000}
      ],
      "total_rows": 10,
      "query_time_ms": 234.56,
      "sql": "SELECT state, population FROM census.states ORDER BY population DESC LIMIT 10",
      "enrichment_metadata": null,
      "calculation_metadata": null
    },
    "clarifying_question": null,
    "insights": [
      {
        "type": "trend",
        "message": "California has 35% more residents than Texas",
        "importance": "medium"
      },
      {
        "type": "suggestion",
        "message": "compare with historical census data",
        "importance": "low"
      }
    ],
    "is_streaming": false
  },
  "conversation_history": [
    {
      "id": "msg_user456",
      "role": "user",
      "content": "Show me the top 10 states by population",
      "timestamp": "2026-02-06T21:49:55.000Z",
      "query_result": null,
      "clarifying_question": null,
      "insights": [],
      "is_streaming": false
    },
    {
      "id": "msg_xyz789",
      "role": "assistant",
      "content": "Here are the top 10 states...",
      "timestamp": "2026-02-06T21:50:00.000Z",
      "query_result": { ... },
      "clarifying_question": null,
      "insights": [...],
      "is_streaming": false
    }
  ]
}
```

**Response Fields**:

- `session_id` (string): Session ID for this conversation (use in subsequent requests)
- `message` (ChatMessage): The assistant's response
  - `id` (string): Unique message identifier
  - `role` (string): Always `"assistant"` for AI responses
  - `content` (string): Natural language response text
  - `timestamp` (string): Message creation time (ISO 8601 UTC)
  - `query_result` (QueryResult | null): Query results if the agent executed a SQL query
  - `clarifying_question` (ClarifyingQuestion | null): Present if agent needs clarification
  - `insights` (Insight[]): AI-generated insights (trends, anomalies, suggestions)
  - `is_streaming` (boolean): Always `false` (streaming not yet implemented)
- `conversation_history` (ChatMessage[]): Full conversation ordered chronologically

#### QueryResult Structure

When the agent executes a BigQuery query, the response includes a `query_result` object:

```json
{
  "columns": [
    {
      "name": "state",
      "type": "STRING",
      "is_enriched": false,
      "is_calculated": false
    },
    {
      "name": "_enriched_capital",
      "type": "STRING",
      "is_enriched": true,
      "is_calculated": false
    },
    {
      "name": "residents_per_store",
      "type": "FLOAT64",
      "is_enriched": false,
      "is_calculated": true
    }
  ],
  "rows": [
    {
      "state": "California",
      "_enriched_capital": {
        "value": "Sacramento",
        "source": "https://en.wikipedia.org/wiki/California",
        "confidence": "high",
        "freshness": "2025-01-15T10:00:00Z",
        "warning": null
      },
      "residents_per_store": {
        "value": 12500.5,
        "expression": "population / store_count",
        "format_type": "number",
        "is_calculated": true,
        "warning": null
      }
    }
  ],
  "total_rows": 50,
  "query_time_ms": 456.78,
  "sql": "SELECT state, population, store_count FROM sales.by_state LIMIT 1000",
  "enrichment_metadata": {
    "source_column": "state",
    "enriched_fields": ["capital"],
    "total_enriched": 50,
    "warnings": [],
    "partial_failure": false
  },
  "calculation_metadata": {
    "calculated_columns": [
      {
        "name": "residents_per_store",
        "expression": "population / store_count",
        "format_type": "number"
      }
    ],
    "warnings": []
  }
}
```

**Column Types**:
- **Regular columns**: Primitive values (string, number, boolean, null)
- **Enriched columns**: Objects with `{value, source, confidence, freshness, warning}`
  - Prefixed with `_enriched_`
  - Added via `apply_enrichment()` from Google Search
- **Calculated columns**: Objects with `{value, expression, format_type, is_calculated, warning}`
  - Added via `add_calculated_column()` from Python expressions

#### Clarifying Questions

When the agent needs more information, it returns a clarifying question:

```json
{
  "message": {
    ...
    "clarifying_question": {
      "question": "Which state do you want to analyze?",
      "options": [
        "California",
        "Texas",
        "New York",
        "Florida"
      ],
      "context": "I found data for multiple states. Please select one."
    }
  }
}
```

**Frontend Handling**: Display options as clickable buttons. When user selects an option, send it as a new message.

#### Insights

The agent proactively generates insights from query results:

```json
{
  "insights": [
    {
      "type": "trend",
      "message": "Sales peaked in Q4 with 45% growth over Q3",
      "importance": "high"
    },
    {
      "type": "anomaly",
      "message": "Texas had unusually low sales in December",
      "importance": "medium"
    },
    {
      "type": "comparison",
      "message": "California outperformed Texas by 2.5x",
      "importance": "medium"
    },
    {
      "type": "suggestion",
      "message": "compare with last year's Q4 performance",
      "importance": "low"
    }
  ]
}
```

**Insight Types**:
- `trend`: Data trends or patterns
- `anomaly`: Unusual values or outliers
- `comparison`: Comparative analysis
- `suggestion`: Recommendations for follow-up queries

#### Status Codes

- `200 OK`: Successful chat interaction
- `422 Unprocessable Entity`: Invalid request (missing `message`, message too long)
- `500 Internal Server Error`: Agent error (returned as assistant message with error text)

#### Examples

**Simple Query**:
```bash
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How many Chipotle locations are in South Carolina?"
  }'
```

**Continue Conversation**:
```bash
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What about North Carolina?",
    "session_id": "session_abc123"
  }'
```

**Complex Query with Enrichment**:
```bash
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me sales by state and enrich with state capitals"
  }'
```

---

### Session Management

Manage conversation sessions for context preservation across multiple queries.

#### Create Session

Create a new chat session.

**Request**:
```http
POST /api/sessions
```

**Headers**:
```
Content-Type: application/json
```

**Body**:
```json
{
  "name": "Sales Analysis Session"
}
```

**Fields**:
- `name` (string, **optional**): Human-readable session name

**Response**:
```json
{
  "id": "session_abc123",
  "name": "Sales Analysis Session",
  "created_at": "2026-02-06T22:00:00.000Z",
  "updated_at": "2026-02-06T22:00:00.000Z",
  "message_count": 0
}
```

**Status Codes**:
- `200 OK`: Session created successfully
- `500 Internal Server Error`: Failed to create session

**Example**:
```bash
curl -X POST http://localhost:8088/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "Q4 Analysis"}'
```

---

#### List Sessions

Get all existing chat sessions.

**Request**:
```http
GET /api/sessions
```

**Headers**: None required

**Query Parameters**: None

**Response**:
```json
{
  "sessions": [
    {
      "id": "session_abc123",
      "name": "Sales Analysis",
      "created_at": "2026-02-06T22:00:00.000Z",
      "updated_at": "2026-02-06T22:05:00.000Z",
      "message_count": 12
    },
    {
      "id": "session_xyz789",
      "name": null,
      "created_at": "2026-02-06T21:30:00.000Z",
      "updated_at": "2026-02-06T21:45:00.000Z",
      "message_count": 5
    }
  ]
}
```

**Status Codes**:
- `200 OK`: Sessions retrieved successfully

**Example**:
```bash
curl http://localhost:8088/api/sessions
```

---

#### Get Session

Retrieve information about a specific session.

**Request**:
```http
GET /api/sessions/{session_id}
```

**Path Parameters**:
- `session_id` (string, **required**): Session identifier

**Response**:
```json
{
  "id": "session_abc123",
  "name": "Sales Analysis",
  "created_at": "2026-02-06T22:00:00.000Z",
  "updated_at": "2026-02-06T22:05:00.000Z",
  "message_count": 12
}
```

**Status Codes**:
- `200 OK`: Session found
- `404 Not Found`: Session does not exist

**Example**:
```bash
curl http://localhost:8088/api/sessions/session_abc123
```

---

#### Delete Session

Delete a chat session and all its messages.

**Request**:
```http
DELETE /api/sessions/{session_id}
```

**Path Parameters**:
- `session_id` (string, **required**): Session identifier

**Response**:
```json
{
  "status": "deleted"
}
```

**Status Codes**:
- `200 OK`: Session deleted successfully
- `404 Not Found`: Session does not exist

**Example**:
```bash
curl -X DELETE http://localhost:8088/api/sessions/session_abc123
```

---

#### Get Session Messages

Retrieve all messages in a session.

**Request**:
```http
GET /api/sessions/{session_id}/messages
```

**Path Parameters**:
- `session_id` (string, **required**): Session identifier

**Response**:
```json
[
  {
    "id": "msg_user123",
    "role": "user",
    "content": "Show me sales by state",
    "timestamp": "2026-02-06T22:00:00.000Z",
    "query_result": null,
    "clarifying_question": null,
    "insights": [],
    "is_streaming": false
  },
  {
    "id": "msg_asst456",
    "role": "assistant",
    "content": "Here are the sales by state...",
    "timestamp": "2026-02-06T22:00:05.000Z",
    "query_result": {
      "columns": [...],
      "rows": [...],
      "total_rows": 50,
      "query_time_ms": 234.5,
      "sql": "SELECT ..."
    },
    "clarifying_question": null,
    "insights": [...],
    "is_streaming": false
  }
]
```

**Status Codes**:
- `200 OK`: Messages retrieved successfully
- `404 Not Found`: Session does not exist

**Example**:
```bash
curl http://localhost:8088/api/sessions/session_abc123/messages
```

---

### Schema Metadata

Retrieve BigQuery table schema information.

#### List Available Tables

Get all tables in the configured BigQuery dataset.

**Request**:
```http
GET /api/schema/tables
```

**Headers**: None required

**Query Parameters**: None

**Response**:
```json
{
  "status": "success",
  "tables": [
    {
      "name": "states",
      "full_name": "my-project.biglake.states",
      "description": "US state information",
      "num_rows": 50,
      "columns": [
        {
          "name": "state",
          "type": "STRING",
          "description": "State name",
          "mode": "REQUIRED"
        },
        {
          "name": "population",
          "type": "INTEGER",
          "description": "Population count",
          "mode": "NULLABLE"
        }
      ]
    },
    {
      "name": "sales",
      "full_name": "my-project.biglake.sales",
      "description": "Sales transactions",
      "num_rows": 1000000,
      "columns": [...]
    }
  ]
}
```

**Response Fields**:
- `status` (string): `"success"` or `"error"`
- `tables` (array): List of table metadata objects
  - `name` (string): Simple table name
  - `full_name` (string): Fully qualified table name (`project.dataset.table`)
  - `description` (string): Table description
  - `num_rows` (integer): Approximate row count
  - `columns` (array): Column schema information
    - `name` (string): Column name
    - `type` (string): BigQuery data type (STRING, INTEGER, FLOAT64, etc.)
    - `description` (string): Column description
    - `mode` (string): `REQUIRED`, `NULLABLE`, or `REPEATED`

**Status Codes**:
- `200 OK`: Tables retrieved successfully
- `500 Internal Server Error`: BigQuery connection error

**Example**:
```bash
curl http://localhost:8088/api/schema/tables
```

---

#### Get Table Schema

Get detailed schema for a specific table.

**Request**:
```http
GET /api/schema/tables/{table_name}
```

**Path Parameters**:
- `table_name` (string, **required**): Table name (simple or fully qualified)
  - Examples: `"states"`, `"my-project.biglake.states"`

**Response**:
```json
{
  "status": "success",
  "table_name": "states",
  "columns": [
    {
      "name": "state",
      "type": "STRING",
      "description": "State name",
      "mode": "REQUIRED",
      "is_nullable": false
    },
    {
      "name": "population",
      "type": "INTEGER",
      "description": "Population count",
      "mode": "NULLABLE",
      "is_nullable": true
    },
    {
      "name": "capital",
      "type": "STRING",
      "description": "State capital city",
      "mode": "NULLABLE",
      "is_nullable": true
    }
  ],
  "sample_values": {
    "state": ["California", "Texas", "Florida"],
    "population": [39500000, 29100000, 21500000],
    "capital": ["Sacramento", "Austin", "Tallahassee"]
  }
}
```

**Response Fields**:
- `status` (string): `"success"` or `"error"`
- `table_name` (string): Table name
- `columns` (array): Column schema with extended metadata
  - `is_nullable` (boolean): Whether the column allows NULL values
- `sample_values` (object): Sample values for each column (for context)

**Status Codes**:
- `200 OK`: Schema retrieved successfully
- `404 Not Found`: Table does not exist
- `500 Internal Server Error`: BigQuery connection error

**Example**:
```bash
curl http://localhost:8088/api/schema/tables/states
```

---

## Error Handling

### Standard Error Response

All errors follow the FastAPI standard error format:

```json
{
  "detail": "Error message describing the problem"
}
```

### Common Error Codes

#### 400 Bad Request

**Cause**: Invalid request payload or parameters

**Example**:
```json
{
  "detail": "Message cannot be empty"
}
```

#### 404 Not Found

**Cause**: Requested resource does not exist (session, table)

**Example**:
```json
{
  "detail": "Session not found"
}
```

#### 422 Unprocessable Entity

**Cause**: Request validation failed (Pydantic)

**Example**:
```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    },
    {
      "loc": ["body", "message"],
      "msg": "ensure this value has at most 10000 characters",
      "type": "value_error.any_str.max_length",
      "ctx": {"limit_value": 10000}
    }
  ]
}
```

**Fields**:
- `loc` (array): Path to the invalid field (`["body", "message"]`)
- `msg` (string): Human-readable error message
- `type` (string): Error type identifier
- `ctx` (object): Additional context (e.g., limits, patterns)

#### 500 Internal Server Error

**Cause**: Server-side error (database connection, agent crash)

**Chat Endpoint Exception**: Errors in the chat endpoint are returned as **assistant messages** with error text, not HTTP 500 errors. This allows the conversation to continue.

**Example** (chat endpoint):
```json
{
  "session_id": "session_abc123",
  "message": {
    "role": "assistant",
    "content": "I encountered an error processing your request: Table 'nonexistent' not found. Please try again."
  }
}
```

**Example** (other endpoints):
```json
{
  "detail": "Failed to connect to BigQuery"
}
```

### Error Testing

**Trigger 404**:
```bash
curl http://localhost:8088/api/sessions/nonexistent_session
# Response: {"detail": "Session not found"}
```

**Trigger 422**:
```bash
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{}'
# Response: {"detail": [{"loc": ["body", "message"], "msg": "field required", ...}]}
```

**Trigger 400** (manual validation):
```bash
curl -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": ""}'
# Response: {"detail": [{"loc": ["body", "message"], "msg": "ensure this value has at least 1 characters", ...}]}
```

---

## Rate Limiting

**Current**: No rate limiting

**Future**: Consider implementing rate limits for:
- Chat endpoint: 60 requests/minute per session
- Schema endpoints: 100 requests/minute per IP
- Session creation: 10 requests/minute per IP

---

## Versioning

**Current**: Version 1.0.0 (indicated in `/api/health` response)

**Future**: API versioning may be implemented via URL path (`/api/v2/chat`) or headers (`Accept: application/vnd.data-insights.v2+json`).

---

## WebSocket Support

**Status**: Not implemented

**Future**: Real-time streaming responses via WebSocket for:
- Token-by-token chat streaming
- Query progress updates
- Live query result streaming

Proposed endpoint: `ws://localhost:8088/api/ws/chat`

---

## Development Tips

### Testing with curl

**Set a variable for base URL**:
```bash
export API_URL="http://localhost:8088/api"
```

**Create session and store ID**:
```bash
SESSION_ID=$(curl -s -X POST $API_URL/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "Test"}' | jq -r '.id')
```

**Send message with session**:
```bash
curl -X POST $API_URL/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Show me sales\", \"session_id\": \"$SESSION_ID\"}"
```

### Testing with HTTPie

**Install**: `pip install httpie`

**Simple query**:
```bash
http POST localhost:8088/api/chat message="Show me sales by state"
```

**With session**:
```bash
http POST localhost:8088/api/chat message="What about Texas?" session_id=session_abc123
```

### Testing with Python

```python
import requests

# Create session
response = requests.post("http://localhost:8088/api/sessions", json={"name": "Test"})
session_id = response.json()["id"]

# Send message
response = requests.post(
    "http://localhost:8088/api/chat",
    json={
        "message": "Show me sales by state",
        "session_id": session_id
    }
)
data = response.json()
print(data["message"]["content"])

# Check for query results
if data["message"]["query_result"]:
    result = data["message"]["query_result"]
    print(f"Query returned {result['total_rows']} rows in {result['query_time_ms']}ms")
```

---

## Related Documentation

- **Architecture**: See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for system design and agent workflows
- **Development**: See [`DEVELOPMENT.md`](./DEVELOPMENT.md) for extending the API with new endpoints or tools
- **Main README**: See [`README.md`](../README.md) for setup and deployment instructions

---

*Last updated: February 2026*
