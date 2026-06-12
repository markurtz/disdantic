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

"""Compatibility abstractions for optional dependencies.

This module centralizes fallback logic for safely importing optional dependencies
like ``opentelemetry`` and ``yaml``. It provides standardized access points for
these modules, avoiding scattered ``try-except`` blocks across the codebase.
Maintainers should import optional dependencies from this module rather than
attempting direct imports elsewhere.
"""

from __future__ import annotations

import types
from typing import Annotated

_opentelemetry_trace: types.ModuleType | None
try:
    from opentelemetry import (  # type: ignore[import-not-found, unused-ignore]
        trace as _opentelemetry_trace_mod,
    )

    _opentelemetry_trace = _opentelemetry_trace_mod
except ImportError:
    _opentelemetry_trace = None

_yaml: types.ModuleType | None
try:
    import yaml as _yaml_mod  # type: ignore[import-not-found, unused-ignore]

    _yaml = _yaml_mod
except ImportError:
    _yaml = None

__all__ = ["opentelemetry_trace", "yaml"]

opentelemetry_trace: Annotated[
    types.ModuleType | None,
    "Enables distributed tracing integration. Used for tracing execution paths "
    "when OpenTelemetry is present. Provides the ``opentelemetry.trace`` module "
    "or ``None``.",
] = _opentelemetry_trace

yaml: Annotated[
    types.ModuleType | None,
    "Provides YAML serialization capabilities. Used when PyYAML is installed "
    "to dump and format object configurations, or None if unavailable.",
] = _yaml
