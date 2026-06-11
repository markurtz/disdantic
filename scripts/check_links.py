"""
Platform-agnostic utility to scan and check URLs in markdown files.

This module provides a command-line interface powered by Typer and uses `urlchecker`
to scan files and directories, extracting and validating links for formatting and
availability. It integrates with environment variables to resolve target paths.
"""

from __future__ import annotations

import subprocess
from os import environ
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

__all__: Annotated[
    list[str],
    "The list of public symbols exported by this module.",
] = ["app", "collect_markdown_files", "main"]

app: Annotated[
    typer.Typer,
    "The Typer application instance used to define and execute the link-checking CLI.",
] = typer.Typer(add_completion=False)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def main(
    context: typer.Context,
    targets: Annotated[
        list[str] | None,
        typer.Argument(help="Files or directories to scan"),
    ] = None,
) -> None:
    """
    Scan targets and run urlchecker on markdown files.

    This command collects markdown files under the specified targets, environment
    variables, or default directories, and invokes ``urlchecker`` on each to validate
    all contained URLs.

    Example:
        .. code-block:: bash

            hatch run project:tests-e2e docs/ README.md

    :param context: The Typer context containing parsed arguments and extra CLI options.
    :param targets: An optional list of file or directory paths to check. If omitted,
                    targets are retrieved from the ``PROJECT_TARGETS`` or
                    ``MDFORMAT_TARGETS`` environment variables, falling back to a
                    default set of folders.
    :return: None
    :raises typer.Exit: If one or more link checks fail (exit code 1).
    """
    resolved_targets = targets
    if not resolved_targets:
        env_targets = environ.get("PROJECT_TARGETS") or environ.get("MDFORMAT_TARGETS")
        if env_targets:
            resolved_targets = [
                target for target in env_targets.split() if "*" not in target
            ]
        else:
            resolved_targets = [
                ".devcontainer",
                ".github",
                "crates",
                "docs",
                "examples",
                "scripts",
                "src",
                "tests",
            ]

    markdown_files = collect_markdown_files(resolved_targets)
    extra_options = context.args

    failed = False
    for md_file in markdown_files:
        logger.info(f"Checking links in: {md_file}")

        # Run urlchecker
        try:
            subprocess.run(
                [
                    "urlchecker",
                    "check",
                    str(md_file),
                    "--file-types",
                    ".md",
                    "--exclude-patterns",
                    "localhost,127.0.0.1,actions/workflows,github.com/markurtz/disdantic/tree",
                ]
                + extra_options,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            logger.error(f"Error checking {md_file}: {error}")
            failed = True

    if failed:
        raise typer.Exit(code=1)


def collect_markdown_files(targets: list[str]) -> list[Path]:
    """
    Collect all target markdown files from the specified targets.

    This function searches the root directory and the provided targets (files or
    directories) to assemble a sorted, unique list of markdown files for checking.

    Example:
        .. code-block:: python

            from pathlib import Path
            files = collect_markdown_files(["docs", "README.md"])

    :param targets: A list of paths (directories or files) to scan for markdown files.
    :return: A sorted list of Paths to markdown files.
    """
    markdown_files: list[Path] = []

    # Check root level md files
    for path in Path().glob("*.md"):
        markdown_files.append(path)

    # Check targeted subdirectories
    for target in targets:
        target_path = Path(target)
        if target_path.exists():
            if target_path.is_file() and target_path.suffix == ".md":
                markdown_files.append(target_path)
            elif target_path.is_dir():
                markdown_files.extend(target_path.rglob("*.md"))

    # Sort files to ensure deterministic execution
    markdown_files.sort()
    return markdown_files


if __name__ == "__main__":
    app()
