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

"""E2E/Regression test suite for the Lazy Loading & Introspection example."""

from __future__ import annotations

import pytest

from disdantic.singleton import SingletonMeta
from examples.lazy_loading_and_introspection.main import main


@pytest.mark.sanity
class TestExLazyIntrospection:
    """Test case class validating the Lazy Loading & Introspection example."""

    def test_example_execution_and_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify the example runs successfully and outputs correct signatures."""
        # Clear cached instances to ensure clean state
        SingletonMeta.clear_all_singletons()

        # Execute example main
        main()

        # Capture output
        captured = capsys.readouterr()
        stdout = captured.out

        # Verify stdout signatures
        assert (
            "Double-checked locking successful! Total manager instances created: 1"
            in stdout
        )
        assert (
            "Proxy successfully resolved connected status: "
            "[True, True, True, True, True]" in stdout
        )
        assert "Alice's Introspection Dict:" in stdout
        assert "<CircularReference: ID" in stdout
        assert '"type": "DeveloperNode"' in stdout
        assert '"name": "Alice"' in stdout
        assert '"name": "Bob"' in stdout
