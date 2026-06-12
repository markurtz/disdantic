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

"""Integration tests for the model module."""

from __future__ import annotations

import inspect
import types
from collections.abc import Generator
from typing import Any, Generic, TypeVar

import pytest
from pydantic import BaseModel, ValidationError
from pytest_mock import MockerFixture

import disdantic.model as model_module
from disdantic.model import ReloadableBaseModel
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import get_settings, reset_settings


class IntegratedChild(ReloadableBaseModel):
    """A simple child model for integration testing."""

    name: str
    value: int = 42


class IntegratedParent(ReloadableBaseModel):
    """A parent model referencing IntegratedChild."""

    child: IntegratedChild
    tag: str


class IntegratedGrandparent(ReloadableBaseModel):
    """A grandparent model referencing IntegratedParent."""

    parent: IntegratedParent
    flag: bool = True


class BaseMsg(PydanticClassRegistryMixin):
    """A class registry base type for integration testing."""


class OuterModel(ReloadableBaseModel):
    """An outer model referencing the polymorphic BaseMsg registry."""

    msg: BaseMsg


TypeVarT = TypeVar("TypeVarT")


class GenericBase(ReloadableBaseModel, Generic[TypeVarT]):
    """A generic base class to test origin subclass checking."""


class GenericChildModel(ReloadableBaseModel):
    """A model referencing GenericBase with type arguments.

    Used to trigger line 166 coverage.
    """

    child: GenericBase[int]


class ExceptionPostRebuildModel(ReloadableBaseModel):
    """A model to test exception handling post-rebuild in schema comparison."""

    msg: BaseMsg


@pytest.mark.smoke
def test_model_exports() -> None:
    """Validate public variables, constants, and module-level exports."""
    assert hasattr(model_module, "__all__")
    expected_exports = ["ReloadableBaseModel"]
    assert sorted(model_module.__all__) == sorted(expected_exports)


