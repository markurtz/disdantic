# Reference

The Reference section contains the complete technical documentation for template-python — API classes and configuration options. This is the section to bookmark when you need to look something up.

## In This Section

<div class="grid cards" markdown>

<div class="card" markdown>
:material-code-json: **API Reference**

______________________________________________________________________

Auto-generated documentation for all public classes, methods, and modules.

[:octicons-arrow-right-24: Python API Reference](api/template_python/)

</div>

<div class="card" markdown>
:material-test-tube: **Test Coverage**

______________________________________________________________________

Run `hatch run test:all-cov` to generate HTML reports locally, or view the latest pipeline runs:

- [:octicons-arrow-right-24: Unit Tests](../coverage/unit/htmlcov/index.html)
- [:octicons-arrow-right-24: Integration Tests](../coverage/integration/htmlcov/index.html)
- [:octicons-arrow-right-24: End-to-End Tests](../coverage/e2e/htmlcov/index.html)

</div>

</div>

## Python API Usage

`template-python` can also be used programmatically in your own Python scripts:

```python
from template_python import Settings, configure_logger, logger
from template_python.logging import LoggingSettings

# Initialize the global logger
configure_logger(LoggingSettings(enabled=True, level="INFO"))

# Load application settings
settings = Settings(environment="production")

# Log the current configuration
logger.info("Application initialized with settings: {}", settings)
```

## Generating Reference Docs

This project is pre-configured to work with [`mkdocstrings`](https://mkdocstrings.github.io/) for auto-generating API documentation from docstrings.

### Setup

> [!NOTE]
> `mkdocstrings` supports multiple languages via handlers (e.g., Python, C++, Crystal). See the [mkdocstrings documentation](https://mkdocstrings.github.io/) to configure it for your language.

1. The plugin and its Python handler are already managed by Hatch in the `docs` environment (`mkdocstrings[python]`).
1. Configure `mkdocs.yml` according to your language handler and create your reference pages.
