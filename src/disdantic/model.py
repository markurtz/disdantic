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

import sys
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

    This class does not define any fields or class variables itself; it is
    intended solely as an abstract base class for reloadable models.

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

        This method triggers Pydantic's underlying model rebuilding process for
        the target model, forcing a compilation of its core schema. If parent
        cascading is requested and enabled globally, it also traverses the
        dependency tree to rebuild all models referencing this target model.

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

        This method scans all active subclasses of `BaseModel` in the runtime
        registry, identifies which of those models reference the current model
        class (or any of its parent classes in its MRO), and triggers a
        topological rebuild of those dependents.

        .. code-block:: python

            ReloadableBaseModel.reload_parent_schemas()

        :returns: None.
        """
        potential_parents: set[type[BaseModel]] = set()
        stack: list[type[BaseModel]] = [BaseModel]

        while stack:
            current = stack.pop()
            for subclass in current.__subclasses__():
                if (
                    subclass is not cls
                    and subclass not in potential_parents
                    and hasattr(subclass, "__module__")
                    and isinstance(subclass.__module__, str)
                    and subclass.__module__ in sys.modules
                ):
                    potential_parents.add(subclass)
                    stack.append(subclass)

        for check in cls.__mro__:
            if (
                isinstance(check, type)
                and issubclass(check, BaseModel)
                and check is not BaseModel
                and check is not ReloadableBaseModel
            ):
                cls._rebuild_dependents(check, potential_parents)

    @classmethod
    def _rebuild_dependents(
        cls,
        target: type[BaseModel],
        types: set[type[BaseModel]],
    ) -> None:
        # Gather all checkable model classes and build the reference adjacency list.
        all_types = types | {target}
        dependents = cls._build_dependency_map(all_types)

        # Find transitively reachable dependents of the target (excluding target).
        reachable = cls._find_reachable(target, dependents)
        subgraph_nodes = reachable - {target}
        if not subgraph_nodes:
            return

        # Sort parent models topologically (dependencies before dependents).
        ordered = cls._topological_sort(subgraph_nodes, dependents)

        for parent_cls in ordered:
            parent_cls.model_rebuild(force=True)

    @classmethod
    def _build_dependency_map(
        cls, types: set[type[BaseModel]]
    ) -> dict[type[BaseModel], set[type[BaseModel]]]:
        dependents: dict[type[BaseModel], set[type[BaseModel]]] = {
            model_cls: set() for model_cls in types
        }

        # Map each model to the set of models that directly depend on it.
        for candidate in types:
            for possible_dep in types:
                if possible_dep is not candidate and any(
                    cls._references_type(possible_dep, field.annotation)
                    for field in candidate.model_fields.values()
                    if field.annotation
                ):
                    dependents[possible_dep].add(candidate)
        return dependents

    @classmethod
    def _find_reachable(
        cls,
        target: type[BaseModel],
        dependents: dict[type[BaseModel], set[type[BaseModel]]],
    ) -> set[type[BaseModel]]:
        # DFS traversal to find all transitively reachable dependent models.
        reachable: set[type[BaseModel]] = set()
        stack: list[type[BaseModel]] = [target]
        while stack:
            curr = stack.pop()
            if curr not in reachable:
                reachable.add(curr)
                stack.extend(dependents.get(curr, ()))
        return reachable

    @classmethod
    def _topological_sort(
        cls,
        subgraph_nodes: set[type[BaseModel]],
        dependents: dict[type[BaseModel], set[type[BaseModel]]],
    ) -> list[type[BaseModel]]:
        # Kahn's algorithm: sort dependents to rebuild parent schemas in order.
        in_degree: dict[type[BaseModel], int] = dict.fromkeys(subgraph_nodes, 0)
        subgraph_dependents: dict[type[BaseModel], set[type[BaseModel]]] = {
            node: set() for node in subgraph_nodes
        }

        for node_u in subgraph_nodes:
            for node_v in dependents.get(node_u, ()):
                if node_v in subgraph_nodes:
                    subgraph_dependents[node_u].add(node_v)
                    in_degree[node_v] += 1

        queue: list[type[BaseModel]] = [
            node for node, deg in in_degree.items() if deg == 0
        ]
        ordered: list[type[BaseModel]] = []

        while queue:
            # Sort lexicographically by name to ensure a stable, deterministic order.
            queue.sort(key=lambda model: model.__name__)
            curr = queue.pop(0)
            ordered.append(curr)

            for neighbor in subgraph_dependents[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Fallback for cyclic/recursive schemas: append remaining nodes alphabetically.
        if len(ordered) < len(subgraph_nodes):
            remaining = sorted(
                subgraph_nodes - set(ordered),
                key=lambda model: model.__name__,
            )
            ordered.extend(remaining)

        return ordered

    @classmethod
    def _references_type(cls, target: type, candidate: Any) -> bool:
        # Recursively check types, postponed annotations, and generic arguments.
        if target is candidate:
            return True

        # Match postponed string annotations (e.g., "ChildModel").
        if isinstance(candidate, str):
            return candidate == target.__name__ or candidate.endswith(
                f".{target.__name__}"
            )

        origin = get_origin(candidate)
        if origin is None:
            return isinstance(candidate, type) and issubclass(candidate, target)

        if isinstance(origin, type) and issubclass(origin, target):
            return True

        return any(cls._references_type(target, arg) for arg in get_args(candidate))
