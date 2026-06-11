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

"""Integration tests for the main CLI entrypoint."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import typer
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from disdantic.__main__ import __all__, app, main
from disdantic.diagnose import DiagnosticsReport, RegistryDiagnostics, RegistryModelInfo
from disdantic.registry import RegistryManager
from disdantic.settings import reset_settings
from disdantic.version import __version__
from tests.python.integration.test_registry import (
    BaseIntegrationModel,
    ImageIntegrationModel,
    TextIntegrationModel,
)


@pytest.mark.smoke
def test_param_all() -> None:
    """Validate public module-level __all__ variable."""
    assert isinstance(__all__, list)
    assert __all__ == ["main"]


@pytest.mark.smoke
def test_param_app() -> None:
    """Validate public module-level app Typer instance."""
    assert isinstance(app, typer.Typer)


class TestMain:
    """Integration test suite for the main() function entrypoint."""

    @pytest.mark.smoke
    def test_invocation(self, mocker: MockerFixture) -> None:
        """Verify calling main() executes the Typer app correctly."""
        mock_app = mocker.patch("disdantic.__main__.app")
        main()
        mock_app.assert_called_once()


class TestCLIEntrypoint:
    """Integration test suite for the disdantic CLI interface."""

    @pytest.fixture(autouse=True)
    def clean_settings_and_registries(self) -> Any:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        BaseIntegrationModel.clear_registry()
        BaseIntegrationModel.register_decorator(TextIntegrationModel, name="text")
        BaseIntegrationModel.register_decorator(ImageIntegrationModel, name="image")
        yield
        BaseIntegrationModel.clear_registry()
        reset_settings()

    @pytest.mark.smoke
    def test_cli_callback_no_command(self) -> None:
        """Verify executing CLI without any command completes successfully."""
        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == 0

    @pytest.mark.smoke
    @pytest.mark.parametrize("version_flag", ["--version", "-v"])
    def test_cli_callback_version(self, version_flag: str) -> None:
        """Verify executing CLI with version options outputs correct info."""
        runner = CliRunner()
        result = runner.invoke(app, [version_flag])
        assert result.exit_code == 0
        assert f"disdantic v{__version__}" in result.stdout

    @pytest.mark.smoke
    @pytest.mark.parametrize("help_flag", ["--help", "-h"])
    def test_cli_callback_help(self, help_flag: str) -> None:
        """Verify executing CLI with help options outputs usage guidance."""
        runner = CliRunner()
        result = runner.invoke(app, [help_flag])
        assert result.exit_code == 0
        assert "Disdantic: A lightweight collection of utilities" in result.stdout

    @pytest.mark.sanity
    def test_cli_diagnose_help(self) -> None:
        """Verify diagnose subcommand display help guidance details."""
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--help"])
        assert result.exit_code == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.stdout)
        assert "--path" in clean_stdout
        assert "--json" in clean_stdout

    @pytest.mark.sanity
    def test_cli_diagnose_default_healthy(self) -> None:
        """Verify executing diagnose subcommand under healthy configuration."""
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose"])
        assert result.exit_code == 0
        assert "Registries diagnosis completed successfully" in result.stdout
        assert "Subclass Registries Summary" in result.stdout
        assert "BaseIntegrationModel" in result.stdout

    @pytest.mark.sanity
    def test_cli_diagnose_json_healthy(self) -> None:
        """Verify executing diagnose subcommand in JSON mode.

        Ensure it returns structured healthy reports.
        """
        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--json"])
        assert result.exit_code == 0
        report_data = json.loads(result.stdout)
        assert report_data["is_healthy"] is True
        assert any(
            registry["registry_name"] == "BaseIntegrationModel"
            for registry in report_data["registries"]
        )

    @pytest.mark.sanity
    def test_cli_diagnose_custom_path_healthy(self, tmp_path: Path) -> None:
        """Verify executing diagnose with custom healthy path layout."""
        # Create a dummy package to scan
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        toml_content = "[tool.disdantic]\nauto_packages = []\n"
        (project_dir / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--path", str(project_dir), "--json"])
        assert result.exit_code == 0
        report_data = json.loads(result.stdout)
        assert report_data["is_healthy"] is True

    @pytest.mark.regression
    def test_cli_diagnose_custom_path_unhealthy(self, tmp_path: Path) -> None:
        """Verify executing diagnose with custom path.

        Ensure it points to an unhealthy configuration.
        """
        # Create a dummy project root scanning a missing package
        project_dir = tmp_path / "broken_project"
        project_dir.mkdir()

        toml_content = (
            "[tool.disdantic]\nauto_packages = ['completely_missing_package']\n"
        )
        (project_dir / "pyproject.toml").write_text(toml_content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(app, ["diagnose", "--path", str(project_dir), "--json"])
        assert result.exit_code == 1
        report_data = json.loads(result.stdout)
        assert report_data["is_healthy"] is False
        assert any(
            "completely_missing_package" in error
            for error in report_data["import_errors"]
        )

    @pytest.mark.regression
    def test_cli_diagnose_unhealthy_report_exit_code(
        self, mocker: MockerFixture
    ) -> None:
        """Verify diagnose subcommand returns exit code 1.

        Ensure exit code is 1 when the registries report is unhealthy.
        """
        mock_report = DiagnosticsReport(
            is_healthy=False,
            scanned_packages=["mock_pkg"],
            registries=[
                RegistryDiagnostics(
                    registry_name="BrokenRegistry",
                    discriminator_key="type",
                    auto_discovery_enabled=True,
                    models=[
                        RegistryModelInfo(
                            key="broken",
                            class_name="BrokenModel",
                            module_path="mock_pkg.models",
                            compilation_status="error",
                            error_detail="Simulated validation error",
                        )
                    ],
                    orphans=["mock_pkg.models.OrphanModel"],
                )
            ],
            import_errors=["Simulated import failure"],
        )
        mocker.patch("disdantic.__main__.verify_registries", return_value=mock_report)

        runner = CliRunner()
        # Test standard Console output exit code
        result_console = runner.invoke(app, ["diagnose"])
        assert result_console.exit_code == 1
        assert "Registries diagnosis failed" in result_console.stdout
        assert "Simulated import failure" in result_console.stdout
        assert "Detail: Simulated validation error" in result_console.stdout
        assert "OrphanModel" in result_console.stdout

        # Test JSON mode exit code
        result_json = runner.invoke(app, ["diagnose", "--json"])
        assert result_json.exit_code == 1
        parsed_report = json.loads(result_json.stdout)
        assert parsed_report["is_healthy"] is False

    @pytest.mark.sanity
    def test_cli_schema_json_stdout(self) -> None:
        """Verify generating schema for a valid registry.

        Ensure it outputs JSON schema to stdout.
        """
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.python.integration.test_registry.BaseIntegrationModel"],
        )
        assert result.exit_code == 0
        schema_dict = json.loads(result.stdout)
        assert "$defs" in schema_dict
        assert "TextIntegrationModel" in schema_dict["$defs"]

    @pytest.mark.sanity
    def test_cli_schema_openapi_stdout(self) -> None:
        """Verify generating schema in OpenAPI format.

        Ensure it outputs components structure to stdout.
        """
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.python.integration.test_registry.BaseIntegrationModel",
                "--format",
                "openapi",
            ],
        )
        assert result.exit_code == 0
        schema_dict = json.loads(result.stdout)
        assert "components" in schema_dict
        assert "schemas" in schema_dict["components"]

    @pytest.mark.sanity
    def test_cli_schema_indent(self) -> None:
        """Verify schema output respects custom indentation level flag."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.python.integration.test_registry.BaseIntegrationModel",
                "--indent",
                "4",
            ],
        )
        assert result.exit_code == 0
        assert "\n    " in result.stdout

    @pytest.mark.sanity
    def test_cli_schema_file_output(self, tmp_path: Path) -> None:
        """Verify schema generation writes directly to output file.

        Ensure it writes to file when option is given.
        """
        output_file = tmp_path / "output_schema.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.python.integration.test_registry.BaseIntegrationModel",
                "-o",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        schema_dict = json.loads(output_file.read_text(encoding="utf-8"))
        assert "$defs" in schema_dict

    @pytest.mark.sanity
    def test_cli_schema_invalid_path(self) -> None:
        """Verify schema command exits with code 1.

        Ensure exit code is 1 for invalid non-dot path structures.
        """
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "BaseIntegrationModel"])
        assert result.exit_code == 1
        assert "Error: Invalid path" in result.stderr

    @pytest.mark.sanity
    def test_cli_schema_non_existent_module(self) -> None:
        """Verify schema command exits with code 1 when importing missing modules."""
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "completely_missing_module_name.Model"])
        assert result.exit_code == 1
        assert "Error: Could not import module" in result.stderr

    @pytest.mark.sanity
    def test_cli_schema_non_existent_attribute(self) -> None:
        """Verify schema command exits with code 1.

        Ensure exit code is 1 when the class does not exist in module.
        """
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.python.integration.test_registry.MissingRegistryModel"],
        )
        assert result.exit_code == 1
        assert "has no attribute" in result.stderr

    @pytest.mark.sanity
    def test_cli_schema_not_registry_class(self) -> None:
        """Verify schema command exits with code 1.

        Ensure exit code is 1 when target is not a registry subclass.
        """
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "disdantic.settings.Settings"])
        assert result.exit_code == 1
        assert "is not a subclass of PydanticClassRegistryMixin" in result.stderr

    @pytest.mark.regression
    def test_cli_schema_generation_failure(self, mocker: MockerFixture) -> None:
        """Verify schema command handles schema builder exceptions.

        Ensure it exits gracefully.
        """
        mocker.patch(
            "disdantic.__main__.get_registry_schema",
            side_effect=ValueError("Simulated generator failure"),
        )
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.python.integration.test_registry.BaseIntegrationModel"],
        )
        assert result.exit_code == 1
        assert "Error generating schema: Simulated generator failure" in result.stderr

    @pytest.mark.regression
    def test_cli_schema_write_failure(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Verify schema command handles write errors and exits with status 1."""
        output_file = tmp_path / "readonly_schema.json"

        # Mock Path.write_text to raise an OSError
        mocker.patch.object(
            Path,
            "write_text",
            side_effect=OSError("Simulated write permission error"),
        )

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.python.integration.test_registry.BaseIntegrationModel",
                "-o",
                str(output_file),
            ],
        )
        assert result.exit_code == 1
        assert "Error writing schema to" in result.stderr

    @pytest.mark.sanity
    def test_cli_list_default(self) -> None:
        """Verify list command successfully displays a structured registry tree."""
        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "BaseIntegrationModel (discriminator: msg_type)" in result.stdout
        expected_text = (
            '"text" -> tests.python.integration.test_registry.TextIntegrationModel'
        )
        assert expected_text in result.stdout

    @pytest.mark.sanity
    def test_cli_list_json(self) -> None:
        """Verify list command in JSON mode prints valid dictionary mappings."""
        runner = CliRunner()
        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        list_dict = json.loads(result.stdout)
        assert "BaseIntegrationModel" in list_dict
        assert list_dict["BaseIntegrationModel"] == {
            "text": "tests.python.integration.test_registry.TextIntegrationModel",
            "image": "tests.python.integration.test_registry.ImageIntegrationModel",
        }

    @pytest.mark.regression
    def test_cli_list_query_error(self, mocker: MockerFixture) -> None:
        """Verify list command prints errors.

        Ensure it exits with status 1 on querying failures.
        """
        mocker.patch.object(
            RegistryManager,
            "list_registries",
            side_effect=RuntimeError("Simulated database failure"),
        )
        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        assert "Error querying registries: Simulated database failure" in result.stderr
