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
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import disdantic.loading
from disdantic.loading import LazyLoader, LazyProxy


class TestLazyProxy:
    """Test suite for the LazyProxy class."""

    @pytest.fixture(
        params=[
            {"factory": lambda: [1, 2, 3]},
            {"factory": lambda: {"key": "value"}},
            {"factory": lambda: "hello_world"},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> LazyProxy:
        """Fixture providing instantiated valid variations of LazyProxy."""
        return LazyProxy(request.param["factory"])

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate class signature, inheritance, and methods."""
        assert issubclass(LazyProxy, object)
        assert hasattr(LazyProxy, "__getattr__")
        assert hasattr(LazyProxy, "__dir__")
        assert hasattr(LazyProxy, "__repr__")
        assert hasattr(LazyProxy, "_resolve")
        assert inspect.isfunction(LazyProxy.__getattr__)
        assert inspect.isfunction(LazyProxy.__dir__)
        assert inspect.isfunction(LazyProxy.__repr__)
        assert inspect.isfunction(LazyProxy._resolve)

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: LazyProxy) -> None:
        """Test initializing LazyProxy and verify state mappings."""
        assert isinstance(valid_instances, LazyProxy)
        assert valid_instances._wrapped is None
        assert not valid_instances._resolved
        assert isinstance(valid_instances._lock, type(threading.Lock()))
        assert callable(valid_instances._factory)

    @pytest.mark.regression
    def test_invalid_initialization_values(self) -> None:
        """Verify behavior with invalid factory parameter."""
        proxy_inst = LazyProxy("not_a_callable")  # type: ignore
        assert proxy_inst._wrapped is None
        with pytest.raises(TypeError):
            _val = proxy_inst.some_attr

    @pytest.mark.regression
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization fails when factory argument is missing."""
        with pytest.raises(TypeError):
            LazyProxy()  # type: ignore

    @pytest.mark.sanity
    def test___getattr__(self) -> None:
        """Test retrieving attributes from the lazily resolved target object."""
        proxy_inst = LazyProxy(lambda: [1, 2, 3])
        assert proxy_inst._wrapped is None
        proxy_inst.append(4)
        assert proxy_inst._wrapped == [1, 2, 3, 4]
        assert len(proxy_inst._wrapped) == 4

    @pytest.mark.regression
    def test___getattr___invalid(self) -> None:
        """Verify AttributeErrors are raised for invalid attributes."""
        proxy_inst = LazyProxy(lambda: [1, 2, 3])
        with pytest.raises(AttributeError):
            _val = proxy_inst.non_existent_attribute

    @pytest.mark.sanity
    def test___dir__(self) -> None:
        """Test that __dir__ returns attributes from the resolved target."""
        proxy_inst = LazyProxy(lambda: [1, 2, 3])
        assert proxy_inst._wrapped is None
        attributes = dir(proxy_inst)
        assert "append" in attributes
        assert "extend" in attributes
        assert proxy_inst._wrapped == [1, 2, 3]

    @pytest.mark.sanity
    def test___repr__(self) -> None:
        """Test string representation before and after resolution."""

        def factory_fn() -> dict[str, int]:
            return {"data": 42}

        proxy_inst = LazyProxy(factory_fn)
        repr_before = repr(proxy_inst)
        assert "uninitialized factory" in repr_before
        assert "LazyProxy" in repr_before

        assert proxy_inst.get("data") == 42
        assert repr(proxy_inst) == repr({"data": 42})

    @pytest.mark.regression
    def test_factory_returns_none(self) -> None:
        """Verify that a factory returning None is cached and only called once."""
        call_count = 0

        def factory_returning_none() -> None:
            nonlocal call_count
            call_count += 1

        proxy_inst = LazyProxy(factory_returning_none)
        assert proxy_inst._wrapped is None
        assert not proxy_inst._resolved

        dir(proxy_inst)
        assert proxy_inst._resolved
        assert call_count == 1

        dir(proxy_inst)
        assert call_count == 1

    @pytest.mark.regression
    def test_factory_failure_recovery(self) -> None:
        """Verify that if the factory fails, it can retry and succeed later."""
        call_count = 0

        def failing_then_succeeding_factory() -> list[int]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call failure")
            return [10, 20]

        proxy_inst = LazyProxy(failing_then_succeeding_factory)
        assert not proxy_inst._resolved

        with pytest.raises(ValueError, match="First call failure"):
            _val = proxy_inst.append
        assert not proxy_inst._resolved

        proxy_inst.append(30)
        assert proxy_inst._resolved
        assert proxy_inst._wrapped == [10, 20, 30]
        assert call_count == 2

    @pytest.mark.regression
    def test_thread_safety(self) -> None:
        """Verify double-checked locking and thread safety of resolution."""
        call_count = 0
        execution_lock = threading.Lock()

        def slow_factory() -> list[int]:
            nonlocal call_count
            with execution_lock:
                call_count += 1
            time.sleep(0.05)
            return [9, 8, 7]

        proxy_inst = LazyProxy(slow_factory)
        results_list: list[Any] = []

        def target_thread() -> None:
            results_list.append(proxy_inst.copy())

        threads_list = [threading.Thread(target=target_thread) for _idx in range(10)]
        for thread_inst in threads_list:
            thread_inst.start()
        for thread_inst in threads_list:
            thread_inst.join()

        assert len(results_list) == 10
        assert all(res_val == [9, 8, 7] for res_val in results_list)
        assert call_count == 1


class TestLazyLoader:
    """Test suite for the LazyLoader class."""

    @pytest.fixture(params=[{}])
    def valid_instances(self, request: pytest.FixtureRequest) -> LazyLoader:
        """Fixture providing instantiated valid variations of LazyLoader."""
        return LazyLoader()

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate class signature, inheritance, and class methods."""
        assert issubclass(LazyLoader, object)
        assert hasattr(LazyLoader, "module")
        assert hasattr(LazyLoader, "class_attributes")
        assert hasattr(LazyLoader, "definition")
        assert hasattr(LazyLoader, "load_module_proxy")
        assert inspect.ismethod(LazyLoader.module)
        assert inspect.ismethod(LazyLoader.class_attributes)
        assert inspect.ismethod(LazyLoader.definition)
        assert inspect.ismethod(LazyLoader.load_module_proxy)
        assert hasattr(LazyLoader, "_global_lock")
        assert isinstance(LazyLoader._global_lock, type(threading.Lock()))

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: LazyLoader) -> None:
        """Test initializing LazyLoader and verify state mappings."""
        assert isinstance(valid_instances, LazyLoader)

    @pytest.mark.regression
    def test_invalid_initialization_values(self) -> None:
        """Verify behavior when initializing with invalid arguments."""
        with pytest.raises(TypeError):
            LazyLoader(42)  # type: ignore

    @pytest.mark.regression
    def test_invalid_initialization_missing(self) -> None:
        """Verify instantiation is valid with no arguments."""
        loader_inst = LazyLoader()
        assert isinstance(loader_inst, LazyLoader)

    @pytest.mark.sanity
    def test_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test decorator for lazy-loading module subpackages on demand."""
        pkg_name = "test_lazy_pkg"
        mock_pkg = types.ModuleType(pkg_name)
        monkeypatch.setitem(sys.modules, pkg_name, mock_pkg)

        decorator_fn = LazyLoader.module(pkg_name)
        lazy_mod = decorator_fn(mock_pkg)

        assert sys.modules[pkg_name] is lazy_mod

        sub_module_name = f"{pkg_name}.submod"
        mock_sub = types.ModuleType(sub_module_name)

        with patch("importlib.import_module") as mock_import:
            mock_import.return_value = mock_sub
            resolved = lazy_mod.submod
            mock_import.assert_called_once_with(sub_module_name)
            assert resolved is mock_sub

    @pytest.mark.regression
    def test_module_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify module decorator attribute failure raises AttributeError."""
        pkg_name = "test_failed_pkg"
        mock_pkg = types.ModuleType(pkg_name)
        monkeypatch.setitem(sys.modules, pkg_name, mock_pkg)

        decorator_fn = LazyLoader.module(pkg_name)
        lazy_mod = decorator_fn(mock_pkg)

        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("No module found")
            with pytest.raises(AttributeError) as exc_info:
                _unused = lazy_mod.missing_sub
            err_msg = str(exc_info.value)
            assert f"Module '{pkg_name}' has no attribute 'missing_sub'" in err_msg

    @pytest.mark.regression
    def test_module_thread_safety(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify concurrent attribute imports on lazy modules are thread-safe."""
        pkg_name = "test_concurrent_pkg"
        mock_pkg = types.ModuleType(pkg_name)
        monkeypatch.setitem(sys.modules, pkg_name, mock_pkg)

        decorator_fn = LazyLoader.module(pkg_name)
        lazy_mod = decorator_fn(mock_pkg)

        sub_module_name = f"{pkg_name}.submod"
        mock_sub = types.ModuleType(sub_module_name)
        results_list: list[Any] = []

        def target_thread() -> None:
            with patch("importlib.import_module") as mock_import:
                mock_import.return_value = mock_sub
                results_list.append(lazy_mod.submod)

        threads_list = [threading.Thread(target=target_thread) for _idx in range(5)]
        for thread_inst in threads_list:
            thread_inst.start()
        for thread_inst in threads_list:
            thread_inst.join()

        assert len(results_list) == 5
        assert all(resolved is mock_sub for resolved in results_list)

    @pytest.mark.sanity
    def test_class_attributes(self) -> None:
        """Verify class attributes bind lazy property descriptors to target class."""
        call_count = 0

        def my_factory() -> str:
            nonlocal call_count
            call_count += 1
            return "factory_value"

        @LazyLoader.class_attributes(
            {
                "math_mod": "math",
                "fact_val": my_factory,
            }
        )
        class DummyTargetClass:
            math_mod: Any
            fact_val: Any

        instance_inst = DummyTargetClass()
        assert call_count == 0

        assert instance_inst.math_mod is sys.modules["math"]
        assert instance_inst.fact_val == "factory_value"
        assert call_count == 1

        assert instance_inst.fact_val == "factory_value"
        assert call_count == 1

    @pytest.mark.regression
    def test_class_attributes_shared_proxy(self) -> None:
        """Verify that lazy attributes are shared at the class level via same proxy."""
        call_count = 0

        def counter_factory() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        @LazyLoader.class_attributes({"value": counter_factory})
        class SharedProxyClass:
            value: Any

        inst_alpha = SharedProxyClass()
        inst_beta = SharedProxyClass()

        assert call_count == 0

        val_alpha = inst_alpha.value
        assert val_alpha == 1
        assert call_count == 1

        val_beta = inst_beta.value
        assert val_beta == 1
        assert call_count == 1

    @pytest.mark.regression
    def test_class_attributes_invalid(self) -> None:
        """Verify class attributes decorator handling of failure paths."""

        def failing_factory() -> None:
            raise ValueError("factory error")

        @LazyLoader.class_attributes(
            {
                "failing_import": "non_existent_module_path_xyz",
                "failing_factory": failing_factory,
            }
        )
        class DummyFailingClass:
            failing_import: Any
            failing_factory: Any

        instance_inst = DummyFailingClass()

        with pytest.raises(ImportError):
            _unused = instance_inst.failing_import

        with pytest.raises(ValueError, match="factory error"):
            _unused = instance_inst.failing_factory

    @pytest.mark.sanity
    def test_definition(self) -> None:
        """Test definition class method creating variable proxies."""
        proxy_inst = LazyLoader.definition(lambda: [100, 200])
        assert isinstance(proxy_inst, LazyProxy)
        assert proxy_inst.count(100) == 1

    @pytest.mark.sanity
    def test_load_module_proxy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test lazy loader proxy directly within module mapping."""
        temp_dir = tmp_path / "custom_import_path"
        temp_dir.mkdir()
        module_file = temp_dir / "lazy_module_to_load.py"
        module_file.write_text("TEST_CONSTANT = 'abc_123'\n")

        monkeypatch.syspath_prepend(str(temp_dir))
        monkeypatch.delitem(sys.modules, "lazy_module_to_load", raising=False)

        lazy_mod = LazyLoader.load_module_proxy("lazy_module_to_load")
        assert sys.modules["lazy_module_to_load"] is lazy_mod

        assert lazy_mod.TEST_CONSTANT == "abc_123"

    @pytest.mark.sanity
    def test_load_module_proxy_already_loaded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify load_module_proxy shortcut if module already loaded."""
        mock_module = types.ModuleType("already_existing")
        monkeypatch.setitem(sys.modules, "already_existing", mock_module)

        resolved = LazyLoader.load_module_proxy("already_existing")
        assert resolved is mock_module

    @pytest.mark.regression
    def test_load_module_proxy_invalid(self) -> None:
        """Verify load_module_proxy raises ModuleNotFoundError on no spec."""
        with patch("importlib.util.find_spec") as mock_find:
            mock_find.return_value = None
            with pytest.raises(ModuleNotFoundError) as exc_info:
                LazyLoader.load_module_proxy("totally_fictional_module")
            err_msg = str(exc_info.value)
            assert (
                "No module named 'totally_fictional_module' could be resolved"
                in err_msg
            )

    @pytest.mark.regression
    def test_load_module_proxy_thread_safety(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that calling load_module_proxy concurrently is thread-safe."""
        temp_dir = tmp_path / "thread_safe_import_path"
        temp_dir.mkdir()
        module_file = temp_dir / "thread_safe_lazy_module.py"
        module_file.write_text("THREAD_SAFE_VAL = 'xyz_789'\n")

        monkeypatch.syspath_prepend(str(temp_dir))
        monkeypatch.delitem(sys.modules, "thread_safe_lazy_module", raising=False)

        results_list: list[Any] = []

        def target_thread() -> None:
            mod_proxy = LazyLoader.load_module_proxy("thread_safe_lazy_module")
            results_list.append(mod_proxy)

        threads_list = [threading.Thread(target=target_thread) for _idx in range(5)]
        for thread_inst in threads_list:
            thread_inst.start()
        for thread_inst in threads_list:
            thread_inst.join()

        assert len(results_list) == 5
        first_mod = results_list[0]
        assert all(mod_proxy is first_mod for mod_proxy in results_list)
        assert first_mod.THREAD_SAFE_VAL == "xyz_789"


@pytest.mark.smoke
def test_all_exports() -> None:
    """Verify that all expected elements are in the module __all__."""
    assert hasattr(disdantic.loading, "__all__")
    assert set(disdantic.loading.__all__) == {"LazyLoader", "LazyProxy"}
