# Data Insights Agent

> **Early Stage Development**: This project is in very early stage development and is intended for demonstration and experimental purposes only. It is not production-ready and APIs, features, and architecture may change significantly. Use at your own risk.

An AI-powered data analysis tool that enables users to query BigQuery data using natural language. Built with Google ADK (Agent Development Kit), FastAPI, React, and Apache ECharts.

## Features

- **Natural Language Queries**: Ask questions about your data in plain English
- **Smart SQL Generation**: Automatically converts questions to optimized SQL
- **Data Enrichment**: Augment query results with real-time data from Google Search
- **Calculated Columns**: Derive new values from existing and enriched data without re-querying
- **Uncertainty Handling**: Agent asks clarifying questions when queries are ambiguous
- **Proactive Insights**: Automatically surfaces trends, anomalies, and suggestions
- **Interactive Visualizations**: Toggle between table, bar, line, area, and pie charts
- **SQL Transparency**: View the generated SQL for every query
- **CSV Export**: Download query results for further analysis

## Prerequisites

- Python 3.11+ (with `uv` recommended for package management)
- Node.js 18+
- Google Cloud Project with:
  - BigQuery API enabled
  - Vertex AI API enabled
  - A BigQuery dataset with data to query
- Google Cloud authentication configured (ADC recommended)

## Quick Start

### 1. Clone and Configure

```bash
cd data-insights-agent

# Backend configuration
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your settings:
```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=global
BIGQUERY_DATASET=your_dataset_name
```

### 2. Set Up Google Cloud Authentication

```bash
gcloud auth application-default login
```

### 3. Install and Run Backend

```bash
cd backend

# Using uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh #optional if not installed
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Or using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the server
uvicorn api.main:app --host 0.0.0.0 --port 8088 --reload
# Or simply use:
# python run.py
```

### 4. Install and Run Frontend

In a new terminal:
```bash
cd frontend
npm install
npm run dev
```

### 5. Access the Application

Open http://localhost:5173 in your browser.

## Usage Examples

Try these queries:

- "What tables are available?"
- "Show me all data from the states table"
- "How many chipotle stores are in California?"
- "Show me the top 10 movies by rating"

The agent will:
1. Understand your question
2. Ask for clarification if needed
3. Generate and execute the SQL query
4. Present results in an interactive data table
5. Allow you to visualize data as charts (bar, line, pie, area)

## Project Structure

```
data-insights-agent/
├── backend/
│   ├── agent/              # ADK agent configuration
│   │   ├── agent.py        # Main agent definition
│   │   ├── config.py       # Configuration management
│   │   ├── prompts.py      # System prompts
│   │   ├── tools.py        # Custom BigQuery tools
│   │   └── enrichment/     # Enrichment sub-agent
│   ├── api/                # FastAPI routes and models
│   ├── services/           # Session management
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── Chat/       # Chat interface
│   │   │   ├── Results/    # Results panel & charts
│   │   │   └── Layout/     # App layout
│   │   ├── hooks/          # Custom React hooks
│   │   ├── services/       # API client
│   │   └── types/          # TypeScript types
│   └── package.json
├── docs/                   # Project documentation
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Send a message to the agent |
| `/api/sessions` | GET/POST | List or create chat sessions |
| `/api/schema/tables` | GET | List available tables |

## Configuration

### Backend Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | - | GCP project ID |
| `BIGQUERY_DATASET` | Yes | - | Default BigQuery dataset |
| `GOOGLE_CLOUD_REGION` | No | global | Vertex AI region |
| `PORT` | No | 8088 | Server port |
| `DEBUG` | No | true | Enable debug mode |
| `CORS_ORIGINS` | No | localhost:5173 | Allowed CORS origins |

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | How to use the application (queries, charts, enrichment, export) |
| [Architecture](docs/ARCHITECTURE.md) | System design, data flow, and design decisions |
| [API Reference](docs/API.md) | Complete API endpoint documentation |
| [Configuration](docs/CONFIGURATION.md) | All environment variables and settings |
| [Development](docs/DEVELOPMENT.md) | How-to guides for adding features and extending the system |
| [Deployment](docs/DEPLOYMENT.md) | Local, Docker, and Cloud Run deployment |
| [Testing](docs/TESTING.md) | Testing strategy and example tests |
| [Security](docs/SECURITY.md) | Security considerations and production hardening |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Contributing](CONTRIBUTING.md) | Code style, Git workflow, and PR process |

## Troubleshooting

See the [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for comprehensive solutions. Common issues:

### "Permission denied" errors
- Ensure your GCP credentials have BigQuery Data Viewer and Vertex AI User roles
- Run `gcloud auth application-default login` again

### Agent not responding
- Verify Vertex AI API is enabled in your project
- Check the backend logs for error details

### Model not found errors
- Ensure `GOOGLE_CLOUD_REGION=global` in your `.env` file
- The app uses `gemini-3-flash-preview` model

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for code style guidelines, Git workflow, and pull request process.

## Disclaimer

This software is provided as-is for demonstration and educational purposes. It is in early stage development and should not be used in production environments. The authors make no warranties about the suitability of this software for any purpose.

## License

MIT License
