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

"""Unit tests for the singleton module."""

from __future__ import annotations

import inspect
import threading
import time

import pytest

from disdantic import singleton
from disdantic.singleton import SingletonMeta


class DummyServiceA(metaclass=SingletonMeta):
    """A simple service with default init arguments."""

    def __init__(self, value: str = "default") -> None:
        self.value = value


class DummyServiceB(metaclass=SingletonMeta):
    """A service with multiple parameters and types."""

    def __init__(self, number: int = 42, flag: bool = False) -> None:
        self.number = number
        self.flag = flag


class RequiredArgService(metaclass=SingletonMeta):
    """A service requiring a positional argument."""

    def __init__(self, required_val: str) -> None:
        self.required_val = required_val


class StrictService(metaclass=SingletonMeta):
    """A service with validation checks inside init."""

    def __init__(self, value: int) -> None:
        if not isinstance(value, int):
            raise ValueError("value must be an integer")
        self.value = value


class TestSingletonMeta:
    """Test suite for the SingletonMeta metaclass."""

    @pytest.fixture(
        params=[
            DummyServiceA,
            DummyServiceB,
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> type:
        """Fixture providing varied singleton classes (instances of SingletonMeta)."""
        return request.param

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the class signature and metaclass traits."""
        assert issubclass(SingletonMeta, type)
        assert hasattr(SingletonMeta, "_instances")
        assert hasattr(SingletonMeta, "_lock")

        # Verify method signatures
        assert inspect.isfunction(SingletonMeta.clear_instances)
        assert inspect.ismethod(SingletonMeta.clear_all_singletons)

        # Verify metaclass call signature
        call_signature = inspect.signature(SingletonMeta.__call__)
        assert "args" in call_signature.parameters
        assert "kwargs" in call_signature.parameters

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: type) -> None:
        """Verify that instantiation caches and returns the exact same instance."""
        # Setup: Reset singleton state
        SingletonMeta.clear_all_singletons()

        # Invoke: Create instances
        instance_one = valid_instances()
        instance_two = valid_instances()

        # Assert: Verify identity
        assert instance_one is instance_two

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify initialization with malformed values fails custom validation."""
        # Setup: Reset singleton state
        SingletonMeta.clear_all_singletons()

        # Invoke & Assert: Passing invalid parameter type
        with pytest.raises(ValueError, match="value must be an integer"):
            StrictService("not_an_integer")

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization with missing required parameters raises TypeError."""
        # Setup: Reset singleton state
        SingletonMeta.clear_all_singletons()

        # Invoke & Assert: Omit required argument
        with pytest.raises(TypeError):
            RequiredArgService()

    @pytest.mark.sanity
    def test_clear_instances(self) -> None:
        """Verify clear_instances evicts the instance of a class from cache."""
        # Setup: Reset state and instantiate
        SingletonMeta.clear_all_singletons()
        instance_one = DummyServiceA("one")
        assert DummyServiceA in SingletonMeta._instances

        # Invoke: Clear instances for the class
        DummyServiceA.clear_instances()

        # Assert: Verify eviction and subsequent instantiation creates new instance
        assert DummyServiceA not in SingletonMeta._instances
        instance_two = DummyServiceA("two")
        assert instance_one is not instance_two
        assert instance_two.value == "two"

    @pytest.mark.regression
    def test_clear_all_singletons(self) -> None:
        """Verify clear_all_singletons wipes all tracked singleton instances."""
        # Setup: Reset state and instantiate multiple classes
        SingletonMeta.clear_all_singletons()
        instance_a = DummyServiceA()
        instance_b = DummyServiceB()
        assert DummyServiceA in SingletonMeta._instances
        assert DummyServiceB in SingletonMeta._instances

        # Invoke: Clear all singletons
        SingletonMeta.clear_all_singletons()

        # Assert: Verify both are evicted
        assert len(SingletonMeta._instances) == 0
        new_instance_a = DummyServiceA()
        new_instance_b = DummyServiceB()
        assert instance_a is not new_instance_a
        assert instance_b is not new_instance_b

    @pytest.mark.regression
    def test_thread_safety(self) -> None:
        """Verify thread-safe initialization behavior and double-checked locking."""
        # Setup: Reset state
        SingletonMeta.clear_all_singletons()

        class ThreadedService(metaclass=SingletonMeta):
            init_count = 0
            init_lock = threading.Lock()

            def __init__(self) -> None:
                with self.init_lock:
                    type(self).init_count += 1
                # Sleep to induce race condition
                time.sleep(0.01)

        instances: list[ThreadedService] = []
        list_lock = threading.Lock()

        def target() -> None:
            instance = ThreadedService()
            with list_lock:
                instances.append(instance)

        # Invoke: Spawn 50 threads trying to instantiate simultaneously
        threads = [threading.Thread(target=target) for index in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Assert: Verify only one instance was created and __init__ ran exactly once
        assert len(instances) == 50
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance
        assert ThreadedService.init_count == 1


@pytest.mark.smoke
def test_all_exports() -> None:
    """Verify the exported components of the module."""
    assert singleton.__all__ == ["SingletonMeta"]
