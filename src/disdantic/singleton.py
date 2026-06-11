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

"""
Thread-safe singleton patterns using metaclass interception.

This module provides the :class:`SingletonMeta` metaclass, which implements a
thread-safe singleton pattern for Python classes. By intercepting class
instantiation via metaclass mechanisms, it ensures that only a single instance
of a class exists throughout the application lifecycle.

The implementation utilizes double-checked locking to optimize performance,
avoiding lock acquisition overhead on the fast path when the instance already
exists. It also provides mechanisms to programmatically reset singleton
instances during testing.
"""

from __future__ import annotations

import threading
from typing import Any

__all__ = ["SingletonMeta"]


class SingletonMeta(type):
    """
    Thread-safe Singleton metaclass.

    This metaclass intercepts class instantiation to enforce the singleton
    pattern, ensuring that subsequent calls to the class constructor return
    the same cached instance. It uses double-checked locking to guarantee
    thread safety during initialization without compromising read performance
    on subsequent retrievals.

    Example:
        .. code-block:: python

            from disdantic.singleton import SingletonMeta

            class DatabaseConnection(metaclass=SingletonMeta):
                def __init__(self, connection_string: str) -> None:
                    self.connection_string = connection_string

            # Both variables reference the exact same instance
            conn1 = DatabaseConnection("db://host1")
            conn2 = DatabaseConnection("db://host2")
            assert conn1 is conn2
    """

    _instances: dict[type, Any] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def clear_all_singletons(cls) -> None:
        """
        Wipes all cached singleton instances across the application workspace.

        This method is primarily designed for cleanup between test runs, ensuring
        that side effects from singleton states do not leak across test boundaries.
        """
        with cls._lock:
            cls._instances.clear()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """
        Intercepts class instantiation to return the cached singleton instance.

        If the instance does not already exist, it is created using double-checked
        locking to handle initialization race conditions.

        :param args: Positional arguments passed to the class constructor.
        :param kwargs: Keyword arguments passed to the class constructor.
        :returns: The single, thread-safe cached instance of the class.
        """
        # Fast Path: Check if instance already exists without acquiring a lock
        if cls not in cls._instances:
            with cls._lock:
                # Slow Path: Double-check within the lock context to handle
                # race conditions.
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    def clear_instances(cls) -> None:
        """
        Evicts the active single instance of the class from runtime tracking.

        Calling this method allows a new instance of the class to be created on the
        next instantiation attempt.
        """
        with cls._lock:
            cls._instances.pop(cls, None)
