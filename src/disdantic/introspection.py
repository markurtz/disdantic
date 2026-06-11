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

"""Runtime self-introspection and serialization utilities for arbitrary Python objects.

This module provides mechanisms to recursively traverse and extract public attributes,
properties, and values from Python object graphs into standard primitives. It is
specifically engineered to safely handle circular references, lazy proxies, and
unexpected property access errors during serialization.

The primary entry point is the :class:`InfoMixin` class, which exposes an object's
public structure as a primitive dictionary mapping via the :attr:`info` property,
with built-in support for exporting to JSON and YAML.
"""

from __future__ import annotations

import collections.abc
import json
from typing import Annotated, Any

from disdantic.loading import LazyLoader, LazyProxy
from disdantic.settings import get_settings

try:
    yaml = LazyLoader.load_module_proxy("yaml")
except (ImportError, ModuleNotFoundError):
    yaml = None

__all__ = ["PRIMITIVE_TYPES", "InfoMixin"]

PRIMITIVE_TYPES: Annotated[
    tuple[type, ...],
    "Tuple of Python built-in types considered primitive "
    "for serialization representation. These types are directly "
    "returned during introspection without recursive traversal.",
] = (str, int, float, bool, type(None))


def _is_default_info(attr: Any) -> bool:
    """Check if the class attribute is the default InfoMixin.info property."""
    if isinstance(attr, property) and attr.fget is not None:
        return getattr(attr.fget, "__qualname__", None) == "InfoMixin.info"
    return False


