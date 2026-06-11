"""Manage dynamic Python API reference pages in the docs directory.

This module automates the discovery of source code files and generates corresponding
Markdown files containing mkdocstrings directives. This setup ensures that the
project's Python API reference documentation is dynamically built, cleanly organized,
and synchronized with source changes.

Example:
    To programmatically trigger a reference page build:

    .. code-block:: python

        from pathlib import Path
        from gen_ref_pages import generate

        generate(src_dir=Path("src"), ref_dir=Path("docs/reference/python_api"))
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

__all__ = [
    "REF_DIR",
    "SRC_DIR",
    "app",
    "clean",
    "generate",
]

SRC_DIR: Annotated[
    Path,
    "The default root directory containing the project source code to scan.",
] = Path("src")
REF_DIR: Annotated[
    Path,
    "The default target directory where markdown reference files will be written.",
] = Path("docs/reference/python_api")

app: Annotated[
    typer.Typer,
    "The Typer application instance orchestrating command-line entry points "
    "for reference documentation management.",
] = typer.Typer(help="Manage dynamic Python API reference pages.")


@app.command()
def clean(
    ref_dir: Annotated[
        Path,
        typer.Option(
            "--ref-dir",
            help="Reference directory to clean.",
        ),
    ] = REF_DIR,
) -> None:
    """Purge the generated reference directory to prevent stale pages.

    This utility removes all dynamically generated reference files to ensure
    that modules deleted or renamed in the source directory do not leave
    stale reference documentation behind in the build output.

    Example:
        .. code-block:: python

            from pathlib import Path
            from gen_ref_pages import clean

            clean(ref_dir=Path("docs/reference/python_api"))

    :param ref_dir: The target reference directory path to delete.
    """
    if ref_dir.exists():
        shutil.rmtree(ref_dir)


@app.command()
def generate(
    src_dir: Annotated[
        Path,
        typer.Option(
            "--src-dir",
            help="Source directory containing Python code.",
        ),
    ] = SRC_DIR,
    ref_dir: Annotated[
        Path,
        typer.Option(
            "--ref-dir",
            help="Reference directory where documentation is generated.",
        ),
    ] = REF_DIR,
) -> None:
    """Generate Python API reference pages dynamically in the docs directory.

    This function scans the source directory for Python modules and creates a
    corresponding reference Markdown file containing the appropriate
    mkdocstrings directive. It automatically excludes `__main__` entry points
    and handles package `__init__` files to build a clean documentation hierarchy.

    Example:
        .. code-block:: python

            from pathlib import Path
            from gen_ref_pages import generate

            generate(src_dir=Path("src"), ref_dir=Path("docs/reference/python_api"))

    :param src_dir: The root directory containing Python source modules.
    :param ref_dir: The destination directory to write Markdown reference pages.
    """
    clean(ref_dir=ref_dir)
    ref_dir.mkdir(parents=True, exist_ok=True)

    for source_path in sorted(src_dir.rglob("*.py")):
        module_path = source_path.relative_to(src_dir).with_suffix("")
        module_parts = list(module_path.parts)

        # Exclude __main__ command line entry points or non-public modules
        if module_parts[-1] == "__main__":
            continue

        is_index = False
        if module_parts[-1] == "__init__":
            module_parts.pop()
            is_index = True

        if not module_parts:
            continue

        import_str = ".".join(module_parts)

        # Strip the root package name to keep the navigation clean
        doc_parts = module_parts[1:]

        if is_index:
            doc_path = ref_dir.joinpath(*doc_parts, "index.md")
        else:
            doc_path = ref_dir.joinpath(*doc_parts).with_suffix(".md")

        # Ensure parent directories exist
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate the file with mkdocstrings directive
        with doc_path.open("w", encoding="utf-8") as doc_file:
            doc_file.write(f"# {import_str}\n\n")
            doc_file.write(f"::: {import_str}\n")


if __name__ == "__main__":
    app()
