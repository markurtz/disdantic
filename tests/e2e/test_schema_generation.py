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

"""End-to-end tests for Schema Generation (US-7.2)."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.schema import get_registry_schema
from disdantic.settings import reset_settings


class BaseE2ESchemaModel(PydanticClassRegistryMixin):
    """Base model class used to test PydanticClassRegistryMixin schema generation."""

    schema_discriminator = "schema_type"
    schema_type: str


@BaseE2ESchemaModel.register("text")
class TextSchemaModel(BaseE2ESchemaModel):
    """Subclass representing text schema model."""

    schema_type: Literal["text"] = "text"
    body: str


@BaseE2ESchemaModel.register("image")
class ImageSchemaModel(BaseE2ESchemaModel):
    """Subclass representing image schema model."""

    schema_type: Literal["image"] = "image"
    url: str
    width: int


class TestSchemaGeneration:
    """End-to-end test suite for US-7.2: Schema Generation."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        BaseE2ESchemaModel.clear_registry()
        BaseE2ESchemaModel.register_decorator(TextSchemaModel, name="text")
        BaseE2ESchemaModel.register_decorator(ImageSchemaModel, name="image")
        yield
        BaseE2ESchemaModel.clear_registry()
        reset_settings()

    @pytest.fixture(params=["text_instance", "image_instance"])
    def valid_instances(self, request: pytest.FixtureRequest) -> BaseE2ESchemaModel:
        """Fixture supplying properly configured model instances."""
        if request.param == "text_instance":
            return TextSchemaModel(body="Hello schema E2E")
        return ImageSchemaModel(url="https://example.com/e2e.jpg", width=1920)

    @pytest.mark.smoke
    def test_contract_and_environment(self) -> None:
        """Validate structural environment contracts and schema API."""
        assert inspect.isfunction(get_registry_schema)
        assert issubclass(BaseE2ESchemaModel, PydanticClassRegistryMixin)
        assert issubclass(BaseE2ESchemaModel, BaseModel)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: BaseE2ESchemaModel) -> None:
        """Assert correct initial system wiring and startup state."""
        assert isinstance(valid_instances, BaseE2ESchemaModel)
        assert valid_instances.schema_type in ("text", "image")

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify explicit system blockages on invalid construction parameters."""
        with pytest.raises(ValidationError):
            ImageSchemaModel(url="https://example.com/e2e.jpg", width="not_a_number")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify system boundary defense lines when missing required parameters."""
        with pytest.raises(ValidationError):
            TextSchemaModel()  # type: ignore

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: BaseE2ESchemaModel) -> None:
        """Verify model_dump and model_validate serialization boundaries."""
        dumped_data = valid_instances.model_dump()
        assert isinstance(dumped_data, dict)
        assert dumped_data["schema_type"] == valid_instances.schema_type

        validated_instance = BaseE2ESchemaModel.model_validate(dumped_data)
        assert validated_instance.schema_type == valid_instances.schema_type

    @pytest.mark.regression
    def test_dynamic_resolution(self) -> None:
        """Verify dynamic schema resolution gets registry schema successfully."""
        schema_dict = get_registry_schema(BaseE2ESchemaModel, format="json")
        assert isinstance(schema_dict, dict)
        assert "$defs" in schema_dict

    @pytest.mark.smoke
    def test_schema_format_json(self) -> None:
        """Verify standard JSON schema format contains expected defs."""
        schema_dict = get_registry_schema(BaseE2ESchemaModel, format="json")
        assert "$defs" in schema_dict
        assert "TextSchemaModel" in schema_dict["$defs"]
        assert "ImageSchemaModel" in schema_dict["$defs"]

    @pytest.mark.sanity
    def test_schema_format_openapi(self) -> None:
        """Verify OpenAPI schema format restructures defs under components."""
        schema_dict = get_registry_schema(BaseE2ESchemaModel, format="openapi")
        assert "components" in schema_dict
        assert "schemas" in schema_dict["components"]
        assert "TextSchemaModel" in schema_dict["components"]["schemas"]
        assert "ImageSchemaModel" in schema_dict["components"]["schemas"]


class TestCLIEntrypoint:
    """E2E test suite for 'schema' CLI subcommand."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        BaseE2ESchemaModel.clear_registry()
        BaseE2ESchemaModel.register_decorator(TextSchemaModel, name="text")
        BaseE2ESchemaModel.register_decorator(ImageSchemaModel, name="image")
        yield
        BaseE2ESchemaModel.clear_registry()
        reset_settings()

    @pytest.mark.smoke
    def test_cli_schema_help(self) -> None:
        """Verify that schema help prints configuration flags."""
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "--help"])
        assert result.exit_code == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.stdout)
        assert "--output" in clean_stdout
        assert "--format" in clean_stdout
        assert "--indent" in clean_stdout

    @pytest.mark.smoke
    def test_cli_schema_stdout_json(self) -> None:
        """Verify stdout outputs standard JSON schema."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.e2e.test_schema_generation.BaseE2ESchemaModel"],
        )
        assert result.exit_code == 0
        schema_dict = json.loads(result.stdout)
        assert "$defs" in schema_dict

    @pytest.mark.sanity
    def test_cli_schema_stdout_openapi(self) -> None:
        """Verify stdout outputs OpenAPI formatted schema structure."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.e2e.test_schema_generation.BaseE2ESchemaModel",
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
        """Verify schema output respects custom indentation formatting."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.e2e.test_schema_generation.BaseE2ESchemaModel",
                "--indent",
                "4",
            ],
        )
        assert result.exit_code == 0
        assert "\n    " in result.stdout

    @pytest.mark.regression
    def test_cli_schema_file_output(self, tmp_path: Path) -> None:
        """Verify schema generation writes directly to output file."""
        output_file = tmp_path / "schema.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                "tests.e2e.test_schema_generation.BaseE2ESchemaModel",
                "-o",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        schema_dict = json.loads(output_file.read_text(encoding="utf-8"))
        assert "$defs" in schema_dict

    @pytest.mark.regression
    def test_cli_schema_invalid_path(self) -> None:
        """Verify schema command exits with code 1 for invalid paths."""
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "BaseE2ESchemaModel"])
        assert result.exit_code == 1

    @pytest.mark.regression
    def test_cli_schema_non_existent_module(self) -> None:
        """Verify schema command exits with code 1 on missing module imports."""
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "completely_missing_pkg.Model"])
        assert result.exit_code == 1

    @pytest.mark.regression
    def test_cli_schema_non_registry_class(self) -> None:
        """Verify schema command exits with code 1 for non-registry targets."""
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "disdantic.settings.Settings"])
        assert result.exit_code == 1
