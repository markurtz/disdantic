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

"""Thread-safe lazy loading proxies and descriptive decorators.

This module provides structural abstractions for deferred object instantiation
and lazy package imports. It implements thread-safe proxy containers that wrap
factory functions, only invoking them when attribute access, string representation,
or directory inspection is performed. These utilities help resolve circular import
dependencies, optimize application startup times, and isolate optional imports.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import threading
import types
from collections.abc import Callable
from typing import Any, TypeVar

__all__ = ["LazyLoader", "LazyProxy"]

TargetT = TypeVar("TargetT")


class LazyProxy:
    """Proxy container wrapping modules or factories until an attribute is read.

    Acts as a placeholder for objects whose construction is expensive or requires
    deferred execution. The target object is instantiated and resolved by invoking a
    provided factory function upon the first query of attributes, string representation,
    or directory listing. Resolution is fully thread-safe.

    Example:
        .. code-block:: python

            from disdantic.loading import LazyProxy

            def expensive_factory():
                return {"data": 42}

            proxy = LazyProxy(expensive_factory)
            # expensive_factory is not called yet
            print(proxy.data)  # Triggers resolution and outputs: 42
    """

    def __init__(self, factory: Callable[[], Any]) -> None:
        """Initialize the lazy proxy wrapper with a factory callable.

        :param factory: A zero-argument callable returning the target object to wrap.
        """
        self._factory = factory
        self._wrapped: Any = None
        self._resolved = False
        self._lock = threading.Lock()

    def __getattr__(self, name: str) -> Any:
        """Retrieve attributes from the lazily resolved target object.

        :param name: The name of the attribute to retrieve.
        :returns: The attribute value from the resolved object.
        """
        return getattr(self._resolve(), name)

    def __dir__(self) -> list[str]:
        """Return the directory list of attributes from the resolved target object.

        :returns: List of attributes available on the wrapped object.
        """
        return dir(self._resolve())

    def __repr__(self) -> str:
        """Return a string representation of the proxy or the wrapped target.

        :returns: A string indicating initialization state or the wrapped
            representation.
        """
        if not self._resolved:
            return f"<LazyProxy for uninitialized factory: {self._factory}>"
        return repr(self._wrapped)

    def _resolve(self) -> Any:
        # Double-checked locking implementation preventing concurrent serialization
        # or import errors.
        if not self._resolved:
            with self._lock:
                if not self._resolved:
                    self._wrapped = self._factory()
                    self._resolved = True
        return self._wrapped


class LazyLoader:
    """Provides thread-safe lazy loading decorators for modules, classes, and variables.

    Encapsulates static utilities to defer package imports and object instantiation.
    It supports lazy module resolution, injecting descriptors into classes, and
    wrapping functional closures inside proxy containers.

    Example:
        .. code-block:: python

            from disdantic.loading import LazyLoader

            # Lazy-load a module namespace
            lazy_sys = LazyLoader.load_module_proxy("sys")
    """

    _global_lock = threading.Lock()

    @classmethod
    def module(cls, module_name: str) -> Callable[[types.ModuleType], types.ModuleType]:
        """Create a decorator to lazy-load module subpackages on demand.

        Example:
            .. code-block:: python

                import sys
                from disdantic.loading import LazyLoader

                @LazyLoader.module("disdantic")
                def loading(mod):
                    pass

        :param module_name: The fully qualified name of the package or module.
        :returns: A decorator function that replaces the target module with
            a lazy module proxy.
        """

        def decorator(_: types.ModuleType) -> types.ModuleType:
            class LazyModule(types.ModuleType):
                def __getattr__(self, name: str) -> Any:
                    with cls._global_lock:
                        try:
                            target_path = f"{module_name}.{name}"
                            return importlib.import_module(target_path)  # nosemgrep
                        except ImportError as error:
                            raise AttributeError(
                                f"Module '{module_name}' has no attribute '{name}'"
                            ) from error

            lazy_mod = LazyModule(module_name)
            sys.modules[module_name] = lazy_mod
            return lazy_mod

        return decorator

    @classmethod
    def class_attributes(
        cls, mapping: dict[str, str | Callable[[], Any]]
    ) -> Callable[[type[TargetT]], type[TargetT]]:
        """Bind lazy property descriptors to class attributes to defer instantiation.

        Accepts a dictionary mapping attribute names to either importable module paths
        or factory callables, and returning a decorator for the target class.

        Example:
            .. code-block:: python

                from disdantic.loading import LazyLoader

                @LazyLoader.class_attributes({"sys": "sys"})
                class MyClass:
                    pass

                instance = MyClass()
                # Accessing sys will load the module lazily
                print(instance.sys.path)

        :param mapping: Dictionary mapping attribute names to module paths or callables.
        :returns: A decorator function that updates the class with lazy attributes.
        """

        def decorator(target_cls: type[TargetT]) -> type[TargetT]:
            for attr_name, target in mapping.items():

                def _create_getter(
                    target_val: str | Callable[[], Any] = target,
                ) -> property:
                    proxy = LazyProxy(
                        lambda: (
                            importlib.import_module(target_val)  # nosemgrep
                            if isinstance(target_val, str)
                            else target_val()
                        )
                    )
                    return property(lambda _: proxy._resolve())  # noqa: SLF001

                setattr(target_cls, attr_name, _create_getter())
            return target_cls

        return decorator

    @classmethod
    def definition(cls, factory: Callable[[], Any]) -> LazyProxy:
        """Create an explicit variable proxy from a functional factory closure.

        Defers execution of the factory callable until attributes are accessed
        on the returned proxy.

        Example:
            .. code-block:: python

                from disdantic.loading import LazyLoader

                proxy = LazyLoader.definition(lambda: [1, 2, 3])
                # Factory remains uncalled until accessed
                print(len(proxy))

        :param factory: A zero-argument callable returning the target object.
        :returns: A LazyProxy instance wrapping the factory function.
        """
        return LazyProxy(factory)

    @classmethod
    def load_module_proxy(cls, fullname: str) -> types.ModuleType:
        """Generate a standard lazy loader proxy directly within the module mapping.

        Resolves the module spec and registers a lazy-loading module in sys.modules,
        only executing the module when its attributes are accessed.

        Example:
            .. code-block:: python

                from disdantic.loading import LazyLoader

                # Loads my_module lazily
                my_mod = LazyLoader.load_module_proxy("my_module")

        :param fullname: The fully qualified name of the module to lazy-load.
        :returns: A module proxy that triggers execution of the module on access.
        :raises ModuleNotFoundError: If the module specified by fullname cannot
            be resolved.
        """
        with cls._global_lock:
            if fullname in sys.modules:
                return sys.modules[fullname]

            spec = importlib.util.find_spec(fullname)
            if not spec or not spec.loader:
                raise ModuleNotFoundError(
                    f"No module named '{fullname}' could be resolved."
                )

            module = importlib.util.module_from_spec(spec)
            sys.modules[fullname] = module

            lazy_loader = importlib.util.LazyLoader(spec.loader)
            lazy_loader.exec_module(module)
            return module
