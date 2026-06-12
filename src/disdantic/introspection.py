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

from pydantic import BaseModel

from disdantic.compat import yaml
from disdantic.loading import LazyProxy
from disdantic.registry import RegistryMixin
from disdantic.settings import get_settings

__all__ = ["PRIMITIVE_TYPES", "InfoMixin"]

PRIMITIVE_TYPES: Annotated[
    tuple[type, ...],
    "Tuple of Python built-in types considered primitive "
    "for serialization representation. These types are directly "
    "returned during introspection without recursive traversal.",
] = (str, int, float, bool, type(None))


class InfoMixin:
    """Mixin providing runtime self-introspection to generate object structures.

    This mixin allows subclassing models to expose their public attributes,
    properties, slots, and instance dicts as sanitized primitives. It recursively
    inspects objects, resolves lazy loaders or proxies, and handles circular reference
    loops and property extraction errors without raising exceptions.
    """

    @classmethod
    def extract_from_obj(
        cls, obj: Any, visited: set[int] | None = None
    ) -> dict[str, Any]:
        """Parse complex objects into sanitized primitive dictionaries.

        This method recursively crawls the object to extract public fields,
        evaluates custom `.info` hooks if defined, and translates collections
        or nested objects into JSON/YAML compatible dictionaries.
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
                    raw_info = info_val() if callable(info_val) else info_val
                    return dict(cls._sanitize(raw_info, visited))
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
            "str": cls._sanitize_fallback(obj),
            "type": obj_class.__name__,
            "module": obj_class.__module__,
            "attributes": attributes,
        }

    def __repr__(self) -> str:
        """__repr__ delegating to MRO overrides or fallback."""
        return self._delegate_dunder("__repr__")

    def __str__(self) -> str:
        """__str__ delegating to MRO overrides or fallback."""
        return self._delegate_dunder("__str__")

    @property
    def info(self) -> dict[str, Any]:
        """Self-introspection dictionary representing the public state."""
        return self.extract_from_obj(self)

    def info_json(
        self,
        *,
        indent: int | None = None,
        sort_keys: bool = False,
        **kwargs: Any,
    ) -> str:
        """Serialize the introspection info dictionary into a valid JSON string."""
        prepared = self._sanitize(self.info, set())
        return json.dumps(prepared, indent=indent, sort_keys=sort_keys, **kwargs)

    def info_yaml(
        self,
        *,
        indent: int | None = None,
        sort_keys: bool = False,
        **kwargs: Any,
    ) -> str:
        """Serialize the introspection info dictionary into a valid YAML string."""
        if yaml is None:
            raise ImportError(
                "PyYAML is required for YAML serialization. "
                "Install disdantic with the 'yaml' extra: pip install disdantic[yaml]"
            )
        prepared = self._sanitize(self.info, set())
        return yaml.dump(prepared, indent=indent, sort_keys=sort_keys, **kwargs)

    def _delegate_dunder(self, name: str) -> str:
        # Delegate repr/str dunder method to MRO overrides or fallback.
        for cls_item in self.__class__.__mro__:
            if cls_item.__name__ in (
                "InfoMixin",
                "object",
                "BaseModel",
                "ReloadableBaseModel",
            ):
                continue
            if name in cls_item.__dict__:
                return str(getattr(cls_item, name)(self))
        return f"<{self.__class__.__name__} info={self.info}>"

    @classmethod
    def _is_class_variable(cls, obj: Any, key: str) -> bool:
        # Check if the key is defined on class, not instance dict/slots
        if isinstance(obj, type):
            return False

        if hasattr(obj, "__dict__") and key in obj.__dict__:
            return False

        # Slots check across MRO
        for mro_cls in type(obj).__mro__:
            slots = getattr(mro_cls, "__slots__", None)
            if slots and key in slots:
                return False

        # Check if the key is defined on any class in the MRO.
        for mro_cls in type(obj).__mro__:
            if key in mro_cls.__dict__:
                class_attr = mro_cls.__dict__[key]
                # If it has a __get__ method (e.g. property, method, descriptor),
                # it's evaluated on the instance and represents instance state.
                return not hasattr(class_attr, "__get__")

        return False

    @classmethod
    def _has_info_protocol(cls, val: Any) -> bool:
        # Check if an object implements the info protocol without evaluating it.
        try:
            return getattr(type(val), "info", None) is not None or (
                hasattr(val, "__dict__") and "info" in val.__dict__
            )
        except Exception:  # noqa: BLE001
            return False

    @classmethod
    def _extract_attributes(cls, obj: Any, visited: set[int]) -> dict[str, Any]:
        # Scrapes attributes from instance spaces, slots, and properties safely.
        attributes: dict[str, Any] = {}

        exclude_keys = set(get_settings().info_exclude_keys)
        is_pydantic = isinstance(obj, BaseModel)
        is_registry = isinstance(obj, RegistryMixin)

        for key in dir(obj):
            if key.startswith("_") or key in exclude_keys:
                continue

            if is_pydantic and key in (
                "model_fields",
                "model_computed_fields",
                "model_config",
                "model_fields_set",
                "model_extra",
            ):
                continue

            if is_registry and key in (
                "registry",
                "registry_auto_discovery",
                "registry_populated",
                "schema_discriminator",
            ):
                continue

            if cls._is_class_variable(obj, key):
                continue

            try:
                val = getattr(obj, key)
                if isinstance(val, collections.abc.Callable):
                    continue

                attributes[key] = cls._sanitize(val, visited)
            except Exception as err:  # noqa: BLE001
                attributes[key] = f"<Extraction Error: {err!r}>"

        return attributes

    @classmethod
    def _sanitize(cls, val: Any, visited: set[int]) -> Any:
        # Unified recursive sanitization and preparation for serialization.
        if isinstance(val, LazyProxy):
            val = val._resolve()  # noqa: SLF001

        val_id = id(val)
        if val_id in visited:
            res = f"<CircularReference: ID {val_id}>"
        elif isinstance(val, PRIMITIVE_TYPES):
            res = val
        elif isinstance(val, dict):
            visited.add(val_id)
            try:
                res = {
                    str(item_key): cls._sanitize(item_val, visited)
                    for item_key, item_val in val.items()
                }
            finally:
                visited.discard(val_id)
        elif isinstance(val, list | tuple | set):
            visited.add(val_id)
            try:
                res = [cls._sanitize(item, visited) for item in val]
            finally:
                visited.discard(val_id)
        elif isinstance(val, type):
            try:
                res = repr(val)
            except Exception:  # noqa: BLE001
                res = f"<{val.__name__} object at {hex(id(val))}>"
        elif cls._has_info_protocol(val):
            res = cls._sanitize_custom(val, val_id, visited)
        else:
            res = cls._sanitize_fallback(val)

        return res

    @classmethod
    def _sanitize_custom(cls, val: Any, val_id: int, visited: set[int]) -> Any:
        # Sanitize a custom object that implements the info protocol.
        try:
            info_class_attr = getattr(type(val), "info", None)
            visited.add(val_id)
            try:
                if _is_default_info(info_class_attr):
                    return cls.extract_from_obj(val, visited)
                info_val = val.info
                raw_info = info_val() if callable(info_val) else info_val
                return cls._sanitize(raw_info, visited)
            finally:
                visited.discard(val_id)
        except Exception:  # noqa: BLE001
            return cls._sanitize_fallback(val)

    @classmethod
    def _sanitize_fallback(cls, val: Any) -> str:
        # Get a safe string representation of val, avoiding infinite loops.
        val_class = getattr(val, "__class__", type(val))
        fallback = f"<{val_class.__name__} object at {hex(id(val))}>"
        try:
            mro = val_class.__mro__
            if not any(mro_cls.__name__ == "InfoMixin" for mro_cls in mro):
                return str(val)
            for cls_item in mro:
                if (
                    cls_item.__name__
                    not in (
                        "InfoMixin",
                        "object",
                        "BaseModel",
                        "ReloadableBaseModel",
                    )
                    and "__str__" in cls_item.__dict__
                ):
                    return str(val)
            return fallback
        except Exception:  # noqa: BLE001
            return fallback


def _is_default_info(attr: Any) -> bool:
    """Check if the class attribute is the default InfoMixin.info property."""
    if isinstance(attr, property) and attr.fget is not None:
        return getattr(attr.fget, "__qualname__", None) == "InfoMixin.info"
    return False