class InfoMixin:
    """Mixin providing runtime self-introspection to generate object structures.

    This mixin allows subclassing models to expose their public attributes,
    properties, slots, and instance dicts as sanitized primitives. It recursively
    inspects objects, resolves lazy loaders or proxies, and handles circular reference
    loops and property extraction errors without raising exceptions.

    Example:
        .. code-block:: python

            from disdantic.introspection import InfoMixin

            class User(InfoMixin):
                def __init__(self, name: str, email: str):
                    self.name = name
                    self.email = email
                    self._password_hash = "secret"

            user = User("Alice", "alice@example.com")
            print(user.info)
            # Output:
            # {
            #     "str": "<User object at ...>",
            #     "type": "User",
            #     "module": "__main__",
            #     "attributes": {"name": "Alice", "email": "alice@example.com"}
            # }
    """

    @classmethod
    def extract_from_obj(
        cls, obj: Any, visited: set[int] | None = None
    ) -> dict[str, Any]:
        """Parse complex objects into sanitized primitive dictionaries.

        This method recursively crawls the object to extract public fields,
        evaluates custom `.info` hooks if defined, and translates collections
        or nested objects into JSON/YAML compatible dictionaries.

        Example:
            .. code-block:: python

                from disdantic.introspection import InfoMixin

                data = InfoMixin.extract_from_obj([1, 2, 3])

        :param obj: The target object to inspect and extract public state from.
        :param visited: Optional set of object IDs to prevent circular cycles.
        :returns: A dictionary containing the object's metadata and attributes.
        """
        if visited is None:
            visited = set()

        if not isinstance(obj, type) and obj is not cls:
            try:
                info_class_attr = getattr(type(obj), "info", None)
                if not _is_default_info(info_class_attr) and (
                    info_class_attr is not None or hasattr(obj, "info")
                ):
                    info_val = obj.info
                    return dict(info_val() if callable(info_val) else info_val)
            except Exception:  # noqa: BLE001, S110
                pass

        obj_class = getattr(obj, "__class__", type(obj))
        obj_id = id(obj)

        visited.add(obj_id)
        try:
            attributes = cls._extract_attributes(obj, visited)
        finally:
            visited.discard(obj_id)

        return {
            "str": str(obj),
            "type": obj_class.__name__,
            "module": obj_class.__module__,
            "attributes": attributes,
        }

    @property
    def info(self) -> dict[str, Any]:
        """Self-introspection dictionary representing the public state of the instance.

        Example:
            .. code-block:: python

                info_dict = instance.info

        :return: A mapping of the calling instance's public state.
        """
        return self.extract_from_obj(self)

    def info_json(
        self,
        *,
        indent: int | None = None,
        sort_keys: bool = False,
        **kwargs: Any,
    ) -> str:
        """Serialize the introspection info dictionary into a valid JSON string.

        Example:
            .. code-block:: python

                json_data = instance.info_json(indent=2)

        :param indent: Prettify the output with the given indentation space count.
        :param sort_keys: Sort dictionary keys alphabetically before serialization.
        :param kwargs: Additional arguments to pass to the underlying JSON serializer.
        :returns: A JSON string representation of the instance's public state.
        """
        prepared = self._prepare_for_serialization(self.info)
        return json.dumps(prepared, indent=indent, sort_keys=sort_keys, **kwargs)

    def info_yaml(
        self,
        *,
        indent: int | None = None,
        sort_keys: bool = False,
        **kwargs: Any,
    ) -> str:
        """Serialize the introspection info dictionary into a valid YAML string.

        This method dynamically delegates to the PyYAML library if it is installed
        in the environment, falling back to a custom pure-Python YAML emitter.

        Example:
            .. code-block:: python

                yaml_data = instance.info_yaml(indent=2)

        :param indent: Prettify the output with the given indentation space count.
        :param sort_keys: Sort dictionary keys alphabetically before serialization.
        :param kwargs: Additional arguments to pass to the underlying YAML serializer.
        :returns: A YAML string representation of the instance's public state.
        """
        prepared = self._prepare_for_serialization(self.info)
        if yaml is not None:
            return yaml.dump(prepared, indent=indent, sort_keys=sort_keys, **kwargs)

        indent_spaces = 2 if indent is None else indent
        res = self._to_fallback_yaml(
            prepared, indent_level=0, indent_spaces=indent_spaces, sort_keys=sort_keys
        )
        if res and not res.endswith("\n"):
            res += "\n"
        return res

    @classmethod
    def _extract_attributes(cls, obj: Any, visited: set[int]) -> dict[str, Any]:
        # Scrapes attributes from instance spaces, slots, and properties safely.
        attributes: dict[str, Any] = {}

        exclude_keys = set(get_settings().info_exclude_keys)

        for key in dir(obj):
            if key.startswith("_") or key in exclude_keys:
                continue

            try:
                val = getattr(obj, key)
                if isinstance(val, collections.abc.Callable):
                    continue

                attributes[key] = cls._sanitize_value(val, visited)
            except Exception as err:  # noqa: BLE001
                attributes[key] = f"<Extraction Error: {err!r}>"

        return attributes

    @classmethod
    def _sanitize_value(cls, val: Any, visited: set[int] | None = None) -> Any:
        # Recursively processes arrays and values into primitives.
        # Prevents infinite loops by reference tracking.
        if visited is None:
            visited = set()

        if isinstance(val, LazyProxy):
            val = val._resolve()  # noqa: SLF001

        val_id = id(val)
        if val_id in visited:
            return f"<CircularReference: ID {val_id}>"

        if isinstance(val, PRIMITIVE_TYPES):
            return val

        if isinstance(val, list | tuple | set | dict):
            return cls._sanitize_collection(val, visited)

        if not isinstance(val, type):
            return cls._sanitize_custom(val, visited)

        return repr(val)

    @classmethod
    def _sanitize_collection(cls, val: Any, visited: set[int]) -> Any:
        val_id = id(val)
        visited.add(val_id)
        try:
            if isinstance(val, dict):
                return {
                    str(item_key): cls._sanitize_value(item_val, visited)
                    for item_key, item_val in val.items()
                }
            return [cls._sanitize_value(item, visited) for item in val]
        finally:
            visited.discard(val_id)

    @classmethod
    def _sanitize_custom(cls, val: Any, visited: set[int]) -> Any:
        info_class_attr = getattr(type(val), "info", None)
        if info_class_attr is None and not hasattr(val, "info"):
            return repr(val)

        val_id = id(val)
        visited.add(val_id)
        try:
            if _is_default_info(info_class_attr):
                extractor = getattr(type(val), "extract_from_obj", cls.extract_from_obj)
                return extractor(val, visited)
            info_val = val.info
            return info_val() if callable(info_val) else info_val
        except Exception:  # noqa: BLE001, S110
            return repr(val)
        finally:
            visited.discard(val_id)

    @classmethod
    def _prepare_for_serialization(
        cls, obj: Any, visited: set[int] | None = None
    ) -> Any:
        if visited is None:
            visited = set()

        is_container = isinstance(obj, dict | list | set | tuple)
        obj_id = id(obj)

        if is_container:
            if obj_id in visited:
                return f"<CircularReference: ID {obj_id}>"
            visited.add(obj_id)

        try:
            if isinstance(obj, str | int | float | bool | type(None)):
                return obj
            elif isinstance(obj, dict):
                return {
                    str(key): cls._prepare_for_serialization(val, visited)
                    for key, val in obj.items()
                }
            elif isinstance(obj, list | tuple | set):
                return [cls._prepare_for_serialization(item, visited) for item in obj]
            else:
                return str(obj)
        finally:
            if is_container:
                visited.discard(obj_id)

    @classmethod
    def _to_fallback_yaml(
        cls,
        obj: Any,
        indent_level: int = 0,
        indent_spaces: int = 2,
        sort_keys: bool = False,
    ) -> str:
        if isinstance(obj, dict):
            return cls._to_fallback_yaml_dict(
                obj, indent_level, indent_spaces, sort_keys
            )
        if isinstance(obj, list | tuple | set):
            return cls._to_fallback_yaml_seq(
                obj, indent_level, indent_spaces, sort_keys
            )

        if obj is None:
            return "null"
        if isinstance(obj, bool):
            return "true" if obj else "false"
        if isinstance(obj, str):
            return json.dumps(obj)
        return str(obj)

    @classmethod
    def _to_fallback_yaml_dict(
        cls,
        obj: dict[Any, Any],
        indent_level: int,
        indent_spaces: int,
        sort_keys: bool,
    ) -> str:
        if not obj:
            return "{}"
        spacing = " " * (indent_level * indent_spaces)
        lines = []
        keys = sorted(obj.keys()) if sort_keys else list(obj.keys())
        for key in keys:
            val = obj[key]
            string_key = str(key)
            formatted_key = (
                json.dumps(key)
                if (
                    not string_key
                    or any(char in string_key for char in ":{}[],&*#?|-<>=!%@` ")
                )
                else string_key
            )
            is_non_empty = (isinstance(val, dict) and len(val) > 0) or (
                isinstance(val, list | tuple | set) and len(val) > 0
            )
            if is_non_empty:
                val_str = cls._to_fallback_yaml(
                    val, indent_level + 1, indent_spaces, sort_keys
                )
                lines.append(f"{spacing}{formatted_key}:\n{val_str}")
            else:
                val_str = cls._to_fallback_yaml(val, 0, indent_spaces, sort_keys)
                lines.append(f"{spacing}{formatted_key}: {val_str}")
        return "\n".join(lines)

    @classmethod
    def _to_fallback_yaml_seq(
        cls,
        obj: list[Any] | tuple[Any, ...] | set[Any],
        indent_level: int,
        indent_spaces: int,
        sort_keys: bool,
    ) -> str:
        if not obj:
            return "[]"
        spacing = " " * (indent_level * indent_spaces)
        lines = []
        for item in obj:
            is_non_empty = (isinstance(item, dict) and len(item) > 0) or (
                isinstance(item, list | tuple | set) and len(item) > 0
            )
            if is_non_empty:
                item_str = cls._to_fallback_yaml(
                    item, indent_level + 1, indent_spaces, sort_keys
                )
                leading_spaces = (indent_level + 1) * indent_spaces
                if item_str.startswith(" " * leading_spaces):
                    item_str = item_str[leading_spaces:]
                lines.append(f"{spacing}- {item_str}")
            else:
                val_str = cls._to_fallback_yaml(item, 0, indent_spaces, sort_keys)
                lines.append(f"{spacing}- {val_str}")
        return "\n".join(lines)
