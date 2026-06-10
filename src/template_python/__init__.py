"""
Core initialization module for the template-python package.

This module serves as the primary entry point for the library, exposing the public
API components such as logging settings, application configuration, and version
metadata for convenient access by downstream consumers.
"""

from __future__ import annotations

from .logging import LoggingSettings, configure_logger, logger
from .settings import Settings
from .version import __version__

__all__ = ["LoggingSettings", "Settings", "__version__", "configure_logger", "logger"]
