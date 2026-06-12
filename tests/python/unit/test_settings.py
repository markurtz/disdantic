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

"""Unit tests for the settings module."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
)

from disdantic.settings import Settings, get_settings, reset_settings
from disdantic.settings import __all__ as settings_exports


class MockSettingsSource(PydanticBaseSettingsSource):
    """Mock settings source for testing customise_sources."""

    def __call__(self) -> dict[str, Any]:
        return {"project_root": Path("/test/tmp")}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, "", False


class TestSettings:
    """Test suite for the Settings model."""

    @pytest.fixture(
        params=[
            {},
            {"default_schema_discriminator": "custom_type"},
            {
                "default_schema_discriminator": "another_type",
                "project_root": Path("/test/root"),
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> Settings:
        """Fixture providing varied valid instances of Settings."""
        return Settings(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the class signature and extensions."""
        assert issubclass(Settings, BaseSettings)
        assert hasattr(Settings, "model_config")

        config = Settings.model_config
        assert config.get("env_prefix") == "DISDANTIC__"
        assert config.get("cli_prefix") == "disdantic_"
        assert config.get("cli_parse_args") is True
        assert config.get("pyproject_toml_table_header") == ("tool", "disdantic")

        fields = Settings.model_fields
        assert "project_root" in fields
        assert "default_schema_discriminator" in fields
        assert "registry_auto_discovery" in fields
        assert "auto_packages" in fields
        assert "auto_ignore_modules" in fields
        assert "enable_schema_rebuilding" in fields
        assert "schema_rebuild_parents" in fields
        assert "info_exclude_keys" in fields

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: Settings) -> None:
        """Test proper initialization from the fixture."""
        assert isinstance(valid_instances, Settings)
        assert isinstance(valid_instances.project_root, Path)
        assert isinstance(valid_instances.default_schema_discriminator, str)
        assert isinstance(valid_instances.registry_auto_discovery, bool)
        assert isinstance(valid_instances.auto_packages, list)
        assert isinstance(valid_instances.auto_ignore_modules, list)
        assert isinstance(valid_instances.enable_schema_rebuilding, bool)
        assert isinstance(valid_instances.schema_rebuild_parents, bool)
        assert isinstance(valid_instances.info_exclude_keys, list)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Test initialization with invalid values fails validation."""
        with pytest.raises(ValidationError):
            Settings(registry_auto_discovery="invalid_bool")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Test initialization with None for non-optional fields fails validation."""
        with pytest.raises(ValidationError):
            Settings(default_schema_discriminator=None)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        with pytest.raises(ValidationError):
            Settings(project_root=None)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: Settings) -> None:
        """Test Pydantic dumping and validation."""
        data_dict = valid_instances.model_dump()
        recreated_settings = Settings.model_validate(data_dict)
        assert recreated_settings.project_root == valid_instances.project_root
        assert (
            recreated_settings.default_schema_discriminator
            == valid_instances.default_schema_discriminator
        )

    @pytest.mark.regression
    def test_settings_customise_sources(self) -> None:
        """Test customization of settings sources."""
        init_source = MockSettingsSource(Settings)
        sources = Settings.settings_customise_sources(
            Settings, init_source, init_source, init_source, init_source
        )
        assert len(sources) == 5
        assert sources[0] is init_source
        assert sources[1] is init_source
        assert sources[2] is init_source

        toml_source = sources[3]
        assert isinstance(toml_source, PyprojectTomlConfigSettingsSource)
        assert toml_source.toml_file_path == Path("/test/tmp/pyproject.toml")

        cli_source = sources[4]
        assert isinstance(cli_source, CliSettingsSource)

    @pytest.mark.smoke
    def test___str__(self, valid_instances: Settings) -> None:
        """Test the concise string representation."""
        string_val = str(valid_instances)
        assert "Settings(" in string_val
        assert f"project_root={valid_instances.project_root!r}" in string_val

    @pytest.mark.smoke
    def test___repr__(self, valid_instances: Settings) -> None:
        """Test the detailed string representation."""
        repr_val = repr(valid_instances)
        assert "Settings(" in repr_val
        assert f"project_root={valid_instances.project_root!r}" in repr_val


class TestGetSettings:
    """Test suite for the get_settings global function."""

    @pytest.mark.sanity
    def test_invocation(self) -> None:
        """Verify retrieval of the global Settings singleton and thread safety."""
        reset_settings()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
        assert isinstance(settings1, Settings)

        results = []

        def worker() -> None:
            results.append(get_settings())

        threads = [threading.Thread(target=worker) for idx in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 10
        for instance in results:
            assert instance is settings1

    @pytest.mark.sanity
    def test_invalid(self) -> None:
        """Verify get_settings returns a settings instance on clean setup."""
        reset_settings()
        settings_instance = get_settings()
        assert settings_instance is not None


class TestResetSettings:
    """Test suite for the reset_settings global function."""

    @pytest.mark.sanity
    def test_invocation(self) -> None:
        """Verify resetting the global settings instance."""
        reset_settings()
        settings1 = get_settings()

        reset_settings()
        settings2 = get_settings()

        assert settings1 is not settings2


@pytest.mark.smoke
def test_exports() -> None:
    """Verify module-level exports config."""
    assert "Settings" in settings_exports
    assert "get_settings" in settings_exports
    assert "reset_settings" in settings_exports
    assert len(settings_exports) == 3
