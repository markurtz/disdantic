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
E2E validation tests for the Auto-Discovery and Diagnostics example.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Generator

import pytest

from disdantic.settings import reset_settings
from examples.auto_discovery_and_diagnostics.core_registry import PluginRegistry
from examples.auto_discovery_and_diagnostics.main import main


@pytest.mark.regression
class TestExAutoDiscovery:
    """End-to-end regression tests validating the auto-discovery example."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        PluginRegistry.clear_registry()
        yield
        PluginRegistry.clear_registry()
        reset_settings()

    def test_example_script_runs(self) -> None:
        """Verify that the example script executes without raising errors."""
        main()

    def test_cli_list_json(self) -> None:
        """Verify disdantic list --json runs and returns registry info."""
        env = os.environ.copy()
        env["PYTHONPATH"] = f".{os.pathsep}{env.get('PYTHONPATH', '')}"
        env["DISDANTIC__AUTO_PACKAGES"] = (
            '["examples.auto_discovery_and_diagnostics.plugins"]'
        )
        env["DISDANTIC__AUTO_IGNORE_MODULES"] = (
            '["examples.auto_discovery_and_diagnostics.plugins.broken_plugin"]'
        )

        result = subprocess.run(
            [sys.executable, "-m", "disdantic", "list", "--json"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"CLI output on failure: {result.stderr}"
        data = json.loads(result.stdout)
        assert "PluginRegistry" in data
        assert "healthy_plugin" in data["PluginRegistry"]

    def test_cli_diagnose_json(self) -> None:
        """Verify disdantic diagnose --json detects the broken plugin."""
        env = os.environ.copy()
        env["PYTHONPATH"] = f".{os.pathsep}{env.get('PYTHONPATH', '')}"
        env["DISDANTIC__AUTO_PACKAGES"] = (
            '["examples.auto_discovery_and_diagnostics.plugins"]'
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "disdantic",
                "diagnose",
                "--path",
                "examples/auto_discovery_and_diagnostics",
                "--json",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        # The command exit code is 1 since the registry is unhealthy
        assert result.returncode == 1, (
            f"CLI output on success (unexpected): {result.stdout}"
        )
        data = json.loads(result.stdout)
        assert data["is_healthy"] is False
        assert len(data["import_errors"]) > 0
        assert any("broken_plugin" in error_msg for error_msg in data["import_errors"])

    def test_cli_schema_export(self) -> None:
        """Verify disdantic schema command exports the OpenAPI registry schema."""
        env = os.environ.copy()
        env["PYTHONPATH"] = f".{os.pathsep}{env.get('PYTHONPATH', '')}"
        env["DISDANTIC__AUTO_PACKAGES"] = (
            '["examples.auto_discovery_and_diagnostics.plugins"]'
        )
        env["DISDANTIC__AUTO_IGNORE_MODULES"] = (
            '["examples.auto_discovery_and_diagnostics.plugins.broken_plugin"]'
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "disdantic",
                "schema",
                "examples.auto_discovery_and_diagnostics.core_registry.PluginRegistry",
                "--format",
                "openapi",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"CLI output on failure: {result.stderr}"
        data = json.loads(result.stdout)
        assert "components" in data
        assert "schemas" in data["components"]
