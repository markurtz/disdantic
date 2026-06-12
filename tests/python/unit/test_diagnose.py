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

"""Unit tests for the diagnose module."""

from __future__ import annotations

import contextlib
import importlib
import pkgutil
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, Literal, cast
from unittest import mock

import pytest
from pydantic import BaseModel, ValidationError

import disdantic.diagnose
from disdantic.diagnose import (
    DiagnosticsReport,
    RegistryDiagnostics,
    RegistryModelInfo,
    verify_registries,
)
from disdantic.registry import PydanticClassRegistryMixin, RegistryMixin
from disdantic.settings import get_settings, reset_settings

if TYPE_CHECKING:

    class NonExistentType:
        pass


# Global tracking to isolate dynamic local classes defined inside test functions
# from leaking into subsequent unit tests.
_original_get_all_subclasses = disdantic.diagnose._get_all_subclasses
_active_registries: set[type] = set()


def _filtered_get_all_subclasses(cls: type) -> set[type]:
    all_subs = _original_get_all_subclasses(cls)
    filtered = set()
    for subclass in all_subs:
        if "<locals>" in subclass.__qualname__:
            if subclass in _active_registries:
                filtered.add(subclass)
        else:
            filtered.add(subclass)
    return filtered


# Globally patch the subclass utility in the target module
disdantic.diagnose._get_all_subclasses = cast("Any", _filtered_get_all_subclasses)


