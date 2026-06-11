# Reference

The Reference section contains the complete technical documentation for `disdantic` — API classes, configuration options, CLI reference, and test coverage reports.

## In This Section

<div class="grid cards" markdown>

-   **[:material-console: CLI](cli.md)**

    Command-line usage and subcommands.

-   **[:material-api: Python API](python_api/index.md)**

    Complete public Python API documentation.

-   **[:material-shield-check: Python Tests](python_coverage.md)**

    Python coverage reports for unit, integration, functional, and E2E tests.

</div>

## Python API Usage

`disdantic` can also be used programmatically in your own Python scripts:

```python
from disdantic import Settings, configure_logger, logger
from disdantic.logging import LoggingSettings

# Initialize the global logger
configure_logger(LoggingSettings(enabled=True, level="INFO"))

# Load application settings
settings = Settings(environment="production")

# Log the current configuration
logger.info("Application initialized with settings: {}", settings)
```
