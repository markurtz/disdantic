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
Package initialization and unified entry point for the disdantic library.

This library simplifies registry management, polymorphic serialization,
dynamic schema generation, and automatic module discovery. It provides
mixins and managers to register and retrieve subclasses dynamically,
making it easier to construct polymorphic data structures without manual
boilerplate.

The core architecture exposes base components including `RegistryMixin` and
`InfoMixin` for behavior tracking, `LazyLoader` and `LazyProxy` for
performance-focused import loading, along with `configure_logger` and
package-level `Settings` for system initialization.
"""

from __future__ import annotations

from typing import Annotated

from .diagnose import (
    DiagnosticsReport,
    RegistryDiagnostics,
    RegistryModelInfo,
    verify_registries,
)
from .importer import AutoImporterMixin
from .introspection import InfoMixin
from .loading import LazyLoader, LazyProxy
from .logging import LoggingSettings, configure_logger, logger
from .model import ReloadableBaseModel
from .registry import PydanticClassRegistryMixin, RegistryManager, RegistryMixin
from .schema import get_registry_schema
from .settings import Settings, get_settings, reset_settings
from .singleton import SingletonMeta
from .version import __version__ as _version

__version__: Annotated[
    str,
    "The package version identifier string conforming to PEP 440 specifications.",
] = _version

__all__ = [
    "AutoImporterMixin",
    "DiagnosticsReport",
    "InfoMixin",
    "LazyLoader",
    "LazyProxy",
    "LoggingSettings",
    "PydanticClassRegistryMixin",
    "RegistryDiagnostics",
    "RegistryManager",
    "RegistryMixin",
    "RegistryModelInfo",
    "ReloadableBaseModel",
    "Settings",
    "SingletonMeta",
    "__version__",
    "configure_logger",
    "get_registry_schema",
    "get_settings",
    "logger",
    "reset_settings",
    "verify_registries",
]

configure_logger()
