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
Main entrypoint for the disdantic package.

This module provides the executable routine when the package is run directly
via the command line (e.g., ``python -m disdantic``). It uses Typer to define
the CLI application and commands.
"""

from __future__ import annotations

from typing import Annotated

import typer

from disdantic.logging import LoggingSettings, configure_logger, logger
from disdantic.settings import Settings
from disdantic.version import __version__

__all__ = ["main"]

app = typer.Typer(
    help="Disdantic: A lightweight collection of utilities and mixins for Pydantic.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            is_eager=True,
            help="Show the application version and exit.",
        ),
    ] = None,
) -> None:
    """
    Global setup for the CLI application.
    Initializes application settings and logging.
    """
    if version:
        typer.echo(f"disdantic v{__version__}")
        raise typer.Exit

    configure_logger(
        LoggingSettings(
            enabled=True,
            level="INFO",
            clear_loggers=True,
            filter=("disdantic", "__main__"),
        )
    )
    settings = Settings()

    if ctx.invoked_subcommand is None:
        logger.info("Hello from disdantic v{}!", __version__)
        logger.info("Settings: {}", settings)


def main() -> None:
    """
    Execute the main routine via Typer.
    """
    app()


if __name__ == "__main__":
    main()
