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

"""E2E tests for Programmatic Clean and Unregistration."""

from __future__ import annotations

import inspect
import threading
import time
from typing import Any

import pytest
from pydantic import BaseModel

from disdantic.registry import RegistryMixin


class PluginBase:
    """Base class for plugins registered in E2E tests."""


class TestProgrammaticCleanAndUnregistration:
    """Test class encapsulating clean and unregistration E2E user journeys."""

    @pytest.fixture(params=["alpha", "beta"])
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> type[RegistryMixin[type]]:
        """Supply isolated registry classes configured with different settings."""

        class DynamicRegistry(RegistryMixin[type]):
            """Isolated registry space created for test execution."""

        DynamicRegistry.registry_auto_discovery = request.param == "alpha"
        DynamicRegistry.clear_registry()
        return DynamicRegistry

    @pytest.mark.smoke
    def test_contract_and_environment(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Validate structural environment contracts and unregistration signatures."""
        assert issubclass(valid_instances, RegistryMixin)
        assert inspect.isroutine(valid_instances.unregister)
        assert inspect.isroutine(valid_instances.clear_registry)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: type[RegistryMixin[type]]) -> None:
        """Assert correct initial wiring starts clean."""
        assert valid_instances.registry == {}
        assert valid_instances._lower_registry == {}
        assert valid_instances.registry_populated is False

    @pytest.mark.sanity
    def test_invalid_initialization_values(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Verify explicit system blockages on invalid construction parameters."""
        with pytest.raises(TypeError):
            valid_instances(unexpected_argument="fail")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Verify default constructor safety."""
        instance = valid_instances()
        assert isinstance(instance, valid_instances)

    @pytest.mark.smoke
    def test_unregister_removes_keys(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Assert calling unregister removes mappings (canonical & case-insensitive)."""
        registry = valid_instances

        @registry.register("CamelCaseKey")
        class TargetPlugin(PluginBase):
            """Plugin that will be unregistered."""

        assert registry.is_registered("CamelCaseKey") is True
        assert registry.is_registered("camelcasekey") is True

        # Unregister (case-insensitive check)
        registry.unregister("camelcasekey")

        assert registry.is_registered("CamelCaseKey") is False
        assert registry.is_registered("camelcasekey") is False
        assert "CamelCaseKey" not in registry.registry
        assert "camelcasekey" not in registry._lower_registry

        # Teardown
        registry.clear_registry()

    @pytest.mark.sanity
    def test_unregister_missing_raises_error(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Assert unregistering a missing key raises ValueError."""
        registry = valid_instances

        err_msg = "is not present in the DynamicRegistry registry"
        with pytest.raises(ValueError, match=err_msg):
            registry.unregister("non_existent_key")

    @pytest.mark.sanity
    def test_clear_registry_resets_all(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Assert clear_registry empties mappings, flags, and caches."""
        registry = valid_instances

        @registry.register("key_to_clear")
        class ClearPlugin(PluginBase):
            """Plugin to clear."""

        registry.registry_populated = True

        registry.clear_registry()

        assert registry.registry == {}
        assert registry._lower_registry == {}
        assert registry.registry_populated is False

    @pytest.mark.regression
    def test_unregister_thread_safety(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Assert concurrent registration and unregistration is thread-safe."""
        registry = valid_instances
        errors_list: list[Exception] = []

        class ThreadDummy:
            """Dummy class for thread registration."""

        def worker(thread_key: str) -> None:
            try:
                registry.register_decorator(ThreadDummy, name=thread_key)
                time.sleep(0.001)
                assert registry.is_registered(thread_key)
                registry.unregister(thread_key)
                assert not registry.is_registered(thread_key)
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

        assert not errors_list, f"Concurrent execution errors: {errors_list}"
        assert not registry.registry

        # Teardown
        registry.clear_registry()

    @pytest.mark.sanity
    def test_marshalling(self, valid_instances: type[RegistryMixin[type]]) -> None:
        """Assert marshalling bounds after unregistration/clearing."""
        registry = valid_instances

        @registry.register("temp_plugin")
        class TempPlugin:
            """Temporary plugin."""

        class TempConfig(BaseModel):
            """Pydantic configuration model."""

            plugin_name: str

            def resolve_plugin(self) -> Any:
                """Resolve the registered class."""
                return registry.get_registered_object(self.plugin_name)

        config = TempConfig.model_validate({"plugin_name": "temp_plugin"})
        assert config.resolve_plugin() is TempPlugin

        # Unregister the plugin
        registry.unregister("temp_plugin")

        # Now resolution should fail (return None)
        assert config.resolve_plugin() is None

        # Teardown
        registry.clear_registry()

    @pytest.mark.sanity
    def test_dynamic_resolution(
        self, valid_instances: type[RegistryMixin[type]]
    ) -> None:
        """Verify dynamic resolution behaves correctly after registry clearing."""
        registry = valid_instances

        @registry.register("workflow_plugin")
        class WorkflowPlugin:
            """Workflow execution module."""

        assert registry.get_registered_object("workflow_plugin") is WorkflowPlugin

        registry.clear_registry()

        assert registry.get_registered_object("workflow_plugin") is None
