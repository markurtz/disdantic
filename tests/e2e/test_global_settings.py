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

"""End-to-end test suite for unified global configuration hierarchy (US-12)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

import disdantic.settings as settings_module
from disdantic.settings import Settings, get_settings, reset_settings


class TestUnifiedGlobalConfigurationHierarchy:
    """E2E test class validating US-12 Global Configuration features."""

    @pytest.fixture(
        params=[
            {},
            {"default_schema_discriminator": "custom_type"},
            {"registry_auto_discovery": True},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> Settings:
        """Fixture providing isolated, valid configurations of Settings."""
        return Settings(**request.param)

    @pytest.mark.smoke
    def test_settings_contract(self) -> None:
        """Validate structural contracts of Settings."""
        fields = Settings.model_fields
        assert "project_root" in fields
        assert "default_schema_discriminator" in fields
        assert "registry_auto_discovery" in fields
        assert "auto_packages" in fields
        assert "auto_ignore_modules" in fields
        assert "enable_schema_rebuilding" in fields
        assert "schema_rebuild_parents" in fields
        assert "info_exclude_keys" in fields

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: Settings) -> None:
        """Verify correct initial wiring."""
        assert isinstance(valid_instances, Settings)
        assert isinstance(valid_instances.project_root, Path)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify that passing invalid configuration values raises ValidationError."""
        with pytest.raises(ValidationError) as validation_error:
            Settings(registry_auto_discovery=cast("Any", "not_a_boolean"))
        assert "registry_auto_discovery" in str(validation_error.value)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization defaults when arguments are omitted."""
        settings_instance = Settings()
        assert settings_instance.default_schema_discriminator == "model_type"
        assert settings_instance.registry_auto_discovery is False

    @pytest.mark.smoke
    def test_marshalling(self, valid_instances: Settings) -> None:
        """Verify model serialization and deserialization boundaries."""
        dumped_data = valid_instances.model_dump()
        reloaded_instance = Settings.model_validate(dumped_data)
        assert reloaded_instance.project_root == valid_instances.project_root
        assert reloaded_instance.auto_packages == valid_instances.auto_packages

    @pytest.mark.regression
    def test_settings_override_hierarchy_precedence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify unified configuration hierarchy override precedence.

        Precedence must resolve as:
        constructor args > env variables > pyproject.toml > defaults.
        """
        # Create a mock pyproject.toml in the temporary path
        toml_content = (
            "[tool.disdantic]\n"
            "registry_auto_discovery = false\n"
            "default_schema_discriminator = 'toml_discriminator'\n"
        )
        pyproject_file = tmp_path / "pyproject.toml"
        pyproject_file.write_text(toml_content, encoding="utf-8")

        # Set environment variables
        monkeypatch.setenv("DISDANTIC__REGISTRY_AUTO_DISCOVERY", "true")
        monkeypatch.setenv(
            "DISDANTIC__DEFAULT_SCHEMA_DISCRIMINATOR", "env_discriminator"
        )

        # 1. Constructor parameters must have highest priority
        settings_constructor = Settings(
            project_root=tmp_path,
            registry_auto_discovery=False,
            default_schema_discriminator="constructor_discriminator",
        )
        assert settings_constructor.registry_auto_discovery is False
        assert (
            settings_constructor.default_schema_discriminator
            == "constructor_discriminator"
        )

        # 2. Environment variables override pyproject.toml configurations
        settings_env = Settings(project_root=tmp_path)
        assert settings_env.registry_auto_discovery is True
        assert settings_env.default_schema_discriminator == "env_discriminator"

        # 3. pyproject.toml configurations override default values
        monkeypatch.delenv("DISDANTIC__REGISTRY_AUTO_DISCOVERY", raising=False)
        monkeypatch.delenv("DISDANTIC__DEFAULT_SCHEMA_DISCRIMINATOR", raising=False)
        settings_toml = Settings(project_root=tmp_path)
        assert settings_toml.registry_auto_discovery is False
        assert settings_toml.default_schema_discriminator == "toml_discriminator"

    @pytest.mark.regression
    def test_thread_safe_double_checked_settings_singleton(self) -> None:
        """Verify thread-safety and eviction of get_settings / reset_settings."""
        reset_settings()

        # Wrap the original settings module level lock to monitor interactions
        original_lock = settings_module._settings_lock
        mock_lock = MagicMock(wraps=original_lock)

        with patch.object(settings_module, "_settings_lock", mock_lock):
            # Verify singleton returns same instance on multiple calls
            settings_first = get_settings()
            settings_second = get_settings()
            assert settings_first is settings_second
            assert mock_lock.__enter__.called

        # Evict singleton from memory
        reset_settings()
        assert settings_module._global_settings is None

        # Spawning concurrent threads calling get_settings using real lock
        instances: list[Settings] = []
        threads: list[threading.Thread] = []

        def worker() -> None:
            instances.append(get_settings())

        for _index in range(20):
            thread_worker = threading.Thread(target=worker)
            threads.append(thread_worker)
            thread_worker.start()

        for thread_worker in threads:
            thread_worker.join()

        # Ensure all threads retrieved the identical singleton instance
        assert len(instances) == 20
        singleton_instance = instances[0]
        for retrieved_instance in instances:
            assert retrieved_instance is singleton_instance
