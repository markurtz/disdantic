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

"""End-to-End tests for RegistryMixin and PydanticClassRegistryMixin."""

from __future__ import annotations

from typing import Literal

import pytest

import disdantic
from disdantic.exceptions import AutoPopulationError, RegistryCollisionError
from disdantic.registry import (
    PydanticClassRegistryMixin,
    RegistryManager,
    RegistryMixin,
)


class ServiceRegistry(RegistryMixin[type]):
    """Custom registry for testing RegistryMixin functionality."""


class PydanticServiceRegistry(PydanticClassRegistryMixin):
    """Custom registry for testing PydanticClassRegistryMixin functionality."""

    model_type: str
    content: str


class DummyClass:
    """Dummy class used for registration targets in tests."""


class TestRegistryMixin:
    """End-to-End test suite for registry mixin capabilities."""

    @pytest.fixture(params=["service", "pydantic"])
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> type[RegistryMixin[type]] | type[PydanticServiceRegistry]:
        """Provide isolated and cleared registry classes."""
        if request.param == "service":
            ServiceRegistry.clear_registry()
            return ServiceRegistry
        PydanticServiceRegistry.clear_registry()
        return PydanticServiceRegistry

    @pytest.mark.smoke
    def test_environment_contracts(self) -> None:
        """Validate structural environment contracts and API presence."""
        assert disdantic.__version__ is not None
        assert issubclass(ServiceRegistry, RegistryMixin)
        assert issubclass(PydanticServiceRegistry, PydanticClassRegistryMixin)
        assert hasattr(ServiceRegistry, "register")
        assert hasattr(ServiceRegistry, "unregister")
        assert hasattr(ServiceRegistry, "clear_registry")

    @pytest.mark.smoke
    def test_initialization(
        self,
        valid_instances: type[RegistryMixin[type]] | type[PydanticServiceRegistry],
    ) -> None:
        """Verify registry starts up in a clean, unpopulated state."""
        assert len(valid_instances.registry) == 0
        assert not valid_instances.registry_populated

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass invalid naming types to verify registration blocks."""
        # Non-string, non-sequence key raises ValueError
        with pytest.raises(ValueError, match="Unsupported naming format"):
            ServiceRegistry.register_decorator(DummyClass, name=123)  # type: ignore

        # Sequence containing non-string key raises TypeError
        with pytest.raises(TypeError, match="Registry keys must explicitly be strings"):
            ServiceRegistry.register_decorator(DummyClass, name=["valid_name", 123])  # type: ignore

        # Non-BaseModel subclass registered in Pydantic registry
        with pytest.raises(TypeError, match="must extend Pydantic BaseModel"):
            PydanticServiceRegistry.register_decorator(DummyClass, name="invalid_type")

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify unregistering missing key triggers a ValueError."""
        with pytest.raises(ValueError, match="is not present in the"):
            ServiceRegistry.unregister("non_existent_key")

    @pytest.mark.smoke
    def test_subclass_registration_retrieval(self) -> None:
        """Verify subclass registration via decorators and direct invocation."""
        ServiceRegistry.clear_registry()

        # 1. Named decorator: @register("name")
        @ServiceRegistry.register("custom_service")
        class MyService:
            pass

        # 2. Nameless decorator: @register()
        @ServiceRegistry.register()
        class NamelessService:
            pass

        # 3. Direct registration (without a decorator)
        class DirectService:
            pass

        ServiceRegistry.register_decorator(DirectService, name="direct_key")

        # Assertions
        assert ServiceRegistry.is_registered("custom_service") is True
        assert ServiceRegistry.get_registered_object("custom_service") is MyService

        assert ServiceRegistry.is_registered("NamelessService") is True
        assert (
            ServiceRegistry.get_registered_object("NamelessService") is NamelessService
        )

        assert ServiceRegistry.is_registered("direct_key") is True
        assert ServiceRegistry.get_registered_object("direct_key") is DirectService

        # Cleanup
        ServiceRegistry.clear_registry()

    @pytest.mark.regression
    def test_namespace_collision_prevention(self) -> None:
        """Verify double registration on the same key raises collision error."""
        ServiceRegistry.clear_registry()

        @ServiceRegistry.register("service_key")
        class FirstService:
            pass

        class SecondService:
            pass

        with pytest.raises(RegistryCollisionError, match="Collision detected"):
            ServiceRegistry.register_decorator(SecondService, name="service_key")

        # Verify that original service is still bound to the key
        assert ServiceRegistry.get_registered_object("service_key") is FirstService

        # Cleanup
        ServiceRegistry.clear_registry()

    @pytest.mark.smoke
    def test_subclass_unregistration_and_purging(self) -> None:
        """Verify de-registration and purging of active namespaces."""
        ServiceRegistry.clear_registry()

        @ServiceRegistry.register("service_key")
        class MyService:
            pass

        # Unregister once
        ServiceRegistry.unregister("service_key")
        assert ServiceRegistry.is_registered("service_key") is False

        # Unregister twice should raise ValueError
        with pytest.raises(ValueError, match="is not present in the"):
            ServiceRegistry.unregister("service_key")

        # Clear registry
        ServiceRegistry.register_decorator(MyService, name="service_key")
        ServiceRegistry.clear_registry()
        assert len(ServiceRegistry.registered_objects()) == 0

    @pytest.mark.sanity
    def test_case_insensitive_lookups(self) -> None:
        """Verify case-insensitivity in all query and lookup routines."""
        ServiceRegistry.clear_registry()

        @ServiceRegistry.register("CamelCaseKey")
        class MyService:
            pass

        assert ServiceRegistry.is_registered("CamelCaseKey") is True
        assert ServiceRegistry.is_registered("camelcasekey") is True
        assert ServiceRegistry.is_registered("CAMELCASEKEY") is True

        assert ServiceRegistry.get_registered_object("camelcasekey") is MyService
        assert ServiceRegistry.get_registered_object("CAMELCASEKEY") is MyService

        # Cleanup
        ServiceRegistry.clear_registry()

    @pytest.mark.sanity
    def test_marshalling(
        self,
        valid_instances: type[RegistryMixin[type]] | type[PydanticServiceRegistry],
    ) -> None:
        """Verify serialization and validation boundaries for Pydantic models."""
        if not issubclass(valid_instances, PydanticClassRegistryMixin):
            pytest.skip("Marshalling only applies to PydanticClassRegistryMixin")

        @valid_instances.register("text")
        class TextService(PydanticServiceRegistry):
            model_type: Literal["text"] = "text"
            text_val: str

        # Create model instance
        instance = TextService(content="message content", text_val="hello")

        # model_dump check
        payload = instance.model_dump()
        assert isinstance(payload, dict)
        assert payload["model_type"] == "text"
        assert payload["content"] == "message content"
        assert payload["text_val"] == "hello"

        # model_validate check
        validated = valid_instances.model_validate(payload)
        assert isinstance(validated, TextService)
        assert validated.text_val == "hello"
        assert validated.content == "message content"

        # Case-insensitive discriminator lookup on validation input
        mixed_payload = {
            "model_type": "TeXt",
            "content": "message content",
            "text_val": "hello",
        }
        validated_mixed = valid_instances.model_validate(mixed_payload)
        assert isinstance(validated_mixed, TextService)
        assert validated_mixed.model_type == "text"

    @pytest.mark.regression
    def test_dynamic_flow_registry(self) -> None:
        """Verify dynamic resolution and global mapping indexing via RegistryManager."""
        ServiceRegistry.clear_registry()
        PydanticServiceRegistry.clear_registry()

        @ServiceRegistry.register("service_a")
        class ServiceOne:
            pass

        @PydanticServiceRegistry.register("pydantic_b")
        class PydanticOne(PydanticServiceRegistry):
            model_type: Literal["pydantic_b"] = "pydantic_b"

        registries = RegistryManager.list_registries()

        assert "ServiceRegistry" in registries
        assert "service_a" in registries["ServiceRegistry"]

        assert "PydanticServiceRegistry" in registries
        assert "pydantic_b" in registries["PydanticServiceRegistry"]

        # Cleanup
        ServiceRegistry.clear_registry()
        PydanticServiceRegistry.clear_registry()

    @pytest.mark.smoke
    def test_registered_classes(self) -> None:
        """Verify retrieval of registered classes from PydanticClassRegistryMixin."""
        PydanticServiceRegistry.clear_registry()

        @PydanticServiceRegistry.register("text_class")
        class TextService(PydanticServiceRegistry):
            model_type: Literal["text_class"] = "text_class"

        classes = PydanticServiceRegistry.registered_classes()
        assert TextService in classes

        PydanticServiceRegistry.clear_registry()
        with pytest.raises(Exception, match="No objects are currently present"):
            PydanticServiceRegistry.registered_classes()

    @pytest.mark.sanity
    def test_auto_populate_disabled(self) -> None:
        """Verify auto_populate_registry raises AutoPopulationError.

        Discovery must be disabled to trigger this check.
        """
        ServiceRegistry.registry_auto_discovery = False
        with pytest.raises(AutoPopulationError, match="Auto-population rejected"):
            ServiceRegistry.auto_populate_registry()

    @pytest.mark.sanity
    def test_auto_discovery_status(self) -> None:
        """Verify is_auto_discovery_enabled returns correct status."""
        ServiceRegistry.registry_auto_discovery = False
        assert ServiceRegistry.is_auto_discovery_enabled() is False

        ServiceRegistry.registry_auto_discovery = True
        assert ServiceRegistry.is_auto_discovery_enabled() is True

        # Restore
        ServiceRegistry.registry_auto_discovery = False
