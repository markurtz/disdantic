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

"""Registry diagnostics and integrity check orchestrator for subclass registries.

This module provides programmatic tools and interfaces to scan Python packages,
recursively import modules to trigger dynamic model registration, and verify the
Pydantic compilation health and consistency of all registered classes.

Veteran maintainers can utilize this module's verify_registries function to run
diagnostic checks, while new contributors can refer to it to verify that their
newly created Pydantic subclasses are properly auto-discovered and compiled.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from typing import Any, cast

from pydantic import BaseModel, Field

import disdantic.settings
from disdantic.registry import PydanticClassRegistryMixin, RegistryMixin
from disdantic.settings import Settings

__all__ = [
    "DiagnosticsReport",
    "RegistryDiagnostics",
    "RegistryModelInfo",
    "verify_registries",
]


def verify_registries(settings: Settings | None = None) -> DiagnosticsReport:
    """Scan configured packages, discover registries, and verify compilation.

    Examples:
        .. code-block:: python

            from disdantic.diagnose import verify_registries

            report = verify_registries()
            if not report.is_healthy:
                print(f"Diagnostics failed. Errors: {report.import_errors}")

    :param settings: Optional settings configuration instance to customize packages
        and ignore rules.
    :returns: The aggregated health diagnostics report.
    """
    if settings is not None:
        with disdantic.settings._settings_lock:  # noqa: SLF001
            disdantic.settings._global_settings = settings  # noqa: SLF001

    resolved_settings = disdantic.settings.get_settings()
    unique_packages = _resolve_packages_to_scan(resolved_settings)
    ignore_set = _resolve_ignore_set(resolved_settings)

    import_errors: list[str] = []
    _scan_packages(unique_packages, ignore_set, import_errors)

    valid_registries = _find_valid_registries()

    registries_diagnostics: list[RegistryDiagnostics] = []
    is_healthy = len(import_errors) == 0

    for registry_class in valid_registries:
        registry_diag = _diagnose_registry(registry_class, import_errors)
        registries_diagnostics.append(registry_diag)

        if issubclass(registry_class, PydanticClassRegistryMixin):
            try:
                registry_class.model_rebuild(force=True, raise_errors=True)
                registry_class.model_json_schema()
            except Exception:  # noqa: BLE001
                is_healthy = False

        if any(model.compilation_status == "error" for model in registry_diag.models):
            is_healthy = False

    if import_errors:
        is_healthy = False

    return DiagnosticsReport(
        is_healthy=is_healthy,
        scanned_packages=unique_packages,
        registries=registries_diagnostics,
        import_errors=import_errors,
    )


class DiagnosticsReport(BaseModel):
    """Aggregated health status and discovery details of all checked registries.

    This class serves as the root container returned by the verification pipeline. It
    consolidates individual registry diagnostics, scanned packages, and import failure
    traces into a single report.

    Examples:
        .. code-block:: python

            from disdantic.diagnose import verify_registries

            report = verify_registries()
            if not report.is_healthy:
                print(f"Scanned packages: {report.scanned_packages}")
                print(f"Import errors: {report.import_errors}")
    """

    is_healthy: bool = Field(
        description=(
            "Indicates whether the entire check is clean, enabling safe dynamic model "
            "resolution with zero registry or import failures."
        )
    )
    scanned_packages: list[str] = Field(
        description="Maps the list of Python package names traversed during discovery."
    )
    registries: list[RegistryDiagnostics] = Field(
        default_factory=list,
        description=(
            "Configures the collection of registry-specific diagnostics reports."
        ),
    )
    import_errors: list[str] = Field(
        default_factory=list,
        description=(
            "Maps the traceback strings for import errors encountered during scanning."
        ),
    )


class RegistryDiagnostics(BaseModel):
    """Configuration, model metadata, and integrity status of a registry.

    This class tracks the metadata of a single registry subclassing RegistryMixin. It
    records the dynamic auto-discovery configuration, registered sub-models, and any
    orphaned subclasses that were imported but failed to register.

    Examples:
        .. code-block:: python

            from disdantic.diagnose import verify_registries

            report = verify_registries()
            for registry in report.registries:
                print(f"Registry: {registry.registry_name}")
                print(f"Orphaned subclasses: {registry.orphans}")
    """

    registry_name: str = Field(
        description="Maps the name of the registry base class under diagnostic check."
    )
    discriminator_key: str = Field(
        description=(
            "Configures the attribute name used to identify model types in polymorphic "
            "schemas."
        )
    )
    auto_discovery_enabled: bool = Field(
        description=(
            "Enables package scanning and dynamic registration for this registry."
        )
    )
    models: list[RegistryModelInfo] = Field(
        default_factory=list,
        description=(
            "Configures the list of registered models and their compilation states."
        ),
    )
    orphans: list[str] = Field(
        default_factory=list,
        description="Maps imported subclasses that are not registered with any key.",
    )


class RegistryModelInfo(BaseModel):
    """Metadata and compilation status of a registered subclass inside a registry.

    This class captures the import details, registration key, and Pydantic schema
    compilation status of a single model registered under a RegistryMixin class.

    Examples:
        .. code-block:: python

            from disdantic.diagnose import verify_registries

            report = verify_registries()
            for registry in report.registries:
                for model in registry.models:
                    if model.compilation_status == "error":
                        print(
                            f"Model {model.class_name} compilation error: "
                            f"{model.error_detail}"
                        )
    """

    key: str = Field(
        description="Maps the unique lookup key used to register this subclass."
    )
    class_name: str = Field(description="Maps the name of the registered Python class.")
    module_path: str = Field(
        description="Maps the import path of the module defining the model class."
    )
    compilation_status: str = Field(
        description="Configures the health status, set to 'healthy' or 'error'."
    )
    error_detail: str | None = Field(
        default=None,
        description=(
            "Maps the traceback or validation error message if compilation failed."
        ),
    )


def _find_valid_registries() -> list[type[RegistryMixin[Any]]]:
    # Finds all valid subclasses of RegistryMixin to verify.
    all_registries = _get_all_subclasses(RegistryMixin)
    valid_registries: list[type[RegistryMixin[Any]]] = []
    for subclass in all_registries:
        if subclass.__name__ in ("RegistryMixin", "PydanticClassRegistryMixin"):
            continue
        if issubclass(subclass, PydanticClassRegistryMixin) and (
            subclass.__pydantic_schema_base_type__() is not subclass
        ):
            continue
        if subclass not in valid_registries:
            valid_registries.append(cast("type[RegistryMixin[Any]]", subclass))
    valid_registries.sort(key=lambda registry: registry.__name__)
    return valid_registries


def _resolve_packages_to_scan(settings: Settings) -> list[str]:
    # Resolves all package names configured or declared in subclass registries.
    packages_to_scan: list[str] = []

    if settings.auto_packages:
        packages_to_scan.extend(settings.auto_packages)

    for subclass in _get_all_subclasses(RegistryMixin):
        if subclass.__name__ in ("RegistryMixin", "PydanticClassRegistryMixin"):
            continue
        auto_package = getattr(subclass, "auto_package", None)
        if auto_package:
            if isinstance(auto_package, str):
                packages_to_scan.append(auto_package)
            else:
                packages_to_scan.extend(auto_package)

    return list(dict.fromkeys(packages_to_scan))


def _resolve_ignore_set(settings: Settings) -> set[str]:
    # Gathers all ignored module names from settings and registry definitions.
    ignore_set = set(settings.auto_ignore_modules or [])
    for subclass in _get_all_subclasses(RegistryMixin):
        if subclass.__name__ in ("RegistryMixin", "PydanticClassRegistryMixin"):
            continue
        auto_ignore = getattr(subclass, "auto_ignore_modules", None)
        if auto_ignore:
            ignore_set.update(auto_ignore)
    return ignore_set


def _scan_packages(
    packages: list[str], ignore_set: set[str], errors_list: list[str]
) -> None:
    # Recursively import package submodules and collect import errors.
    for package_name in packages:
        try:
            package = importlib.import_module(package_name)  # nosemgrep
        except Exception as error:  # noqa: BLE001
            errors_list.append(
                f"Failed to import package root '{package_name}': {error}"
            )
            continue

        if not hasattr(package, "__path__"):
            continue

        def on_error(name: str) -> None:
            # Silence walking errors
            pass

        try:
            for _, module_name, is_package in pkgutil.walk_packages(
                package.__path__,
                f"{package.__name__}.",
                onerror=on_error,
            ):
                if is_package or module_name in ignore_set:
                    continue
                try:
                    importlib.import_module(module_name)  # nosemgrep
                except Exception as error:  # noqa: BLE001
                    errors_list.append(
                        f"Failed to import module '{module_name}': {error}"
                    )
        except Exception as error:  # noqa: BLE001
            errors_list.append(f"Error walking package '{package_name}': {error}")


def _diagnose_registry(
    registry_class: type[RegistryMixin[Any]],
    errors_list: list[str],
) -> RegistryDiagnostics:
    # Inspects a single registry class and returns its diagnostics.
    registry_name = registry_class.__name__
    auto_discovery_enabled = registry_class.is_auto_discovery_enabled()

    if issubclass(registry_class, PydanticClassRegistryMixin):
        discriminator_key = registry_class.get_schema_discriminator()
    else:
        discriminator_key = getattr(registry_class, "schema_discriminator", "N/A")

    has_packages = bool(
        getattr(registry_class, "auto_package", None)
        or disdantic.settings.get_settings().auto_packages
    )

    if (
        auto_discovery_enabled
        and not registry_class.registry_populated
        and has_packages
    ):
        try:
            registry_class.auto_populate_registry()
        except Exception as error:  # noqa: BLE001
            errors_list.append(
                f"Auto-population failed for registry '{registry_name}': {error}"
            )

    models_info: list[RegistryModelInfo] = []
    for key, target_object in registry_class.registry.items():
        class_name = (
            target_object.__name__
            if isinstance(target_object, type)
            else type(target_object).__name__
        )
        module_path = (
            target_object.__module__ if hasattr(target_object, "__module__") else ""
        )

        compilation_status = "healthy"
        error_detail = None

        if (
            issubclass(registry_class, PydanticClassRegistryMixin)
            and isinstance(target_object, type)
            and issubclass(target_object, BaseModel)
        ):
            try:
                target_object.model_rebuild(force=True, raise_errors=True)
                target_object.model_json_schema()
            except Exception as error:  # noqa: BLE001
                compilation_status = "error"
                error_detail = str(error)

        models_info.append(
            RegistryModelInfo(
                key=key,
                class_name=class_name,
                module_path=module_path,
                compilation_status=compilation_status,
                error_detail=error_detail,
            )
        )

    models_info.sort(key=lambda model: model.key)

    orphans: list[str] = []
    for subclass in _get_all_subclasses(registry_class):
        if subclass not in registry_class.registry.values():
            if subclass.__name__ in (
                "RegistryMixin",
                "PydanticClassRegistryMixin",
            ):
                continue
            orphans.append(f"{subclass.__module__}.{subclass.__name__}")
    orphans.sort()

    return RegistryDiagnostics(
        registry_name=registry_name,
        discriminator_key=discriminator_key,
        auto_discovery_enabled=auto_discovery_enabled,
        models=models_info,
        orphans=orphans,
    )


def _get_all_subclasses(cls: type) -> set[type]:
    # Helper to recursively find all subclasses of a given class.
    subclasses = set()
    for subclass in cls.__subclasses__():
        if (
            hasattr(subclass, "__module__")
            and isinstance(subclass.__module__, str)
            and subclass.__module__ in sys.modules
        ):
            subclasses.add(subclass)
            subclasses.update(_get_all_subclasses(subclass))
    return subclasses
