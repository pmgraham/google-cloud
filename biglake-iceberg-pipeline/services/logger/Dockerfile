FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependencies
COPY pyproject.toml .
RUN uv pip install -r pyproject.toml --system

# Copy application code
COPY . .

# Cloud Run entry point
ENV PORT=8080
CMD exec gunicorn --bind :${PORT} --workers 1 --threads 8 --timeout 0 main:app
