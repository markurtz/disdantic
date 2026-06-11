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

"""End-to-end tests for Registry Diagnostics Execution (US-7.1)."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.diagnose import (
    DiagnosticsReport,
    RegistryDiagnostics,
    RegistryModelInfo,
    _get_all_subclasses,
    verify_registries,
)
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import reset_settings


@pytest.fixture(autouse=True)
def isolate_diagnose_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter out other test registry classes from verify_registries discovery."""

    def filtered_subclasses(cls: type) -> set[type]:
        subs = _get_all_subclasses(cls)
        return {
            sub
            for sub in subs
            if not sub.__module__.startswith("tests.e2e.")
            or sub.__module__ == "tests.e2e.test_registry_diagnostics_execution"
        }

    monkeypatch.setattr("disdantic.diagnose._get_all_subclasses", filtered_subclasses)


class BaseE2EDiagnoseModel(PydanticClassRegistryMixin):
    """Base model class used to test PydanticClassRegistryMixin diagnostics."""

    schema_discriminator = "diag_type"
    diag_type: str


class TestRegistryDiagnosticsExecution:
    """End-to-end test suite for US-7.1: Registry Diagnostics Execution."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        BaseE2EDiagnoseModel.clear_registry()
        yield
        BaseE2EDiagnoseModel.clear_registry()
        reset_settings()

    @pytest.fixture(params=["healthy_info", "unhealthy_info"])
    def valid_instances(self, request: pytest.FixtureRequest) -> RegistryModelInfo:
        """Fixture supplying properly configured RegistryModelInfo instances."""
        if request.param == "healthy_info":
            return RegistryModelInfo(
                key="text",
                class_name="TextMessage",
                module_path="disdantic.examples",
                compilation_status="healthy",
                error_detail=None,
            )
        return RegistryModelInfo(
            key="broken",
            class_name="BrokenMessage",
            module_path="disdantic.examples",
            compilation_status="error",
            error_detail="Simulated compilation error details",
        )

    @pytest.mark.smoke
    def test_contract_and_environment(self) -> None:
        """Validate structural environment contracts and API presence."""
        assert inspect.isfunction(verify_registries)
        assert issubclass(RegistryModelInfo, BaseModel)
        assert issubclass(RegistryDiagnostics, BaseModel)
        assert issubclass(DiagnosticsReport, BaseModel)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: RegistryModelInfo) -> None:
        """Assert correct initial system wiring and startup state."""
        assert isinstance(valid_instances, RegistryModelInfo)
        assert valid_instances.key in ("text", "broken")
        assert valid_instances.compilation_status in ("healthy", "error")

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify explicit system blockages on invalid construction parameters."""
        with pytest.raises(ValidationError):
            RegistryModelInfo(
                key=[],  # list is invalid for str field  # type: ignore
                class_name="TextMessage",
                module_path="disdantic.examples",
                compilation_status="healthy",
            )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify system boundary defense lines when missing required parameters."""
        with pytest.raises(ValidationError):
            RegistryModelInfo(  # type: ignore
                key="text",
                class_name="TextMessage",
                # missing module_path and compilation_status
            )

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: RegistryModelInfo) -> None:
        """Verify model_dump and model_validate serialization boundaries."""
        dumped_data = valid_instances.model_dump()
        assert isinstance(dumped_data, dict)
        assert dumped_data["key"] == valid_instances.key

        validated_instance = RegistryModelInfo.model_validate(dumped_data)
        assert validated_instance.key == valid_instances.key
        assert (
            validated_instance.compilation_status == valid_instances.compilation_status
        )

    @pytest.mark.regression
    def test_dynamic_resolution(self) -> None:
        """Verify dynamic registry reporting and formatting output structure."""
        report = verify_registries()
        assert isinstance(report, DiagnosticsReport)
        assert hasattr(report, "is_healthy")
        assert hasattr(report, "registries")

    @pytest.mark.smoke
    def test_verify_registries_workflow(self) -> None:
        """Setup -> Execute -> Assert -> Teardown for verify_registries."""

        @BaseE2EDiagnoseModel.register("valid_key")
        class ValidDiagModel(BaseE2EDiagnoseModel):
            diag_type: str = "valid_key"
            content: str

        report = verify_registries()
        assert report.is_healthy is True
        assert any(
            registry.registry_name == "BaseE2EDiagnoseModel"
            for registry in report.registries
        )

    @pytest.mark.regression
    def test_verify_registries_with_orphans_workflow(self) -> None:
        """Setup -> Execute -> Assert -> Teardown for orphan detection."""

        class OrphanDiagModel(BaseE2EDiagnoseModel):
            diag_type: str = "orphan_key"
            content: str

        report = verify_registries()
        assert report.is_healthy is True

        target_registry = next(
            registry
            for registry in report.registries
            if registry.registry_name == "BaseE2EDiagnoseModel"
        )
        assert any("OrphanDiagModel" in orphan for orphan in target_registry.orphans)


class TestCLIEntrypoint:
    """E2E test suite for 'diagnose' CLI subcommand."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        BaseE2EDiagnoseModel.clear_registry()
        yield
        BaseE2EDiagnoseModel.clear_registry()
        reset_settings()

    @pytest.mark.smoke
    def test_cli_diagnose_help(self) -> None:
        """Verify that diagnose help prints configuration flags."""
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--help"])
        assert result.exit_code == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.stdout)
        assert "--path" in clean_stdout
        assert "--json" in clean_stdout

    @pytest.mark.smoke
    def test_cli_diagnose_default_workflow(self) -> None:
        """Verify standard run of diagnose command on the package."""

        @BaseE2EDiagnoseModel.register("text")
        class TextDiagModel(BaseE2EDiagnoseModel):
            diag_type: str = "text"
            text_content: str

        runner = CliRunner()
        result = runner.invoke(app, ["diagnose"])
        assert result.exit_code == 0
        assert "Registries diagnosis completed successfully" in result.stdout
        assert "Subclass Registries Summary" in result.stdout

    @pytest.mark.sanity
    def test_cli_diagnose_json_workflow(self) -> None:
        """Verify diagnose JSON output schema matches DiagnosticsReport."""

        @BaseE2EDiagnoseModel.register("text")
        class TextDiagModel(BaseE2EDiagnoseModel):
            diag_type: str = "text"
            text_content: str

        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--json"])
        assert result.exit_code == 0
        parsed_report = json.loads(result.stdout)
        assert parsed_report["is_healthy"] is True
        assert "registries" in parsed_report

    @pytest.mark.regression
    def test_cli_diagnose_custom_path_healthy(self, tmp_path: Path) -> None:
        """Verify executing diagnose with a custom healthy path layout."""
        project_dir = tmp_path / "healthy_project"
        project_dir.mkdir()
        toml_content = "[tool.disdantic]\nauto_packages = []\n"
        (project_dir / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--path", str(project_dir), "--json"])
        assert result.exit_code == 0
        parsed_report = json.loads(result.stdout)
        assert parsed_report["is_healthy"] is True

    @pytest.mark.regression
    def test_cli_diagnose_custom_path_unhealthy(self, tmp_path: Path) -> None:
        """Verify executing diagnose with a custom path pointing to unhealthy config."""
        project_dir = tmp_path / "unhealthy_project"
        project_dir.mkdir()
        toml_content = "[tool.disdantic]\nauto_packages = ['completely_missing_pkg']\n"
        (project_dir / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--path", str(project_dir), "--json"])
        assert result.exit_code == 1
        parsed_report = json.loads(result.stdout)
        assert parsed_report["is_healthy"] is False
        assert any(
            "completely_missing_pkg" in error_msg
            for error_msg in parsed_report["import_errors"]
        )
