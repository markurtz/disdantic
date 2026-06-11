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
Configure logging infrastructure and provide utilities for disdantic.

This module initializes and manages the global logger via the
`configure_logger` interface, establishing log levels, target sinks, and
thread-safe queues. It supports standard library logging interception through
`InterceptHandler` and `intercept_standard_logging`, automated function
telemetry via the `autolog` decorator, and structured OpenTelemetry-compliant
JSON logging using the `OtelSink` wrapper.

Veteran maintainers can quickly use `configure_logger` with `LoggingSettings` to
configure logging behavior, while new contributors can leverage the `autolog`
decorator to auto-instrument functions.
"""

from __future__ import annotations

import contextlib
import functools
import json
import logging
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, TypeVar, cast, overload

from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from disdantic.compat import opentelemetry_trace

__all__ = [
    "InterceptHandler",
    "LoggingSettings",
    "OtelSink",
    "autolog",
    "configure_logger",
    "intercept_standard_logging",
    "logger",
]


class LoggingSettings(BaseSettings):
    """
    Settings configuration for the disdantic logging subsystem.

    This class defines the configuration schema for logging, loading parameters
    from environment variables prefixed with `DISDANTIC__LOGGING__` or via
    direct instantiation. It allows customizing the output sink, log level,
    format template, OpenTelemetry integration, and thread-safe queueing.

    Example:
        .. code-block:: python

            from disdantic.logging import LoggingSettings, configure_logger

            settings = LoggingSettings(
                enabled=True,
                level="DEBUG",
                sink="stdout"
            )
            configure_logger(settings)

    :cvar model_config: Configuration dictionary dictating environment variable
                        prefixes and nested delimiters.
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Enables or disables logging output across the disdantic package."
        ),
    )
    clear_loggers: bool = Field(
        default=False,
        description=(
            "Configures whether all existing active logger sinks "
            "are removed prior to setup."
        ),
    )
    sink: str | Any = Field(
        default=sys.stderr,
        description=(
            "Specifies and maps the output target, such as standard streams "
            "(stdout, stderr) or a file path, for log messages."
        ),
    )
    level: str = Field(
        default="WARNING",
        description=(
            "Configures the minimum severity level required for log messages "
            "to be emitted."
        ),
    )
    otel_formatting: Literal["auto", "enable", "disable"] = Field(
        default="auto",
        description=(
            "Configures the OpenTelemetry-compliant JSON formatting option "
            "(auto, enable, or disable)."
        ),
    )
    format: str | Callable[..., Any] | None = Field(
        default="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>\n",
        description=(
            "Configures the standard text template layout for emitted log lines."
        ),
    )
    filter: Any = Field(
        default=True,
        description=(
            "Configures the filtering criteria, using a prefix string, "
            "list of prefixes, or a filter function."
        ),
    )
    enqueue: bool = Field(
        default=True,
        description="Enables or disables asynchronous, thread-safe message queueing.",
    )
    kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Maps additional custom arguments passed directly "
            "to the loguru add handler."
        ),
    )

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="DISDANTIC__LOGGING__",
        env_nested_delimiter="__",
    )

    @field_validator("sink", mode="before")
    @classmethod
    def _parse_sink(cls, value: Any) -> Any:
        # Convert string aliases for standard output/error streams to stream objects.
        if isinstance(value, str):
            mapping = {
                "stdout": sys.stdout,
                "sys.stdout": sys.stdout,
                "stderr": sys.stderr,
                "sys.stderr": sys.stderr,
            }
            return mapping.get(value.lower(), value)
        return value


