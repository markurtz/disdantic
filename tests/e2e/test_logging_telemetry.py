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

from __future__ import annotations

import json
import logging
import types
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.logging import (
    LoggingSettings,
    OtelSink,
    _state,
    autolog,
    configure_logger,
    intercept_standard_logging,
    logger,
)

# Setup optional OpenTelemetry dependencies
trace: types.ModuleType | None
TracerProvider: type[Any] | None

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.trace import TracerProvider as OtelTracerProvider

    trace = otel_trace
    TracerProvider = OtelTracerProvider
except ImportError:
    trace = None
    TracerProvider = None


class TestLoggingTelemetry:
    """E2E test suite for Structured Logging & Telemetry Instrumentation."""

    @pytest.fixture(
        params=[
            {"enabled": True, "level": "DEBUG", "otel_formatting": "disable"},
            {"enabled": True, "level": "INFO", "otel_formatting": "enable"},
            {"enabled": False, "level": "WARNING", "otel_formatting": "auto"},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> LoggingSettings:
        """Fixture supplying properly initialized LoggingSettings instances."""
        return LoggingSettings(**request.param)

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(LoggingSettings, BaseSettings)
        assert callable(configure_logger)
        assert callable(autolog)
        assert issubclass(OtelSink, object)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: LoggingSettings) -> None:
        """Verify initialization mapping and logger configuration logic."""
        assert isinstance(valid_instances, LoggingSettings)
        original_handler_id = _state["handler_id"]
        try:
            stream = StringIO()
            settings = LoggingSettings(
                enabled=valid_instances.enabled,
                level=valid_instances.level,
                otel_formatting=valid_instances.otel_formatting,
                sink=stream,
                clear_loggers=True,
                enqueue=False,
                filter=False,  # Allow logs from this test module to bypass filter
            )
            configure_logger(settings)

            # Perform action: log a message
            logger.warning("initialization log check")

            output = stream.getvalue()
            if settings.enabled:
                assert "initialization log check" in output
            else:
                assert "initialization log check" not in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify explicit system blockages on invalid logging configurations."""
        with pytest.raises(ValidationError):
            LoggingSettings(otel_formatting=cast("Any", "invalid_option"))

        with pytest.raises(ValidationError):
            LoggingSettings(enabled=cast("Any", "not_a_boolean"))

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify fallback values when environment configurations are missing."""
        monkeypatch.delenv("DISDANTIC__LOGGING__ENABLED", raising=False)
        monkeypatch.delenv("DISDANTIC__LOGGING__LEVEL", raising=False)
        monkeypatch.delenv("DISDANTIC__LOGGING__OTEL_FORMATTING", raising=False)

        settings = LoggingSettings()
        assert settings.enabled is False
        assert settings.level == "WARNING"
        assert settings.otel_formatting == "auto"

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: LoggingSettings) -> None:
        """Verify Pydantic marshalling pipelines across module boundaries."""
        dumped_data = valid_instances.model_dump()
        reloaded_settings = LoggingSettings.model_validate(dumped_data)
        assert reloaded_settings.enabled == valid_instances.enabled
        assert reloaded_settings.level == valid_instances.level
        assert reloaded_settings.otel_formatting == valid_instances.otel_formatting

    @pytest.mark.regression
    def test_autolog_success(self) -> None:
        """Verify decorated function outputs entry and exit logs at DEBUG level."""
        stream = StringIO()
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    sink=stream,
                    level="DEBUG",
                    filter=False,
                    otel_formatting="disable",
                    enqueue=False,
                )
            )

            @autolog
            def compute_value(value_a: int, value_b: int) -> int:
                return value_a + value_b

            result = compute_value(2, 3)
            assert result == 5

            output = stream.getvalue()
            assert "Calling function" in output
            assert "compute_value" in output
            assert "args=(2, 3)" in output
            assert "returned: 5" in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_autolog_exception(self) -> None:
        """Verify decorated function logs exception trace at ERROR level."""
        stream = StringIO()
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    sink=stream,
                    level="DEBUG",
                    filter=False,
                    otel_formatting="disable",
                    enqueue=False,
                )
            )

            @autolog
            def compute_value(value_a: int, value_b: int) -> int:
                if value_a == 2:
                    raise ValueError("invalid math request")
                return value_a + value_b

            with pytest.raises(ValueError, match="invalid math request"):
                compute_value(2, 3)

            output = stream.getvalue()
            assert "Exception occurred in function" in output
            assert "compute_value" in output
            assert "invalid math request" in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_autolog_custom_exception_levels(self) -> None:
        """Verify autolog decorator with custom log levels or disabled reporting."""
        stream = StringIO()
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    sink=stream,
                    level="DEBUG",
                    filter=False,
                    otel_formatting="disable",
                    enqueue=False,
                )
            )

            @autolog(exception_log_level="WARNING")
            def compute_value_warn() -> None:
                raise ValueError("warn exception")

            with pytest.raises(ValueError, match="warn exception"):
                compute_value_warn()

            output = stream.getvalue()
            assert "Exception occurred in function" in output
            assert "WARNING" in output

            # Test exception_log_level=None
            @autolog(exception_log_level=None)
            def compute_value_none() -> None:
                raise ValueError("silent exception")

            with pytest.raises(ValueError, match="silent exception"):
                compute_value_none()
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_list_filter_prefixes(self) -> None:
        """Verify configure_logger handles list/tuple filtering prefixes correctly."""
        stream = StringIO()
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    sink=stream,
                    level="DEBUG",
                    filter=["disdantic", "tests.e2e"],
                    otel_formatting="disable",
                    enqueue=False,
                )
            )
            logger.warning("prefix allowed message")
            output = stream.getvalue()
            assert "prefix allowed message" in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_otel_json_logging(self) -> None:
        """Verify logs are serialized as OpenTelemetry-compliant JSON."""
        if trace is None or TracerProvider is None:
            pytest.skip("OpenTelemetry SDK is not installed in the environment.")

        # Ensure a provider is initialized
        try:
            if not isinstance(trace.get_tracer_provider(), TracerProvider):
                trace.set_tracer_provider(TracerProvider())
        except ValueError:
            pass

        stream = StringIO()
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    sink=stream,
                    level="DEBUG",
                    filter=False,
                    otel_formatting="enable",
                    enqueue=False,
                )
            )

            tracer = trace.get_tracer("disdantic-e2e")
            with tracer.start_as_current_span("e2e-span"):
                logger.debug("traced test message")

            output = stream.getvalue()
            assert output != ""

            # Parse output JSON
            log_record = json.loads(output.strip())

            assert "trace_id" in log_record
            assert "span_id" in log_record
            assert log_record["severity_text"] == "DEBUG"
            assert log_record["body"] == "traced test message"
            assert "attributes" in log_record

            attributes = log_record["attributes"]
            assert "module" in attributes
            assert "function" in attributes
            assert "process_id" in attributes
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_otel_formatting_missing_otel(self) -> None:
        """Verify configure_logger throws ImportError when otel is missing."""
        with (
            patch("disdantic.logging.opentelemetry_trace", None),
            pytest.raises(ImportError, match="OpenTelemetry is not installed"),
        ):
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    otel_formatting="enable",
                )
            )

    @pytest.mark.regression
    def test_otel_sink_close(self, tmp_path: Path) -> None:
        """Verify OtelSink close method handles target close cleanly."""
        log_file = tmp_path / "otel_close_test.log"
        sink = OtelSink(log_file)
        sink.write("raw log message\n")
        sink.close()
        assert log_file.read_text() == "raw log message\n"

    @pytest.mark.regression
    def test_otel_sink_with_file_path(self, tmp_path: Path) -> None:
        """Verify OtelSink handles Path target objects in configure_logger."""
        log_file = tmp_path / "otel_file_test.log"
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    sink=log_file,
                    level="DEBUG",
                    filter=False,
                    otel_formatting="enable",
                    enqueue=False,
                )
            )
            logger.debug("hello file otel")

            output = log_file.read_text()
            assert "hello file otel" in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_standard_logging_interception_e2e(self) -> None:
        """Verify standard library logging interception redirects to Loguru."""
        stream = StringIO()
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(
                LoggingSettings(
                    enabled=True,
                    sink=stream,
                    level="WARNING",
                    filter=False,
                    otel_formatting="disable",
                    enqueue=False,
                )
            )
            std_logger = logging.getLogger("test_interception_e2e")
            std_logger.warning("intercepted e2e warning message")

            output = stream.getvalue()
            assert "intercepted e2e warning message" in output
        finally:
            intercept_standard_logging(False)
            logger.remove()
            _state["handler_id"] = original_handler_id


class TestCLIEntrypoint:
    """E2E test suite for CLI entrypoints invoking logging setup."""

    @pytest.mark.smoke
    def test_cli_help(self) -> None:
        """Verify calling disdantic CLI with --help exits with 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Show the application version" in result.stdout

    @pytest.mark.smoke
    def test_cli_logging_execution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify calling disdantic CLI root triggers hello log."""
        monkeypatch.setenv("DISDANTIC__LOGGING__SINK", "stderr")
        monkeypatch.setenv("DISDANTIC__LOGGING__ENQUEUE", "false")

        original_handler_id = _state["handler_id"]
        try:
            runner = CliRunner()
            result = runner.invoke(app, [])
            assert result.exit_code == 0

            combined_output = result.stdout + result.stderr
            assert "Hello from disdantic" in combined_output
            assert "Settings:" in combined_output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.sanity
    def test_cli_invalid_subcommand(self) -> None:
        """Verify calling an invalid subcommand exits with non-zero error."""
        runner = CliRunner()
        result = runner.invoke(app, ["invalid-subcommand"])
        assert result.exit_code != 0
        assert "No such command" in result.stdout or "No such command" in result.stderr
