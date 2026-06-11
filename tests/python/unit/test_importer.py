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

"""Unit tests for the importer module."""

from __future__ import annotations

import importlib
import pkgutil
import sys
from types import ModuleType
from typing import Any

import pytest

from disdantic.importer import AutoImporterMixin
from disdantic.settings import get_settings


class TestAutoImporterMixin:
    """Test suite for the AutoImporterMixin class."""

    @pytest.fixture(
        params=[
            {
                "auto_package": "disdantic",
                "auto_ignore_modules": ["disdantic.settings"],
            },
            {"auto_package": ["disdantic"], "auto_ignore_modules": None},
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

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the class signature and structural contracts."""
        assert issubclass(AutoImporterMixin, object)
        assert hasattr(AutoImporterMixin, "auto_package")
        assert hasattr(AutoImporterMixin, "auto_ignore_modules")
        assert hasattr(AutoImporterMixin, "_auto_imported_modules")
        assert hasattr(AutoImporterMixin, "auto_import_package_modules")
        assert hasattr(AutoImporterMixin, "reset_importer_cache")

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: AutoImporterMixin) -> None:
        """Verify that initialization maps states correctly."""
        assert isinstance(valid_instances, AutoImporterMixin)
        auto_package = valid_instances.auto_package
        assert auto_package is not None
        assert isinstance(auto_package, (str, list))

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass unexpected initialization arguments to verify TypeError."""
        with pytest.raises(TypeError):
            AutoImporterMixin(invalid_parameter="value")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify that default instantiation succeeds without arguments."""
        instance = AutoImporterMixin()
        assert isinstance(instance, AutoImporterMixin)

    @pytest.mark.sanity
    def test_auto_import_package_modules_no_package(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify ValueError is raised when no packages are configured."""

        class ImporterWithoutPackage(AutoImporterMixin):
            auto_package = None

        settings = get_settings()
        monkeypatch.setattr(settings, "auto_packages", [])

        with pytest.raises(ValueError) as exc_info:
            ImporterWithoutPackage.auto_import_package_modules()
        assert "auto_package" in str(exc_info.value)

    @pytest.mark.sanity
    def test_auto_import_package_modules_missing_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify ImportError is raised when root package cannot be resolved."""

        class ImporterWithMissingPackage(AutoImporterMixin):
            auto_package = "non_existent_root_package"

        def mock_import_module(name: str) -> ModuleType:
            raise ModuleNotFoundError(f"No module named '{name}'")

        monkeypatch.setattr(importlib, "import_module", mock_import_module)

        with pytest.raises(ImportError) as exc_info:
            ImporterWithMissingPackage.auto_import_package_modules()
        assert "root 'non_existent_root_package' could not be resolved" in str(
            exc_info.value
        )

    @pytest.mark.sanity
    def test_auto_import_package_modules_not_a_package(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify early exit when root package is a simple module with no __path__."""

        class ImporterWithSimpleModule(AutoImporterMixin):
            auto_package = "simple_module"

        mock_module = ModuleType("simple_module")
        if hasattr(mock_module, "__path__"):
            delattr(mock_module, "__path__")

        monkeypatch.setattr(importlib, "import_module", lambda name: mock_module)

        walk_called = False

        def mock_walk_packages(*args: Any, **kwargs: Any) -> list:
            nonlocal walk_called
            walk_called = True
            return []

        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk_packages)

        ImporterWithSimpleModule.auto_import_package_modules()
        assert not walk_called

    @pytest.mark.regression
    def test_auto_import_package_modules_walk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify import logic, ignore rules, and cache additions during traversal."""

        class ImporterForWalk(AutoImporterMixin):
            auto_package = "my_package"
            auto_ignore_modules = ["my_package.ignored_sub"]

        ImporterForWalk.reset_importer_cache()

        root_package = ModuleType("my_package")
        root_package.__path__ = ["/dummy/path"]  # type: ignore[attr-defined]

        discovered_modules = [
            (None, "my_package.pkg_sub", True),
            (None, "my_package.ignored_sub", False),
            (None, "my_package.cached_sub", False),
            (None, "my_package.sys_sub", False),
            (None, "my_package.new_sub", False),
        ]

        ImporterForWalk._auto_imported_modules.add("my_package.cached_sub")

        mock_sys_sub = ModuleType("my_package.sys_sub")
        monkeypatch.setitem(sys.modules, "my_package.sys_sub", mock_sys_sub)

        imported_modules: list[str] = []

        def mock_import_module(name: str) -> ModuleType:
            imported_modules.append(name)
            if name == "my_package":
                return root_package
            return ModuleType(name)

        monkeypatch.setattr(importlib, "import_module", mock_import_module)
        monkeypatch.setattr(
            pkgutil, "walk_packages", lambda path, prefix: discovered_modules
        )

        ImporterForWalk.auto_import_package_modules()

        assert "my_package.pkg_sub" not in ImporterForWalk._auto_imported_modules
        assert "my_package.ignored_sub" not in ImporterForWalk._auto_imported_modules
        assert "my_package.cached_sub" in ImporterForWalk._auto_imported_modules
        assert "my_package.sys_sub" in ImporterForWalk._auto_imported_modules
        assert "my_package.new_sub" in ImporterForWalk._auto_imported_modules

        assert imported_modules == ["my_package", "my_package.new_sub"]

    @pytest.mark.regression
    def test_auto_import_package_modules_settings_integration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify packages/ignores merge from class and global settings."""

        class ImporterWithSettings(AutoImporterMixin):
            auto_package = ["pkg_a", "pkg_b"]
            auto_ignore_modules = ["pkg_a.sub_ignored"]

        settings = get_settings()
        monkeypatch.setattr(settings, "auto_packages", ["pkg_b", "pkg_c"])
        monkeypatch.setattr(settings, "auto_ignore_modules", ["pkg_b.sub_ignored"])

        imported_roots: list[str] = []

        def mock_import_module(name: str) -> ModuleType:
            imported_roots.append(name)
            mock_module = ModuleType(name)
            mock_module.__path__ = ["/dummy"]  # type: ignore[attr-defined]
            return mock_module

        monkeypatch.setattr(importlib, "import_module", mock_import_module)
        monkeypatch.setattr(pkgutil, "walk_packages", lambda path, prefix: [])

        ImporterWithSettings.auto_import_package_modules()

        assert imported_roots == ["pkg_a", "pkg_b", "pkg_c"]

        discovered_modules = [
            (None, "pkg_a.sub_ignored", False),
            (None, "pkg_b.sub_ignored", False),
            (None, "pkg_a.sub_valid", False),
        ]

        ImporterWithSettings.reset_importer_cache()
        imported_subs: list[str] = []

        def mock_import_module_walk(name: str) -> ModuleType:
            if "." in name:
                imported_subs.append(name)
            mock_module = ModuleType(name)
            mock_module.__path__ = ["/dummy"]  # type: ignore[attr-defined]
            return mock_module

        monkeypatch.setattr(importlib, "import_module", mock_import_module_walk)
        monkeypatch.setattr(
            pkgutil, "walk_packages", lambda path, prefix: discovered_modules
        )

        ImporterWithSettings.auto_import_package_modules()

        assert "pkg_a.sub_valid" in imported_subs
        assert "pkg_a.sub_ignored" not in imported_subs
        assert "pkg_b.sub_ignored" not in imported_subs

    @pytest.mark.smoke
    def test_reset_importer_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify reset_importer_cache clears cache and sys.modules."""

        class ImporterForReset(AutoImporterMixin):
            pass

        ImporterForReset._auto_imported_modules.clear()
        ImporterForReset._auto_imported_modules.update(
            {
                "my_package.module_one",
                "my_package.module_two",
            }
        )

        mock_module_one = ModuleType("my_package.module_one")
        mock_module_two = ModuleType("my_package.module_two")
        monkeypatch.setitem(sys.modules, "my_package.module_one", mock_module_one)
        monkeypatch.setitem(sys.modules, "my_package.module_two", mock_module_two)

        ImporterForReset.reset_importer_cache()

        assert "my_package.module_one" not in sys.modules
        assert "my_package.module_two" not in sys.modules
        assert len(ImporterForReset._auto_imported_modules) == 0
