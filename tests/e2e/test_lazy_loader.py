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

import inspect
import sys
import threading
import time
import types
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from disdantic.loading import LazyLoader, LazyProxy


class TestLazyProxyWorkflow:
    """End-to-End test suite for validating LazyProxy workflows."""

    @pytest.fixture(
        params=[
            "dict_factory",
            "list_factory",
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> LazyProxy:
        """Fixture supplying properly initialized variations of LazyProxy."""
        if request.param == "dict_factory":
            return LazyProxy(lambda: {"status": "success", "code": 200})
        return LazyProxy(lambda: [100, 200, 300])

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate class structural contracts across integrated boundaries."""
        assert issubclass(LazyProxy, object)
        assert hasattr(LazyProxy, "__getattr__")
        assert hasattr(LazyProxy, "__dir__")
        assert hasattr(LazyProxy, "__repr__")
        assert hasattr(LazyProxy, "_resolve")

        init_sig = inspect.signature(LazyProxy.__init__)
        assert "factory" in init_sig.parameters

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: LazyProxy) -> None:
        """Verify initialization maps target correctly without invoking factory."""
        assert isinstance(valid_instances, LazyProxy)
        assert valid_instances._wrapped is None
        assert not valid_instances._resolved
        assert callable(valid_instances._factory)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify initialization with non-callable factory triggers TypeErrors.

        Resolution is forced on attribute access, raising TypeError.
        """
        proxy_instance = LazyProxy("non-callable-factory")  # type: ignore
        assert proxy_instance._wrapped is None
        with pytest.raises(TypeError):
            # Accessing attribute forces resolution and triggers TypeError
            _unused = proxy_instance.status

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization fails when factory parameter is missing."""
        with pytest.raises(TypeError):
            LazyProxy()  # type: ignore

    @pytest.mark.smoke
    def test_lazy_proxy_thread_safety(self) -> None:
        """Verify thread safety and double-checked locking of proxy resolution."""
        call_counter = 0
        counting_lock = threading.Lock()

        def slow_factory() -> types.SimpleNamespace:
            nonlocal call_counter
            with counting_lock:
                call_counter += 1
            # Delay to encourage concurrency issues if lock fails
            time.sleep(0.05)
            return types.SimpleNamespace(status="success")

        proxy_instance = LazyProxy(slow_factory)

        # Assert factory has not been executed yet
        assert call_counter == 0
        assert not proxy_instance._resolved

        results_list: list[str] = []

        def target_thread() -> None:
            # Retrieve attribute to trigger resolution
            results_list.append(proxy_instance.status)

        threads_list = [
            threading.Thread(target=target_thread) for _ignored in range(10)
        ]
        for thread_item in threads_list:
            thread_item.start()
        for thread_item in threads_list:
            thread_item.join()

        assert len(results_list) == 10
        assert all(res_val == "success" for res_val in results_list)
        assert call_counter == 1

    @pytest.mark.regression
    def test_factory_returns_none(self) -> None:
        """Verify that a factory returning None is cached and only called once."""
        call_counter = 0

        def factory_returning_none() -> None:
            nonlocal call_counter
            call_counter += 1

        proxy_instance = LazyProxy(factory_returning_none)
        assert proxy_instance._wrapped is None
        assert not proxy_instance._resolved

        # Trigger resolution
        resolved_value = proxy_instance._resolve()
        assert resolved_value is None
        assert proxy_instance._resolved
        assert call_counter == 1

        # Retrieve again, count should still be 1
        resolved_value_again = proxy_instance._resolve()
        assert resolved_value_again is None
        assert call_counter == 1


class TestLazyLoaderWorkflow:
    """End-to-End test suite for validating LazyLoader workflows."""

    @pytest.fixture(
        params=[
            "std_class",
            "pydantic_model",
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> Any:
        """Fixture supplying properly initialized classes/models.

        Uses LazyLoader descriptors.
        """
        if request.param == "std_class":

            @LazyLoader.class_attributes({"sys_module": "sys"})
            class StandardController:
                pass

            return StandardController()

        @LazyLoader.class_attributes({"sys_module": "sys"})
        class PydanticController(BaseModel):
            config_name: str

        return PydanticController(config_name="e2e_test")

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate class structural contracts across integrated boundaries."""
        assert issubclass(LazyLoader, object)
        assert hasattr(LazyLoader, "module")
        assert hasattr(LazyLoader, "class_attributes")
        assert hasattr(LazyLoader, "definition")
        assert hasattr(LazyLoader, "load_module_proxy")

        module_sig = inspect.signature(LazyLoader.module)
        assert "module_name" in module_sig.parameters

        class_attribs_sig = inspect.signature(LazyLoader.class_attributes)
        assert "mapping" in class_attribs_sig.parameters

        definition_sig = inspect.signature(LazyLoader.definition)
        assert "factory" in definition_sig.parameters

        load_proxy_sig = inspect.signature(LazyLoader.load_module_proxy)
        assert "fullname" in load_proxy_sig.parameters

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: Any) -> None:
        """Verify instance is initialized and descriptors are present but unresolved."""
        assert hasattr(type(valid_instances), "sys_module")
        # Inspect descriptor property closure to ensure proxy is unresolved
        cls_obj = type(valid_instances)
        prop_obj = cls_obj.sys_module
        assert isinstance(prop_obj, property)

        prop_closure = prop_obj.fget.__closure__
        assert prop_closure is not None

        found_proxy = False
        for cell_obj in prop_closure:
            cell_contents = cell_obj.cell_contents
            if isinstance(cell_contents, LazyProxy):
                assert not cell_contents._resolved
                found_proxy = True
                break
        assert found_proxy

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify decorator calls with invalid mapping values raise TypeError.

        The error is raised on attribute access.
        """

        @LazyLoader.class_attributes({"sys_module": 12345})  # type: ignore
        class InvalidController:
            sys_module: Any

        invalid_instance = InvalidController()
        with pytest.raises(TypeError):
            # Accessing the attribute forces resolution, which encounters
            # type validation failure.
            _unused = invalid_instance.sys_module

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify class_attributes decorator raises TypeError on missing mapping."""
        with pytest.raises(TypeError):
            LazyLoader.class_attributes()  # type: ignore

    @pytest.mark.sanity
    def test_class_attributes_descriptor(self) -> None:
        """Verify LazyLoader class attribute descriptor lazy loading and resolution."""
        # Ensure colorsys is removed from sys.modules to verify lazy load
        sys.modules.pop("colorsys", None)

        @LazyLoader.class_attributes({"color_mod": "colorsys"})
        class ColorController:
            color_mod: Any

        controller_instance = ColorController()
        # Assert colorsys is not loaded yet
        assert "colorsys" not in sys.modules

        # Trigger attribute read
        resolved_module = controller_instance.color_mod
        assert resolved_module is sys.modules["colorsys"]
        assert hasattr(resolved_module, "rgb_to_hsv")

        # Read dynamic attribute value
        hsv_val = controller_instance.color_mod.rgb_to_hsv(0.2, 0.4, 0.6)
        assert hsv_val == pytest.approx((0.5833333333333334, 0.6666666666666666, 0.6))

    @pytest.mark.regression
    def test_module_decorator(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify decorator for lazy-loading module subpackages on demand."""
        package_name = "test_lazy_pkg_e2e"
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
            resolved_submodule = lazy_any.submod
            mock_import.assert_called_once_with(submodule_name)
            assert resolved_submodule is mock_submodule

        # Test import error propagation
        with (
            patch("importlib.import_module", side_effect=ImportError("Import failed")),
            pytest.raises(
                AttributeError,
                match=f"Module '{package_name}' has no attribute 'missing_submod'",
            ),
        ):
            _unused = lazy_module.missing_submod

    @pytest.mark.regression
    def test_load_module_proxy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify load_module_proxy returns existing entry.

        If loaded, returns it; otherwise, lazy loads it.
        """
        # Test already loaded path
        mock_module = types.ModuleType("already_loaded_module_e2e")
        monkeypatch.setitem(sys.modules, "already_loaded_module_e2e", mock_module)
        resolved_val = LazyLoader.load_module_proxy("already_loaded_module_e2e")
        assert resolved_val is mock_module

        # Test invalid spec path
        with pytest.raises(ModuleNotFoundError):
            LazyLoader.load_module_proxy("non_existent_module_e2e_abc")

    @pytest.mark.regression
    def test_definition_helper(self) -> None:
        """Verify definition helper wraps closures in LazyProxy instances."""
        proxy_instance = LazyLoader.definition(lambda: {"status": "success"})
        assert isinstance(proxy_instance, LazyProxy)
        assert proxy_instance._wrapped is None
        assert proxy_instance.get("status") == "success"

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: Any) -> None:
        """Verify both model_dump and model_validate on Pydantic models.

        Validates execution boundaries with lazy attributes.
        """
        if not isinstance(valid_instances, BaseModel):
            # Skip for standard class instances
            return

        # Test serialization (model_dump)
        dumped_data = valid_instances.model_dump()
        assert "sys_module" not in dumped_data
        assert dumped_data == {"config_name": "e2e_test"}

        # Test deserialization/validation (model_validate)
        cls_type = type(valid_instances)
        validated_instance = cls_type.model_validate({"config_name": "validated_e2e"})
        assert validated_instance.config_name == "validated_e2e"

        # Verify lazy descriptor attribute functions after validation
        validated_any: Any = validated_instance
        assert validated_any.sys_module is sys

    @pytest.mark.regression
    def test_registry_factory_integration(self) -> None:
        """Verify dynamic flow registry factory resolves and constructs correctly."""
        registry_map: dict[str, Callable[[], Any]] = {
            "e2e_service_a": lambda: types.SimpleNamespace(service_type="A", port=8000),
            "e2e_service_b": lambda: types.SimpleNamespace(service_type="B", port=9000),
        }

        lazy_service_a = LazyLoader.definition(registry_map["e2e_service_a"])
        lazy_service_b = LazyLoader.definition(registry_map["e2e_service_b"])

        assert lazy_service_a._wrapped is None
        assert lazy_service_b._wrapped is None

        assert lazy_service_a.service_type == "A"
        assert lazy_service_a.port == 8000
        assert lazy_service_b.service_type == "B"
        assert lazy_service_b.port == 9000

        assert lazy_service_a._wrapped.service_type == "A"
        assert lazy_service_b._wrapped.service_type == "B"
