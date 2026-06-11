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

# Developing `disdantic`

This guide provides instructions for setting up your development environment, navigating the project structure, and adhering to our coding standards.

## Setup & Prerequisites

Ensure your system meets the requirements below to establish a consistent local development environment, or utilize our containerized development setup.

### Supported Operating Systems

- **macOS & Linux**: Standard operating systems that are fully supported, actively tested, and maintained.
- **Windows**: Not officially tested or maintained. Windows users encountering issues should use the [Development Environment Container](#development-environment-container-devcontainer) setup.

### Development Environment Container (.devcontainer)

- **Requirements**: [Docker Desktop](https://www.docker.com/products/docker-desktop/) and [VS Code](https://code.visualstudio.com/) with the **[Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers)** extension installed.
- **Usage**:
  1. Clone this repository: `git clone https://github.com/markurtz/disdantic.git`
  1. Open the project folder in VS Code.
  1. A prompt will appear: "Reopen in Container". Click it to launch the environment.
  1. VS Code will build the container, automatically run `uv sync --all-groups --all-extras` to install and sync the Python environment.

> [!NOTE]
> **Local `.venv` vs. Hatch Environments**:
> The `uv sync` command creates a local `.venv` in the project root solely to provide VS Code extensions (like [Pylance](https://github.com/microsoft/pylance-release) and [Ruff](https://astral.sh/ruff)) with a standard environment for editor autocomplete, hover information, and in-editor diagnostics. All command-line and automated task execution (formatting, linting, testing, building) is managed via **[Hatch](https://hatch.pypa.io/)** isolated environments (`hatch run ...`). Do not activate or modify this root `.venv` directly for running tasks.

### Local Setup

- **[Git](https://git-scm.com/)**: Version control tool. Refer to the [Git Documentation](https://git-scm.com/doc) for installation instructions.
- **[Docker](https://www.docker.com/)**: Container management system. Install via the [Docker Installation Guide](https://docs.docker.com/get-docker/).
- **[Python](https://www.python.org/) 3.10 - 3.14**: Core runtime environment. Install via the [Python Downloads Page](https://www.python.org/downloads/).
- **[uv](https://docs.astral.sh/uv/)**: Fast package installer and resolver. Install via the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).
- **[Hatch](https://hatch.pypa.io/)**: Project workflow orchestrator. Install via the [Hatch installation guide](https://hatch.pypa.io/latest/install/). If you have `uv` installed, we recommend installing Hatch cleanly as a tool using:
  ```bash
  uv tool install hatch
  ```
  to avoid polluting your global system packages.

> [!TIP]
> **Editor Autocomplete Setup (Local)**:
> For local development outside of the Dev Container, if you want your editor (VS Code, [PyCharm](https://www.jetbrains.com/pycharm/), etc.) to resolve imports and provide autocomplete/diagnostics, run `uv sync --all-groups --all-extras` once to create the local `.venv`.

## Developer Quickstart

Once your environment is set up (either via the Dev Container or manually), follow this consolidated workflow for a standard development cycle:

- **Branch & Code**: Create your feature branch and make changes:
  ```bash
  git checkout -b feat/my-contribution
  ```
- **Quality Assurance (Unified)**: Automatically format code, lint, type check, and run security scans across all environments:
  ```bash
  hatch run all:quality
  ```
  *(Alternatively, you can run individual checks if preferred: `hatch run all:format`, `hatch run all:lint`, `hatch run all:types`, or `hatch run all:security`)*
- **Test (Unified)**: Run all unit, integration, and E2E tests with coverage:
  ```bash
  hatch run all:tests-cov
  ```
  *(For running tests without coverage: `hatch run all:tests`)*
- **Build (Unified)**: Compile package artifacts (source & wheels) and build the OCI container image *(requires Docker daemon to be running for the OCI phase)*:
  ```bash
  hatch run all:build
  ```
  *(To build only the Python wheel locally: `hatch build`)*
- **Serve Documentation**: Serve documentation locally (this automatically builds the site):
  ```bash
  hatch run all:docs-serve
  ```
- **Push**: Push your changes to open a Pull Request:
  ```bash
  git push -u origin feat/my-contribution
  ```

## Hatch Development Environments Overview

Our build, verification, and execution pipelines are partitioned into target-specific environments using Hatch. This ensures isolation, prevents dependency bloat, and standardizes workflows:

- **`default`**: The base environment template. It configures shared environment variables (such as target paths, directory structures, and script file paths) and installs the core dependency groups.
- **`all`**: The orchestrator environment. It defines cascading workflows to run formatting, linting, typing, security scanning, testing, and documentation generation across all components sequentially or concurrently.
- **`python`**: Encompasses Python-specific verification tools including [Ruff](https://astral.sh/ruff) for linting/formatting, [Ty](https://github.com/astral-sh/ty) for type-checking, [Pytest](https://docs.pytest.org/) for testing, and [Typer](https://typer.tiangolo.com/) for CLI documentation generation.
- **`oci`**: Manages OCI container builds (`docker build`), compose verification (`docker compose config`), linting ([hadolint](https://github.com/hadolint/hadolint)), security auditing ([trivy](https://trivy.dev/), [dockle](https://github.com/goodwithtech/dockle)), and container structure tests ([cstest](https://github.com/GoogleContainerTools/container-structure-test)).
- **`project`**: Targets repository-wide configuration and file standards, including Markdown formatting (`[mdformat](https://github.com/executablebooks/mdformat)`), configuration checkouts (`[yamlfix](https://github.com/lyz-code/yamlfix)`, `[yamllint](https://github.com/adrienverge/yamllint)`, `[taplo](https://taplo.tamasfe.dev/)`), security baselines (`[detect-secrets](https://github.com/Yelp/detect-secrets)`, `[checkov](https://www.checkov.io/)`), link checkers, and site compilation (using the **[Zensical](https://zensical.org)** static site generator/documentation compiler).

## Coding Workflows

All development commands are unified under [pyproject.toml](./pyproject.toml) and managed using Hatch. The commands are generally invoked using the format:

```bash
hatch run [ENVIRONMENT]:[SCRIPT]
```

For orchestrating tasks across all environments, use the `all` environment scripts:

```bash
hatch run all:[SCRIPT]
```

### Quality Assurance & Static Analysis

This workflow enforces code quality, style conventions, static type correctness, and security policies across all codebase layers.

> [!TIP]
> **Unified Quality Check**:
> You can run all formatting, linting, type-checking, and security scans across all environments in a single command using the unified quality check:
>
> ```bash
> hatch run all:quality
> ```

| Environment            | Formatting Command         | Linting Command          | Type-Checking Command        | Security Auditing Command    |
| :--------------------- | :------------------------- | :----------------------- | :--------------------------- | :--------------------------- |
| **All / Orchestrator** | `hatch run all:format`     | `hatch run all:lint`     | `hatch run all:types`        | `hatch run all:security`     |
| **Python**             | `hatch run python:format`  | `hatch run python:lint`  | `hatch run python:types`     | `hatch run python:security`  |
| **OCI**                | `hatch run oci:format`     | `hatch run oci:lint`     | `hatch run oci:types` \*     | `hatch run oci:security`     |
| **Project**            | `hatch run project:format` | `hatch run project:lint` | `hatch run project:types` \* | `hatch run project:security` |

*\* Note: Type checking is not applicable for OCI and Project environments; executing these commands will output an information message.*

#### Code Formatting

- **Tools / Methodology / Rationale**:
  - **Python**: Uses `[ruff](https://astral.sh/ruff)` to automatically check/fix imports and format code layout. This delivers high-performance style standardization.
    - **OCI**: Uses `[dclint](https://github.com/zavoloklom/docker-compose-linter)` (via a helper script) to auto-format Docker Compose files. While `dclint` is primarily a compose linter, the format step (`hatch run oci:format`) executes it with the `--fix` flag to automatically correct lint errors and standard style issues in place. (Dockerfile linting/validation is handled separately by `[hadolint](https://github.com/hadolint/hadolint)`).
  - **Project**: Employs `[mdformat](https://github.com/executablebooks/mdformat)` for Markdown, `[yamlfix](https://github.com/lyz-code/yamlfix)` for YAML files, and `[taplo](https://taplo.tamasfe.dev/)` for TOML file formatting to maintain a uniform structure for all configuration and documentation files.
- **Expected Outputs & Locations**:
  - In-place modifications applied directly to the files targeted by the respective environment variables: `PYTHON_TARGETS`, `MDFORMAT_TARGETS` (Markdown targets), `YAML_TARGETS`, and `TOML_TARGETS`.

#### Linting & Verification

- **Tools / Methodology / Rationale**:
  - **Python**: Runs `[ruff](https://astral.sh/ruff) check` and `[ruff](https://astral.sh/ruff) format --check` to verify compliance with PEP 8 and project style guidelines without modifying files.
    - **OCI**: Uses `[hadolint](https://github.com/hadolint/hadolint)` to validate Dockerfile syntax and standard practices, and runs `docker compose config` to verify the syntactic and semantic validity of compose files.
  - **Project**: Runs `[mdformat](https://github.com/executablebooks/mdformat) --check` to check Markdown formatting, `[yamlfix](https://github.com/lyz-code/yamlfix) --check` and `[yamllint](https://github.com/adrienverge/yamllint)` for YAML files, and `[taplo](https://taplo.tamasfe.dev/) check` for TOML configuration syntax.
- **Expected Outputs & Locations**:
  - Summary reports, warnings, and errors output directly to the terminal stdout/stderr. Standard exit codes (non-zero on failures) are used to gate CI pipelines.

#### Static Type Checking

- **Tools / Methodology / Rationale**:
  - **Python**: Employs Astral's `[ty check](https://github.com/astral-sh/ty)` frontend to statically analyze and verify Python type annotations.
  - **Expected Outputs & Locations**:
  - Type checker error listings and tracebacks are printed to the terminal console.

#### Security & Vulnerability Auditing

- **Tools / Methodology / Rationale**:
  - **Python**: Employs `[semgrep](https://semgrep.dev/)` for semantic pattern matching, `[pip-audit](https://github.com/pypa/pip-audit)` to detect known vulnerabilities in Python packages, and `[ruff](https://astral.sh/ruff) check --select S` to check for security vulnerabilities.
    - **OCI**: Scans built containers using `[dockle](https://github.com/goodwithtech/dockle)` (verifies image best practices/secrets) and `[trivy](https://trivy.dev/)` (scans OS-level packages for CVEs).
  - **Project**: Employs `[detect-secrets](https://github.com/Yelp/detect-secrets)` to scan for accidentally committed secrets against a baseline, and `[checkov](https://www.checkov.io/)` to scan infrastructure-as-code files and development configurations.
- **Expected Outputs & Locations**:
  - Standard reports output to the console.
  - Project environment updates and validates the secrets baseline file located at `.detect-secrets.scan.json`. Run `hatch run project:security-update` to update this baseline file.

### Testing Strategy & Suites

Our testing strategy is split into component-level, integration-level, and system-level suites, each of which supports code coverage reporting.

#### Coverage Configurations & Directories

Code coverage runs collect data during test executions and format them into human-readable Markdown summaries.

- **Python Coverage**: Configured to output to `coverage/python/` (`PYTHON_COV_DIR`). The test suites automatically output terminal reports and compile Markdown reports (e.g., `coverage_tests-unit.md`).

| Test Suite                 | Python Command                    | OCI Command                   | Project Command                     | All Command                   |
| :------------------------- | :-------------------------------- | :---------------------------- | :---------------------------------- | :---------------------------- |
| **All Local Tests**        | N/A                               | N/A                           | N/A                                 | `hatch run all:tests`         |
| **All Tests + Coverage**   | N/A                               | N/A                           | N/A                                 | `hatch run all:tests-cov`     |
| **Functional Tests**       | `hatch run python:tests-func`     | N/A                           | `hatch run all:tests-func`          |                               |
| **Func Tests + Coverage**  | `hatch run python:tests-func-cov` | N/A                           | `hatch run all:tests-func-cov`      |                               |
| **Unit Tests**             | `hatch run python:tests-unit`     | N/A                           | `hatch run all:tests-unit`          |                               |
| **Unit Tests + Coverage**  | `hatch run python:tests-unit-cov` | N/A                           | `hatch run all:tests-unit-cov`      |                               |
| **Integration Tests**      | `hatch run python:tests-int`      | `hatch run project:tests-int` | `hatch run all:tests-int`           |                               |
| **Int Tests + Coverage**   | `hatch run python:tests-int-cov`  | N/A                           | `hatch run all:tests-int-cov`       |                               |
| **End-to-End Tests**       | `hatch run python:tests-e2e`      | `hatch run oci:tests-e2e`     | `hatch run project:tests-e2e`       | `hatch run all:tests-e2e`     |
| **E2E Tests + Coverage**   | `hatch run python:tests-e2e-cov`  | `hatch run oci:tests-e2e-cov` | `hatch run project:tests-e2e-cov`   | `hatch run all:tests-e2e-cov` |
| **Link Checks**            | N/A                               | N/A                           | `hatch run project:link-checks`     | N/A                           |
| **Link Checks + Coverage** | N/A                               | N/A                           | `hatch run project:link-checks-cov` | N/A                           |

*\* Note: While Hatch commands for `N/A` cells can technically be run (and will print a message stating that the test suite is not defined for that environment), they have no logical test targets or execution paths. They are marked `N/A` for clarity.*

#### Test Suites Breakdown

#### Full Suite (`tests` / `tests-cov`)

- **Methodology & Rationale**: Executes all local functional and E2E tests across all environments to ensure complete validation of the codebase before code integration.
- **Expected Outputs & Locations**: Unified console log output, combined test summaries, and all coverage Markdown files compiled under `coverage/python/`.

#### Functional Testing (`tests-func` / `tests-func-cov`)

- **Methodology & Rationale**: Executes both unit and integration tests under the targeted environment to verify logical flows and subsystem communication.
- **Expected Outputs & Locations**:
  - **Python**: Outputs to console and `coverage/python/coverage_tests-func.md`.

#### Unit Testing (`tests-unit` / `tests-unit-cov`)

- **Methodology & Rationale**:
  - **Python**: Runs isolated tests under `tests/python/unit` via `pytest`. Focuses on validating individual modules and class behaviors.
- **Expected Outputs & Locations**:
  - **Python**: Outputs `coverage/python/coverage_tests-unit.md`.

#### Integration Testing (`tests-int` / `tests-int-cov`)

- **Methodology & Rationale**:
  - **Python**: Runs tests under `tests/python/integration` via `pytest` to verify interactions between Python modules.
  - **Project**: Runs documentation code block tests. It utilizes `scripts/generate_doc_tests.py` to parse Markdown files and compile code block assertions under `.tests/docs` (`DOC_TESTS_PATH`), which are then executed using `pytest`.
- **Expected Outputs & Locations**:
  - **Python**: Outputs `coverage/python/coverage_tests-int.md`.
  - **Project**: Verifies doc tests compile and pass; outputs progress to stdout.

#### End-to-End Testing (`tests-e2e` / `tests-e2e-cov`)

- **Methodology & Rationale**:
  - **Python**: Compiles Python packages with `hatch build`, force reinstalls them via `pip`, and runs pytest against `tests/e2e` (`E2E_TESTS`) to verify CLI commands and package distribution paths in a black-box environment.
  - **OCI**: Builds the OCI image and executes Google's Container Structure Tests (`cstest` via `scripts/run_oci.py`) to confirm that the image metadata, file layouts, and execution endpoints conform to specifications.
  - **Project**: Runs automated tests across the `examples/` directory using pytest to verify real-world integrations.
- **Expected Outputs & Locations**:
  - **Python**: Outputs `coverage/python/coverage_tests-e2e.md`.
  - **OCI**: Outputs Container Structure Test results to the console.
  - **Project**: Outputs example test execution summaries to the console.

#### Link Checking (`link-checks` / `link-checks-cov`)

- **Methodology & Rationale**:
  - **Project**: Executes `scripts/check_links.py` to recursively crawl project documents (`MDFORMAT_TARGETS`) and verify all internal/external links resolve successfully.
- **Expected Outputs & Locations**:
  - **Project**: Outputs link-checking validation summaries to the console.

#### Test Categorization & Test Pathways

To manage test execution speed and pipeline efficiency, every Python test is categorized into one of our three test pathways: **smoke**, **sanity**, or **regression**. These pathways directly govern how frequently and in which environments those tests are executed in CI/CD pipelines.

##### Pathway Specification & Filtering

A test's pathway can be specified and detected in one of two ways:

1. **By Marker**: Decorating the test function or class with a custom pytest marker (e.g., `@pytest.mark.smoke`, `@pytest.mark.sanity`, `@pytest.mark.regression`).
1. **By Name**: Including the pathway name in the test function or class name (e.g., `def test_smoke_initialization()`, `class TestSanityCore`, `def test_regression_bug_fix()`).

##### Test Pathways Breakdown

- **`smoke`**:
  - **Encapsulation & Scope**: Extremely fast, non-flaky, critical-path verification checks. These confirm that the fundamental, basic logic of the application functions correctly (e.g., orchestrator bootstrap, CLI command recognition).
  - **Execution Frequency**: Run on **every commit and Pull Request** (e.g., `development.yml`) as a quick health gate.
- **`sanity`**:
  - **Encapsulation & Scope**: Detailed, comprehensive tests of core system behaviors, APIs, and edge cases. These verify that the main business logic functions robustly but may take slightly longer than smoke tests.
  - **Execution Frequency**: Run on **pushes to the main branch** (e.g., `main.yml`) and release branches to ensure overall stability of the codebase.
- **`regression`**:
  - **Encapsulation & Scope**: Deep, system-wide, and heavy integration/E2E regression verification checks. These ensure that complex interactions, edge cases, and past bugs do not reappear.
  - **Execution Frequency**: Run on **nightly, weekly, and release schedule pipelines** due to their longer execution time.

##### Default Pathway Execution

If no specific filtering arguments, markers, or keyword flags are provided, pytest assumes a **regression** pathway by default.

Running the test suite without any arguments executes a full regression run. This is because a default regression run executes:

- All smoke tests
- All sanity tests
- All regression tests
- Any tests not marked or named under a specific category

##### Filtering Python Tests

Hatch dynamically passes CLI arguments through to the underlying `pytest` execution via the `{args}` placeholder configured in [pyproject.toml](./pyproject.toml). To filter by test pathways (`smoke`, `sanity`, or `regression`), use pytest's keyword option (`-k`). This correctly matches both annotated markers and naming patterns (e.g., pathway keywords in the function or class name).

- **Run only smoke tests**:
  ```bash
  hatch run python:tests-unit -k smoke
  ```
- **Run sanity and smoke tests**:
  ```bash
  hatch run python:tests-unit -k "sanity or smoke"
  ```

##### Testing a Specific Sub-Package or File

Hatch environments make it easy to target a specific test directory, sub-package, or single file by appending the path to your `hatch run` command. The provided path will override the default directories configured in `pyproject.toml`.

- **Run all tests in a specific file**:
  ```bash
  hatch run python:tests-unit tests/python/unit/test_settings.py
  ```
- **Run tests in a specific sub-package / directory**:
  ```bash
  hatch run python:tests-unit tests/python/unit/compat/
  ```
- **Run functional tests for a specific integration file**:
  ```bash
  hatch run python:tests-func tests/python/integration/test_utils.py
  ```

### Documentation Workflows

Our documentation is managed as code. It includes auto-generated CLI references and a unified project site built using **[Zensical](https://zensical.org)**.

> [!NOTE]
> **Zensical Documentation Tool**:
> [Zensical](https://zensical.org) is a static site generator and documentation compiler configured via `zensical.toml` that integrates [MkDocs](https://www.mkdocs.org/) and its plugin ecosystem (such as [mkdocstrings](https://github.com/mkdocstrings/mkdocstrings) and [macros](https://mkdocs-macros-plugin.readthedocs.io/)) under a simplified configuration structure.

#### CLI Documentation Generation

- **Tools / Methodology / Rationale**: Uses the `[typer](https://typer.tiangolo.com/)` utility to compile and output reference docs directly from the Python entrypoint `src/disdantic/__main__.py`.
- **Command**: `hatch run python:docs`
- **Expected Outputs & Locations**: A generated Markdown reference file at `.docs/cli.md`.

#### Project Website Compilation

- **Tools / Methodology / Rationale**: Compiles the final developer documentation site via **Zensical**, incorporating the general Markdown guides, Python CLI docs.
- **Command**: `hatch run project:docs` (or `hatch run all:docs` to generate Python docs and compile project docs together)
- **Expected Outputs & Locations**: Static build files compiled to the `site/` directory.

> [!TIP]
> **Dynamic Coverage Report Inclusion**:
> When compiling the website locally, Zensical dynamically embeds the Python test coverage reports (extracted from `coverage/python/`) into the final reference pages (`docs/reference/python_coverage.md`). If the coverage reports have been generated locally, they will automatically be included in the compiled docs site.

#### Live Development Preview Server

- **Tools / Methodology / Rationale**: Launches a hot-reloading web server to preview changes locally in real-time.
- **Command**:
  - Local Project Server: `hatch run project:docs-serve`
  - Global Orchestrator: `hatch run all:docs-serve`
- **Expected Outputs & Locations**: Hot-reloading site hosted locally at `http://localhost:8000`.

### Build & Distribution Workflows

These workflows handle compiling code, bundling extension modules, and building containerized runtimes for distribution.

#### Python Package Build

- **Tools / Methodology / Rationale**: Uses Hatchling to bundle Python distribution packages.
- **Command**: `hatch build`
- **Expected Outputs & Locations**: Built source distributions and `.whl` files output to the `dist/` directory.

#### OCI Container Image Build

- **Tools / Methodology / Rationale**: Executes a Docker build to compile the multi-stage production image, tagging the result using metadata parameters.
- **Command**: `hatch run oci:build`
- **Expected Outputs & Locations**: Local Docker image compiled and tagged as `disdantic:latest` (configured via `{env:OCI_IMAGE}`).

## CI/CD Workflows

We maintain high quality gates using git workflows, automated reviews, and [GitHub Actions](https://github.com/features/actions) pipelines.

### Version Control Standards

- **Tools**: Git
- **Workflow & Commands**:
  - **Branching Model**: Standard branch prefixes are enforced:
    - Features: `feature/short-description`
    - Bugs: `bugfix/short-description`
    - Docs: `docs/short-description`
  - **Commit Messages**: Enforce [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat: ...`, `fix: ...`, `docs: ...`).
  - **Versioning Tags**: Release tags must follow semver format (`v*.*.*`).

### Repository Policy & Pull Requests

- **Tools**: GitHub Pull Requests and Review tools
- **Workflow & Commands**:
  - Open a PR against the `main` branch.
  - All pipeline checks must pass (Linting, static typing, security gates, unit/integration/e2e tests).
  - Require review and approval from at least one core maintainer before merging.

### GitHub Actions Architecture

Our pipelines use a highly modular and DRY architecture to avoid duplication of setup steps:

- **Tools**: [GitHub Actions](https://github.com/features/actions)

- **Configuration / Manifest Files**: Reusable actions under `.github/actions/...` and triggers under `.github/workflows/...`

- **Python Versioning & Parameters**:

  - All composite actions (Python, OCI, and Project) support an optional `python-version` parameter.
  - If omitted, actions standardize on the oldest supported version (default: `"3.10"`).
  - All composite actions using change detection (`[dorny/paths-filter](https://github.com/dorny/paths-filter)`) support a `force-run` parameter (default: `"false"`). When set to `"true"`, it bypasses path-filtering check gates and executes the steps unconditionally (used in scheduled and release workflows).

- **OCI Tools Native Execution**:

  - The repository utilizes unified platform-agnostic OCI runner logic (`scripts/run_oci.py`).
  - When running in CI under `.github/actions/oci/`, the actions natively install OCI scanning and linting tools (`[hadolint](https://github.com/hadolint/hadolint)`, `[dclint](https://github.com/zavoloklom/docker-compose-linter)`, `[dockle](https://github.com/goodwithtech/dockle)`, `[trivy](https://trivy.dev/)`, and `[container-structure-test](https://github.com/GoogleContainerTools/container-structure-test)`) on the runner.
  - This native pre-installation ensures that `run_oci.py` executes these binaries directly on the host machine, bypassing the performance overhead and Docker socket mounting requirements of containerized container-in-container execution.

  > [!WARNING]
  > **Tool Version Drift Risk**:
  > Running these tools natively in CI while developers run them locally via Docker fallback containers (e.g., `aquasec/trivy:latest`) can lead to version drift. To prevent the *"it passes locally but fails in CI"* issue:
  >
  > 1. Keep your system-installed binaries updated to match the versions used in CI workflows (defined in the OCI composite actions).
  > 1. Periodically pull the latest container images locally (`docker pull aquasec/trivy:latest`) to keep Docker fallbacks in sync with CI runner environments.

- **Utility Actions (`.github/actions/utility/...`)**:

  - `setup-python`: Sets up Python, and installs uv and Hatch.

- **Environment Actions (`.github/actions/[env]/...`)**:

  - Partitioned into folders for each environment: `python`, `oci`, and `project`.
  - Inside each environment, standard actions run specific scripts:
    - `quality`: Runs formatting, linting, and type checking.
    - `security`: Runs dependency audits, secrets checks, and security linters.
    - `tests`: Runs unit, integration, and E2E tests, accepting `test-level`, `test-category`, and `generate-coverage` inputs.
    - `build`: Compiles wheels (Python), container images (OCI), or all elements (Project).
    - `publish`: Publishes release packages to [PyPI](https://pypi.org/) (Python) or container images to [GHCR](https://github.com/features/packages) (OCI).

- **Workflows (`.github/workflows/...`)**: Triggered pipelines separated into:

  - **Core Pipelines**:
    - `pipeline-development.yml`: PR checks (quality, security, package build, tests, and documentation previews).
    - `pipeline-main.yml`: Triggered on push to `main` branch (runs full checks and deploys latest docs).
    - `pipeline-nightly.yml`: Nightly regression tests, vulnerability audits, and nightly releases.
    - `pipeline-release.yml`: Release tag pushes (`v*.*.*`); packages binary builds, attests them, publishes to PyPI and GHCR, and creates releases.
    - `pipeline-weekly.yml`: Scheduled weekly checks to verify environment health.
  - **Utility Workflows**:
    - `util-development-cleanup.yml`: Cleans up transient PR doc deployments.
    - `util-pr-comment.yml`: Securely posts PR comments (build status, compiled coverage summary, documentation previews, and build packages) to avoid fork permission limits.

### Local Workflow Testing with `act`

You can test and validate [GitHub Actions](https://github.com/features/actions) workflows locally on your development machine using [nektos/act](https://github.com/nektos/act). This ensures that workflows run correctly before you push changes to GitHub.

#### Prerequisites

1. Install **[Docker](https://www.docker.com/)** (required by `act` to spin up runner containers).
1. Install `act` using your package manager:
   - macOS ([Homebrew](https://brew.sh/)): `brew install act`
   - Linux (curl): `curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash`

> [!IMPORTANT]
> **Apple Silicon (M-series Chips) Emulation**:
> If you are on an Apple Silicon Mac, you must specify the target execution architecture using `--container-architecture linux/amd64`. This ensures that `act` pulls the `amd64` container image and installs pre-compiled `x86_64` wheels (such as `taplo`), bypassing compile-from-source errors due to missing arm64 wheels.

#### Running Workflows Locally

Run `act` from the repository root:

- **List all jobs**:
  ```bash
  act -l
  ```
- **Run the default (pull_request) event (runs Development Pipeline)**:
  ```bash
  act pull_request
  ```
- **Run a specific job (e.g., project-quality)**:
  ```bash
  act -j project-quality
  ```
- **Dry-run a workflow (displays steps without execution)**:
  ```bash
  act -n
  ```

#### Mocking Event Payloads (Change Detection)

Because composite actions use `dorny/paths-filter` to detect path-level changes, running `act` directly will fail if the required event metadata is missing. To solve this, the repository contains two mock payload files that simulate the GitHub event context:

1. **`pull_request_event.json`** for simulating PR events:

   ```json
   {
     "pull_request": {
       "number": 1,
       "head": {
         "ref": "feat/repo-setup",
         "sha": "HEAD"
       },
       "base": {
         "ref": "main",
         "sha": "main"
       }
     }
   }
   ```

   *Usage Example:*

   ```bash
   act pull_request -W .github/workflows/pipeline-development.yml -j project-quality -e pull_request_event.json --container-architecture linux/amd64
   ```

1. **`push_event.json`** for simulating direct push events (e.g. to the `main` branch):

   ```json
   {
     "ref": "refs/heads/main",
     "before": "0000000000000000000000000000000000000000",
     "after": "HEAD",
     "repository": {
       "default_branch": "main"
     }
   }
   ```

   *Usage Example:*

   ```bash
   act push -W .github/workflows/pipeline-main.yml -j init-gate -e push_event.json --container-architecture linux/amd64
   ```

> [!NOTE]
> `act` runs steps inside Docker containers that simulate GitHub environments. By default, it uses a medium-sized Ubuntu image, but you can specify a fuller image using `act -P ubuntu-latest=catthehacker/ubuntu:act-latest`. Both event payload files are automatically ignored in `.gitignore`.

### Security & Code Scanning Gates

- **Tools**: [detect-secrets](https://github.com/Yelp/detect-secrets) (secret scanning), [checkov](https://www.checkov.io/) (infrastructure auditing), [semgrep](https://semgrep.dev/) (semantic scanning), [pip-audit](https://github.com/pypa/pip-audit) (Python package audits), and [trivy](https://trivy.dev/) / [dockle](https://github.com/goodwithtech/dockle) (OCI image scanning).
- **Workflow & Rationale**:
  - **Secret Gating**: [detect-secrets](https://github.com/Yelp/detect-secrets) runs locally and in PR gates against the committed `.detect-secrets.scan.json` baseline to prevent credential leaks.
  - **Static Analysis & CVE Auditing**: [Semgrep](https://semgrep.dev/), [Trivy](https://trivy.dev/), [Checkov](https://www.checkov.io/), [pip-audit](https://github.com/pypa/pip-audit) run automatically as background checks on every pull request to guarantee compliance with our security baseline.

______________________________________________________________________

For additional assistance, please refer to our [SUPPORT.md](SUPPORT.md).
