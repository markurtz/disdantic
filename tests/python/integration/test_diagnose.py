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

"""Integration tests for the registry diagnostics orchestration."""

from __future__ import annotations

import importlib
import json
import pkgutil
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from unittest import mock

import pytest
from pydantic import BaseModel, ValidationError
from typer.testing import CliRunner

import disdantic.diagnose
from disdantic.__main__ import app
from disdantic.diagnose import (
    DiagnosticsReport,
    RegistryDiagnostics,
    RegistryModelInfo,
    verify_registries,
)
from disdantic.registry import PydanticClassRegistryMixin, RegistryMixin
from disdantic.settings import get_settings, reset_settings
from tests.python.integration.test_registry import (
    BaseIntegrationModel,
    ImageIntegrationModel,
    TextIntegrationModel,
)

if TYPE_CHECKING:

    class NonExistentType:
        """Type stub only visible to the type checker.

        Prevents unresolved reference errors.
        """


class UnregisteredIntegrationChild(BaseIntegrationModel):
    """A module-level subclass used to test orphan detection.

    Used specifically in integration tests.
    """

    msg_type: Literal["unregistered"] = "unregistered"
    url: str


@pytest.fixture(autouse=True)
def clean_registry_mixin(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Ensure BaseIntegrationModel is clean and correctly registered
    across all tests.
    """
    BaseIntegrationModel.clear_registry()
    BaseIntegrationModel.register_decorator(TextIntegrationModel, name="text")
    BaseIntegrationModel.register_decorator(ImageIntegrationModel, name="image")
    BaseIntegrationModel.register_decorator(
        UnregisteredIntegrationChild,
        name="unregistered",
    )

    original_get_subclasses = disdantic.diagnose._get_all_subclasses

    def safe_get_subclasses(cls: type) -> set[type]:
        subclasses = original_get_subclasses(cls)
        return {
            sub
            for sub in subclasses
            if sub.__name__
            in (
                "BaseIntegrationModel",
                "ConcreteIntegrationRegistry",
                "TextIntegrationModel",
                "ImageIntegrationModel",
                "UnregisteredIntegrationChild",
                "RegistryMixin",
                "PydanticClassRegistryMixin",
            )
        }

    monkeypatch.setattr(disdantic.diagnose, "_get_all_subclasses", safe_get_subclasses)

    yield
    BaseIntegrationModel.clear_registry()
    BaseIntegrationModel.register_decorator(TextIntegrationModel, name="text")
    BaseIntegrationModel.register_decorator(ImageIntegrationModel, name="image")


class TestCLIEntrypoint:
    """Integration test suite for the 'diagnose' CLI subcommand."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensures clean global settings state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.mark.smoke
    def test_diagnose_help(self) -> None:
        """Verify that diagnose help option prints correct guidance."""
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--help"])
        assert result.exit_code == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.stdout)
        assert "Scans all configured auto-discovery packages" in clean_stdout
        assert "--path" in clean_stdout
        assert "--json" in clean_stdout

    @pytest.mark.sanity
    def test_diagnose_default(self) -> None:
        """Verify standard run of diagnose command on the package."""
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose"])
        if result.exit_code != 0:
            print("CLI OUTPUT ON FAILURE:", result.stdout)
        assert result.exit_code == 0
        # Check that the rich success symbol and output table are printed
        assert "Registries diagnosis completed successfully" in result.stdout
        assert "Subclass Registries Summary" in result.stdout
        assert "Registries Detail" in result.stdout

    @pytest.mark.sanity
    def test_diagnose_json(self) -> None:
        """Verify diagnose JSON output matches correct schema format."""
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--json"])
        if result.exit_code != 0:
            print("CLI JSON OUTPUT ON FAILURE:", result.stdout)
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "is_healthy" in parsed
        assert "scanned_packages" in parsed
        assert "registries" in parsed
        assert "import_errors" in parsed
        assert parsed["is_healthy"] is True

    @pytest.mark.sanity
    def test_diagnose_custom_path(self, tmp_path: Path) -> None:
        """Verify diagnose correctly handles custom project root path."""
        # Create a dummy pyproject.toml in tmp_path
        toml_content = (
            "[tool.disdantic]\nauto_packages = ['non_existent_pkg_from_toml']\n"
        )
        (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        runner = CliRunner()
        # Diagnose with path pointing to the temp directory
        result = runner.invoke(app, ["diagnose", "--path", str(tmp_path), "--json"])
        # Should fail (exit non-zero) since the package
        # 'non_existent_pkg_from_toml' cannot be imported
        assert result.exit_code == 1
        parsed = json.loads(result.stdout)
        assert parsed["is_healthy"] is False
        assert "non_existent_pkg_from_toml" in parsed["scanned_packages"]
        assert len(parsed["import_errors"]) > 0
        assert any(
            "non_existent_pkg_from_toml" in err for err in parsed["import_errors"]
        )


class TestVerifyRegistries:
    """Integration test suite for verify_registries orchestrator."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        "scenario",
        ["empty", "healthy", "orphans"],
    )
    def test_invocation(self, scenario: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify verify_registries under different integration scenarios."""
        if scenario == "empty":
            monkeypatch.setattr(
                disdantic.diagnose,
                "_get_all_subclasses",
                lambda class_type: set(),
            )
            report = verify_registries()
            assert report.is_healthy is True
            assert len(report.registries) == 0

        elif scenario == "healthy":
            report = verify_registries()
            assert report.is_healthy is True

            reg_diagnostics = next(
                (
                    registry
                    for registry in report.registries
                    if registry.registry_name == "BaseIntegrationModel"
                ),
                None,
            )
            assert reg_diagnostics is not None
            assert reg_diagnostics.discriminator_key == "msg_type"
            assert len(reg_diagnostics.models) >= 3
            keys = {model.key for model in reg_diagnostics.models}
            assert "text" in keys
            assert "image" in keys
            assert "unregistered" in keys
            assert all(
                model.compilation_status == "healthy"
                for model in reg_diagnostics.models
            )
            assert len(reg_diagnostics.orphans) == 0

        elif scenario == "orphans":
            BaseIntegrationModel.registry.pop("unregistered", None)
            BaseIntegrationModel._lower_registry.pop("unregistered", None)

            report = verify_registries()
            assert report.is_healthy is True

            reg_diagnostics = next(
                (
                    registry
                    for registry in report.registries
                    if registry.registry_name == "BaseIntegrationModel"
                ),
                None,
            )
            assert reg_diagnostics is not None
            assert len(reg_diagnostics.orphans) >= 1
            assert any(
                "UnregisteredIntegrationChild" in orphan
                for orphan in reg_diagnostics.orphans
            )

    @pytest.mark.regression
    def test_invalid_compilation_error(self) -> None:
        """Verify behavior under compilation errors."""

        class BrokenIntegrationChild(BaseIntegrationModel):
            msg_type: Literal["broken"] = "broken"
            broken_field: NonExistentType  # type: ignore[name-defined] # noqa: F821

        BaseIntegrationModel.registry["broken"] = BrokenIntegrationChild
        BaseIntegrationModel._lower_registry["broken"] = BrokenIntegrationChild
        try:
            report = verify_registries()
            assert report.is_healthy is False

            reg_diagnostics = next(
                (
                    registry
                    for registry in report.registries
                    if registry.registry_name == "BaseIntegrationModel"
                ),
                None,
            )
            assert reg_diagnostics is not None
            broken_model = next(
                (model for model in reg_diagnostics.models if model.key == "broken"),
                None,
            )
            assert broken_model is not None
            assert broken_model.compilation_status == "error"
            assert broken_model.error_detail is not None
            assert "NonExistentType" in broken_model.error_detail
        finally:
            BaseIntegrationModel.registry.pop("broken", None)
            BaseIntegrationModel._lower_registry.pop("broken", None)

    @pytest.mark.regression
    def test_invalid_import_root_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify behavior under root import failures."""
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

    @pytest.mark.regression
    def test_invalid_walk_package_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify behavior under package walking failures."""
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
            "Error walking package 'valid_root_pkg'" in err
            for err in report.import_errors
        )

    @pytest.mark.regression
    def test_invalid_import_submodule_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify behavior under submodule import failures."""
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
            "Failed to import module 'valid_root_pkg.broken_sub'" in err
            for err in report.import_errors
        )

    @pytest.mark.regression
    def test_invalid_auto_populate_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify behavior under auto-population failures."""

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

        monkeypatch.setattr(
            disdantic.diagnose,
            "_get_all_subclasses",
            lambda class_type: {BrokenPopRegistry},
        )

        settings = get_settings()
        settings.auto_packages = []

        report = verify_registries()
        assert report.is_healthy is False
        assert any(
            "Auto-population failed for registry 'BrokenPopRegistry'" in err
            for err in report.import_errors
        )

    @pytest.mark.regression
    def test_invalid_base_rebuild_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify behavior under base model rebuild failures."""

        class RebuildErrorRegistry(PydanticClassRegistryMixin):
            model_type: str

            @classmethod
            def model_rebuild(cls, *args: Any, **kwargs: Any) -> Any:
                raise ValueError("Simulated model rebuild error")

        monkeypatch.setattr(
            disdantic.diagnose,
            "_get_all_subclasses",
            lambda class_type: {RebuildErrorRegistry},
        )

        report = verify_registries()
        assert report.is_healthy is False

    @pytest.mark.sanity
    def test_resolve_packages_auto_package_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that auto_package declared as a list is correctly
        resolved and scanned.
        """

        class ListPackageRegistry(RegistryMixin[Any]):
            auto_package = ["package_one", "package_two"]

        monkeypatch.setattr(
            disdantic.diagnose,
            "_get_all_subclasses",
            lambda class_type: {ListPackageRegistry},
        )

        settings = get_settings()
        settings.auto_packages = ["package_three"]

        imported_packages: list[str] = []

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            imported_packages.append(name)
            mock_pkg = mock.Mock()
            if hasattr(mock_pkg, "__path__"):
                delattr(mock_pkg, "__path__")
            return mock_pkg

        monkeypatch.setattr(importlib, "import_module", mock_import)

        report = verify_registries()
        assert report.is_healthy is True
        assert "package_one" in report.scanned_packages
        assert "package_two" in report.scanned_packages
        assert "package_three" in report.scanned_packages
        assert len(report.scanned_packages) == 3

    @pytest.mark.sanity
    def test_resolve_ignore_set_subclass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that auto_ignore_modules on subclass registries
        are correctly resolved.
        """

        class IgnoredModulesRegistry(RegistryMixin[Any]):
            auto_ignore_modules = {"test_pkg.ignored_subclass_module"}

        monkeypatch.setattr(
            disdantic.diagnose,
            "_get_all_subclasses",
            lambda class_type: {IgnoredModulesRegistry},
        )

        settings = get_settings()
        settings.auto_packages = ["test_pkg"]
        settings.auto_ignore_modules = ["test_pkg.settings_ignored_module"]

        mock_pkg = mock.Mock()
        mock_pkg.__path__ = ["/mock/path"]
        mock_pkg.__name__ = "test_pkg"

        imported_modules: list[str] = []

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "test_pkg":
                return mock_pkg
            imported_modules.append(name)
            return mock.Mock()

        def mock_walk(
            path: Any, prefix: str, onerror: Any = None
        ) -> Generator[tuple[Any, str, bool], None, None]:
            yield None, "test_pkg.settings_ignored_module", False
            yield None, "test_pkg.ignored_subclass_module", False
            yield None, "test_pkg.normal_module", False

        monkeypatch.setattr(importlib, "import_module", mock_import)
        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk)

        report = verify_registries()
        assert report.is_healthy is True
        assert "test_pkg.normal_module" in imported_modules
        assert "test_pkg.settings_ignored_module" not in imported_modules
        assert "test_pkg.ignored_subclass_module" not in imported_modules

    @pytest.mark.regression
    def test_scan_packages_non_package_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that scanning a module lacking __path__ is bypassed correctly."""
        settings = get_settings()
        settings.auto_packages = ["non_pkg_module"]

        mock_module = mock.Mock()
        if hasattr(mock_module, "__path__"):
            delattr(mock_module, "__path__")
        mock_module.__name__ = "non_pkg_module"

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "non_pkg_module":
                return mock_module
            raise ImportError(f"Unexpected import request for {name}")

        monkeypatch.setattr(importlib, "import_module", mock_import)

        report = verify_registries()
        assert report.is_healthy is True
        assert len(report.import_errors) == 0

    @pytest.mark.regression
    def test_scan_packages_walk_onerror_callback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that onerror callback in pkgutil.walk_packages is
        triggered and handled.
        """
        settings = get_settings()
        settings.auto_packages = ["trigger_onerror_pkg"]

        mock_pkg = mock.Mock()
        mock_pkg.__path__ = ["/mock/path"]
        mock_pkg.__name__ = "trigger_onerror_pkg"

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "trigger_onerror_pkg":
                return mock_pkg
            return mock.Mock()

        def mock_walk(
            path: Any, prefix: str, onerror: Any = None
        ) -> Generator[tuple[Any, str, bool], None, None]:
            if onerror is not None:
                onerror("simulated_submodule_name")
            yield None, "trigger_onerror_pkg.normal_mod", False

        monkeypatch.setattr(importlib, "import_module", mock_import)
        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk)

        report = verify_registries()
        assert report.is_healthy is True
        assert len(report.import_errors) == 0

    @pytest.mark.regression
    def test_scan_packages_skip_subpackages_and_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that subpackages (is_package=True) and ignored
        modules are not imported.
        """
        settings = get_settings()
        settings.auto_packages = ["mixed_pkg"]
        settings.auto_ignore_modules = ["mixed_pkg.ignored_mod"]

        mock_pkg = mock.Mock()
        mock_pkg.__path__ = ["/mock/path"]
        mock_pkg.__name__ = "mixed_pkg"

        imported_modules: list[str] = []

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "mixed_pkg":
                return mock_pkg
            imported_modules.append(name)
            return mock.Mock()

        def mock_walk(
            path: Any, prefix: str, onerror: Any = None
        ) -> Generator[tuple[Any, str, bool], None, None]:
            yield None, "mixed_pkg.subpkg", True
            yield None, "mixed_pkg.ignored_mod", False
            yield None, "mixed_pkg.normal_mod", False

        monkeypatch.setattr(importlib, "import_module", mock_import)
        monkeypatch.setattr(pkgutil, "walk_packages", mock_walk)

        report = verify_registries()
        assert report.is_healthy is True
        assert "mixed_pkg.normal_mod" in imported_modules
        assert "mixed_pkg.subpkg" not in imported_modules
        assert "mixed_pkg.ignored_mod" not in imported_modules

    @pytest.mark.regression
    def test_diagnose_registry_orphan_mixin_skipped(self) -> None:
        """Verify that subclasses named RegistryMixin or
        PydanticClassRegistryMixin are skipped from orphans.
        """

        class RegistryMixin(BaseIntegrationModel):
            msg_type: Literal["dummy_mixin"] = "dummy_mixin"

        report = verify_registries()
        assert report.is_healthy is True
        reg_diagnostics = next(
            (
                registry
                for registry in report.registries
                if registry.registry_name == "BaseIntegrationModel"
            ),
            None,
        )
        assert reg_diagnostics is not None
        assert not any(
            "dummy_mixin" in orphan or "RegistryMixin" in orphan
            for orphan in reg_diagnostics.orphans
        )


