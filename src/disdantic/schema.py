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

"""Dynamic schema generation and OpenAPI translation utilities.

This module provides programmatic tools to generate unified JSON Schema
representations for dynamic registries. It supports resolving all registered
models, force-rebuilding schemas to ensure correctness, and translating
references to conform with OpenAPI specifications.

Veteran maintainers can utilize this module's schemas for external dynamic
routing, while new contributors can use it to inspect the collective schema
of their registered classes.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from disdantic.registry import PydanticClassRegistryMixin

__all__ = ["SchemaFormat", "get_registry_schema"]

SchemaFormat = Annotated[
    Literal["json", "openapi"],
    (
        "Supported schema export formats, where 'json' represents a standard "
        "JSON schema and 'openapi' represents an OpenAPI-compatible schema."
    ),
]


def get_registry_schema(
    registry_class: type[PydanticClassRegistryMixin],
    *,
    format: SchemaFormat = "json",  # noqa: A002
) -> dict[str, Any]:
    """Generates the schema for the specified registry base class.

    Example:
        .. code-block:: python

            from disdantic.schema import get_registry_schema
            from myapp.registry import MyRegistry

            # Generate OpenAPI schema for the registry
            schema = get_registry_schema(MyRegistry, format="openapi")

    :param registry_class: The registry base class subclassing
        PydanticClassRegistryMixin.
    :param format: The output format, either 'json' or 'openapi'.
    :raises TypeError: If the registry_class is not a subclass of
        PydanticClassRegistryMixin.
    :returns: A dictionary representing the generated schema.
    """
    if not isinstance(registry_class, type) or not issubclass(
        registry_class, PydanticClassRegistryMixin
    ):
        got_type = (
            registry_class if isinstance(registry_class, type) else type(registry_class)
        )
        raise TypeError(
            "Expected a subclass of PydanticClassRegistryMixin, "
            f"got {got_type.__name__}"
        )

    # Rebuild class and registered models
    registry_class.model_rebuild(force=True)

    if format == "openapi":
        schema = registry_class.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        if "$defs" in schema:
            schema["components"] = {"schemas": schema.pop("$defs")}
    else:
        schema = registry_class.model_json_schema()

    return schema
