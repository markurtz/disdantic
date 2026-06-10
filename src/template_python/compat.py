"""
Compatibility abstractions for optional dependencies.

This module centralizes fallback logic for safely importing optional dependencies
like ``opentelemetry``. It provides standardized access points for these modules,
avoiding scattered ``try-except`` blocks across the codebase. Maintainers should
import optional dependencies from this module rather than attempting direct
imports elsewhere.
"""

from __future__ import annotations

import types
from typing import Annotated

try:
    from opentelemetry import (
        trace as _opentelemetry_trace,  # type: ignore[import-not-found]
    )
except ImportError:
    _opentelemetry_trace = None  # type: ignore[assignment]

__all__ = ["opentelemetry_trace"]

opentelemetry_trace: Annotated[
    types.ModuleType | None,
    "Enables distributed tracing integration. Used for tracing execution paths "
    "when OpenTelemetry is present. Provides the ``opentelemetry.trace`` module "
    "or ``None``.",
] = _opentelemetry_trace