class TestRegistryModelInfo:
    """Integration test suite for RegistryModelInfo model."""

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
        ],
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> RegistryModelInfo:
        """Shared fixture supplying valid RegistryModelInfo instances."""
        return RegistryModelInfo(**request.param)

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
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
        """Verify model instances are successfully created."""
        assert isinstance(valid_instances, RegistryModelInfo)
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
    """Integration test suite for RegistryDiagnostics model."""

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
                    ),
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
        ],
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> RegistryDiagnostics:
        """Shared fixture supplying valid RegistryDiagnostics instances."""
        return RegistryDiagnostics(**request.param)

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
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
        """Verify model instances are successfully created."""
        assert isinstance(valid_instances, RegistryDiagnostics)
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
                auto_discovery_enabled=cast("Any", "not-a-bool"),  # Invalid type
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
    """Integration test suite for DiagnosticsReport model."""

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
                    ),
                ],
                "import_errors": ["Failed to import broken_pkg"],
            },
        ],
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> DiagnosticsReport:
        """Shared fixture supplying valid DiagnosticsReport instances."""
        return DiagnosticsReport(**request.param)

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate structural contracts: inheritance and public exposures."""
        assert issubclass(DiagnosticsReport, BaseModel)
        fields = DiagnosticsReport.model_fields
        assert "is_healthy" in fields
        assert "scanned_packages" in fields
        assert "registries" in fields
        assert "import_errors" in fields

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: DiagnosticsReport) -> None:
        """Verify model instances are successfully created."""
        assert isinstance(valid_instances, DiagnosticsReport)
        assert isinstance(valid_instances.is_healthy, bool)
        assert isinstance(valid_instances.scanned_packages, list)
        assert isinstance(valid_instances.registries, list)
        assert isinstance(valid_instances.import_errors, list)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        with pytest.raises(ValidationError):
            DiagnosticsReport(
                is_healthy=cast("Any", "invalid-bool"),  # Invalid type
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
