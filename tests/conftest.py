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
#
# Unless otherwise noted, all files in this directory and its subdirectories
# are licensed under the Apache License, Version 2.0.

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Coroutine, Generator
from functools import wraps
from pathlib import Path
from typing import Any

import pytest


def async_timeout(
    delay: float,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, Any]]],
    Callable[..., Coroutine[Any, Any, Any]],
]:
    """Decorator to enforce a timeout on asynchronous test executions."""

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(func)
        async def new_func(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=delay)

        return new_func

    return decorator


class TemporaryPackageBuilder:
    """Helper to dynamically construct a package structure on disk,
    managing sys.path and sys.modules cleanups automatically.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.added_paths: list[str] = []
        self.created_packages: list[str] = []

    def create_package(self, package_name: str, modules: dict[str, str]) -> Path:
        """Create a package with specified submodules.

        Args:
            package_name: Name of the package, e.g., "my_package"
            modules: Dictionary of submodule relative names to code contents,
                     e.g. {"sub_one": "x = 1", "sub_two": "y = 2"}
        """
        pkg_dir = self.base_dir / package_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text(
            "# Auto-generated package init",
            encoding="utf-8",
        )

        for mod_name, content in modules.items():
            mod_parts = mod_name.split(".")
            if len(mod_parts) > 1:
                # Nested module
                sub_pkg_dir = pkg_dir / "/".join(mod_parts[:-1])
                sub_pkg_dir.mkdir(parents=True, exist_ok=True)
                # Ensure all intermediate dirs have __init__.py
                curr = pkg_dir
                for part in mod_parts[:-1]:
                    curr = curr / part
                    init_file = curr / "__init__.py"
                    if not init_file.exists():
                        init_file.write_text(
                            "# Auto-generated sub-package init",
                            encoding="utf-8",
                        )

                mod_file = pkg_dir / f"{'/'.join(mod_parts)}.py"
            else:
                mod_file = pkg_dir / f"{mod_name}.py"

            mod_file.write_text(content, encoding="utf-8")

        # Add base_dir to sys.path if not already there
        base_path_str = str(self.base_dir)
        if base_path_str not in sys.path:
            sys.path.insert(0, base_path_str)
            self.added_paths.append(base_path_str)

        self.created_packages.append(package_name)
        return pkg_dir

    def cleanup(self) -> None:
        """Purge all created packages from sys.modules and base_dir from sys.path."""
        # Clean sys.modules
        for pkg_name in self.created_packages:
            to_remove = [
                mod
                for mod in sys.modules
                if mod == pkg_name or mod.startswith(f"{pkg_name}.")
            ]
            for mod in to_remove:
                sys.modules.pop(mod, None)

        # Clean sys.path
        for path_str in self.added_paths:
            if path_str in sys.path:
                sys.path.remove(path_str)
        self.added_paths.clear()
        self.created_packages.clear()


@pytest.fixture
def temp_package_builder(
    tmp_path: Path,
) -> Generator[TemporaryPackageBuilder, None, None]:
    """Fixture providing a TemporaryPackageBuilder instance.

    Creates dynamic test packages.
    """
    builder = TemporaryPackageBuilder(tmp_path)
    yield builder
    builder.cleanup()
