"""
Settings configuration for the template-python application.

This module provides the primary configuration structure for the application
using Pydantic Settings. It aggregates configuration from multiple sources,
including environment variables and CLI arguments, and exposes a unified interface
for safe, typed configuration access across the codebase.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

__all__ = ["Settings"]


class Settings(BaseSettings):
    """
    Configuration state for the application.

    This class aggregates and prioritizes configuration from multiple sources,
    providing a unified state for the application. It is built on top of
    pydantic-settings to allow validation, default values, and type coercion.

    Example:
        .. code-block:: python

            from template_python.settings import Settings

            settings = Settings(environment="production")
            print(settings.project_root)
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        arbitrary_types_allowed=True,
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,
        env_prefix="TEMPLATE_PYTHON__",
    )
    """Pydantic config dict dictating environment prefixes and validation."""

    # Core Application Properties
    project_root: Path = Field(
        default_factory=Path.cwd,
        description=(
            "The root directory of the project. Used for resolving relative paths."
        ),
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="The current deployment environment of the application.",
    )

    def __str__(self) -> str:
        """
        Return a concise string representation of the settings.

        :return: A concise, human-readable string summary of the settings.
        :rtype: str
        """
        return (
            f"Settings(environment={self.environment!r}, "
            f"project_root={self.project_root!r})"
        )

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the settings.

        :return: A detailed string representation suitable for debugging.
        :rtype: str
        """
        return (
            f"Settings("
            f"environment={self.environment!r}, "
            f"project_root={self.project_root!r}"
            f")"
        )
