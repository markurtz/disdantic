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

"""End-to-end tests for Concurrency Safe Lazy Proxy Factory (US-6.1)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from disdantic.loading import LazyProxy
from disdantic.registry import RegistryMixin


class DictWithAttributes(dict[str, Any]):
    """Helper class to allow attribute access on dictionaries."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(name) from err


class TestConcurrencySafeLazyProxyFactory:
    """E2E test suite validating thread-safe lazy proxy factories."""

    @pytest.fixture(params=["list_data", "dict_data"])
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> tuple[Callable[[], Any], LazyProxy, dict[str, Any]]:
        """Provide parameterized factories and initialized LazyProxy objects."""
        state = {"call_count": 0}

        if request.param == "list_data":

            def factory() -> list[str]:
                state["call_count"] += 1
                return ["val_one", "val_two"]

        else:

            def factory() -> DictWithAttributes:
                state["call_count"] += 1
                return DictWithAttributes({"key_one": "val_one"})

        proxy = LazyProxy(factory)
        return factory, proxy, state

    @pytest.mark.smoke
    def test_contract_and_environment(
        self,
        valid_instances: tuple[Callable[[], Any], LazyProxy, dict[str, Any]],
    ) -> None:
        """Validate structural environment contracts of LazyProxy."""
        _factory, proxy, _state = valid_instances
        assert isinstance(proxy, LazyProxy)
        assert hasattr(proxy, "_resolve")
        assert hasattr(proxy, "_lock")
        assert hasattr(proxy, "_factory")
        assert hasattr(proxy, "_wrapped")
        assert hasattr(proxy, "_resolved")
        assert isinstance(proxy._lock, type(threading.Lock()))

    @pytest.mark.smoke
    def test_initialization(
        self,
        valid_instances: tuple[Callable[[], Any], LazyProxy, dict[str, Any]],
    ) -> None:
        """Assert correct initial system wiring and state mapping."""
        _factory, proxy, state = valid_instances
        assert proxy._resolved is False
        assert proxy._wrapped is None
        assert state["call_count"] == 0

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify explicit system blockages when invalid factory values are passed."""
        proxy = LazyProxy(12345)  # type: ignore
        with pytest.raises(TypeError):
            proxy._resolve()

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify system boundary defense when critical parameters are omitted."""
        with pytest.raises(TypeError):
            LazyProxy()  # type: ignore

    @pytest.mark.sanity
    def test_concurrency_resolution(self) -> None:
        """Verify that concurrent queries trigger exactly one call.

        Under concurrent access from multiple threads, only one thread executes the
        factory block.
        """
        call_count = 0
        factory_started = threading.Event()
        factory_proceed = threading.Event()

        def slow_factory() -> DictWithAttributes:
            nonlocal call_count
            factory_started.set()
            factory_proceed.wait(timeout=5.0)
            call_count += 1
            return DictWithAttributes({"status": "ready"})

        proxy = LazyProxy(slow_factory)
        results: list[Any] = []
        threads: list[threading.Thread] = []

        def access_proxy() -> None:
            results.append(proxy.status)

        for _idx in range(5):
            thread = threading.Thread(target=access_proxy)
            threads.append(thread)
            thread.start()

        assert factory_started.wait(timeout=5.0)
        factory_proceed.set()

        for thread in threads:
            thread.join()

        assert call_count == 1
        assert len(results) == 5
        assert all(val == "ready" for val in results)

    @pytest.mark.regression
    def test_marshalling(
        self,
        valid_instances: tuple[Callable[[], Any], LazyProxy, dict[str, Any]],
    ) -> None:
        """Verify Pydantic model serialization and deserialization boundaries."""
        _factory, proxy, _state = valid_instances

        class TestModel(BaseModel):
            name: str
            items: list[str] | dict[str, str]

        model_factory_call_count = 0

        def model_factory() -> TestModel:
            nonlocal model_factory_call_count
            model_factory_call_count += 1
            resolved_data = proxy._resolve()
            return TestModel(name="wrapped_model", items=resolved_data)

        model_proxy = LazyProxy(model_factory)

        assert model_proxy._resolved is False
        assert model_factory_call_count == 0

        dumped_data = model_proxy.model_dump()
        assert model_proxy._resolved is True
        assert model_factory_call_count == 1
        assert dumped_data["name"] == "wrapped_model"

        validated_model = TestModel.model_validate(dumped_data)
        assert isinstance(validated_model, TestModel)
        assert validated_model.name == "wrapped_model"

    @pytest.mark.sanity
    def test_dynamic_resolution(
        self,
        valid_instances: tuple[Callable[[], Any], LazyProxy, dict[str, Any]],
    ) -> None:
        """Validate lazy proxy integration with dynamic registry workflows."""

        class E2EDynamicRegistry(RegistryMixin[type]):
            """Isolated dynamic registry for testing."""

        @E2EDynamicRegistry.register("target_class")
        class TargetClass:
            def get_message(self) -> str:
                return "hello_from_target"

        def get_instance() -> TargetClass:
            resolved_class = E2EDynamicRegistry.get_registered_object("target_class")
            assert resolved_class is not None
            return resolved_class()

        lazy_resolved_instance = LazyProxy(get_instance)

        assert lazy_resolved_instance._resolved is False

        message = lazy_resolved_instance.get_message()
        assert lazy_resolved_instance._resolved is True
        assert message == "hello_from_target"

        E2EDynamicRegistry.clear_registry()
