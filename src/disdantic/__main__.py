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

import importlib
import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

import disdantic.settings
from disdantic.diagnose import DiagnosticsReport, verify_registries
from disdantic.logging import LoggingSettings, configure_logger, logger
from disdantic.registry import (
    PydanticClassRegistryMixin,
    RegistryManager,
    RegistryMixin,
)
from disdantic.schema import get_registry_schema
from disdantic.settings import Settings, reset_settings
from disdantic.version import __version__

__all__ = ["main"]

app = typer.Typer(
    help="Disdantic: A lightweight collection of utilities and mixins for Pydantic.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def main() -> None:
    """
    Execute the main routine via Typer.
    """
    app()


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


@app.command()
def diagnose(
    path: Annotated[
        str | None,
        typer.Option(
            "--path",
            "-p",
            help="Project root directory (defaults to current working directory).",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output result as a raw JSON string for scripts.",
        ),
    ] = False,
) -> None:
    """Scans all configured auto-discovery packages, identifies all subclass registries,

    and verifies their integrity and compilation health.
    """
    if path:
        reset_settings()
        disdantic.settings._global_settings = Settings(  # noqa: SLF001
            project_root=Path(path)
        )

    report = verify_registries()

    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        if not report.is_healthy:
            raise typer.Exit(code=1)
        return

    console = Console()

    if report.is_healthy:
        console.print(
            "[bold green]✔ Registries diagnosis completed successfully.[/bold green]\n"
        )
    else:
        console.print("[bold red]✗ Registries diagnosis failed.[/bold red]\n")

    if report.import_errors:
        console.print("[bold red]Import Errors:[/bold red]")
        for err in report.import_errors:
            console.print(f"  [red]- {err}[/red]")
        console.print()

    _render_diagnose_table(report, console)
    _render_diagnose_tree(report, console)

    if not report.is_healthy:
        raise typer.Exit(code=1)


@app.command()
def schema(
    registry_path: Annotated[
        str,
        typer.Argument(
            ...,
            help=(
                "The dot-path to the registry class "
                "(e.g. my_package.models.BaseMessage)."
            ),
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Save schema directly to the specified file (defaults to stdout).",
        ),
    ] = None,
    schema_format: Annotated[
        Literal["json", "openapi"],
        typer.Option(
            "--format",
            "-f",
            help="Schema target format.",
        ),
    ] = "json",
    indent: Annotated[
        int,
        typer.Option(
            "--indent",
            help="Pretty-print indentation level.",
        ),
    ] = 2,
) -> None:
    """Generates the schema for the specified registry base class."""
    # Ensure current working directory is in sys.path
    cwd_str = str(Path.cwd())
    if cwd_str not in sys.path:
        sys.path.insert(0, cwd_str)

    if "." not in registry_path:
        typer.echo(
            f"Error: Invalid path '{registry_path}'. "
            "Must be a fully qualified dot-path to a class.",
            err=True,
        )
        raise typer.Exit(code=1)

    module_path, class_name = registry_path.rsplit(".", 1)

    try:
        module = importlib.import_module(module_path)
    except Exception as err:  # noqa: BLE001
        typer.echo(
            f"Error: Could not import module '{module_path}': {err}",
            err=True,
        )
        raise typer.Exit(code=1) from err

    try:
        cls = getattr(module, class_name)
    except AttributeError as err:
        typer.echo(
            f"Error: Module '{module_path}' has no attribute '{class_name}'.",
            err=True,
        )
        raise typer.Exit(code=1) from err

    if not isinstance(cls, type) or not issubclass(cls, PydanticClassRegistryMixin):
        typer.echo(
            f"Error: '{registry_path}' is not a subclass of "
            "PydanticClassRegistryMixin.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        schema_dict = get_registry_schema(cls, format=schema_format)
        schema_json = json.dumps(schema_dict, indent=indent)
    except Exception as err:  # noqa: BLE001
        typer.echo(
            f"Error generating schema: {err}",
            err=True,
        )
        raise typer.Exit(code=1) from err

    if output:
        try:
            output.write_text(schema_json, encoding="utf-8")
        except Exception as err:  # noqa: BLE001
            typer.echo(
                f"Error writing schema to '{output}': {err}",
                err=True,
            )
            raise typer.Exit(code=1) from err
    else:
        typer.echo(schema_json)


@app.command("list")
def list_cmd(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output as raw JSON representation.",
        ),
    ] = False,
) -> None:
    """List active registries and their registered classes."""
    try:
        registries = RegistryManager.list_registries()
    except Exception as err:
        typer.echo(f"Error querying registries: {err}", err=True)
        raise typer.Exit(code=1) from err

    if json_output:
        typer.echo(json.dumps(registries, indent=2))
        return

    def _get_subclasses(registry_class: type) -> set[type]:
        subs = set()
        for sub in registry_class.__subclasses__():
            subs.add(sub)
            subs.update(_get_subclasses(sub))
        return subs

    all_subs = _get_subclasses(RegistryMixin)
    reg_classes = {sub.__name__: sub for sub in all_subs}

    for reg_name, mappings in registries.items():
        reg_class = reg_classes.get(reg_name)
        if reg_class is not None and issubclass(reg_class, PydanticClassRegistryMixin):
            discriminator = reg_class.get_schema_discriminator()
            header = f"{reg_name} (discriminator: {discriminator})"
        else:
            header = reg_name

        typer.echo(f"└── {header}")

        items = list(mappings.items())
        for index, (key, path) in enumerate(items):
            is_last = index == len(items) - 1
            prefix = "    └── " if is_last else "    ├── "
            typer.echo(f'{prefix}"{key}" -> {path}')


