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

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Literal

import pytest

from disdantic.exceptions import MissingPackagesError
from disdantic.importer import AutoImporterMixin
from disdantic.registry import (
    PydanticClassRegistryMixin,
    RegistryManager,
    RegistryMixin,
)
from disdantic.settings import get_settings, reset_settings


class RegistryA(RegistryMixin[type]):
    """Test registry A for E2E programmatic discovery tests."""


class RegistryB(RegistryMixin[type]):
    """Test registry B for E2E programmatic discovery tests."""


class BaseE2EModel(PydanticClassRegistryMixin):
    """Base model class used to test PydanticClassRegistryMixin serialization."""

    schema_discriminator = "msg_type"
    msg_type: str


class TestRegistryDiscovery:
    """End-to-End test suite validating programmatic registry discovery."""

    @pytest.fixture(autouse=True)
    def clean_registries(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        RegistryA.clear_registry()
        RegistryB.clear_registry()
        BaseE2EModel.clear_registry()
        yield
        RegistryA.clear_registry()
        RegistryB.clear_registry()
        BaseE2EModel.clear_registry()
        reset_settings()

    @pytest.fixture(params=["simple", "complex"])
    def valid_instances(self, request: pytest.FixtureRequest) -> dict[str, str]:
        """Fixture supplying configured registration details."""
        if request.param == "simple":
            return {
                "key_a": "key_a1",
                "key_b": "key_b1",
                "class_a": "TargetA",
                "class_b": "TargetB",
            }
        return {
            "key_a": "complex_key_a",
            "key_b": "complex_key_b",
            "class_a": "ComplexTargetA",
            "class_b": "ComplexTargetB",
        }

    @pytest.mark.smoke
    def test_environment_contract_validation(self) -> None:
        """Validate structural registry contracts and class configurations."""
        assert issubclass(RegistryA, RegistryMixin)
        assert issubclass(RegistryB, RegistryMixin)
        assert issubclass(BaseE2EModel, PydanticClassRegistryMixin)
        assert hasattr(RegistryManager, "list_registries")

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: dict[str, str]) -> None:
        """Verify dynamic class registration and global programmatic discovery."""
        key_a = valid_instances["key_a"]
        key_b = valid_instances["key_b"]

        @RegistryA.register(key_a)
        class TargetA:
            pass

        @RegistryB.register(key_b)
        class TargetB:
            pass

        # Call list_registries to query all discovered registries
        registry_map = RegistryManager.list_registries()

        assert "RegistryA" in registry_map
        assert "RegistryB" in registry_map
        assert registry_map["RegistryA"][key_a] == f"{__name__}.{TargetA.__name__}"
        assert registry_map["RegistryB"][key_b] == f"{__name__}.{TargetB.__name__}"

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify handling of invalid config settings causing imports to fail."""
        settings = get_settings()
        settings.auto_packages = ["non_existent_package_12345"]

        with pytest.raises(ImportError, match="could not be resolved"):
            RegistryManager.list_registries()

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify behavior when no packages are configured for discovery."""
        settings = get_settings()
        settings.auto_packages = []

        class EmptyImporter(AutoImporterMixin):
            pass

        with pytest.raises(MissingPackagesError, match="must be configured"):
            EmptyImporter.auto_import_package_modules()

    @pytest.mark.regression
    def test_dynamic_registry_resolution(self, valid_instances: dict[str, str]) -> None:
        """Verify that dynamically resolved keys execute correctly."""
        key_a = valid_instances["key_a"]

        @RegistryA.register(key_a)
        class DynamicTargetA:
            pass

        assert RegistryA.is_registered(key_a) is True
        assert RegistryA.get_registered_object(key_a) is DynamicTargetA
        assert DynamicTargetA in RegistryA.registered_objects()

    @pytest.mark.regression
    def test_marshalling(self) -> None:
        """Verify Pydantic model serialization/deserialization."""

        @BaseE2EModel.register("text")
        class TextE2EModel(BaseE2EModel):
            msg_type: Literal["text"] = "text"
            content: str

        payload = {"msg_type": "text", "content": "e2e_data"}

        validated = BaseE2EModel.model_validate(payload)
        assert isinstance(validated, TextE2EModel)
        assert validated.content == "e2e_data"
        assert validated.msg_type == "text"

        dumped = validated.model_dump()
        assert dumped == payload


class TestCLIEntrypoint:
    """End-to-End test suite validating CLI entrypoint listing of registries."""

    def _create_temp_package(
        self, tmp_path: Path, pkg_name: str, key_a: str, key_b: str
    ) -> None:
        """Helper to create a temporary package directory with test registries."""
        pkg_dir = tmp_path / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)

        init_content = f"""# Copyright 2026 markurtz
# Apache License 2.0
from __future__ import annotations
from disdantic.registry import RegistryMixin

class RegistryA(RegistryMixin[type]):
    pass

class RegistryB(RegistryMixin[type]):
    pass

@RegistryA.register("{key_a}")
class TargetA:
    pass

@RegistryB.register("{key_b}")
class TargetB:
    pass
"""
        (pkg_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    @pytest.mark.sanity
    def test_cli_tree_view(self, tmp_path: Path) -> None:
        """Verify disdantic list displays a rich visual tree of active registries."""
        pkg_name = "temp_e2e_tree_pkg"
        key_a = "key_tree_a"
        key_b = "key_tree_b"
        self._create_temp_package(tmp_path, pkg_name, key_a, key_b)

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{env.get('PYTHONPATH', '')}"
        env["DISDANTIC__AUTO_PACKAGES"] = f'["{pkg_name}"]'

        result = subprocess.run(
            [sys.executable, "-m", "disdantic", "list"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"CLI command failed: {result.stderr}"
        assert "└── RegistryA" in result.stdout
        assert "└── RegistryB" in result.stdout
        assert f'    └── "{key_a}" -> {pkg_name}.TargetA' in result.stdout
        assert f'    └── "{key_b}" -> {pkg_name}.TargetB' in result.stdout

    @pytest.mark.sanity
    def test_cli_json_view(self, tmp_path: Path) -> None:
        """Verify disdantic list --json outputs raw JSON string representation."""
        pkg_name = "temp_e2e_json_pkg"
        key_a = "key_json_a"
        key_b = "key_json_b"
        self._create_temp_package(tmp_path, pkg_name, key_a, key_b)

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{env.get('PYTHONPATH', '')}"
        env["DISDANTIC__AUTO_PACKAGES"] = f'["{pkg_name}"]'

        result = subprocess.run(
            [sys.executable, "-m", "disdantic", "list", "--json"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"CLI command failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "RegistryA" in data
        assert "RegistryB" in data
        assert data["RegistryA"] == {key_a: f"{pkg_name}.TargetA"}
        assert data["RegistryB"] == {key_b: f"{pkg_name}.TargetB"}

    @pytest.mark.regression
    def test_cli_invalid_config(self) -> None:
        """Verify CLI fails and returns non-zero code on invalid auto package config."""
        env = os.environ.copy()
        env["DISDANTIC__AUTO_PACKAGES"] = '["non_existent_package_12345"]'

        result = subprocess.run(
            [sys.executable, "-m", "disdantic", "list"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        assert "Error querying registries" in result.stderr
