# Testing Strategy

This document describes the testing frameworks, conventions, and procedures for the Data Insights Agent project.

## Current Status

The project does not yet have a test suite. This document outlines the recommended strategy and provides guidance for adding tests incrementally.

## Tech Stack

| Layer | Framework | Runner |
|-------|-----------|--------|
| Backend (Python) | pytest | `pytest` |
| Frontend (TypeScript/React) | Vitest | `npx vitest` |

## Backend Testing (pytest)

### Setup

Install test dependencies (add to `requirements.txt` or a separate `requirements-dev.txt`):

```
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0          # For FastAPI TestClient async support
```

Install:

```bash
cd backend
source .venv/bin/activate
pip install pytest pytest-asyncio httpx
```

### Directory Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures
│   ├── test_tools.py          # Agent tool unit tests
│   ├── test_routes.py         # API endpoint tests
│   ├── test_session_service.py # Session management tests
│   └── test_models.py         # Pydantic model tests
├── agent/
├── api/
└── services/
```

### Running Tests

```bash
cd backend
pytest                         # Run all tests
pytest tests/test_tools.py     # Run specific file
pytest -v                      # Verbose output
pytest -x                      # Stop on first failure
pytest --tb=short              # Short tracebacks
pytest -k "test_validate"      # Run tests matching pattern
```

### Writing Tool Tests

Agent tools (`backend/agent/tools.py`) are the most testable backend code since they have clear inputs and outputs. However, most tools require BigQuery access. Use mocking to test without external dependencies.

#### Example: Testing `add_calculated_column`

```python
# tests/test_tools.py
import pytest
from unittest.mock import patch
from agent.tools import add_calculated_column, _last_query_result

@pytest.fixture
def sample_query_result():
    """Fixture providing a sample query result for tool tests."""
    return {
        "status": "success",
        "columns": [
            {"name": "state", "type": "STRING"},
            {"name": "population", "type": "INTEGER"},
            {"name": "store_count", "type": "INTEGER"},
        ],
        "rows": [
            {"state": "CA", "population": 39500000, "store_count": 150},
            {"state": "TX", "population": 29100000, "store_count": 120},
            {"state": "NY", "population": 20200000, "store_count": 90},
        ],
        "total_rows": 3,
        "query_time_ms": 234.56,
        "sql": "SELECT state, population, store_count FROM data",
    }


def test_add_calculated_column_basic(sample_query_result):
    """Test adding a simple calculated column."""
    with patch("agent.tools._last_query_result", sample_query_result):
        result = add_calculated_column(
            column_name="residents_per_store",
            expression="population / store_count",
            format_type="integer",
        )

    assert result["status"] == "success"
    # Check new column was added
    col_names = [c["name"] for c in result["columns"]]
    assert "residents_per_store" in col_names

    # Check calculated values
    ca_row = result["rows"][0]
    assert ca_row["residents_per_store"]["is_calculated"] is True
    assert ca_row["residents_per_store"]["value"] == 263333  # 39500000 / 150


def test_add_calculated_column_no_query_result():
    """Test error when no prior query result exists."""
    with patch("agent.tools._last_query_result", None):
        result = add_calculated_column("col", "a + b")

    assert result["status"] == "error"
    assert "No query result" in result["error"]


def test_add_calculated_column_missing_column(sample_query_result):
    """Test error when expression references non-existent column."""
    with patch("agent.tools._last_query_result", sample_query_result):
        result = add_calculated_column("col", "nonexistent * 2")

    assert result["status"] == "error"
    assert "not found" in result["error"]


def test_add_calculated_column_division_by_zero(sample_query_result):
    """Test graceful handling of division by zero."""
    sample_query_result["rows"][0]["store_count"] = 0
    with patch("agent.tools._last_query_result", sample_query_result):
        result = add_calculated_column("ratio", "population / store_count")

    assert result["status"] == "success"
    assert result["rows"][0]["ratio"]["value"] is None
    assert result["rows"][0]["ratio"]["warning"] == "Division by zero"
```

#### Example: Testing `apply_enrichment`

```python
# tests/test_tools.py (continued)
from agent.tools import apply_enrichment

def test_apply_enrichment_basic(sample_query_result):
    """Test basic enrichment merge."""
    enrichment_data = [
        {
            "original_value": "CA",
            "enriched_fields": {
                "capital": {
                    "value": "Sacramento",
                    "source": "Wikipedia",
                    "confidence": "high",
                    "freshness": "static",
                }
            },
        },
        {
            "original_value": "TX",
            "enriched_fields": {
                "capital": {
                    "value": "Austin",
                    "source": "Wikipedia",
                    "confidence": "high",
                    "freshness": "static",
                }
            },
        },
    ]

    with patch("agent.tools._last_query_result", sample_query_result):
        result = apply_enrichment("state", enrichment_data)

    assert result["status"] == "success"
    # Check enriched column was added
    col_names = [c["name"] for c in result["columns"]]
    assert "_enriched_capital" in col_names

    # Check enrichment metadata
    assert result["enrichment_metadata"]["source_column"] == "state"
    assert "capital" in result["enrichment_metadata"]["enriched_fields"]


