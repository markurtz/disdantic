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
from typing import Any

import pytest

import disdantic
from disdantic.diagnose import DiagnosticsReport, verify_registries
from disdantic.importer import AutoImporterMixin
from disdantic.registry import PydanticClassRegistryMixin, RegistryManager
from disdantic.settings import Settings, get_settings, reset_settings
from tests.conftest import TemporaryPackageBuilder


class E2EDiagnosticsRegistry(PydanticClassRegistryMixin):
    """Registry subclass for E2E diagnostics testing."""

    schema_discriminator = "model_type"
    model_type: str
    registry_auto_discovery = True


class TestRegistryDiagnostics:
    """E2E test suite for programmatic registry diagnostics capabilities."""

    @pytest.fixture(autouse=True)
    def clean_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        E2EDiagnosticsRegistry.clear_registry()

        # Monkeypatch _get_all_subclasses to isolate this test suite
        # from subclasses defined in other test files.
        original_get_subclasses = disdantic.diagnose._get_all_subclasses

        def safe_get_subclasses(cls: type) -> set[type]:
            subclasses = original_get_subclasses(cls)
            return {
                sub
                for sub in subclasses
                if sub.__module__ == "tests.e2e.test_cli_diagnose"
                or sub.__module__.startswith("temp_")
                or sub.__name__ in ("RegistryMixin", "PydanticClassRegistryMixin")
            }

        monkeypatch.setattr(
            disdantic.diagnose, "_get_all_subclasses", safe_get_subclasses
        )

        yield
        E2EDiagnosticsRegistry.clear_registry()
        reset_settings()

    @pytest.fixture(params=["healthy", "broken", "orphans"])
    def valid_instances(
        self,
        request: pytest.FixtureRequest,
        temp_package_builder: TemporaryPackageBuilder,
    ) -> dict[str, Any]:
        """Provides dynamic configuration details and constructs packages."""
        scenario = request.param
        pkg_name = f"temp_diagnose_pkg_{scenario}"

        if scenario == "healthy":
            modules = {
                "models": (
                    "from __future__ import annotations\n"
                    "from typing import Literal\n"
                    "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                    "@E2EDiagnosticsRegistry.register('healthy_msg')\n"
                    "class HealthyMessage(E2EDiagnosticsRegistry):\n"
                    "    model_type: Literal['healthy_msg'] = 'healthy_msg'\n"
                    "    text: str\n"
                )
            }
        elif scenario == "broken":
            modules = {
                "models": (
                    "from __future__ import annotations\n"
                    "from typing import Literal\n"
                    "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                    "@E2EDiagnosticsRegistry.register('broken_msg')\n"
                    "class BrokenMessage(E2EDiagnosticsRegistry):\n"
                    "    model_type: Literal['broken_msg'] = 'broken_msg'\n"
                    "    text: NonExistentType\n"
                )
            }
        else:  # orphans
            modules = {
                "models": (
                    "from __future__ import annotations\n"
                    "from typing import Literal\n"
                    "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                    "class OrphanMessage(E2EDiagnosticsRegistry):\n"
                    "    model_type: Literal['orphan_msg'] = 'orphan_msg'\n"
                    "    text: str\n"
                )
            }

        pkg_dir = temp_package_builder.create_package(pkg_name, modules)

        return {
            "scenario": scenario,
            "pkg_name": pkg_name,
            "pkg_dir": pkg_dir,
        }

    @pytest.mark.smoke
    def test_environment_contract(self) -> None:
        """Validate structural diagnostics API and setting contracts."""
        assert disdantic.__version__ is not None
        assert hasattr(disdantic.diagnose, "verify_registries")
        assert hasattr(disdantic.diagnose, "DiagnosticsReport")
        assert issubclass(E2EDiagnosticsRegistry, PydanticClassRegistryMixin)
        assert issubclass(E2EDiagnosticsRegistry, AutoImporterMixin)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: dict[str, Any]) -> None:
        """Verify proper initial wiring, settings config, and registry states."""
        pkg_name = valid_instances["pkg_name"]

        # Configure settings to scan the temp package
        settings = get_settings()
        settings.auto_packages = [pkg_name]

        # Assert the registry starts clean
        assert len(E2EDiagnosticsRegistry.registry) == 0
        assert not E2EDiagnosticsRegistry.registry_populated

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify verify_registries fails/reports errors on invalid settings."""
        # Using a package path that does not exist to verify failure behavior
        settings = Settings(auto_packages=["non_existent_package_12345"])
        report = verify_registries(settings=settings)

        assert report.is_healthy is False
        assert len(report.import_errors) > 0
        assert any(
            "non_existent_package_12345" in error for error in report.import_errors
        )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify behavior when auto_packages settings config is omitted/empty."""
        settings = Settings(auto_packages=[])
        report = verify_registries(settings=settings)

        # Should be healthy but find no packages or registries
        assert report.is_healthy is True
        assert len(report.scanned_packages) == 0

    @pytest.mark.smoke
    def test_programmatic_diagnose_healthy(
        self, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Execute programmatic diagnostics on a healthy package."""
        pkg_name = "temp_prog_healthy"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "@E2EDiagnosticsRegistry.register('ok_msg')\n"
                "class OkMessage(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['ok_msg'] = 'ok_msg'\n"
                "    text: str\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        settings = get_settings()
        settings.auto_packages = [pkg_name]

        report = verify_registries(settings=settings)
        assert report.is_healthy is True
        assert pkg_name in report.scanned_packages

        registry_diag = next(
            (
                registry
                for registry in report.registries
                if registry.registry_name == "E2EDiagnosticsRegistry"
            ),
            None,
        )
        assert registry_diag is not None
        assert registry_diag.auto_discovery_enabled is True
        assert registry_diag.discriminator_key == "model_type"
        assert len(registry_diag.models) == 1
        assert registry_diag.models[0].key == "ok_msg"
        assert registry_diag.models[0].compilation_status == "healthy"
        assert len(registry_diag.orphans) == 0

    @pytest.mark.sanity
    def test_programmatic_diagnose_unhealthy(
        self, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Verify compilation failures are correctly identified and
        report is unhealthy.
        """
        pkg_name = "temp_prog_unhealthy"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "@E2EDiagnosticsRegistry.register('broken_msg')\n"
                "class BrokenMessage(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['broken_msg'] = 'broken_msg'\n"
                "    text: NonExistentType\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        settings = get_settings()
        settings.auto_packages = [pkg_name]

        report = verify_registries(settings=settings)
        assert report.is_healthy is False
        assert len(report.import_errors) > 0
        assert any(pkg_name in error for error in report.import_errors)

    @pytest.mark.regression
    def test_programmatic_diagnose_orphans(
        self, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Verify orphan subclasses (unregistered) are detected."""
        pkg_name = "temp_prog_orphans"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "class OrphanMessage(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['orphan_msg'] = 'orphan_msg'\n"
                "    text: str\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        settings = get_settings()
        settings.auto_packages = [pkg_name]

        report = verify_registries(settings=settings)
        assert report.is_healthy is True

        registry_diag = next(
            (
                registry
                for registry in report.registries
                if registry.registry_name == "E2EDiagnosticsRegistry"
            ),
            None,
        )
        assert registry_diag is not None
        assert len(registry_diag.orphans) >= 1
        assert any("OrphanMessage" in orphan for orphan in registry_diag.orphans)

    @pytest.mark.regression
    def test_marshalling(self, temp_package_builder: TemporaryPackageBuilder) -> None:
        """Verify serialization and deserialization boundaries of DiagnosticsReport."""
        pkg_name = "temp_prog_marshalling"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "@E2EDiagnosticsRegistry.register('ok_msg_b')\n"
                "class OkMessageB(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['ok_msg_b'] = 'ok_msg_b'\n"
                "    text: str\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        settings = get_settings()
        settings.auto_packages = [pkg_name]

        report = verify_registries(settings=settings)

        # Dump to JSON
        json_data = report.model_dump_json()
        assert isinstance(json_data, str)

        # Validate back
        parsed_report = DiagnosticsReport.model_validate_json(json_data)
        assert parsed_report.is_healthy == report.is_healthy
        assert parsed_report.scanned_packages == report.scanned_packages

    @pytest.mark.regression
    def test_dynamic_registry_resolution(self) -> None:
        """Verify that dynamic flow registries listing contains our test registry."""
        registries = RegistryManager.list_registries()
        assert "E2EDiagnosticsRegistry" in registries


class TestCLIEntrypoint:
    """End-to-End test suite for the 'diagnose' CLI subcommand."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        E2EDiagnosticsRegistry.clear_registry()
        yield
        E2EDiagnosticsRegistry.clear_registry()
        reset_settings()

    @pytest.fixture(params=["simple", "json"])
    def valid_instances(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        """Provides configured CLI options and execution contexts."""
        if request.param == "simple":
            return {"args": [], "expected_format": "text"}
        return {"args": ["--json"], "expected_format": "json"}

    @pytest.mark.smoke
    def test_cli_diagnose_help(self) -> None:
        """Verify that diagnose help option prints correct guidance."""
        result = subprocess.run(
            [sys.executable, "-m", "disdantic", "diagnose", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "show this help message and exit" in result.stdout
        assert "--disdantic_.project_root" in result.stdout

    @pytest.mark.sanity
    def test_cli_diagnose_healthy(
        self, tmp_path: Path, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Verify standard run of diagnose command on a healthy package."""
        pkg_name = "temp_cli_healthy"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "@E2EDiagnosticsRegistry.register('cli_ok')\n"
                "class CliOkMessage(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['cli_ok'] = 'cli_ok'\n"
                "    content: str\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        # Write pyproject.toml in tmp_path
        toml_content = f'[tool.disdantic]\nauto_packages = ["{pkg_name}"]\n'
        (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        result = subprocess.run(
            [sys.executable, "-m", "disdantic", "diagnose", "--path", str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"CLI output on failure: {result.stderr}"
        assert "Registries diagnosis completed successfully" in result.stdout
        assert "Subclass Registries Summary" in result.stdout
        assert "Registries Detail" in result.stdout
        assert "E2EDiagnosticsRegistry" in result.stdout
        assert "cli_ok" in result.stdout

    @pytest.mark.smoke
    def test_cli_diagnose_json_healthy(
        self, tmp_path: Path, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Verify diagnose --json option outputs raw JSON on a healthy package."""
        pkg_name = "temp_cli_json_healthy"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "@E2EDiagnosticsRegistry.register('cli_json_ok')\n"
                "class CliJsonOkMessage(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['cli_json_ok'] = 'cli_json_ok'\n"
                "    content: str\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        # Write pyproject.toml in tmp_path
        toml_content = f'[tool.disdantic]\nauto_packages = ["{pkg_name}"]\n'
        (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "disdantic",
                "diagnose",
                "--path",
                str(tmp_path),
                "--json",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"CLI output on failure: {result.stderr}"
        parsed_data = json.loads(result.stdout)
        assert parsed_data["is_healthy"] is True
        assert pkg_name in parsed_data["scanned_packages"]
        registries = parsed_data["registries"]
        registry_info = next(
            (
                registry
                for registry in registries
                if registry["registry_name"] == "E2EDiagnosticsRegistry"
            ),
            None,
        )
        assert registry_info is not None
        assert any(model["key"] == "cli_json_ok" for model in registry_info["models"])

    @pytest.mark.sanity
    def test_cli_diagnose_unhealthy(
        self, tmp_path: Path, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Verify diagnose command fails and returns non-zero code on
        unhealthy packages.
        """
        pkg_name = "temp_cli_unhealthy"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "@E2EDiagnosticsRegistry.register('cli_broken')\n"
                "class CliBrokenMessage(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['cli_broken'] = 'cli_broken'\n"
                "    content: NonExistentType\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        # Write pyproject.toml in tmp_path
        toml_content = f'[tool.disdantic]\nauto_packages = ["{pkg_name}"]\n'
        (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        result = subprocess.run(
            [sys.executable, "-m", "disdantic", "diagnose", "--path", str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "Registries diagnosis failed" in result.stdout
        assert "Import Errors" in result.stdout
        assert "Failed to import module" in result.stdout

    @pytest.mark.regression
    def test_cli_diagnose_json_unhealthy(
        self, tmp_path: Path, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Verify diagnose --json option outputs failure JSON and returns code 1."""
        pkg_name = "temp_cli_json_unhealthy"
        modules = {
            "models": (
                "from __future__ import annotations\n"
                "from typing import Literal\n"
                "from tests.e2e.test_cli_diagnose import E2EDiagnosticsRegistry\n\n"
                "@E2EDiagnosticsRegistry.register('cli_json_broken')\n"
                "class CliJsonBrokenMessage(E2EDiagnosticsRegistry):\n"
                "    model_type: Literal['cli_json_broken'] = 'cli_json_broken'\n"
                "    content: NonExistentType\n"
            )
        }
        temp_package_builder.create_package(pkg_name, modules)

        # Write pyproject.toml in tmp_path
        toml_content = f'[tool.disdantic]\nauto_packages = ["{pkg_name}"]\n'
        (tmp_path / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "disdantic",
                "diagnose",
                "--path",
                str(tmp_path),
                "--json",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        parsed_data = json.loads(result.stdout)
        assert parsed_data["is_healthy"] is False
        assert len(parsed_data["import_errors"]) > 0
