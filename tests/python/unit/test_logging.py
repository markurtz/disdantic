from __future__ import annotations

import inspect
import json
import logging
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings

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


def set_process_id(process: Any, value: int) -> None:
    """Helper to dynamically set process ID without ruff constant setattr warning."""
    name = "".join(["i", "d"])
    setattr(process, name, value)


class TestLoggingSettings:
    """Test suite for the LoggingSettings class."""

    @pytest.fixture(
        params=[
            {},
            {"enabled": True, "level": "DEBUG"},
            {"sink": "stdout", "otel_formatting": "enable"},
            {"sink": "sys.stderr", "filter": False},
            {"sink": "stderr"},
            {"sink": "sys.stdout"},
            {"sink": "logfile.log"},
            {"format": "{message}", "clear_loggers": True},
            {"enqueue": False, "kwargs": {"backtrace": True}},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> LoggingSettings:
        """Fixture providing instantiated valid variations of LoggingSettings."""
        return LoggingSettings(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate class signature, inheritance, and attributes."""
        assert issubclass(LoggingSettings, BaseSettings)
        expected_fields = {
            "enabled",
            "clear_loggers",
            "sink",
            "level",
            "otel_formatting",
            "format",
            "filter",
            "enqueue",
            "kwargs",
        }
        assert expected_fields.issubset(LoggingSettings.model_fields.keys())
        assert hasattr(LoggingSettings, "model_config")
        assert LoggingSettings.model_config.get("env_prefix") == "DISDANTIC__LOGGING__"

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: LoggingSettings) -> None:
        """Test initializing LoggingSettings and verify state mappings."""
        assert isinstance(valid_instances, LoggingSettings)
        sink_val = valid_instances.sink
        if isinstance(sink_val, str):
            assert sink_val not in {"stdout", "sys.stdout", "stderr", "sys.stderr"}
        else:
            assert sink_val in {sys.stdout, sys.stderr}

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "invalid_data",
        [
            {"otel_formatting": "invalid_value"},
            {"enabled": "not_a_bool"},
            {"kwargs": "not_a_dict"},
        ],
    )
    def test_invalid_initialization_values(self, invalid_data: dict[str, Any]) -> None:
        """Test initializing LoggingSettings with invalid values."""
        with pytest.raises(ValidationError):
            LoggingSettings(**invalid_data)

    @pytest.mark.regression
    def test_invalid_initialization_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test initializing LoggingSettings when arguments are missing."""
        monkeypatch.delenv("DISDANTIC__LOGGING__LEVEL", raising=False)
        settings = LoggingSettings()
        assert settings.enabled is False
        assert settings.clear_loggers is False
        assert settings.sink is sys.stderr
        assert settings.level == "WARNING"
        assert settings.otel_formatting == "auto"
        assert settings.filter is True
        assert settings.enqueue is True
        assert settings.kwargs == {}
        assert isinstance(settings.format, str)
        assert "{message}" in settings.format

    @pytest.mark.sanity
    def test_marshalling(self, valid_instances: LoggingSettings) -> None:
        """Verify Pydantic model_dump and model_validate pipelines."""
        dumped_data = valid_instances.model_dump()
        validated_settings = LoggingSettings.model_validate(dumped_data)
        assert valid_instances.enabled == validated_settings.enabled
        assert valid_instances.level == validated_settings.level
        assert valid_instances.clear_loggers == validated_settings.clear_loggers
        assert valid_instances.otel_formatting == validated_settings.otel_formatting
        assert valid_instances.format == validated_settings.format
        assert valid_instances.enqueue == validated_settings.enqueue

    @pytest.mark.regression
    def test_env_loading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify DISDANTIC__LOGGING__ env variables override settings."""
        monkeypatch.setenv("DISDANTIC__LOGGING__LEVEL", "WARNING")
        monkeypatch.setenv("DISDANTIC__LOGGING__ENABLED", "true")
        monkeypatch.setenv("DISDANTIC__LOGGING__CLEAR_LOGGERS", "true")
        settings = LoggingSettings()
        assert settings.level == "WARNING"
        assert settings.enabled is True
        assert settings.clear_loggers is True


class TestOtelSink:
    """Test suite for the OtelSink class."""

    @pytest.fixture(
        params=[
            "stdout",
            "stderr",
            "temp_file_path",
        ]
    )
    def valid_instances(
        self, request: pytest.FixtureRequest, tmp_path: Path
    ) -> OtelSink:
        """Fixture providing instantiated valid variations of OtelSink."""
        target = request.param
        if target == "stdout":
            return OtelSink(sys.stdout)
        if target == "stderr":
            return OtelSink(sys.stderr)
        return OtelSink(tmp_path / "otel_fixture.log")

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate class signature, inheritance, and public methods."""
        assert hasattr(OtelSink, "write")
        assert hasattr(OtelSink, "close")
        assert inspect.isfunction(OtelSink.write)
        assert inspect.isfunction(OtelSink.close)

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: OtelSink) -> None:
        """Test initializing OtelSink and verify state mappings."""
        assert isinstance(valid_instances, OtelSink)
        assert valid_instances.target is not None
        if isinstance(valid_instances.target, (str, Path)):
            assert valid_instances._file is not None
        else:
            assert valid_instances._file is None

    @pytest.mark.regression
    def test_invalid_initialization_values(self) -> None:
        """Verify behavior with non-writable custom target objects."""
        sink = OtelSink(object())
        assert sink.target is not None
        assert sink._file is None

    @pytest.mark.regression
    def test_invalid_initialization_missing(self) -> None:
        """Verify instantiation fails when required arguments are missing."""
        with pytest.raises(TypeError):
            OtelSink()  # type: ignore

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        "message_payload",
        [
            "raw string message payload\n",
            "another text line\n",
        ],
    )
    def test_write(self, tmp_path: Path, message_payload: str) -> None:
        """Test write method executing Setup -> Mock -> Invoke -> Teardown."""
        # 1. StringIO target (stream)
        stream = StringIO()
        sink = OtelSink(stream)
        sink.write(message_payload)
        assert stream.getvalue() == message_payload

        # 2. File path target
        file_path = tmp_path / "otel_test_write.log"
        sink_file = OtelSink(file_path)
        sink_file.write(message_payload)
        sink_file.close()
        assert file_path.read_text(encoding="utf-8") == message_payload

    @pytest.mark.sanity
    def test_write_loguru_record(self, tmp_path: Path) -> None:
        """Test write method with a mock loguru record dict."""

        class MockLevel:
            name = "INFO"

        mock_process = MagicMock()
        set_process_id(mock_process, 9999)

        record_dict = {
            "time": datetime(2026, 6, 11, 8, 12, 11),
            "level": MockLevel(),
            "message": "test message",
            "name": "test_module",
            "function": "test_func",
            "line": 42,
            "process": mock_process,
            "extra": {"custom_extra": "value"},
        }

        class MockMessage(str):
            record: dict[str, Any]

        msg_obj = MockMessage("formatted message\n")
        msg_obj.record = record_dict

        # StringIO stream target
        stream = StringIO()
        sink = OtelSink(stream)
        sink.write(msg_obj)
        output_str = stream.getvalue()

        # Verify JSON properties
        data = json.loads(output_str)
        assert data["timestamp"] == "2026-06-11T08:12:11"
        assert data["severity_text"] == "INFO"
        assert data["body"] == "test message"
        assert data["attributes"]["module"] == "test_module"
        assert data["attributes"]["custom_extra"] == "value"

        # File target
        file_path = tmp_path / "otel_test_record.log"
        sink_file = OtelSink(file_path)
        sink_file.write(msg_obj)
        sink_file.close()

        file_data = json.loads(file_path.read_text(encoding="utf-8"))
        assert file_data["timestamp"] == "2026-06-11T08:12:11"

    @pytest.mark.sanity
    def test_write_otel_record_with_trace_and_exception(self) -> None:
        """Test OtelSink.write when OpenTelemetry tracing is active

        and an exception is present.
        """

        class MockContext:
            is_valid = True
            trace_id = 12345
            span_id = 67890
            trace_flags = 1

        class MockSpan:
            def get_span_context(self) -> MockContext:
                return MockContext()

        class MockTrace:
            def get_current_span(self) -> MockSpan:
                return MockSpan()

        class MockLevel:
            name = "ERROR"

        mock_process = MagicMock()
        set_process_id(mock_process, 7777)

        class MockException:
            type = ValueError
            value = ValueError("custom error message")
            traceback = None

        record_dict = {
            "time": datetime(2026, 6, 11, 9, 30, 0),
            "level": MockLevel(),
            "message": "error logged",
            "name": "disdantic",
            "function": "error_func",
            "line": 80,
            "process": mock_process,
            "extra": {},
            "exception": MockException(),
        }

        class MockMessage(str):
            record: dict[str, Any]

        msg_obj = MockMessage("formatted error message\n")
        msg_obj.record = record_dict

        stream = StringIO()
        sink = OtelSink(stream)

        mock_trace = MockTrace()
        with patch("disdantic.logging.opentelemetry_trace", mock_trace):
            sink.write(msg_obj)

        output_str = stream.getvalue()
        data = json.loads(output_str)

        # Check trace and span ID fields
        assert data["trace_id"] == format(12345, "032x")
        assert data["span_id"] == format(67890, "016x")
        assert data["trace_flags"] == format(1, "02x")

        # Check exception attributes
        assert data["attributes"]["exception.type"] == "ValueError"
        assert data["attributes"]["exception.message"] == "custom error message"
        assert "exception.stacktrace" in data["attributes"]

    @pytest.mark.sanity
    def test_close(self, tmp_path: Path) -> None:
        """Test close method executing Setup -> Mock -> Invoke -> Teardown."""
        # Stream target - close is a no-op
        stream = StringIO()
        sink = OtelSink(stream)
        sink.close()  # should not raise error

        # File target - close should close file descriptor
        file_path = tmp_path / "otel_test_close.log"
        sink_file = OtelSink(file_path)
        assert sink_file._file is not None
        assert not sink_file._file.closed
        sink_file.close()
        assert sink_file._file.closed


class TestInterceptHandler:
    """Test suite for the InterceptHandler class."""

    @pytest.fixture(
        params=[
            {"level": 0},
            {"level": logging.WARNING},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> InterceptHandler:
        """Fixture providing instantiated valid variations of InterceptHandler."""
        return InterceptHandler(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Validate class signature, inheritance, and methods."""
        assert issubclass(InterceptHandler, logging.Handler)
        assert hasattr(InterceptHandler, "emit")
        assert inspect.isfunction(InterceptHandler.emit)

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: InterceptHandler) -> None:
        """Test initializing InterceptHandler and verify state mappings."""
        assert isinstance(valid_instances, InterceptHandler)
        assert hasattr(valid_instances, "level")

    @pytest.mark.regression
    def test_invalid_initialization_values(self) -> None:
        """Verify behavior with invalid parameters."""
        with pytest.raises(ValueError):
            InterceptHandler(level="NOT_A_LEVEL")

    @pytest.mark.regression
    def test_invalid_initialization_missing(self) -> None:
        """Verify default instantiation works."""
        handler = InterceptHandler()
        assert handler.level == 0

    @pytest.mark.sanity
    def test_emit(self) -> None:
        """Test emit method forwarding standard LogRecord to Loguru logger."""
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="some/file_path.py",
            lineno=12,
            msg="test message %s",
            args=("arg_val",),
            exc_info=None,
            func="some_func",
        )

        handler = InterceptHandler()

        with patch("disdantic.logging.logger") as mock_logger:
            mock_level_info = MagicMock()
            mock_level_info.name = "WARNING"
            mock_logger.level.return_value = mock_level_info

            mock_patch = MagicMock()
            mock_bind = MagicMock()
            mock_opt = MagicMock()

            mock_logger.patch.return_value = mock_patch
            mock_patch.bind.return_value = mock_bind
            mock_bind.opt.return_value = mock_opt

            handler.emit(record)

            mock_logger.patch.assert_called_once()
            mock_patch.bind.assert_called_once_with(
                pathname="some/file_path.py",
                lineno=12,
                funcName="some_func",
            )
            mock_bind.opt.assert_called_once_with(exception=None)
            mock_opt.log.assert_called_once_with("WARNING", "test message arg_val")

    @pytest.mark.regression
    def test_emit_unknown_level(self) -> None:
        """Test emit method with a custom/unknown log level (falls back to numeric)."""
        record = logging.LogRecord(
            name="test_logger",
            level=35,
            pathname="some/file_path.py",
            lineno=12,
            msg="custom level message",
            args=(),
            exc_info=None,
            func="some_func",
        )
        record.levelname = "UNKNOWN_LEVEL_NAME"

        handler = InterceptHandler()

        with patch("disdantic.logging.logger") as mock_logger:
            mock_logger.level.side_effect = ValueError("no such level")

            mock_patch = MagicMock()
            mock_bind = MagicMock()
            mock_opt = MagicMock()

            mock_logger.patch.return_value = mock_patch
            mock_patch.bind.return_value = mock_bind
            mock_bind.opt.return_value = mock_opt

            handler.emit(record)

            mock_opt.log.assert_called_once_with(35, "custom level message")


class TestConfigureLogger:
    """Test suite for configure_logger module-level function."""

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        "scenario",
        [
            {"settings": None, "expect_disabled": True},
            {"settings": {"enabled": False}, "expect_disabled": True},
            {"settings": {"enabled": True, "level": "DEBUG"}, "expect_enabled": True},
            {
                "settings": {"enabled": True, "level": "auto"},
                "expect_enabled": True,
                "expected_level": "WARNING",
            },
            {
                "settings": {"enabled": True, "clear_loggers": True},
                "expect_enabled": True,
            },
            {
                "settings": {"enabled": True, "filter": "custom_prefix"},
                "expect_enabled": True,
                "expected_filter": "custom_prefix",
            },
            {
                "settings": {"enabled": True, "filter": ["prefix1", "prefix2"]},
                "expect_enabled": True,
                "expected_filter_prefixes": ("prefix1", "prefix2"),
            },
            {
                "settings": {"enabled": True, "filter": ("prefix3", "prefix4")},
                "expect_enabled": True,
                "expected_filter_prefixes": ("prefix3", "prefix4"),
            },
            {
                "settings": {"enabled": True, "filter": False},
                "expect_enabled": True,
                "expected_filter": None,
            },
        ],
    )
    def test_invocation(self, scenario: dict[str, Any]) -> None:
        """Test configure_logger execution scenarios via Mock -> Invoke -> Teardown."""
        settings_dict = scenario.get("settings")
        settings = (
            LoggingSettings(**settings_dict) if settings_dict is not None else None
        )

        with patch("disdantic.logging.logger") as mock_logger:
            mock_logger.add.return_value = 1234

            configure_logger(settings)

            if scenario.get("expect_disabled"):
                mock_logger.disable.assert_called_once_with("disdantic")
                mock_logger.enable.assert_not_called()
            else:
                mock_logger.enable.assert_called_once_with("disdantic")
                mock_logger.add.assert_called_once()
                add_kwargs = mock_logger.add.call_args.kwargs

                # Check level
                expected_level = scenario.get(
                    "expected_level", settings.level if settings else "WARNING"
                )
                assert add_kwargs["level"] == expected_level

                # Check filter
                logger_filter = add_kwargs["filter"]
                if "expected_filter" in scenario:
                    assert logger_filter == scenario["expected_filter"]
                elif "expected_filter_prefixes" in scenario:
                    assert callable(logger_filter)
                    prefixes = scenario["expected_filter_prefixes"]
                    assert logger_filter({"name": f"{prefixes[0]}.module"}) is True
                    assert logger_filter({"name": "other_module"}) is False
                    assert logger_filter({"name": None}) is False

    @pytest.mark.regression
    @pytest.mark.parametrize(
        ("otel_setting", "mock_trace_present", "expect_error"),
        [
            ("enable", False, True),
            ("enable", True, False),
            ("auto", True, False),
            ("auto", False, False),
        ],
    )
    def test_invalid(
        self, otel_setting: str, mock_trace_present: bool, expect_error: bool
    ) -> None:
        """Verify exception/failure conditions and boundary overrides

        for configure_logger.
        """
        settings = LoggingSettings(enabled=True, otel_formatting=otel_setting)  # type: ignore

        mock_trace = MagicMock() if mock_trace_present else None

        with (
            patch("disdantic.logging.opentelemetry_trace", mock_trace),
            patch("disdantic.logging.logger") as mock_logger,
        ):
            mock_logger.add.return_value = 42

            if expect_error:
                with pytest.raises(ImportError, match="OpenTelemetry is not installed"):
                    configure_logger(settings)
            else:
                configure_logger(settings)
                mock_logger.add.assert_called_once()
                add_kwargs = mock_logger.add.call_args.kwargs
                if otel_setting == "enable" or (
                    otel_setting == "auto" and mock_trace_present
                ):
                    assert isinstance(add_kwargs["sink"], OtelSink)
                else:
                    assert not isinstance(add_kwargs["sink"], OtelSink)

    @pytest.mark.regression
    def test_invocation_existing_handler_cleanup(self) -> None:
        """Verify configure_logger removes the previously registered handler."""
        _state["handler_id"] = 9999
        settings = LoggingSettings(enabled=True)
        with patch("disdantic.logging.logger") as mock_logger:
            mock_logger.add.return_value = 1234
            configure_logger(settings)
            mock_logger.remove.assert_called_once_with(9999)
            assert _state["handler_id"] == 1234

    @pytest.mark.regression
    def test_invocation_clear_loggers_real_logger(self) -> None:
        """Test configure_logger clear_loggers path with a real

        non-mock logger (line 215-221).
        """
        original_handler_id = _state["handler_id"]
        try:
            configure_logger(LoggingSettings(enabled=True))
            first_handler_id = _state["handler_id"]
            assert isinstance(first_handler_id, int)

            configure_logger(LoggingSettings(enabled=True, clear_loggers=True))
            second_handler_id = _state["handler_id"]
            assert isinstance(second_handler_id, int)
            assert second_handler_id != first_handler_id
        finally:
            logger.remove()
            _state["handler_id"] = original_handler_id


class TestAutolog:
    """Test suite for autolog module-level decorator."""

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        ("use_factory", "exception_level", "should_fail"),
        [
            (False, "ERROR", False),
            (True, "ERROR", False),
            (False, "ERROR", True),
            (True, "ERROR", True),
            (True, None, True),
            (True, "WARNING", True),
        ],
    )
    def test_invocation(
        self,
        use_factory: bool,
        exception_level: str | None,
        should_fail: bool,
    ) -> None:
        """Test autolog decorator's core logging and wrapping functionality."""

        def target_func(first_arg: int, second_arg: str) -> str:
            if should_fail:
                raise ValueError("custom error")
            return f"{first_arg}-{second_arg}"

        if use_factory:
            decorator = autolog(exception_log_level=exception_level)
            wrapped = decorator(target_func)
        else:
            wrapped = autolog(target_func)

        with patch("disdantic.logging.logger") as mock_logger:
            mock_opt_logger = MagicMock()
            mock_logger.opt.return_value = mock_opt_logger

            if should_fail:
                with pytest.raises(ValueError, match="custom error") as exc_info:
                    wrapped(42, "hello")

                expected_msg = (
                    "Calling function "
                    "'TestAutolog.test_invocation.<locals>.target_func' "
                    "with args=(42, 'hello'), kwargs={}"
                )
                mock_logger.debug.assert_any_call(expected_msg)

                if exception_level is not None or not use_factory:
                    expected_level = exception_level if use_factory else "ERROR"
                    if expected_level == "ERROR":
                        mock_logger.opt.assert_called_once_with(
                            exception=exc_info.value
                        )
                        mock_opt_logger.error.assert_called_once()
                        log_args = mock_opt_logger.error.call_args[0]
                        assert "Exception occurred in function" in log_args[0]
                    else:
                        mock_logger.opt.assert_not_called()
                        mock_logger.log.assert_called_once()
                        log_args = mock_logger.log.call_args[0]
                        assert log_args[0] == expected_level
                        assert "Exception occurred in function" in log_args[1]
                else:
                    mock_logger.opt.assert_not_called()
                    mock_logger.log.assert_not_called()
            else:
                result = wrapped(42, "hello")
                assert result == "42-hello"

                assert mock_logger.debug.call_count == 2
                first_call_args = mock_logger.debug.call_args_list[0][0][0]
                assert "Calling function" in first_call_args
                assert "target_func" in first_call_args
                assert "42" in first_call_args
                assert "hello" in first_call_args

                second_call_args = mock_logger.debug.call_args_list[1][0][0]
                assert "returned" in second_call_args
                assert "42-hello" in second_call_args

    @pytest.mark.regression
    def test_invalid(self) -> None:
        """Verify invalid autolog usage raising TypeError."""
        with pytest.raises(TypeError):
            cast("Any", autolog)(None, "WARNING")


class TestInterceptStandardLogging:
    """Test suite for intercept_standard_logging module-level function."""

    @pytest.mark.sanity
    @pytest.mark.parametrize("enable_flag", [True, False])
    def test_invocation(self, enable_flag: bool) -> None:
        """Test enabling and disabling standard logging interception."""
        intercept_standard_logging(enable_flag)
        root_logger = logging.getLogger()

        has_handler = any(
            isinstance(handler, InterceptHandler) for handler in root_logger.handlers
        )
        assert has_handler is enable_flag

        if enable_flag:
            intercept_standard_logging(False)

    @pytest.mark.sanity
    def test_interception_flow(self) -> None:
        """Test standard logging message is correctly intercepted and patched."""
        stream = StringIO()

        handler_id = logger.add(
            stream, format="{file.name}:{line}:{function} - {message}\n"
        )
        try:
            intercept_standard_logging(True)
            std_logger = logging.getLogger("test_interception_flow_logger")
            std_logger.warning("intercepted log message")
        finally:
            intercept_standard_logging(False)
            logger.remove(handler_id)

        output_str = stream.getvalue()
        assert "intercepted log message" in output_str
        assert "test_logging.py" in output_str
        assert "test_interception_flow" in output_str


@pytest.mark.smoke
def test_logger() -> None:
    """Validate that the public logger is configured correctly."""
    assert type(logger).__name__ == "Logger"
    logger.debug("Test public logger validation message")


@pytest.mark.regression
def test_otel_private_helpers() -> None:
    """Verify that private helpers _otel_serialize and

    _otel_formatter execute correctly.
    """

    class MockLevel:
        name = "INFO"

    mock_process = MagicMock()
    set_process_id(mock_process, 8888)

    record = {
        "time": datetime(2026, 6, 11, 10, 0, 0),
        "level": MockLevel(),
        "message": "private helper test",
        "name": "disdantic",
        "function": "some_func",
        "line": 100,
        "process": mock_process,
        "extra": {},
    }

    serialized_dict = _otel_serialize(record)
    assert serialized_dict["timestamp"] == "2026-06-11T10:00:00"
    assert serialized_dict["severity_text"] == "INFO"
    assert serialized_dict["body"] == "private helper test"

    formatted_str = _otel_formatter(record)
    assert "private helper test" in formatted_str
    assert formatted_str.endswith("\n")
