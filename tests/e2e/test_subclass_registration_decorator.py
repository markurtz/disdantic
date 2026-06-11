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

"""E2E tests for Subclass Registration Decorator."""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from pydantic import BaseModel

from disdantic.exceptions import RegistryCollisionError
from disdantic.registry import RegistryMixin


class PluginBase:
    """Base class for plugins registered in E2E tests."""


class TestSubclassRegistrationDecorator:
    """Test class encapsulating all decorator registration E2E user journeys."""

    @pytest.fixture(params=["alpha", "beta"])
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> type[RegistryMixin[type]]:
        """Supply isolated registry classes configured with different settings."""

        class DynamicRegistry(RegistryMixin[type]):
            """Isolated registry space created for test execution."""

        if request.param == "alpha":
            DynamicRegistry.registry_auto_discovery = True
            DynamicRegistry.auto_import_package_modules = classmethod(lambda cls: None)  # type: ignore
        else:
            DynamicRegistry.registry_auto_discovery = False

        # Ensure it is clear
        DynamicRegistry.clear_registry()
        return DynamicRegistry

    @pytest.mark.smoke
    def test_contract_and_environment(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Validate structural environment contracts and registry capabilities."""
        assert issubclass(valid_instances, RegistryMixin)
        assert hasattr(valid_instances, "registry")
        assert hasattr(valid_instances, "_lower_registry")
        assert inspect.isroutine(valid_instances.register)
        assert inspect.isroutine(valid_instances.register_decorator)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: type[RegistryMixin[type]]) -> None:
        """Assert correct initial system wiring and session startup state."""
        assert valid_instances.registry == {}
        assert valid_instances._lower_registry == {}
        assert valid_instances.registry_populated is False

    @pytest.mark.sanity
    def test_invalid_initialization_values(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Verify explicit system blockages on invalid construction parameters."""
        with pytest.raises(TypeError):
            valid_instances(unexpected_argument="failure_payload")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Verify registry initialization is safe without optional parameters."""
        instance = valid_instances()
        assert isinstance(instance, valid_instances)

    @pytest.mark.smoke
    def test_register_single_key(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Setup Context -> Execute -> Assert -> Teardown."""
        registry = valid_instances

        @registry.register("custom_key")
        class CustomPlugin(PluginBase):
            """Plugin registered under a specific custom key."""

        assert registry.get_registered_object("custom_key") is CustomPlugin
        assert registry.is_registered("custom_key") is True

        # Teardown
        registry.clear_registry()

    @pytest.mark.smoke
    def test_register_multiple_keys(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Registering a subclass under multiple keys registers it under all."""
        registry = valid_instances

        @registry.register(["key_one", "key_two"])
        class MultiKeyPlugin(PluginBase):
            """Plugin registered under multiple keys."""

        assert registry.get_registered_object("key_one") is MultiKeyPlugin
        assert registry.get_registered_object("key_two") is MultiKeyPlugin
        assert registry.is_registered("key_one") is True
        assert registry.is_registered("key_two") is True

        # Teardown
        registry.clear_registry()

    @pytest.mark.smoke
    def test_register_default_name(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Registering a subclass with no arguments defaults to subclass __name__."""
        registry = valid_instances

        @registry.register()
        class DefaultNamedPlugin(PluginBase):
            """Plugin registered without a name key, defaulting to class name."""

        registered = registry.get_registered_object("DefaultNamedPlugin")
        assert registered is DefaultNamedPlugin
        assert registry.is_registered("DefaultNamedPlugin") is True

        # Teardown
        registry.clear_registry()

    @pytest.mark.regression
    def test_register_collision_raises_error(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Assert duplicate registrations raise RegistryCollisionError."""
        registry = valid_instances

        @registry.register("colliding_key")
        class FirstPlugin(PluginBase):
            """First plugin registered with the colliding key."""

        with pytest.raises(RegistryCollisionError, match="Collision detected"):

            @registry.register("colliding_key")
            class SecondPlugin(PluginBase):
                """Second plugin attempting to register with the same key."""

        # Teardown
        registry.clear_registry()

    @pytest.mark.regression
    def test_register_decorator_invalid(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Assert registration decorator raises errors on invalid naming inputs."""
        registry = valid_instances

        class BadPlugin(PluginBase):
            """Plugin class that will fail registration due to name type."""

        with pytest.raises(ValueError, match="Unsupported naming format"):
            registry.register_decorator(BadPlugin, name=999)  # type: ignore

        err_key_msg = "Registry keys must explicitly be strings"
        with pytest.raises(ValueError, match=err_key_msg):
            registry.register_decorator(BadPlugin, name=["valid_key", 123])  # type: ignore

        # Teardown
        registry.clear_registry()

    @pytest.mark.sanity
    def test_marshalling(self, valid_instances: type[RegistryMixin[type]]) -> None:
        """Assert Pydantic marshalling boundaries for registry keys."""
        # Create a Pydantic model that utilizes the registry names
        registry = valid_instances

        @registry.register("json_parser")
        class JsonParserPlugin:
            """Simple plugin class."""

        class ParserConfig(BaseModel):
            """Config specifying a parser type dynamically resolved."""

            parser_type: str

            def resolve_parser(self) -> Any:
                """Resolve the registered class."""
                return registry.get_registered_object(self.parser_type)

        # Marshal from dict
        config_data = {"parser_type": "json_parser"}
        config_instance = ParserConfig.model_validate(config_data)
        assert config_instance.parser_type == "json_parser"
        assert config_instance.resolve_parser() is JsonParserPlugin

        # Marshal to dict
        dumped_data = config_instance.model_dump()
        assert dumped_data == {"parser_type": "json_parser"}

        # Teardown
        registry.clear_registry()

    @pytest.mark.sanity
    def test_dynamic_resolution(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Verify dynamic resolution of plugin subclasses inside user workflows."""
        registry = valid_instances

        @registry.register("math_plugin")
        class MathPlugin:
            """Plugin implementing standard run interface."""

            def execute(self, val_a: int, val_b: int) -> int:
                """Execute simple math."""
                return val_a + val_b

        # Resolve dynamically and execute
        resolved_class = registry.get_registered_object("math_plugin")
        assert resolved_class is not None

        plugin_instance = resolved_class()
        result_val = plugin_instance.execute(10, 20)
        assert result_val == 30

        # Teardown
        registry.clear_registry()
