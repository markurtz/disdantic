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

"""Unit tests for the model module."""

from __future__ import annotations

import inspect
from collections.abc import Generator
from typing import Any, Generic, TypeVar

import pytest
from pydantic import BaseModel, ValidationError
from pytest_mock import MockerFixture

from disdantic.model import ReloadableBaseModel
from disdantic.settings import get_settings, reset_settings


# Helper Models for Testing
class SimpleChild(ReloadableBaseModel):
    """A simple child model for testing."""

    name: str
    value: int = 42


class ComplexChild(ReloadableBaseModel):
    """A complex child model for testing."""

    tag: str
    flag: bool = True


class LeafModel(ReloadableBaseModel):
    """A leaf model in a deep dependency hierarchy."""

    value: str


class MidModel(ReloadableBaseModel):
    """A middle model referencing the leaf model."""

    leaf: LeafModel


class RootModel(ReloadableBaseModel):
    """A root model referencing the middle model."""

    leaf: LeafModel
    mid: MidModel


class TargetModel(ReloadableBaseModel):
    """A target model referenced by other models."""

    name: str


class StringAnnotationModel(ReloadableBaseModel):
    """A model referencing TargetModel using a postponed string annotation."""

    target: TargetModel


class GenericAnnotationModel(ReloadableBaseModel):
    """A model referencing TargetModel in generic/union structures."""

    target_list: list[TargetModel]
    target_union: TargetModel | str
    target_dict: dict[str, TargetModel]


class BaseChildModel(ReloadableBaseModel):
    """A base child model for testing subclass matching."""


class SubChildModel(BaseChildModel):
    """A sub-child model inheriting from BaseChildModel."""


class SubclassAnnotationModel(ReloadableBaseModel):
    """A model referencing BaseChildModel."""

    child: BaseChildModel


class ExceptionSchemaModel(ReloadableBaseModel):
    """A model referencing TargetModel used to test exception handling."""

    target: TargetModel


TypeVarT = TypeVar("TypeVarT")


class GenericSubclassModel(BaseChildModel, Generic[TypeVarT]):
    """A generic model inheriting from BaseChildModel."""


class GenericSubclassAnnotationModel(ReloadableBaseModel):
    """A model referencing GenericSubclassModel with type arguments."""

    generic_child: GenericSubclassModel[int]


class PlainBase:
    """A plain base class for testing origin sub-classes."""


class PythonGeneric(PlainBase, Generic[TypeVarT]):
    """A standard generic Python class inheriting from PlainBase."""