def test_apply_enrichment_no_query_result():
    """Test error when no prior query result exists."""
    with patch("agent.tools._last_query_result", None):
        result = apply_enrichment("state", [{"original_value": "CA", "enriched_fields": {}}])

    assert result["status"] == "error"
```

#### Example: Testing `validate_sql_query` (requires mocking BigQuery)

```python
# tests/test_tools.py (continued)
from unittest.mock import MagicMock
from agent.tools import validate_sql_query

def test_validate_sql_valid_query():
    """Test validation of a valid SQL query."""
    mock_job = MagicMock()
    mock_job.total_bytes_processed = 1048576  # 1 MB

    mock_client = MagicMock()
    mock_client.query.return_value = mock_job

    with patch("agent.tools.bigquery.Client", return_value=mock_client):
        result = validate_sql_query("SELECT * FROM table LIMIT 10")

    assert result["status"] == "valid"
    assert result["estimated_bytes"] == 1048576
    assert "1.00 MB" in result["estimated_size"]


def test_validate_sql_invalid_query():
    """Test validation of an invalid SQL query."""
    mock_client = MagicMock()
    mock_client.query.side_effect = Exception("Syntax error")

    with patch("agent.tools.bigquery.Client", return_value=mock_client):
        result = validate_sql_query("INVALID SQL")

    assert result["status"] == "invalid"
    assert "Syntax error" in result["error"]
