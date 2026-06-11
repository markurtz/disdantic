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

"""Provides model integration layers for dynamic validation schema rebuilding.

This module defines the foundational schema-rebuild behavior used by polymorphic
model registries to cascade validation changes. When schemas are updated
dynamically (such as registering new subtypes at runtime), dependent models
must rebuild their core validation structures so that they correctly parse the
newly introduced models.

The main interface is the `ReloadableBaseModel` class, which extends Pydantic's
`BaseModel` to add automatic dependency tracking and top-down traversal for
rebuilding schemas. By tracking subclasses and model field annotations, it
ensures that runtime polymorphic expansions propagate correctly throughout the
entire application's schema registry.
"""

from __future__ import annotations

from typing import Any, get_args, get_origin

from pydantic import BaseModel

from disdantic.settings import get_settings

__all__ = ["ReloadableBaseModel"]


class ReloadableBaseModel(BaseModel):
    """Pydantic base model that dynamically cascades validation schema updates.

    This class enables reloading of parent and dependent schemas when child or
    dependent schemas are dynamically updated at runtime. By subclassing
    `ReloadableBaseModel`, any modification to a child model can automatically
    trigger updates to parent models that reference the child model in their
    fields.

    It functions by traversing Python's subclass tree and evaluating field
    annotations recursively, identifying models that reference a modified
    target. The class respects configuration flags from the global registry
    settings to selectively enable or disable rebuild propagation.

    .. code-block:: python

        from pydantic import Field
        from disdantic.model import ReloadableBaseModel

        class ChildModel(ReloadableBaseModel):
            value: str

        class ParentModel(ReloadableBaseModel):
            child: ChildModel

        # Rebuilding ChildModel will automatically cascade to ParentModel
        ChildModel.reload_schema()
    """

    @classmethod
    def reload_schema(cls, parents: bool = True) -> None:
        """Forces a compilation rebuild of the local core schema.

        .. code-block:: python

            ReloadableBaseModel.reload_schema(parents=True)

        :param parents: Specifies whether schema updates should propagate to
            dependent parent models.
        :returns: None.
        """
        settings = get_settings()

        if not settings.enable_schema_rebuilding:
            return

        cls.model_rebuild(force=True)
        if parents and settings.schema_rebuild_parents:
            cls.reload_parent_schemas()

    @classmethod
    def reload_parent_schemas(cls) -> None:
        """Traverses subclasses and rebuilds all dependent parent schemas.

        .. code-block:: python

            ReloadableBaseModel.reload_parent_schemas()

        :returns: None.
        """
        potential_parents: set[type[BaseModel]] = set()
        stack: list[type[BaseModel]] = [BaseModel]

        while stack:
            current = stack.pop()
            for subclass in current.__subclasses__():
                if subclass is not cls and subclass not in potential_parents:
                    potential_parents.add(subclass)
                    stack.append(subclass)

        for check in cls.__mro__:
            if (
                isinstance(check, type)
                and issubclass(check, BaseModel)
                and check is not BaseModel
                and check is not ReloadableBaseModel
            ):
                cls._reload_schemas_depending_on(check, potential_parents)

    @classmethod
    def _reload_schemas_depending_on(
        cls,
        target: type[BaseModel],
        types: set[type[BaseModel]],
    ) -> None:
        changed = True
        while changed:
            changed = False
            for candidate in types:
                if any(
                    cls._uses_type(target, field.annotation)
                    for field in candidate.model_fields.values()
                    if field.annotation
                ):
                    try:
                        before = candidate.model_json_schema()
                    except Exception:  # noqa: BLE001
                        # Gracefully handle models with currently un-rebuildable schemas
                        before = None

                    candidate.model_rebuild(force=True)

                    if before is not None:
                        try:
                            changed |= before != candidate.model_json_schema()
                        except Exception:  # noqa: BLE001
                            # Fallback if comparing new schema throws an exception
                            changed = True

    @classmethod
    def _uses_type(cls, target: type, candidate: Any) -> bool:
        # Evaluates variable annotation definitions recursively.
        #
        # Addresses Bug B by verifying both strict type classes and postponed string
        # literals.
        if target is candidate:
            return True
        if isinstance(candidate, str):
            return candidate == target.__name__ or candidate.endswith(
                f".{target.__name__}"
            )
        origin = get_origin(candidate)
        if origin is None:
            return isinstance(candidate, type) and issubclass(candidate, target)
        if isinstance(origin, type) and issubclass(origin, target):
            return True
        return any(cls._uses_type(target, arg) for arg in get_args(candidate))