def configure_logger(  # noqa: C901, PLR0912, PLR0915
    settings: LoggingSettings | None = None,
    **default_overrides: Any,
) -> None:
    """
    Configure the global Loguru logger based on settings.

    This function initializes or updates the active logger handler. If no
    settings are provided, it loads settings from environment variables.
    It enables interception of standard library log statements and configures
    formatting, sinks, filtering, and queue options.

    Example:
        .. code-block:: python

            from disdantic.logging import LoggingSettings, configure_logger

            configure_logger(
                settings=LoggingSettings(level="INFO"),
                clear_loggers=True
            )

    :param settings: Logging configurations, defaults to None (loads from environment).
    :param default_overrides: Parameter overrides merged into env settings if
                              settings is None.
    :returns: None.
    :raises ImportError: Raised if OpenTelemetry formatting is enabled but the
                         package is not installed.
    """
    if settings is None:
        env_settings = LoggingSettings()
        merged = default_overrides.copy()
        for field in env_settings.model_fields_set:
            merged[field] = getattr(env_settings, field)
        settings = LoggingSettings(**merged)

    if not settings.enabled:
        logger.disable("disdantic")
        intercept_standard_logging(False)
        return

    logger.enable("disdantic")
    intercept_standard_logging(True)

    if settings.clear_loggers:
        if hasattr(logger, "_mock_name") or type(logger).__name__ in (
            "MagicMock",
            "Mock",
        ):
            logger.remove()
        else:
            for handler_id, handler in list(cast("Any", logger)._core.handlers.items()):  # noqa: SLF001
                sink = getattr(handler, "_sink", None)
                handler_obj = getattr(sink, "_handler", None)
                if handler_obj and type(handler_obj).__name__ == "PropagateHandler":
                    continue
                with contextlib.suppress(ValueError):
                    logger.remove(handler_id)
        _state["handler_id"] = None
    elif isinstance(_state["handler_id"], int):
        with contextlib.suppress(ValueError):
            logger.remove(_state["handler_id"])
        _state["handler_id"] = None

    use_otel = settings.otel_formatting == "enable" or (
        settings.otel_formatting == "auto" and opentelemetry_trace is not None
    )
    if settings.otel_formatting == "enable" and opentelemetry_trace is None:
        raise ImportError(
            "OpenTelemetry is not installed but 'otel_formatting' was set to 'enable'."
        )

    if use_otel:
        sink_val = OtelSink(settings.sink)
        log_format = "{message}\n"
    else:
        sink_val = settings.sink
        log_format = settings.format

    filter_val = "disdantic" if settings.filter is True else settings.filter

    if isinstance(filter_val, str):
        final_filter: Any = filter_val
    elif isinstance(filter_val, (list, tuple)):
        prefixes = tuple(filter_val)

        def final_filter(record: dict[str, Any]) -> bool:
            return bool(record["name"] and record["name"].startswith(prefixes))

    else:
        final_filter = None if filter_val is False else filter_val

    # Resolve "auto" log level
    level_val = settings.level
    if level_val == "auto":
        level_val = "WARNING"

    _state["handler_id"] = logger.add(
        sink=cast("Any", sink_val),
        level=level_val,
        filter=cast("Any", final_filter),
        format=cast("Any", log_format),
        enqueue=settings.enqueue,
        **settings.kwargs,
    )


@overload
def autolog(func: _FuncT) -> _FuncT:
    """
    Decorate a function to automatically log call inputs, outputs, and exceptions.

    :param func: Target function to wrap.
    :returns: The decorated wrapper.
    """


@overload
def autolog(
    func: None = None,
    *,
    exception_log_level: str | None = "ERROR",
) -> Callable[[_FuncT], _FuncT]:
    """
    Create a decorator factory to log functions with a custom exception log level.

    :param func: Must be None.
    :param exception_log_level: Log level for exception reporting, defaults to "ERROR".
    :returns: A decorator factory function.
    """


