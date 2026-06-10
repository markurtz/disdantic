"""
A generic example template demonstrating the basic initialization
and usage of the template_python framework.

This script shows how to:
1. Load configuration using the standard Settings model.
2. Initialize the centralized logging system.
3. Execute standard application logic.
"""

from template_python.logging import LoggingSettings, configure_logger, logger
from template_python.settings import Settings


def main() -> None:
    # 1. Initialize configuration
    # Settings automatically loads from the environment or .env file
    # matching the TEMPLATE_PYTHON__ prefix.
    settings = Settings()

    # 2. Configure logging
    # Enable logging for the example and configure output format
    logging_config = LoggingSettings(
        enabled=True,
        level="DEBUG",
        clear_loggers=True,
        filter=None,
    )
    configure_logger(logging_config)

    # 3. Application logic
    logger.info("Starting example template")

    logger.debug(f"Current environment: {settings.environment}")
    logger.debug(f"Project root: {settings.project_root}")

    logger.success("Example completed successfully!")


if __name__ == "__main__":
    main()
