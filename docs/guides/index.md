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

# Guides

This section contains task-oriented how-to guides for `disdantic`. Unlike the [Getting Started](../getting-started/index.md) section, these guides are standalone — jump to whichever one is relevant to your current task.

## Available Guides

<div class="grid cards" markdown>

<div class="card" markdown>
:material-transit-connection-variant: **CI/CD & GitHub Workflows**

Walkthrough of the GitHub Actions pipelines, development pathways, and CI/CD standards.

[:octicons-arrow-right-24: View Guide](github-workflows.md)

</div>

<div class="card" markdown>
:material-layers-outline: **Subclass Registries & Schema Rebuilding**

Guide to dynamic Pydantic subclass registries, tagged union validation, dynamic unregistration, and schema cascades.

[:octicons-arrow-right-24: View Guide](registries.md)

</div>

<div class="card" markdown>
:material-console: **CLI, Diagnostics & Schema Export**

Guide to listing registries, verifying model compilation health, and exporting schemas to JSON or OpenAPI.

[:octicons-arrow-right-24: View Guide](cli-diagnostics.md)

</div>

<div class="card" markdown>
:material-tools: **System & Integration Utilities**

Guide to runtime introspection, thread-safe lazy loaders, singletons, structured logging, and configuration settings.

[:octicons-arrow-right-24: View Guide](utilities.md)

</div>

</div>

!!! tip "Contributing a Guide"
Have a workflow or pattern worth documenting? See the [Contributing Guide](../community/contributing.md) to learn how to add a new guide to this section.
