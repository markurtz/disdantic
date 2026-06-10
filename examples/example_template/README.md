# Example Template

This directory serves as a generic template for creating new examples in the `template-python` repository. It demonstrates the standard structure, documentation, and foundational code required for a well-formed example, ensuring it adheres to the latest standards and workflows.

## Prerequisites

1. Ensure you have installed the core package dependencies from the root repository.
   ```bash
   hatch env create
   ```
1. Install any example-specific requirements (none required for this basic template):
   ```bash
   pip install -r requirements.txt
   ```

## Running the Example

Execute the main script from the root of the repository to ensure all relative paths and imports resolve correctly:

```bash
python examples/example_template/main.py
```

## Core Components Highlighted

This template highlights the following essential components that should be included in most project examples:

- **Standard Structure:** A contained directory with its own `README.md`, `requirements.txt`, and executable python script (`main.py`).
- **Configuration (Settings):** How to initialize the `Settings` model using `template_python.settings.Settings`.
- **Telemetry (Logging):** How to properly configure application logging using `template_python.logging.LoggingSettings` and `configure_logger` to emit structured logs.
- **Best Practices:** Demonstration of clear code organization, descriptive docstrings, and safe execution patterns (`if __name__ == "__main__":`).
