# Copyright 2026 markurtz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Settings configuration for the disdantic application.

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
    CliSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
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

            from disdantic.settings import Settings

            settings = Settings(environment="production")
            print(settings.project_root)
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        arbitrary_types_allowed=True,
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,
        env_prefix="DISDANTIC__",
        cli_prefix="disdantic_",
        cli_parse_args=True,
        pyproject_toml_table_header=("tool", "disdantic"),
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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        Customize configuration sources and priority for loading settings.

        This method overrides the default pydantic-settings loaders to resolve
        values in the following order: constructor kwargs, pyproject.toml,
        dotenv files, environment variables, and CLI arguments.
        """
        _ = (file_secret_settings,)  # Allow unused variable to satisfy lint/format
        input_args = init_settings()
        project_root = Path(input_args.get("project_root") or Path.cwd())

        return (
            init_settings,
            PyprojectTomlConfigSettingsSource(
                settings_cls, toml_file=project_root / "pyproject.toml"
            ),
            dotenv_settings,
            env_settings,
            CliSettingsSource(
                settings_cls,
                cli_ignore_unknown_args=True,
                cli_parse_args=True,
                cli_prefix=settings_cls.model_config.get("cli_prefix", ""),
            ),
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
