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

"""Lazy Loading & Introspection Example.

Demonstrates thread-safe lazy proxies, singleton double-checked locking,
and recursive circular reference safety for runtime self-introspection.
"""

from __future__ import annotations

import threading
import time

from disdantic.introspection import InfoMixin
from disdantic.loading import LazyProxy
from disdantic.logging import LoggingSettings, configure_logger, logger
from disdantic.singleton import SingletonMeta

__all__ = ["DatabaseConnectionManager", "DeveloperNode", "main"]


class DatabaseConnectionManager(metaclass=SingletonMeta):
    """Thread-safe Singleton Database Connection Manager."""

    def __init__(self) -> None:
        logger.info("Initializing heavy database connection manager...")
        time.sleep(0.5)  # Simulate expensive database socket startup
        self.connected: bool = True


class DeveloperNode(InfoMixin):
    """Introspection Target Class with Circular References."""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.peer: DeveloperNode | None = None


def main() -> None:
    """Run all workflows in the example."""
    # 1. Verify Singleton Double-Checked Locking under Concurrency
    num_threads = 5
    threads: list[threading.Thread] = []
    instances: list[DatabaseConnectionManager] = []

    def worker() -> None:
        inst = DatabaseConnectionManager()
        instances.append(inst)

    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # All instances retrieved must point to the same memory address
    assert len(instances) == num_threads
    assert all(inst is instances[0] for inst in instances)
    print("Double-checked locking successful! Total manager instances created: 1")

    # 2. Verify Thread-Safe LazyProxy
    def expensive_factory() -> DatabaseConnectionManager:
        return DatabaseConnectionManager()

    proxy = LazyProxy(expensive_factory)

    # Read attribute of proxy from multiple threads
    proxy_resolutions: list[bool] = []

    def proxy_worker() -> None:
        proxy_resolutions.append(proxy.connected)

    proxy_threads = [threading.Thread(target=proxy_worker) for _ in range(5)]
    for pt in proxy_threads:
        pt.start()
    for pt in proxy_threads:
        pt.join()

    print(f"Proxy successfully resolved connected status: {proxy_resolutions}")

    # 3. Verify Self-Introspection with Circular Reference Handling
    dev1 = DeveloperNode("Alice")
    dev2 = DeveloperNode("Bob")

    # Create circular reference loop
    dev1.peer = dev2
    dev2.peer = dev1

    # Execute introspection scraping
    info_dict = dev1.info
    print("Alice's Introspection Dict:")
    print(f"Name: {info_dict['attributes']['name']}")
    print(f"Peer: {info_dict['attributes']['peer']}")

    # Export to raw JSON serialization
    json_output = dev1.info_json(indent=2)
    print("\nSerialized JSON string:")
    print(json_output)


if __name__ == "__main__":
    configure_logger(LoggingSettings(enabled=True, level="INFO"))
    main()
