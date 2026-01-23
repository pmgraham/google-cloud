# Data Insights Agent

> **Early Stage Development**: This project is in very early stage development and is intended for demonstration and experimental purposes only. It is not production-ready and APIs, features, and architecture may change significantly. Use at your own risk.

An AI-powered data analysis tool that enables users to query BigQuery data using natural language. Built with Google ADK (Agent Development Kit), FastAPI, React, and Apache ECharts.

## Features

- **Natural Language Queries**: Ask questions about your data in plain English
- **Smart SQL Generation**: Automatically converts questions to optimized SQL
- **Uncertainty Handling**: Agent asks clarifying questions when queries are ambiguous
- **Proactive Insights**: Automatically surfaces trends, anomalies, and suggestions
- **Interactive Visualizations**: Toggle between table, bar, line, area, and pie charts
- **SQL Transparency**: View the generated SQL for every query
- **Auto-display Results**: Query results automatically appear in a side panel

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
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Or using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8088 --reload
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
│   ├── agent/           # ADK agent configuration
│   │   ├── agent.py     # Main agent definition
│   │   ├── config.py    # Configuration management
│   │   ├── prompts.py   # System prompts
│   │   └── tools.py     # Custom BigQuery tools
│   ├── api/             # FastAPI routes and models
│   ├── services/        # Session management
│   ├── main.py          # Application entry point
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/  # React components
│   │   │   ├── Chat/    # Chat interface
│   │   │   ├── Results/ # Results panel & charts
│   │   │   └── Layout/  # App layout
│   │   ├── hooks/       # Custom React hooks
│   │   └── types/       # TypeScript types
│   └── package.json
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

## Troubleshooting

### "Permission denied" errors
- Ensure your GCP credentials have BigQuery Data Viewer and Vertex AI User roles
- Run `gcloud auth application-default login` again

### Agent not responding
- Verify Vertex AI API is enabled in your project
- Check the backend logs: `tail -f /tmp/backend.log`

### Model not found errors
- Ensure `GOOGLE_CLOUD_REGION=global` in your `.env` file
- The app uses `gemini-3-flash-preview` model

## Disclaimer

This software is provided as-is for demonstration and educational purposes. It is in early stage development and should not be used in production environments. The authors make no warranties about the suitability of this software for any purpose.

## License

MIT License
