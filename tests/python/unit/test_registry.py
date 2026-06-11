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

"""Unit tests for the registry module."""

from __future__ import annotations

import inspect
import threading
import time
from collections.abc import Generator
from typing import Literal

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError
from pytest_mock import MockerFixture

from disdantic.exceptions import DiscriminatorNotFoundError, RegistryCollisionError
from disdantic.importer import AutoImporterMixin
from disdantic.model import ReloadableBaseModel
from disdantic.registry import (
    PydanticClassRegistryMixin,
    RegistryManager,
    RegistryMixin,
)
from disdantic.settings import get_settings, reset_settings


class ConcreteRegistry(RegistryMixin[type]):
    """Concrete registry subclass used exclusively for testing RegistryMixin."""

    variant_name: str


class DummyClass:
    """Dummy class used for registration targets in tests."""


class PydanticBaseTestModel(PydanticClassRegistryMixin):
    """Base model class used to test PydanticClassRegistryMixin."""

    model_type: str
    content: str


class PydanticTextTestModel(PydanticBaseTestModel):
    """Subclass representing text message type."""

    model_type: Literal["text"] = "text"
    text_val: str


class PydanticImageTestModel(PydanticBaseTestModel):
    """Subclass representing image message type."""

    model_type: Literal["image"] = "image"
    url: str


