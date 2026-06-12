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

"""End-to-end test suite for the Telemetry & Settings Example."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from examples.telemetry_and_settings.main import main


class TestExTelemetrySettings:
    """E2E test suite validating the Telemetry & Settings Example execution."""

    def _find_log(self, logs: list[dict], severity: str, fragment: str) -> dict | None:
        """Helper to locate a log record by severity and body fragment."""
        for log in logs:
            body = log.get("body", "")
            if log.get("severity_text") == severity and fragment in body:
                return log
        return None

    @pytest.mark.regression
    def test_example_execution_flow(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify the example runs successfully and outputs valid logs."""
        orig_cwd = Path.cwd()
        orig_env = dict(os.environ)

        try:
            # Execute the main example workflow
            main()
        finally:
            os.chdir(orig_cwd)
            os.environ.clear()
            os.environ.update(orig_env)

        # Capture standard output and error stream outputs
        captured = capsys.readouterr()
        stdout_lines = captured.out.strip().splitlines()
        stderr_lines = captured.err.strip().splitlines()

        # Assert correct stdout contents showing settings precedence
        assert "Loaded Discriminator from TOML: custom_type" in stdout_lines
        assert "Registry resolved discriminator key: custom_type" in stdout_lines
        assert "Successfully validated task type: EmailTask" in stdout_lines
        assert "Overridden Discriminator: constructor_discriminator" in stdout_lines

        # Assert correct structured OpenTelemetry JSON log output in standard error
        assert len(stderr_lines) > 0

        parsed_logs = []
        for line in stderr_lines:
            line_str = line.strip()
            if line_str and line_str.startswith("{") and line_str.endswith("}"):
                log = json.loads(line_str)
                # Verify basic structure of every JSON log
                assert "timestamp" in log
                assert "severity_text" in log
                assert "body" in log
                assert "resource" in log
                assert log["resource"]["service.name"] == "disdantic"
                assert "attributes" in log
                parsed_logs.append(log)

        # Retrieve specific logs
        info_start = self._find_log(parsed_logs, "INFO", "Starting calculation")
        debug_enter = self._find_log(parsed_logs, "DEBUG", "args=(10,)")
        debug_exit = self._find_log(parsed_logs, "DEBUG", "returned: 20")
        error_log = self._find_log(parsed_logs, "ERROR", "Value cannot be negative!")
        warning_catch = self._find_log(parsed_logs, "WARNING", "telemetry exception")

        assert info_start is not None, "Starting log not found"
        module_options = {"__main__", "examples.telemetry_and_settings.main"}
        assert info_start["attributes"]["module"] in module_options
        assert info_start["attributes"]["function"] == "main"

        assert debug_enter is not None, "Autolog enter log not found"
        assert debug_enter["attributes"]["module"] == "disdantic.logging"

        assert debug_exit is not None, "Autolog exit log not found"

        assert error_log is not None, "Exception log not found"
        assert error_log["attributes"]["exception.type"] == "ValueError"
        assert "exception.stacktrace" in error_log["attributes"]

        assert warning_catch is not None, "Caught exception log not found"
