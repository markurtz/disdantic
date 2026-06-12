# Telemetry & Settings Example

## Overview

This example demonstrates how to configure the `disdantic` library using a standard workspace `pyproject.toml` file. It showcases how settings are loaded according to a strict priority hierarchy, how registry classes dynamically fall back to the default discriminator key defined in the project configuration, and how to enable structured JSON telemetry logging with OpenTelemetry span tracing context.

## Prerequisites & Setup

Before running the example, ensure you have set up the project environment.

1. Install the required dependencies:

   ```bash
   pip install -e .
   pip install opentelemetry-api
   ```

   *Note: If you are using the Hatch development workflow, dependencies are resolved automatically within the environment.*

1. Navigate to the project root:

   ```bash
   cd /Users/markkurtz/code/github/markurtz/disdantic
   ```

## Execution Blueprint

Execute the example script using the python command:

```bash
python examples/telemetry_and_settings/main.py
```

Or, using the Hatch environment runner:

```bash
hatch run python examples/telemetry_and_settings/main.py
```

## Expected Results

When executed, the script outputs setting values to standard output and OpenTelemetry-compliant JSON logs to standard error:

```json
Loaded Settings Environment: staging
Loaded Discriminator from TOML: custom_type
Registry resolved discriminator key: custom_type
Successfully validated task type: EmailTask
Overridden Settings Environment: production
{"timestamp": "2026-06-12T12:34:33.069523-04:00", "severity_text": "INFO", "body": "Starting calculation cycle...", "resource": {"service.name": "disdantic"}, "attributes": {"module": "__main__", "function": "main", "line": 144, "process_id": 10936}}
{"timestamp": "2026-06-12T12:34:33.069680-04:00", "severity_text": "DEBUG", "body": "Calling function 'process_data' with args=(10,), kwargs={}", "resource": {"service.name": "disdantic"}, "attributes": {"module": "disdantic.logging", "function": "wrapper", "line": 327, "process_id": 10936}}
{"timestamp": "2026-06-12T12:34:33.069740-04:00", "severity_text": "DEBUG", "body": "Function 'process_data' returned: 20", "resource": {"service.name": "disdantic"}, "attributes": {"module": "disdantic.logging", "function": "wrapper", "line": 344, "process_id": 10936}}
{"timestamp": "2026-06-12T12:34:33.069783-04:00", "severity_text": "INFO", "body": "Calculation output: 20", "resource": {"service.name": "disdantic"}, "attributes": {"module": "__main__", "function": "main", "line": 146, "process_id": 10936}}
{"timestamp": "2026-06-12T12:34:33.069818-04:00", "severity_text": "DEBUG", "body": "Calling function 'process_data' with args=(-5,), kwargs={}", "resource": {"service.name": "disdantic"}, "attributes": {"module": "disdantic.logging", "function": "wrapper", "line": 327, "process_id": 10936}}
{"timestamp": "2026-06-12T12:34:33.069851-04:00", "severity_text": "ERROR", "body": "Exception occurred in function 'process_data': Value cannot be negative!", "resource": {"service.name": "disdantic"}, "attributes": {"module": "disdantic.logging", "function": "wrapper", "line": 334, "process_id": 10936, "exception.type": "ValueError", "exception.message": "Value cannot be negative!", "exception.stacktrace": "ValueError: Value cannot be negative!\n"}}
{"timestamp": "2026-06-12T12:34:33.070590-04:00", "severity_text": "WARNING", "body": "Caught expected telemetry exception.", "resource": {"service.name": "disdantic"}, "attributes": {"module": "__main__", "function": "main", "line": 151, "process_id": 10936}}
```

## Troubleshooting

- **Configuration not loaded from `pyproject.toml`**: Ensure that the tool options block is prefixed with `[tool.disdantic]`. The setting resolver looks strictly for this table header.
- **`.env` variables not overriding `pyproject.toml`**: Precedence is strict. Ensure environment variable names are prefixed with `DISDANTIC__` (e.g. `DISDANTIC__ENVIRONMENT=staging`).
- **Telemetry logs not showing up**: OpenTelemetry formatting requires the optional `opentelemetry-api` package to be installed. If not installed and `otel_formatting="enable"` is set, an `ImportError` is raised.
