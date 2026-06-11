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

"""Unit tests for the thread-safe lazy loading proxies and loaders."""

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
        assert isinstance(valid_instances._lock, type(threading.Lock()))
        assert callable(valid_instances._factory)

    @pytest.mark.regression
    def test_invalid_initialization_values(self) -> None:
        """Verify behavior with invalid factory parameter."""
        # Type check says Callable[[], Any], so runtime doesn't fail on __init__
        # but will fail on resolve.
        proxy = LazyProxy("not_a_callable")  # type: ignore
        assert proxy._wrapped is None
        with pytest.raises(TypeError):
            proxy._resolve()

    @pytest.mark.regression
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization fails when factory argument is missing."""
        with pytest.raises(TypeError):
            LazyProxy()  # type: ignore

    @pytest.mark.sanity
    def test___getattr__(self) -> None:
        """Test retrieving attributes from the lazily resolved target object."""
        proxy = LazyProxy(lambda: [1, 2, 3])
        # Before attribute access, it is uninitialized
        assert proxy._wrapped is None
        # Accessing an attribute resolves the target
        proxy.append(4)
        assert proxy._wrapped == [1, 2, 3, 4]
        # Subsequent access uses resolved target
        assert len(proxy._wrapped) == 4

    @pytest.mark.sanity
    def test___dir__(self) -> None:
        """Test that __dir__ returns attributes from the resolved target."""
        proxy = LazyProxy(lambda: [1, 2, 3])
        assert proxy._wrapped is None
        attributes = dir(proxy)
        assert "append" in attributes
        assert "extend" in attributes
        assert proxy._wrapped == [1, 2, 3]

    @pytest.mark.sanity
    def test___repr__(self) -> None:
        """Test string representation before and after resolution."""

        def factory_fn() -> dict[str, int]:
            return {"data": 42}

        proxy = LazyProxy(factory_fn)
        # Uninitialized repr contains factory signature/details
        repr_before = repr(proxy)
        assert "uninitialized factory" in repr_before
        assert "LazyProxy" in repr_before

        # Resolve
        val = proxy.get("data")
        assert val == 42
        # Initialized repr matches wrapped target repr
        assert repr(proxy) == repr({"data": 42})

    @pytest.mark.regression
    def test__resolve(self) -> None:
        """Verify double-checked locking and thread safety of resolution."""
        call_count = 0
        execution_lock = threading.Lock()

        def slow_factory() -> list[int]:
            nonlocal call_count
            with execution_lock:
                call_count += 1
            # Delay to encourage concurrency issues if lock fails
            time.sleep(0.05)
            return [9, 8, 7]

        proxy = LazyProxy(slow_factory)
        results: list[Any] = []

        def target_thread() -> None:
            # Retrieve attribute to trigger resolution
            results.append(proxy._resolve())

        threads = [threading.Thread(target=target_thread) for _idx in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 10
        assert all(res == [9, 8, 7] for res in results)
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

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: LazyLoader) -> None:
        """Test initializing LazyLoader and verify state mappings."""
        assert isinstance(valid_instances, LazyLoader)

    @pytest.mark.regression
    def test_invalid_initialization_values(self) -> None:
        """Verify behavior when initializing with invalid arguments."""
        with pytest.raises(TypeError):
            LazyLoader(42)  # type: ignore

    @pytest.mark.sanity
    def test_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test decorator for lazy-loading module subpackages on demand."""
        # Prepare dummy package and module in sys.modules
        pkg_name = "test_lazy_pkg"
        mock_pkg = types.ModuleType(pkg_name)
        monkeypatch.setitem(sys.modules, pkg_name, mock_pkg)

        decorator = LazyLoader.module(pkg_name)
        lazy_mod = decorator(mock_pkg)

        # Check that it replaced the entry in sys.modules
        assert sys.modules[pkg_name] is lazy_mod

        # Accessing an attribute triggers imports
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

        decorator = LazyLoader.module(pkg_name)
        lazy_mod = decorator(mock_pkg)

        with patch("importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("No module found")
            with pytest.raises(AttributeError) as exc_info:
                _unused = lazy_mod.missing_sub
            err_msg = str(exc_info.value)
            assert f"Module '{pkg_name}' has no attribute 'missing_sub'" in err_msg

    @pytest.mark.sanity
    def test_class_attributes(self) -> None:
        """Verify class attributes bind lazy property descriptors to target class."""
        call_count = 0

        def my_factory() -> str:
            nonlocal call_count
            call_count += 1
            return "factory_value"

        # Apply decorator
        @LazyLoader.class_attributes(
            {
                "math_mod": "math",
                "fact_val": my_factory,
            }
        )
        class DummyTargetClass:
            math_mod: Any
            fact_val: Any

        instance = DummyTargetClass()
        # Verify call count is still 0 before access
        assert call_count == 0

        # Verify attributes resolve correctly
        assert instance.math_mod is sys.modules["math"]
        assert instance.fact_val == "factory_value"
        assert call_count == 1

        # Access again, call count should not increment
        assert instance.fact_val == "factory_value"
        assert call_count == 1

    @pytest.mark.regression
    def test_class_attributes_invalid(self) -> None:
        """Verify class attributes decorator handling of failure paths."""

        def failing_factory() -> None:
            raise ValueError("factory error")

        @LazyLoader.class_attributes(
            {
                "failing_import": "non_existent_module_path_abc",
                "failing_factory": failing_factory,
            }
        )
        class DummyFailingClass:
            failing_import: Any
            failing_factory: Any

        instance = DummyFailingClass()

        with pytest.raises(ImportError):
            _unused = instance.failing_import

        with pytest.raises(ValueError, match="factory error"):
            _unused = instance.failing_factory

    @pytest.mark.sanity
    def test_definition(self) -> None:
        """Test definition class method creating variable proxies."""
        proxy = LazyLoader.definition(lambda: [100, 200])
        assert isinstance(proxy, LazyProxy)
        # Access attribute to verify correct wrapped object
        assert proxy.count(100) == 1

    @pytest.mark.sanity
    def test_load_module_proxy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test lazy loader proxy directly within module mapping."""
        # Create a temporary directory and module file
        temp_dir = tmp_path / "custom_import_path"
        temp_dir.mkdir()
        module_file = temp_dir / "lazy_module_to_load.py"
        module_file.write_text("TEST_CONSTANT = 'abc_123'\n")

        # Prep path and modules
        monkeypatch.syspath_prepend(str(temp_dir))
        monkeypatch.delitem(sys.modules, "lazy_module_to_load", raising=False)

        # Retrieve lazy loader proxy
        lazy_mod = LazyLoader.load_module_proxy("lazy_module_to_load")
        assert sys.modules["lazy_module_to_load"] is lazy_mod

        # Constant should not be loaded yet, verify attribute access resolves it
        assert lazy_mod.TEST_CONSTANT == "abc_123"

    @pytest.mark.sanity
    def test_load_module_proxy_already_loaded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify load_module_proxy shortcut if module already loaded."""
        mock_module = types.ModuleType("already_existing")
        monkeypatch.setitem(sys.modules, "already_existing", mock_module)

        # Directly returns existing
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
