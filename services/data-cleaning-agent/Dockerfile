FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependencies
COPY pyproject.toml .
# No lock file for now to avoid platform issues
RUN uv pip install -r pyproject.toml --system

# Copy application code
COPY . .

# Cloud Run entry point
ENV PORT=8080
CMD exec functions-framework --target=handle_gcs_event --signature-type=cloudevent --port=${PORT}
