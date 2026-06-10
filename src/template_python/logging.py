"""
Loguru-based logging configuration and environment settings for template_python.

This module provides a unified interface for configuring application-level logging
using loguru and Pydantic settings. It handles dynamic OpenTelemetry formatting,
across the codebase and build environments.
"""

from __future__ import annotations

import contextlib
import json
import sys
import traceback
from collections.abc import Callable
from typing import Any, ClassVar, Literal

from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from template_python.compat import opentelemetry_trace

__all__ = ["LoggingSettings", "configure_logger", "logger"]

_HANDLER_ID: int | None = None


class LoggingSettings(BaseSettings):
    """
    Settings model for configuring the loguru logging infrastructure.

    This Pydantic model loads configuration from environment variables prefixed
    with ``TEMPLATE_PYTHON__LOGGING__`` and provides typed fields for controlling
    log output, formatting, and OpenTelemetry integration.

    Example:
        .. code-block:: python

            from template_python.logging import LoggingSettings, configure_logger

            settings = LoggingSettings(enabled=True, level="DEBUG")
            configure_logger(settings)
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Whether to enable template_python loguru logging across the application."
        ),
    )
    clear_loggers: bool = Field(
        default=False,
        description=(
            "If true, removes all existing loguru handlers before configuring new ones."
        ),
    )
    sink: str | Any = Field(
        default=sys.stdout,
        description=(
            "The output sink for log messages. Can be an object or string "
            "alias ('stdout')."
        ),
    )
    level: str = Field(
        default="INFO",
        description="The minimum severity level for emitted log messages.",
    )
    otel_formatting: Literal["auto", "enable", "disable"] = Field(
        default="auto",
        description=(
            "Controls OpenTelemetry JSON formatting. 'auto' enables it if "
            "otel is installed."
        ),
    )
    format: str | Callable[..., Any] | None = Field(
        default="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>\n",
        description=(
            "The log format string or function to use when otel formatting is disabled."
        ),
    )
    filter: Any = Field(
        default=True,
        description=(
            "Filters log records. Defaults to True to filter by the "
            "'template_python' prefix."
        ),
    )
    enqueue: bool = Field(
        default=True,
        description="Whether to enable thread-safe asynchronous logging.",
    )
    kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Additional keyword arguments to pass directly to loguru's add() method."
        ),
    )

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="TEMPLATE_PYTHON__LOGGING__",
        env_nested_delimiter="__",
    )
    """Pydantic configuration dict dictating environment variable prefixes."""

    @field_validator("sink", mode="before")
    @classmethod
    def _parse_sink(cls, value: Any) -> Any:
        # Convert string aliases for stdout/stderr to actual objects.
        if isinstance(value, str):
            mapping = {
                "stdout": sys.stdout,
                "sys.stdout": sys.stdout,
                "stderr": sys.stderr,
                "sys.stderr": sys.stderr,
            }
            return mapping.get(value.lower(), value)
        return value


def _otel_formatter(record: dict[str, Any]) -> str:
    # Format the log record as an OpenTelemetry compliant JSON string.
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
        "resource": {"service.name": "template_python"},
        "attributes": {
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
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

    # Escape braces so loguru doesn't interpret the JSON string as a format string
    return json.dumps(log_record).replace("{", "{{").replace("}", "}}") + "\n"


def configure_logger(settings: LoggingSettings | None = None) -> None:
    """
    Initializes the loguru logger with the provided settings or from the environment.

    This function configures the global loguru logger instance based on the provided
    ``LoggingSettings``. It handles enabling/disabling the logger, managing sinks,
    and injecting the appropriate formatter (including OpenTelemetry).

    Example:
        .. code-block:: python

            from template_python.logging import configure_logger, LoggingSettings

            configure_logger(LoggingSettings(level="DEBUG"))

    :param settings: An optional instance of ``LoggingSettings``. If not provided,
                     settings are automatically loaded from the environment.
    :return: None
    :raises ImportError: If OpenTelemetry formatting is explicitly enabled but the
                         package is not installed.
    """
    global _HANDLER_ID  # noqa: PLW0603

    settings = settings or LoggingSettings()

    if not settings.enabled:
        logger.disable("template_python")
        return

    logger.enable("template_python")

    if settings.clear_loggers:
        logger.remove()
        _HANDLER_ID = None
    elif isinstance(_HANDLER_ID, int):
        with contextlib.suppress(ValueError):
            logger.remove(_HANDLER_ID)
        _HANDLER_ID = None

    use_otel = settings.otel_formatting == "enable" or (
        settings.otel_formatting == "auto" and opentelemetry_trace is not None
    )
    if settings.otel_formatting == "enable" and opentelemetry_trace is None:
        raise ImportError(
            "OpenTelemetry is not installed but 'otel_formatting' was set to 'enable'."
        )

    log_format = _otel_formatter if use_otel else settings.format
    filter_val = "template_python" if settings.filter is True else settings.filter

    if isinstance(filter_val, (list, tuple)):
        prefixes = tuple(filter_val)

        def final_filter(record: dict[str, Any]) -> bool:
            return bool(record["name"] and record["name"].startswith(prefixes))

    elif isinstance(filter_val, str):

        def final_filter(record: dict[str, Any]) -> bool:
            return bool(record["name"] and record["name"].startswith(filter_val))

    else:
        final_filter = None if filter_val is False else filter_val  # type: ignore[assignment]

    _HANDLER_ID = logger.add(
        settings.sink,  # type: ignore[arg-type]
        level=settings.level,
        filter=final_filter,  # type: ignore[arg-type]
        format=log_format,  # type: ignore[arg-type]
        enqueue=settings.enqueue,
        **settings.kwargs,
    )
