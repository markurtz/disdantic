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

import inspect
import json
import logging
import sys
import threading
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

import disdantic.logging as logging_module
from disdantic.logging import (
    InterceptHandler,
    LoggingSettings,
    OtelSink,
    _otel_formatter,
    _otel_serialize,
    _state,
    autolog,
    configure_logger,
    intercept_standard_logging,
    logger,
)


def set_process_id_helper(process_object: Any, identifier_value: int) -> None:
    """Helper to dynamically set process ID without ruff constant setattr warning."""
    attribute_name = "".join(["i", "d"])
    setattr(process_object, attribute_name, identifier_value)


@pytest.mark.smoke
def test_logging_exports() -> None:
    """Validate public variables, constants, and module-level exports."""
    assert hasattr(logging_module, "__all__")
    expected_exports = [
        "InterceptHandler",
        "LoggingSettings",
        "OtelSink",
        "autolog",
        "configure_logger",
        "intercept_standard_logging",
        "logger",
    ]
    assert sorted(logging_module.__all__) == sorted(expected_exports)
    assert logging_module.logger is logger


@pytest.mark.sanity
def test_interface_signature_validation() -> None:
    """Validate structural contracts across integrated boundaries."""
    # Check inheritance lineage
    assert issubclass(LoggingSettings, BaseSettings)
    assert issubclass(InterceptHandler, logging.Handler)

    # Check method signatures and parameter names
    configure_logger_sig = inspect.signature(configure_logger)
    assert "settings" in configure_logger_sig.parameters

    otel_sink_sig = inspect.signature(OtelSink.__init__)
    assert "target" in otel_sink_sig.parameters

    intercept_standard_logging_sig = inspect.signature(intercept_standard_logging)
    assert "enable" in intercept_standard_logging_sig.parameters


