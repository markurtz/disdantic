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

"""Integration tests for the settings module and CLI propagation."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
)
from typer.testing import CliRunner

import disdantic.settings as settings_module
from disdantic.__main__ import app
from disdantic.settings import Settings, get_settings, reset_settings
from disdantic.version import __version__


class MockSettingsSource(PydanticBaseSettingsSource):
    """Mock settings source for testing customise_sources."""

    def __call__(self) -> dict[str, Any]:
        return {}

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, "", False


@pytest.mark.smoke
def test_all_export() -> None:
    """Validate public variables, constants, and module-level exports."""
    assert hasattr(settings_module, "__all__")
    expected_exports = ["Settings", "get_settings", "reset_settings"]
    assert sorted(settings_module.__all__) == sorted(expected_exports)


class TestCLIEntrypoint:
    """Integration test suite for the CLI entrypoint."""

    @pytest.mark.smoke
    def test_help_flag(self) -> None:
        """Test invoking help flag via Typer CliRunner."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Disdantic" in result.stdout
        assert "Show the application version" in result.stdout

    @pytest.mark.smoke
    def test_version_flag(self) -> None:
        """Test invoking version flag via Typer CliRunner."""
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert f"disdantic v{__version__}" in result.stdout

    @pytest.mark.sanity
    def test_default_execution(self) -> None:
        """Test invoking CLI without arguments."""
        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == 0

    @pytest.mark.sanity
    def test_invalid_arguments(self) -> None:
        """Test invoking CLI with invalid arguments."""
        runner = CliRunner()
        result = runner.invoke(app, ["--invalid-flag"])
        assert result.exit_code != 0

    @pytest.mark.regression
    @pytest.mark.parametrize("env_name", ["staging", "production"])
    def test_settings_propagation(self, env_name: str) -> None:
        """Test CLI arguments settings propagation."""
        runner = CliRunner()
        instances: list[Settings] = []

        def wrap_settings(*args: Any, **kwargs: Any) -> Settings:
            instance = Settings(*args, **kwargs)
            instances.append(instance)
            return instance

        original_argv = sys.argv
        sys.argv = ["disdantic", "--disdantic_.environment", env_name]
        try:
            with patch("disdantic.__main__.Settings", new=wrap_settings):
                result = runner.invoke(app, [])
                assert result.exit_code == 0
                assert len(instances) == 1
                assert instances[0].environment == env_name
        finally:
            sys.argv = original_argv

    @pytest.mark.regression
    def test_env_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables take precedence over CLI arguments."""
        runner = CliRunner()
        instances: list[Settings] = []

        def wrap_settings(*args: Any, **kwargs: Any) -> Settings:
            instance = Settings(*args, **kwargs)
            instances.append(instance)
            return instance

        monkeypatch.setenv("DISDANTIC__ENVIRONMENT", "production")
        original_argv = sys.argv
        sys.argv = ["disdantic", "--disdantic_.environment", "staging"]
        try:
            with patch("disdantic.__main__.Settings", new=wrap_settings):
                result = runner.invoke(app, [])
                assert result.exit_code == 0
                assert len(instances) == 1
                assert instances[0].environment == "production"
        finally:
            sys.argv = original_argv

    @pytest.mark.regression
    def test_toml_precedence(self, tmp_path: Path) -> None:
        """Test that settings correctly load values from pyproject.toml."""
        toml_content = (
            "[tool.disdantic]\n"
            'default_schema_discriminator = "custom_type"\n'
            'environment = "staging"\n'
        )
        toml_file = tmp_path / "pyproject.toml"
        toml_file.write_text(toml_content, encoding="utf-8")

        # Instantiate Settings targeting the temporary root
        settings = Settings(project_root=tmp_path)
        assert settings.default_schema_discriminator == "custom_type"
        assert settings.environment == "staging"


class TestSettings:
    """Integration test suite for the Settings class."""

    @pytest.fixture(
        params=[
            {},
            {"environment": "production"},
            {"auto_packages": ["pkg1", "pkg2"]},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> Settings:
        """Fixture providing varied valid instances of Settings."""
        return Settings(**request.param)

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate structural contracts and inheritance lineages."""
        assert issubclass(Settings, BaseSettings)
        # Check that class signature contains key fields
        fields = Settings.model_fields
        assert "project_root" in fields
        assert "environment" in fields
        assert "default_schema_discriminator" in fields
        assert "registry_auto_discovery" in fields
        assert "auto_packages" in fields
        assert "auto_ignore_modules" in fields
        assert "enable_schema_rebuilding" in fields
        assert "schema_rebuild_parents" in fields
        assert "info_exclude_keys" in fields

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: Settings) -> None:
        """Test proper initialization of Settings."""
        assert isinstance(valid_instances, Settings)
        assert valid_instances.environment in {"development", "staging", "production"}

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify that invalid field values raise ValidationError."""
        with pytest.raises(ValidationError):
            Settings(environment=cast("Any", "invalid_env"))

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization defaults when arguments are missing."""
        # By design, settings can be fully initialized without any arguments.
        settings = Settings()
        assert settings.environment == "development"
        assert settings.default_schema_discriminator == "model_type"

    @pytest.mark.regression
    def test_settings_customise_sources(self) -> None:
        """Test customise sources priority structure."""
        mock_source = MockSettingsSource(Settings)
        sources = Settings.settings_customise_sources(
            Settings, mock_source, mock_source, mock_source, mock_source
        )
        assert len(sources) == 5
        assert sources[0] is mock_source
        assert sources[1] is mock_source
        assert sources[2] is mock_source
        assert isinstance(sources[3], PyprojectTomlConfigSettingsSource)
        assert isinstance(sources[4], CliSettingsSource)

    @pytest.mark.smoke
    def test_str(self, valid_instances: Settings) -> None:
        """Verify __str__ outputs correct information."""
        string_repr = str(valid_instances)
        assert "Settings(" in string_repr
        assert f"environment='{valid_instances.environment}'" in string_repr

    @pytest.mark.smoke
    def test_repr(self, valid_instances: Settings) -> None:
        """Verify __repr__ outputs correct debug information."""
        debug_repr = repr(valid_instances)
        assert "Settings(" in debug_repr
        assert f"environment='{valid_instances.environment}'" in debug_repr

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: Settings) -> None:
        """Verify data dump and reload validation integrity."""
        dumped_data = valid_instances.model_dump()
        reloaded_settings = Settings.model_validate(dumped_data)
        assert reloaded_settings.environment == valid_instances.environment
        assert reloaded_settings.project_root == valid_instances.project_root
        assert reloaded_settings.auto_packages == valid_instances.auto_packages


