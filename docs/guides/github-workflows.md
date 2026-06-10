# Using CI/CD and GitHub workflows

This guide explains the continuous integration and continuous deployment (CI/CD) pipelines used in `template-python`. It outlines the standard pathways, development cycles, and what standards must be met to contribute to the repository.

## Understand the architecture

The repository utilizes a modular, standardized GitHub Actions architecture. Workflows are categorized into core lifecycle events (e.g., development, main, nightly) and reusable helper templates (prefixed with `_`).

Our CI/CD pipelines ensure that all code merged into the `main` branch meets strict code quality, type-safety, testing, and security standards.

## Navigate standard development pathways

When contributing to this repository, your code will travel through the following pipeline stages.

### 1. The pull request cycle (`development.yml`)

When you open a Pull Request against `main`, the `development.yml` workflow is triggered. This is the primary gateway for all code changes.

**What it enables:**

- **Quality Gates:** Runs `hatch run lint:check` (Ruff/mdformat) and `hatch run types:check` (Mypy) to enforce consistent formatting and type safety.
- **Security Audits:** Scans for vulnerabilities in dependencies and code patterns.
- **Testing:** Runs the unit and integration test suites. The PR will be blocked from merging if any tests fail.
- **Documentation Previews:** Verifies that the documentation can be built cleanly.

**Validation Standards:**
Your PR must pass all checks before it can be merged. We require strict adherence to PEP 8, full type annotations, and all tests must pass with adequate coverage.

### 2. Main branch validation (`main.yml`)

Once your PR is reviewed and merged into `main`, the `main.yml` workflow acts as a secondary validation layer.

**What it enables:**

- **Full Test Suite:** Runs unit, integration, and full end-to-end (e2e) tests to ensure the merged changes didn't introduce regressions.
- **Documentation Deployment:** Builds and deploys the `latest` version of the documentation site to the `gh-pages` branch.
- **Sanity Checks:** Re-runs quality and security checks on the finalized codebase.

### 3. Nightly and weekly pipelines

To catch configuration drift and conduct deeper analysis, we run scheduled workflows:

- **Nightly (`nightly.yml`):** Runs daily at 00:00 UTC. It performs extended regression testing, builds alpha container images, and does deep security analysis.
- **Weekly (`weekly.yml`):** Runs every Sunday at 00:00 UTC. Focused on dependency hygiene, checking for outdated constraints and ensuring the test suite is robust against external changes.

## Manage releases (`release.yml`)

Releasing a new version is automated using Git tags.

**What it enables:**
When a maintainer pushes a `v*.*.*` tag (e.g., `v1.2.0`), the `release.yml` workflow takes over.

- It performs a final, full verification of the entire test suite.
- It builds immutable Python packages (sdist and wheel).
- It attests the build provenance using OIDC.
- It publishes the artifacts to **PyPI** and the container image to the **GitHub Container Registry (GHCR)**.

## Utilize reusable templates

To maintain consistency and reduce duplication, our lifecycle pipelines rely on modular templates located in the `.github/workflows/` directory. If you need to add new checks, you generally modify these templates rather than the lifecycle workflows directly.

- `_tests.yml`: Orchestrates test suite execution (unit, integration, e2e).
- `_quality.yml`: Defines the exact linting and type-checking commands.
- `_security.yml`: Configures dependency scanning and SAST tooling.
- `_docs.yml`: Handles building MkDocs.
- `_build_package.yml`: Standardizes artifact generation.

By relying on templates, we ensure that the exact same linting rules are applied whether you are testing a PR, running a nightly build, or deploying a release.

______________________________________________________________________

**Next Steps:**

- See the [Contributing Guide](../community/contributing.md) for details on how to set up your local environment.
- Review the [Repository Setup](repository-setup.md) guide if you are the maintainer configuring these workflows for the first time.