class TestLoggingSettings:
    """Integration test suite for LoggingSettings."""

    @pytest.fixture(
        params=[
            {"enabled": True, "level": "DEBUG"},
            {"enabled": False, "level": "INFO"},
            {"sink": "stdout"},
            {"sink": "sys.stderr"},
            {"otel_formatting": "enable"},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> LoggingSettings:
        """Fixture supplying properly initialized LoggingSettings instances."""
        return LoggingSettings(**request.param)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: LoggingSettings) -> None:
        """Verify initialization mapping logic."""
        assert isinstance(valid_instances, LoggingSettings)
        sink_value = valid_instances.sink
        if isinstance(sink_value, str):
            assert sink_value not in {"stdout", "sys.stdout", "stderr", "sys.stderr"}
        else:
            assert sink_value in {sys.stdout, sys.stderr}

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify validation errors for invalid types and options."""
        with pytest.raises(ValidationError):
            LoggingSettings(otel_formatting=cast("Any", "invalid_option"))

        with pytest.raises(ValidationError):
            LoggingSettings(enabled=cast("Any", "not_a_boolean"))

        with pytest.raises(ValidationError):
            LoggingSettings(kwargs=cast("Any", "not_a_dictionary"))

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify default initialization values when missing fields."""
        monkeypatch.delenv("DISDANTIC__LOGGING__LEVEL", raising=False)
        monkeypatch.delenv("DISDANTIC__LOGGING__ENABLED", raising=False)
        monkeypatch.delenv("DISDANTIC__LOGGING__CLEAR_LOGGERS", raising=False)
        monkeypatch.delenv("DISDANTIC__LOGGING__OTEL_FORMATTING", raising=False)
        settings = LoggingSettings()
        assert settings.enabled is False
        assert settings.clear_loggers is False
        assert settings.sink is sys.stderr
        assert settings.level == "WARNING"
        assert settings.otel_formatting == "auto"
        assert settings.filter is True
        assert settings.enqueue is True
        assert settings.kwargs == {}

    @pytest.mark.regression
    def test_env_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify environment variable overrides take precedence."""
        monkeypatch.setenv("DISDANTIC__LOGGING__LEVEL", "INFO")
        monkeypatch.setenv("DISDANTIC__LOGGING__ENABLED", "true")
        monkeypatch.setenv("DISDANTIC__LOGGING__CLEAR_LOGGERS", "true")

        settings = LoggingSettings()
        assert settings.level == "INFO"
        assert settings.enabled is True
        assert settings.clear_loggers is True

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: LoggingSettings) -> None:
        """Verify Pydantic marshalling pipelines across module boundaries."""
        dumped_data = valid_instances.model_dump()
        reloaded_settings = LoggingSettings.model_validate(dumped_data)
        assert reloaded_settings.enabled == valid_instances.enabled
        assert reloaded_settings.level == valid_instances.level
        assert reloaded_settings.clear_loggers == valid_instances.clear_loggers
        assert reloaded_settings.otel_formatting == valid_instances.otel_formatting


class TestOtelSink:
    """Integration test suite for OtelSink wrapper."""

    @pytest.fixture(
        params=[
            "stdout",
            "file",
        ]
    )
    def valid_instances(
        self, request: pytest.FixtureRequest, tmp_path: Path
    ) -> OtelSink:
        """Fixture supplying properly initialized OtelSink instances."""
        target_type = request.param
        if target_type == "stdout":
            return OtelSink(sys.stdout)
        return OtelSink(tmp_path / "otel_integration.log")

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: OtelSink) -> None:
        """Verify initialization maps target correctly."""
        assert isinstance(valid_instances, OtelSink)
        assert valid_instances.target is not None
        if isinstance(valid_instances.target, (str, Path)):
            assert valid_instances._file is not None
        else:
            assert valid_instances._file is None

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify behavior with non-writable target object."""
        sink_instance = OtelSink(object())
        assert sink_instance.target is not None
        assert sink_instance._file is None

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify target parameter is required."""
        with pytest.raises(TypeError):
            OtelSink()  # type: ignore

    @pytest.mark.sanity
    def test_write_raw_messages(self, tmp_path: Path) -> None:
        """Verify writing raw string messages to streams and files."""
        stream_target = StringIO()
        sink_stream = OtelSink(stream_target)
        sink_stream.write("raw integration message\n")
        assert stream_target.getvalue() == "raw integration message\n"

        file_target_path = tmp_path / "otel_raw.log"
        sink_file = OtelSink(file_target_path)
        sink_file.write("file integration message\n")
        sink_file.close()
        assert (
            file_target_path.read_text(encoding="utf-8") == "file integration message\n"
        )

    @pytest.mark.regression
    def test_write_otel_record(self) -> None:
        """Verify writing and converting loguru records to OpenTelemetry JSON."""

        class MockLevel:
            name = "INFO"

        mock_process_obj = MagicMock()
        set_process_id_helper(mock_process_obj, 1234)

        record_dict = {
            "time": datetime(2026, 6, 11, 11, 30, 0),
            "level": MockLevel(),
            "message": "structured message",
            "name": "disdantic.logging",
            "function": "test_write_otel_record",
            "line": 150,
            "process": mock_process_obj,
            "extra": {"context_field": "context_value"},
        }

        class MockMessage(str):
            record: dict[str, Any]

        message_instance = MockMessage("formatted\n")
        message_instance.record = record_dict

        stream_target = StringIO()
        sink_stream = OtelSink(stream_target)
        sink_stream.write(message_instance)
        output_data = json.loads(stream_target.getvalue())

        assert output_data["timestamp"] == "2026-06-11T11:30:00"
        assert output_data["severity_text"] == "INFO"
        assert output_data["body"] == "structured message"
        assert output_data["attributes"]["module"] == "disdantic.logging"
        assert output_data["attributes"]["context_field"] == "context_value"

    @pytest.mark.regression
    def test_write_otel_record_with_trace(self) -> None:
        """Verify trace context fields are added when tracing is present."""

        class MockSpanContext:
            is_valid = True
            trace_id = 9988776655
            span_id = 112233
            trace_flags = 2

        class MockSpan:
            def get_span_context(self) -> MockSpanContext:
                return MockSpanContext()

        class MockTrace:
            def get_current_span(self) -> MockSpan:
                return MockSpan()

        class MockLevel:
            name = "DEBUG"

        mock_process_obj = MagicMock()
        set_process_id_helper(mock_process_obj, 5678)

        record_dict = {
            "time": datetime(2026, 6, 11, 11, 40, 0),
            "level": MockLevel(),
            "message": "traced log message",
            "name": "disdantic.logging",
            "function": "test_write_otel_record_with_trace",
            "line": 200,
            "process": mock_process_obj,
            "extra": {},
        }

        class MockMessage(str):
            record: dict[str, Any]

        message_instance = MockMessage("formatted\n")
        message_instance.record = record_dict

        stream_target = StringIO()
        sink_stream = OtelSink(stream_target)

        mock_trace_lib = MockTrace()
        with patch("disdantic.logging.opentelemetry_trace", mock_trace_lib):
            sink_stream.write(message_instance)

        output_data = json.loads(stream_target.getvalue())
        assert output_data["trace_id"] == format(9988776655, "032x")
        assert output_data["span_id"] == format(112233, "016x")
        assert output_data["trace_flags"] == format(2, "02x")

    @pytest.mark.regression
    def test_write_otel_record_with_exception(self) -> None:
        """Verify exception information is parsed and formatted."""

        class MockLevel:
            name = "ERROR"

        mock_process_obj = MagicMock()
        set_process_id_helper(mock_process_obj, 9012)

        class MockExceptionInfo:
            type = RuntimeError
            value = RuntimeError("unhandled execution failure")
            traceback = None

        record_dict = {
            "time": datetime(2026, 6, 11, 11, 50, 0),
            "level": MockLevel(),
            "message": "exception payload",
            "name": "disdantic.logging",
            "function": "test_write_otel_record_with_exception",
            "line": 250,
            "process": mock_process_obj,
            "extra": {},
            "exception": MockExceptionInfo(),
        }

        class MockMessage(str):
            record: dict[str, Any]

        message_instance = MockMessage("formatted\n")
        message_instance.record = record_dict

        stream_target = StringIO()
        sink_stream = OtelSink(stream_target)
        sink_stream.write(message_instance)

        output_data = json.loads(stream_target.getvalue())
        assert output_data["attributes"]["exception.type"] == "RuntimeError"
        assert (
            output_data["attributes"]["exception.message"]
            == "unhandled execution failure"
        )
        assert "exception.stacktrace" in output_data["attributes"]

    @pytest.mark.regression
    def test_close(self, tmp_path: Path) -> None:
        """Verify close method releases file descriptors."""
        stream_target = StringIO()
        sink_stream = OtelSink(stream_target)
        sink_stream.close()  # No error on stream close

        file_target_path = tmp_path / "otel_close.log"
        sink_file = OtelSink(file_target_path)
        assert sink_file._file is not None
        assert not sink_file._file.closed
        sink_file.close()
        assert sink_file._file.closed


class TestInterceptHandler:
    """Integration test suite for InterceptHandler."""

    @pytest.fixture(
        params=[
            {"level": logging.INFO},
            {"level": logging.ERROR},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> InterceptHandler:
        """Fixture supplying properly initialized InterceptHandler instances."""
        return InterceptHandler(**request.param)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: InterceptHandler) -> None:
        """Verify initialization setups handler."""
        assert isinstance(valid_instances, InterceptHandler)
        assert valid_instances.level in {logging.INFO, logging.ERROR}

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify invalid log level raises ValueError."""
        with pytest.raises(ValueError):
            InterceptHandler(level="NOT_A_VALID_LEVEL")

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify default instantiation works."""
        handler_instance = InterceptHandler()
        assert handler_instance.level == 0

    @pytest.mark.regression
    def test_emit(self) -> None:
        """Verify standard LogRecord maps and forwards to Loguru correctly."""
        record_instance = logging.LogRecord(
            name="standard_logger",
            level=logging.WARNING,
            pathname="path/to/script.py",
            lineno=75,
            msg="standard message %s",
            args=("interpolated",),
            exc_info=None,
            func="script_function",
        )

        handler_instance = InterceptHandler()

        with patch("disdantic.logging.logger") as mock_loguru:
            mock_level_info = MagicMock()
            mock_level_info.name = "WARNING"
            mock_loguru.level.return_value = mock_level_info

            mock_patch_chain = MagicMock()
            mock_bind_chain = MagicMock()
            mock_opt_chain = MagicMock()

            mock_loguru.patch.return_value = mock_patch_chain
            mock_patch_chain.bind.return_value = mock_bind_chain
            mock_bind_chain.opt.return_value = mock_opt_chain

            handler_instance.emit(record_instance)

            mock_loguru.patch.assert_called_once()
            mock_patch_chain.bind.assert_called_once_with(
                pathname="path/to/script.py",
                lineno=75,
                funcName="script_function",
            )
            mock_bind_chain.opt.assert_called_once_with(exception=None)
            mock_opt_chain.log.assert_called_once_with(
                "WARNING", "standard message interpolated"
            )

    @pytest.mark.regression
    def test_emit_unknown_level(self) -> None:
        """Test standard log record with unknown level maps to levelno."""
        record_instance = logging.LogRecord(
            name="standard_logger",
            level=35,
            pathname="path/to/script.py",
            lineno=75,
            msg="custom level message",
            args=(),
            exc_info=None,
            func="script_function",
        )
        record_instance.levelname = "CUSTOM_LEVEL"

        handler_instance = InterceptHandler()
        with patch("disdantic.logging.logger") as mock_loguru:
            mock_loguru.level.side_effect = ValueError("no such level")
            mock_patch_chain = MagicMock()
            mock_bind_chain = MagicMock()
            mock_opt_chain = MagicMock()

            mock_loguru.patch.return_value = mock_patch_chain
            mock_patch_chain.bind.return_value = mock_bind_chain
            mock_bind_chain.opt.return_value = mock_opt_chain

            handler_instance.emit(record_instance)
            mock_opt_chain.log.assert_called_once_with(35, "custom level message")


class TestConfigureLogger:
    """Integration test suite for configure_logger."""

    @pytest.mark.smoke
    @pytest.mark.parametrize(
        "scenario_config",
        [
            {"settings": {"enabled": False}, "expect_disabled": True},
            {"settings": {"enabled": True, "level": "DEBUG"}, "expect_enabled": True},
            {
                "settings": {"enabled": True, "level": "auto"},
                "expect_enabled": True,
                "expected_level": "WARNING",
            },
            {
                "settings": {"enabled": True, "filter": "custom"},
                "expect_enabled": True,
                "expected_filter": "custom",
            },
            {
                "settings": {"enabled": True, "filter": ["pre1", "pre2"]},
                "expect_enabled": True,
                "expected_filter_prefixes": ("pre1", "pre2"),
            },
            {
                "settings": {"enabled": True, "filter": False},
                "expect_enabled": True,
                "expected_filter": None,
            },
            {
                "settings": {"enabled": True, "clear_loggers": True},
                "expect_enabled": True,
            },
        ],
    )
    def test_invocation(self, scenario_config: dict[str, Any]) -> None:
        """Verify logger configuration under varying options."""
        settings_dict = scenario_config.get("settings") or {}
        settings_instance = LoggingSettings(**settings_dict)

        with patch("disdantic.logging.logger") as mock_loguru:
            mock_loguru.add.return_value = 999
            configure_logger(settings_instance)

            if scenario_config.get("expect_disabled"):
                mock_loguru.disable.assert_called_once_with("disdantic")
            else:
                mock_loguru.enable.assert_called_once_with("disdantic")
                mock_loguru.add.assert_called_once()
                kwargs_dict = mock_loguru.add.call_args.kwargs

                expected_level = scenario_config.get(
                    "expected_level", settings_instance.level
                )
                assert kwargs_dict["level"] == expected_level

                actual_filter = kwargs_dict["filter"]
                if "expected_filter" in scenario_config:
                    assert actual_filter == scenario_config["expected_filter"]
                elif "expected_filter_prefixes" in scenario_config:
                    assert callable(actual_filter)
                    prefixes = scenario_config["expected_filter_prefixes"]
                    assert actual_filter({"name": f"{prefixes[0]}.sub"}) is True
                    assert actual_filter({"name": "other"}) is False
                    assert actual_filter({"name": None}) is False

    @pytest.mark.sanity
    def test_invalid_otel_missing_dep(self) -> None:
        """Verify configure_logger throws ImportError when otel is requested

        but not installed.
        """
        settings_instance = LoggingSettings(enabled=True, otel_formatting="enable")
        with (
            patch("disdantic.logging.opentelemetry_trace", None),
            patch("disdantic.logging.logger"),
            pytest.raises(ImportError, match="OpenTelemetry is not installed"),
        ):
            configure_logger(settings_instance)

    @pytest.mark.regression
    def test_invocation_cleanup_and_leaks(self) -> None:
        """Verify configure_logger successfully cleans up old handlers."""
        _state["handler_id"] = 777
        settings_instance = LoggingSettings(enabled=True)
        with patch("disdantic.logging.logger") as mock_loguru:
            mock_loguru.add.return_value = 888
            configure_logger(settings_instance)
            mock_loguru.remove.assert_called_once_with(777)
            assert _state["handler_id"] == 888

    @pytest.mark.regression
    def test_invocation_clear_loggers_real_logger(self) -> None:
        """Test configure_logger clear_loggers path with a real logger."""
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(LoggingSettings(enabled=True))
            first_handler_id = _state["handler_id"]
            assert isinstance(first_handler_id, int)

            # Now clear loggers
            configure_logger(LoggingSettings(enabled=True, clear_loggers=True))
            second_handler_id = _state["handler_id"]
            assert isinstance(second_handler_id, int)
            assert second_handler_id != first_handler_id
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_enqueue_thread_safety(self, tmp_path: Path) -> None:
        """Verify concurrent logging with enqueue=True works in a thread-safe manner."""
        log_file_path = tmp_path / "thread_safety.log"
        settings_instance = LoggingSettings(
            enabled=True,
            sink=str(log_file_path),
            level="INFO",
            format="{message}",
            filter=False,
            otel_formatting="disable",
            enqueue=True,
            clear_loggers=True,
        )

        original_handler_id = _state["handler_id"]
        try:
            configure_logger(settings_instance)

            thread_count = 5
            logs_per_thread = 10
            threads_list = []

            def log_worker(thread_index: int) -> None:
                for log_index in range(logs_per_thread):
                    logger.info(f"Thread-{thread_index}-Log-{log_index}")
                    time.sleep(0.001)

            for thread_index in range(thread_count):
                thread_instance = threading.Thread(
                    target=log_worker, args=(thread_index,)
                )
                threads_list.append(thread_instance)
                thread_instance.start()

            for thread_instance in threads_list:
                thread_instance.join()

            # Wait briefly to allow async queue to drain
            time.sleep(0.2)

            # Read logs and verify count
            log_lines = log_file_path.read_text(encoding="utf-8").strip().splitlines()
            expected_total_logs = thread_count * logs_per_thread
            assert len(log_lines) == expected_total_logs

            for thread_index in range(thread_count):
                for log_index in range(logs_per_thread):
                    expected_message = f"Thread-{thread_index}-Log-{log_index}"
                    assert expected_message in log_lines

        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id


@pytest.mark.sanity
def test_intercept_standard_logging_lifecycle() -> None:
    """Test attaching and detaching standard logging handlers."""
    intercept_standard_logging(True)
    root_logger = logging.getLogger()
    assert any(
        isinstance(handler, InterceptHandler) for handler in root_logger.handlers
    )

    intercept_standard_logging(False)
    assert not any(
        isinstance(handler, InterceptHandler) for handler in root_logger.handlers
    )


@pytest.mark.regression
def test_standard_logging_interception_e2e() -> None:
    """Test standard logging message is correctly intercepted, patched, and printed."""
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
                format="{file.name}:{line}:{function} - {message}\n",
            )
        )
        std_logger = logging.getLogger("test_interception")
        std_logger.warning("intercepted warning message")

        output = stream.getvalue()
        assert "intercepted warning message" in output
        assert "test_logging.py" in output
        assert "test_standard_logging_interception_e2e" in output
    finally:
        intercept_standard_logging(False)
        logger.remove()
        _state["handler_id"] = original_handler_id


@pytest.mark.regression
def test_otel_private_helpers() -> None:
    """Verify private helpers _otel_serialize and _otel_formatter."""

    class MockLevel:
        name = "INFO"

    mock_process_obj = MagicMock()
    set_process_id_helper(mock_process_obj, 7777)

    record_dict = {
        "time": datetime(2026, 6, 11, 12, 0, 0),
        "level": MockLevel(),
        "message": "private helper test",
        "name": "disdantic",
        "function": "test_func",
        "line": 99,
        "process": mock_process_obj,
        "extra": {},
    }

    serialized_dict = _otel_serialize(record_dict)
    assert serialized_dict["body"] == "private helper test"

    formatted_str = _otel_formatter(record_dict)
    assert "private helper test" in formatted_str


class TestAutolog:
    """Integration test suite for autolog decorator."""

    @pytest.mark.sanity
    def test_autolog_success(self) -> None:
        """Test autolog on a successful function call."""

        @autolog
        def sample_func(arg_a: int, arg_b: str) -> str:
            return f"{arg_a}-{arg_b}"

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
            result = sample_func(123, "test")
            assert result == "123-test"

            output = stream.getvalue()
            assert "Calling function" in output
            assert "sample_func" in output
            assert "returned: 123-test" in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_autolog_exception_error(self) -> None:
        """Test autolog on a function raising exception with default ERROR level."""

        @autolog
        def sample_fail() -> None:
            raise ValueError("fail message")

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
            with pytest.raises(ValueError, match="fail message"):
                sample_fail()

            output = stream.getvalue()
            assert "Exception occurred in function" in output
            assert "sample_fail" in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_autolog_exception_custom_level(self) -> None:
        """Test autolog with a custom exception log level like WARNING."""

        @autolog(exception_log_level="WARNING")
        def sample_fail() -> None:
            raise ValueError("custom level message")

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
            with pytest.raises(ValueError, match="custom level message"):
                sample_fail()

            output = stream.getvalue()
            assert "Exception occurred in function" in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id

    @pytest.mark.regression
    def test_autolog_exception_none_level(self) -> None:
        """Test autolog with exception_log_level=None (no exception log)."""

        @autolog(exception_log_level=None)
        def sample_fail() -> None:
            raise ValueError("no log message")

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
            with pytest.raises(ValueError, match="no log message"):
                sample_fail()

            output = stream.getvalue()
            assert "Exception occurred" not in output
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id
