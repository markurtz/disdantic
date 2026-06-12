# Copyright 2026 markurtz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# =================================================================-------------
# Stage 1: Build Stage (Python)
# =================================================================-------------
FROM python:3.10-slim-bookworm AS builder

# Set working directory
WORKDIR /app

# Install system dependencies for Python build steps
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python packaging tools
# hadolint ignore=DL3013
RUN pip install --no-cache-dir uv hatch "gitversioned>=0.3.0"

ARG VERSION=0.1.0.dev20260612+da90149

# Copy package manifests
COPY pyproject.toml README.md LICENSE NOTICE Dockerfile ./
COPY scripts/ ./scripts/

# Copy source tree
COPY src/ ./src/


# Build Python wheel distributions
# hadolint ignore=DL3059
RUN hatch build


# =================================================================-------------
# Stage 2: Runtime Stage (Minimal & Secure)
# =================================================================-------------
FROM python:3.10-slim-bookworm

# Define standard OCI build parameters
ARG BUILD_DATE
ARG GIT_SHA
ARG VERSION=0.1.0.dev20260612+da90149

# OCI Metadata Labels
LABEL org.opencontainers.image.created=$BUILD_DATE \
      org.opencontainers.image.authors="markurtz" \
      org.opencontainers.image.url="https://github.com/markurtz/disdantic" \
      org.opencontainers.image.documentation="https://markurtz.github.io/disdantic/" \
      org.opencontainers.image.source="https://github.com/markurtz/disdantic" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$GIT_SHA \
      org.opencontainers.image.vendor="markurtz" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.title="disdantic" \
      org.opencontainers.image.description="The missing polymorphic engine for Pydantic"

# Define standard production runtime environment variables
ENV APP_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Create a secure, non-root system user and home directory
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -m -d /home/appuser -s /sbin/nologin appuser

# Copy sdist/wheel package from builder and install it
COPY --from=builder /app/dist/*.whl ./
# hadolint ignore=DL3013,SC2035
RUN pip install --no-cache-dir *.whl && rm -- *.whl

# Change ownership of the runtime directory to appuser
RUN chown -R appuser:appgroup /app

# Switch to the secure non-root user
USER appuser

# Expose production port
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -m disdantic --version || exit 1

# Run the installed application entrypoint
CMD ["python", "-m", "disdantic"]
