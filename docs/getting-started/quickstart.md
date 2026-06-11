# Quick Start

This guide gets you from a fresh clone to a running local development environment in under 5 minutes.

## Step 1 — Clone the Repository

Clone the `disdantic` repository to your local machine:

```bash
git clone https://github.com/markurtz/disdantic.git
cd disdantic
```

## Step 2 — Set Up and Sync the Environment

We use **[uv](https://docs.astral.sh/uv/)** to manage Python packages and environments, and **[Hatch](https://hatch.pypa.io/)** to orchestrate development tasks.

Sync the Python environment to install all required dependencies and tools:

```bash
uv sync --all-groups --all-extras
```

This will create a local `.venv` directory for IDE code resolution and install the development tools.

## Step 3 — Run Tests and Quality Checks

Verify that your local environment is configured correctly by running the pre-configured quality checks and tests:

```bash
# Run linting and type checking
hatch run python:lint
hatch run python:types

# Run the python unit test suite
hatch run python:tests-unit
```

If all tests pass, your local environment is successfully set up and ready!

## Step 4 — Run an Example

You can explore and run a basic example to see how the project functions. Run the template example:

```bash
python examples/example_template/main.py
```

> [!TIP]
> See the [Developer Guide](../community/developing.md) for more details on local development commands and advanced options.

## Step 5 — Explore Further

Now that your project is ready, explore what `disdantic` provides:

- **[Guides](../guides/index.md)** — Task-specific deep dives including CI/CD workflows.
- **[Reference](../reference/index.md)** — Full configuration reference.

**Next:** [Guides →](../guides/index.md)
