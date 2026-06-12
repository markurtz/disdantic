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

"""Integration tests for disdantic's singleton pattern module."""

from __future__ import annotations

import inspect
import os
import threading
import time
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, BeforeValidator

from disdantic.loading import LazyProxy
from disdantic.registry import RegistryMixin
from disdantic.settings import get_settings, reset_settings
from disdantic.singleton import SingletonMeta


class ComponentRegistry(RegistryMixin[type]):
    """Registry for testing singleton integration with registries."""


@ComponentRegistry.register("service_a")
class SingletonServiceA(metaclass=SingletonMeta):
    """A service that is a singleton and registered in ComponentRegistry."""

    def __init__(self, value: str = "default_a") -> None:
        self.value = value


@ComponentRegistry.register("service_b")
class SingletonServiceB(metaclass=SingletonMeta):
    """Another service that is a singleton and registered in ComponentRegistry."""

    def __init__(self, number: int = 42) -> None:
        self.number = number


class ConfiguredService(metaclass=SingletonMeta):
    """A singleton service that integrates with the settings module."""

    def __init__(self) -> None:
        settings = get_settings()
        self.default_schema_discriminator = settings.default_schema_discriminator
        self.project_root = settings.project_root


class StrictSingleton(metaclass=SingletonMeta):
    """A singleton service with validation checks inside initialization."""

    def __init__(self, score: int) -> None:
        if not isinstance(score, int):
            raise ValueError("Score must be an integer")
        self.score = score


class RequiredArgSingleton(metaclass=SingletonMeta):
    """A singleton service requiring positional arguments."""

    def __init__(self, required_val: str) -> None:
        self.required_val = required_val


class ConnectionPool(metaclass=SingletonMeta):
    """A database connection pool simulation for Pydantic integration."""

    def __init__(self, size: int = 10) -> None:
        self.size = size


def validate_connection_pool(value: Any) -> ConnectionPool:
    """Validator that maps input values to the ConnectionPool singleton."""
    if isinstance(value, ConnectionPool):
        return value
    if isinstance(value, dict):
        return ConnectionPool(**value)
    if isinstance(value, int):
        return ConnectionPool(size=value)
    raise ValueError("Invalid connection pool initialization parameters")


class DatabaseConfig(BaseModel):
    """Pydantic model that holds a reference to a singleton connection pool."""

    name: str
    pool: Annotated[ConnectionPool, BeforeValidator(validate_connection_pool)]

    model_config = {
        "arbitrary_types_allowed": True,
    }