class TestRegistryMixin:
    """Test suite for validating RegistryMixin functionality."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.fixture(autouse=True)
    def clear_registry_fixture(self) -> Generator[None, None, None]:
        """Clear registry before and after each test to isolate state."""
        ConcreteRegistry.clear_registry()
        yield
        ConcreteRegistry.clear_registry()

    @pytest.fixture(params=["variant_alpha", "variant_beta"])
    def valid_instances(self, request: pytest.FixtureRequest) -> ConcreteRegistry:
        """Fixture supplying instantiated valid variations of the registry class."""
        instance = ConcreteRegistry()
        instance.variant_name = request.param
        return instance

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate structural contracts: inheritance and method signatures."""
        assert issubclass(ConcreteRegistry, RegistryMixin)
        assert issubclass(ConcreteRegistry, AutoImporterMixin)

        # Verify class variables exist
        assert hasattr(ConcreteRegistry, "registry")
        assert hasattr(ConcreteRegistry, "_lower_registry")
        assert hasattr(ConcreteRegistry, "registry_auto_discovery")
        assert hasattr(ConcreteRegistry, "registry_populated")

        assert inspect.isroutine(ConcreteRegistry.is_auto_discovery_enabled)
        assert inspect.isroutine(ConcreteRegistry.register)
        assert inspect.isroutine(ConcreteRegistry.register_decorator)
        assert inspect.isroutine(ConcreteRegistry.auto_populate_registry)
        assert inspect.isroutine(ConcreteRegistry.registered_objects)
        assert inspect.isroutine(ConcreteRegistry.is_registered)
        assert inspect.isroutine(ConcreteRegistry.get_registered_object)
        assert inspect.isroutine(ConcreteRegistry.clear_registry)
        assert inspect.isroutine(ConcreteRegistry.unregister)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: ConcreteRegistry) -> None:
        """Verify correct state mapping on registry instances."""
        assert isinstance(valid_instances, ConcreteRegistry)
        assert hasattr(valid_instances, "variant_name")
        assert ConcreteRegistry.registry == {}
        assert ConcreteRegistry._lower_registry == {}

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed/unexpected values during construction to verify handling."""
        with pytest.raises(TypeError):
            ConcreteRegistry(unexpected_argument="fail")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit default arguments to verify standard construction is safe."""
        instance = ConcreteRegistry()
        assert isinstance(instance, ConcreteRegistry)

    @pytest.mark.smoke
    def test_is_auto_discovery_enabled(self) -> None:
        """Verify auto-discovery detection based on settings or class attributes."""
        ConcreteRegistry.registry_auto_discovery = False
        assert not ConcreteRegistry.is_auto_discovery_enabled()

        ConcreteRegistry.registry_auto_discovery = True
        assert ConcreteRegistry.is_auto_discovery_enabled()

        # Check fallback to global settings
        ConcreteRegistry.registry_auto_discovery = False
        get_settings().registry_auto_discovery = True
        assert ConcreteRegistry.is_auto_discovery_enabled()

    @pytest.mark.smoke
    def test_register(self) -> None:
        """Verify decorator registers targets with different name inputs."""

        # 1. No name provided: defaults to __name__
        @ConcreteRegistry.register()
        class DefaultTarget:
            pass

        assert ConcreteRegistry.get_registered_object("DefaultTarget") is DefaultTarget

        # 2. String name provided
        @ConcreteRegistry.register("custom_service")
        class CustomTarget:
            pass

        assert ConcreteRegistry.get_registered_object("custom_service") is CustomTarget

        # 3. Sequence of names provided
        @ConcreteRegistry.register(["alias1", "alias2"])
        class MultiTarget:
            pass

        assert ConcreteRegistry.get_registered_object("alias1") is MultiTarget
        assert ConcreteRegistry.get_registered_object("alias2") is MultiTarget

    @pytest.mark.smoke
    def test_register_decorator(self) -> None:
        """Verify direct register_decorator invocation adds mappings correctly."""
        result = ConcreteRegistry.register_decorator(
            DummyClass, name="decorator_target"
        )
        assert result is DummyClass
        assert ConcreteRegistry.get_registered_object("decorator_target") is DummyClass

    @pytest.mark.sanity
    def test_register_decorator_invalid(self) -> None:
        """Verify registry rejects non-string naming formats and invalid sequences."""
        with pytest.raises(ValueError, match="Unsupported naming format"):
            ConcreteRegistry.register_decorator(DummyClass, name=123)  # type: ignore

        with pytest.raises(ValueError, match="Unsupported naming format"):
            ConcreteRegistry.register_decorator(DummyClass, name={"name": "fail"})  # type: ignore

        err_msg = "Registry keys must explicitly be strings"
        with pytest.raises(ValueError, match=err_msg):
            ConcreteRegistry.register_decorator(DummyClass, name=["valid_name", 123])  # type: ignore

    @pytest.mark.regression
    def test_register_decorator_collision(self) -> None:
        """Verify duplicate registrations raise RegistryCollisionError."""
        ConcreteRegistry.register_decorator(DummyClass, name="colliding_key")

        class AnotherClass:
            pass

        with pytest.raises(RegistryCollisionError, match="Collision detected"):
            ConcreteRegistry.register_decorator(AnotherClass, name="colliding_key")

    @pytest.mark.sanity
    def test_auto_populate_registry(self, mocker: MockerFixture) -> None:
        """Verify auto-population flow and flags management."""
        get_settings().registry_auto_discovery = False
        ConcreteRegistry.registry_auto_discovery = False

        with pytest.raises(ValueError, match="Auto-population rejected"):
            ConcreteRegistry.auto_populate_registry()

        ConcreteRegistry.registry_auto_discovery = True
        mock_import_package = mocker.patch.object(
            ConcreteRegistry, "auto_import_package_modules"
        )

        assert ConcreteRegistry.auto_populate_registry() is True
        mock_import_package.assert_called_once()
        assert ConcreteRegistry.registry_populated is True

        mock_import_package.reset_mock()
        assert ConcreteRegistry.auto_populate_registry() is False
        mock_import_package.assert_not_called()

    @pytest.mark.smoke
    def test_registered_objects(self, mocker: MockerFixture) -> None:
        """Verify list of registered items is returned, auto-populating if needed."""
        ConcreteRegistry.registry_auto_discovery = False
        assert ConcreteRegistry.registered_objects() == ()

        ConcreteRegistry.register_decorator(DummyClass, name="dummy")
        assert ConcreteRegistry.registered_objects() == (DummyClass,)

        ConcreteRegistry.clear_registry()
        ConcreteRegistry.registry_auto_discovery = True
        mock_auto_populate = mocker.patch.object(
            ConcreteRegistry, "auto_populate_registry"
        )

        ConcreteRegistry.registered_objects()
        mock_auto_populate.assert_called_once()

    @pytest.mark.smoke
    def test_is_registered(self) -> None:
        """Verify case-insensitive presence check works in O(1) time."""
        ConcreteRegistry.register_decorator(DummyClass, name="CamelCaseKey")

        assert ConcreteRegistry.is_registered("CamelCaseKey") is True
        assert ConcreteRegistry.is_registered("camelcasekey") is True
        assert ConcreteRegistry.is_registered("CAMELCASEKEY") is True
        assert ConcreteRegistry.is_registered("non_existent") is False

    @pytest.mark.smoke
    def test_get_registered_object(self) -> None:
        """Verify retrieval is case-insensitive, returning None if not found."""
        ConcreteRegistry.register_decorator(DummyClass, name="CamelCaseKey")

        assert ConcreteRegistry.get_registered_object("CamelCaseKey") is DummyClass
        assert ConcreteRegistry.get_registered_object("camelcasekey") is DummyClass
        assert ConcreteRegistry.get_registered_object("CAMELCASEKEY") is DummyClass
        assert ConcreteRegistry.get_registered_object("non_existent") is None

    @pytest.mark.sanity
    def test_clear_registry(self) -> None:
        """Verify registry namespace dict and flags are reset."""
        ConcreteRegistry.register_decorator(DummyClass, name="dummy")
        ConcreteRegistry.registry_populated = True

        ConcreteRegistry.clear_registry()
        assert ConcreteRegistry.registry == {}
        assert ConcreteRegistry._lower_registry == {}
        assert ConcreteRegistry.registry_populated is False

    @pytest.mark.smoke
    def test_unregister(self) -> None:
        """Verify de-registration of an identifier (canonical & lowercase)."""
        ConcreteRegistry.register_decorator(DummyClass, name="CamelCaseKey")
        assert ConcreteRegistry.is_registered("CamelCaseKey")

        ConcreteRegistry.unregister("CamelCaseKey")
        assert not ConcreteRegistry.is_registered("CamelCaseKey")
        assert "CamelCaseKey" not in ConcreteRegistry.registry
        assert "camelcasekey" not in ConcreteRegistry._lower_registry

    @pytest.mark.smoke
    def test_unregister_case_insensitive(self) -> None:
        """Verify de-registration works case-insensitively."""
        ConcreteRegistry.register_decorator(DummyClass, name="CamelCaseKey")
        assert ConcreteRegistry.is_registered("CamelCaseKey")

        # Unregister using a lowercase token
        ConcreteRegistry.unregister("camelcasekey")
        assert not ConcreteRegistry.is_registered("CamelCaseKey")
        assert "CamelCaseKey" not in ConcreteRegistry.registry
        assert "camelcasekey" not in ConcreteRegistry._lower_registry

    @pytest.mark.sanity
    def test_unregister_not_found(self) -> None:
        """Verify trying to unregister non-existent token raises ValueError."""
        err_msg = "is not present in the ConcreteRegistry registry"
        with pytest.raises(ValueError, match=err_msg):
            ConcreteRegistry.unregister("non_existent")

    @pytest.mark.regression
    def test_unregister_thread_safety(self) -> None:
        """Verify thread-safety of concurrent registration & de-registration."""
        errors_list: list[Exception] = []

        def worker(thread_key: str) -> None:
            try:
                ConcreteRegistry.register_decorator(DummyClass, name=thread_key)
                time.sleep(0.001)
                assert ConcreteRegistry.is_registered(thread_key)
                ConcreteRegistry.unregister(thread_key)
                assert not ConcreteRegistry.is_registered(thread_key)
            except Exception as thread_exc:  # noqa: BLE001
                errors_list.append(thread_exc)

        threads_list = [
            threading.Thread(target=worker, args=(f"thread_key_{thread_index}",))
            for thread_index in range(50)
        ]
        for active_thread in threads_list:
            active_thread.start()
        for active_thread in threads_list:
            active_thread.join()

        assert not errors_list, (
            f"Errors occurred during concurrent execution: {errors_list}"
        )
        assert not ConcreteRegistry.registry


