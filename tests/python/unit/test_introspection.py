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

import builtins
import importlib
import inspect
import json
import sys
import warnings
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from pydantic import BaseModel

import disdantic.compat
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
        # Setup
        # Mock
        # Invoke & Assert
        assert issubclass(SimpleModel, InfoMixin)
        assert hasattr(InfoMixin, "extract_from_obj")
        assert hasattr(InfoMixin, "info")
        assert isinstance(InfoMixin.info, property)

        extract_sig = inspect.signature(InfoMixin.extract_from_obj)
        assert "obj" in extract_sig.parameters
        assert "visited" in extract_sig.parameters
        # Teardown

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: SimpleModel) -> None:
        """Verify correct initialization and state mapping from the fixture."""
        # Setup
        # Mock
        # Invoke & Assert
        assert valid_instances.name in {"Alice", "Bob"}
        assert valid_instances.age in {25, 30}
        assert valid_instances._private_val == "secret"
        # Teardown

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify direct instantiation failure when parameters are provided."""
        # Setup
        # Mock
        # Invoke & Assert
        with pytest.raises(TypeError):
            InfoMixin(dummy_param="value")  # type: ignore[call-arg]  # ty: ignore[unknown-argument]
        # Teardown

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify instantiation succeeds with no params and fails with missing."""
        # Setup
        # Mock
        # Invoke
        instance = InfoMixin()

        # Assert
        assert isinstance(instance, InfoMixin)
        with pytest.raises(TypeError):
            SimpleModel(name="OnlyName")  # type: ignore[call-arg]  # ty: ignore[missing-argument]
        # Teardown

    @pytest.mark.smoke
    def test_info(self, valid_instances: SimpleModel) -> None:
        """Verify the info property extracts dynamic self-introspection data."""
        # Setup
        # Mock
        # Invoke
        info_data = valid_instances.info

        # Assert
        assert isinstance(info_data, dict)
        assert info_data["str"].startswith("<SimpleModel object at")
        assert info_data["type"] == "SimpleModel"
        assert info_data["module"] == "tests.python.unit.test_introspection"
        assert info_data["attributes"] == {
            "name": valid_instances.name,
            "age": valid_instances.age,
        }
        # Teardown

    @pytest.mark.smoke
    def test_extract_from_obj(self) -> None:
        """Verify the extract_from_obj class method parses public attributes."""
        # Setup
        model = SimpleModel("Charlie", 40)

        # Mock
        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        assert info_data["str"].startswith("<SimpleModel object at")
        assert info_data["type"] == "SimpleModel"
        assert info_data["module"] == "tests.python.unit.test_introspection"
        assert info_data["attributes"] == {
            "name": "Charlie",
            "age": 40,
        }
        # Teardown

    @pytest.mark.sanity
    def test_extract_from_obj_invalid(self) -> None:
        """Verify fallback behavior when object parsing encounters exceptions."""
        # Setup
        model = ModelWithExtractionError()

        # Mock
        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        error_msg = info_data["attributes"]["broken"]
        assert error_msg.startswith("<Extraction Error:")
        assert "ValueError" in error_msg
        # Teardown

    @pytest.mark.sanity
    def test_extract_from_obj_containers(self) -> None:
        """Verify containers like lists, tuples, sets, and dicts parse recursively."""
        # Setup
        model = ModelWithContainers()

        # Mock
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
        # Teardown

    @pytest.mark.sanity
    def test_extract_from_obj_custom_info(self) -> None:
        """Verify customized .info properties or callable methods are preferred."""
        # Setup
        model_custom = ModelWithCustomInfo()
        model_callable = ModelWithCustomCallableInfo()
        model_raising = ModelWithCustomCallableInfoRaising()
        model_nested = ModelWithCustomNested()

        # Mock
        # Invoke
        info_custom = InfoMixin.extract_from_obj(model_custom)
        info_callable = InfoMixin.extract_from_obj(model_callable)
        info_raising = InfoMixin.extract_from_obj(model_raising)
        info_nested = InfoMixin.extract_from_obj(model_nested)

        # Assert
        assert info_custom == {"custom": True, "value_attr": "value"}
        assert info_callable == {"callable_custom": True}
        assert "attributes" in info_raising
        assert info_raising["type"] == "ModelWithCustomCallableInfoRaising"

        attributes = info_nested["attributes"]
        assert attributes["custom_callable"] == {"callable_custom": True}
        assert attributes["custom_property"] == {
            "custom": True,
            "value_attr": "value",
        }
        assert (
            "ModelWithCustomCallableInfoRaising object" in attributes["custom_raising"]
        )

        assert InfoMixin._sanitize("fallback_val", set()) == "fallback_val"
        # Teardown

    @pytest.mark.sanity
    def test_extract_from_obj_exclude_keys(self) -> None:
        """Verify fields listed in info_exclude_keys settings are excluded."""
        # Setup
        reset_settings()
        get_settings().info_exclude_keys = ["info", "age"]
        model = SimpleModel("Alice", 25)

        # Mock
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
        # Setup
        model_circular_list = ModelWithCircularContainers()
        model_self_ref = ModelWithSelfReference()
        model_self_ref.myself = model_self_ref

        model_first = ModelWithCrossReference("ModelA")
        model_second = ModelWithCrossReference("ModelB")
        model_first.other = model_second
        model_second.other = model_first

        # Mock
        # Invoke
        info_circular_list = InfoMixin.extract_from_obj(model_circular_list)
        info_self_ref = InfoMixin.extract_from_obj(model_self_ref)
        info_cross_ref = InfoMixin.extract_from_obj(model_first)

        # Assert
        elements = info_circular_list["attributes"]["elements"]
        assert len(elements) == 3
        assert elements[0] == 1
        assert elements[1] == 2
        assert elements[2].startswith("<CircularReference:")

        myself_val = info_self_ref["attributes"]["myself"]
        assert myself_val.startswith("<CircularReference:")

        other_attributes = info_cross_ref["attributes"]["other"]["attributes"]
        assert other_attributes["name"] == "ModelB"
        circular_ref = other_attributes["other"]
        assert circular_ref.startswith("<CircularReference:")
        # Teardown

    @pytest.mark.sanity
    def test_extract_from_obj_lazy_proxy(self) -> None:
        """Verify resolving of LazyProxy attributes in the serialization pipeline."""
        # Setup
        model = ModelWithLazyProxy("resolved_secret")

        # Mock
        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        assert info_data["attributes"]["lazy_val"] == "resolved_secret"
        # Teardown

    @pytest.mark.sanity
    def test_extract_from_obj_type_value(self) -> None:
        """Verify type objects are sanitized directly to their repr."""
        # Setup
        model = ModelWithTypeValue()

        # Mock
        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        assert info_data["attributes"]["type_val"] == [repr(int)]
        # Teardown

    @pytest.mark.sanity
    def test_extract_from_obj_custom_no_info(self) -> None:
        """Verify custom objects without an info attribute resolve to repr."""
        # Setup
        model = ModelWithCustomNoInfo()

        # Mock
        # Invoke
        info_data = InfoMixin.extract_from_obj(model)

        # Assert
        assert info_data["attributes"]["dummy"] == "<CustomDummyWithoutInfo>"
        # Teardown

    @pytest.mark.sanity
    def test_info_json(self) -> None:
        """Verify basic JSON serialization and its options."""
        # Setup
        model = SimpleModel("Alice", 25)
        model_circular = ModelWithCircularContainers()

        # Mock
        # Invoke
        json_str = model.info_json()
        data = json.loads(json_str)

        json_indent = model.info_json(indent=4)
        json_sorted = model.info_json(sort_keys=True)
        json_kwargs = model.info_json(separators=(",", ":"))
        json_circular_str = model_circular.info_json()
        data_circular = json.loads(json_circular_str)

        # Assert
        assert data["type"] == "SimpleModel"
        assert data["attributes"] == {"name": "Alice", "age": 25}
        assert "\n    " in json_indent
        assert '"age": 25' in json_sorted
        assert '"name": "Alice"' in json_sorted
        assert ":" in json_kwargs
        assert ", " not in json_kwargs

        elements = data_circular["attributes"]["elements"]
        assert len(elements) == 3
        assert elements[2].startswith("<CircularReference:")
        # Teardown

    @pytest.mark.sanity
    def test_info_json_invalid(self) -> None:
        """Verify invalid arguments to info_json raise TypeError."""
        # Setup
        model = SimpleModel("Alice", 25)

        # Mock
        # Invoke & Assert
        with pytest.raises(TypeError):
            model.info_json(cls=object)
        # Teardown

    @pytest.mark.sanity
    def test_info_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify YAML serialization using PyYAML and fallback modes."""
        # Setup
        model = SimpleModel("Bob", 30)

        class ComplexObj(InfoMixin):
            def __init__(self) -> None:
                self.str_val = "hello"
                self.bool_val = True
                self.none_val = None
                self.empty_dict: dict[str, Any] = {}
                self.empty_list: list[Any] = []
                self.nested_list = [1, [2], {"key_a": []}]

        obj = ComplexObj()

        # Mock
        # Invoke
        yaml_str = model.info_yaml()
        data = yaml.safe_load(yaml_str)

        yaml_sorted = model.info_yaml(sort_keys=True)
        yaml_flow = model.info_yaml(default_flow_style=True)

        monkeypatch.setattr(disdantic.introspection, "yaml", None)
        with pytest.raises(ImportError) as exc_info:
            model.info_yaml(indent=2, sort_keys=True)
        assert "PyYAML is required for YAML serialization" in str(exc_info.value)

        with pytest.raises(ImportError) as exc_info:
            obj.info_yaml(sort_keys=True)
        assert "PyYAML is required for YAML serialization" in str(exc_info.value)

        # Assert
        assert data["type"] == "SimpleModel"
        assert data["attributes"] == {"name": "Bob", "age": 30}
        assert "age: 30" in yaml_sorted
        assert "type: SimpleModel" in yaml_flow or (
            "{type: SimpleModel" in yaml_flow.replace(" ", "")
        )
        # Teardown

    @pytest.mark.sanity
    def test_info_yaml_invalid(self) -> None:
        """Verify invalid arguments to info_yaml raise exceptions."""
        # Setup
        model = SimpleModel("Bob", 30)

        # Mock
        # Invoke & Assert
        with pytest.raises((TypeError, ValueError)):
            model.info_yaml(invalid_argument_for_yaml=True)
        # Teardown

    @pytest.mark.regression
    def test_info_json_circular_implicit(self) -> None:
        """Verify circular reference lists/dicts are serialized implicitly
        through public json pathway.
        """

        # Setup
        class ModelWithCustomCircular(InfoMixin):
            @property
            def info(self) -> dict[str, Any]:
                circular_list: list[Any] = []
                circular_list.append(circular_list)
                circular_dict: dict[str, Any] = {}
                circular_dict["self"] = circular_dict
                return {"list": circular_list, "dict": circular_dict}

        model_circular = ModelWithCustomCircular()

        # Mock
        # Invoke
        json_circular_str = model_circular.info_json()
        data_circular = json.loads(json_circular_str)

        # Assert
        list_val = data_circular["list"]
        assert len(list_val) == 1
        assert list_val[0].startswith("<CircularReference:")

        dict_val = data_circular["dict"]
        assert dict_val["self"].startswith("<CircularReference:")
        # Teardown

    @pytest.mark.regression
    def test_info_json_fallback_implicit(self) -> None:
        """Verify fallback representation of custom objects is serialized
        to string representation implicitly.
        """

        # Setup
        class ModelWithCustomRawInfo(InfoMixin):
            @property
            def info(self) -> dict[str, Any]:
                return {"raw_object": object()}

        model_raw = ModelWithCustomRawInfo()

        # Mock
        # Invoke
        json_str = model_raw.info_json()
        data = json.loads(json_str)

        # Assert
        raw_val = data["raw_object"]
        assert raw_val.startswith("<object object at ")
        # Teardown

    @pytest.mark.regression
    def test_yaml_import_error(self) -> None:
        """Verify module handles yaml module load ImportError."""
        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "yaml":
                raise ImportError("Mocked yaml import error")
            return original_import(name, *args, **kwargs)

        # Mock & Invoke
        yaml_module = sys.modules.pop("yaml", None)
        try:
            with patch("builtins.__import__", side_effect=mock_import):
                importlib.reload(disdantic.compat)
                importlib.reload(disdantic.introspection)

                # Assert
                assert disdantic.introspection.yaml is None
        finally:
            # Teardown
            if yaml_module is not None:
                sys.modules["yaml"] = yaml_module
            importlib.reload(disdantic.compat)
            importlib.reload(disdantic.introspection)

    @pytest.mark.regression
    def test_info_pydantic_no_deprecation_warnings(self) -> None:
        """Verify Pydantic models introspect without deprecation warnings.

        Also check for metadata leakage.
        """

        # Setup
        class DummyPydanticModel(BaseModel, disdantic.introspection.InfoMixin):
            name: str
            val: int

        model = DummyPydanticModel(name="test_pydantic", val=42)

        # Mock & Invoke
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")
            info_data = model.info

        # Assert
        # 1. No deprecation warnings should be emitted
        deprecation_warnings = [
            w
            for w in caught_warnings
            if issubclass(w.category, DeprecationWarning)
            or "deprecation" in str(w.message).lower()
        ]
        assert len(deprecation_warnings) == 0, (
            f"Deprecation warnings occurred: {deprecation_warnings}"
        )

        # 2. Pydantic metadata keys must be omitted
        attributes = info_data["attributes"]
        assert attributes == {"name": "test_pydantic", "val": 42}

    @pytest.mark.regression
    def test_class_variable_filtering(self) -> None:
        """Verify that class variables/constants are excluded from introspection."""

        # Setup
        class ModelWithClassVar(InfoMixin):
            CLASS_CONST = 100
            _private_class_const = 200

            def __init__(self, name: str):
                self.name = name

            @property
            def computed_prop(self) -> str:
                return "prop_val"

        model = ModelWithClassVar(name="instance_val")

        # Invoke
        info_data = model.info

        # Assert
        # 1. Instance variable and property should be included
        assert info_data["attributes"]["name"] == "instance_val"
        assert info_data["attributes"]["computed_prop"] == "prop_val"

        # 2. Class constants and variables should be skipped
        assert "CLASS_CONST" not in info_data["attributes"]
        assert "_private_class_const" not in info_data["attributes"]

    @pytest.mark.regression
    def test_repr_str_overrides(self) -> None:
        """Verify that __repr__ and __str__ delegate to overrides or fallback."""

        # Setup
        # Case A: Plain InfoMixin subclass (no other parent implements custom repr/str)
        class PlainInfoModel(InfoMixin):
            def __init__(self) -> None:
                self.val = 42

        # Case B: Subclass overrides __repr__ or __str__
        class CustomReprModel(InfoMixin):
            def __init__(self) -> None:
                self.val = 100

            def __repr__(self) -> str:
                return "custom_repr"

            def __str__(self) -> str:
                return "custom_str"

        # Case C: Multiple inheritance with another parent that overrides repr/str
        class ParentWithCustomRepr:
            def __repr__(self) -> str:
                return "parent_repr"

            def __str__(self) -> str:
                return "parent_str"

        class InheritedReprModel(InfoMixin, ParentWithCustomRepr):
            pass

        # Invoke & Assert
        model_a = PlainInfoModel()
        model_b = CustomReprModel()
        model_c = InheritedReprModel()

        # Plain model uses the info fallback representation
        assert repr(model_a) == f"<PlainInfoModel info={model_a.info}>"
        assert str(model_a) == f"<PlainInfoModel info={model_a.info}>"

        # Custom repr/str overrides are respected
        assert repr(model_b) == "custom_repr"
        assert str(model_b) == "custom_str"

        # MRO inheritance is respected
        assert repr(model_c) == "parent_repr"
        assert str(model_c) == "parent_str"


@pytest.mark.smoke
def test_primitive_types() -> None:
    """Verify PRIMITIVE_TYPES constant contents and type-matching compatibility."""
    # Setup
    # Mock
    # Invoke & Assert
    assert isinstance(PRIMITIVE_TYPES, tuple)
    assert len(PRIMITIVE_TYPES) == 5
    assert str in PRIMITIVE_TYPES
    assert int in PRIMITIVE_TYPES
    assert float in PRIMITIVE_TYPES
    assert bool in PRIMITIVE_TYPES
    assert type(None) in PRIMITIVE_TYPES
    # Teardown
