# Developing `template-python`

This guide provides instructions for setting up your development environment, navigating the project structure, and adhering to our coding standards.

## Prerequisites

Ensure your system meets the following requirements before getting started:

- **[Docker](https://docs.docker.com/get-docker/)** (Recommended for isolated environments)
- **[Git](https://git-scm.com/)** (Version control)
- **[Python](https://www.python.org/)** 3.10+
- **[Hatch](https://hatch.pypa.io/)** (Project manager)

> [!NOTE]
> We strongly recommend using our Docker setup to ensure your local environment exactly matches our CI/CD pipelines.

## Quick Start (Docker)

> [!IMPORTANT]
> The `Dockerfile` and `docker-compose.yml` files included in this template are **placeholders** that must be filled in for your specific language stack before they are usable. The default `CMD` in both files will exit with an error if run without modification.
>
> Once implemented, you can spin up the development environment with:
>
> ```bash
> git clone https://github.com/markurtz/template-python.git
> cd template-python
>
> # Build and start the development environment in the background
> docker-compose up -d --build
> ```

To view the logs of your running containers:

```bash
docker-compose logs -f
```

## Local Setup

If you prefer to develop directly on your host machine, this project uses [uv](https://docs.astral.sh/uv/) for environment management and dependency resolution, alongside [Hatch](https://hatch.pypa.io/) as our command orchestrator.

> [!NOTE]
> **A note on shared tooling:** This project uses [MkDocs](https://www.mkdocs.org/) for documentation.

```bash
# 1. Install uv and hatch globally (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install hatch

# 2. Optionally, set up a Python virtual environment
uv venv
source .venv/bin/activate

# 3. Sync the development environment (installs all dependency groups and extras)
uv sync --all-groups --all-extras

# 4. Run hatch commands directly
hatch run test:all
hatch run lint:check
```

### Managing Dependencies

Use `uv` to add or update dependencies efficiently:

```bash
# Add a general dependency
uv add <package>

# Add a development dependency
uv add --group dev <package>

# Add to a specific extra
uv add <package> --optional <extra_name>

# Sync targeted groups or extras
uv sync --group dev
uv sync --extra <extra_name>
```

## Running Tests

We maintain strict testing standards. Our tests are located in the `tests/` directory and are categorized by tier.

| Test Tier       | Directory            | Description                                                        |
| :-------------- | :------------------- | :----------------------------------------------------------------- |
| **Unit**        | `tests/unit/`        | Fast, isolated tests for individual functions and classes.         |
| **Integration** | `tests/integration/` | Slower tests that verify interactions between multiple components. |
| **End-to-End**  | `tests/e2e/`         | Full-stack tests simulating real user workflows.                   |

Replace the commands below with those appropriate for your language stack:

```bash
# Run unit tests
hatch run test:unit

# Run integration tests
hatch run test:integration

# Run all tests with coverage
hatch run test:all-cov
```

## Code Quality and Formatting

We use opinionated formatters and linters to maintain consistency: Ruff for linting/formatting and Mypy for static type checking.

- **Formatters & Linters:**
  ```bash
  # Check for linting and formatting issues
  hatch run lint:check
  hatch run types:check

  # Auto-format code
  hatch run lint:format
  ```

> [!TIP]
> **IDE Configuration:** We highly recommend configuring your editor (e.g., VSCode, IntelliJ) to format on save using the project's formatting tools. For VSCode, ensure you have the relevant extensions installed and check `.vscode/settings.json` if available.

### Pre-commit Hooks

We use [pre-commit](https://pre-commit.com/) to ensure code quality standards are met before changes are committed. This repository is configured to use our existing Hatch environments for these checks, guaranteeing consistency with CI/CD pipelines.

**Setup:**

1. Install pre-commit globally or in your local virtual environment:

   ```bash
   uv pip install pre-commit
   ```

1. Install the git hook scripts:

   ```bash
   pre-commit install
   ```

**Usage:**

Once installed, pre-commit will automatically run on the modified files whenever you commit. To run the hooks manually on all files:

```bash
pre-commit run --all-files
```

## Git Workflow & Branching

We follow a structured branching strategy to maintain a clean git history.

1. **Branch Naming:**

   - Feature branches: `feature/short-description`
   - Bug fixes: `bugfix/short-description`
   - Documentation: `docs/short-description`

1. **Commit Messages:**
   We encourage following [Conventional Commits](https://www.conventionalcommits.org/).

   - `feat: add new user endpoint`
   - `fix: resolve crash on startup`
   - `docs: update developing guide`

1. **Pull Requests:**

   - Push your branch to the remote repository.
   - Open a Pull Request against the `main` branch.
   - Ensure all CI checks (tests, linters) pass.
   - Request a review from at least one core maintainer.

## CI/CD Architecture

This repository uses a modular, standardized GitHub Actions architecture. Workflows are divided into core lifecycle events and reusable helper templates.

### Lifecycle Workflows

| Workflow                            | Trigger                | Purpose                                                                                                                       |
| :---------------------------------- | :--------------------- | :---------------------------------------------------------------------------------------------------------------------------- |
| **Development** (`development.yml`) | Pull Request to `main` | Runs quality gates, security audits, unit/integration tests, and builds documentation previews. Blocks merges if checks fail. |
| **Main** (`main.yml`)               | Push to `main`         | Post-merge validation. Runs unit/integration/e2e tests, quality/security checks, and updates the `latest` documentation.      |
| **Nightly** (`nightly.yml`)         | Cron (Daily 00:00 UTC) | Runs extended regression tests, alpha builds, nightly documentation deployment, and deeper security analysis.                 |
| **Release** (`release.yml`)         | Push of `v*.*.*` tag   | Performs full verification, builds immutable release packages, versioned documentation, and publishes artifacts.              |
| **Weekly** (`weekly.yml`)           | Cron (Sun 00:00 UTC)   | Conducts dependency hygiene and full test suite regression to catch configuration drift.                                      |

### PR Feedback & Cleanup

- **Safe PR Commenting:** The `pr_comment.yml` workflow uses `workflow_run` to securely post CI status comments on pull requests, circumventing write permission limits on forks.
- **Environment Cleanup:** When a PR is closed or merged, `development_cleanup.yml` automatically removes ephemeral documentation environments and artifacts to maintain a clean workspace.

### Reusable Templates

Our pipelines rely on modular templates located in `.github/workflows/_*.yml` (e.g., `_tests.yml`, `_quality.yml`, `_docs.yml`, `_security.yml`, `_build_package.yml`). This ensures testing granularity and linting rules remain perfectly consistent across all stages of the software lifecycle.

## Building Documentation

Our documentation is built using [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To preview documentation changes locally:

```bash
# Hatch manages the isolated docs environment
# Serve documentation on http://127.0.0.1:8000 with hot-reload
hatch run docs:serve
```

For further assistance, please refer to our [SUPPORT.md](SUPPORT.md).
