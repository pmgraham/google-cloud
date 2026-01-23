#!/usr/bin/env python3
"""Application entry point for the Data Insights Agent backend server.

This script starts the FastAPI application using Uvicorn ASGI server with
configuration loaded from environment variables (.env file).

**Usage**:
    # Development mode (with auto-reload)
    python run.py

    # Production mode (set DEBUG=false in .env)
    python run.py

    # Direct uvicorn invocation (alternative)
    uvicorn api.main:app --host 0.0.0.0 --port 8088 --reload

**Environment Variables**:
Loaded from `.env` file in the backend directory:
- GOOGLE_CLOUD_PROJECT (required): GCP project ID
- BIGQUERY_DATASET (required): Default BigQuery dataset
- GOOGLE_CLOUD_REGION (optional): Vertex AI region (default: us-central1)
- HOST (optional): Server bind address (default: 0.0.0.0)
- PORT (optional): Server port (default: 8000)
- DEBUG (optional): Enable auto-reload (default: false)
- CORS_ORIGINS (optional): Allowed CORS origins (default: localhost:5173,localhost:3000)

**Startup Sequence**:
1. Load environment variables from .env file
2. Import settings to validate configuration
3. Display server configuration
4. Start Uvicorn server with FastAPI app

**Important**:
- Ensure `.env` file exists with required variables before running
- Application Default Credentials (ADC) must be configured for GCP access:
  `gcloud auth application-default login`
- Auto-reload (DEBUG=true) should only be used in development

**Troubleshooting**:
- "Field required" error: Missing required environment variable in .env
- "Permission denied": Check firewall rules or use different port
- "Model not found": Verify GOOGLE_CLOUD_REGION has gemini-3-flash-preview available

Examples:
    >>> # Run with default settings from .env
    >>> python run.py

    >>> # Check configuration before starting (import only)
    >>> from agent.config import settings
    >>> print(settings.google_cloud_project)
"""

import uvicorn
from dotenv import load_dotenv

# ========== STEP 1: Load Environment Variables ==========
# Load .env file from current directory into os.environ
# This must happen BEFORE importing settings to ensure Pydantic reads the values
load_dotenv()

# ========== STEP 2: Main Entry Point ==========
# Only execute when script is run directly (not when imported as module)
if __name__ == "__main__":
    # Import settings after dotenv load to ensure .env values are read
    from agent.config import settings

    # ========== STEP 3: Display Configuration ==========
    # Print startup banner with key configuration details for debugging
    print("=" * 50)
    print("Data Insights Agent Backend")
    print("=" * 50)
    print(f"Project: {settings.google_cloud_project}")
    print(f"Dataset: {settings.bigquery_dataset}")
    print(f"Region: {settings.google_cloud_region}")
    print(f"Server: http://{settings.host}:{settings.port}")
    print(f"Docs: http://{settings.host}:{settings.port}/docs")
    print("=" * 50)

    # ========== STEP 4: Start Uvicorn Server ==========
    # Launch FastAPI application with Uvicorn ASGI server
    #
    # Parameters:
    # - "api.main:app": Module path to FastAPI app instance (lazy import)
    # - host: Bind address (0.0.0.0 = all interfaces, needed for Docker)
    # - port: TCP port for HTTP server
    # - reload: Auto-reload on code changes (development only, slower)
    #
    # Note: Using string import "api.main:app" instead of direct import allows
    # Uvicorn to reload the app when files change (when reload=True)
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
