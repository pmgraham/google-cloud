# Contributing to Data Insights Agent

Thank you for your interest in contributing to the Data Insights Agent. This guide covers the conventions, workflows, and standards we use.

> **Note**: This project is in early stage development. Contribution processes may evolve as the project matures.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Environment](#development-environment)
3. [Code Style](#code-style)
4. [Git Workflow](#git-workflow)
5. [Pull Request Process](#pull-request-process)
6. [Documentation Standards](#documentation-standards)
7. [Adding Features](#adding-features)
8. [Reporting Issues](#reporting-issues)

---

## Getting Started

1. **Fork the repository** and clone your fork
2. **Set up your development environment** following the [Development Guide](docs/DEVELOPMENT.md)
3. **Read the [Architecture Guide](docs/ARCHITECTURE.md)** to understand the system design
4. **Check open issues** for tasks to work on

---

## Development Environment

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google Cloud Project with BigQuery and Vertex AI APIs enabled
- `uv` (recommended) or `pip` for Python packages

### Setup

```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your GCP project and dataset
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### Running Locally

```bash
# Terminal 1: Backend
cd backend && python run.py

# Terminal 2: Frontend
cd frontend && npm run dev
```

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed setup instructions including Docker and Cloud Run options.

---

## Code Style

### Python (Backend)

- **Style guide**: PEP 8
- **Line length**: 100 characters maximum
- **Formatting**: Use consistent formatting with your editor's Python formatter
- **Type hints**: Required on all function signatures
- **Docstrings**: Google-style docstrings on all public functions

```python
def execute_query(sql: str, max_rows: int = 1000) -> dict[str, Any]:
    """Execute a SQL query against BigQuery and return results.

    Args:
        sql: The SQL query string to execute.
        max_rows: Maximum number of rows to return. Defaults to 1000.

    Returns:
        A dictionary containing columns, rows, total_rows, query_time_ms,
        and the executed SQL string.

    Raises:
        ValueError: If the SQL string is empty.
        google.api_core.exceptions.BadRequest: If the SQL is invalid.
    """
```

**Naming conventions**:
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private/internal: prefix with `_` (e.g., `_schema_cache`, `_last_query_result`)

**Import ordering**:
1. Standard library imports
2. Third-party imports
3. Local imports

```python
import json
from typing import Any

from google.cloud import bigquery
from fastapi import APIRouter

from .config import settings
```

### TypeScript (Frontend)

- **Linting**: ESLint with the project's existing configuration
- **Formatting**: Follow the existing codebase conventions
- **Type safety**: Avoid `any` where possible; use proper TypeScript types
- **Components**: Functional components with hooks

```typescript
// Props interfaces above components
interface MessageInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

// Functional components with explicit return types
const MessageInput: React.FC<MessageInputProps> = ({ onSend, isLoading }) => {
  // ...
};
```

**Naming conventions**:
- Components: `PascalCase` (files and identifiers)
- Hooks: `camelCase` with `use` prefix (e.g., `useChat`)
- Types/Interfaces: `PascalCase`
- Variables and functions: `camelCase`
- Constants: `UPPER_SNAKE_CASE` or `camelCase` depending on scope

**Run the linter before committing**:
```bash
cd frontend && npm run lint
```

---

## Git Workflow

### Branch Naming

Use descriptive branch names with a category prefix:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New functionality | `feature/streaming-responses` |
| `fix/` | Bug fixes | `fix/session-persistence` |
| `refactor/` | Code restructuring | `refactor/tool-registry` |
| `docs/` | Documentation changes | `docs/api-reference` |
| `chore/` | Maintenance tasks | `chore/update-dependencies` |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Scopes**: `agent`, `api`, `frontend`, `tools`, `enrichment`, `config`, `deps`

**Examples**:
```
feat(agent): add table row count to schema tool response
fix(api): handle missing session gracefully in chat endpoint
docs(api): add WebSocket endpoint documentation
refactor(tools): extract query validation into separate function
test(frontend): add unit tests for useChartConfig hook
```

### Keeping Your Branch Updated

```bash
git fetch origin
git rebase origin/main
```

---

## Pull Request Process

### Before Submitting

1. **Ensure your code follows the style guidelines** described above
2. **Run the frontend linter**: `cd frontend && npm run lint`
3. **Test your changes manually** -- verify the feature works end-to-end
4. **Update documentation** if your change affects:
   - API endpoints (update `docs/API.md`)
   - Configuration (update `docs/CONFIGURATION.md`)
   - Architecture (update `docs/ARCHITECTURE.md`)
   - Agent tools or prompts (update `CLAUDE.md`)

### PR Template

```markdown
## Summary

Brief description of the changes.

## Changes

- List of specific changes made

## Testing

- How the changes were tested
- Steps to reproduce / verify

## Documentation

- [ ] Updated relevant docs
- [ ] Updated CLAUDE.md if architecture changed
```

### Review Checklist

Reviewers will check for:

- [ ] Code follows project style guidelines
- [ ] No security vulnerabilities introduced (see [SECURITY.md](docs/SECURITY.md))
- [ ] No hardcoded credentials or secrets
- [ ] Error handling is appropriate
- [ ] Changes are documented where needed
- [ ] No unnecessary dependencies added

---

## Documentation Standards

### Markdown Files

- Use ATX-style headers (`#`, `##`, `###`)
- Include a table of contents for documents longer than 3 sections
- Use fenced code blocks with language identifiers
- Use tables for structured comparisons
- End files with a single newline

### Python Docstrings

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> dict:
    """Short description of the function.

    Longer description if needed, explaining behavior,
    side effects, or important details.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of the return value.

    Raises:
        ValueError: When param1 is empty.
    """
```

### TypeScript/JSDoc

Use JSDoc for complex functions and exported utilities:

```typescript
/**
 * Extract a numeric value from a cell that may be a primitive or enriched object.
 * @param value - The cell value (number, string, or enriched object with .value)
 * @returns The numeric value, or null if not numeric
 */
export function extractNumericValue(value: unknown): number | null {
  // ...
}
```

---

## Adding Features

### Adding a New Agent Tool

1. Define the function in `backend/agent/tools.py` with type hints and a docstring
2. Add it to the `CUSTOM_TOOLS` list at the bottom of the file
3. Document the tool in `backend/agent/prompts.py` SYSTEM_INSTRUCTION
4. Test by sending a natural language query that should trigger the tool

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed how-to guides.

### Adding a New API Endpoint

1. Add the route in `backend/api/routes.py`
2. Define request/response models in `backend/api/models.py`
3. Document in `docs/API.md`
4. Update the frontend API service in `frontend/src/services/api.ts`

### Adding a Frontend Component

1. Create the component in the appropriate subdirectory under `frontend/src/components/`
2. Define a props interface if the component accepts props
3. Use existing hooks (`useChat`, `useChartConfig`) for state management
4. Follow the existing patterns in sibling components

### Adding a New Chart Type

1. Update `ChartView.tsx` to handle the new chart type
2. Add configuration logic in `useChartConfig.ts`
3. Add the chart type to the `ChartType` union in `frontend/src/types/index.ts`

---

## Reporting Issues

### Bug Reports

Include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (OS, Python version, Node version, browser)
- Relevant logs or error messages (sanitize any credentials)

### Feature Requests

Include:
- Problem description (what you're trying to solve)
- Proposed solution
- Alternatives considered
- Whether you'd be willing to implement it

---

## Related Documentation

- [Development Guide](docs/DEVELOPMENT.md) -- Detailed setup and how-to guides
- [Architecture Guide](docs/ARCHITECTURE.md) -- System design and data flow
- [API Reference](docs/API.md) -- Endpoint documentation
- [Configuration Guide](docs/CONFIGURATION.md) -- Environment variables
- [Security Guide](docs/SECURITY.md) -- Security considerations
- [Testing Guide](docs/TESTING.md) -- Testing strategy and examples

---

*Last updated: February 2026*
