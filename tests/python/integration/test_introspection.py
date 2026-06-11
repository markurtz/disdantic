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

from __future__ import annotations

import inspect
import json
import threading
from collections.abc import Generator
from typing import Any, ClassVar, Literal

import pytest
from pydantic import Field, ValidationError

import disdantic.introspection
from disdantic.introspection import PRIMITIVE_TYPES, InfoMixin
from disdantic.loading import LazyProxy
from disdantic.model import ReloadableBaseModel
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import get_settings, reset_settings


class IntegrationModel(ReloadableBaseModel, InfoMixin):
    """Integration test Pydantic model incorporating InfoMixin."""

    name: str
    age: int
    description: str | None = None


class NestedIntegrationModel(ReloadableBaseModel, InfoMixin):
    """Pydantic model containing nested models and collections."""

    title: str
    child: IntegrationModel
    children_list: list[IntegrationModel] = Field(default_factory=list)


class CyclicIntegrationModel(ReloadableBaseModel, InfoMixin):
    """Pydantic model with circular reference possibilities."""

    name: str
    nested_child: CyclicIntegrationModel | None = None
    sibling_list: list[CyclicIntegrationModel] = Field(default_factory=list)

    def __repr__(self) -> str:
        return f"CyclicIntegrationModel(name={self.name!r})"


# Rebuild schemas to register field connections
IntegrationModel.model_rebuild()
NestedIntegrationModel.model_rebuild()
CyclicIntegrationModel.model_rebuild()


@pytest.mark.smoke
def test_primitive_types() -> None:
    """Verify public module-level variables and primitive type compatibility."""
    assert isinstance(PRIMITIVE_TYPES, tuple)
    assert len(PRIMITIVE_TYPES) == 5
    assert str in PRIMITIVE_TYPES
    assert int in PRIMITIVE_TYPES
    assert float in PRIMITIVE_TYPES
    assert bool in PRIMITIVE_TYPES
    assert type(None) in PRIMITIVE_TYPES


