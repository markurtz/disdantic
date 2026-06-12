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
Core registry definition for the Auto-Discovery and Diagnostics example.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from typing import Any, ClassVar

from disdantic.registry import PydanticClassRegistryMixin

__all__ = ["PluginRegistry"]


class PluginRegistry(PydanticClassRegistryMixin):
    """Base registry supporting automatic import of plugin modules."""

    schema_discriminator = "plugin_type"
    plugin_type: str
    registry_auto_discovery: ClassVar[bool] = True

    @classmethod
    def register_decorator(
        cls, target_object: Any, name: str | Sequence[str] | None = None
    ) -> Any:
        """
        Index target objects into namespace mappings with transactional rollback.
        """
        try:
            return super().register_decorator(target_object, name=name)
        except Exception as error:
            # Rollback registration if rebuilding/compilation fails
            if name is None:
                resolved_names: list[str] = [
                    getattr(target_object, "__name__", str(target_object))
                ]
            elif isinstance(name, str):
                resolved_names = [name]
            else:
                resolved_names = list(name)

            for resolved_name in resolved_names:
                cls.registry.pop(resolved_name, None)
                cls._lower_registry.pop(resolved_name.lower(), None)
            raise error

    @classmethod
    def model_rebuild(
        cls,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: dict[str, Any] | None = None,
    ) -> bool | None:
        """
        Trigger auto-discovery and registry population before rebuilding model schema.
        """
        if cls.is_auto_discovery_enabled():
            with contextlib.suppress(Exception):
                cls.auto_populate_registry()
        return super().model_rebuild(
            force=force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )
