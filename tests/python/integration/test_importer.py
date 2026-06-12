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

"""Integration test suite for the AutoImporterMixin class."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

import disdantic.importer as importer_module
from disdantic.exceptions import MissingPackagesError
from disdantic.importer import AutoImporterMixin
from disdantic.registry import PydanticClassRegistryMixin, RegistryMixin
from disdantic.settings import reset_settings


class DummyTestRegistry(RegistryMixin[type]):
    """Test registry to verify dynamic class loading."""


class DummyPydanticRegistry(PydanticClassRegistryMixin):
    """Registry class for testing marshalling data across module boundaries."""

    schema_discriminator = "msg_type"
    msg_type: str


@pytest.mark.smoke
def test_module_exports() -> None:
    """Validate public module-level variables, constants, and exports."""
    assert hasattr(importer_module, "__all__")
    assert "AutoImporterMixin" in importer_module.__all__


class TestAutoImporterMixin:
    """Integration test suite for validating AutoImporterMixin."""

    @pytest.fixture(
        params=[
            {
                "auto_package": "temp_pkg_str",
                "auto_ignore_modules": ["temp_pkg_str.ignored"],
            },
            {
                "auto_package": ["temp_pkg_list"],
                "auto_ignore_modules": None,
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> AutoImporterMixin:
        """Fixture providing varied valid instances of AutoImporterMixin subclasses."""
        auto_package = request.param.get("auto_package")
        auto_ignore_modules = request.param.get("auto_ignore_modules")

        class DynamicImporter(AutoImporterMixin):
            pass

        DynamicImporter.auto_package = auto_package
        DynamicImporter.auto_ignore_modules = auto_ignore_modules

        return DynamicImporter()

    def _create_temporary_package(
        self,
        base_path: Path,
        package_name: str,
        modules: dict[str, str],
    ) -> None:
        """Helper to dynamically construct a real package with submodules on disk."""
        package_dir = base_path / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        for module_name, content in modules.items():
            sub_file = package_dir / f"{module_name}.py"
            sub_file.write_text(content, encoding="utf-8")

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify structural contracts and class signature of AutoImporterMixin."""
        assert issubclass(AutoImporterMixin, object)
        assert hasattr(AutoImporterMixin, "auto_package")
        assert hasattr(AutoImporterMixin, "auto_ignore_modules")
        assert hasattr(AutoImporterMixin, "_auto_imported_modules")
        assert hasattr(AutoImporterMixin, "auto_import_package_modules")
        assert hasattr(AutoImporterMixin, "reset_importer_cache")

        # Verify method signatures
        assert inspect.isroutine(AutoImporterMixin.auto_import_package_modules)
        assert inspect.isroutine(AutoImporterMixin.reset_importer_cache)

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: AutoImporterMixin) -> None:
        """Test component assembly and valid configurations initialization."""
        assert isinstance(valid_instances, AutoImporterMixin)
        auto_package = valid_instances.auto_package
        assert auto_package is not None
        assert isinstance(auto_package, (str, list))

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass unexpected arguments to verify standard subclass instantiation."""
        with pytest.raises(TypeError):
            AutoImporterMixin(invalid_field="unexpected_value")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify default instantiation succeeds with no arguments."""
        instance = AutoImporterMixin()
        assert isinstance(instance, AutoImporterMixin)

    @pytest.mark.smoke
    def test_auto_import_package_modules(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify dynamic discovery, file importing, and cache mechanics.

        Performs discovery on the filesystem and verifies state integrations.
        """
        package_name = "temp_pkg_traversal"
        modules = {
            "sub_one": (
                "from __future__ import annotations\n"
                "from tests.python.integration.test_importer import (\n"
                "    DummyTestRegistry,\n"
                ")\n\n"
                "@DummyTestRegistry.register('key_one')\n"
                "class ClassOne:\n"
                "    pass\n"
            ),
            "sub_two": (
                "from __future__ import annotations\n"
                "from tests.python.integration.test_importer import (\n"
                "    DummyTestRegistry,\n"
                ")\n\n"
                "@DummyTestRegistry.register('key_two')\n"
                "class ClassTwo:\n"
                "    pass\n"
            ),
            "sub_pre_imported": ("from __future__ import annotations\n"),
        }
        self._create_temporary_package(tmp_path, package_name, modules)

        # Prepend to sys.path so importlib can find it
        monkeypatch.syspath_prepend(str(tmp_path))

        # Setup class settings with a list to cover list parameter parsing
        class TempImporter(AutoImporterMixin):
            auto_package = [package_name]

        # Verify nothing is registered yet
        assert not DummyTestRegistry.is_registered("key_one")
        assert not DummyTestRegistry.is_registered("key_two")

        # Pre-populate sys.modules to cover sys.modules bypass (lines 112-114)
        mock_pre_imported = f"{package_name}.sub_pre_imported"
        sys.modules[mock_pre_imported] = sys.modules["sys"]

        try:
            # Run traversal
            TempImporter.auto_import_package_modules()

            # Assert dynamic registration happened
            assert DummyTestRegistry.is_registered("key_one")
            assert DummyTestRegistry.is_registered("key_two")

            # Verify cached modules tracking
            assert f"{package_name}.sub_one" in TempImporter._auto_imported_modules
            assert f"{package_name}.sub_two" in TempImporter._auto_imported_modules
            assert mock_pre_imported in TempImporter._auto_imported_modules

            # Run second time - should be a no-op and not raise errors
            TempImporter.auto_import_package_modules()
        finally:
            # Cleanup
            TempImporter.reset_importer_cache()
            DummyTestRegistry.clear_registry()
            sys.modules.pop(package_name, None)
            sys.modules.pop(f"{package_name}.sub_one", None)
            sys.modules.pop(f"{package_name}.sub_two", None)
            sys.modules.pop(mock_pre_imported, None)

    @pytest.mark.sanity
    def test_settings_integration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify AutoImporterMixin resolves auto packages and ignores.

        Ensures packages are loaded and ignored settings are merged from global.
        """
        package_name = "temp_pkg_settings"
        modules = {
            "sub_normal": (
                "from __future__ import annotations\n"
                "from tests.python.integration.test_importer import (\n"
                "    DummyTestRegistry,\n"
                ")\n\n"
                "@DummyTestRegistry.register('key_normal')\n"
                "class ClassNormal:\n"
                "    pass\n"
            ),
            "sub_ignored": (
                "from __future__ import annotations\n"
                "from tests.python.integration.test_importer import (\n"
                "    DummyTestRegistry,\n"
                ")\n\n"
                "@DummyTestRegistry.register('key_ignored')\n"
                "class ClassIgnored:\n"
                "    pass\n"
            ),
        }
        self._create_temporary_package(tmp_path, package_name, modules)
        monkeypatch.syspath_prepend(str(tmp_path))

        # Configure settings via environment variables
        monkeypatch.setenv("DISDANTIC__AUTO_PACKAGES", f'["{package_name}"]')
        monkeypatch.setenv(
            "DISDANTIC__AUTO_IGNORE_MODULES",
            f'["{package_name}.sub_ignored"]',
        )
        reset_settings()

        class SettingsImporter(AutoImporterMixin):
            # No class-level auto_package configured!
            pass

        try:
            # Trigger import
            SettingsImporter.auto_import_package_modules()

            # Assert normal was imported and registered
            assert DummyTestRegistry.is_registered("key_normal")
            # Assert ignored was NOT registered/imported
            assert not DummyTestRegistry.is_registered("key_ignored")

            assert (
                f"{package_name}.sub_normal" in SettingsImporter._auto_imported_modules
            )
            assert (
                f"{package_name}.sub_ignored"
                not in SettingsImporter._auto_imported_modules
            )
        finally:
            SettingsImporter.reset_importer_cache()
            DummyTestRegistry.clear_registry()
            reset_settings()
            sys.modules.pop(package_name, None)
            sys.modules.pop(f"{package_name}.sub_normal", None)
            sys.modules.pop(f"{package_name}.sub_ignored", None)

    @pytest.mark.sanity
    def test_missing_packages_error(self) -> None:
        """Verify that MissingPackagesError is raised when none is configured."""
        reset_settings()

        class NoPackageImporter(AutoImporterMixin):
            auto_package = None

        with pytest.raises(MissingPackagesError, match="must be configured"):
            NoPackageImporter.auto_import_package_modules()

    @pytest.mark.sanity
    def test_import_error_unresolved_package(self) -> None:
        """Verify that ImportError is raised when target package name is wrong."""

        class UnresolvedImporter(AutoImporterMixin):
            auto_package = "completely_non_existent_package_123"

        with pytest.raises(ImportError, match="could not be resolved"):
            UnresolvedImporter.auto_import_package_modules()

    @pytest.mark.regression
    def test_non_package_module(self) -> None:
        """Verify that standard modules without __path__ are skipped gracefully."""

        # Using a standard library module like "math" which has no __path__
        class MathImporter(AutoImporterMixin):
            auto_package = "math"

        # Should complete without error
        MathImporter.auto_import_package_modules()
        assert not MathImporter._auto_imported_modules

    @pytest.mark.regression
    def test_reset_importer_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify reset_importer_cache completely purges tracking caches.

        Ensures sys.modules is popped and tracking caches are wiped.
        """
        package_name = "temp_pkg_reset"
        modules = {
            "sub_reset": (
                "from __future__ import annotations\n"
                "from tests.python.integration.test_importer import (\n"
                "    DummyTestRegistry,\n"
                ")\n\n"
                "@DummyTestRegistry.register('key_reset')\n"
                "class ClassReset:\n"
                "    pass\n"
            ),
        }
        self._create_temporary_package(tmp_path, package_name, modules)
        monkeypatch.syspath_prepend(str(tmp_path))

        class ResetImporter(AutoImporterMixin):
            auto_package = package_name

        try:
            ResetImporter.auto_import_package_modules()

            # Assert imported
            assert f"{package_name}.sub_reset" in sys.modules
            assert f"{package_name}.sub_reset" in ResetImporter._auto_imported_modules

            # Reset cache
            ResetImporter.reset_importer_cache()

            # Assert popped
            assert f"{package_name}.sub_reset" not in sys.modules
            assert (
                f"{package_name}.sub_reset" not in ResetImporter._auto_imported_modules
            )
        finally:
            ResetImporter.reset_importer_cache()
            DummyTestRegistry.clear_registry()
            sys.modules.pop(package_name, None)
            sys.modules.pop(f"{package_name}.sub_reset", None)

    @pytest.mark.regression
    def test_marshalling(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify model validation and dump pipelines across boundaries.

        Verifies integration of Pydantic model serialization after walk import.
        """
        package_name = "temp_pkg_marshalling"
        modules = {
            "sub_models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.python.integration.test_importer import (\n"
                "    DummyPydanticRegistry,\n"
                ")\n\n"
                "@DummyPydanticRegistry.register('text_msg')\n"
                "class DynamicTextModel(DummyPydanticRegistry):\n"
                "    msg_type: Literal['text_msg'] = 'text_msg'\n"
                "    text_content: str\n"
            ),
        }
        self._create_temporary_package(tmp_path, package_name, modules)
        monkeypatch.syspath_prepend(str(tmp_path))

        class MarshallingImporter(AutoImporterMixin):
            auto_package = package_name

        try:
            # Traversal to load
            MarshallingImporter.auto_import_package_modules()

            # Test model validation pipeline
            payload = {"msg_type": "text_msg", "text_content": "hello integration"}
            validated_instance = DummyPydanticRegistry.model_validate(payload)
            assert validated_instance.__class__.__name__ == "DynamicTextModel"
            assert getattr(validated_instance, "text_content") == "hello integration"  # noqa: B009

            # Test model dump pipeline
            dumped_data = validated_instance.model_dump()
            assert dumped_data == payload
        finally:
            MarshallingImporter.reset_importer_cache()
            DummyPydanticRegistry.clear_registry()
            sys.modules.pop(package_name, None)
            sys.modules.pop(f"{package_name}.sub_models", None)

    @pytest.mark.regression
    def test_registry_integration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validate dynamic subclass resolution via registry patterns.

        Verifies factory construction and execution from dynamic imports.
        """
        package_name = "temp_pkg_factory"
        modules = {
            "sub_factory": (
                "from __future__ import annotations\n"
                "from tests.python.integration.test_importer import (\n"
                "    DummyTestRegistry,\n"
                ")\n\n"
                "@DummyTestRegistry.register('custom_factory_key')\n"
                "class FactoryComponent:\n"
                "    def execute(self) -> str:\n"
                "        return 'factory_success'\n"
            ),
        }
        self._create_temporary_package(tmp_path, package_name, modules)
        monkeypatch.syspath_prepend(str(tmp_path))

        class FactoryImporter(AutoImporterMixin):
            auto_package = package_name

        try:
            FactoryImporter.auto_import_package_modules()

            # Retrieve registered constructor/class from registry
            registered_class = DummyTestRegistry.get_registered_object(
                "custom_factory_key"
            )
            assert registered_class is not None
            instance = registered_class()
            assert instance.execute() == "factory_success"
        finally:
            FactoryImporter.reset_importer_cache()
            DummyTestRegistry.clear_registry()
            sys.modules.pop(package_name, None)
            sys.modules.pop(f"{package_name}.sub_factory", None)
