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
Automatic package directory traversal, layout analysis, and loading loops.

This module provides mechanisms for scanning package directories recursively,
identifying submodules, and dynamically importing them to populate class
registries. It simplifies automatic discovery of polymorphic model shapes
while maintaining utility to clear imported caches in testing environments.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from collections.abc import Sequence
from typing import ClassVar

from disdantic.exceptions import MissingPackagesError
from disdantic.settings import get_settings

__all__ = ["AutoImporterMixin"]


class AutoImporterMixin:
    """
    Provides recursive package directory module scanning with cache wiping.

    This mixin enables classes to dynamically discover and import submodules
    in a configured package hierarchy. It is typically integrated into registry
    systems to trigger dynamic registration of Pydantic model subclasses at runtime.

    Example:
        .. code-block:: python

            from disdantic.importer import AutoImporterMixin

            class MyRegistry(AutoImporterMixin):
                auto_package = "my_app.models"
                auto_ignore_modules = ["my_app.models.private_model"]

            # Scan and load the modules
            MyRegistry.auto_import_package_modules()
    """

    auto_package: ClassVar[str | Sequence[str] | None] = None
    """The target package or packages to scan for auto-importing."""

    auto_ignore_modules: ClassVar[Sequence[str] | None] = None
    """A list of submodule names or paths to ignore during package discovery."""

    _auto_imported_modules: ClassVar[set[str]] = set()

    @classmethod
    def auto_import_package_modules(cls) -> None:
        """
        Walks configured module layouts recursively and imports submodules.

        This method scans the configured packages, ignoring designated modules,
        and imports all discovered submodules to trigger dynamic registration.

        :raises ValueError: If the class variable 'auto_package' has not been
            properly configured and settings do not specify any auto_packages.
        :raises ImportError: If a target package name cannot be resolved.
        :returns: None.
        """
        packages = cls._resolve_auto_packages()
        if not packages:
            raise MissingPackagesError(
                f"The class variable 'auto_package' must be configured on "
                f"{cls.__name__} or 'auto_packages' configured in settings "
                f"to enable automated package discovery."
            )

        ignore_set = cls._resolve_ignore_set()

        for package_name in packages:
            try:
                package = importlib.import_module(package_name)  # nosemgrep
            except ModuleNotFoundError as err:
                raise ImportError(
                    f"Target auto_package root '{package_name}' could not be resolved."
                ) from err

            if not hasattr(package, "__path__"):
                continue

            for _, module_name, is_pkg in pkgutil.walk_packages(
                package.__path__,
                f"{package.__name__}.",
            ):
                if (
                    is_pkg
                    or module_name in ignore_set
                    or module_name in cls._auto_imported_modules
                ):
                    continue

                if module_name in sys.modules:
                    cls._auto_imported_modules.add(module_name)
                    continue

                importlib.import_module(module_name)  # nosemgrep
                cls._auto_imported_modules.add(module_name)

    @classmethod
    def reset_importer_cache(cls) -> None:
        """
        Purges cached system modules imported by this class.

        Clears the tracked imported submodules from both sys.modules and the
        internal tracking set to guarantee clean test executions.

        :returns: None.
        """
        for module_name in list(cls._auto_imported_modules):
            sys.modules.pop(module_name, None)
        cls._auto_imported_modules.clear()

    @classmethod
    def _resolve_auto_packages(cls) -> list[str]:
        # Resolves and deduplicates the list of target packages to scan.
        packages: list[str] = []
        if cls.auto_package:
            if isinstance(cls.auto_package, str):
                packages.append(cls.auto_package)
            else:
                packages.extend(cls.auto_package)

        settings = get_settings()
        if settings.auto_packages:
            packages.extend(settings.auto_packages)

        # Deduplicate while preserving order
        unique: list[str] = []
        for pkg in packages:
            if pkg not in unique:
                unique.append(pkg)
        return unique

    @classmethod
    def _resolve_ignore_set(cls) -> set[str]:
        # Resolves and merges package/settings ignore lists.
        ignore_set = set(cls.auto_ignore_modules or [])
        settings = get_settings()
        if settings.auto_ignore_modules:
            ignore_set.update(settings.auto_ignore_modules)
        return ignore_set
