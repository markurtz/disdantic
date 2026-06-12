# Auto-Discovery & Diagnostics Example

This example demonstrates how to configure automatic package scanning, dynamic module registration, programmatic and CLI diagnostics, and schema exports using `disdantic`.

It shows how `AutoImporterMixin` can dynamically scan a Python package to discover and register subclasses of `PydanticClassRegistryMixin`, and how you can run diagnostics on your registries to detect compilation issues (such as unresolvable forward references or syntax errors) before running your application.

## Prerequisites & Setup

1. Ensure the core `disdantic` package is installed and initialized in your Hatch environment:

   ```bash
   .venv/bin/hatch env create
   ```

1. Install example-specific dependencies:

   ```bash
   .venv/bin/hatch run python:pip install -r examples/auto_discovery_and_diagnostics/requirements.txt
   ```

## Execution Blueprint

To run the programmatic example, execute the following command from the root of the repository:

```bash
.venv/bin/hatch run python:python examples/auto_discovery_and_diagnostics/main.py
```

To list registries using the `disdantic` CLI, set the PYTHONPATH and auto-packages environment variables:

```bash
PYTHONPATH=. DISDANTIC__AUTO_PACKAGES='["examples.auto_discovery_and_diagnostics.plugins"]' DISDANTIC__AUTO_IGNORE_MODULES='["examples.auto_discovery_and_diagnostics.plugins.broken_plugin"]' .venv/bin/hatch run python:python -m disdantic list
```

To run diagnostics using the `disdantic` CLI:

```bash
PYTHONPATH=. DISDANTIC__AUTO_PACKAGES='["examples.auto_discovery_and_diagnostics.plugins"]' .venv/bin/hatch run python:python -m disdantic diagnose --path examples/auto_discovery_and_diagnostics
```

## Expected Results

When running the programmatic example `main.py`, you should see the following output in the console:

```text
Discovered Registries: {'PluginRegistry': {'healthy_plugin': 'examples.auto_discovery_and_diagnostics.plugins.healthy_plugin.HealthyPlugin'}}
Diagnostics Health: Unhealthy
Registry: PluginRegistry
  - Model 'broken_plugin': status=error
    Error: name 'UnresolvableType' is not defined

For further information visit https://errors.pydantic.dev/2.13/u/undefined-annotation
  - Model 'healthy_plugin': status=healthy
```

## Troubleshooting

- **MRO Conflicts**: Always ensure you inherit directly from `PydanticClassRegistryMixin` rather than combining both mixins on your target class. `PydanticClassRegistryMixin` already inherits from `AutoImporterMixin`.
- **Diagnostics Errors**: If a plugin is reported with a status of `error`, verify that all forward references (such as type annotations used in models) are correctly defined in the module or can be resolved at runtime.