class TestPydanticClassRegistryMixin:
    """Test suite for validating PydanticClassRegistryMixin functionality."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.fixture(autouse=True)
    def setup_pydantic_registry(self) -> Generator[None, None, None]:
        """Ensure registry is populated before each test and cleaned up."""
        PydanticBaseTestModel.clear_registry()
        PydanticBaseTestModel.register_decorator(PydanticTextTestModel, name="text")
        PydanticBaseTestModel.register_decorator(PydanticImageTestModel, name="image")
        yield
        PydanticBaseTestModel.clear_registry()

    @pytest.fixture(params=["text_msg", "image_msg"])
    def valid_instances(self, request: pytest.FixtureRequest) -> PydanticBaseTestModel:
        """Fixture supplying valid model subclass variations."""
        if request.param == "text_msg":
            return PydanticTextTestModel(content="hello", text_val="world")
        return PydanticImageTestModel(content="photo", url="http://example.com/img.png")

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate structural contracts: inheritance and method signatures."""
        assert issubclass(PydanticBaseTestModel, PydanticClassRegistryMixin)
        assert issubclass(PydanticBaseTestModel, ReloadableBaseModel)
        assert issubclass(PydanticBaseTestModel, RegistryMixin)

        assert hasattr(PydanticBaseTestModel, "schema_discriminator")

        assert inspect.isroutine(PydanticBaseTestModel.get_schema_discriminator)
        assert inspect.isroutine(PydanticBaseTestModel.register_decorator)
        assert inspect.isroutine(PydanticBaseTestModel.auto_populate_registry)
        assert inspect.isroutine(PydanticBaseTestModel.registered_classes)
        assert inspect.isroutine(PydanticBaseTestModel.clear_registry)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: PydanticBaseTestModel) -> None:
        """Verify correct state mapping on registry instances."""
        assert isinstance(valid_instances, PydanticBaseTestModel)
        assert valid_instances.content in ("hello", "photo")

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify passing unexpected/malformed values raises ValidationError."""
        with pytest.raises(ValidationError):
            PydanticTextTestModel(content={"invalid": 123}, text_val="ok")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify omission of required parameters raises ValidationError."""
        with pytest.raises(ValidationError):
            PydanticTextTestModel(content="hello")  # type: ignore

    @pytest.mark.smoke
    def test_get_schema_discriminator(self) -> None:
        """Verify resolution of schema discriminator attribute."""

        class DefaultDiscModel(PydanticClassRegistryMixin):
            pass

        assert DefaultDiscModel.get_schema_discriminator() == "model_type"

        get_settings().default_schema_discriminator = "custom_disc"
        assert DefaultDiscModel.get_schema_discriminator() == "custom_disc"

        class OverrideDiscModel(PydanticClassRegistryMixin):
            schema_discriminator = "class_disc"

        assert OverrideDiscModel.get_schema_discriminator() == "class_disc"

    @pytest.mark.sanity
    def test_register_decorator_invalid(self) -> None:
        """Verify registry rejects non-BaseModel subclass types."""

        class NonPydanticClass:
            pass

        with pytest.raises(TypeError, match="must extend Pydantic BaseModel"):
            PydanticBaseTestModel.register_decorator(NonPydanticClass, name="fail")

    @pytest.mark.sanity
    def test_auto_populate_registry(self, mocker: MockerFixture) -> None:
        """Verify auto-population triggers base rebuild."""

        class AutoPopBase(PydanticClassRegistryMixin):
            pass

        AutoPopBase.registry_auto_discovery = True
        mock_import_package = mocker.patch.object(
            AutoPopBase, "auto_import_package_modules"
        )
        mock_rebuild = mocker.patch.object(AutoPopBase, "_trigger_base_rebuild")

        assert AutoPopBase.auto_populate_registry() is True
        mock_import_package.assert_called_once()
        mock_rebuild.assert_called_once()

    @pytest.mark.smoke
    def test_registered_classes(self) -> None:
        """Verify retrieval of registered classes, raising error if empty."""
        registered_classes_list = PydanticBaseTestModel.registered_classes()
        assert PydanticTextTestModel in registered_classes_list
        assert PydanticImageTestModel in registered_classes_list

        class EmptyBase(PydanticClassRegistryMixin):
            pass

        with pytest.raises(ValueError, match="No objects are currently present"):
            EmptyBase.registered_classes()

    @pytest.mark.sanity
    def test_clear_registry(self, mocker: MockerFixture) -> None:
        """Verify clear wipes subclasses and triggers base rebuild."""
        mock_rebuild = mocker.patch.object(
            PydanticBaseTestModel, "_trigger_base_rebuild"
        )

        PydanticBaseTestModel.clear_registry()
        assert PydanticBaseTestModel.registry == {}
        mock_rebuild.assert_called_once()

    @pytest.mark.smoke
    def test_marshalling(self, valid_instances: PydanticBaseTestModel) -> None:
        """Verify serialization round-tripping for polymorphic models."""
        dumped_data = valid_instances.model_dump()
        assert isinstance(dumped_data, dict)
        assert dumped_data["content"] == valid_instances.content
        assert dumped_data["model_type"] == valid_instances.model_type

        validated_object = PydanticBaseTestModel.model_validate(dumped_data)
        assert isinstance(validated_object, type(valid_instances))
        assert validated_object.content == valid_instances.content
        assert validated_object.model_dump() == dumped_data

    @pytest.mark.regression
    def test_pydantic_core_schema(self) -> None:
        """Verify validation intercepts casing differences."""
        data_text_lower = {
            "model_type": "TEXT",
            "content": "hello",
            "text_val": "world",
        }
        validated_object = PydanticBaseTestModel.model_validate(data_text_lower)
        assert isinstance(validated_object, PydanticTextTestModel)
        assert validated_object.model_type == "text"

        data_image_mixed = {
            "model_type": "ImAgE",
            "content": "photo",
            "url": "http://img",
        }
        validated_object = PydanticBaseTestModel.model_validate(data_image_mixed)
        assert isinstance(validated_object, PydanticImageTestModel)
        assert validated_object.model_type == "image"

    @pytest.mark.regression
    def test_pydantic_core_schema_invalid(self) -> None:
        """Verify invalid discriminator values raise DiscriminatorNotFoundError."""
        data_invalid = {
            "model_type": "nonexistent",
            "content": "hello",
            "text_val": "world",
        }
        with pytest.raises(ValidationError) as validation_exc_info:
            PydanticBaseTestModel.model_validate(data_invalid)

        err_msg = "Failed to resolve polymorphic configuration layer"
        assert err_msg in str(validation_exc_info.value)
        assert "'nonexistent' is not a recognized mapping target" in str(
            validation_exc_info.value
        )

        # Directly verify the custom exception attributes
        custom_exc = DiscriminatorNotFoundError("nonexistent", ["text", "image"])
        assert custom_exc.rejected_value == "nonexistent"
        assert custom_exc.valid_options == ["text", "image"]

    @pytest.mark.smoke
    def test_pydantic_schema_base_type(self) -> None:
        """Verify root base type resolution through the MRO hierarchy."""

        class BaseOne(PydanticClassRegistryMixin):
            pass

        class SubOne(BaseOne):
            pass

        class SubSubOne(SubOne):
            pass

        assert BaseOne.__pydantic_schema_base_type__() is BaseOne
        assert SubOne.__pydantic_schema_base_type__() is BaseOne
        assert SubSubOne.__pydantic_schema_base_type__() is BaseOne

    @pytest.mark.regression
    def test_pydantic_generate_base_schema(self) -> None:
        """Verify any_schema fallback when class registry is completely empty."""

        class EmptyBase(PydanticClassRegistryMixin):
            pass

        type_adapter = TypeAdapter(EmptyBase)
        schema_dict = type_adapter.core_schema
        assert schema_dict["type"] == "any"

    @pytest.mark.sanity
    def test_trigger_base_rebuild(self, mocker: MockerFixture) -> None:
        """Verify _trigger_base_rebuild behaves correctly based on settings."""
        get_settings().enable_schema_rebuilding = False
        mock_reload = mocker.patch.object(PydanticBaseTestModel, "reload_schema")

        PydanticBaseTestModel._trigger_base_rebuild()
        mock_reload.assert_not_called()

        get_settings().enable_schema_rebuilding = True
        PydanticBaseTestModel._trigger_base_rebuild()
        mock_reload.assert_called_once()

        mock_reload.reset_mock()

        class NonReloadableBase(BaseModel):
            pass

        mocker.patch.object(
            PydanticBaseTestModel,
            "__pydantic_schema_base_type__",
            return_value=NonReloadableBase,
        )
        mock_rebuild = mocker.patch.object(NonReloadableBase, "model_rebuild")

        PydanticBaseTestModel._trigger_base_rebuild()
        mock_rebuild.assert_called_once_with(force=True)

    @pytest.mark.smoke
    def test_unregister_rebuilds_schema(self, mocker: MockerFixture) -> None:
        """Verify unregister rebuilds base schema and changes validation."""
        # Clean state has "text" and "image" registered.
        assert PydanticBaseTestModel.is_registered("text")

        # Test validation before unregistering
        data_text = {"model_type": "text", "content": "hello", "text_val": "world"}
        validated_object = PydanticBaseTestModel.model_validate(data_text)
        assert isinstance(validated_object, PydanticTextTestModel)

        # Unregister "text"
        mock_rebuild = mocker.spy(PydanticBaseTestModel, "_trigger_base_rebuild")
        PydanticBaseTestModel.unregister("text")

        mock_rebuild.assert_called_once()
        assert not PydanticBaseTestModel.is_registered("text")

        # Test validation after unregistering (should fail)
        with pytest.raises(ValidationError):
            PydanticBaseTestModel.model_validate(data_text)

        # Unregistering nonexistent raises ValueError
        with pytest.raises(ValueError, match="is not present"):
            PydanticBaseTestModel.unregister("text")

    @pytest.mark.regression
    def test_registry_extensions(self) -> None:
        """Validate object factory initialization and model_validate access paths."""
        # Expected keys check
        assert PydanticBaseTestModel.is_registered("text")
        assert PydanticBaseTestModel.is_registered("image")

        # Confirm instantiation resilience
        data_text = {
            "model_type": "text",
            "content": "test_content",
            "text_val": "resilient",
        }
        model_instance = PydanticBaseTestModel.model_validate(data_text)
        assert isinstance(model_instance, PydanticTextTestModel)
        assert model_instance.content == "test_content"
        assert model_instance.text_val == "resilient"


