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

"""End-to-End tests for dynamic cascading schema rebuilding."""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

import disdantic
from disdantic.model import ReloadableBaseModel
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import get_settings, reset_settings


# Models for testing direct, string-postponed, and union annotations
class E2EChildModel(ReloadableBaseModel):
    """Child model for E2E schema rebuild tests."""

    value: int


class E2EParentDirect(ReloadableBaseModel):
    """Parent model with direct reference to child."""

    child: E2EChildModel


class E2EParentString(ReloadableBaseModel):
    """Parent model with string annotation reference to child."""

    child: E2EChildModel


class E2EParentUnion(ReloadableBaseModel):
    """Parent model referencing child within a Union."""

    child: E2EChildModel | None


# Chained propagation hierarchy
class E2ELeafModel(ReloadableBaseModel):
    """Leaf model in a deep dependency chain."""

    value: str


class E2EMidModel(ReloadableBaseModel):
    """Middle model referencing the leaf model."""

    leaf: E2ELeafModel


class E2ERootModel(ReloadableBaseModel):
    """Root model referencing the middle model."""

    mid: E2EMidModel


class E2EAncestorModel(ReloadableBaseModel):
    """Ancestor model referencing the root model."""

    root: E2ERootModel


# Registry discriminated union propagation
class E2ERegistryBase(PydanticClassRegistryMixin):
    """Polymorphic registry base for E2E tests."""


class E2EParentUnionRegistry(ReloadableBaseModel):
    """Parent model referencing polymorphic registry base."""

    message: E2ERegistryBase


