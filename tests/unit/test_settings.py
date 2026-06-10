"""Unit tests for the settings module."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from template_python.settings import Settings


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
        assert Settings.model_config.get("env_prefix") == "TEMPLATE_PYTHON__"
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
            Settings(environment="invalid_env")  # type: ignore[arg-type]

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: Settings) -> None:
        """Test Pydantic dumping and validation."""
        data_dict = valid_instances.model_dump()
        recreated_settings = Settings.model_validate(data_dict)
        assert recreated_settings.environment == valid_instances.environment
        assert recreated_settings.project_root == valid_instances.project_root

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
