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

"""Integration tests for the schema CLI command and programmatic API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal, get_args, get_origin

import pytest
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.schema import SchemaFormat, get_registry_schema
from tests.python.integration.test_registry import (
    BaseIntegrationModel,
    ImageIntegrationModel,
    TextIntegrationModel,
)


@pytest.mark.smoke
def test_schema_format() -> None:
    """Validate public module-level SchemaFormat annotation type."""
    origin_type = get_origin(SchemaFormat)
    assert origin_type is Annotated

    type_arguments = get_args(SchemaFormat)
    assert len(type_arguments) >= 2

    literal_type = type_arguments[0]
    assert get_origin(literal_type) is Literal
    assert get_args(literal_type) == ("json", "openapi")

    description_text = type_arguments[1]
    assert isinstance(description_text, str)
    assert "Supported schema export formats" in description_text


class DynamicIntegrationTestBase(PydanticClassRegistryMixin):
    schema_discriminator = "action_type"
    action_type: str


@DynamicIntegrationTestBase.register("click")
class ClickAction(DynamicIntegrationTestBase):
    action_type: Literal["click"] = "click"
    button_id: str


@DynamicIntegrationTestBase.register("hover")
class HoverAction(DynamicIntegrationTestBase):
    action_type: Literal["hover"] = "hover"
    element_id: str


class TestGetRegistrySchema:
    """Integration tests validating get_registry_schema orchestrator."""

    @pytest.mark.sanity
    @pytest.mark.parametrize("schema_fmt", ["json", "openapi"])
    def test_invocation(self, schema_fmt: SchemaFormat) -> None:
        """Verify get_registry_schema invocation for happy path formats.

        Follows the Assemble -> Invoke -> Teardown lifecycle.
        """
        # --- Invoke & Verify ---
        schema_dict = get_registry_schema(DynamicIntegrationTestBase, format=schema_fmt)

        assert isinstance(schema_dict, dict)
        if schema_fmt == "openapi":
            assert "$defs" not in schema_dict
            assert "components" in schema_dict
            assert "schemas" in schema_dict["components"]
            assert "ClickAction" in schema_dict["components"]["schemas"]
            assert "HoverAction" in schema_dict["components"]["schemas"]
        else:
            assert "$defs" in schema_dict
            assert "ClickAction" in schema_dict["$defs"]
            assert "HoverAction" in schema_dict["$defs"]

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        "invalid_input",
        [
            int,
            str,
            None,
            123,
            "not_a_class",
        ],
    )
    def test_invalid(self, invalid_input: Any) -> None:
        """Verify invalid registry class types raise TypeError."""
        with pytest.raises(TypeError) as exc_info:
            get_registry_schema(invalid_input)  # type: ignore[arg-type]
        assert "Expected a subclass of PydanticClassRegistryMixin" in str(
            exc_info.value
        )


class TestCLIEntrypoint:
    """Integration tests validating disdantic schema CLI subcommand."""

    @pytest.fixture(autouse=True)
    def setup_registry(self) -> None:
        """Initialize and populate the registry class for CLI testing."""
        BaseIntegrationModel.clear_registry()
        BaseIntegrationModel.register_decorator(TextIntegrationModel, name="text")
        BaseIntegrationModel.register_decorator(ImageIntegrationModel, name="image")

    @pytest.mark.sanity
    def test_schema_json_stdout(self) -> None:
        """Verify schema JSON generation outputs to stdout."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.python.integration.test_registry.BaseIntegrationModel"],
        )

        assert result.exit_code == 0
        schema_dict = json.loads(result.stdout)
        assert isinstance(schema_dict, dict)
        assert "$defs" in schema_dict
        assert "TextIntegrationModel" in schema_dict["$defs"]
        assert "ImageIntegrationModel" in schema_dict["$defs"]

    @pytest.mark.sanity
    def test_schema_openapi_stdout(self) -> None:
        """Verify schema OpenAPI generation outputs to stdout."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.python.integration.test_registry.BaseIntegrationModel",
                "-f",
                "openapi",
            ],
        )

        assert result.exit_code == 0
        schema_dict = json.loads(result.stdout)
        assert isinstance(schema_dict, dict)
        assert "$defs" not in schema_dict
        assert "components" in schema_dict
        assert "schemas" in schema_dict["components"]
        assert "TextIntegrationModel" in schema_dict["components"]["schemas"]

    @pytest.mark.sanity
    def test_schema_indent(self) -> None:
        """Verify schema CLI output obeys indentation level constraint."""
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
    def test_schema_file_output(self, tmp_path: Path) -> None:
        """Verify schema writes output to file if output option is specified."""
        output_file = tmp_path / "schema.json"
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
        assert "TextIntegrationModel" in schema_dict["$defs"]

    @pytest.mark.sanity
    def test_schema_invalid_path_syntax(self) -> None:
        """Verify exit code 1 when path is not a dot-path."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "BaseIntegrationModel"],
        )

        assert result.exit_code != 0
        assert "Error: Invalid path" in result.stderr

    @pytest.mark.sanity
    def test_schema_non_existent_module(self) -> None:
        """Verify exit code 1 when module doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "non_existent_module.BaseIntegrationModel"],
        )

        assert result.exit_code != 0
        assert "Error: Could not import module" in result.stderr

    @pytest.mark.sanity
    def test_schema_non_existent_attribute(self) -> None:
        """Verify exit code 1 when attribute doesn't exist in module."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.python.integration.test_registry.NonExistent"],
        )

        assert result.exit_code != 0
        assert "has no attribute" in result.stderr

    @pytest.mark.sanity
    def test_schema_not_registry_class(self) -> None:
        """Verify exit code 1 when class is not a PydanticClassRegistryMixin."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "disdantic.settings.Settings"],
        )

        assert result.exit_code != 0
        assert "is not a subclass of PydanticClassRegistryMixin" in result.stderr

    @pytest.mark.regression
    def test_schema_generation_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI error output and exit status when schema generation fails."""

        def mock_get_schema(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Mock schema generation failure")

        monkeypatch.setattr("disdantic.__main__.get_registry_schema", mock_get_schema)

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.python.integration.test_registry.BaseIntegrationModel"],
        )

        assert result.exit_code != 0
        assert (
            "Error generating schema: Mock schema generation failure" in result.stderr
        )

    @pytest.mark.regression
    def test_schema_write_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI error output and exit status when file writing fails."""

        def mock_write_text(*args: Any, **kwargs: Any) -> Any:
            raise PermissionError("Permission denied")

        monkeypatch.setattr(Path, "write_text", mock_write_text)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.python.integration.test_registry.BaseIntegrationModel",
                "-o",
                "dummy_output.json",
            ],
        )

        assert result.exit_code != 0
        assert "Error writing schema to" in result.stderr
        assert "Permission denied" in result.stderr