class TestRegistryModelInfo:
    """Test suite for RegistryModelInfo class."""

    @pytest.fixture(
        params=[
            {
                "key": "text",
                "class_name": "TextMessage",
                "module_path": "disdantic.examples",
                "compilation_status": "healthy",
                "error_detail": None,
            },
            {
                "key": "image",
                "class_name": "ImageMessage",
                "module_path": "disdantic.examples",
                "compilation_status": "error",
                "error_detail": "Failed to compile schema due to missing field type",
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> RegistryModelInfo:
        """Shared fixture supplying valid RegistryModelInfo instances."""
        return RegistryModelInfo(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate structural contracts: inheritance and public exposures."""
        assert issubclass(RegistryModelInfo, BaseModel)
        fields = RegistryModelInfo.model_fields
        assert "key" in fields
        assert "class_name" in fields
        assert "module_path" in fields
        assert "compilation_status" in fields
        assert "error_detail" in fields

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: RegistryModelInfo) -> None:
        """Verify initialization sets attributes correctly."""
        assert isinstance(valid_instances.key, str)
        assert isinstance(valid_instances.class_name, str)
        assert isinstance(valid_instances.module_path, str)
        assert valid_instances.compilation_status in ("healthy", "error")
        if valid_instances.compilation_status == "error":
            assert isinstance(valid_instances.error_detail, str)
        else:
            assert valid_instances.error_detail is None

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        with pytest.raises(ValidationError):
            RegistryModelInfo(
                key="text",
                class_name="TextMessage",
                module_path="disdantic.examples",
                compilation_status=cast("Any", 123),  # Invalid type
                error_detail=None,
            )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        with pytest.raises(ValidationError):
            RegistryModelInfo.model_validate(
                {
                    "class_name": "TextMessage",
                    "module_path": "disdantic.examples",
                    "compilation_status": "healthy",
                }
            )

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: RegistryModelInfo) -> None:
        """Verify model_dump and model_validate pipelines."""
        dumped_data = valid_instances.model_dump()
        validated_instance = RegistryModelInfo.model_validate(dumped_data)
        assert validated_instance == valid_instances


class TestRegistryDiagnostics:
    """Test suite for RegistryDiagnostics class."""

    @pytest.fixture(
        params=[
            {
                "registry_name": "MessageBase",
                "discriminator_key": "type",
                "auto_discovery_enabled": True,
                "models": [
                    RegistryModelInfo(
                        key="text",
                        class_name="TextMessage",
                        module_path="disdantic.examples",
                        compilation_status="healthy",
                        error_detail=None,
                    )
                ],
                "orphans": [],
            },
            {
                "registry_name": "SimpleRegistry",
                "discriminator_key": "N/A",
                "auto_discovery_enabled": False,
                "models": [],
                "orphans": ["disdantic.examples.OrphanChild"],
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> RegistryDiagnostics:
        """Shared fixture supplying valid RegistryDiagnostics instances."""
        return RegistryDiagnostics(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate structural contracts: inheritance and public exposures."""
        assert issubclass(RegistryDiagnostics, BaseModel)
        fields = RegistryDiagnostics.model_fields
        assert "registry_name" in fields
        assert "discriminator_key" in fields
        assert "auto_discovery_enabled" in fields
        assert "models" in fields
        assert "orphans" in fields

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: RegistryDiagnostics) -> None:
        """Verify initialization sets attributes correctly."""
        assert isinstance(valid_instances.registry_name, str)
        assert isinstance(valid_instances.discriminator_key, str)
        assert isinstance(valid_instances.auto_discovery_enabled, bool)
        assert isinstance(valid_instances.models, list)
        assert isinstance(valid_instances.orphans, list)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        with pytest.raises(ValidationError):
            RegistryDiagnostics(
                registry_name="MessageBase",
                discriminator_key="type",
                # invalid boolean value
                auto_discovery_enabled=cast("Any", "not-a-bool"),
                models=[],
                orphans=[],
            )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        with pytest.raises(ValidationError):
            RegistryDiagnostics.model_validate(
                {
                    "discriminator_key": "type",
                    "auto_discovery_enabled": True,
                }
            )

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: RegistryDiagnostics) -> None:
        """Verify model_dump and model_validate pipelines."""
        dumped_data = valid_instances.model_dump()
        validated_instance = RegistryDiagnostics.model_validate(dumped_data)
        assert validated_instance == valid_instances


class TestDiagnosticsReport:
    """Test suite for DiagnosticsReport class."""

    @pytest.fixture(
        params=[
            {
                "is_healthy": True,
                "scanned_packages": ["disdantic.examples"],
                "registries": [],
                "import_errors": [],
            },
            {
                "is_healthy": False,
                "scanned_packages": ["disdantic.examples", "broken_pkg"],
                "registries": [
                    RegistryDiagnostics(
                        registry_name="BrokenBase",
                        discriminator_key="type",
                        auto_discovery_enabled=True,
                        models=[],
                        orphans=[],
                    )
                ],
                "import_errors": ["Failed to import broken_pkg"],
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> DiagnosticsReport:
        """Shared fixture supplying valid DiagnosticsReport instances."""
        return DiagnosticsReport(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate structural contracts: inheritance and public exposures."""
        assert issubclass(DiagnosticsReport, BaseModel)
        fields = DiagnosticsReport.model_fields
        assert "is_healthy" in fields
        assert "scanned_packages" in fields
        assert "registries" in fields
        assert "import_errors" in fields

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: DiagnosticsReport) -> None:
        """Verify initialization sets attributes correctly."""
        assert isinstance(valid_instances.is_healthy, bool)
        assert isinstance(valid_instances.scanned_packages, list)
        assert isinstance(valid_instances.registries, list)
        assert isinstance(valid_instances.import_errors, list)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        with pytest.raises(ValidationError):
            DiagnosticsReport(
                is_healthy=cast("Any", "invalid-bool"),  # invalid boolean value
                scanned_packages=[],
                registries=[],
                import_errors=[],
            )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        with pytest.raises(ValidationError):
            DiagnosticsReport.model_validate(
                {
                    "scanned_packages": [],
                }
            )

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: DiagnosticsReport) -> None:
        """Verify model_dump and model_validate pipelines."""
        dumped_data = valid_instances.model_dump()
        validated_instance = DiagnosticsReport.model_validate(dumped_data)
        assert validated_instance == valid_instances


class TestVerifyRegistries:
    """Test suite for verifying verify_registries functionality."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.fixture(autouse=True)
    def clean_registries_fixture(self) -> Generator[None, None, None]:
        """Clears all subclass registries before and after each test."""
        _active_registries.clear()

        def clear_all() -> None:
            # We recursively find and clear all subclasses of RegistryMixin
            def clear_recursive(cls: type[RegistryMixin[Any]]) -> None:
                if (
                    cls is not RegistryMixin
                    and hasattr(cls, "registry")
                    and ("<locals>" in cls.__qualname__ or cls in _active_registries)
                ):
                    with contextlib.suppress(Exception):
                        cls.clear_registry()
                for subclass in cls.__subclasses__():
                    clear_recursive(subclass)

            clear_recursive(RegistryMixin)

        clear_all()
        yield
        clear_all()
        _active_registries.clear()

    @pytest.mark.smoke
    def test_invocation_empty(self) -> None:
        """Verify report structure with no user-defined registries."""
        report = verify_registries()
        assert report.is_healthy is True
        assert isinstance(report.scanned_packages, list)
        assert isinstance(report.registries, list)
        assert isinstance(report.import_errors, list)

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        "scenario",
        [
            "healthy",
            "orphans",
            "non_pydantic_registry",
            "auto_package_string",
            "auto_package_list",
            "auto_ignore_modules",
            "package_no_path",
            "walk_package_is_package",
            "orphan_ignored_name",
        ],
    )
    def test_invocation(
        self,
        scenario: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify registry verification under various healthy/happy configurations."""
        helper_name = f"_run_scenario_{scenario}"
        helper = getattr(self, helper_name)
        helper(monkeypatch)

    def _run_scenario_healthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class HealthyBase(PydanticClassRegistryMixin):
            model_type: str

        @HealthyBase.register("first")
        class FirstChild(HealthyBase):
            model_type: Literal["first"] = "first"
            value: int

        _active_registries.update([HealthyBase, FirstChild])

        report = verify_registries()
        assert report.is_healthy is True
        reg_diagnostics = next(
            (
                registry
                for registry in report.registries
                if registry.registry_name == "HealthyBase"
            ),
            None,
        )
        assert reg_diagnostics is not None
        assert reg_diagnostics.discriminator_key == "model_type"
        assert len(reg_diagnostics.models) == 1
        assert reg_diagnostics.models[0].key == "first"
        assert reg_diagnostics.models[0].class_name == "FirstChild"
        assert reg_diagnostics.models[0].compilation_status == "healthy"
        assert len(reg_diagnostics.orphans) == 0

    def _run_scenario_orphans(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class OrphanBase(PydanticClassRegistryMixin):
            model_type: str

        class UnregisteredChild(OrphanBase):
            model_type: Literal["unregistered"] = "unregistered"
            url: str

        _active_registries.update([OrphanBase, UnregisteredChild])

        report = verify_registries()
        assert report.is_healthy is True
        reg_diagnostics = next(
            (
                registry
                for registry in report.registries
                if registry.registry_name == "OrphanBase"
            ),
            None,
        )
        assert reg_diagnostics is not None
        assert len(reg_diagnostics.orphans) == 1
        assert "UnregisteredChild" in reg_diagnostics.orphans[0]

    def _run_scenario_non_pydantic_registry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class SimpleRegistry(RegistryMixin[Any]):
            pass

        @SimpleRegistry.register("simple_class")
        class SimpleChild:
            pass

        class NoModuleObject:
            @property
            def __module__(self) -> str:
                raise AttributeError("No module attribute exists")

        mock_obj = NoModuleObject()
        SimpleRegistry.registry["simple_instance"] = SimpleChild()
        SimpleRegistry.registry["no_module"] = mock_obj

        _active_registries.update([SimpleRegistry, SimpleChild])

        report = verify_registries()
        assert report.is_healthy is True
        reg_diagnostics = next(
            (
                registry
                for registry in report.registries
                if registry.registry_name == "SimpleRegistry"
            ),
            None,
        )
        assert reg_diagnostics is not None
        assert reg_diagnostics.discriminator_key == "N/A"
        assert len(reg_diagnostics.models) == 3
        names_found = {model.class_name for model in reg_diagnostics.models}
        assert "SimpleChild" in names_found
        assert "NoModuleObject" in names_found
        module_paths = {model.module_path for model in reg_diagnostics.models}
        assert "" in module_paths

    def _run_scenario_auto_package_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class StringPkgRegistry(RegistryMixin[Any]):
            auto_package = "single_pkg"

        _active_registries.add(StringPkgRegistry)
        scanned: list[str] = []

        def mock_scan(
            packages: list[str],
            ignore_set: set[str],
            errors_list: list[str],
        ) -> None:
            scanned.extend(packages)

        monkeypatch.setattr("disdantic.diagnose._scan_packages", mock_scan)

        report = verify_registries()
        assert "single_pkg" in scanned
        assert report.is_healthy is True

    def _run_scenario_auto_package_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class ListPkgRegistry(RegistryMixin[Any]):
            auto_package = ["pkg_one", "pkg_two"]

        _active_registries.add(ListPkgRegistry)
        scanned: list[str] = []

        def mock_scan(
            packages: list[str],
            ignore_set: set[str],
            errors_list: list[str],
        ) -> None:
            scanned.extend(packages)

        monkeypatch.setattr("disdantic.diagnose._scan_packages", mock_scan)

        report = verify_registries()
        assert "pkg_one" in scanned
        assert "pkg_two" in scanned
        assert report.is_healthy is True

    def _run_scenario_auto_ignore_modules(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = get_settings()
        settings.auto_ignore_modules = ["settings_ignored"]

        class IgnoreRegistry(RegistryMixin[Any]):
            auto_ignore_modules = ["registry_ignored"]

        _active_registries.add(IgnoreRegistry)
        ignored: set[str] = set()

        def mock_scan(
            packages: list[str],
            ignore_set: set[str],
            errors_list: list[str],
        ) -> None:
            ignored.update(ignore_set)

        monkeypatch.setattr("disdantic.diagnose._scan_packages", mock_scan)

        report = verify_registries()
        assert "settings_ignored" in ignored
        assert "registry_ignored" in ignored
        assert report.is_healthy is True

    def _run_scenario_package_no_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        settings.auto_packages = ["no_path_pkg"]
        mock_pkg = mock.Mock(spec=[])

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "no_path_pkg":
                return mock_pkg
            raise ImportError(f"Unexpected import request for {name}")

        monkeypatch.setattr(importlib, "import_module", mock_import)

        report = verify_registries()
        assert report.is_healthy is True
        assert len(report.import_errors) == 0

    def _run_scenario_walk_package_is_package(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = get_settings()
        settings.auto_packages = ["valid_root_pkg"]
        mock_pkg = mock.Mock()
        mock_pkg.__path__ = ["/mock/path"]
        mock_pkg.__name__ = "valid_root_pkg"

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "valid_root_pkg":
                return mock_pkg
            raise ImportError(f"Unexpected import request for {name}")

        def mock_walk(
            path: Any, prefix: str, onerror: Any = None
        ) -> Generator[tuple[Any, str, bool], None, None]:
            if onerror:
                onerror("simulated walk error")
            yield None, "valid_root_pkg.sub_pkg", True

        monkeypatch.setattr(importlib, "import_module", mock_import)
        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk)

        report = verify_registries()
        assert report.is_healthy is True
        assert len(report.import_errors) == 0

    def _run_scenario_orphan_ignored_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class IgnoredNameBase(RegistryMixin[Any]):
            pass

        class IgnoredSubclass(IgnoredNameBase):
            pass

        IgnoredSubclass.__name__ = "RegistryMixin"

        _active_registries.update([IgnoredNameBase, IgnoredSubclass])

        report = verify_registries()
        assert report.is_healthy is True
        reg_diagnostics = next(
            (
                registry
                for registry in report.registries
                if registry.registry_name == "IgnoredNameBase"
            ),
            None,
        )
        assert reg_diagnostics is not None
        assert len(reg_diagnostics.orphans) == 0

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        "scenario",
        [
            "import_root_error",
            "walk_package_error",
        ],
    )
    def test_sanity_invalid(
        self,
        scenario: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify sanity failure conditions for verify_registries."""
        helper_name = f"_run_sanity_{scenario}"
        helper = getattr(self, helper_name)
        helper(monkeypatch)

    def _run_sanity_import_root_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        settings.auto_packages = ["broken_root_pkg"]

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "broken_root_pkg":
                raise ImportError("Simulated package root import failure")
            raise ImportError(f"Unexpected import request for {name}")

        monkeypatch.setattr(importlib, "import_module", mock_import)

        report = verify_registries()
        assert report.is_healthy is False
        assert any(
            "Failed to import package root 'broken_root_pkg'" in err
            for err in report.import_errors
        )

    def _run_sanity_walk_package_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = get_settings()
        settings.auto_packages = ["valid_root_pkg"]
        mock_pkg = mock.Mock()
        mock_pkg.__path__ = ["/mock/path"]
        mock_pkg.__name__ = "valid_root_pkg"

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "valid_root_pkg":
                return mock_pkg
            raise ImportError(f"Unexpected import request for {name}")

        def mock_walk(path: Any, prefix: str, onerror: Any = None) -> Any:
            raise ValueError("Simulated walk packages error")

        monkeypatch.setattr(importlib, "import_module", mock_import)
        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk)

        report = verify_registries()
        assert report.is_healthy is False
        assert any(
            ("Error walking package 'valid_root_pkg': Simulated walk packages error")
            in err
            for err in report.import_errors
        )

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "scenario",
        [
            "import_submodule_error",
            "auto_populate_error",
            "base_type_rebuild_error",
            "child_class_compilation_error",
        ],
    )
    def test_regression_invalid(
        self,
        scenario: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify regression failure conditions for verify_registries."""
        helper_name = f"_run_regression_{scenario}"
        helper = getattr(self, helper_name)
        helper(monkeypatch)

    def _run_regression_import_submodule_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = get_settings()
        settings.auto_packages = ["valid_root_pkg"]
        mock_pkg = mock.Mock()
        mock_pkg.__path__ = ["/mock/path"]
        mock_pkg.__name__ = "valid_root_pkg"

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "valid_root_pkg":
                return mock_pkg
            if name == "valid_root_pkg.broken_sub":
                raise ImportError("Simulated submodule import failure")
            raise ImportError(f"Unexpected import request for {name}")

        def mock_walk(
            path: Any, prefix: str, onerror: Any = None
        ) -> Generator[tuple[Any, str, bool], None, None]:
            yield None, "valid_root_pkg.broken_sub", False

        monkeypatch.setattr(importlib, "import_module", mock_import)
        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk)

        report = verify_registries()
        assert report.is_healthy is False
        assert any(
            (
                "Failed to import module 'valid_root_pkg.broken_sub': "
                "Simulated submodule import failure"
            )
            in err
            for err in report.import_errors
        )

    def _run_regression_auto_populate_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class BrokenPopRegistry(RegistryMixin[Any]):
            auto_discovery_enabled = True
            registry_populated = False
            auto_package = "mock_pkg"

            @classmethod
            def is_auto_discovery_enabled(cls) -> bool:
                return True

            @classmethod
            def auto_populate_registry(cls) -> bool:
                raise ValueError("Simulated populate error")

        _active_registries.add(BrokenPopRegistry)
        settings = get_settings()
        settings.auto_packages = []

        def mock_scan(
            packages: list[str],
            ignore_set: set[str],
            errors_list: list[str],
        ) -> None:
            pass

        monkeypatch.setattr("disdantic.diagnose._scan_packages", mock_scan)

        report = verify_registries()
        assert report.is_healthy is False
        assert any(
            (
                "Auto-population failed for registry "
                "'BrokenPopRegistry': Simulated populate error"
            )
            in err
            for err in report.import_errors
        )

    def _run_regression_base_type_rebuild_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class RebuildErrorRegistry(PydanticClassRegistryMixin):
            model_type: str

            @classmethod
            def model_rebuild(cls, *args: Any, **kwargs: Any) -> Any:
                raise ValueError("Simulated model rebuild error")

        _active_registries.add(RebuildErrorRegistry)

        report = verify_registries()
        assert report.is_healthy is False

    def _run_regression_child_class_compilation_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class BrokenBase(PydanticClassRegistryMixin):
            model_type: str

        class BrokenChild(BrokenBase):
            model_type: Literal["broken"] = "broken"
            broken_field: NonExistentType  # type: ignore[name-defined] # noqa: F821

        BrokenBase.registry["broken"] = BrokenChild
        BrokenBase._lower_registry["broken"] = BrokenChild

        _active_registries.update([BrokenBase, BrokenChild])

        try:
            report = verify_registries()
            assert report.is_healthy is False

            reg_diagnostics = next(
                (
                    registry
                    for registry in report.registries
                    if registry.registry_name == "BrokenBase"
                ),
                None,
            )
            assert reg_diagnostics is not None
            assert len(reg_diagnostics.models) == 1
            assert reg_diagnostics.models[0].key == "broken"
            assert reg_diagnostics.models[0].compilation_status == "error"
            assert reg_diagnostics.models[0].error_detail is not None
            assert "NonExistentType" in reg_diagnostics.models[0].error_detail
        finally:
            BrokenBase.clear_registry()


@pytest.mark.smoke
def test_all_exports() -> None:
    """Verify public module exports of disdantic.diagnose."""
    assert hasattr(disdantic.diagnose, "__all__")
    expected = {
        "DiagnosticsReport",
        "RegistryDiagnostics",
        "RegistryModelInfo",
        "verify_registries",
    }
    assert set(disdantic.diagnose.__all__) == expected
    for name in expected:
        assert hasattr(disdantic.diagnose, name)
