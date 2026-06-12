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

"""Configuration settings orchestration for disdantic polymorphism.

This module provides the central settings schema utilizing Pydantic Settings
to manage, validate, and load configuration parameters. It aggregates settings
from multiple sources, including constructor arguments, environment variables,
dotenv files, CLI inputs, and pyproject.toml configurations.

The primary interface is the Settings class, which defines validation schemas
for paths, environment states, registry discriminator configurations, dynamic
auto-discovery parameters, and validation compilation behaviors.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict,
)

__all__ = ["Settings", "get_settings", "reset_settings"]


class Settings(BaseSettings):
    """Central configuration store and validation schema for the disdantic package.

    This class serves as the single source of truth for runtime configurations,
    defining default options and loading overrides dynamically across modules.
    It integrates with Pydantic's BaseSettings to enforce type validation,
    coercion, and environment prefixing.

    Example:
        .. code-block:: python

            from disdantic.settings import Settings, get_settings

            # Initialize a localized settings instance
            settings = Settings(default_schema_discriminator="custom_type")
            assert settings.default_schema_discriminator == "custom_type"

            # Retrieve the global settings singleton instance
            global_settings = get_settings()
            print(global_settings.project_root)
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
    """Configuration dictionary defining Pydantic Settings behavior options.

    Controls environment variables parsing prefix, CLI integration arguments,
    pyproject.toml headers, and assignment validation rules.
    """

    # Core Application Properties
    project_root: Path = Field(
        default_factory=Path.cwd,
        description=(
            "Maps the file system paths and resolves relative configuration files."
        ),
    )

    # Registry & Serialization Settings
    default_schema_discriminator: str = Field(
        default="model_type",
        description=(
            "Maps and retrieves model types within Pydantic registries using this "
            "key name."
        ),
    )
    registry_auto_discovery: bool = Field(
        default=False,
        description=(
            "Enables automatic scanning and loading of subclasses during registry "
            "initialization."
        ),
    )

    # Auto Import Settings
    auto_packages: list[str] = Field(
        default_factory=list,
        description=(
            "Configures target package namespaces to scan, enabling dynamic model "
            "discovery across submodules."
        ),
    )
    auto_ignore_modules: list[str] = Field(
        default_factory=list,
        description=(
            "Configures submodule import paths to skip, mapping excluded modules "
            "during dynamic scanning."
        ),
    )

    # Schema Compilation Settings
    enable_schema_rebuilding: bool = Field(
        default=True,
        description=(
            "Enables dynamic rebuilding of validation schemas, triggering Pydantic "
            "model schema rebuilds."
        ),
    )
    schema_rebuild_parents: bool = Field(
        default=True,
        description=(
            "Enables parent propagation, mapping validation schema updates up the "
            "subclass MRO hierarchy."
        ),
    )

    # Introspection Settings
    info_exclude_keys: list[str] = Field(
        default_factory=lambda: ["info"],
        description=(
            "Maps specific fields to skip and exclude during InfoMixin logging."
        ),
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
        """Customize configuration loaders and define prioritize hierarchy.

        This method overrides the default Pydantic source loading priorities
        to determine the resolving order of configuration options.

        :param settings_cls: The settings class being constructed.
        :param init_settings: Settings passed directly to the class constructor.
        :param env_settings: Settings loaded from system environment variables.
        :param dotenv_settings: Settings loaded from active .env file streams.
        :param file_secret_settings: Settings loaded from secrets files paths.
        :returns: A tuple of settings sources ordered by loading priority.
        """
        _ = (file_secret_settings,)  # Allow unused variable to satisfy lint/format
        input_args = init_settings()
        project_root = Path(input_args.get("project_root") or Path.cwd())

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            PyprojectTomlConfigSettingsSource(
                settings_cls, toml_file=project_root / "pyproject.toml"
            ),
            CliSettingsSource(
                settings_cls,
                cli_ignore_unknown_args=True,
                cli_parse_args=True,
                cli_prefix=settings_cls.model_config.get("cli_prefix", ""),
            ),
        )

    def __str__(self) -> str:
        """Generate a concise string representation of the settings.

        :returns: A human-readable string summary of the configuration state.
        """
        return f"Settings(project_root={self.project_root!r})"

    def __repr__(self) -> str:
        """Generate a detailed string representation of the settings.

        :returns: A detailed debug string representation of the settings.
        """
        return f"Settings(project_root={self.project_root!r})"


def get_settings() -> Settings:
    """Retrieve the global Settings singleton instance.

    Uses double-checked locking to resolve initialization race conditions
    in multi-threaded applications.

    Example:
        .. code-block:: python

            from disdantic.settings import get_settings

            settings = get_settings()
            print(settings.project_root)

    :returns: The global Settings singleton instance.
    """
    global _global_settings  # noqa: PLW0603
    if _global_settings is None:
        with _settings_lock:
            if _global_settings is None:
                _global_settings = Settings()
    return _global_settings


def reset_settings() -> None:
    """Reset the global Settings singleton instance to None.

    Forces a complete reload and re-validation of settings on the next
    invocation of get_settings().

    Example:
        .. code-block:: python

            from disdantic.settings import reset_settings

            # Evicts active settings from memory
            reset_settings()

    :returns: None
    """
    global _global_settings  # noqa: PLW0603
    with _settings_lock:
        _global_settings = None


_settings_lock = threading.Lock()
_global_settings: Settings | None = None
