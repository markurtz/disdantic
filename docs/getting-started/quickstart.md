# Quick Start

This guide gets you from a fresh clone to a bootstrapped and running project in under 5 minutes.

## Step 1 — Instantiate the Template

1. Navigate to the [template-python repository on GitHub](https://github.com/markurtz/template-python).
1. Click the green **Use this template** button and select **Create a new repository**.
1. Choose your repository name and visibility, then click **Create repository**.
1. Clone your new repository to your local machine:
   ```bash
   git clone https://github.com/YOUR_ORG/YOUR_REPO.git
   cd YOUR_REPO
   ```

## Step 2 — Bootstrap the Project

The template comes with an interactive script that automatically replaces all placeholders with your project's details.

Run the bootstrap script using `uv`:

```bash
uv run scripts/bootstrap.py
```

Follow the interactive prompts to configure your project. Once complete, you can choose to finalize the process, which will delete the bootstrap script and its tests.

## Step 3 — Sync the Environment

Now that your project is renamed and configured, install all dependencies and set up your local development environment:

```bash
uv sync --all-groups --all-extras
```

## Step 4 — Run Tests and Quality Checks

Ensure everything is configured correctly by running the pre-configured quality checks and tests:

```bash
# Run linting and type checking
hatch run lint:check
hatch run types:check

# Run tests
hatch run test:all
```

If all tests pass, your new project is successfully bootstrapped and ready for development!

> [!TIP]
> See the [Developer Guide](../community/developing.md) for more details on local development commands.

## Step 5 — Explore Further

Now that your project is ready, explore what `template-python` provides:

- **[Repository Setup](../guides/repository-setup.md)** — Complete your GitHub configuration (Actions, Discussions, PyPI publishing).
- **[Guides](../guides/index.md)** — Task-specific deep dives including CI/CD workflows.
- **[Reference](../reference/index.md)** — Full configuration reference.

**Next:** [Repository Setup →](../guides/repository-setup.md)
