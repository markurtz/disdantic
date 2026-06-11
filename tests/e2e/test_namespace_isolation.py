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

"""E2E tests for Namespace Isolation."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from disdantic.registry import RegistryMixin


class PluginBase:
    """Base class for plugins registered in E2E tests."""


class TestNamespaceIsolation:
    """Test class encapsulating namespace isolation E2E user journeys."""

    @pytest.fixture(params=["alpha", "beta"])
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]]:
        """Supply a pair of isolated registry classes for E2E tests."""

        class RegistryOne(RegistryMixin[type]):
            """First isolated registry subclass."""

        class RegistryTwo(RegistryMixin[type]):
            """Second isolated registry subclass."""

        RegistryOne.registry_auto_discovery = request.param == "alpha"
        RegistryTwo.registry_auto_discovery = request.param == "alpha"

        RegistryOne.clear_registry()
        RegistryTwo.clear_registry()

        return RegistryOne, RegistryTwo

    @pytest.mark.smoke
    def test_contract_and_environment(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Validate structural environment contracts and memory separation."""
        registry_one, registry_two = valid_instances

        assert issubclass(registry_one, RegistryMixin)
        assert issubclass(registry_two, RegistryMixin)

        # Ensure registries are not the same dictionary in memory
        assert registry_one.registry is not registry_two.registry
        assert registry_one._lower_registry is not registry_two._lower_registry

    @pytest.mark.smoke
    def test_initialization(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Assert isolated registries start empty."""
        registry_one, registry_two = valid_instances

        assert registry_one.registry == {}
        assert registry_two.registry == {}

    @pytest.mark.sanity
    def test_invalid_initialization_values(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Verify explicit system blockages on invalid construction parameters."""
        registry_one, registry_two = valid_instances
        with pytest.raises(TypeError):
            registry_one(unexpected_argument="fail")  # type: ignore
        with pytest.raises(TypeError):
            registry_two(unexpected_argument="fail")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Verify default constructors remain safe for both namespaces."""
        registry_one, registry_two = valid_instances
        instance_one = registry_one()
        instance_two = registry_two()
        assert isinstance(instance_one, registry_one)
        assert isinstance(instance_two, registry_two)

    @pytest.mark.smoke
    def test_namespace_isolation_active(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Assert registrations in one registry space do not leak into another."""
        registry_one, registry_two = valid_instances

        @registry_one.register("alert_plugin")
        class AlertPlugin(PluginBase):
            """Plugin registered exclusively on registry one."""

        assert registry_one.is_registered("alert_plugin") is True
        assert registry_two.is_registered("alert_plugin") is False
        assert registry_one.get_registered_object("alert_plugin") is AlertPlugin
        assert registry_two.get_registered_object("alert_plugin") is None

        # Teardown
        registry_one.clear_registry()
        registry_two.clear_registry()

    @pytest.mark.smoke
    def test_same_name_different_registries(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Assert identical key names on different registries do not collide."""
        registry_one, registry_two = valid_instances

        @registry_one.register("email")
        class EmailAlert(PluginBase):
            """Plugin for emailing alerts."""

        @registry_two.register("email")
        class EmailTask(PluginBase):
            """Plugin for email tasks."""

        assert registry_one.get_registered_object("email") is EmailAlert
        assert registry_two.get_registered_object("email") is EmailTask

        # Teardown
        registry_one.clear_registry()
        registry_two.clear_registry()

    @pytest.mark.sanity
    def test_marshalling(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Assert Pydantic routes dynamically to the correct namespace."""
        registry_one, registry_two = valid_instances

        @registry_one.register("slack")
        class SlackAlert:
            """Slack alert channel."""

        @registry_two.register("slack")
        class SlackTask:
            """Slack job runner."""

        class MultiRouteConfig(BaseModel):
            """Pydantic config executing targets across isolated domains."""

            route_key: str

            def resolve_alert(self) -> Any:
                """Resolve alert from registry one."""
                return registry_one.get_registered_object(self.route_key)

            def resolve_task(self) -> Any:
                """Resolve task from registry two."""
                return registry_two.get_registered_object(self.route_key)

        config_instance = MultiRouteConfig.model_validate({"route_key": "slack"})
        assert config_instance.resolve_alert() is SlackAlert
        assert config_instance.resolve_task() is SlackTask

        # Teardown
        registry_one.clear_registry()
        registry_two.clear_registry()

    @pytest.mark.sanity
    def test_dynamic_resolution(
        self,
        valid_instances: tuple[type[RegistryMixin[type]], type[RegistryMixin[type]]],
    ) -> None:
        """Verify dynamic same-named key execution resolves per namespace."""
        registry_one, registry_two = valid_instances

        @registry_one.register("formatter")
        class UpperFormatter:
            """Formats text to uppercase."""

            def format_text(self, text_input: str) -> str:
                """Uppercase implementation."""
                return text_input.upper()

        @registry_two.register("formatter")
        class LowerFormatter:
            """Formats text to lowercase."""

            def format_text(self, text_input: str) -> str:
                """Lowercase implementation."""
                return text_input.lower()

        formatter_one_class = registry_one.get_registered_object("formatter")
        formatter_two_class = registry_two.get_registered_object("formatter")

        assert formatter_one_class is not None
        assert formatter_two_class is not None

        formatter_one = formatter_one_class()
        formatter_two = formatter_two_class()

        assert formatter_one.format_text("Hello") == "HELLO"
        assert formatter_two.format_text("Hello") == "hello"

        # Teardown
        registry_one.clear_registry()
        registry_two.clear_registry()