class TestGetSettings:
    """Integration test suite for the get_settings global function."""

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        ("env_var", "env_value", "expected_val"),
        [
            ("DISDANTIC__ENVIRONMENT", "staging", "staging"),
            ("DISDANTIC__ENVIRONMENT", "production", "production"),
            ("DISDANTIC__DEFAULT_SCHEMA_DISCRIMINATOR", "custom_key", "custom_key"),
        ],
    )
    def test_invocation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_var: str,
        env_value: str,
        expected_val: str,
    ) -> None:
        """Verify get_settings returns correctly configured singleton instances."""
        # Setup
        reset_settings()
        monkeypatch.setenv(env_var, env_value)

        # Invoke
        settings_one = get_settings()
        settings_two = get_settings()

        # Assertions
        assert settings_one is settings_two
        if env_var == "DISDANTIC__ENVIRONMENT":
            assert settings_one.environment == expected_val
        elif env_var == "DISDANTIC__DEFAULT_SCHEMA_DISCRIMINATOR":
            assert settings_one.default_schema_discriminator == expected_val

        # Teardown
        reset_settings()

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        ("env_var", "invalid_value"),
        [
            ("DISDANTIC__ENVIRONMENT", "invalid_env_name"),
            ("DISDANTIC__REGISTRY_AUTO_DISCOVERY", "not_a_bool"),
            ("DISDANTIC__ENABLE_SCHEMA_REBUILDING", "not_a_bool"),
        ],
    )
    def test_invalid(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_var: str,
        invalid_value: str,
    ) -> None:
        """Verify that invalid environment configuration raises ValidationError.

        This check ensures get_settings validation holds on invalid env
        parameters.
        """
        # Setup
        reset_settings()
        monkeypatch.setenv(env_var, invalid_value)

        # Invoke and Assert
        with pytest.raises(ValidationError):
            get_settings()

        # Teardown
        reset_settings()

    @pytest.mark.regression
    def test_thread_safety(self) -> None:
        """Verify concurrent access returns the same singleton instance safely."""
        reset_settings()
        instances: list[Settings] = []
        threads: list[threading.Thread] = []

        def worker() -> None:
            settings_instance = get_settings()
            instances.append(settings_instance)

        for _unused_index in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(instances) == 10
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance


class TestResetSettings:
    """Integration test suite for the reset_settings global function."""

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        ("env_var", "env_value"),
        [
            ("DISDANTIC__ENVIRONMENT", "staging"),
            ("DISDANTIC__ENVIRONMENT", "production"),
        ],
    )
    def test_invocation(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_var: str,
        env_value: str,
    ) -> None:
        """Verify reset_settings clears the singleton and forces a reload."""
        # Setup
        reset_settings()
        settings_one = get_settings()

        # Invoke (with modified environment)
        reset_settings()
        monkeypatch.setenv(env_var, env_value)
        settings_two = get_settings()

        # Assertions
        assert settings_one is not settings_two
        assert settings_two.environment == env_value

        # Teardown
        reset_settings()

    @pytest.mark.sanity
    @pytest.mark.parametrize("repeat_count", [1, 2, 5])
    def test_invalid(self, repeat_count: int) -> None:
        """Verify reset_settings behaves gracefully.

        Ensures reset_settings is idempotent under repeated calls.
        """
        # Setup
        reset_settings()

        # Invoke repeated resets
        for _unused_index in range(repeat_count):
            reset_settings()

        # Verify get_settings still works and constructs a fresh default instance
        settings_instance = get_settings()
        assert settings_instance.environment == "development"

        # Teardown
        reset_settings()
