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

"""Unit tests for the disdantic CLI entrypoint module."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest import mock

import pytest
import typer
from pytest_mock import MockerFixture

from disdantic.__main__ import (
    __all__,
    app,
    diagnose,
    list_cmd,
    main,
    main_callback,
    schema,
)
from disdantic.diagnose import DiagnosticsReport, RegistryDiagnostics, RegistryModelInfo
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.version import __version__


class TestMain:
    """Test suite for the main function."""

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the signature of main function."""
        assert callable(main)
        parameters = inspect.signature(main).parameters
        assert len(parameters) == 0

    @pytest.mark.smoke
    def test_invocation(self, mocker: MockerFixture) -> None:
        """Verify main function executes the typer app."""
        app_mock = mocker.patch("disdantic.__main__.app")
        main()
        app_mock.assert_called_once()


class TestMainCallback:
    """Test suite for the main_callback function."""

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the signature and types of main_callback function."""
        assert callable(main_callback)
        parameters = inspect.signature(main_callback).parameters
        assert "ctx" in parameters
        assert "version" in parameters

    @pytest.mark.smoke
    def test_invocation_version(self, mocker: MockerFixture) -> None:
        """Verify that passing version=True echoes version and exits."""
        echo_mock = mocker.patch("typer.echo")
        context_mock = mocker.MagicMock()

        with pytest.raises(typer.Exit) as exit_info:
            main_callback(ctx=context_mock, version=True)

        echo_mock.assert_called_once_with(f"disdantic v{__version__}")
        assert exit_info.value.exit_code == 0

    @pytest.mark.smoke
    def test_invocation_no_version(self, mocker: MockerFixture) -> None:
        """Verify that passing version=False configures logger and settings."""
        config_logger_mock = mocker.patch("disdantic.__main__.configure_logger")
        settings_mock = mocker.patch("disdantic.__main__.Settings")
        logger_mock = mocker.patch("disdantic.__main__.logger")
        context_mock = mocker.MagicMock()
        context_mock.invoked_subcommand = None

        main_callback(ctx=context_mock, version=False)

        config_logger_mock.assert_called_once()
        settings_mock.assert_called_once()
        logger_mock.info.assert_called()


class TestDiagnose:
    """Test suite for the diagnose command."""

    @pytest.fixture
    def mock_diagnose_deps(self, mocker: MockerFixture) -> dict[str, mock.MagicMock]:
        """Fixture to mock external dependencies of diagnose."""
        return {
            "reset_settings": mocker.patch("disdantic.__main__.reset_settings"),
            "verify_registries": mocker.patch("disdantic.__main__.verify_registries"),
            "Console": mocker.patch("disdantic.__main__.Console"),
            "_render_diagnose_table": mocker.patch(
                "disdantic.__main__._render_diagnose_table"
            ),
            "_render_diagnose_tree": mocker.patch(
                "disdantic.__main__._render_diagnose_tree"
            ),
            "typer_echo": mocker.patch("typer.echo"),
        }

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the signature and types of diagnose function."""
        assert callable(diagnose)
        parameters = inspect.signature(diagnose).parameters
        assert "path" in parameters
        assert "json_output" in parameters

    @pytest.mark.smoke
    def test_invocation_healthy(
        self, mock_diagnose_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify diagnose invocation on a healthy report."""
        report_mock = mock.MagicMock()
        report_mock.is_healthy = True
        report_mock.import_errors = []
        mock_diagnose_deps["verify_registries"].return_value = report_mock

        diagnose(path=None, json_output=False)

        mock_diagnose_deps["verify_registries"].assert_called_once()
        mock_diagnose_deps["reset_settings"].assert_not_called()
        mock_diagnose_deps["_render_diagnose_table"].assert_called_once_with(
            report_mock, mock.ANY
        )
        mock_diagnose_deps["_render_diagnose_tree"].assert_called_once_with(
            report_mock, mock.ANY
        )

    @pytest.mark.sanity
    def test_invocation_json_healthy(
        self, mock_diagnose_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify diagnose invocation with JSON output on healthy report."""
        report_mock = mock.MagicMock()
        report_mock.is_healthy = True
        report_mock.model_dump_json.return_value = '{"is_healthy": true}'
        mock_diagnose_deps["verify_registries"].return_value = report_mock

        diagnose(path=None, json_output=True)

        mock_diagnose_deps["typer_echo"].assert_called_once_with('{"is_healthy": true}')
        mock_diagnose_deps["_render_diagnose_table"].assert_not_called()

    @pytest.mark.regression
    def test_invocation_json_unhealthy(
        self, mock_diagnose_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify diagnose invocation with JSON output on unhealthy report.

        Ensure it raises typer.Exit.
        """
        report_mock = mock.MagicMock()
        report_mock.is_healthy = False
        report_mock.model_dump_json.return_value = '{"is_healthy": false}'
        mock_diagnose_deps["verify_registries"].return_value = report_mock

        with pytest.raises(typer.Exit) as exit_info:
            diagnose(path=None, json_output=True)

        assert exit_info.value.exit_code == 1
        mock_diagnose_deps["typer_echo"].assert_called_once_with(
            '{"is_healthy": false}'
        )

    @pytest.mark.regression
    def test_invocation_unhealthy_with_errors(
        self, mock_diagnose_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify diagnose prints errors and raises Exit on unhealthy report."""
        report_mock = mock.MagicMock()
        report_mock.is_healthy = False
        report_mock.import_errors = ["Failed to import module_name"]
        mock_diagnose_deps["verify_registries"].return_value = report_mock

        with pytest.raises(typer.Exit) as exit_info:
            diagnose(path=None, json_output=False)

        assert exit_info.value.exit_code == 1
        mock_diagnose_deps["_render_diagnose_table"].assert_called_once_with(
            report_mock, mock.ANY
        )
        mock_diagnose_deps["_render_diagnose_tree"].assert_called_once_with(
            report_mock, mock.ANY
        )

    @pytest.mark.sanity
    def test_invocation_custom_path(
        self, mock_diagnose_deps: dict[str, mock.MagicMock], mocker: MockerFixture
    ) -> None:
        """Verify diagnose overrides project root when path provided.

        It should reset settings and instantiate Settings with the path.
        """
        report_mock = mock.MagicMock()
        report_mock.is_healthy = True
        report_mock.import_errors = []
        mock_diagnose_deps["verify_registries"].return_value = report_mock
        settings_init_mock = mocker.patch("disdantic.__main__.Settings")

        diagnose(path="/my/project/path", json_output=False)

        mock_diagnose_deps["reset_settings"].assert_called_once()
        settings_init_mock.assert_called_once_with(
            project_root=Path("/my/project/path")
        )

    @pytest.mark.sanity
    def test_invalid_unexpected_exception(
        self, mock_diagnose_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify that unexpected exceptions in verify_registries propagate."""
        mock_diagnose_deps["verify_registries"].side_effect = ValueError(
            "Unexpected verify error"
        )

        with pytest.raises(ValueError, match="Unexpected verify error"):
            diagnose(path=None, json_output=False)

    @pytest.mark.sanity
    def test_invocation_healthy_rendering(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that diagnose actually renders the table and tree when healthy."""
        report = DiagnosticsReport(
            is_healthy=True,
            scanned_packages=["my_pkg"],
            registries=[
                RegistryDiagnostics(
                    registry_name="MyRegistry",
                    discriminator_key="type",
                    auto_discovery_enabled=True,
                    models=[
                        RegistryModelInfo(
                            key="text",
                            class_name="TextMessage",
                            module_path="my_pkg.models",
                            compilation_status="healthy",
                            error_detail=None,
                        )
                    ],
                    orphans=["my_pkg.models.OrphanMessage"],
                ),
                RegistryDiagnostics(
                    registry_name="EmptyRegistry",
                    discriminator_key="",
                    auto_discovery_enabled=False,
                    models=[],
                    orphans=[],
                ),
            ],
            import_errors=[],
        )

        mocker.patch("disdantic.__main__.verify_registries", return_value=report)
        mocker.patch("disdantic.__main__.reset_settings")

        diagnose(path=None, json_output=False)

        captured = capsys.readouterr()
        assert "Registries diagnosis completed successfully" in captured.out
        assert "Subclass Registries Summary" in captured.out
        assert "MyRegistry" in captured.out
        assert "type" in captured.out
        assert "TextMessage" in captured.out
        assert "OrphanMessage" in captured.out
        assert "EmptyRegistry" in captured.out
        assert "No models registered" in captured.out

    @pytest.mark.regression
    def test_invocation_unhealthy_rendering(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that diagnose renders details when unhealthy.

        It should print the table, tree, and import errors.
        """
        report = DiagnosticsReport(
            is_healthy=False,
            scanned_packages=["my_pkg"],
            registries=[
                RegistryDiagnostics(
                    registry_name="MyRegistry",
                    discriminator_key="type",
                    auto_discovery_enabled=True,
                    models=[
                        RegistryModelInfo(
                            key="text",
                            class_name="TextMessage",
                            module_path="my_pkg.models",
                            compilation_status="error",
                            error_detail="Invalid field definition",
                        )
                    ],
                    orphans=[],
                )
            ],
            import_errors=["Failed to import my_pkg.broken_module"],
        )

        mocker.patch("disdantic.__main__.verify_registries", return_value=report)
        mocker.patch("disdantic.__main__.reset_settings")

        with pytest.raises(typer.Exit) as exit_info:
            diagnose(path=None, json_output=False)

        assert exit_info.value.exit_code == 1

        captured = capsys.readouterr()
        assert "Registries diagnosis failed" in captured.out
        assert "Import Errors:" in captured.out
        assert "Failed to import my_pkg.broken_module" in captured.out
        assert "Detail: Invalid field definition" in captured.out


class TestSchema:
    """Test suite for the schema command."""

    @pytest.fixture
    def mock_schema_deps(self, mocker: MockerFixture) -> dict[str, mock.MagicMock]:
        """Fixture to mock external dependencies of schema."""
        return {
            "importlib": mocker.patch("disdantic.__main__.importlib"),
            "get_registry_schema": mocker.patch(
                "disdantic.__main__.get_registry_schema"
            ),
            "typer_echo": mocker.patch("typer.echo"),
        }

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the signature and types of schema function."""
        assert callable(schema)
        parameters = inspect.signature(schema).parameters
        assert "registry_path" in parameters
        assert "output" in parameters
        assert "schema_format" in parameters
        assert "indent" in parameters

    @pytest.mark.smoke
    def test_invocation_stdout(
        self, mock_schema_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify schema generation to stdout with default format."""
        mock_module = mock.MagicMock()

        class DummyRegistry(PydanticClassRegistryMixin):
            model_type: str

        mock_module.DummyRegistry = DummyRegistry
        mock_schema_deps["importlib"].import_module.return_value = mock_module
        mock_schema_deps["get_registry_schema"].return_value = {
            "schema_key": "schema_value"
        }

        schema(
            registry_path="mock_module.DummyRegistry",
            output=None,
            schema_format="json",
            indent=2,
        )

        mock_schema_deps["importlib"].import_module.assert_called_once_with(
            "mock_module"
        )
        mock_schema_deps["get_registry_schema"].assert_called_once_with(
            DummyRegistry, format="json"
        )
        mock_schema_deps["typer_echo"].assert_called_once_with(
            '{\n  "schema_key": "schema_value"\n}'
        )

    @pytest.mark.sanity
    def test_invocation_output_file(
        self, mock_schema_deps: dict[str, mock.MagicMock], mocker: MockerFixture
    ) -> None:
        """Verify schema generation to file."""
        mock_module = mock.MagicMock()

        class DummyRegistry(PydanticClassRegistryMixin):
            model_type: str

        mock_module.DummyRegistry = DummyRegistry
        mock_schema_deps["importlib"].import_module.return_value = mock_module
        mock_schema_deps["get_registry_schema"].return_value = {
            "schema_key": "schema_value"
        }

        output_mock = mocker.MagicMock(spec=Path)

        schema(
            registry_path="mock_module.DummyRegistry",
            output=output_mock,
            schema_format="openapi",
            indent=4,
        )

        mock_schema_deps["get_registry_schema"].assert_called_once_with(
            DummyRegistry, format="openapi"
        )
        output_mock.write_text.assert_called_once_with(
            '{\n    "schema_key": "schema_value"\n}', encoding="utf-8"
        )
        mock_schema_deps["typer_echo"].assert_not_called()

    @pytest.mark.sanity
    def test_invalid_path_no_dot(
        self, mock_schema_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify schema raises Exit when registry path has no dot."""
        with pytest.raises(typer.Exit) as exit_info:
            schema(registry_path="nodotregistry", output=None)

        assert exit_info.value.exit_code == 1
        mock_schema_deps["typer_echo"].assert_called_once_with(
            "Error: Invalid path 'nodotregistry'. "
            "Must be a fully qualified dot-path to a class.",
            err=True,
        )

    @pytest.mark.sanity
    def test_invalid_import_failure(
        self, mock_schema_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify schema raises Exit when module cannot be imported."""
        mock_schema_deps["importlib"].import_module.side_effect = ImportError(
            "No module named 'mock_module'"
        )

        with pytest.raises(typer.Exit) as exit_info:
            schema(registry_path="mock_module.Registry", output=None)

        assert exit_info.value.exit_code == 1
        mock_schema_deps["typer_echo"].assert_called_once_with(
            "Error: Could not import module 'mock_module': "
            "No module named 'mock_module'",
            err=True,
        )

    @pytest.mark.sanity
    def test_invalid_missing_attribute(
        self, mock_schema_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify schema raises Exit when class attribute is not found in module."""
        mock_module = mock.MagicMock()
        del mock_module.Registry
        mock_schema_deps["importlib"].import_module.return_value = mock_module

        with pytest.raises(typer.Exit) as exit_info:
            schema(registry_path="mock_module.Registry", output=None)

        assert exit_info.value.exit_code == 1
        mock_schema_deps["typer_echo"].assert_called_once_with(
            "Error: Module 'mock_module' has no attribute 'Registry'.",
            err=True,
        )

    @pytest.mark.sanity
    def test_invalid_not_subclass(
        self, mock_schema_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify schema raises Exit when class is not a valid subclass.

        It should check for PydanticClassRegistryMixin subclass.
        """
        mock_module = mock.MagicMock()

        class NotARegistryClass:
            pass

        mock_module.Registry = NotARegistryClass
        mock_schema_deps["importlib"].import_module.return_value = mock_module

        with pytest.raises(typer.Exit) as exit_info:
            schema(registry_path="mock_module.Registry", output=None)

        assert exit_info.value.exit_code == 1
        mock_schema_deps["typer_echo"].assert_called_once_with(
            "Error: 'mock_module.Registry' is not a subclass of "
            "PydanticClassRegistryMixin.",
            err=True,
        )

    @pytest.mark.regression
    def test_invalid_generation_error(
        self, mock_schema_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify schema raises Exit when schema generation fails."""
        mock_module = mock.MagicMock()

        class DummyRegistry(PydanticClassRegistryMixin):
            model_type: str

        mock_module.DummyRegistry = DummyRegistry
        mock_schema_deps["importlib"].import_module.return_value = mock_module
        mock_schema_deps["get_registry_schema"].side_effect = ValueError(
            "Generation error"
        )

        with pytest.raises(typer.Exit) as exit_info:
            schema(registry_path="mock_module.DummyRegistry", output=None)

        assert exit_info.value.exit_code == 1
        mock_schema_deps["typer_echo"].assert_called_once_with(
            "Error generating schema: Generation error",
            err=True,
        )

    @pytest.mark.regression
    def test_invalid_write_error(
        self, mock_schema_deps: dict[str, mock.MagicMock], mocker: MockerFixture
    ) -> None:
        """Verify schema raises Exit when writing output file fails."""
        mock_module = mock.MagicMock()

        class DummyRegistry(PydanticClassRegistryMixin):
            model_type: str

        mock_module.DummyRegistry = DummyRegistry
        mock_schema_deps["importlib"].import_module.return_value = mock_module
        mock_schema_deps["get_registry_schema"].return_value = {
            "schema_key": "schema_value"
        }

        output_mock = mocker.MagicMock(spec=Path)
        output_mock.write_text.side_effect = OSError("Write permission denied")

        with pytest.raises(typer.Exit) as exit_info:
            schema(
                registry_path="mock_module.DummyRegistry",
                output=output_mock,
            )

        assert exit_info.value.exit_code == 1
        mock_schema_deps["typer_echo"].assert_called_once_with(
            f"Error writing schema to '{output_mock}': Write permission denied",
            err=True,
        )


class TestListCmd:
    """Test suite for the list_cmd command."""

    @pytest.fixture
    def mock_list_deps(self, mocker: MockerFixture) -> dict[str, mock.MagicMock]:
        """Fixture to mock external dependencies of list_cmd."""
        return {
            "list_registries": mocker.patch(
                "disdantic.registry.RegistryManager.list_registries"
            ),
            "typer_echo": mocker.patch("typer.echo"),
        }

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the signature and types of list_cmd function."""
        assert callable(list_cmd)
        parameters = inspect.signature(list_cmd).parameters
        assert "json_output" in parameters

    @pytest.mark.smoke
    def test_invocation_json(self, mock_list_deps: dict[str, mock.MagicMock]) -> None:
        """Verify list_cmd outputs JSON when json_output=True."""
        mock_registries = {"RegistryA": {"key1": "path.to.Model1"}}
        mock_list_deps["list_registries"].return_value = mock_registries

        list_cmd(json_output=True)

        mock_list_deps["list_registries"].assert_called_once()
        mock_list_deps["typer_echo"].assert_called_once_with(
            json.dumps(mock_registries, indent=2)
        )

    @pytest.mark.sanity
    def test_invocation_tree(self, mock_list_deps: dict[str, mock.MagicMock]) -> None:
        """Verify list_cmd outputs structured tree view."""
        mock_registries = {
            "DummyListRegistry": {"key1": "path.to.Model1"},
            "UnknownRegistry": {"key2": "path.to.Model2"},
        }
        mock_list_deps["list_registries"].return_value = mock_registries

        class DummyListRegistry(PydanticClassRegistryMixin):
            model_type: str

            @classmethod
            def get_schema_discriminator(cls) -> str:
                return "model_type"

        list_cmd(json_output=False)

        calls = [
            call_args[0][0] for call_args in mock_list_deps["typer_echo"].call_args_list
        ]
        assert any("DummyListRegistry" in call_str for call_str in calls)
        assert any("model_type" in call_str for call_str in calls)
        assert any("key1" in call_str for call_str in calls)
        assert any("path.to.Model1" in call_str for call_str in calls)
        assert any("UnknownRegistry" in call_str for call_str in calls)
        assert any("key2" in call_str for call_str in calls)
        assert any("path.to.Model2" in call_str for call_str in calls)

    @pytest.mark.sanity
    def test_invalid_query_error(
        self, mock_list_deps: dict[str, mock.MagicMock]
    ) -> None:
        """Verify list_cmd raises Exit on manager querying errors."""
        mock_list_deps["list_registries"].side_effect = ValueError(
            "Database connection failed"
        )

        with pytest.raises(typer.Exit) as exit_info:
            list_cmd(json_output=False)

        assert exit_info.value.exit_code == 1
        mock_list_deps["typer_echo"].assert_called_once_with(
            "Error querying registries: Database connection failed",
            err=True,
        )


@pytest.mark.smoke
def test_app() -> None:
    """Verify the module-level app object is a Typer instance."""
    assert isinstance(app, typer.Typer)


@pytest.mark.smoke
def test___all__() -> None:
    """Verify that the module exports expected symbols in __all__."""
    assert set(__all__) == {"main"}
