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

"""Unit tests for the schema module."""

from __future__ import annotations

import inspect
from collections.abc import Generator
from typing import Any, Literal, cast, get_args, get_origin, get_type_hints

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError
from pytest_mock import MockerFixture

from disdantic.registry import PydanticClassRegistryMixin
from disdantic.schema import SchemaFormat, __all__, get_registry_schema


class SchemaTestBase(PydanticClassRegistryMixin):
    """Base model for schema unit testing."""

    model_type: str


@SchemaTestBase.register("schema_child")
class SchemaTestChild(SchemaTestBase):
    """Child model for schema unit testing."""

    model_type: Literal["schema_child"] = "schema_child"
    value: int


class TestGetRegistrySchema:
    """Test suite for the get_registry_schema function."""

    @pytest.fixture
    def setup_registry(self) -> Generator[type[SchemaTestBase], None, None]:
        """Set up the SchemaTestBase registry and clear it on teardown."""
        SchemaTestBase.clear_registry()
        SchemaTestBase.register_decorator(SchemaTestChild, name="schema_child")
        yield SchemaTestBase
        SchemaTestBase.clear_registry()

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the signature and types of get_registry_schema function."""
        # Verify it is a callable function
        assert callable(get_registry_schema)
        assert inspect.isfunction(get_registry_schema)

        # Verify parameter signatures
        signature_params = inspect.signature(get_registry_schema).parameters
        assert "registry_class" in signature_params
        assert "format" in signature_params

        # Verify type annotations
        type_hints = get_type_hints(get_registry_schema)
        assert "registry_class" in type_hints
        assert "format" in type_hints
        assert "return" in type_hints

    @pytest.mark.smoke
    def test_invocation_json(
        self,
        mocker: MockerFixture,
        setup_registry: type[SchemaTestBase],
    ) -> None:
        """Verify get_registry_schema with JSON format."""
        # Setup: Spy on model_rebuild
        rebuild_mock = mocker.spy(setup_registry, "model_rebuild")

        # Invoke: Generate the schema
        schema = get_registry_schema(setup_registry, format="json")

        # Assert: Validate key traits of the schema structure and rebuild call
        assert isinstance(schema, dict)
        assert "$defs" in schema
        assert "SchemaTestChild" in schema["$defs"]
        assert "discriminator" in schema
        assert schema["discriminator"]["propertyName"] == "model_type"
        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.smoke
    def test_invocation_openapi(
        self,
        mocker: MockerFixture,
        setup_registry: type[SchemaTestBase],
    ) -> None:
        """Verify get_registry_schema with OpenAPI format."""
        # Setup: Spy on model_rebuild
        rebuild_mock = mocker.spy(setup_registry, "model_rebuild")

        # Invoke: Generate the schema
        schema = get_registry_schema(setup_registry, format="openapi")

        # Assert: Validate OpenAPI-specific key traits and ref translation
        assert isinstance(schema, dict)
        assert "$defs" not in schema
        assert "components" in schema
        assert "schemas" in schema["components"]
        assert "SchemaTestChild" in schema["components"]["schemas"]
        # Check ref template translation
        assert "oneOf" in schema
        for item in schema["oneOf"]:
            assert item["$ref"].startswith("#/components/schemas/")
        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.sanity
    def test_invocation_invalid_format(
        self,
        mocker: MockerFixture,
        setup_registry: type[SchemaTestBase],
    ) -> None:
        """Verify get_registry_schema fallback behavior on unsupported formats."""
        # Setup: Spy on model_rebuild
        rebuild_mock = mocker.spy(setup_registry, "model_rebuild")

        # Invoke: Generate the schema with cast to test un-typed string behavior
        schema = get_registry_schema(setup_registry, format=cast("Any", "invalid"))

        # Assert: Validate fallback behavior to standard json format
        assert isinstance(schema, dict)
        assert "$defs" in schema
        assert "SchemaTestChild" in schema["$defs"]
        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        ("invalid_class", "expected_type_name"),
        [
            (BaseModel, "BaseModel"),
            (str, "str"),
            (None, "NoneType"),
            (123, "int"),
            (SchemaTestChild(value=42), "SchemaTestChild"),
        ],
    )
    def test_invalid_registry_class(
        self,
        invalid_class: Any,
        expected_type_name: str,
    ) -> None:
        """Verify TypeError is raised for invalid registry classes."""
        expected_message = (
            "Expected a subclass of PydanticClassRegistryMixin, "
            f"got {expected_type_name}"
        )
        with pytest.raises(TypeError, match=expected_message):
            get_registry_schema(invalid_class)

    @pytest.mark.regression
    def test_empty_registry(self) -> None:
        """Verify get_registry_schema behaves correctly for empty registries."""

        # Setup: Define an empty test registry class
        class EmptyTestRegistry(PydanticClassRegistryMixin):
            model_type: str

        # Invoke: Generate the schema
        schema = get_registry_schema(EmptyTestRegistry)

        # Assert: Schema compiles successfully without unions
        assert isinstance(schema, dict)
        assert "oneOf" not in schema

    @pytest.mark.regression
    def test_custom_discriminator(self) -> None:
        """Verify get_registry_schema respects custom schema discriminator overrides."""

        # Setup: Define registry and child subclass with custom discriminator
        class CustomBase(PydanticClassRegistryMixin):
            schema_discriminator = "custom_type"
            custom_type: str

        @CustomBase.register("custom_child")
        class CustomChild(CustomBase):
            custom_type: Literal["custom_child"] = "custom_child"
            info: str

        # Invoke: Generate the schema
        schema = get_registry_schema(CustomBase)

        # Assert: Discriminator matches CustomBase.schema_discriminator
        assert isinstance(schema, dict)
        assert "discriminator" in schema
        assert schema["discriminator"]["propertyName"] == "custom_type"

        # Teardown: Clean up registry
        CustomBase.clear_registry()

    @pytest.mark.regression
    def test_multiple_subclasses(self) -> None:
        """Verify get_registry_schema manages registries with multiple subclasses."""

        # Setup: Define base registry and register multiple subclasses
        class MultiBase(PydanticClassRegistryMixin):
            model_type: str

        @MultiBase.register("child_one")
        class ChildOne(MultiBase):
            model_type: Literal["child_one"] = "child_one"
            field_one: int

        @MultiBase.register("child_two")
        class ChildTwo(MultiBase):
            model_type: Literal["child_two"] = "child_two"
            field_two: str

        # Invoke: Generate the schema
        schema = get_registry_schema(MultiBase)

        # Assert: Both subclasses are in defs and referenced in oneOf
        assert isinstance(schema, dict)
        assert "$defs" in schema
        assert "ChildOne" in schema["$defs"]
        assert "ChildTwo" in schema["$defs"]
        assert "oneOf" in schema
        assert len(schema["oneOf"]) == 2

        # Teardown: Clean up registry
        MultiBase.clear_registry()


@pytest.mark.smoke
def test_schema_format() -> None:
    """Verify metadata and value options of SchemaFormat type annotation."""
    # Retrieve metadata of SchemaFormat
    origin = get_origin(SchemaFormat)
    args = get_args(SchemaFormat)

    # SchemaFormat should be Annotated
    assert origin is not None

    # Retrieve underlying type args (Annotated wraps the first arg, then metadata)
    assert len(args) >= 2
    literal_type = args[0]
    assert get_origin(literal_type) is Literal
    assert set(get_args(literal_type)) == {"json", "openapi"}

    # Assert description details
    description = args[1]
    assert isinstance(description, str)
    assert "Supported schema export formats" in description

    # Assert validation behavior using TypeAdapter
    adapter = TypeAdapter(SchemaFormat)
    assert adapter.validate_python("json") == "json"
    assert adapter.validate_python("openapi") == "openapi"
    with pytest.raises(ValidationError):
        adapter.validate_python("unsupported_format")


@pytest.mark.smoke
def test_all() -> None:
    """Verify that the module exports expected symbols in __all__."""
    assert set(__all__) == {"SchemaFormat", "get_registry_schema"}
