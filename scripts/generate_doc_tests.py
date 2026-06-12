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
        and not (len(path.parts) == 1 and path.name != "README.md")
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

    # Write conftest.py to dynamically configure the mock package structure
    conftest_content = """# Copyright 2026 markurtz
# Auto-generated conftest for doc tests setup
import sys
import tempfile
import shutil
from pathlib import Path
import pytest

_TEMP_DIR = None
_ADDED_PATH = None

@pytest.fixture(autouse=True)
def clear_all_registries():
    # Reset settings to default before and after each test
    from disdantic.settings import reset_settings
    reset_settings()
    yield
    reset_settings()
    # Clear all active registries to prevent cross-test collisions
    from disdantic.registry import RegistryMixin
    def get_all_subclasses(cls):
        subs = set(cls.__subclasses__())
        return subs.union(*(get_all_subclasses(s) for s in subs))
    for sub in get_all_subclasses(RegistryMixin):
        if hasattr(sub, "clear_registry"):
            sub.clear_registry()

def pytest_sessionstart(session):
    global _TEMP_DIR, _ADDED_PATH
    _TEMP_DIR = tempfile.mkdtemp()
    myapp_dir = Path(_TEMP_DIR) / "myapp"
    models_dir = myapp_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    (myapp_dir / "__init__.py").write_text("# myapp init")
    (models_dir / "__init__.py").write_text('''# myapp.models init
from disdantic import PydanticClassRegistryMixin, InfoMixin

class BaseMessage(PydanticClassRegistryMixin, InfoMixin):
    schema_discriminator = "msg_type"
''')
    (models_dir / "experimental.py").write_text("# experimental models")
    (models_dir / "details.py").write_text('''# details models
from myapp.models import BaseMessage

@BaseMessage.register("text")
class TextMessage(BaseMessage):
    content: str
''')
    (models_dir / "temp.py").write_text("# temp models")

    sys.path.insert(0, _TEMP_DIR)
    _ADDED_PATH = _TEMP_DIR

def pytest_sessionfinish(session, exitstatus):
    global _TEMP_DIR, _ADDED_PATH
    if _ADDED_PATH and _ADDED_PATH in sys.path:
        sys.path.remove(_ADDED_PATH)
    for key in list(sys.modules.keys()):
        if key == "myapp" or key.startswith("myapp."):
            sys.modules.pop(key, None)
    if _TEMP_DIR:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
"""
    (_OUT_DIR / "conftest.py").write_text(conftest_content, encoding="utf-8")

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
            if out_file.exists():
                code = out_file.read_text(encoding="utf-8")
                new_code = f"from __future__ import annotations\n{code}"
                out_file.write_text(new_code, encoding="utf-8")
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
