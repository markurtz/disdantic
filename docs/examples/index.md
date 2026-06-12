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

# Examples

This section contains runnable code examples that demonstrate real-world usage of disdantic. Each example is self-contained and demonstrates key architectural features of the library.

> [!NOTE]
> All examples assume you have completed [Installation](../getting-started/installation.md).

## Example Categories

<div class="grid cards" markdown>

<div class="card" markdown>
:material-chat-processing-outline: **Polymorphic Messaging**

______________________________________________________________________

Simple, self-contained example demonstrating core registry capabilities, case-insensitive lookahead routing, and cascading validation schema rebuilding.

[:octicons-arrow-right-24: View Code](https://github.com/markurtz/disdantic/tree/main/examples/polymorphic_messaging/)

</div>

<div class="card" markdown>
:material-cog-outline: **Telemetry & Settings**

______________________________________________________________________

Demonstrates loading configurations from workspace `pyproject.toml` with strict precedence, default key fallbacks, and structured JSON logging with OpenTelemetry tracing context.

[:octicons-arrow-right-24: View Code](https://github.com/markurtz/disdantic/tree/main/examples/telemetry_and_settings/)

</div>

<div class="card" markdown>
:material-eye-outline: **Lazy Loading & Introspection**

______________________________________________________________________

Showcases deferred loading via thread-safe `LazyProxy`, `SingletonMeta` double-checked locking, and recursive, circular-reference-safe runtime self-introspection with `InfoMixin`.

[:octicons-arrow-right-24: View Code](https://github.com/markurtz/disdantic/tree/main/examples/lazy_loading_and_introspection/)

</div>

<div class="card" markdown>
:material-magnify-expand: **Auto-Discovery & Diagnostics**

______________________________________________________________________

Demonstrates automatic package scanning and registration using `AutoImporterMixin`, programmatic and CLI-based registry diagnostics, and schema exports.

[:octicons-arrow-right-24: View Code](https://github.com/markurtz/disdantic/tree/main/examples/auto_discovery_and_diagnostics/)

</div>

</div>

!!! tip "Contributing an Example"
Have a useful snippet or pattern to share? See the [Contributing Guide](../community/contributing.md) to learn how to add a new example to this section.
