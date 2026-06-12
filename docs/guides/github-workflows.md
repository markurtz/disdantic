# Using CI/CD and GitHub workflows

This guide explains the continuous integration and continuous deployment (CI/CD) pipelines used in `disdantic`. It outlines the standard pathways, development cycles, and what standards must be met to contribute to the repository.

## Understand the architecture

The repository utilizes a modular, standardized GitHub Actions architecture. Workflows are categorized into core lifecycle events (prefixed with `pipeline-`) and utility triggers (prefixed with `util-`).

Our CI/CD pipelines ensure that all code merged into the `main` branch meets strict code quality, type-safety, testing, and security standards.

## Navigate standard development pathways

When contributing to this repository, your code will travel through the following pipeline stages.

### 1. The pull request cycle (`pipeline-development.yml`)

When you open a Pull Request against `main`, the `pipeline-development.yml` workflow is triggered. This is the primary gateway for all code changes.

**What it enables:**

- **Quality Gates:** Runs code quality and formatting checks (`hatch run python:lint`, `hatch run project:lint`, `hatch run oci:lint`) and static type verification (`hatch run python:types`) to enforce consistent standards.
- **Security Audits:** Scans for vulnerabilities in dependencies and code patterns using `detect-secrets`, `pip-audit` (via Python security checks), and `trivy`/`dockle` (via OCI security checks).
- **Testing:** Runs the Python unit, integration, and OCI structure tests. The PR will be blocked from merging if any tests fail.
- **Documentation Previews:** Verifies that the Zensical documentation can be built cleanly.

**Validation Standards:**
Your PR must pass all checks before it can be merged. We require strict adherence to PEP 8/Ruff, Python type annotations, and all tests must pass with adequate coverage.

### 2. Main branch validation (`pipeline-main.yml`)

Once your PR is reviewed and merged into `main`, the `pipeline-main.yml` workflow acts as a secondary validation layer.

**What it enables:**

- **Full Test Suite:** Runs unit, integration, and full end-to-end (e2e) tests to ensure the merged changes didn't introduce regressions.
- **Documentation Deployment:** Builds and deploys the `latest` version of the documentation site to the `gh-pages` branch.
- **Sanity Checks:** Re-runs quality and security checks on the finalized codebase.

### 3. Nightly and weekly pipelines

To catch configuration drift and conduct deeper analysis, we run scheduled workflows:

- **Nightly (`pipeline-nightly.yml`):** Runs daily at 00:00 UTC. It performs extended regression testing, builds alpha container images, and does deep security analysis.
- **Weekly (`pipeline-weekly.yml`):** Runs every Sunday at 00:00 UTC. Focused on dependency hygiene, checking for outdated constraints and ensuring the test suite is robust against external changes.

## Manage releases (`pipeline-release.yml`)

Releasing a new version can be done in two ways:

1. **Manual UI Trigger (Recommended):**
   A maintainer triggers the `CI — Release` workflow manually via the GitHub Actions UI.

   - **Inputs:** Requires entering a version tag matching strict semver (e.g., `v1.2.0`).
   - **Branch Constraints:** Can only be started on the `main` branch or a `releases/*` branch. If triggered on any other branch or tag ref via `workflow_dispatch`, the workflow fails the `init-gate` job and exits.
   - **Process:** The workflow runs all quality, testing, and integrity checks. If they pass, it automatically tags the current commit with the entered version and pushes it to origin.
   - **Unified Release Publishing:** Pushing the tag using the job's `GITHUB_TOKEN` successfully creates the remote tag without triggering recursive pipeline runs. The publishing jobs (`publish-python` and `publish-oci`) then execute immediately within the same manual run as soon as the tagging step succeeds. No Personal Access Tokens (PATs) or manual trigger restarts are required.

1. **Direct Tag Push:**
   When a maintainer pushes a `v*.*.*` tag (e.g., `v1.2.0`) directly to origin, the workflow is triggered on the tag ref.

   - It performs a final, full verification of the entire test suite on the tag.
   - It builds immutable Python packages (sdist and wheel).
   - It attests the build provenance using OIDC.
   - It publishes the artifacts to **PyPI** and the container image to the **GitHub Container Registry (GHCR)**.

### Release Security & Environments

To prevent unauthorized releases, we implement a **Gate Job** pattern using two-stage approvals bound to the `release` GitHub Environment:

- **Required Reviewers & Dual Approval:** Repository Administrators should configure the `release` environment under **Settings -> Environments -> release** to require approvals from designated release managers. The workflow requires two approvals: one at `init-gate` (to authorize starting the verification checks) and a second at `release-gate` (to authorize tagging and publishing after all verification gates have succeeded).
- **Deployment Branches & Early Fail:** Set the deployment branch policy to **Selected branches** allowing only `main` and `releases/*` to run jobs under this environment. Additionally, `init-gate` performs shell validation checking that the ref is a valid version tag (e.g. `v1.2.3`) or that branch execution (`main` or `releases/*`) was explicitly triggered by `workflow_dispatch`. If these conditions are not met, `init-gate` fails immediately.
- **Unified Publishing Gate & Gate Job Pattern:** The `release-gate` job validates all previous gates (`quality-gate`, `functional-gate`, `integrity-gate`, and `e2e-gate`) and propagates the `default_python` configuration output down a linear dependency chain: `release-gate` -> `tag-release` -> `publish-python` -> `docs` / `publish-oci`. This prevents GHA from requesting unnecessary additional approvals and simplifies job conditionals.
- **Publish Input Overrides:** Configured `publish-python` (GitHub Release tag name), `publish-oci` (OCI image tag name), and `docs` (docs version folder name) to use `${{ github.event.inputs.version_tag || github.ref_name }}`. Decoupled `docs` entirely from `init-gate` so that `docs` and `publish-oci` only depend on `publish-python`.

## Utilize custom actions

To maintain consistency and reduce duplication, our lifecycle pipelines rely on composite actions located in the `.github/actions/` directory:

- **Python Environment:**
  - `python/tests`: Orchestrates Python test suite execution (unit, integration, e2e).
  - `python/quality`: Defines the exact linting (Ruff) and type-checking (Mypy/Ty) commands.
  - `python/build` and `python/publish`: Standardizes Python package generation and PyPI distribution.
- **OCI Containers:**
  - `oci/tests`: Runs OCI Container Structure Tests (CST).
  - `oci/quality`: Lint Dockerfiles with Hadolint and Docker Compose configurations.
  - `oci/build` and `oci/publish`: Builds and registers production-ready container images.
- **Project-wide Utilities:**
  - `project/quality`: Enforces repository-wide guidelines (mdformat, yamlfix, taplo).
  - `project/docs`: Handles building MkDocs/Zensical sites.

By relying on these shared actions, we ensure that the exact same linting and test rules are applied whether you are testing a PR, running a nightly build, or deploying a release.

______________________________________________________________________

**Next Steps:**

- See the [Contributing Guide](../community/contributing.md) for details on how to set up your local environment.
