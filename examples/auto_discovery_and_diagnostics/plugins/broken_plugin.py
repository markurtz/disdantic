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
A plugin implementation designed to fail compilation/validation.
"""

from __future__ import annotations

from typing import Literal

from examples.auto_discovery_and_diagnostics.core_registry import PluginRegistry

__all__ = ["BrokenPlugin"]


@PluginRegistry.register("broken_plugin")
class BrokenPlugin(PluginRegistry):
    """A broken plugin model with an unresolvable type reference."""

    plugin_type: Literal["broken_plugin"] = "broken_plugin"
    # Will fail validation because it has an unresolvable type reference
    invalid_field: UnresolvableType  # type: ignore[name-defined] # noqa: F821