def autolog(
    func: _FuncT | None = None,
    *,
    exception_log_level: str | None = "ERROR",
) -> _FuncT | Callable[[_FuncT], _FuncT]:
    """
    Decorate a function to automatically log call inputs, outputs, and
    raised exceptions.

    This decorator logs inputs before execution, logs the return value on
    success, and logs any raised exceptions with trace details before
    re-raising.

    Example:
        .. code-block:: python

            from disdantic.logging import autolog

            @autolog
            def calculate_sum(a: int, b: int) -> int:
                return a + b

    :param func: Target function to wrap, defaults to None.
    :param exception_log_level: Log level for exception reporting, defaults to "ERROR".
    :returns: The decorated wrapper or a decorator factory function.
    """

    def decorator(func_to_wrap: _FuncT) -> _FuncT:
        @functools.wraps(func_to_wrap)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = getattr(func_to_wrap, "__qualname__", "function")
            logger.debug(
                _LOG_ENTRY_FORMAT.format(name=func_name, args=args, kwargs=kwargs)
            )
            try:
                result = func_to_wrap(*args, **kwargs)
            except Exception as error:
                if exception_log_level == "ERROR":
                    logger.opt(exception=error).error(
                        _LOG_EXCEPTION_FORMAT.format(name=func_name, exception=error),
                    )
                elif exception_log_level is not None:
                    logger.log(
                        exception_log_level,
                        _LOG_EXCEPTION_FORMAT.format(name=func_name, exception=error),
                    )
                raise error
            else:
                logger.debug(_LOG_EXIT_FORMAT.format(name=func_name, result=result))
                return result

        return cast("_FuncT", wrapper)

    if func is None:
        return decorator
    return decorator(func)


class OtelSink:
    """
    Wrapper sink for OpenTelemetry-compliant JSON logging.

    This class intercepts log messages emitted by Loguru, extracts metadata
    from the Loguru record (such as exception tracebacks, trace context,
    and process info), and serializes them into standard OpenTelemetry JSON format.

    Example:
        .. code-block:: python

            import sys
            from disdantic.logging import OtelSink

            sink = OtelSink(sys.stderr)
            sink.write("Hello log message")

    """

    target: Annotated[
        Any,
        "The target output stream or file path where log records are written.",
    ]

    def __init__(self, target: Any) -> None:
        """
        Initialize the OpenTelemetry sink wrapper.

        :param target: Output stream or file path where log records are written.
        :returns: None.
        """
        self.target = target
        self._file = None
        if isinstance(target, (str, Path)):
            self._file = Path(target).open("a", encoding="utf-8")  # noqa: SIM115

    def write(self, message: str) -> None:
        """
        Write a message to the target output after formatting it as
        OpenTelemetry JSON if possible.

        :param message: The log message to serialize or write.
        :returns: None.
        """
        record = getattr(message, "record", None)
        if record is not None:
            log_record = _build_otel_record(record)
            serialized = json.dumps(log_record) + "\n"
        else:
            serialized = message

        if self._file is not None:
            self._file.write(serialized)
            self._file.flush()
        elif hasattr(self.target, "write"):
            self.target.write(serialized)
            if hasattr(self.target, "flush"):
                self.target.flush()

    def close(self) -> None:
        """
        Close the underlying file descriptor if a file path was provided as target.

        :returns: None.
        """
        if self._file is not None:
            self._file.close()


class InterceptHandler(logging.Handler):
    """
    Standard logging handler to intercept and forward records to Loguru.

    This class hooks into the standard Python `logging` module. When a
    standard logging record is emitted, it translates the logging level
    and redirects the message, caller context, and exception trace to the
    Loguru pipeline, ensuring unified log aggregation.

    Example:
        .. code-block:: python

            import logging
            from disdantic.logging import InterceptHandler

            logging.basicConfig(handlers=[InterceptHandler()], level=0)

    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a standard library logging record by forwarding it to Loguru.

        :param record: The standard library log record.
        :returns: None.
        """
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Pass the caller info directly to loguru via patch and bind
        # to avoid slow frame walking or runtime function/closure definition.
        logger.patch(_static_patcher).bind(
            pathname=record.pathname,
            lineno=record.lineno,
            funcName=record.funcName,
        ).opt(exception=record.exc_info).log(level, record.getMessage())


