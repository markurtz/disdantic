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

# CLI, Diagnostics & Schema Export

This guide details how to query active registries, run compilation diagnostics, verify registry health, and export polymorphic schemas using the `disdantic` CLI and programmatic API.

## 1. Registry Discovery & Mapping

`disdantic` allows you to list and inspect active model registries within your application runtime or from the command line.

### Programmatic Discovery

The global `RegistryManager` tracks all active registries. Call `list_registries()` to obtain a sorted dictionary of active registry class names mapped to their registered keys and fully qualified import paths:

```python
from disdantic.registry import RegistryManager

# Retrieve the registry mapping
active_registries = RegistryManager.list_registries()

for registry, mapping in active_registries.items():
    print(f"Registry: {registry}")
    for key, fqcn in mapping.items():
        print(f"  - {key}: {fqcn}")
```

### CLI Discovery

Run the `list` subcommand to output a visual tree of all active registries and registered classes:

```console
$ disdantic list
```

To export the registry map as raw JSON (ideal for CI pipelines or external tooling integration), use the `--json` option:

```console
$ disdantic list --json
```

## 2. Programmatic & CLI Registry Diagnostics

You can audit the compilation health of your model registries and detect invalid or orphaned subclasses.

### Programmatic Verification

Use the `verify_registries()` function to scan configured packages and compile diagnostic results. It returns a `DiagnosticsReport` detailing health status, scanned packages, registry metrics, and import tracebacks:

```python
from disdantic.diagnose import verify_registries
from disdantic.settings import Settings

# Run diagnostics with custom settings
settings = Settings(auto_packages=["myapp.models"])
report = verify_registries(settings=settings)

if report.is_healthy:
    print("All registries compiled successfully!")
else:
    print("Diagnostics detected compilation errors:")
    print(f"Import Errors: {report.import_errors}")
```

> [!NOTE]
> If any Pydantic model in a registry fails `model_json_schema()`, the report's `is_healthy` status is automatically set to `False`.

### CLI Diagnostics

Execute the `diagnose` subcommand in your terminal to view a rich summary table of compilation health. The command prints tracebacks for compilation failures and exits with status code `1` if the workspace is unhealthy:

```console
$ disdantic diagnose --path /path/to/project
```

Output the diagnostics report directly to JSON using the `--json` flag:

```console
$ disdantic diagnose --json
```

## 3. Registry Schema Export

`disdantic` exports consolidated JSON schemas representing all registered subtypes of a registry base class.

### Programmatic Schema Export

Use `get_registry_schema()` to generate a collective schema dictionary. The function accepts the registry base class and a format argument:

```python
from disdantic.schema import get_registry_schema
from myapp.models import BaseMessage

# Generate a standard JSON schema
schema = get_registry_schema(BaseMessage, format="json")

# Generate an OpenAPI-compatible schema
openapi_schema = get_registry_schema(BaseMessage, format="openapi")
```

> [!IMPORTANT]
> Passing a class that does not subclass `PydanticClassRegistryMixin` to `get_registry_schema()` raises a `TypeError`.

### CLI Schema Export

Generate a schema directly from the command line by providing the dotted import path of the registry base class:

```console
$ disdantic schema myapp.models.BaseMessage --format openapi
```

#### OpenAPI Format Conversion

When exporting with `--format openapi`, `disdantic` translates Pydantic's default `$defs` references into standard OpenAPI structure under `components/schemas`.

#### Custom Output Files and Indentation

Save the generated schema directly to a file with custom indentation formatting:

```console
$ disdantic schema myapp.models.BaseMessage --output build/schema.json --indent 4
```
