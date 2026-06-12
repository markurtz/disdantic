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
import inspect
import pkgutil
import sys
from types import ModuleType
from typing import Any

import pytest

from disdantic.exceptions import MissingPackagesError
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

        assert inspect.isroutine(AutoImporterMixin.auto_import_package_modules)
        assert inspect.isroutine(AutoImporterMixin.reset_importer_cache)

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

    @pytest.mark.regression
    def test_auto_import_package_modules(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify successful package walking, settings integration,
        ignore rules, and cache additions.
        """

        # Scenario A: Walk discovery with class-level configuration
        class ImporterForWalk(AutoImporterMixin):
            auto_package = "my_package"
            auto_ignore_modules = ["my_package.ignored_sub"]

        ImporterForWalk.reset_importer_cache()

        root_package = ModuleType("my_package")
        root_package_path = ["/dummy/path"]
        root_package.__path__ = root_package_path

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

        def mock_import_module(module_name: str) -> ModuleType:
            imported_modules.append(module_name)
            if module_name == "my_package":
                return root_package
            return ModuleType(module_name)

        monkeypatch.setattr(importlib, "import_module", mock_import_module)

        def mock_walk(
            unused_path: Any, unused_prefix: str
        ) -> list[tuple[None, str, bool]]:
            return discovered_modules

        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk)

        # Invoke
        ImporterForWalk.auto_import_package_modules()

        # Assert / Verify
        assert "my_package.pkg_sub" not in ImporterForWalk._auto_imported_modules
        assert "my_package.ignored_sub" not in ImporterForWalk._auto_imported_modules
        assert "my_package.cached_sub" in ImporterForWalk._auto_imported_modules
        assert "my_package.sys_sub" in ImporterForWalk._auto_imported_modules
        assert "my_package.new_sub" in ImporterForWalk._auto_imported_modules

        assert "my_package" in imported_modules
        assert "my_package.new_sub" in imported_modules

        # Teardown
        ImporterForWalk.reset_importer_cache()

        # Scenario B: Settings integration (merging class-level
        # and settings configurations)
        class ImporterWithSettings(AutoImporterMixin):
            auto_package = ["pkg_a", "pkg_b"]
            auto_ignore_modules = ["pkg_a.sub_ignored"]

        settings = get_settings()
        monkeypatch.setattr(settings, "auto_packages", ["pkg_b", "pkg_c"])
        monkeypatch.setattr(settings, "auto_ignore_modules", ["pkg_b.sub_ignored"])

        imported_roots: list[str] = []

        def mock_import_root(module_name: str) -> ModuleType:
            imported_roots.append(module_name)
            mock_module = ModuleType(module_name)
            mock_module.__path__ = ["/dummy"]
            return mock_module

        monkeypatch.setattr(importlib, "import_module", mock_import_root)

        def mock_empty_walk(unused_path: Any, unused_prefix: str) -> list:
            return []

        monkeypatch.setattr(pkgutil, "walk_packages", mock_empty_walk)

        ImporterWithSettings.auto_import_package_modules()

        assert "pkg_a" in imported_roots
        assert "pkg_b" in imported_roots
        assert "pkg_c" in imported_roots

        # Verify walk with actual filtering
        discovered_subs = [
            (None, "pkg_a.sub_ignored", False),
            (None, "pkg_b.sub_ignored", False),
            (None, "pkg_a.sub_valid", False),
        ]

        ImporterWithSettings.reset_importer_cache()
        imported_subs: list[str] = []

        def mock_import_walk(module_name: str) -> ModuleType:
            if "." in module_name:
                imported_subs.append(module_name)
            mock_module = ModuleType(module_name)
            mock_module.__path__ = ["/dummy"]
            return mock_module

        monkeypatch.setattr(importlib, "import_module", mock_import_walk)

        def mock_sub_walk(
            unused_path: Any, unused_prefix: str
        ) -> list[tuple[None, str, bool]]:
            return discovered_subs

        monkeypatch.setattr(pkgutil, "walk_packages", mock_sub_walk)

        ImporterWithSettings.auto_import_package_modules()

        assert "pkg_a.sub_valid" in imported_subs
        assert "pkg_a.sub_ignored" not in imported_subs
        assert "pkg_b.sub_ignored" not in imported_subs

        # Teardown
        ImporterWithSettings.reset_importer_cache()

    @pytest.mark.sanity
    def test_auto_import_package_modules_invalid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify errors are raised when packages are missing or
        root packages are unresolvable.
        """

        # 1. No package configured at all (MissingPackagesError)
        class ImporterWithoutPackage(AutoImporterMixin):
            auto_package = None

        settings = get_settings()
        monkeypatch.setattr(settings, "auto_packages", [])

        with pytest.raises(MissingPackagesError) as exc_info:
            ImporterWithoutPackage.auto_import_package_modules()
        assert "auto_package" in str(exc_info.value)

        # 2. Missing root package cannot be resolved
        # (ImportError wrapping ModuleNotFoundError)
        class ImporterWithMissingPackage(AutoImporterMixin):
            auto_package = "non_existent_root_package"

        def mock_import_fail(module_name: str) -> ModuleType:
            raise ModuleNotFoundError(f"No module named '{module_name}'")

        monkeypatch.setattr(importlib, "import_module", mock_import_fail)

        with pytest.raises(ImportError) as exc_info:
            ImporterWithMissingPackage.auto_import_package_modules()
        assert "root 'non_existent_root_package' could not be resolved" in str(
            exc_info.value
        )

        # 3. Target is a module rather than a package (has no __path__ attribute)
        class ImporterWithSimpleModule(AutoImporterMixin):
            auto_package = "simple_module"

        mock_module = ModuleType("simple_module")
        if hasattr(mock_module, "__path__"):
            delattr(mock_module, "__path__")

        monkeypatch.setattr(importlib, "import_module", lambda module_name: mock_module)

        walk_called = False

        def mock_walk_fail(unused_path: Any, unused_prefix: str) -> list:
            nonlocal walk_called
            walk_called = True
            return []

        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk_fail)

        ImporterWithSimpleModule.auto_import_package_modules()
        assert not walk_called

    @pytest.mark.smoke
    def test_reset_importer_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify reset_importer_cache clears local cache and pops sys.modules."""

        # 1. Setup & Mock
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

        # 2. Invoke
        ImporterForReset.reset_importer_cache()

        # 3. Assert / Verify
        assert "my_package.module_one" not in sys.modules
        assert "my_package.module_two" not in sys.modules
        assert len(ImporterForReset._auto_imported_modules) == 0