class TestInfoMixin:
    """Integration test suite for validating InfoMixin structural behavior."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.fixture(
        params=[
            "simple_pydantic",
            "nested_pydantic",
            "circular_pydantic",
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> InfoMixin:
        """Fixture supplying variations of the integrated classes."""
        param_value = request.param
        if param_value == "simple_pydantic":
            return IntegrationModel(
                name="test_name", age=25, description="test_description"
            )
        elif param_value == "nested_pydantic":
            child_model = IntegrationModel(name="child", age=10)
            return NestedIntegrationModel(
                title="parent",
                child=child_model,
                children_list=[child_model],
            )
        elif param_value == "circular_pydantic":
            parent_node = CyclicIntegrationModel(name="parent_node")
            child_node = CyclicIntegrationModel(
                name="child_node", nested_child=parent_node
            )
            parent_node.nested_child = child_node
            parent_node.sibling_list = [child_node]
            return parent_node
        raise ValueError(f"Unknown parameter variation: {param_value}")

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate structural contracts across integrated boundaries."""
        # 1. Verify inheritance lineages
        assert issubclass(IntegrationModel, InfoMixin)
        assert issubclass(IntegrationModel, ReloadableBaseModel)
        assert issubclass(NestedIntegrationModel, InfoMixin)
        assert issubclass(CyclicIntegrationModel, InfoMixin)

        # 2. Check public method exposures on InfoMixin and class vars
        assert hasattr(InfoMixin, "extract_from_obj")
        assert hasattr(InfoMixin, "info")
        assert isinstance(InfoMixin.info, property)

        # 3. Verify method signatures across collaborating classes
        extract_signature = inspect.signature(InfoMixin.extract_from_obj)
        assert "obj" in extract_signature.parameters
        assert "visited" in extract_signature.parameters

        # Check that parameter names are valid and match our expectations
        assert extract_signature.parameters["obj"].name == "obj"
        assert extract_signature.parameters["visited"].name == "visited"

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: InfoMixin) -> None:
        """Verify integrated component assembly and initialization properties."""
        assert isinstance(valid_instances, InfoMixin)
        if isinstance(valid_instances, IntegrationModel):
            assert valid_instances.name == "test_name"
            assert valid_instances.age == 25
        elif isinstance(valid_instances, NestedIntegrationModel):
            assert valid_instances.title == "parent"
            assert isinstance(valid_instances.child, IntegrationModel)
        elif isinstance(valid_instances, CyclicIntegrationModel):
            assert valid_instances.name == "parent_node"
            assert isinstance(valid_instances.nested_child, CyclicIntegrationModel)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Test component assembly failures with invalid initialization values."""
        # Verification of Pydantic model validation on IntegrationModel
        with pytest.raises(ValidationError):
            IntegrationModel(name="test", age="not_an_int")  # type: ignore

        # Verification of direct mixin instantiation failure when passing arguments
        with pytest.raises(TypeError):
            InfoMixin(dummy_argument="invalid")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Test component assembly failures when required fields are missing."""
        # Omission of required parameters for IntegrationModel
        with pytest.raises(ValidationError):
            IntegrationModel(name="test")  # type: ignore

        # Direct instantiation of InfoMixin alone (no parameters) succeeds
        mixin_instance = InfoMixin()
        assert isinstance(mixin_instance, InfoMixin)

    @pytest.mark.smoke
    def test_info(self, valid_instances: InfoMixin) -> None:
        """Verify the info property coordinates object structures dynamically."""
        info_data = valid_instances.info
        assert isinstance(info_data, dict)
        assert info_data["type"] == valid_instances.__class__.__name__
        assert info_data["module"] == "tests.python.integration.test_introspection"
        assert "attributes" in info_data

    @pytest.mark.sanity
    def test_extract_from_obj(self) -> None:
        """Validate extraction orchestration with nested custom collections."""
        model_instance = IntegrationModel(name="Alice", age=30)
        extracted = InfoMixin.extract_from_obj(model_instance)
        assert extracted["type"] == "IntegrationModel"
        assert extracted["attributes"]["name"] == "Alice"
        assert extracted["attributes"]["age"] == 30

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: InfoMixin) -> None:
        """Verify model_dump and model_validate pipelines across boundaries."""
        if isinstance(valid_instances, ReloadableBaseModel) and not isinstance(
            valid_instances, CyclicIntegrationModel
        ):
            dumped_data = valid_instances.model_dump()
            assert isinstance(dumped_data, dict)

            revalidated = valid_instances.__class__.model_validate(dumped_data)
            assert isinstance(revalidated, valid_instances.__class__)
            for field_name in valid_instances.model_fields:
                assert getattr(revalidated, field_name) == getattr(
                    valid_instances, field_name
                )

    @pytest.mark.regression
    def test_registry_and_factory_integration(self) -> None:
        """Verify dynamic resolution and schema rebuilds for registered subclasses."""

        class RegisteredBase(PydanticClassRegistryMixin, InfoMixin):
            """Base model in a polymorphic class registry."""

            schema_discriminator: ClassVar[str] = "msg_type"

        @RegisteredBase.register("text_type")
        class RegisteredText(RegisteredBase):
            """Registered subclass specializing in text representation."""

            msg_type: Literal["text_type"] = "text_type"
            text_value: str

        @RegisteredBase.register("image_type")
        class RegisteredImage(RegisteredBase):
            """Registered subclass specializing in image representation."""

            msg_type: Literal["image_type"] = "image_type"
            image_url: str

        try:
            # 1. Assert registry populates expected classes
            registered_types = RegisteredBase.registered_classes()
            assert RegisteredText in registered_types
            assert RegisteredImage in registered_types

            # 2. Assert case-insensitive lookups and initialization factory
            text_payload = {"msg_type": "TEXT_TYPE", "text_value": "hello"}
            resolved_text = RegisteredBase.model_validate(text_payload)
            assert isinstance(resolved_text, RegisteredText)
            assert resolved_text.text_value == "hello"

            # 3. Validate introspection of resolved factory instances
            info_data = resolved_text.info
            assert info_data["type"] == "RegisteredText"
            assert info_data["attributes"]["text_value"] == "hello"
            assert info_data["attributes"]["msg_type"] == "text_type"

        finally:
            RegisteredBase.clear_registry()

    @pytest.mark.regression
    def test_settings_integration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify introspection responds dynamically to settings modifications."""
        model_instance = IntegrationModel(
            name="test_name", age=25, description="test_description"
        )

        # 1. Verify default exclusion behavior (defaults to ["info"])
        assert "name" in model_instance.info["attributes"]
        assert "age" in model_instance.info["attributes"]
        assert "description" in model_instance.info["attributes"]

        # 2. Modify settings dynamically via get_settings()
        get_settings().info_exclude_keys = ["info", "age", "description"]
        try:
            info_attributes = model_instance.info["attributes"]
            assert "name" in info_attributes
            assert "age" not in info_attributes
            assert "description" not in info_attributes

            # 3. Verify env variable overrides take precedence
            monkeypatch.setenv("DISDANTIC__INFO_EXCLUDE_KEYS", '["info", "name"]')
            reset_settings()

            new_info_attributes = model_instance.info["attributes"]
            assert "name" not in new_info_attributes
            assert "age" in new_info_attributes
            assert "description" in new_info_attributes

        finally:
            reset_settings()

    @pytest.mark.regression
    def test_lazy_proxy_integration(self) -> None:
        """Verify introspection handles LazyProxy containers and circular references."""
        # 1. Setup a lazy proxy wrapping a model instance
        resolved_flag = False

        def model_factory() -> IntegrationModel:
            nonlocal resolved_flag
            resolved_flag = True
            return IntegrationModel(name="lazy_model", age=99)

        lazy_proxy = LazyProxy(model_factory)

        # Assert proxy is not resolved yet
        assert resolved_flag is False

        # 2. Introspect an object containing the lazy proxy
        wrapper_dict = {"lazy_field": lazy_proxy}
        extracted = InfoMixin._sanitize_value(wrapper_dict)

        # Assert introspection triggered proxy resolution
        assert resolved_flag is True
        assert isinstance(extracted, dict)
        assert extracted["lazy_field"]["type"] == "IntegrationModel"
        assert extracted["lazy_field"]["attributes"]["name"] == "lazy_model"

        # 3. Verify circular references containing proxies are handled safely
        class CircularProxyHelper(InfoMixin):
            """Helper class to check circular proxy resolution without validation."""

            def __init__(self, name_val: str) -> None:
                self.name_val = name_val
                self.nested: Any = None

        parent_node = CircularProxyHelper("parent")
        lazy_proxy_circular = LazyProxy(lambda: parent_node)
        child_node = CircularProxyHelper("child")
        child_node.nested = lazy_proxy_circular
        parent_node.nested = child_node

        sanitized_circular = InfoMixin.extract_from_obj(child_node)
        assert isinstance(sanitized_circular, dict)
        parent_info = sanitized_circular["attributes"]["nested"]
        assert parent_info["type"] == "CircularProxyHelper"
        circular_ref = parent_info["attributes"]["nested"]
        assert circular_ref.startswith("<CircularReference:")

    @pytest.mark.regression
    def test_thread_safety_introspection(self) -> None:
        """Verify concurrent execution of introspection on cyclic models."""
        # 1. Setup a complex shared circular model
        parent_node = CyclicIntegrationModel(name="thread_shared_root")
        child_node = CyclicIntegrationModel(
            name="thread_shared_child", nested_child=parent_node
        )
        parent_node.nested_child = child_node
        parent_node.sibling_list = [child_node]

        thread_count = 10
        iterations = 50
        errors_list: list[Exception] = []

        def worker() -> None:
            try:
                for _iteration_index in range(iterations):
                    info_data = parent_node.info
                    assert isinstance(info_data, dict)
                    assert info_data["attributes"]["name"] == "thread_shared_root"

                    child_info = info_data["attributes"]["nested_child"]
                    assert child_info["attributes"]["name"] == "thread_shared_child"

                    circular_ref = child_info["attributes"]["nested_child"]
                    assert circular_ref.startswith("<CircularReference:")
            except Exception as error:  # noqa: BLE001
                errors_list.append(error)

        threads = []
        for _thread_index in range(thread_count):
            thread_instance = threading.Thread(target=worker)
            threads.append(thread_instance)
            thread_instance.start()

        for thread_instance in threads:
            thread_instance.join()

        assert not errors_list, f"Concurrency errors detected: {errors_list}"

    @pytest.mark.smoke
    def test_info_json(self, valid_instances: InfoMixin) -> None:
        """Verify the info_json method exports correctly serialized JSON."""
        json_str = valid_instances.info_json(indent=4, sort_keys=True)
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["type"] == valid_instances.__class__.__name__
        assert "attributes" in data

    @pytest.mark.smoke
    def test_info_yaml(self, valid_instances: InfoMixin) -> None:
        """Verify the info_yaml method exports correctly serialized YAML."""
        yaml_str = valid_instances.info_yaml(indent=2, sort_keys=True)
        assert isinstance(yaml_str, str)
        assert valid_instances.__class__.__name__ in yaml_str

    @pytest.mark.regression
    def test_info_yaml_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify the pure-Python fallback YAML writer.

        This runs when yaml (PyYAML) is unavailable.
        """
        monkeypatch.setattr(disdantic.introspection, "yaml", None)

        class FallbackTestModel(InfoMixin):
            def __init__(self) -> None:
                self.empty_dict: dict[str, Any] = {}
                self.empty_seq: list[Any] = []
                self.none_val = None
                self.bool_true = True
                self.bool_false = False
                self.simple_str = "hello"
                self.special_str = "key: value"
                self.nested_dict = {"key_a": 1, "key_b": [2, 3]}
                self.nested_list = [{"key_x": 10}, 20]

        model = FallbackTestModel()
        yaml_str = model.info_yaml(indent=2, sort_keys=True)
        assert isinstance(yaml_str, str)

        assert "empty_dict: {}" in yaml_str
        assert "empty_seq: []" in yaml_str
        assert "none_val: null" in yaml_str
        assert "bool_true: true" in yaml_str
        assert "bool_false: false" in yaml_str
        assert 'simple_str: "hello"' in yaml_str
        assert 'special_str: "key: value"' in yaml_str
        assert "nested_dict:" in yaml_str
        assert "nested_list:" in yaml_str
        assert yaml_str.endswith("\n")

    @pytest.mark.regression
    def test_custom_info_hook(self) -> None:
        """Verify the introspection detects and honors custom info hook variations."""

        class CustomCallableInfo:
            def info(self) -> dict[str, Any]:
                return {"custom": "callable_hook"}

        class CustomDictInfo:
            def __init__(self) -> None:
                self.info = {"custom": "dict_hook"}

        class CustomErrorThrowingInfo:
            @property
            def info(self) -> dict[str, Any]:
                raise ValueError("Introspection hook error")

        extracted_callable = InfoMixin.extract_from_obj(CustomCallableInfo())
        assert extracted_callable == {"custom": "callable_hook"}

        extracted_dict = InfoMixin.extract_from_obj(CustomDictInfo())
        assert extracted_dict == {"custom": "dict_hook"}

        extracted_error = InfoMixin.extract_from_obj(CustomErrorThrowingInfo())
        assert extracted_error["type"] == "CustomErrorThrowingInfo"
        assert "attributes" in extracted_error

        # Nested custom error-throwing info to trigger exception block
        # in _sanitize_custom
        class NestedCustomErrorContainer(InfoMixin):
            def __init__(self) -> None:
                self.nested = CustomErrorThrowingInfo()

        model_with_error = NestedCustomErrorContainer()
        info_data_error = model_with_error.info
        assert "CustomErrorThrowingInfo" in info_data_error["attributes"]["nested"]

        # Nested custom callable hook to cover line 275
        class NestedCustomCallableContainer(InfoMixin):
            def __init__(self) -> None:
                self.nested = CustomCallableInfo()

        model_with_callable = NestedCustomCallableContainer()
        info_data_callable = model_with_callable.info
        assert info_data_callable["attributes"]["nested"] == {"custom": "callable_hook"}

    @pytest.mark.regression
    def test_property_extraction_error(self) -> None:
        """Verify that property extraction errors are caught and sanitized."""

        class ErrorPropertyModel(InfoMixin):
            @property
            def bad_property(self) -> str:
                raise RuntimeError("Failed to compute property")

        model = ErrorPropertyModel()
        info_data = model.info
        assert "bad_property" in info_data["attributes"]
        assert "Extraction Error" in info_data["attributes"]["bad_property"]
        assert "Failed to compute property" in info_data["attributes"]["bad_property"]

    @pytest.mark.regression
    def test_type_and_class_serialization(self) -> None:
        """Verify that passing type objects or classes resolves to representation."""

        class TypeReferenceModel(InfoMixin):
            def __init__(self) -> None:
                self.class_types = [int, float]
                self.custom_types = {"model": IntegrationModel}

        model = TypeReferenceModel()
        info_data = model.info
        assert info_data["attributes"]["class_types"] == [
            "<class 'int'>",
            "<class 'float'>",
        ]
        assert "IntegrationModel" in info_data["attributes"]["custom_types"]["model"]

    @pytest.mark.regression
    def test_prepare_for_serialization_edges(self) -> None:
        """Verify edge cases of prepare_for_serialization.

        This includes circular lists/dicts and custom objects.
        """
        # 1. Circular dict
        circular_dict: dict[str, Any] = {}
        circular_dict["self"] = circular_dict
        serialized_dict = InfoMixin._prepare_for_serialization(circular_dict)
        assert isinstance(serialized_dict, dict)
        assert "CircularReference" in serialized_dict["self"]

        # 2. Circular list
        circular_list: list[Any] = []
        circular_list.append(circular_list)
        serialized_list = InfoMixin._prepare_for_serialization(circular_list)
        assert isinstance(serialized_list, list)
        assert "CircularReference" in serialized_list[0]

        # 3. Custom non-container object fallback
        class DummyObject:
            def __str__(self) -> str:
                return "dummy_repr"

        serialized_dummy = InfoMixin._prepare_for_serialization(DummyObject())
        assert serialized_dummy == "dummy_repr"
