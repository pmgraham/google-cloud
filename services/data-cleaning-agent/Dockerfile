FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies from lock file
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .
RUN uv sync --frozen --no-dev

# Cloud Run entry point
ENV PORT=8080
CMD uv run functions-framework --target=handle_gcs_event --signature-type=cloudevent --port=${PORT}