class TestReloadableBaseModel:
    """Integration test suite for ReloadableBaseModel."""

    @pytest.mark.sanity
    def test_interface_signature_validation(self) -> None:
        """Validate structural contracts across integrated boundaries."""
        # Check inheritance lineage
        assert issubclass(ReloadableBaseModel, BaseModel)

        # Check method signatures and parameter names
        reload_schema_sig = inspect.signature(ReloadableBaseModel.reload_schema)
        assert "parents" in reload_schema_sig.parameters
        assert reload_schema_sig.parameters["parents"].default is True

        reload_parent_sig = inspect.signature(ReloadableBaseModel.reload_parent_schemas)
        assert len(reload_parent_sig.parameters) == 0 or (
            len(reload_parent_sig.parameters) == 1
            and "cls" in reload_parent_sig.parameters
        )

    @pytest.fixture(autouse=True)
    def clean_settings_and_registry(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state and registry setup."""
        reset_settings()
        BaseMsg.clear_registry()
        yield
        reset_settings()
        BaseMsg.clear_registry()

    @pytest.fixture(
        params=[
            (IntegratedChild, {"name": "child_only", "value": 100}),
            (
                IntegratedParent,
                {"child": IntegratedChild(name="nested"), "tag": "parent_tag"},
            ),
            (
                IntegratedGrandparent,
                {
                    "parent": IntegratedParent(
                        child=IntegratedChild(name="deep"), tag="mid"
                    ),
                    "flag": False,
                },
            ),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> ReloadableBaseModel:
        """Fixture supplying properly initialized ReloadableBaseModel instances."""
        model_cls, kwargs = request.param
        return model_cls(**kwargs)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: ReloadableBaseModel) -> None:
        """Verify proper instance initialization and state mapping."""
        assert isinstance(valid_instances, ReloadableBaseModel)
        if isinstance(valid_instances, IntegratedChild):
            assert valid_instances.name == "child_only"
            assert valid_instances.value == 100
        elif isinstance(valid_instances, IntegratedParent):
            assert valid_instances.child.name == "nested"
            assert valid_instances.tag == "parent_tag"
        elif isinstance(valid_instances, IntegratedGrandparent):
            assert valid_instances.parent.child.name == "deep"
            assert valid_instances.flag is False

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify initialization with invalid values raises ValidationError."""
        with pytest.raises(ValidationError):
            IntegratedChild(
                name="valid",
                value="invalid_int",  # ty: ignore[invalid-argument-type]
            )  # type: ignore[arg-type]

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization missing required values raises ValidationError."""
        with pytest.raises(ValidationError):
            IntegratedChild()  # type: ignore[call-arg]  # ty: ignore[missing-argument]

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: ReloadableBaseModel) -> None:
        """Verify Pydantic serialization and validation pipelines."""
        dumped_data = valid_instances.model_dump()
        recreated_instance = valid_instances.__class__.model_validate(dumped_data)
        assert recreated_instance == valid_instances

    @pytest.mark.smoke
    def test_reload_schema(self, mocker: MockerFixture) -> None:
        """Verify reload_schema triggers model rebuild and parent reload cascade."""
        rebuild_mock = mocker.patch.object(
            IntegratedChild, "model_rebuild", wraps=IntegratedChild.model_rebuild
        )
        parent_rebuild_mock = mocker.patch.object(
            IntegratedChild,
            "reload_parent_schemas",
            wraps=IntegratedChild.reload_parent_schemas,
        )

        IntegratedChild.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)
        parent_rebuild_mock.assert_called_once()

        # Trigger generic model reloading to cover line 166 (origin subclass resolution)
        alias = types.GenericAlias(GenericBase, (int,))
        assert ReloadableBaseModel._references_type(GenericBase, alias) is True
        generic_rebuild_mock = mocker.patch.object(
            GenericChildModel, "model_rebuild", wraps=GenericChildModel.model_rebuild
        )
        GenericBase.reload_schema(parents=True)
        assert generic_rebuild_mock.call_count >= 1

    @pytest.mark.sanity
    def test_reload_schema_disabled(self, mocker: MockerFixture) -> None:
        """Verify reload_schema is skipped when globally disabled in settings."""
        settings = get_settings()
        settings.enable_schema_rebuilding = False

        rebuild_mock = mocker.patch.object(IntegratedChild, "model_rebuild")
        parent_rebuild_mock = mocker.patch.object(
            IntegratedChild, "reload_parent_schemas"
        )

        IntegratedChild.reload_schema(parents=True)

        rebuild_mock.assert_not_called()
        parent_rebuild_mock.assert_not_called()

    @pytest.mark.sanity
    def test_reload_schema_parents_propagation_disabled(
        self, mocker: MockerFixture
    ) -> None:
        """Verify parent reload is skipped when disabled via settings or argument."""
        # 1. Disabled via settings
        settings = get_settings()
        settings.schema_rebuild_parents = False

        rebuild_mock = mocker.patch.object(
            IntegratedChild, "model_rebuild", wraps=IntegratedChild.model_rebuild
        )
        parent_rebuild_mock = mocker.patch.object(
            IntegratedChild, "reload_parent_schemas"
        )

        IntegratedChild.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)
        parent_rebuild_mock.assert_not_called()

        # Reset mocks
        rebuild_mock.reset_mock()
        parent_rebuild_mock.reset_mock()

        # 2. Disabled via parameter
        settings.schema_rebuild_parents = True
        IntegratedChild.reload_schema(parents=False)

        rebuild_mock.assert_called_once_with(force=True)
        parent_rebuild_mock.assert_not_called()

    @pytest.mark.regression
    def test_reload_parent_schemas(self) -> None:
        """Verify subclass registration dynamically updates parent models' schemas."""
        # Originally, BaseMsg has no subclasses registered
        # OuterModel is clean
        schema_before = OuterModel.model_json_schema()
        assert "$defs" not in schema_before or "TextMsg" not in schema_before.get(
            "$defs", {}
        )

        # Let's register a type
        @BaseMsg.register("text")
        class TextMsg(BaseMsg):
            text: str

        # Registration should cascade-rebuild OuterModel!
        schema_after = OuterModel.model_json_schema()
        assert "$defs" in schema_after
        assert "TextMsg" in schema_after["$defs"]

        # Validate message parsing works via OuterModel
        payload = {"msg": {"model_type": "text", "text": "hello integration"}}
        parsed = OuterModel.model_validate(payload)
        assert isinstance(parsed.msg, TextMsg)
        assert parsed.msg.text == "hello integration"

        # Let's register another type
        @BaseMsg.register("image")
        class ImageMsg(BaseMsg):
            url: str

        # Schema should now contain both TextMsg and ImageMsg
        schema_final = OuterModel.model_json_schema()
        assert "ImageMsg" in schema_final["$defs"]

        # Validate both types work
        image_payload = {
            "msg": {
                "model_type": "image",
                "url": "http://example.com/img.png",
            }
        }
        image_parsed = OuterModel.model_validate(image_payload)
        assert isinstance(image_parsed.msg, ImageMsg)
        assert image_parsed.msg.url == "http://example.com/img.png"

    @pytest.mark.regression
    def test_registry_integration(self) -> None:
        """Verify registry key matching and case-insensitivity.

        Also verify error scenarios.
        """

        @BaseMsg.register("text")
        class TextMsg(BaseMsg):
            text: str

        # 1. Verify case-insensitivity on model_validate lookahead
        payload_upper = {"msg": {"model_type": "TEXT", "text": "casing test"}}
        parsed_upper = OuterModel.model_validate(payload_upper)
        assert isinstance(parsed_upper.msg, TextMsg)
        assert parsed_upper.msg.text == "casing test"

        # 2. Verify DiscriminatorNotFoundError is wrapped in ValidationError
        payload_invalid = {"msg": {"model_type": "unknown_type", "text": "fail"}}
        with pytest.raises(ValidationError) as exc_info:
            OuterModel.model_validate(payload_invalid)
        assert "Failed to resolve polymorphic configuration layer" in str(
            exc_info.value
        )
        assert "unknown_type" in str(exc_info.value)

    @pytest.mark.regression
    def test_reload_parent_schemas_exception_handling(
        self, mocker: MockerFixture
    ) -> None:
        """Verify exception during model_json_schema or rebuild is caught gracefully."""

        # Register a type
        @BaseMsg.register("text")
        class TextMsg(BaseMsg):
            text: str

        # Mock OuterModel.model_json_schema to throw error, verifying exception block
        mocker.patch.object(
            OuterModel,
            "model_json_schema",
            side_effect=ValueError("Simulated schema failure"),
        )

        rebuild_mock = mocker.patch.object(
            OuterModel, "model_rebuild", wraps=OuterModel.model_rebuild
        )

        # Setup side effect for post-rebuild schema comparison exception
        # (lines 146-148 coverage)
        post_rebuild_calls = 0

        def post_rebuild_schema_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal post_rebuild_calls
            post_rebuild_calls += 1
            if post_rebuild_calls == 1:
                return {"type": "object"}
            raise ValueError("Simulated post-rebuild schema failure")

        # Avoid direct name reference mapping error if any
        mocker.patch.object(
            ExceptionPostRebuildModel,
            "model_json_schema",
            side_effect=post_rebuild_schema_side_effect,
        )

        post_rebuild_mock = mocker.patch.object(
            ExceptionPostRebuildModel,
            "model_rebuild",
            wraps=ExceptionPostRebuildModel.model_rebuild,
        )

        # Triggering a rebuild on BaseMsg should still complete and rebuild
        # both OuterModel and ExceptionPostRebuildModel
        BaseMsg.reload_schema(parents=True)

        assert rebuild_mock.call_count >= 1
        rebuild_mock.assert_called_with(force=True)

        assert post_rebuild_mock.call_count >= 1
        post_rebuild_mock.assert_called_with(force=True)

    @pytest.mark.sanity
    def test_reload_schema_no_dependents(self) -> None:
        """Verify reload_schema returns early when there are no dependents.

        Checks behavior when there are no dependent parent models.
        """

        class StandaloneModel(ReloadableBaseModel):
            value: int

        # Rebuilding StandaloneModel should succeed and return early in
        # _rebuild_dependents because no other active subclasses of
        # BaseModel reference it.
        StandaloneModel.reload_schema(parents=True)

    @pytest.mark.regression
    def test_reload_schema_cyclic_dependencies(self) -> None:
        """Verify cyclic dependencies are handled gracefully.

        Uses alphabetical fallback when sorting cycle.
        """

        class CycleTarget(ReloadableBaseModel):
            value: int

        # We must define the cycle carefully.
        # Since CycleA and CycleB reference each other, we can use forward refs.
        class CycleA(ReloadableBaseModel):
            target: CycleTarget
            sibling: CycleB | None = None

        class CycleB(ReloadableBaseModel):
            sibling: CycleA | None = None

        # Rebuild to resolve forward references
        CycleA.model_rebuild(force=True)
        CycleB.model_rebuild(force=True)

        # Triggering reload on CycleTarget should trigger a rebuild of
        # CycleA and CycleB, resolving the cycle via alphabetical fallback
        # (CycleA, CycleB).
        CycleTarget.reload_schema(parents=True)
