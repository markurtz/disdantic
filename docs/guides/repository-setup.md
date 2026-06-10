# Setting up the repository

Welcome to your new repository! If you have just instantiated this project from the template, there are a few configuration steps required to get your standalone project fully operational.

This guide acts as a checklist for the project maintainer. Once these steps are complete, your CI/CD pipelines, documentation site, and release workflows will be fully enabled.

## 1. Bootstrap the repository

Before making any manual changes, run the included interactive bootstrap script to automatically replace all placeholder variables (like `template-python` and `markurtz`) with your actual project details.

```bash
uv run scripts/bootstrap.py
```

The script will interactively prompt you for your project details (organization, project name, descriptions, and feature toggles) and automatically configure the repository.

> [!NOTE]
> This script will rename the source directory (`src/template_python/` -> `src/my_cool_project/`) and update all references in the documentation, GitHub Actions workflows, and configuration files.

Once you have verified the changes and chosen to finalize the bootstrap process, the script will automatically delete itself and its related end-to-end tests. Commit the updates.

## 2. Configure GitHub settings

To ensure code quality and security, configure the following settings in your repository:

1. **Enable Discussions (Optional but recommended):**
   Go to **Settings > General > Features** and check **Discussions**.

1. **Branch Protection Rules:**
   Go to **Settings > Branches** and add a protection rule for `main`.

   - Check **Require a pull request before merging**.
   - Check **Require status checks to pass before merging** (Require the `main` or `build` job from your CI workflow).
   - Check **Do not allow bypassing the above settings**.

1. **Tag Protection Rules:**
   Go to **Settings > Tags** and add a protection rule for `v*` tags to ensure only authorized maintainers can push release tags.

## 3. Enable documentation hosting

This template uses MkDocs Material to generate a beautiful documentation site. The site is automatically built and deployed to the `gh-pages` branch by the `.github/workflows/pages.yml` workflow when changes are merged into `main`.

To enable hosting:

1. Go to **Settings > Pages**.
1. Under **Build and deployment**, set the **Source** to **Deploy from a branch**.
1. Set the **Branch** to `gh-pages` and the folder to `/ (root)`.
1. Click **Save**.

> [!TIP]
> The `gh-pages` branch will be created automatically the first time the `pages.yml` workflow runs successfully. If it doesn't exist yet, push a change to `main` to trigger the build, then return to the Pages settings to configure it.

## 4. Configure PyPI trusted publishing

The template includes a `.github/workflows/release.yml` workflow that automatically publishes your package to PyPI when a release is created. This workflow uses **Trusted Publishing (OIDC)**, which is more secure than using API tokens.

To configure Trusted Publishing:

1. Go to [PyPI](https://pypi.org/) and navigate to your account settings.
1. Under **Publishing**, add a new **Pending Publisher**.
1. Set the **GitHub repository owner** to your organization or username.
1. Set the **GitHub repository name** to your project name.
1. Set the **Workflow name** to `release.yml`.
1. Set the **Environment name** to `pypi` (or leave it blank if not using an environment in your workflow, though the template defaults to a `pypi` environment).

Once the first release is published, the publisher will become active.

## 5. Enable container builds

If your project includes a `Dockerfile` and you want to publish container images to the GitHub Container Registry (GHCR), the template workflows are already prepared.

1. Ensure the `GITHUB_TOKEN` has `write` permissions for packages. Go to **Settings > Actions > General**.
1. Under **Workflow permissions**, ensure it is set to **Read and write permissions**.
1. When the `release.yml` or `nightly.yml` workflows run, they will build and push the container image to `ghcr.io/YOUR_ORG/YOUR_PROJECT`.

You may also want to make the package public once it is published by going to your Organization's **Packages** settings.

## 6. Manage versions and releases

This template is designed to use Git tags for versioning (e.g., via `hatch-vcs` or a similar dynamic versioning tool). You do not need to hardcode the version number in `pyproject.toml` or `__init__.py`.

To cut a new release:

1. **Tag the commit:** Create an annotated tag for your release (e.g., `v1.0.0`).
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```
1. **Create a GitHub Release:** Go to the repository's **Releases** page and draft a new release using the tag you just pushed.
1. **Automated Publishing:** Creating the release will trigger the `.github/workflows/release.yml` workflow, which will build the package, attest its provenance, and publish it to PyPI and GHCR.

______________________________________________________________________

**Next:** Now that your repository is configured, try running through the [Quick Start](../getting-started/quickstart.md) to verify everything is working locally!
