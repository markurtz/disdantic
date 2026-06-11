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

Unless otherwise noted, all files in this directory and its subdirectories
are licensed under the Apache License, Version 2.0.
-->

# Disdantic - Utility Scripts

This directory contains utility scripts designed to assist with local development, maintenance, and automation tasks for Disdantic.

> [!NOTE]
> These scripts are intended for developer and CI/CD use only and are **not** distributed as part of the final application package.

## Usage Guidelines

To ensure a consistent development experience across the organization, please adhere to the following guidelines when running or adding scripts.

### Execution

Scripts should generally be executed from the root of the repository to ensure relative paths resolve correctly:

```bash
# Example
./scripts/<script_name>.sh
```

Ensure the script has execution permissions before running:

```bash
chmod +x scripts/<script_name>.sh
```

### Scripting Standards

If you are adding or modifying a script in this directory, please ensure it adheres to the following best practices:

- **Prefer Bash (`.sh`) or Python (`.py`):** These languages provide the best cross-platform compatibility.
- **Fail Fast (Bash):** Always begin Bash scripts with `set -euo pipefail` to ensure they exit immediately on errors, undefined variables, or pipeline failures.
- **Environment Variables:** If your script requires secrets or environment-specific configurations, document them at the top of the script and ensure they align with the `.env.example` file.
- **Provide Help:** Scripts should ideally accept a `-h` or `--help` flag that outputs usage instructions.
- **Log Clearly:** Prefix output with `[INFO]`, `[WARN]`, or `[ERROR]` to make CI/CD logs easier to read.

## Available Scripts

*Currently, there are no utility scripts in this directory.*

## Contributing

If you add a new utility script that would benefit other developers, please add it to the **Available Scripts** table above with a brief description of its purpose.
