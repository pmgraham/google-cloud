"""Application configuration management using Pydantic Settings.

This module defines all configuration settings for the Data Insights Agent backend,
loaded from environment variables with validation and type checking via Pydantic.

Environment variables can be set in:
1. `.env` file in the backend directory (for local development)
2. System environment variables (for production deployment)
3. Container environment (for Docker/Kubernetes)

**Required Environment Variables**:
- GOOGLE_CLOUD_PROJECT: GCP project ID containing BigQuery datasets
- BIGQUERY_DATASET: Default BigQuery dataset to query

**Optional Environment Variables** (with defaults):
- GOOGLE_CLOUD_REGION: Vertex AI region (default: "us-central1")
- HOST: Server bind address (default: "0.0.0.0")
- PORT: Server port (default: 8000)
- DEBUG: Enable debug/reload mode (default: False)
- CORS_ORIGINS: Comma-separated allowed origins (default: localhost:5173,localhost:3000)

Example `.env` file:
    GOOGLE_CLOUD_PROJECT=my-project-id
    BIGQUERY_DATASET=analytics
    GOOGLE_CLOUD_REGION=us-central1
    PORT=8088
    DEBUG=true
    CORS_ORIGINS=http://localhost:5173,http://localhost:3000

Usage:
    >>> from agent.config import settings
    >>> settings.google_cloud_project
    'my-project-id'
    >>> settings.cors_origins_list
    ['http://localhost:5173', 'http://localhost:3000']
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables with validation.

    Uses Pydantic Settings for automatic environment variable loading, type validation,
    and default value management. Configuration is immutable after initialization.

    All settings are loaded from environment variables or `.env` file. Required fields
    will raise validation errors if not provided.
    """

    # ========== Google Cloud Configuration ==========
    google_cloud_project: str = Field(
        ...,
        env="GOOGLE_CLOUD_PROJECT",
        description=(
            "GCP project ID containing BigQuery datasets and Vertex AI resources. "
            "REQUIRED. Example: 'my-analytics-project'. "
            "Used for: BigQuery API calls, Vertex AI model access, ADC authentication."
        )
    )

    google_cloud_region: str = Field(
        default="us-central1",
        env="GOOGLE_CLOUD_REGION",
        description=(
            "GCP region for Vertex AI API calls. "
            "IMPORTANT: Use 'global' for gemini-3-flash-preview model availability. "
            "Default: 'us-central1'. "
            "Note: README suggests 'global', but code defaults to 'us-central1'. "
            "Verify model availability in your chosen region."
        )
    )

    # ========== BigQuery Configuration ==========
    bigquery_dataset: str = Field(
        ...,
        env="BIGQUERY_DATASET",
        description=(
            "Default BigQuery dataset to query. "
            "REQUIRED. Example: 'analytics' or 'public_data'. "
            "Fully qualified table names: {project}.{dataset}.{table}. "
            "Agent will use this as the default dataset for all queries."
        )
    )

    # ========== Server Configuration ==========
    host: str = Field(
        default="0.0.0.0",
        env="HOST",
        description=(
            "Server bind address. "
            "Default: '0.0.0.0' (all interfaces, needed for Docker). "
            "For local-only: '127.0.0.1' or 'localhost'. "
            "Production: Keep '0.0.0.0' with proper firewall rules."
        )
    )

    port: int = Field(
        default=8000,
        env="PORT",
        description=(
            "Server port for FastAPI application. "
            "Default: 8000. "
            "Note: README examples use 8088, but code defaults to 8000. "
            "Set PORT=8088 in .env to match README instructions."
        )
    )

    debug: bool = Field(
        default=False,
        env="DEBUG",
        description=(
            "Enable debug mode with auto-reload. "
            "Default: False. "
            "When True: Uvicorn reloads on code changes (for development). "
            "When False: Production mode, no auto-reload. "
            "NEVER enable in production (performance and security impact)."
        )
    )

    # ========== CORS Configuration ==========
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        env="CORS_ORIGINS",
        description=(
            "Comma-separated list of allowed CORS origins. "
            "Default: 'http://localhost:5173,http://localhost:3000' (Vite dev + React dev). "
            "For production, set to your frontend domain(s). "
            "Example: 'https://myapp.com,https://www.myapp.com'. "
            "Wildcards not supported for security reasons."
        )
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list.

        Splits the cors_origins string by commas and strips whitespace from each origin.

        Returns:
            list[str]: List of allowed origin URLs.

        Examples:
            >>> settings.cors_origins = "http://localhost:5173, http://localhost:3000"
            >>> settings.cors_origins_list
            ['http://localhost:5173', 'http://localhost:3000']
        """
        return [origin.strip() for origin in self.cors_origins.split(",")]  # pylint: disable=no-member

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic configuration for Settings class."""
        env_file = ".env"
        env_file_encoding = "utf-8"


# pylint: disable=pointless-string-statement
"""Global settings instance loaded from environment variables.

This is the primary configuration object used throughout the application.
Import and use this instance in all modules that need configuration.

**Initialization**:
Settings are loaded when this module is first imported. Validation errors
will be raised immediately if required environment variables are missing.

**Immutability**:
Settings are immutable after initialization (Pydantic BaseSettings behavior).
Do not attempt to modify settings at runtime.

Example:
    >>> from agent.config import settings
    >>> print(f"Connecting to project: {settings.google_cloud_project}")
    >>> print(f"Querying dataset: {settings.bigquery_dataset}")

Troubleshooting:
    - "Field required" error: Set the required environment variable in .env
    - "Extra values" warning: Remove unknown environment variables
    - Region mismatch: Ensure GOOGLE_CLOUD_REGION matches model availability
"""
settings = Settings()
