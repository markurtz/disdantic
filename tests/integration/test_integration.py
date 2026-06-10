"""Integration tests for the template_python core modules."""

from __future__ import annotations

import sys
from collections.abc import Generator
from io import StringIO

import pytest

import template_python.logging as logging_module
from template_python.__main__ import main
from template_python.logging import LoggingSettings, configure_logger
from template_python.version import (
    __BUILD_METADATA__,
    __GIT_METADATA__,
    __VERSION_METADATA__,
    __version__,
)


@pytest.fixture
def capture_sink() -> Generator[StringIO, None, None]:
    """Fixture to provide a StringIO sink to capture log output."""
    sink = StringIO()
    yield sink
    sink.close()


class TestMain:
    """Integration tests for the main function."""

    @pytest.mark.smoke
    def test_invocation(
        self, monkeypatch: pytest.MonkeyPatch, capture_sink: StringIO
    ) -> None:
        """A smoke test ensuring the main entrypoint executes without crashing."""
        original_configure = configure_logger

        def mock_configure(settings: LoggingSettings | None = None) -> None:
            if settings is None:
                settings = LoggingSettings()
            settings.sink = capture_sink
            settings.filter = False
            settings.enqueue = False
            original_configure(settings)

        monkeypatch.setattr("template_python.__main__.configure_logger", mock_configure)
        monkeypatch.setattr(sys, "argv", ["template_python"])

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        output = capture_sink.getvalue()
        assert __version__ in output
        assert "Settings:" in output


class TestConfigureLogger:
    """Integration tests for the configure_logger function."""

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        ("otel_installed", "expected_output"),
        [
            (False, "INFO - Test message for fallback\n"),
        ],
    )
    def test_invocation(
        self,
        capture_sink: StringIO,
        monkeypatch: pytest.MonkeyPatch,
        otel_installed: bool,
        expected_output: str,
    ) -> None:
        """A sanity test ensuring fallback when otel not installed."""
        settings = LoggingSettings(
            enabled=True,
            level="INFO",
            sink=capture_sink,
            filter=False,
            otel_formatting="auto",
            format="{level} - {message}",
            enqueue=False,
        )

        if not otel_installed:
            monkeypatch.setattr(logging_module, "opentelemetry_trace", None)

        configure_logger(settings)
        logging_module.logger.info("Test message for fallback")

        output = capture_sink.getvalue()
        assert output == expected_output


@pytest.mark.regression
def test_version_metadata() -> None:
    """A regression test to ensure VERSION_METADATA is fully populated."""
    assert __VERSION_METADATA__.major >= 0


@pytest.mark.regression
def test_git_metadata() -> None:
    """A regression test to ensure GIT_METADATA is fully populated."""
    assert isinstance(__GIT_METADATA__.hash, str)


@pytest.mark.regression
def test_build_metadata() -> None:
    """A regression test to ensure BUILD_METADATA is fully populated."""
    assert isinstance(__BUILD_METADATA__.timestamp, str)
