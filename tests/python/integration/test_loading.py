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
import sys
import threading
import time
import types
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from disdantic.loading import LazyLoader, LazyProxy


class TestLazyProxy:
    """Integration test suite for LazyProxy."""

    @pytest.fixture(
        params=[
            "dict_factory",
            "module_factory",
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> LazyProxy:
        """Fixture supplying properly initialized variations of LazyProxy."""
        if request.param == "dict_factory":
            return LazyProxy(lambda: {"status": "success"})
        return LazyProxy(lambda: importlib.import_module("sys"))

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate class structural contracts across integrated boundaries."""
        assert issubclass(LazyProxy, object)
        assert hasattr(LazyProxy, "__getattr__")
        assert hasattr(LazyProxy, "__dir__")
        assert hasattr(LazyProxy, "__repr__")
        assert hasattr(LazyProxy, "_resolve")

        init_sig = inspect.signature(LazyProxy.__init__)
        assert "factory" in init_sig.parameters

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: LazyProxy) -> None:
        """Verify initialization maps target correctly without invoking factory."""
        assert isinstance(valid_instances, LazyProxy)
        assert valid_instances._wrapped is None
        assert callable(valid_instances._factory)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify initialization with non-callable factory triggers TypeErrors.

        Resolution is forced on attribute access, raising TypeError.
        """
        proxy_instance = LazyProxy("non-callable")  # type: ignore
        assert proxy_instance._wrapped is None
        with pytest.raises(TypeError):
            # Accessing attribute forces resolution and triggers TypeError
            _unused = proxy_instance.status

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization fails when factory parameter is missing."""
        with pytest.raises(TypeError):
            LazyProxy()  # type: ignore

    @pytest.mark.sanity
    def test_getattr(self) -> None:
        """Verify accessing an attribute triggers resolution and returns it."""
        proxy_instance = LazyProxy(lambda: {"status": "success", "code": 200})
        assert proxy_instance._wrapped is None
        assert proxy_instance.get("status") == "success"
        assert proxy_instance._wrapped == {"status": "success", "code": 200}
        assert proxy_instance.get("code") == 200

    @pytest.mark.sanity
    def test_dir(self) -> None:
        """Verify dir() lists attributes of the resolved object."""
        proxy_instance = LazyProxy(lambda: {"status": "success"})
        assert proxy_instance._wrapped is None
        directory_list = dir(proxy_instance)
        assert "get" in directory_list
        assert "keys" in directory_list
        assert proxy_instance._wrapped == {"status": "success"}

    @pytest.mark.sanity
    def test_repr(self) -> None:
        """Verify string representations before and after resolution."""

        def factory_function() -> dict[str, str]:
            return {"status": "success"}

        proxy_instance = LazyProxy(factory_function)
        repr_before = repr(proxy_instance)
        assert "uninitialized factory" in repr_before
        assert "LazyProxy" in repr_before

        assert proxy_instance.get("status") == "success"
        assert repr(proxy_instance) == repr({"status": "success"})

    @pytest.mark.regression
    def test_thread_safety(self) -> None:
        """Verify thread safety and double-checked locking of proxy resolution."""
        call_count = 0
        execution_lock = threading.Lock()

        def slow_factory() -> types.SimpleNamespace:
            nonlocal call_count
            with execution_lock:
                call_count += 1
            # Delay to encourage concurrency issues if lock fails
            time.sleep(0.05)
            return types.SimpleNamespace(status="success")

        proxy_instance = LazyProxy(slow_factory)
        results: list[str] = []

        def target_thread() -> None:
            # Retrieve attribute to trigger resolution
            results.append(proxy_instance.status)

        threads_list = [threading.Thread(target=target_thread) for _idx in range(10)]
        for thread_item in threads_list:
            thread_item.start()
        for thread_item in threads_list:
            thread_item.join()

        assert len(results) == 10
        assert all(res_val == "success" for res_val in results)
        assert call_count == 1

    @pytest.mark.regression
    def test_factory_returns_none(self) -> None:
        """Verify that a factory returning None is cached and only called once."""
        call_count = 0

        def factory_returning_none() -> None:
            nonlocal call_count
            call_count += 1

        proxy_instance = LazyProxy(factory_returning_none)
        assert proxy_instance._wrapped is None
        assert not proxy_instance._resolved

        # Trigger resolution
        resolved = proxy_instance._resolve()
        assert resolved is None
        assert proxy_instance._resolved
        assert call_count == 1

        # Retrieve again, count should still be 1
        resolved_again = proxy_instance._resolve()
        assert resolved_again is None
        assert call_count == 1


class TestLazyLoader:
    """Integration test suite for LazyLoader class."""

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate class structural contracts across integrated boundaries."""
        assert issubclass(LazyLoader, object)
        assert hasattr(LazyLoader, "module")
        assert hasattr(LazyLoader, "class_attributes")
        assert hasattr(LazyLoader, "definition")
        assert hasattr(LazyLoader, "load_module_proxy")

    @pytest.mark.sanity
    def test_definition(self) -> None:
        """Verify definition helper wraps closures in LazyProxy instances."""
        proxy_instance = LazyLoader.definition(lambda: {"status": "success"})
        assert isinstance(proxy_instance, LazyProxy)
        assert proxy_instance._wrapped is None
        assert proxy_instance.get("status") == "success"

    @pytest.mark.regression
    def test_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify decorator for lazy-loading module subpackages on demand."""
        package_name = "test_lazy_pkg_int"
        mock_package = types.ModuleType(package_name)
        monkeypatch.setitem(sys.modules, package_name, mock_package)

        decorator_fn = LazyLoader.module(package_name)
        lazy_module = decorator_fn(mock_package)

        assert sys.modules[package_name] is lazy_module

        submodule_name = f"{package_name}.submod"
        mock_submodule = types.ModuleType(submodule_name)

        with patch("importlib.import_module") as mock_import:
            mock_import.return_value = mock_submodule
            lazy_any: Any = lazy_module
            resolved = lazy_any.submod
            mock_import.assert_called_once_with(submodule_name)
            assert resolved is mock_submodule

    @pytest.mark.regression
    def test_module_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify decorator attribute failures propagate as AttributeError.

        This triggers when dynamic module imports encounter ImportError.
        """
        package_name = "test_lazy_pkg_int_error"
        mock_package = types.ModuleType(package_name)
        monkeypatch.setitem(sys.modules, package_name, mock_package)

        decorator_fn = LazyLoader.module(package_name)
        lazy_module = decorator_fn(mock_package)

        with (
            patch("importlib.import_module", side_effect=ImportError("Import failed")),
            pytest.raises(
                AttributeError,
                match=f"Module '{package_name}' has no attribute 'submod'",
            ),
        ):
            _unused = lazy_module.submod

    @pytest.mark.regression
    def test_class_attributes(self) -> None:
        """Verify binding descriptor mapping to class attributes on access.

        Ensures descriptors resolve correctly on both standard classes and
        Pydantic models.
        """
        call_count = 0

        def my_factory() -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            return {"status": "resolved"}

        @LazyLoader.class_attributes(
            {
                "sys_module": "sys",
                "lazy_val": my_factory,
            }
        )
        class ContainerClass:
            sys_module: Any
            lazy_val: Any

        container_instance = ContainerClass()
        assert call_count == 0
        assert container_instance.sys_module is sys
        assert container_instance.lazy_val == {"status": "resolved"}
        assert call_count == 1

        # Subsequent access does not re-invoke factory
        assert container_instance.lazy_val == {"status": "resolved"}
        assert call_count == 1

        # Test compatibility with Pydantic BaseModel integration
        @LazyLoader.class_attributes(
            {
                "sys_module": "sys",
            }
        )
        class ContainerBaseModel(BaseModel):
            regular_field: str

        model_instance = ContainerBaseModel(regular_field="value")
        model_any: Any = model_instance
        assert model_any.sys_module is sys
        assert model_instance.model_dump() == {"regular_field": "value"}

    @pytest.mark.regression
    def test_load_module_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify dynamic load of standard library module using load_module_proxy."""
        # Temporarily clear math to ensure we are testing spec loading behavior
        if "math" in sys.modules:
            monkeypatch.delitem(sys.modules, "math")

        lazy_math = LazyLoader.load_module_proxy("math")
        assert sys.modules["math"] is lazy_math

        # Math attribute read executes spec and loads module
        assert lazy_math.pi > 3.0

    @pytest.mark.regression
    def test_load_module_proxy_already_loaded(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify load_module_proxy directly returns existing entry if loaded.

        If a module is already registered in sys.modules, we skip spec creation.
        """
        mock_module = types.ModuleType("already_loaded_module")
        monkeypatch.setitem(sys.modules, "already_loaded_module", mock_module)

        resolved = LazyLoader.load_module_proxy("already_loaded_module")
        assert resolved is mock_module

    @pytest.mark.regression
    def test_load_module_proxy_invalid(self) -> None:
        """Verify load_module_proxy raises ModuleNotFoundError on invalid spec.

        If the module cannot be resolved, an error is raised.
        """
        with pytest.raises(ModuleNotFoundError):
            LazyLoader.load_module_proxy("non_existent_module_xyz")