class TestSchemaRebuild:
    """E2E test suite for cascading validation schema rebuilding."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state and registry setup."""
        reset_settings()
        E2ERegistryBase.clear_registry()
        yield
        reset_settings()
        E2ERegistryBase.clear_registry()

    @pytest.fixture(
        params=[
            (E2EParentDirect, {"child": {"value": 10}}),
            (E2EParentString, {"child": {"value": 20}}),
            (E2EParentUnion, {"child": {"value": 30}}),
            (
                E2EAncestorModel,
                {"root": {"mid": {"leaf": {"value": "deep_chain"}}}},
            ),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> ReloadableBaseModel:
        """Fixture supplying valid ReloadableBaseModel instances."""
        model_cls, kwargs = request.param
        return model_cls(**kwargs)

    @pytest.mark.smoke
    def test_environment_contracts(self) -> None:
        """Validate structural environment contracts and settings defaults."""
        assert disdantic.__version__ is not None
        assert issubclass(ReloadableBaseModel, BaseModel)

        settings_instance = get_settings()
        assert settings_instance.enable_schema_rebuilding is True
        assert settings_instance.schema_rebuild_parents is True

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: ReloadableBaseModel) -> None:
        """Verify proper initial initialization of model structures."""
        assert isinstance(valid_instances, ReloadableBaseModel)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass invalid values to verify explicit system blockages."""
        with pytest.raises(ValidationError):
            E2EChildModel(value="not_an_int")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit critical parameters to verify system boundary defense lines."""
        with pytest.raises(ValidationError):
            E2EChildModel()  # type: ignore

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: ReloadableBaseModel) -> None:
        """Verify Pydantic serialization and validation pipelines."""
        dumped_data = valid_instances.model_dump()
        recreated = valid_instances.__class__.model_validate(dumped_data)
        assert recreated == valid_instances

    def _dynamically_add_field(
        self,
        model_cls: type[ReloadableBaseModel],
        field_name: str,
        field_type: type,
        default_val: Any = None,
    ) -> None:
        """Dynamically add a field to a model and clear its Pydantic cache."""
        model_cls.__annotations__[field_name] = field_type
        setattr(model_cls, field_name, default_val)
        model_cls.model_fields[field_name] = FieldInfo.from_annotated_attribute(
            field_type, default_val
        )

        for cache_attr in [
            "__pydantic_core_schema__",
            "__pydantic_validator__",
            "__pydantic_serializer__",
            "__pydantic_decorators__",
        ]:
            with contextlib.suppress(AttributeError):
                delattr(model_cls, cache_attr)

    def _dynamically_remove_field(
        self,
        model_cls: type[ReloadableBaseModel],
        field_name: str,
    ) -> None:
        """Dynamically remove a field from a model and clear its Pydantic cache."""
        if field_name in model_cls.__annotations__:
            del model_cls.__annotations__[field_name]
        if hasattr(model_cls, field_name):
            with contextlib.suppress(AttributeError):
                delattr(model_cls, field_name)
        if field_name in model_cls.model_fields:
            del model_cls.model_fields[field_name]

        for cache_attr in [
            "__pydantic_core_schema__",
            "__pydantic_validator__",
            "__pydantic_serializer__",
            "__pydantic_decorators__",
        ]:
            with contextlib.suppress(AttributeError):
                delattr(model_cls, cache_attr)

    @pytest.mark.smoke
    def test_direct_child_rebuild(self) -> None:
        """Verify cascading schema rebuild triggers for direct children."""
        parent_schema_before = E2EParentDirect.model_json_schema()
        assert "extra_field" not in parent_schema_before.get("$defs", {}).get(
            "E2EChildModel", {}
        ).get("properties", {})

        try:
            self._dynamically_add_field(E2EChildModel, "extra_field", str, None)
            E2EChildModel.reload_schema(parents=True)

            parent_schema_after = E2EParentDirect.model_json_schema()
            assert "extra_field" in parent_schema_after.get("$defs", {}).get(
                "E2EChildModel", {}
            ).get("properties", {})
        finally:
            self._dynamically_remove_field(E2EChildModel, "extra_field")
            E2EChildModel.reload_schema(parents=True)

    @pytest.mark.sanity
    def test_string_and_union_rebuild(self) -> None:
        """Verify string-postponed annotations and union traversals reload correctly."""
        schema_string_before = E2EParentString.model_json_schema()
        schema_union_before = E2EParentUnion.model_json_schema()

        assert "extra_field" not in schema_string_before.get("$defs", {}).get(
            "E2EChildModel", {}
        ).get("properties", {})
        assert "extra_field" not in schema_union_before.get("$defs", {}).get(
            "E2EChildModel", {}
        ).get("properties", {})

        try:
            self._dynamically_add_field(E2EChildModel, "extra_field", str, None)
            E2EChildModel.reload_schema(parents=True)

            schema_string_after = E2EParentString.model_json_schema()
            schema_union_after = E2EParentUnion.model_json_schema()

            assert "extra_field" in schema_string_after.get("$defs", {}).get(
                "E2EChildModel", {}
            ).get("properties", {})
            assert "extra_field" in schema_union_after.get("$defs", {}).get(
                "E2EChildModel", {}
            ).get("properties", {})
        finally:
            self._dynamically_remove_field(E2EChildModel, "extra_field")
            E2EChildModel.reload_schema(parents=True)

    @pytest.mark.regression
    def test_rebuild_disabled(self) -> None:
        """Verify rebuild propagation is skipped when globally disabled in settings."""
        settings_instance = get_settings()

        # 1. Disable schema rebuilding completely
        settings_instance.enable_schema_rebuilding = False
        try:
            self._dynamically_add_field(E2EChildModel, "extra_field", str, None)
            E2EChildModel.reload_schema(parents=True)

            parent_schema_after = E2EParentDirect.model_json_schema()
            assert "extra_field" not in parent_schema_after.get("$defs", {}).get(
                "E2EChildModel", {}
            ).get("properties", {})
        finally:
            settings_instance.enable_schema_rebuilding = True
            self._dynamically_remove_field(E2EChildModel, "extra_field")
            E2EChildModel.reload_schema(parents=True)

        # 2. Disable parent propagation only
        settings_instance.schema_rebuild_parents = False
        try:
            self._dynamically_add_field(E2EChildModel, "extra_field", str, None)
            E2EChildModel.reload_schema(parents=True)

            parent_schema_after = E2EParentDirect.model_json_schema()
            assert "extra_field" not in parent_schema_after.get("$defs", {}).get(
                "E2EChildModel", {}
            ).get("properties", {})
        finally:
            settings_instance.schema_rebuild_parents = True
            self._dynamically_remove_field(E2EChildModel, "extra_field")
            E2EChildModel.reload_schema(parents=True)

    @pytest.mark.regression
    def test_chained_propagation(self) -> None:
        """Verify rebuild cascades transitively up deep dependency chains."""
        ancestor_schema_before = E2EAncestorModel.model_json_schema()
        assert "extra_field" not in ancestor_schema_before.get("$defs", {}).get(
            "E2ELeafModel", {}
        ).get("properties", {})

        try:
            self._dynamically_add_field(E2ELeafModel, "extra_field", str, None)
            E2ELeafModel.reload_schema(parents=True)

            ancestor_schema_after = E2EAncestorModel.model_json_schema()
            assert "extra_field" in ancestor_schema_after.get("$defs", {}).get(
                "E2ELeafModel", {}
            ).get("properties", {})
        finally:
            self._dynamically_remove_field(E2ELeafModel, "extra_field")
            E2ELeafModel.reload_schema(parents=True)

    @pytest.mark.sanity
    def test_dynamic_union_registry(self) -> None:
        """Verify dynamic subclass registration cascades."""
        parent_schema_before = E2EParentUnionRegistry.model_json_schema()
        assert "E2ENewMsg" not in parent_schema_before.get("$defs", {})

        # Dynamically register a new message subclass
        @E2ERegistryBase.register("new_msg")
        class E2ENewMsg(E2ERegistryBase):
            text: str

        try:
            parent_schema_after = E2EParentUnionRegistry.model_json_schema()
            assert "E2ENewMsg" in parent_schema_after.get("$defs", {})
            # Verify parsed registry value can validate successfully E2E
            parsed = E2EParentUnionRegistry.model_validate(
                {"message": {"model_type": "new_msg", "text": "hello e2e union"}}
            )
            assert isinstance(parsed.message, E2ENewMsg)
            assert parsed.message.text == "hello e2e union"
        finally:
            E2ERegistryBase.unregister("new_msg")
            E2ERegistryBase.clear_registry()
            # Also clear the dynamically created class from python subclasses
            # by reloading E2ERegistryBase schema
            E2ERegistryBase.reload_schema(parents=True)
