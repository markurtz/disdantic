# Utility Scripts

This directory contains utility scripts designed to assist with local development, maintenance, and automation tasks.

> [!NOTE]
> These scripts are intended for developer and CI/CD use only and are **not** distributed as part of the final application package.

## Usage Guidelines

To ensure a consistent development experience across the organization, please adhere to the following guidelines when running or adding scripts.

### Execution

Scripts should generally be executed from the root of the repository to ensure relative paths resolve correctly:

```bash
# Example
uv run scripts/bootstrap.py
```

Ensure Bash scripts have execution permissions before running:

```bash
chmod +x scripts/<script_name>.sh
```

### Scripting Standards

If you are adding or modifying a script in this directory, please ensure it adheres to the following best practices:

- **Prefer Python (`.py`) or Bash (`.sh`):** Python is preferred for complex logic (managed via `uv run`). Bash is acceptable for simple wrappers.
- **Fail Fast (Bash):** Always begin Bash scripts with `set -euo pipefail` to ensure they exit immediately on errors, undefined variables, or pipeline failures.
- **Environment Variables:** If your script requires secrets or environment-specific configurations, document them at the top of the script and ensure they align with the `.env.example` file.
- **Provide Help:** Scripts should ideally accept a `-h` or `--help` flag that outputs usage instructions.
- **Log Clearly:** Prefix output with `[INFO]`, `[WARN]`, or `[ERROR]` to make CI/CD logs easier to read.

## Available Scripts

| Script         | Description                                                                                                              |
| :------------- | :----------------------------------------------------------------------------------------------------------------------- |
| `bootstrap.py` | Interactively bootstraps a new repository from this template by replacing placeholders and configuring project features. |

## Contributing

If you add a new utility script that would benefit other developers, please add it to the **Available Scripts** table above with a brief description of its purpose.
