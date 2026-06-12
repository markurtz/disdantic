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

"""End-to-end regression test for the polymorphic messaging example.

This module validates that the example main script executes without errors
and successfully performs lookahead routing and schema rebuilding.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from examples.polymorphic_messaging.main import main
from examples.polymorphic_messaging.models import BaseMessage


class TestExPolymorphicMessaging:
    """Regression test suite for the polymorphic messaging example."""

    @pytest.fixture(autouse=True)
    def _cleanup_registry(self) -> Generator[None, None, None]:
        """Ensure the BaseMessage registry is clean before and after each test."""
        BaseMessage.clear_registry()
        yield
        BaseMessage.clear_registry()

    @pytest.mark.regression
    def test_example_runs(self) -> None:
        """Execute the main example script and assert no exceptions are raised."""
        main()
