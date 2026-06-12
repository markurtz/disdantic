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

"""End-to-End test suite for the recursive package auto-discovery and cache wiping."""

from __future__ import annotations

import inspect
import sys
from typing import Any, ClassVar

import pytest

from disdantic.exceptions import MissingPackagesError
from disdantic.importer import AutoImporterMixin
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import reset_settings
from tests.conftest import TemporaryPackageBuilder


class E2ETestRegistryOne(PydanticClassRegistryMixin, AutoImporterMixin):
    """Registry subclass one for E2E testing."""

    schema_discriminator: ClassVar[str] = "msg_type"
    msg_type: str


class E2ETestRegistryTwo(PydanticClassRegistryMixin, AutoImporterMixin):
    """Registry subclass two for E2E testing."""

    schema_discriminator: ClassVar[str] = "msg_type"
    msg_type: str


# Configure package settings for each registry
E2ETestRegistryOne.auto_package = "temp_e2e_pkg_one"
E2ETestRegistryOne.auto_ignore_modules = ["temp_e2e_pkg_one.sub_ignored"]

E2ETestRegistryTwo.auto_package = ["temp_e2e_pkg_two"]
E2ETestRegistryTwo.auto_ignore_modules = []


REGISTRY_CONFIGS: dict[type[PydanticClassRegistryMixin], dict[str, Any]] = {
    E2ETestRegistryOne: {
        "auto_package": "temp_e2e_pkg_one",
        "ignore_modules": ["temp_e2e_pkg_one.sub_ignored"],
    },
    E2ETestRegistryTwo: {
        "auto_package": ["temp_e2e_pkg_two"],
        "ignore_modules": [],
    },
}


