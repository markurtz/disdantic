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

"""End-to-end tests for the disdantic CLI."""

from __future__ import annotations

import shutil
import subprocess

from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.version import __version__


def test_cli_runner_help() -> None:
    """Test invoking help subcommand via Typer CliRunner."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Disdantic" in result.stdout
    assert "Show the application version" in result.stdout


def test_cli_runner_version() -> None:
    """Test invoking version subcommand via Typer CliRunner."""
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"disdantic v{__version__}" in result.stdout


def test_cli_path_execution() -> None:
    """Verify that the disdantic binary is installed and executable on the path."""
    disdantic_path = shutil.which("disdantic")
    assert disdantic_path is not None, "disdantic executable not found in PATH"

    result = subprocess.run(
        [disdantic_path, "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    assert f"disdantic v{__version__}" in result.stdout.strip()