class TestSingletonMeta:
    """Integration test suite for SingletonMeta metaclass boundaries."""

    @pytest.fixture(
        params=[
            SingletonServiceA,
            SingletonServiceB,
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> type:
        """Fixture providing valid variations of integrated singleton classes."""
        return request.param

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate structural contracts, method signatures, and class variables."""
        assert issubclass(SingletonMeta, type)
        assert hasattr(SingletonMeta, "_instances")
        assert hasattr(SingletonMeta, "_lock")

        # Verify public method signatures
        assert inspect.isfunction(SingletonMeta.clear_instances)
        assert inspect.ismethod(SingletonMeta.clear_all_singletons)

        # Verify call signature
        call_sig = inspect.signature(SingletonMeta.__call__)
        assert "args" in call_sig.parameters
        assert "kwargs" in call_sig.parameters

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: type) -> None:
        """Verify happy-path initialization intercepts and caches the instance."""
        # Setup: Reset singleton state
        SingletonMeta.clear_all_singletons()

        # Invoke: Create instances
        instance_one = valid_instances()
        instance_two = valid_instances()

        # Assert: Verify identity
        assert instance_one is instance_two

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify that validation failures inside init raise errors and don't cache."""
        # Setup: Reset singleton state
        SingletonMeta.clear_all_singletons()

        # Invoke & Assert: Passing invalid type
        with pytest.raises(ValueError, match="Score must be an integer"):
            StrictSingleton("not_an_int")

        # Assert that the invalid instance was not cached
        assert StrictSingleton not in SingletonMeta._instances

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization with missing parameters raises TypeError."""
        # Setup: Reset singleton state
        SingletonMeta.clear_all_singletons()

        # Invoke & Assert: Omit required positional argument
        with pytest.raises(TypeError):
            RequiredArgSingleton()

        # Assert that nothing was cached for the class
        assert RequiredArgSingleton not in SingletonMeta._instances

    @pytest.mark.regression
    def test_clear_instances(self) -> None:
        """Verify clear_instances evicts a specific class instance from the cache."""
        # Setup: Reset state and instantiate
        SingletonMeta.clear_all_singletons()
        instance_one = SingletonServiceA("initial")
        assert SingletonServiceA in SingletonMeta._instances

        # Invoke: Evict the service
        SingletonServiceA.clear_instances()

        # Assert: Verify eviction and that subsequent call creates a new instance
        assert SingletonServiceA not in SingletonMeta._instances
        instance_two = SingletonServiceA("new_value")
        assert instance_one is not instance_two
        assert instance_two.value == "new_value"

    @pytest.mark.regression
    def test_clear_all_singletons(self) -> None:
        """Verify clear_all_singletons wipes all tracked singleton instances."""
        # Setup: Reset state and instantiate multiple services
        SingletonMeta.clear_all_singletons()
        instance_a = SingletonServiceA()
        instance_b = SingletonServiceB()
        assert SingletonServiceA in SingletonMeta._instances
        assert SingletonServiceB in SingletonMeta._instances

        # Invoke: Clear all singletons
        SingletonMeta.clear_all_singletons()

        # Assert: Verify all instances are evicted
        assert len(SingletonMeta._instances) == 0
        new_instance_a = SingletonServiceA()
        new_instance_b = SingletonServiceB()
        assert instance_a is not new_instance_a
        assert instance_b is not new_instance_b

    @pytest.mark.regression
    def test_settings_integration(self) -> None:
        """Verify singleton integration with the settings and environment overrides."""
        # Setup: Reset state
        SingletonMeta.clear_all_singletons()
        reset_settings()

        # Verify initial config load
        service = ConfiguredService()
        assert service.default_schema_discriminator == "model_type"

        # Mutate environment variables to test settings precedence
        os.environ["DISDANTIC__DEFAULT_SCHEMA_DISCRIMINATOR"] = "custom_type"
        reset_settings()

        # Accessing the singleton again still returns the cached instance
        # with old settings because it is a singleton and has not been cleared
        service_cached = ConfiguredService()
        assert service_cached is service
        assert service_cached.default_schema_discriminator == "model_type"

        # Now clear the singleton to allow reloading settings
        ConfiguredService.clear_instances()

        # Instantiating now should load the updated settings
        service_reloaded = ConfiguredService()
        assert service_reloaded is not service
        assert service_reloaded.default_schema_discriminator == "custom_type"

        # Teardown: Clean up env variables and reset settings
        os.environ.pop("DISDANTIC__DEFAULT_SCHEMA_DISCRIMINATOR", None)
        reset_settings()
        SingletonMeta.clear_all_singletons()

    @pytest.mark.regression
    def test_lazy_loading_integration(self) -> None:
        """Verify deferred singleton instantiation and concurrent thread-safety.

        Validates correctness when resolved with LazyProxy.
        """
        # Setup: Reset state
        SingletonMeta.clear_all_singletons()

        class ThreadedService(metaclass=SingletonMeta):
            init_count = 0
            init_lock = threading.Lock()

            def __init__(self) -> None:
                with ThreadedService.init_lock:
                    ThreadedService.init_count += 1
                time.sleep(0.01)

        # Create a lazy proxy pointing to the singleton class factory
        proxy = LazyProxy(ThreadedService)

        # Assert that constructor is not called yet
        assert ThreadedService.init_count == 0
        assert ThreadedService not in SingletonMeta._instances

        instances: list[ThreadedService] = []
        list_lock = threading.Lock()

        def access_proxy() -> None:
            # Access proxy attribute to trigger resolution
            instance = proxy._resolve()  # noqa: SLF001
            with list_lock:
                instances.append(instance)

        # Spawn multiple concurrent threads accessing the proxy
        threads = [threading.Thread(target=access_proxy) for index in range(30)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Assert: Verify only one instance was created and __init__ ran exactly once
        assert len(instances) == 30
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance
        assert ThreadedService.init_count == 1

    @pytest.mark.regression
    def test_registry_and_factory_integration(self) -> None:
        """Verify integration with RegistryMixin, testing registration and lookup."""
        # Setup: Reset singleton and registry states
        SingletonMeta.clear_all_singletons()
        ComponentRegistry.clear_registry()

        # Re-register classes to ensure clean state
        ComponentRegistry.register_decorator(SingletonServiceA, name="service_a")
        ComponentRegistry.register_decorator(SingletonServiceB, name="service_b")

        # Resolve types from the registry
        resolved_class_a = ComponentRegistry.get_registered_object("service_a")
        resolved_class_b = ComponentRegistry.get_registered_object("service_b")

        assert resolved_class_a is SingletonServiceA
        assert resolved_class_b is SingletonServiceB

        # Instantiate resolved singleton types
        instance_a1 = resolved_class_a()
        instance_a2 = resolved_class_a()
        instance_b1 = resolved_class_b()
        instance_b2 = resolved_class_b()

        # Assert identity matching for singletons
        assert instance_a1 is instance_a2
        assert instance_b1 is instance_b2
        assert instance_a1 is not instance_b1

        # Case-insensitive resolution check
        resolved_lower = ComponentRegistry.get_registered_object("SERVICE_A")
        assert resolved_lower is SingletonServiceA

    @pytest.mark.regression
    def test_marshalling(self) -> None:
        """Verify singleton behavior inside Pydantic models.

        Checks behavior when validated and serialized.
        """
        # Setup: Reset singleton state
        SingletonMeta.clear_all_singletons()

        # Validate from primitive (int)
        model_a = DatabaseConfig.model_validate({"name": "primary_db", "pool": 15})
        assert isinstance(model_a.pool, ConnectionPool)
        assert model_a.pool.size == 15

        # Validate another model using a dictionary
        model_b = DatabaseConfig.model_validate(
            {"name": "secondary_db", "pool": {"size": 25}}
        )

        # Because ConnectionPool is a singleton, the second validation returns
        # the same cached pool instance created during model_a's validation,
        # ignoring new parameter overrides on the constructor.
        assert model_b.pool is model_a.pool
        assert model_b.pool.size == 15

        # Verify serialization (model_dump)
        dump_data = model_a.model_dump()
        assert dump_data["name"] == "primary_db"
        assert dump_data["pool"] is model_a.pool