def _render_diagnose_table(report: DiagnosticsReport, console: Console) -> None:
    """Renders the summary table for the diagnostics report."""
    table = Table(
        title="Subclass Registries Summary",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Registry Name", style="cyan")
    table.add_column("Discriminator Key", style="green")
    table.add_column("Auto-Discovery", style="yellow")
    table.add_column("Registered Models", style="blue", justify="right")
    table.add_column("Status", justify="center")

    for registry in report.registries:
        has_error = any(
            model.compilation_status == "error" for model in registry.models
        )
        status = (
            "[bold red]✗ Error[/bold red]"
            if has_error
            else "[bold green]✔ Healthy[/bold green]"
        )

        table.add_row(
            registry.registry_name,
            registry.discriminator_key,
            "Enabled" if registry.auto_discovery_enabled else "Disabled",
            str(len(registry.models)),
            status,
        )

    console.print(table)
    console.print()


def _render_diagnose_tree(report: DiagnosticsReport, console: Console) -> None:
    """Renders the detailed tree view for the diagnostics report."""
    tree = Tree("[bold blue]Registries Detail[/bold blue]")
    for registry in report.registries:
        disc_info = (
            f" (discriminator: {registry.discriminator_key})"
            if registry.discriminator_key
            else ""
        )
        reg_node = tree.add(
            f"[bold cyan]{registry.registry_name}[/bold cyan]{disc_info}"
        )

        if registry.models:
            models_node = reg_node.add("[bold]Registered Models[/bold]")
            for model in registry.models:
                path_str = f"{model.module_path}.{model.class_name}"
                if model.compilation_status == "healthy":
                    models_node.add(
                        f"[green]✔[/green] [bold]{model.key}[/bold] -> "
                        f"{path_str} [[green]healthy[/green]]"
                    )
                else:
                    err_node = models_node.add(
                        f"[red]✗[/red] [bold]{model.key}[/bold] -> "
                        f"{path_str} [[red]error[/red]]"
                    )
                    if model.error_detail:
                        err_node.add(
                            f"[bold red]Detail:[/bold red] {model.error_detail}"
                        )
        else:
            reg_node.add("[dim]No models registered[/dim]")

        if registry.orphans:
            orphans_node = reg_node.add(
                "[bold yellow]Orphans (Unregistered Subclasses)[/bold yellow]"
            )
            for orphan in registry.orphans:
                orphans_node.add(f"[yellow]{orphan}[/yellow]")

    console.print(tree)
    console.print()


if __name__ == "__main__":
    main()