class TestRegistryManager:
    """Test suite for validating RegistryManager functionality."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensures a clean global settings state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.fixture(params=["manager_alpha", "manager_beta"])
    def valid_instances(self, request: pytest.FixtureRequest) -> RegistryManager:
        """Reusable parameterized fixture returning RegistryManager instances."""
        return RegistryManager()

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the structural signatures and contracts for RegistryManager."""
        assert hasattr(RegistryManager, "list_registries")
        assert inspect.ismethod(RegistryManager.list_registries) or inspect.isroutine(
            RegistryManager.list_registries
        )

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: RegistryManager) -> None:
        """Verify initialization behaves correctly."""
        assert isinstance(valid_instances, RegistryManager)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify passing arguments to standard initialization raises TypeError."""
        with pytest.raises(TypeError):
            RegistryManager(unexpected_argument="error")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify parameter-free instantiation works correctly."""
        manager_instance = RegistryManager()
        assert isinstance(manager_instance, RegistryManager)

    @pytest.mark.smoke
    def test_list_registries(self) -> None:
        """Verify list_registries returns mapped registry class names and paths."""
        ConcreteRegistry.clear_registry()
        PydanticBaseTestModel.clear_registry()

        # Register items
        @ConcreteRegistry.register("service_b")
        class ServiceB:
            pass

        @ConcreteRegistry.register("service_a")
        class ServiceA:
            pass

        @PydanticBaseTestModel.register("val_c")
        class ValC(PydanticBaseTestModel):
            pass

        registries_dict = RegistryManager.list_registries()

        # Check ConcreteRegistry sorting of keys
        assert "ConcreteRegistry" in registries_dict
        assert registries_dict["ConcreteRegistry"] == {
            "service_a": "tests.python.unit.test_registry.ServiceA",
            "service_b": "tests.python.unit.test_registry.ServiceB",
        }

        # Check PydanticBaseTestModel mapping
        assert "PydanticBaseTestModel" in registries_dict
        assert registries_dict["PydanticBaseTestModel"] == {
            "val_c": "tests.python.unit.test_registry.ValC",
        }

        # Clean up
        ConcreteRegistry.clear_registry()
        PydanticBaseTestModel.clear_registry()

    @pytest.mark.smoke
    def test_list_registries_empty(self) -> None:
        """Verify empty root registries are listed with empty mapping dict."""
        ConcreteRegistry.clear_registry()
        PydanticBaseTestModel.clear_registry()

        registries_dict = RegistryManager.list_registries()
        assert "ConcreteRegistry" in registries_dict
        assert registries_dict["ConcreteRegistry"] == {}
        assert "PydanticBaseTestModel" in registries_dict
        assert registries_dict["PydanticBaseTestModel"] == {}

    @pytest.mark.regression
    def test_discover_registries_auto_packages(self, mocker: MockerFixture) -> None:
        """Verify auto-import logic when settings.auto_packages is set."""
        # Setup settings with truthy auto_packages list
        get_settings().auto_packages = ["disdantic"]

        # Mock the auto_import_package_modules call on AutoImporterMixin
        mock_import_call = mocker.patch.object(
            AutoImporterMixin,
            "auto_import_package_modules",
            return_value=None,
        )

        # Invoke list_registries to trigger _discover_registries discovery flow
        RegistryManager.list_registries()

        # Assert that the auto_import was executed
        assert mock_import_call.call_count >= 1

    @pytest.mark.regression
    def test_resolve_val_path_fallback(self) -> None:
        """Verify fallback behavior for values without __name__ attributes."""
        ConcreteRegistry.clear_registry()

        # Register an instance object which has no __name__ (it uses __class__.__name__)
        instance_object = DummyClass()
        ConcreteRegistry.register_decorator(instance_object, name="dummy_inst")

        # List registries to trigger _resolve_val_path mapping
        registries_dict = RegistryManager.list_registries()

        expected_fallback_path = f"{DummyClass.__module__}.{DummyClass.__name__}"
        resolved_path = registries_dict["ConcreteRegistry"]["dummy_inst"]
        assert resolved_path == expected_fallback_path

        ConcreteRegistry.clear_registry()
