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

# Disdantic Examples

This directory contains practical, runnable demonstrations of how to use Disdantic in various scenarios. These examples are designed to help you quickly understand core concepts, advanced configurations, and best practices.

## Prerequisites

Before running the examples, ensure you have set up your environment correctly:

1. **Install Dependencies:** Make sure you have installed the core package for your environment and any example-specific requirements.
1. **Environment Variables:** Copy `.env.example` to `.env` if the examples require configuration (e.g., API keys or external services).

> [!NOTE]
> Some examples may require additional dependencies not included in the core `disdantic` package. Please check the `README.md` within each specific example directory for details.

## Example Index

Below is a curated list of available examples, categorized by build tool and use case:

### Benchmarking & Network Examples

| Example                                      | Complexity | Description                                                              |
| :------------------------------------------- | :--------- | :----------------------------------------------------------------------- |
| **`[example_template/](example_template/)`** | Beginner   | Generic boilerplate template demonstrating standard example conventions. |

<!-- Add new examples to the tables above as they are created. -->

## Running the Examples

Most examples can be executed directly from the command line. Navigate to the root of the repository and run the desired script:

```bash
# Example: Running a generic example script
python examples/example_name/main.py
```

> [!TIP]
> **Always run examples from the repository root.** This ensures that all relative paths, environment variables, and module imports resolve correctly.

## Contributing New Examples

We welcome community contributions! If you have a use case that isn't covered, please consider submitting a new example:

1. Create a new directory under `examples/` with a descriptive name.
1. Include a focused, easily digestible script or application.
1. Add a local `README.md` within your example directory explaining what it does and how to run it.
1. Update the **Example Index** table above.

For more details on contributing, please review our [Contributing Guide](../CONTRIBUTING.md).