def intercept_standard_logging(enable: bool = True) -> None:
    """
    Hook standard library logging into or detach it from the Loguru pipeline.

    This function attaches `InterceptHandler` to the standard root logger
    to redirect standard library logs, or removes it to restore the
    previous logging handlers.

    Example:
        .. code-block:: python

            from disdantic.logging import intercept_standard_logging

            intercept_standard_logging(enable=True)

    :param enable: True to intercept standard logging; False to detach and restore.
    :returns: None.
    """
    root = logging.getLogger()
    if enable:
        if not _standard_handlers:
            handler = InterceptHandler()
            root.addHandler(handler)
            _standard_handlers.append(handler)
    else:
        # Restore a clean environment slate using our tracked handlers
        for handler in _standard_handlers:
            root.removeHandler(handler)
        _standard_handlers.clear()


# --- Private Helper Variables and Constants ---

_state: dict[str, int | None] = {"handler_id": None}
_standard_handlers: list[logging.Handler] = []

_LOG_ENTRY_FORMAT: str = "Calling function '{name}' with args={args}, kwargs={kwargs}"
_LOG_EXIT_FORMAT: str = "Function '{name}' returned: {result}"
_LOG_EXCEPTION_FORMAT: str = "Exception occurred in function '{name}': {exception}"

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])


class _FileInfo:
    # Helper containing path and name attributes for Loguru records.

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path


def _static_patcher(record: Any) -> None:
    extra = record["extra"]
    pathname = extra.pop("pathname", None)
    if pathname is not None:
        record["file"] = _FileInfo(
            name=Path(pathname).name if pathname else "",
            path=pathname or "",
        )
    lineno = extra.pop("lineno", None)
    if lineno is not None:
        record["line"] = lineno or 0
    func_name = extra.pop("funcName", None)
    if func_name is not None:
        record["function"] = func_name or ""


def _build_otel_record(record: dict[str, Any]) -> dict[str, Any]:
    # Format the log record as an OpenTelemetry compliant dictionary.
    trace_id = span_id = trace_flags = None

    if opentelemetry_trace:
        span = opentelemetry_trace.get_current_span()
        context = span.get_span_context()
        if context.is_valid:
            trace_id = format(context.trace_id, "032x")
            span_id = format(context.span_id, "016x")
            trace_flags = format(context.trace_flags, "02x")

    log_record = {
        "timestamp": record["time"].isoformat(),
        "severity_text": record["level"].name,
        "body": record["message"],
        "resource": {"service.name": "disdantic"},
        "attributes": {
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "process_id": record["process"].id,
            **record["extra"],
        },
    }

    if record.get("exception"):
        exception = record["exception"]
        log_record["attributes"]["exception.type"] = exception.type.__name__
        log_record["attributes"]["exception.message"] = str(exception.value)
        log_record["attributes"]["exception.stacktrace"] = "".join(
            traceback.format_exception(
                exception.type, exception.value, exception.traceback
            )
        )

    if trace_id:
        log_record.update(
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "trace_flags": trace_flags,
            }
        )

    return log_record


def _otel_serialize(record: dict[str, Any]) -> dict[str, Any]:
    # Format the log record as an OpenTelemetry compliant dictionary.
    return _build_otel_record(record)


def _otel_formatter(record: dict[str, Any]) -> str:
    # Format the log record as an OpenTelemetry compliant JSON string.
    log_record = _build_otel_record(record)
    # Escape braces so loguru doesn't interpret the JSON string as a format string
    # Escape '<' and '>' to prevent loguru from interpreting them as color markup tags
    return (
        json.dumps(log_record)
        .replace("{", "{{")
        .replace("}", "}}")
        .replace("<", "\\<")
        .replace(">", "\\>")
    ) + "\n"


logger: Annotated[
    Any,
    "The global Loguru logger instance re-exported from loguru.",
]
