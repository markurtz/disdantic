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
from typing import Any, Literal, get_type_hints

import pytest
from pydantic import BaseModel
from pytest_mock import MockerFixture

from disdantic.registry import PydanticClassRegistryMixin
from disdantic.schema import __all__, get_registry_schema


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
    @pytest.mark.parametrize(
        ("format_type", "expected_key"),
        [
            ("json", "$defs"),
            ("openapi", "components"),
            ("invalid", "$defs"),
        ],
    )
    def test_invocation(
        self,
        mocker: MockerFixture,
        setup_registry: type[SchemaTestBase],
        format_type: Literal["json", "openapi"],
        expected_key: str,
    ) -> None:
        """Verify get_registry_schema with valid inputs and formats."""
        # Setup: Spy on model_rebuild
        rebuild_mock = mocker.spy(setup_registry, "model_rebuild")

        # Invoke: Generate the schema
        schema = get_registry_schema(setup_registry, format=format_type)

        # Assert: Validate key traits of the schema structure and rebuild call
        assert isinstance(schema, dict)
        assert expected_key in schema
        rebuild_mock.assert_called_once_with(force=True)

        if format_type == "openapi":
            assert "$defs" not in schema
            assert "schemas" in schema["components"]
            assert "SchemaTestChild" in schema["components"]["schemas"]
            # Check ref template translation
            assert "oneOf" in schema
            for item in schema["oneOf"]:
                assert item["$ref"].startswith("#/components/schemas/")
        else:
            assert "$defs" in schema
            assert "SchemaTestChild" in schema["$defs"]
            assert "discriminator" in schema
            assert schema["discriminator"]["propertyName"] == "model_type"

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
    def test_invalid(
        self,
        invalid_class: Any,
        expected_type_name: str,
    ) -> None:
        """Verify TypeError is raised for invalid classes."""
        expected_message = (
            "Expected a subclass of PydanticClassRegistryMixin, "
            f"got {expected_type_name}"
        )
        with pytest.raises(TypeError, match=expected_message):
            get_registry_schema(invalid_class)


@pytest.mark.smoke
def test_all() -> None:
    """Verify that the module exports expected symbols in __all__."""
    assert set(__all__) == {"SchemaFormat", "get_registry_schema"}
