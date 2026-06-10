# ---------------------------------------------------------
# template-python Dockerfile
# Licensed under the Apache License, Version 2.0
# ---------------------------------------------------------
# Standardized Multi-stage Dockerfile Template for Python

# ---------------------------------------------------------
# Build Stage
# ---------------------------------------------------------
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Install system build dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv hatch

# Copy package manifests and install dependencies
COPY pyproject.toml README.md ./
# Create a dummy src directory to satisfy hatch build if needed
RUN mkdir -p src/template_python && touch src/template_python/__init__.py
RUN uv pip install --system --no-cache -e .

# Copy application source code
COPY src/ ./src/

# ---------------------------------------------------------
# Build any required distribution artifacts
# ---------------------------------------------------------
RUN hatch build

# ---------------------------------------------------------
# Runtime Stage
# ---------------------------------------------------------
FROM python:3.10-slim

# OCI Standard Labels
LABEL org.opencontainers.image.title="template-python"
LABEL org.opencontainers.image.description="Production-ready Python application container"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.source="https://github.com/markurtz/template-python"

# Define environment variables
ENV APP_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Create a non-root user and set permissions
RUN useradd -m appuser && chown -R appuser /app

# Install runtime dependencies (or copy from builder if using a virtualenv)
# For simplicity, we copy the project and install it
COPY --from=builder /app/dist/*.whl ./
RUN pip install *.whl && rm *.whl

# Switch to the non-root user for security
USER appuser

# Expose necessary ports
EXPOSE 8080

# Define the command to run the application
CMD ["python", "-m", "template_python"]
