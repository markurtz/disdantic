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

"""Test suite for the Lazy Loading & Introspection example."""

from __future__ import annotations

import pytest

from disdantic.singleton import SingletonMeta
from examples.lazy_loading_and_introspection.main import main


@pytest.mark.regression
class TestLazyLoadingAndIntrospection:
    """Test suite verifying the Lazy Loading & Introspection example execution."""

    def test_example_runs(self) -> None:
        """Verify the example main entrypoint executes without exception."""
        SingletonMeta.clear_all_singletons()
        main()