```

### Writing API Route Tests

Use FastAPI's `TestClient` for endpoint testing.

```python
# tests/test_routes.py
import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint returns healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_create_session(client):
    """Test creating a new session."""
    response = client.post("/api/sessions", json={"name": "Test Session"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Session"


def test_list_sessions(client):
    """Test listing sessions."""
    # Create a session first
    client.post("/api/sessions", json={"name": "Test"})

    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) >= 1


def test_delete_nonexistent_session(client):
    """Test deleting a session that doesn't exist."""
    response = client.delete("/api/sessions/nonexistent-id")
    assert response.status_code == 404
```

### Writing Session Service Tests

```python
# tests/test_session_service.py
import pytest
from services.session_service import SessionService
from api.models import MessageRole

@pytest.fixture
def service():
    """Create a fresh session service for each test."""
    return SessionService()


def test_create_session(service):
    """Test session creation returns valid ID."""
    session_id = service.create_session(name="Test")
    assert session_id is not None
    assert len(session_id) > 0


def test_get_session_info(service):
    """Test retrieving session metadata."""
    session_id = service.create_session(name="Test Session")
    info = service.get_session_info(session_id)
    assert info is not None
    assert info.name == "Test Session"
    assert info.message_count == 0


def test_add_and_get_messages(service):
    """Test adding messages and retrieving them."""
    session_id = service.create_session()
    service.add_message(session_id, MessageRole.USER, "Hello")
    service.add_message(session_id, MessageRole.ASSISTANT, "Hi there!")

    messages = service.get_messages(session_id)
    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT


def test_delete_session(service):
    """Test session deletion."""
    session_id = service.create_session()
    assert service.delete_session(session_id) is True
    assert service.get_session(session_id) is None
```

### Writing Pydantic Model Tests

```python
# tests/test_models.py
import pytest
from api.models import (
    ChatRequest,
    QueryResult,
    ColumnInfo,
    EnrichmentMetadata,
    CalculationMetadata,
    CalculatedColumnInfo,
)

def test_chat_request_validation():
    """Test ChatRequest validates message length."""
    request = ChatRequest(message="Hello")
    assert request.message == "Hello"
    assert request.session_id is None


def test_chat_request_empty_message():
    """Test ChatRequest rejects empty message."""
    with pytest.raises(Exception):
        ChatRequest(message="")


def test_query_result_construction():
    """Test QueryResult with all fields."""
    result = QueryResult(
        columns=[ColumnInfo(name="state", type="STRING")],
        rows=[{"state": "CA"}],
        total_rows=1,
        query_time_ms=100.0,
        sql="SELECT state FROM data",
    )
    assert result.total_rows == 1
    assert result.enrichment_metadata is None
    assert result.calculation_metadata is None


def test_query_result_with_enrichment():
    """Test QueryResult with enrichment metadata."""
    result = QueryResult(
        columns=[
            ColumnInfo(name="state", type="STRING"),
            ColumnInfo(name="_enriched_capital", type="STRING", is_enriched=True),
        ],
        rows=[{"state": "CA", "_enriched_capital": {"value": "Sacramento"}}],
        total_rows=1,
        query_time_ms=100.0,
        sql="SELECT state FROM data",
        enrichment_metadata=EnrichmentMetadata(
            source_column="state",
            enriched_fields=["capital"],
            total_enriched=1,
        ),
    )
    assert result.enrichment_metadata is not None
    assert result.columns[1].is_enriched is True
```

## Frontend Testing (Vitest)

### Setup

Install test dependencies:

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

Add Vitest configuration to `vite.config.ts`:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
});
```

Create the setup file:

```typescript
// src/test/setup.ts
import '@testing-library/jest-dom';
```

Add a test script to `package.json`:

```json
{
  "scripts": {
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage"
  }
}
```

### Directory Structure

```
frontend/src/
├── test/
│   └── setup.ts                      # Test setup and global imports
├── components/
│   ├── Chat/
│   │   ├── ChatPanel.tsx
│   │   ├── ChatPanel.test.tsx         # Component tests alongside source
│   │   ├── MessageInput.tsx
│   │   ├── MessageInput.test.tsx
│   │   ├── MessageList.tsx
│   │   ├── MessageList.test.tsx
│   │   ├── ClarificationPrompt.tsx
│   │   └── ClarificationPrompt.test.tsx
│   └── Results/
│       ├── DataTable.tsx
│       ├── DataTable.test.tsx
│       ├── ResultsPanel.tsx
│       └── ResultsPanel.test.tsx
├── hooks/
│   ├── useChat.ts
│   ├── useChat.test.ts
│   ├── useChartConfig.ts
│   └── useChartConfig.test.ts
└── services/
    ├── api.ts
    └── api.test.ts
```

### Running Tests

```bash
cd frontend
npx vitest              # Watch mode (re-runs on changes)
npx vitest run          # Single run
npx vitest run --coverage  # With coverage report
npx vitest run src/hooks   # Run tests in specific directory
```

### Writing Component Tests

#### Example: Testing MessageInput

```tsx
// src/components/Chat/MessageInput.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MessageInput } from './MessageInput';

describe('MessageInput', () => {
  it('renders with default placeholder', () => {
    render(<MessageInput onSend={vi.fn()} isLoading={false} />);
    expect(screen.getByPlaceholderText('Ask a question about your data...')).toBeInTheDocument();
  });

  it('calls onSend when Enter is pressed', async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('Ask a question about your data...');
    await userEvent.type(textarea, 'Show me sales{enter}');

    expect(onSend).toHaveBeenCalledWith('Show me sales');
  });

  it('does not send empty messages', async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('Ask a question about your data...');
    await userEvent.type(textarea, '{enter}');

    expect(onSend).not.toHaveBeenCalled();
  });

  it('disables input when loading', () => {
    render(<MessageInput onSend={vi.fn()} isLoading={true} />);
    expect(screen.getByPlaceholderText('Ask a question about your data...')).toBeDisabled();
  });

  it('allows new lines with Shift+Enter', async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('Ask a question about your data...');
    await userEvent.type(textarea, 'line 1{shift>}{enter}{/shift}line 2');

    expect(onSend).not.toHaveBeenCalled();
  });
});
```

#### Example: Testing ClarificationPrompt

```tsx
// src/components/Chat/ClarificationPrompt.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ClarificationPrompt } from './ClarificationPrompt';

describe('ClarificationPrompt', () => {
  const mockQuestion = {
    question: 'Which table should I query?',
    options: ['orders', 'customers', 'products'],
    context: 'I found multiple tables.',
  };

  it('renders question and options', () => {
    render(<ClarificationPrompt question={mockQuestion} onSelect={vi.fn()} />);

    expect(screen.getByText('Which table should I query?')).toBeInTheDocument();
    expect(screen.getByText('orders')).toBeInTheDocument();
    expect(screen.getByText('customers')).toBeInTheDocument();
    expect(screen.getByText('products')).toBeInTheDocument();
  });

  it('calls onSelect when option is clicked', async () => {
    const onSelect = vi.fn();
    render(<ClarificationPrompt question={mockQuestion} onSelect={onSelect} />);

    await userEvent.click(screen.getByText('orders'));
    expect(onSelect).toHaveBeenCalledWith('orders');
  });

  it('returns null when no options', () => {
    const { container } = render(
      <ClarificationPrompt
        question={{ question: 'Test?', options: [] }}
        onSelect={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });
});
```

### Writing Hook Tests

#### Example: Testing useChartConfig

```typescript
// src/hooks/useChartConfig.test.ts
import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useChartConfig, getNumericColumns } from './useChartConfig';
import type { QueryResult } from '../types';

const mockQueryResult: QueryResult = {
  columns: [
    { name: 'state', type: 'STRING' },
    { name: 'population', type: 'INTEGER' },
  ],
  rows: [
    { state: 'CA', population: 39500000 },
    { state: 'TX', population: 29100000 },
  ],
  total_rows: 2,
  query_time_ms: 100,
  sql: 'SELECT state, population FROM data',
};

describe('getNumericColumns', () => {
  it('identifies numeric columns', () => {
    const result = getNumericColumns(mockQueryResult.columns);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('population');
  });

  it('includes enriched columns as numeric', () => {
    const columns = [
      { name: 'state', type: 'STRING' },
      { name: '_enriched_pop', type: 'STRING', is_enriched: true },
    ];
    const result = getNumericColumns(columns);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('_enriched_pop');
  });
});

describe('useChartConfig', () => {
  it('returns null for table chart type', () => {
    const { result } = renderHook(() =>
      useChartConfig({ queryResult: mockQueryResult, chartType: 'table' })
    );
    expect(result.current).toBeNull();
  });

  it('generates bar chart config', () => {
    const { result } = renderHook(() =>
      useChartConfig({ queryResult: mockQueryResult, chartType: 'bar' })
    );
    expect(result.current).not.toBeNull();
    expect(result.current).toHaveProperty('xAxis');
    expect(result.current).toHaveProperty('yAxis');
    expect(result.current).toHaveProperty('series');
  });

  it('returns null for empty data', () => {
    const emptyResult = { ...mockQueryResult, rows: [] };
    const { result } = renderHook(() =>
      useChartConfig({ queryResult: emptyResult, chartType: 'bar' })
    );
    expect(result.current).toBeNull();
  });
});
```

### Writing API Service Tests

```typescript
// src/services/api.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api, ApiError } from './api';

describe('api', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('healthCheck returns status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'healthy', version: '1.0.0' }))
    );

    const result = await api.healthCheck();
    expect(result.status).toBe('healthy');
  });

  it('sendMessage sends POST request with correct body', async () => {
    const mockResponse = {
      session_id: 'abc',
      message: { id: '1', role: 'assistant', content: 'Hello' },
      conversation_history: [],
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mockResponse))
    );

    await api.sendMessage('test message', 'session-1');

    expect(fetchSpy).toHaveBeenCalledWith('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'test message', session_id: 'session-1' }),
    });
  });

  it('throws ApiError on non-OK response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: 'Not found' }), { status: 404 })
    );

    await expect(api.healthCheck()).rejects.toThrow(ApiError);
  });
});
```

## Test Coverage

### Priority Areas

Tests should be added in this order of priority:

1. **Agent tools** (`backend/agent/tools.py`) -- Core business logic, most prone to regressions
2. **API routes** (`backend/api/routes.py`) -- Request/response contract with frontend
3. **Pydantic models** (`backend/api/models.py`) -- Data validation correctness
4. **Session service** (`backend/services/session_service.py`) -- State management
5. **Frontend hooks** (`frontend/src/hooks/`) -- State logic separated from rendering
6. **Frontend components** (`frontend/src/components/`) -- User interaction correctness

### What to Mock

| Dependency | How to Mock |
|------------|-------------|
| BigQuery Client | `unittest.mock.patch("agent.tools.bigquery.Client")` |
| Google ADK Runner | `unittest.mock.patch` the Runner class |
| `_last_query_result` global | `unittest.mock.patch("agent.tools._last_query_result", ...)` |
| Fetch API (frontend) | `vi.spyOn(globalThis, 'fetch')` |

### Coverage Goals

| Area | Target |
|------|--------|
| Agent tools | 80%+ |
| API routes | 70%+ |
| Pydantic models | 90%+ |
| Frontend hooks | 70%+ |
| Frontend components | 60%+ |

### Running Coverage Reports

**Backend:**

```bash
cd backend
pip install pytest-cov
pytest --cov=agent --cov=api --cov=services --cov-report=html
# Open htmlcov/index.html in browser
```

**Frontend:**

```bash
cd frontend
npm install -D @vitest/coverage-v8
npx vitest run --coverage
# Coverage report printed to terminal
```

## CI/CD Integration

When setting up CI (e.g., GitHub Actions), a test workflow should:

1. Install dependencies for both backend and frontend
2. Run backend tests with `pytest`
3. Run frontend lint with `npm run lint`
4. Run frontend tests with `npx vitest run`
5. Fail the pipeline if any step fails

Example workflow snippet:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r backend/requirements.txt
      - run: pip install pytest pytest-asyncio httpx pytest-cov
      - run: cd backend && pytest --cov

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npx vitest run
```
