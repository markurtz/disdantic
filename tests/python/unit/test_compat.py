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

"""Unit tests for the compatibility module."""

from __future__ import annotations

import importlib
import os
import sys
import types
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from disdantic import compat


@pytest.fixture
def sys_modules_backup() -> Generator[None, None, None]:
    """Fixture to back up and restore sys.modules related to opentelemetry."""
    orig_opentelemetry = sys.modules.get("opentelemetry")
    orig_opentelemetry_trace = sys.modules.get("opentelemetry.trace")

    yield

    # Restore original sys.modules values
    if orig_opentelemetry is None:
        sys.modules.pop("opentelemetry", None)
    else:
        sys.modules["opentelemetry"] = orig_opentelemetry

    if orig_opentelemetry_trace is None:
        sys.modules.pop("opentelemetry.trace", None)
    else:
        sys.modules["opentelemetry.trace"] = orig_opentelemetry_trace

    # Reload compat to restore original state
    importlib.reload(compat)


@pytest.mark.smoke
def test_opentelemetry_trace() -> None:
    """Verify opentelemetry_trace is exported and has correct type/value constraints."""
    assert hasattr(compat, "opentelemetry_trace")
    assert compat.opentelemetry_trace is None or isinstance(
        compat.opentelemetry_trace, types.ModuleType
    )


@pytest.mark.sanity
def test_opentelemetry_trace_present(
    sys_modules_backup: Generator[None, None, None],
) -> None:
    """Verify opentelemetry_trace holds trace when opentelemetry is present."""
    mock_trace = MagicMock(spec=types.ModuleType)
    mock_opentelemetry = MagicMock(spec=types.ModuleType)
    mock_opentelemetry.trace = mock_trace

    sys.modules["opentelemetry"] = mock_opentelemetry
    sys.modules["opentelemetry.trace"] = mock_trace

    importlib.reload(compat)

    assert compat.opentelemetry_trace is mock_trace


@pytest.mark.sanity
def test_opentelemetry_trace_absent(
    sys_modules_backup: Generator[None, None, None],
) -> None:
    """Verify opentelemetry_trace is None when opentelemetry is not present."""
    # Mask both modules to force an ImportError
    sys.modules["opentelemetry"] = None  # type: ignore
    sys.modules.pop("opentelemetry.trace", None)

    importlib.reload(compat)

    assert compat.opentelemetry_trace is None


@pytest.mark.smoke
def test_compat_exports() -> None:
    """Verify the module exports and __all__ list matching."""
    assert compat.__all__ == ["opentelemetry_trace", "yaml"]


@pytest.mark.sanity
def test_yaml_present_absent() -> None:
    """Verify yaml is exported and can be present or absent."""
    assert hasattr(compat, "yaml")
    assert compat.yaml is None or isinstance(compat.yaml, types.ModuleType)


@pytest.mark.smoke
def test_disable_pyston_env_var() -> None:
    """Verify that DISABLE_PYSTON environment variable is configured to '1'."""
    assert os.environ.get("DISABLE_PYSTON") == "1"
