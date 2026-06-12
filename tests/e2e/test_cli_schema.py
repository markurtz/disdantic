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

"""End-to-end test suite for US-07: Registry Schema Export (JSON/OpenAPI)."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from os import environ, pathsep
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.schema import SchemaFormat, get_registry_schema
from tests.conftest import TemporaryPackageBuilder


class TestRegistrySchemaExport:
    """End-to-end test suite validating US-07 Schema Export functionality."""

    @pytest.fixture
    def setup_package(
        self, temp_package_builder: TemporaryPackageBuilder
    ) -> tuple[type[Any], type[Any], type[Any]]:
        """Creates a temporary package and imports the registry class and models."""
        modules = {
            "models": (
                "# Copyright 2026 markurtz\n"
                "from typing import Literal\n"
                "from disdantic.registry import PydanticClassRegistryMixin\n\n"
                "class BaseMessage(PydanticClassRegistryMixin):\n"
                "    schema_discriminator = 'message_type'\n"
                "    message_type: str\n\n"
                "@BaseMessage.register('text')\n"
                "class TextMessage(BaseMessage):\n"
                "    message_type: Literal['text'] = 'text'\n"
                "    text_content: str\n\n"
                "@BaseMessage.register('image')\n"
                "class ImageMessage(BaseMessage):\n"
                "    message_type: Literal['image'] = 'image'\n"
                "    image_url: str\n"
                "    width: int\n"
                "    height: int\n"
            )
        }
        temp_package_builder.create_package("my_pkg_schema", modules)

        models = importlib.import_module("my_pkg_schema.models")

        return models.BaseMessage, models.TextMessage, models.ImageMessage

    @pytest.fixture
    def valid_instances(
        self,
        setup_package: tuple[type[Any], type[Any], type[Any]],
    ) -> list[Any]:
        """Fixture supplying properly configured model instances."""
        _, text_cls, image_cls = setup_package
        return [
            text_cls(text_content="Hello E2E"),
            image_cls(
                image_url="https://example.com/image.png",
                width=640,
                height=480,
            ),
        ]

    @pytest.mark.smoke
    def test_contract_validation(
        self,
        setup_package: tuple[type[Any], type[Any], type[Any]],
    ) -> None:
        """Validate structural environment contracts and registry schema api."""
        base_cls, _, _ = setup_package
        assert issubclass(base_cls, PydanticClassRegistryMixin)
        assert issubclass(base_cls, BaseModel)
        assert hasattr(base_cls, "model_json_schema")

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: list[Any]) -> None:
        """Assert correct initial system wiring and startup state."""
        for instance in valid_instances:
            assert isinstance(instance, BaseModel)
            assert instance.message_type in ("text", "image")

    @pytest.mark.sanity
    def test_invalid_initialization_values(
        self,
        setup_package: tuple[type[Any], type[Any], type[Any]],
    ) -> None:
        """Verify explicit system blockages on invalid construction parameters."""
        _, _, image_cls = setup_package
        with pytest.raises(ValidationError):
            image_cls(
                image_url="https://example.com/image.png",
                width="invalid",
                height=480,
            )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self,
        setup_package: tuple[type[Any], type[Any], type[Any]],
    ) -> None:
        """Verify system boundary defense lines when missing required parameters."""
        _, text_cls, _ = setup_package
        with pytest.raises(ValidationError):
            text_cls()

    @pytest.mark.regression
    def test_marshalling(
        self,
        setup_package: tuple[type[Any], type[Any], type[Any]],
        valid_instances: list[Any],
    ) -> None:
        """Verify model_dump and model_validate serialization boundaries."""
        base_cls, _, _ = setup_package
        for instance in valid_instances:
            dumped_data = instance.model_dump()
            assert isinstance(dumped_data, dict)
            assert dumped_data["message_type"] == instance.message_type

            validated_instance = base_cls.model_validate(dumped_data)
            assert validated_instance.message_type == instance.message_type

    @pytest.mark.regression
    def test_dynamic_registry_keys(
        self,
        setup_package: tuple[type[Any], type[Any], type[Any]],
    ) -> None:
        """Verify registry maps the registered keys properly."""
        base_cls, text_cls, image_cls = setup_package
        assert base_cls.is_registered("text")
        assert base_cls.is_registered("image")
        classes = base_cls.registered_classes()
        assert text_cls in classes
        assert image_cls in classes

    @pytest.mark.regression
    def test_programmatic_get_schema_invalid(self) -> None:
        """Verify get_registry_schema raises TypeError on invalid types."""
        with pytest.raises(TypeError) as exc_info:
            get_registry_schema(cast("Any", None))
        assert "Expected a subclass of PydanticClassRegistryMixin" in str(
            exc_info.value
        )

    @pytest.mark.smoke
    def test_param_schema_format(self) -> None:
        """Validate the module-level SchemaFormat annotation/type."""
        # Simple check of type definition compatibility or schema format properties
        assert "openapi" in SchemaFormat.__metadata__[0]


class TestCLIEntrypoint:
    """E2E test suite for 'schema' CLI subcommand."""

    @pytest.fixture
    def setup_package(self, temp_package_builder: TemporaryPackageBuilder) -> str:
        """Creates a temporary python package to test dynamic import resolution in CLI.

        Returns the dot-path to the generated registry class.
        """
        modules = {
            "models": (
                "# Copyright 2026 markurtz\n"
                "from typing import Literal\n"
                "from disdantic.registry import PydanticClassRegistryMixin\n\n"
                "class BaseMessage(PydanticClassRegistryMixin):\n"
                "    schema_discriminator = 'message_type'\n"
                "    message_type: str\n\n"
                "@BaseMessage.register('text')\n"
                "class TextMessage(BaseMessage):\n"
                "    message_type: Literal['text'] = 'text'\n"
                "    text_content: str\n"
            )
        }
        temp_package_builder.create_package("my_package", modules)
        return "my_package.models.BaseMessage"

    @pytest.mark.smoke
    def test_cli_schema_help(self) -> None:
        """Verify that schema help prints configuration flags."""
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.stdout
        assert "--format" in result.stdout
        assert "--indent" in result.stdout

    @pytest.mark.smoke
    def test_openapi_schema_formatting(self, setup_package: str) -> None:
        """Verify OpenAPI schema formatting converting $defs to components/schemas.

        Given a registry class "BaseMessage" inheriting from
        PydanticClassRegistryMixin When I run command "disdantic schema
        my_package.models.BaseMessage --format openapi" Then the generated schema
        must convert definition references from "$defs" to "components/schemas"
        And stdout must print the JSON schema
        """
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", setup_package, "--format", "openapi"],
        )
        assert result.exit_code == 0
        schema_dict = json.loads(result.stdout)

        # Verify components/schemas structure exists and $defs is absent
        assert "$defs" not in schema_dict
        assert "components" in schema_dict
        assert "schemas" in schema_dict["components"]
        assert "TextMessage" in schema_dict["components"]["schemas"]

        # Verify references in properties use the components path
        root_any_of = schema_dict.get("anyOf") or schema_dict.get("oneOf")
        assert root_any_of is not None
        for ref_item in root_any_of:
            ref_path = ref_item["$ref"]
            assert ref_path.startswith("#/components/schemas/")

    @pytest.mark.sanity
    def test_schema_export_to_output_file(
        self, setup_package: str, tmp_path: Path
    ) -> None:
        """Verify exporting schema to output file with custom indent.

        Given a registry class "BaseMessage" When I execute "disdantic schema
        my_package.models.BaseMessage --output build/schema.json --indent 4"
        Then the file "build/schema.json" must contain the indented JSON schema
        """
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        output_file = build_dir / "schema.json"

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "schema",
                setup_package,
                "--output",
                str(output_file),
                "--indent",
                "4",
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        schema_dict = json.loads(content)
        assert "$defs" in schema_dict

        # Verify indent of 4 spaces is used in the output file
        assert "\n    " in content

    @pytest.mark.sanity
    def test_schema_export_non_registry_class(self) -> None:
        """Verify command outputs error and exits with code 1 if not registry.

        And if the class is not a subclass of PydanticClassRegistryMixin,
        the command must output an error and exit with code 1
        """
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "disdantic.settings.Settings"],
        )
        assert result.exit_code == 1
        assert "is not a subclass of PydanticClassRegistryMixin" in result.stderr

    @pytest.mark.regression
    def test_cli_subprocess_execution(
        self, setup_package: str, temp_package_builder: TemporaryPackageBuilder
    ) -> None:
        """Verify E2E execution via actual subprocess using Python interpreter."""
        build_dir = temp_package_builder.base_dir / "build_sub"
        build_dir.mkdir()
        output_file = build_dir / "schema.json"

        env = environ.copy()
        env["PYTHONPATH"] = pathsep.join(
            [str(temp_package_builder.base_dir), env.get("PYTHONPATH", "")]
        )

        cmd = [
            sys.executable,
            "-m",
            "disdantic",
            "schema",
            setup_package,
            "--output",
            str(output_file),
            "--indent",
            "4",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        assert result.returncode == 0
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        schema_dict = json.loads(content)
        assert "$defs" in schema_dict
        assert "\n    " in content

        # Also run openapi stdout in subprocess
        cmd_openapi = [
            sys.executable,
            "-m",
            "disdantic",
            "schema",
            setup_package,
            "--format",
            "openapi",
        ]
        result_openapi = subprocess.run(
            cmd_openapi,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result_openapi.returncode == 0
        schema_dict_openapi = json.loads(result_openapi.stdout)
        assert "$defs" not in schema_dict_openapi
        assert "components" in schema_dict_openapi