class TestPackageImporter:
    """End-to-End test cases for package auto-importing and caching."""

    @pytest.fixture(
        params=[
            E2ETestRegistryOne,
            E2ETestRegistryTwo,
        ]
    )
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> type[PydanticClassRegistryMixin]:
        """Fixture providing parameterized configurations for importer testing."""
        return request.param

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structure and method contracts of AutoImporterMixin."""
        assert issubclass(AutoImporterMixin, object)
        assert hasattr(AutoImporterMixin, "auto_package")
        assert hasattr(AutoImporterMixin, "auto_ignore_modules")
        assert hasattr(AutoImporterMixin, "_auto_imported_modules")
        assert hasattr(AutoImporterMixin, "auto_import_package_modules")
        assert hasattr(AutoImporterMixin, "reset_importer_cache")

        # Verify classmethod routines
        assert inspect.isroutine(AutoImporterMixin.auto_import_package_modules)
        assert inspect.isroutine(AutoImporterMixin.reset_importer_cache)

    @pytest.mark.sanity
    def test_initialization(
        self,
        valid_instances: type[PydanticClassRegistryMixin],
    ) -> None:
        """Assert correct initialization, naming, and attribute properties."""
        registry_class = valid_instances
        config = REGISTRY_CONFIGS[registry_class]
        assert issubclass(registry_class, AutoImporterMixin)
        assert issubclass(registry_class, PydanticClassRegistryMixin)
        assert registry_class.auto_package == config["auto_package"]
        assert registry_class.auto_ignore_modules == config["ignore_modules"]

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass unexpected arguments to verify instantiation checks."""
        with pytest.raises(TypeError):
            AutoImporterMixin(invalid_field="unexpected_value")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify default instantiation succeeds with no arguments."""
        instance = AutoImporterMixin()
        assert isinstance(instance, AutoImporterMixin)

    @pytest.mark.smoke
    def test_auto_import_package_modules(
        self,
        valid_instances: type[PydanticClassRegistryMixin],
        temp_package_builder: TemporaryPackageBuilder,
    ) -> None:
        """Verify dynamic discovery, recursive walk, and subclass registration."""
        registry_class = valid_instances
        config = REGISTRY_CONFIGS[registry_class]
        auto_pkg = config["auto_package"]
        package_name = auto_pkg if isinstance(auto_pkg, str) else auto_pkg[0]
        ignore_modules = config["ignore_modules"]

        # Create modules dynamically
        # We use a nested package structure to verify recursive walk
        modules_data = {
            "models.details": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_package_importer "
                f"import {registry_class.__name__}\n\n"
                f"@{registry_class.__name__}.register('key_one')\n"
                f"class ModelOne({registry_class.__name__}):\n"
                "    msg_type: Literal['key_one'] = 'key_one'\n"
                "    content: str\n"
            ),
            "models.sub_two": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_package_importer "
                f"import {registry_class.__name__}\n\n"
                f"@{registry_class.__name__}.register('key_two')\n"
                f"class ModelTwo({registry_class.__name__}):\n"
                "    msg_type: Literal['key_two'] = 'key_two'\n"
                "    content: str\n"
            ),
        }

        # Add ignored module to test auto_ignore_modules filtering
        if ignore_modules:
            for ignored in ignore_modules:
                rel_ignored = ignored[len(package_name) + 1 :]
                modules_data[rel_ignored] = (
                    "from __future__ import annotations\n"
                    "from typing import Literal\n"
                    "from tests.e2e.test_package_importer "
                    f"import {registry_class.__name__}\n\n"
                    f"@{registry_class.__name__}.register('key_ignored')\n"
                    f"class ModelIgnored({registry_class.__name__}):\n"
                    "    msg_type: Literal['key_ignored'] = 'key_ignored'\n"
                    "    content: str\n"
                )

        temp_package_builder.create_package(package_name, modules_data)

        # Clear registry beforehand to ensure clean state
        registry_class.clear_registry()
        registry_class.reset_importer_cache()

        try:
            # Call auto importer
            registry_class.auto_import_package_modules()

            # Assert registration is successful
            assert registry_class.is_registered("key_one")
            assert registry_class.is_registered("key_two")

            if ignore_modules:
                assert not registry_class.is_registered("key_ignored")

            # Check that registered classes are imported and in sys.modules
            assert f"{package_name}.models.details" in sys.modules
            assert f"{package_name}.models.sub_two" in sys.modules

            imported_modules = registry_class._auto_imported_modules
            assert f"{package_name}.models.details" in imported_modules
            assert f"{package_name}.models.sub_two" in imported_modules

            if ignore_modules:
                for ignored in ignore_modules:
                    assert ignored not in imported_modules
        finally:
            registry_class.reset_importer_cache()
            registry_class.clear_registry()

    @pytest.mark.smoke
    def test_reset_importer_cache(
        self,
        valid_instances: type[PydanticClassRegistryMixin],
        temp_package_builder: TemporaryPackageBuilder,
    ) -> None:
        """Verify module cache wiping for testing isolation."""
        registry_class = valid_instances
        config = REGISTRY_CONFIGS[registry_class]
        auto_pkg = config["auto_package"]
        package_name = auto_pkg if isinstance(auto_pkg, str) else auto_pkg[0]

        modules_data = {
            "temp_sub": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_package_importer "
                f"import {registry_class.__name__}\n\n"
                f"@{registry_class.__name__}.register('key_temp')\n"
                f"class ModelTemp({registry_class.__name__}):\n"
                "    msg_type: Literal['key_temp'] = 'key_temp'\n"
                "    content: str\n"
            )
        }
        temp_package_builder.create_package(package_name, modules_data)

        registry_class.clear_registry()
        registry_class.reset_importer_cache()

        try:
            registry_class.auto_import_package_modules()
            target_module = f"{package_name}.temp_sub"
            assert target_module in sys.modules
            assert target_module in registry_class._auto_imported_modules

            # Run reset cache
            registry_class.reset_importer_cache()

            # Assert removed
            assert target_module not in sys.modules
            assert len(registry_class._auto_imported_modules) == 0
        finally:
            registry_class.reset_importer_cache()
            registry_class.clear_registry()

    @pytest.mark.sanity
    def test_missing_packages_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify MissingPackagesError when packages are not configured."""
        monkeypatch.delenv("DISDANTIC__AUTO_PACKAGES", raising=False)
        reset_settings()

        class AppRegistry(AutoImporterMixin):
            auto_package = None

        try:
            with pytest.raises(MissingPackagesError, match="must be configured"):
                AppRegistry.auto_import_package_modules()
        finally:
            reset_settings()

    @pytest.mark.sanity
    def test_import_error_unresolved_package(self) -> None:
        """Verify ImportError is raised when target package name cannot be resolved."""

        class UnresolvedRegistry(AutoImporterMixin):
            auto_package = "completely_non_existent_package_xyz"

        with pytest.raises(ImportError, match="could not be resolved"):
            UnresolvedRegistry.auto_import_package_modules()

    @pytest.mark.regression
    def test_non_package_module(self) -> None:
        """Verify that standard modules without __path__ are skipped gracefully."""

        class MathRegistry(AutoImporterMixin):
            auto_package = "math"

        try:
            MathRegistry.auto_import_package_modules()
            assert not MathRegistry._auto_imported_modules
        finally:
            MathRegistry.reset_importer_cache()

    @pytest.mark.regression
    def test_marshalling(
        self,
        valid_instances: type[PydanticClassRegistryMixin],
        temp_package_builder: TemporaryPackageBuilder,
    ) -> None:
        """Verify model_validate and model_dump boundaries for dynamic models."""
        registry_class = valid_instances
        config = REGISTRY_CONFIGS[registry_class]
        auto_pkg = config["auto_package"]
        package_name = auto_pkg if isinstance(auto_pkg, str) else auto_pkg[0]

        modules_data = {
            "models.details": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_package_importer "
                f"import {registry_class.__name__}\n\n"
                f"@{registry_class.__name__}.register('key_one')\n"
                f"class ModelOne({registry_class.__name__}):\n"
                "    msg_type: Literal['key_one'] = 'key_one'\n"
                "    content: str\n"
            ),
        }
        temp_package_builder.create_package(package_name, modules_data)

        registry_class.clear_registry()
        registry_class.reset_importer_cache()

        try:
            registry_class.auto_import_package_modules()

            # Test model validation from dictionary
            payload = {"msg_type": "key_one", "content": "E2E Content"}
            model_instance: Any = registry_class.model_validate(payload)
            assert model_instance.__class__.__name__ == "ModelOne"
            assert model_instance.content == "E2E Content"

            # Test model dump
            dumped = model_instance.model_dump()
            assert dumped == payload
        finally:
            registry_class.reset_importer_cache()
            registry_class.clear_registry()

    @pytest.mark.regression
    def test_registry_integration(
        self,
        valid_instances: type[PydanticClassRegistryMixin],
        temp_package_builder: TemporaryPackageBuilder,
    ) -> None:
        """Validate dynamic subclass resolution and key building."""
        registry_class = valid_instances
        config = REGISTRY_CONFIGS[registry_class]
        auto_pkg = config["auto_package"]
        package_name = auto_pkg if isinstance(auto_pkg, str) else auto_pkg[0]

        modules_data = {
            "models.details": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_package_importer "
                f"import {registry_class.__name__}\n\n"
                f"@{registry_class.__name__}.register('custom_factory_key')\n"
                f"class FactoryModel({registry_class.__name__}):\n"
                "    msg_type: Literal['custom_factory_key'] = 'custom_factory_key'\n"
                "    def process(self) -> str:\n"
                "        return 'factory_processing_success'\n"
            ),
        }
        temp_package_builder.create_package(package_name, modules_data)

        registry_class.clear_registry()
        registry_class.reset_importer_cache()

        try:
            registry_class.auto_import_package_modules()

            # Assert key is registered and subclass can be fetched and instantiated
            registered_class = registry_class.get_registered_object(
                "custom_factory_key"
            )
            assert registered_class is not None
            instance = registered_class(msg_type="custom_factory_key")
            assert hasattr(instance, "process")
            assert instance.process() == "factory_processing_success"
        finally:
            registry_class.reset_importer_cache()
            registry_class.clear_registry()