class TestReloadableBaseModel:
    """Test suite for the ReloadableBaseModel class."""

    @pytest.fixture(autouse=True)
    def clean_settings(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state."""
        reset_settings()
        yield
        reset_settings()

    @pytest.fixture(
        params=[
            (SimpleChild, {"name": "simple", "value": 100}),
            (SimpleChild, {"name": "default"}),
            (ComplexChild, {"tag": "complex", "flag": False}),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> ReloadableBaseModel:
        """Fixture providing valid instances of ReloadableBaseModel subclasses."""
        model_cls, kwargs = request.param
        return model_cls(**kwargs)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify structural contracts and class/method signatures."""
        assert issubclass(ReloadableBaseModel, BaseModel)
        assert hasattr(ReloadableBaseModel, "reload_schema")
        assert hasattr(ReloadableBaseModel, "reload_parent_schemas")

        reload_schema_sig = inspect.signature(ReloadableBaseModel.reload_schema)
        assert "parents" in reload_schema_sig.parameters
        assert reload_schema_sig.parameters["parents"].default is True

        reload_parent_sig = inspect.signature(ReloadableBaseModel.reload_parent_schemas)
        assert len(reload_parent_sig.parameters) == 0 or (
            len(reload_parent_sig.parameters) == 1
            and "cls" in reload_parent_sig.parameters
        )

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: ReloadableBaseModel) -> None:
        """Verify proper instance initialization and state mapping."""
        assert isinstance(valid_instances, ReloadableBaseModel)
        if isinstance(valid_instances, SimpleChild):
            assert isinstance(valid_instances.name, str)
            assert isinstance(valid_instances.value, int)
        elif isinstance(valid_instances, ComplexChild):
            assert isinstance(valid_instances.tag, str)
            assert isinstance(valid_instances.flag, bool)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify initialization with invalid values raises ValidationError."""
        with pytest.raises(ValidationError):
            SimpleChild(name="valid", value="invalid")  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization missing required values raises ValidationError."""
        with pytest.raises(ValidationError):
            SimpleChild()  # type: ignore[call-arg] # ty: ignore[missing-argument]

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: ReloadableBaseModel) -> None:
        """Verify Pydantic serialization and validation pipelines."""
        dumped_data = valid_instances.model_dump()
        recreated_instance = valid_instances.__class__.model_validate(dumped_data)
        assert recreated_instance == valid_instances

    @pytest.mark.smoke
    def test_reload_schema(self, mocker: MockerFixture) -> None:
        """Verify reload_schema triggers model rebuild and parent reload."""
        rebuild_mock = mocker.patch.object(ReloadableBaseModel, "model_rebuild")
        parent_rebuild_mock = mocker.patch.object(
            ReloadableBaseModel, "reload_parent_schemas"
        )

        ReloadableBaseModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)
        parent_rebuild_mock.assert_called_once()

    @pytest.mark.sanity
    def test_reload_schema_disabled(self, mocker: MockerFixture) -> None:
        """Verify reload_schema is skipped when globally disabled."""
        get_settings().enable_schema_rebuilding = False
        rebuild_mock = mocker.patch.object(ReloadableBaseModel, "model_rebuild")
        parent_rebuild_mock = mocker.patch.object(
            ReloadableBaseModel, "reload_parent_schemas"
        )

        ReloadableBaseModel.reload_schema()

        rebuild_mock.assert_not_called()
        parent_rebuild_mock.assert_not_called()

    @pytest.mark.sanity
    def test_reload_schema_parent_propagation_disabled(
        self, mocker: MockerFixture
    ) -> None:
        """Verify parent rebuild propagation is skipped when disabled via settings."""
        get_settings().schema_rebuild_parents = False
        rebuild_mock = mocker.patch.object(ReloadableBaseModel, "model_rebuild")
        parent_rebuild_mock = mocker.patch.object(
            ReloadableBaseModel, "reload_parent_schemas"
        )

        ReloadableBaseModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)
        parent_rebuild_mock.assert_not_called()

    @pytest.mark.sanity
    def test_reload_schema_parents_argument_false(self, mocker: MockerFixture) -> None:
        """Verify parent rebuild propagation is skipped when parents
        argument is False.
        """
        rebuild_mock = mocker.patch.object(ReloadableBaseModel, "model_rebuild")
        parent_rebuild_mock = mocker.patch.object(
            ReloadableBaseModel, "reload_parent_schemas"
        )

        ReloadableBaseModel.reload_schema(parents=False)

        rebuild_mock.assert_called_once_with(force=True)
        parent_rebuild_mock.assert_not_called()

    @pytest.mark.sanity
    def test_reload_parent_schemas_direct(self, mocker: MockerFixture) -> None:
        """Verify parent rebuild is triggered directly by child reload."""
        rebuild_mock = mocker.patch.object(
            MidModel, "model_rebuild", wraps=MidModel.model_rebuild
        )

        LeafModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.regression
    def test_reload_parent_schemas_transitive(self, mocker: MockerFixture) -> None:
        """Verify rebuild cascades to multiple dependent models using the
        change loop.
        """
        mid_call_count = 0

        def mid_schema(*args: Any, **kwargs: Any) -> Any:
            nonlocal mid_call_count
            mid_call_count += 1
            if mid_call_count == 1:
                return {"title": "MidModelOld"}
            return {"title": "MidModelNew"}

        mocker.patch.object(MidModel, "model_json_schema", side_effect=mid_schema)

        mid_mock = mocker.patch.object(
            MidModel, "model_rebuild", wraps=MidModel.model_rebuild
        )
        root_mock = mocker.patch.object(
            RootModel, "model_rebuild", wraps=RootModel.model_rebuild
        )

        LeafModel.reload_schema(parents=True)

        # Since MidModel schema changes on the first rebuild, changed is True,
        # triggering a second iteration where both models are rebuilt again.
        assert mid_mock.call_count == 2
        assert root_mock.call_count == 2

    @pytest.mark.sanity
    def test_reload_parent_schemas_uses_type_string(
        self, mocker: MockerFixture
    ) -> None:
        """Verify rebuild cascades to string-annotated (postponed) fields."""
        rebuild_mock = mocker.patch.object(
            StringAnnotationModel,
            "model_rebuild",
            wraps=StringAnnotationModel.model_rebuild,
        )

        TargetModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.sanity
    def test_reload_parent_schemas_uses_type_generics(
        self, mocker: MockerFixture
    ) -> None:
        """Verify rebuild cascades to generic/union field annotations."""
        rebuild_mock = mocker.patch.object(
            GenericAnnotationModel,
            "model_rebuild",
            wraps=GenericAnnotationModel.model_rebuild,
        )

        TargetModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.regression
    def test_reload_parent_schemas_uses_type_subclass(
        self, mocker: MockerFixture
    ) -> None:
        """Verify rebuild cascades when field specifies base type of
        reloaded subclass.
        """
        rebuild_mock = mocker.patch.object(
            SubclassAnnotationModel,
            "model_rebuild",
            wraps=SubclassAnnotationModel.model_rebuild,
        )

        SubChildModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.regression
    def test_reload_parent_schemas_uses_type_generic_subclass(
        self, mocker: MockerFixture
    ) -> None:
        """Verify rebuild cascades to generic models whose origin is
        a subclass of target.
        """
        # Direct check to ensure coverage of origin type checks
        assert ReloadableBaseModel._uses_type(BaseChildModel, GenericSubclassModel[int])
        assert ReloadableBaseModel._uses_type(PlainBase, PythonGeneric[int])

        rebuild_mock = mocker.patch.object(
            GenericSubclassAnnotationModel,
            "model_rebuild",
            wraps=GenericSubclassAnnotationModel.model_rebuild,
        )

        BaseChildModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.regression
    def test_reload_parent_schemas_exception_handling_get_schema(
        self, mocker: MockerFixture
    ) -> None:
        """Verify exception during model_json_schema is handled gracefully."""
        mocker.patch.object(
            ExceptionSchemaModel,
            "model_json_schema",
            side_effect=ValueError("Test exception before rebuild"),
        )
        rebuild_mock = mocker.patch.object(
            ExceptionSchemaModel,
            "model_rebuild",
            wraps=ExceptionSchemaModel.model_rebuild,
        )

        TargetModel.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)

    @pytest.mark.regression
    def test_reload_parent_schemas_exception_handling_changed_schema(
        self, mocker: MockerFixture
    ) -> None:
        """Verify exception during post-rebuild schema comparison falls
        back to changed=True.
        """
        call_count = 0

        def side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "object"}
            raise ValueError("Test exception after rebuild")

        mocker.patch.object(
            ExceptionSchemaModel,
            "model_json_schema",
            side_effect=side_effect,
        )
        rebuild_mock = mocker.patch.object(
            ExceptionSchemaModel,
            "model_rebuild",
            wraps=ExceptionSchemaModel.model_rebuild,
        )

        TargetModel.reload_schema(parents=True)

        # Exception fallback sets changed=True, causing a second iteration.
        assert rebuild_mock.call_count == 2
