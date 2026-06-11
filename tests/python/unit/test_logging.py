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

"""Unit tests for the logging module."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from typing import Any, cast
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from pydantic_settings import BaseSettings

from disdantic.logging import (
    LoggingSettings,
    _state,
    autolog,
    configure_logger,
)
from disdantic.logging import (
    logger as global_logger,
)


@pytest.fixture(autouse=True)
def reset_logger_fixture() -> Generator[None, None, None]:
    """Ensure loggers are cleared after each test."""
    yield
    global_logger.remove()
    global_logger.enable("disdantic")
    _state["handler_id"] = None


class TestLoggingSettings:
    """Test suite for the LoggingSettings model."""

    @pytest.fixture(
        params=[
            {},
            {"enabled": True, "level": "DEBUG"},
            {"enabled": False, "sink": "stdout"},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> LoggingSettings:
        """Fixture providing valid instances of LoggingSettings."""
        return LoggingSettings(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify the class signature and fields."""
        assert issubclass(LoggingSettings, BaseSettings)
        assert hasattr(LoggingSettings, "model_config")
        assert LoggingSettings.model_config.get("env_prefix") == "DISDANTIC__LOGGING__"
        assert "enabled" in LoggingSettings.model_fields
        assert "level" in LoggingSettings.model_fields

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: LoggingSettings) -> None:
        """Test proper initialization."""
        assert isinstance(valid_instances.enabled, bool)
        assert isinstance(valid_instances.level, str)

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: LoggingSettings) -> None:
        """Test Pydantic dumping and validation."""
        data_dict = valid_instances.model_dump()
        recreated_settings = LoggingSettings.model_validate(data_dict)
        assert recreated_settings.enabled == valid_instances.enabled
        assert recreated_settings.level == valid_instances.level


class TestConfigureLogger:
    """Test suite for the configure_logger function."""

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"enabled": False},
            {"enabled": True, "level": "DEBUG", "clear_loggers": True},
            {
                "enabled": True,
                "filter": ("disdantic", "__main__"),
                "clear_loggers": True,
            },
        ],
    )
    def test_invocation(self, kwargs: dict[str, Any]) -> None:
        """Test successful configuration of the global logger."""
        settings_obj = LoggingSettings(**kwargs)  # type: ignore[arg-type]
        configure_logger(settings_obj)

        if settings_obj.enabled:
            global_logger.debug("Test invocation")

    @pytest.mark.sanity
    def test_invalid(self) -> None:
        """
        Test ImportError when otel_formatting is explicitly enabled without package.
        """
        settings_obj = LoggingSettings(enabled=True, otel_formatting="enable")
        with (
            mock.patch("disdantic.logging.opentelemetry_trace", None),
            pytest.raises(ImportError, match="OpenTelemetry is not installed"),
        ):
            configure_logger(settings_obj)

    @pytest.mark.sanity
    @pytest.mark.parametrize(
        ("settings_dict", "mock_otel", "expect_otel"),
        [
            ({"enabled": True, "otel_formatting": "disable"}, True, False),
            ({"enabled": True, "otel_formatting": "auto"}, True, True),
            ({"enabled": True, "otel_formatting": "auto"}, False, False),
            ({"enabled": True, "otel_formatting": "enable"}, True, True),
        ],
    )
    def test_invocation_otel(
        self,
        settings_dict: dict[str, Any],
        mock_otel: bool,
        expect_otel: bool,
    ) -> None:
        """Test configure_logger correctly configures OpenTelemetry formatting."""
        settings = LoggingSettings(**settings_dict)

        with patch("disdantic.logging.logger") as mock_logger:
            mock_logger.add.return_value = 42
            if mock_otel:
                mock_trace = MagicMock()
                mock_span = MagicMock()
                mock_context = MagicMock()
                mock_context.is_valid = True
                mock_context.trace_id = 12345
                mock_context.span_id = 67890
                mock_context.trace_flags = 1
                mock_span.get_span_context.return_value = mock_context
                mock_trace.get_current_span.return_value = mock_span
                patch_target = "disdantic.logging.opentelemetry_trace"
                with patch(patch_target, mock_trace):
                    configure_logger(settings)
            else:
                with patch("disdantic.logging.opentelemetry_trace", None):
                    configure_logger(settings)

            mock_logger.add.assert_called_once()
            add_kwargs = mock_logger.add.call_args.kwargs

            if expect_otel:
                assert callable(add_kwargs["format"])

                class MockLevel:
                    name = "INFO"

                class MockProcess:
                    id = 1234

                record_data: dict[str, Any] = {
                    "time": datetime.now(),
                    "level": MockLevel(),
                    "message": "test message {with} <brackets>",
                    "name": "disdantic.test",
                    "function": "func",
                    "line": 10,
                    "extra": {"custom_key": "custom_val"},
                    "process": MockProcess(),
                }

                # Verify formatter output formatting with trace details
                if mock_otel:
                    with patch("disdantic.logging.opentelemetry_trace", mock_trace):
                        formatted_log = add_kwargs["format"](record_data)
                        assert "trace_id" in formatted_log
                        assert "span_id" in formatted_log
                        assert "trace_flags" in formatted_log
                        assert "\\<brackets\\>" in formatted_log
                        assert "{{with}}" in formatted_log
                        assert "process_id" in formatted_log
            else:
                assert add_kwargs["format"] == settings.format


class TestAutolog:
    """Test suite for the autolog decorator."""

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

                # Verify entry log
                expected_msg = (
                    "Calling function "
                    "'TestAutolog.test_invocation.<locals>.target_func' "
                    "with args=(42, 'hello'), kwargs={}"
                )
                mock_logger.debug.assert_any_call(expected_msg)

                # Verify exception log
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

                # Verify entry and exit debug logs
                assert mock_logger.debug.call_count == 2
                first_call_args = mock_logger.debug.call_args_list[0][0][0]
                assert "Calling function" in first_call_args
                assert "target_func" in first_call_args
                assert "42" in first_call_args
                assert "hello" in first_call_args

                second_call_args = mock_logger.debug.call_args_list[1][0][0]
                assert "returned" in second_call_args
                assert "42-hello" in second_call_args

    @pytest.mark.sanity
    def test_invalid(self) -> None:
        """Verify invalid autolog usage raising TypeError."""
        with pytest.raises(TypeError):
            cast("Any", autolog)(None, "WARNING")
