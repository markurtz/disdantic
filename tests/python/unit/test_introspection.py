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

import importlib
import inspect
import json
from typing import Any
from unittest.mock import patch

import pytest
import yaml

import disdantic.introspection
from disdantic.introspection import PRIMITIVE_TYPES, InfoMixin
from disdantic.loading import LazyProxy
from disdantic.settings import get_settings, reset_settings


class SimpleModel(InfoMixin):
    """Simple model helper class inheriting from InfoMixin."""

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
        self._private_val = "secret"

    def some_method(self) -> str:
        return "method"


class ModelWithContainers(InfoMixin):
    """Model helper class containing various containers."""

    def __init__(self) -> None:
        self.items = [1, 2, "three"]
        self.mapping = {"key_a": 1, "key_b": [2, 3]}
        self.nested = SimpleModel("nested", 30)


class ModelWithCircularContainers(InfoMixin):
    """Model helper class with circular references inside list containers."""

    def __init__(self) -> None:
        self.elements: list[Any] = [1, 2]
        self.elements.append(self.elements)


class ModelWithSelfReference(InfoMixin):
    """Model helper class containing a self-reference attribute."""

    def __init__(self) -> None:
        self.name = "self-ref"
        self.myself: ModelWithSelfReference | None = None


class ModelWithCrossReference(InfoMixin):
    """Model helper class with circular references across different instances."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.other: ModelWithCrossReference | None = None


class ModelWithExtractionError(InfoMixin):
    """Model helper class that raises an error when property is accessed."""

    @property
    def broken(self) -> str:
        raise ValueError("broken property")


class ModelWithCustomInfo(InfoMixin):
    """Model helper class with custom non-callable info property."""

    def __init__(self) -> None:
        self.value_attr = "value"

    @property
    def info(self) -> dict[str, Any]:
        return {"custom": True, "value_attr": self.value_attr}


class ModelWithCustomCallableInfo:
    """Class without InfoMixin base but defining a callable info method."""

    def info(self) -> dict[str, Any]:
        return {"callable_custom": True}


class ModelWithCustomCallableInfoRaising:
    """Class without InfoMixin base raising exception in callable info."""

    def info(self) -> dict[str, Any]:
        raise ValueError("custom info error")


class ModelWithCustomNested(InfoMixin):
    """Model helper class nesting custom info objects."""

    def __init__(self) -> None:
        self.custom_callable = ModelWithCustomCallableInfo()
        self.custom_property = ModelWithCustomInfo()
        self.custom_raising = ModelWithCustomCallableInfoRaising()


class CustomDummyWithoutInfo:
    """A custom class that does not have an info attribute/property."""

    def __repr__(self) -> str:
        return "<CustomDummyWithoutInfo>"


class ModelWithLazyProxy(InfoMixin):
    """Model helper class containing a LazyProxy attribute."""

    def __init__(self, value: Any) -> None:
        self.lazy_val = LazyProxy(lambda: value)


class ModelWithTypeValue(InfoMixin):
    """Model helper class containing a class type attribute."""

    def __init__(self) -> None:
        self.type_val = [int]


class ModelWithCustomNoInfo(InfoMixin):
    """Model helper class containing a custom object without an info attribute."""

    def __init__(self) -> None:
        self.dummy = CustomDummyWithoutInfo()


class TestInfoMixin:
    """Comprehensive unit tests for the InfoMixin class."""

    @pytest.fixture(
        params=[
            {"name": "Alice", "age": 25},
            {"name": "Bob", "age": 30},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> SimpleModel:
        """Fixture supplying instantiated valid variations of SimpleModel."""
        return SimpleModel(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify structural contracts and exact signatures of InfoMixin."""
        # Inheritance check
        assert issubclass(SimpleModel, InfoMixin)

        # Public properties and methods presence
        assert hasattr(InfoMixin, "extract_from_obj")
        assert hasattr(InfoMixin, "info")

        # Property checks
        assert isinstance(InfoMixin.info, property)

        # Method signature check
        extract_sig = inspect.signature(InfoMixin.extract_from_obj)
        assert "obj" in extract_sig.parameters
        assert "visited" in extract_sig.parameters

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: SimpleModel) -> None:
        """Verify correct initialization and state mapping from the fixture."""
        assert valid_instances.name in {"Alice", "Bob"}
        assert valid_instances.age in {25, 30}
        assert valid_instances._private_val == "secret"

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify direct instantiation failure when parameters are provided."""
        with pytest.raises(TypeError):
            InfoMixin(dummy_param="value")  # type: ignore[call-arg]  # ty: ignore[unknown-argument]

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify instantiation succeeds with no params and fails with missing."""
        instance = InfoMixin()
        assert isinstance(instance, InfoMixin)

        with pytest.raises(TypeError):
            SimpleModel(name="OnlyName")  # type: ignore[call-arg]  # ty: ignore[missing-argument]

    @pytest.mark.smoke
    def test_info(self, valid_instances: SimpleModel) -> None:
        """Verify the info property extracts dynamic self-introspection data."""
        # Setup (valid_instances fixture is the setup)
        # Mock (not needed for local properties)
        # Invoke
        info_data = valid_instances.info

        # Assert / Teardown
        assert isinstance(info_data, dict)
        assert info_data["str"] == str(valid_instances)
        assert info_data["type"] == "SimpleModel"
        assert info_data["module"] == "tests.python.unit.test_introspection"
        assert info_data["attributes"] == {
            "name": valid_instances.name,
            "age": valid_instances.age,
        }

    @pytest.mark.smoke
    def test_extract_from_obj(self) -> None:
        """Verify the extract_from_obj class method parses public attributes."""
        # Setup
        model = SimpleModel("Charlie", 40)

        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        assert info_data["str"] == str(model)
        assert info_data["type"] == "SimpleModel"
        assert info_data["module"] == "tests.python.unit.test_introspection"
        assert info_data["attributes"] == {
            "name": "Charlie",
            "age": 40,
        }

    @pytest.mark.sanity
    def test_extract_from_obj_invalid(self) -> None:
        """Verify fallback behavior when object parsing encounters exceptions."""
        # Setup: object with a property that raises Exception
        model = ModelWithExtractionError()

        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        error_msg = info_data["attributes"]["broken"]
        assert error_msg.startswith("<Extraction Error:")
        assert "ValueError" in error_msg

    @pytest.mark.sanity
    def test_extract_from_obj_containers(self) -> None:
        """Verify containers like lists, tuples, sets, and dicts parse recursively."""
        # Setup
        model = ModelWithContainers()

        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        attributes = info_data["attributes"]
        assert attributes["items"] == [1, 2, "three"]
        assert attributes["mapping"] == {"key_a": 1, "key_b": [2, 3]}
        assert attributes["nested"]["type"] == "SimpleModel"
        assert attributes["nested"]["attributes"] == {
            "name": "nested",
            "age": 30,
        }

    @pytest.mark.sanity
    def test_extract_from_obj_custom_info(self) -> None:
        """Verify customized .info properties or callable methods are preferred."""
        # Custom property info
        model_custom = ModelWithCustomInfo()
        info_custom = InfoMixin.extract_from_obj(model_custom)
        assert info_custom == {"custom": True, "value_attr": "value"}

        # Custom callable info
        model_callable = ModelWithCustomCallableInfo()
        info_callable = InfoMixin.extract_from_obj(model_callable)
        assert info_callable == {"callable_custom": True}

        # Custom callable info raising exception (falls back to normal extraction)
        model_raising = ModelWithCustomCallableInfoRaising()
        info_raising = InfoMixin.extract_from_obj(model_raising)
        assert "attributes" in info_raising
        assert info_raising["type"] == "ModelWithCustomCallableInfoRaising"

        # Nested custom objects (covers _sanitize_value traversal)
        model_nested = ModelWithCustomNested()
        info_nested = InfoMixin.extract_from_obj(model_nested)
        attributes = info_nested["attributes"]
        assert attributes["custom_callable"] == {"callable_custom": True}
        assert attributes["custom_property"] == {
            "custom": True,
            "value_attr": "value",
        }
        assert (
            "ModelWithCustomCallableInfoRaising object" in attributes["custom_raising"]
        )

        # Implicitly cover _sanitize_value default visited parameter
        # to ensure 100% module coverage.
        assert InfoMixin._sanitize_value("fallback_val") == "fallback_val"

    @pytest.mark.sanity
    def test_extract_from_obj_exclude_keys(self) -> None:
        """Verify fields listed in info_exclude_keys settings are excluded."""
        # Setup
        reset_settings()
        get_settings().info_exclude_keys = ["info", "age"]
        model = SimpleModel("Alice", 25)

        try:
            # Invoke
            info_data = InfoMixin.extract_from_obj(model)

            # Assert
            assert info_data["attributes"] == {"name": "Alice"}
            assert "age" not in info_data["attributes"]
        finally:
            # Teardown
            reset_settings()

    @pytest.mark.regression
    def test_extract_from_obj_circular_references(self) -> None:
        """Verify circular reference detection resolves to a sentinel representation."""
        # Scenario 1: Circular reference in list elements
        model_circular_list = ModelWithCircularContainers()
        info_circular_list = InfoMixin.extract_from_obj(model_circular_list)
        elements = info_circular_list["attributes"]["elements"]
        assert len(elements) == 3
        assert elements[0] == 1
        assert elements[1] == 2
        assert elements[2].startswith("<CircularReference:")

        # Scenario 2: Circular reference to self
        model_self_ref = ModelWithSelfReference()
        model_self_ref.myself = model_self_ref
        info_self_ref = InfoMixin.extract_from_obj(model_self_ref)
        myself_val = info_self_ref["attributes"]["myself"]
        assert myself_val.startswith("<CircularReference:")

        # Scenario 3: Circular cross-reference across two objects
        model_a = ModelWithCrossReference("ModelA")
        model_b = ModelWithCrossReference("ModelB")
        model_a.other = model_b
        model_b.other = model_a

        info_cross_ref = InfoMixin.extract_from_obj(model_a)
        other_attributes = info_cross_ref["attributes"]["other"]["attributes"]
        assert other_attributes["name"] == "ModelB"
        circular_ref = other_attributes["other"]
        assert circular_ref.startswith("<CircularReference:")

    @pytest.mark.sanity
    def test_extract_from_obj_lazy_proxy(self) -> None:
        """Verify resolving of LazyProxy attributes in the serialization pipeline."""
        model = ModelWithLazyProxy("resolved_secret")
        info_data = InfoMixin.extract_from_obj(model)
        assert info_data["attributes"]["lazy_val"] == "resolved_secret"

    @pytest.mark.sanity
    def test_extract_from_obj_type_value(self) -> None:
        """Verify type objects are sanitized directly to their repr."""
        model = ModelWithTypeValue()
        info_data = InfoMixin.extract_from_obj(model)
        assert info_data["attributes"]["type_val"] == [repr(int)]

    @pytest.mark.sanity
    def test_extract_from_obj_custom_no_info(self) -> None:
        """Verify custom objects without an info attribute resolve to repr."""
        model = ModelWithCustomNoInfo()
        info_data = InfoMixin.extract_from_obj(model)
        assert info_data["attributes"]["dummy"] == "<CustomDummyWithoutInfo>"

    @pytest.mark.sanity
    def test_info_json(self) -> None:
        """Verify basic JSON serialization and its options."""
        model = SimpleModel("Alice", 25)

        # Basic serialization
        json_str = model.info_json()
        data = json.loads(json_str)
        assert data["type"] == "SimpleModel"
        assert data["attributes"] == {"name": "Alice", "age": 25}

        # Indent option
        json_indent = model.info_json(indent=4)
        assert "\n    " in json_indent

        # Sort keys option
        json_sorted = model.info_json(sort_keys=True)
        assert '"age": 25' in json_sorted
        assert '"name": "Alice"' in json_sorted

        # Additional kwargs
        json_kwargs = model.info_json(separators=(",", ":"))
        assert ":" in json_kwargs
        assert ", " not in json_kwargs

        # Circular reference in JSON serialization
        model_circular = ModelWithCircularContainers()
        json_circular_str = model_circular.info_json()
        data_circular = json.loads(json_circular_str)
        elements = data_circular["attributes"]["elements"]
        assert len(elements) == 3
        assert elements[2].startswith("<CircularReference:")

    @pytest.mark.sanity
    def test_info_json_invalid(self) -> None:
        """Verify invalid arguments to info_json raise TypeError."""
        model = SimpleModel("Alice", 25)
        # Passing an un-serializable object as an extra argument
        with pytest.raises(TypeError):
            model.info_json(cls=object)

    @pytest.mark.sanity
    def test_info_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify YAML serialization using PyYAML and fallback modes."""
        model = SimpleModel("Bob", 30)

        # Standard YAML
        yaml_str = model.info_yaml()
        data = yaml.safe_load(yaml_str)
        assert data["type"] == "SimpleModel"
        assert data["attributes"] == {"name": "Bob", "age": 30}

        # Sort keys options
        yaml_sorted = model.info_yaml(sort_keys=True)
        assert "age: 30" in yaml_sorted

        # Kwargs options
        yaml_flow = model.info_yaml(default_flow_style=True)
        assert "type: SimpleModel" in yaml_flow or (
            "{type: SimpleModel" in yaml_flow.replace(" ", "")
        )

        # Fallback YAML mode when PyYAML is unavailable
        monkeypatch.setattr(disdantic.introspection, "yaml", None)
        yaml_fallback_str = model.info_yaml(indent=2, sort_keys=True)
        assert 'type: "SimpleModel"' in yaml_fallback_str
        assert 'name: "Charlie"' not in yaml_fallback_str
        assert "age: 30" in yaml_fallback_str

        fallback_data = yaml.safe_load(yaml_fallback_str)
        assert fallback_data["type"] == "SimpleModel"
        assert fallback_data["attributes"] == {"name": "Bob", "age": 30}

        # Fallback YAML complex nested/empty structures
        class ComplexObj(InfoMixin):
            def __init__(self) -> None:
                self.str_val = "hello"
                self.bool_val = True
                self.none_val = None
                self.empty_dict: dict[str, Any] = {}
                self.empty_list: list[Any] = []
                self.nested_list = [1, [2], {"a": []}]

        obj = ComplexObj()
        yaml_complex_str = obj.info_yaml(sort_keys=True)
        complex_data = yaml.safe_load(yaml_complex_str)
        assert complex_data["type"] == "ComplexObj"
        assert complex_data["attributes"]["str_val"] == "hello"
        assert complex_data["attributes"]["bool_val"] is True
        assert complex_data["attributes"]["none_val"] is None
        assert complex_data["attributes"]["empty_dict"] == {}
        assert complex_data["attributes"]["empty_list"] == []
        assert complex_data["attributes"]["nested_list"] == [1, [2], {"a": []}]

    @pytest.mark.sanity
    def test_info_yaml_invalid(self) -> None:
        """Verify invalid arguments to info_yaml raise exceptions."""
        model = SimpleModel("Bob", 30)
        # Passing invalid arguments to PyYAML dump
        with pytest.raises((TypeError, ValueError)):
            model.info_yaml(invalid_argument_for_yaml=True)

    @pytest.mark.regression
    def test_prepare_for_serialization_circular(self) -> None:
        """Verify _prepare_for_serialization detects circular references."""
        circular_list: list[Any] = []
        circular_list.append(circular_list)
        res_list = InfoMixin._prepare_for_serialization(circular_list)
        assert isinstance(res_list, list)
        assert len(res_list) == 1
        assert res_list[0].startswith("<CircularReference:")

        circular_dict: dict[str, Any] = {}
        circular_dict["self"] = circular_dict
        res_dict = InfoMixin._prepare_for_serialization(circular_dict)
        assert isinstance(res_dict, dict)
        assert res_dict["self"].startswith("<CircularReference:")

    @pytest.mark.regression
    def test_prepare_for_serialization_fallback(self) -> None:
        """Verify _prepare_for_serialization fallback representation."""
        dummy_obj = object()
        res = InfoMixin._prepare_for_serialization(dummy_obj)
        assert res == str(dummy_obj)

    @pytest.mark.regression
    def test_yaml_import_error(self) -> None:
        """Verify module handles yaml module load ImportError."""
        try:
            with patch(
                "disdantic.loading.LazyLoader.load_module_proxy",
                side_effect=ImportError,
            ):
                importlib.reload(disdantic.introspection)
                assert disdantic.introspection.yaml is None
        finally:
            importlib.reload(disdantic.introspection)


@pytest.mark.smoke
def test_primitive_types() -> None:
    """Verify PRIMITIVE_TYPES constant contents and type-matching compatibility."""
    assert isinstance(PRIMITIVE_TYPES, tuple)
    assert len(PRIMITIVE_TYPES) == 5
    assert str in PRIMITIVE_TYPES
    assert int in PRIMITIVE_TYPES
    assert float in PRIMITIVE_TYPES
    assert bool in PRIMITIVE_TYPES
    assert type(None) in PRIMITIVE_TYPES
