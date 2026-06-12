<!--
Copyright 2026 markurtz

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# AGENTS.md — AI Agent & Coding Assistant Guide

This file provides repository-specific context, setup instructions, executable commands, and security boundaries for AI coding assistants.

## System Overview

`disdantic` is the missing polymorphic engine for Pydantic. It simplifies registries and discriminated unions with automatic model discovery and auto-importing, helping you manage polymorphic data shapes with less boilerplate.

- **Primary Languages:** Python 3.10+
- **Configuration & Build Backend:** Hatch
- **Key Dependencies:** Loguru, Pydantic / Pydantic-Settings v2, Typer, Opentelemetry

## Core Directories & Architecture

- `src/disdantic/`: Python interface and orchestrator client.
  - `__main__.py`: CLI entrypoint (subcommands: `diagnose`, `setup`).
  - `settings.py`: Pydantic settings schema for project options.
  - `client.py`: Process client wrapper.
  - `logging.py`: Loguru logging and telemetry hooks.
- `tests/`: Organized into `python/unit/` (isolated logic), `python/integration/` (subsystem interactions), and `e2e/` (orchestrator black-box integration).
- `docs/`: MkDocs Material documentation source using Zensical.
- `.github/workflows/`: CI/CD workflows.

## Environment & Developer Workflows

This project is configured to run using Hatch environments. Use the local `.venv` for all executions as instructed by the user.

### 1. Setup & Bootstrapping

Activate the environment and initialize Hatch:

```bash
# Set up/update dependencies via Hatch inside virtualenv wrapper
.venv/bin/hatch env create
```

### 2. Testing Pipeline

Tests are tiered across languages. Run targeted tests or full suite:

```bash
# Run all Python functional tests (unit + integration)
.venv/bin/hatch run python:tests-func

# Run Python unit tests only
.venv/bin/hatch run python:tests-unit

# Run Python integration tests only
.venv/bin/hatch run python:tests-int

# Run OCI Container Structure Tests (CST)
.venv/bin/hatch run oci:tests

# Run E2E tests (builds dist wheel and installs it first)
.venv/bin/hatch run project:tests-e2e

# Run all tests with coverage reports
.venv/bin/hatch run tests-cov
```

### 3. Code Quality, Formatting & Types

Run formatting and quality gates before committing:

```bash
# Auto-format Python and project configuration files
.venv/bin/hatch run python:format
.venv/bin/hatch run project:format

# Run lint checks (Ruff, mdformat, yamlfix, taplo)
.venv/bin/hatch run python:lint
.venv/bin/hatch run project:lint

# Run static type checks (Mypy via Ty for Python)
.venv/bin/hatch run python:types
```

### 4. Documentation & Packaging

```bash
# Build and serve docs locally (http://127.0.0.1:8000)
.venv/bin/hatch run project:docs-serve

# Build package distributions (sdist and wheel)
.venv/bin/hatch build
```

## Security & Behavior Boundaries

To maintain project integrity and security, agents must strictly adhere to the following rules:

### 1. Secrets & Credentials

- **Never commit secrets:** Never add API keys, tokens, or credentials anywhere.
- Run security audits using: `.venv/bin/hatch run project:security`.

### 2. Critical Files & CI Guardrails

- **Do not modify `LICENSE` or `NOTICE`.**
- **Do not modify GitHub Actions workflow triggers or steps** (in `.github/`) without explicit human review.
- **Apache 2.0 copyright header:** Every new source file (Python) must begin with the standard Apache 2.0 copyright and license notice.

### 3. Execution Constraints

- Always use tools installed in the `.venv` (e.g. `.venv/bin/hatch`, `.venv/bin/pytest`).
- Avoid global packages or running unverified external binaries.
- Do not add new external dependencies to `pyproject.toml` without verifying compatibility with Python 3.10+.
