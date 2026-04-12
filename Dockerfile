# Dockerfile for E2E testing (lightweight, no persistent DB)
FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy dependency files first (better layer caching)
COPY pyproject.toml poetry.lock ./

# Install dependencies (no dev deps for smaller image)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy application code
COPY taskmanagement_app ./taskmanagement_app
COPY alembic.ini ./

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "taskmanagement_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
