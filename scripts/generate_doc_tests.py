"""
Extract and generate test files from markdown documents.

This module uses ``phmdoctest`` to parse code blocks in markdown files and convert
them into executable pytest files. It helps automate code snippet verification in docs.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from os import environ
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

__all__ = ["main"]

# Output directory for the generated test files.
_OUT_DIR = Path(".tests/docs")

app: Annotated[
    typer.Typer,
    "Typer CLI application instance for document test generation.",
] = typer.Typer(
    help=(
        "Platform-agnostic script to extract and generate test files from "
        "markdown documents using phmdoctest."
    ),
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)


# Resolve targets from arguments, environment variables, or defaults.
def _resolve_targets(targets_and_options: list[str]) -> list[str]:
    targets = [arg for arg in targets_and_options if not arg.startswith("-")]
    if targets:
        return targets

    env_targets = environ.get("PROJECT_TARGETS") or environ.get("PYTHON_TARGETS")
    if env_targets:
        return [target for target in env_targets.split() if "*" not in target]

    return [
        ".devcontainer",
        ".github",
        "crates",
        "docs",
        "examples",
        "scripts",
        "src",
        "tests",
    ]


# Find all markdown files under targets, excluding reference and test directories.
def _find_markdown_files(targets: list[str]) -> list[Path]:
    markdown_files = list(Path().glob("*.md"))

    for target in targets:
        target_path = Path(target)
        if not target_path.exists():
            continue
        if target_path.is_file() and target_path.suffix == ".md":
            markdown_files.append(target_path)
        elif target_path.is_dir():
            markdown_files.extend(target_path.rglob("*.md"))

    return sorted(
        path
        for path in markdown_files
        if ".tests" not in path.parts
        and not ("docs" in path.parts and "reference" in path.parts)
    )


@app.callback(invoke_without_command=True)
def run_generate_doc_tests(
    targets_and_options: Annotated[
        list[str] | None,
        typer.Argument(
            help="Target paths and/or extra phmdoctest arguments.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """
    Extract and generate test files from markdown documents.

    Examples:
        >>> from typer.testing import CliRunner
        >>> runner = CliRunner()
        >>> result = runner.invoke(app, ["docs/"])

    :param targets_and_options: Target paths or extra phmdoctest arguments.
    :return: None.
    """
    # Clean up and recreate .tests/docs directory
    if _OUT_DIR.exists():
        shutil.rmtree(_OUT_DIR)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets_and_options = targets_and_options or []
    targets = _resolve_targets(targets_and_options)
    markdown_files = _find_markdown_files(targets)
    extra_options = [arg for arg in targets_and_options if arg.startswith("-")]

    failed = False
    for markdown_file in markdown_files:
        # Generate safe filename for python file: replace slashes and dots
        # e.g., docs/getting-started/quickstart.md ->
        # test_docs__getting-started__quickstart_md.py
        safe_name = str(markdown_file).replace("/", "__").replace(".", "__")
        out_file = _OUT_DIR / f"test_{safe_name}.py"

        logger.info("Generating tests from {} -> {}", markdown_file, out_file)
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "phmdoctest",
                    str(markdown_file),
                    "--outfile",
                    str(out_file),
                ]
                + extra_options,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            logger.error("Error generating tests for {}: {}", markdown_file, error)
            failed = True

    if failed:
        sys.exit(1)


def main() -> None:
    """
    Execute the CLI application.

    Examples:
        >>> main()

    :return: None.
    """
    app()


if __name__ == "__main__":
    main()
