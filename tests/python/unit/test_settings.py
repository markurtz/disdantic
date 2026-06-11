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

from disdantic.settings import Settings


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
            {"environment": "production"},
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
        assert Settings.model_config.get("env_prefix") == "DISDANTIC__"
        assert "project_root" in Settings.model_fields
        assert "environment" in Settings.model_fields

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: Settings) -> None:
        """Test proper initialization from the fixture."""
        assert valid_instances.environment in {"development", "staging", "production"}
        assert isinstance(valid_instances.project_root, Path)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Test initialization with invalid values fails validation."""
        with pytest.raises(ValidationError):
            Settings(environment="invalid_env")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: Settings) -> None:
        """Test Pydantic dumping and validation."""
        data_dict = valid_instances.model_dump()
        recreated_settings = Settings.model_validate(data_dict)
        assert recreated_settings.environment == valid_instances.environment
        assert recreated_settings.project_root == valid_instances.project_root

    @pytest.mark.regression
    def test_settings_customise_sources(self) -> None:
        """Test customization of settings sources."""
        init_source = MockSettingsSource(Settings)
        sources = Settings.settings_customise_sources(
            Settings, init_source, init_source, init_source, init_source
        )
        assert len(sources) == 5
        assert sources[0] is init_source
        assert isinstance(sources[1], PyprojectTomlConfigSettingsSource)
        assert sources[2] is init_source
        assert sources[3] is init_source
        assert isinstance(sources[4], CliSettingsSource)

    @pytest.mark.smoke
    def test___str__(self, valid_instances: Settings) -> None:
        """Test the concise string representation."""
        string_val = str(valid_instances)
        assert "Settings(" in string_val
        assert "environment=" in string_val
        assert "project_root=" in string_val

    @pytest.mark.smoke
    def test___repr__(self, valid_instances: Settings) -> None:
        """Test the detailed string representation."""
        repr_val = repr(valid_instances)
        assert "Settings(" in repr_val
        assert "environment=" in repr_val
        assert "project_root=" in repr_val
