"""Unit tests for the __init__ module."""

from __future__ import annotations

import pytest

import template_python


@pytest.mark.smoke
def test___all__() -> None:
    """Verify that the root __init__.py correctly exposes expected API."""
    expected_exports = [
        "LoggingSettings",
        "Settings",
        "__version__",
        "configure_logger",
        "logger",
    ]
    assert template_python.__all__ == expected_exports
    for export_name in expected_exports:
        assert hasattr(template_python, export_name)
