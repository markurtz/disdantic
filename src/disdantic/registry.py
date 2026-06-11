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
Provides isolated registry mixins for dynamic polymorphic schemas.

The module implements registry spaces using `RegistryMixin` and
`PydanticClassRegistryMixin` which prevent namespace conflicts between
distinct domain models. Subclass tracking is decoupled across registrations
to enforce safe, independent type lookup structures. The `RegistryManager`
class orchestrates global discovery, query operations, and class indexing.

Through integration with Pydantic's core validation layer, this architecture
enables automatic sub-package scanning and schema rebuilding. Registered models
are seamlessly resolved during JSON validation using a customizable discriminator
key, handling case-insensitive fallbacks and dynamic type dispatching safely.
"""

from __future__ import annotations

import contextlib
import threading
from abc import ABC
from collections.abc import Callable, Sequence
from typing import Any, ClassVar, Generic, TypeVar, cast

from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from disdantic.exceptions import DiscriminatorNotFoundError, RegistryCollisionError
from disdantic.importer import AutoImporterMixin
from disdantic.model import ReloadableBaseModel
from disdantic.settings import get_settings

__all__ = ["PydanticClassRegistryMixin", "RegistryManager", "RegistryMixin"]

RegistryObjT = TypeVar("RegistryObjT")
RegisterT = TypeVar("RegisterT")
BaseModelT = TypeVar("BaseModelT", bound=BaseModel)


class RegistryMixin(Generic[RegistryObjT], AutoImporterMixin):
    """
    Isolated registry namespace tracking across distinct base class domains.

    This mixin provides base class structures with automated tracking mappings,
    enabling subclasses to map dynamic components and discover submodules recursively.
    Each registry is fully isolated to avoid leakage between unrelated interfaces.
    It supports registration decorators, lookup checks, and programmatic unregistration.

    Example:
        .. code-block:: python

            from disdantic.registry import RegistryMixin

            class ComponentRegistry(RegistryMixin[type]):
                pass

            @ComponentRegistry.register("service")
            class MyService:
                pass

    :var registry: The canonical tracking directory mapping identifiers to
        registered objects.
    :var registry_auto_discovery: Controls whether sub-module scanning is
        automatically triggered on access.
    :var registry_populated: Tracks if the auto-population routine has
        completed for this namespace.
    """

    # 1. Public static / Class-level attributes and properties
    registry: ClassVar[dict[str, Any]]
    """The canonical tracking directory mapping identifiers to registered objects."""

    registry_auto_discovery: ClassVar[bool] = False
    """Controls whether sub-module scanning is automatically triggered on access."""

    registry_populated: ClassVar[bool] = False
    """Tracks if the auto-population routine has completed for this namespace."""

    _lower_registry: ClassVar[dict[str, Any]]
    _registry_lock: ClassVar[threading.RLock]

    # 2. Public static / Class methods
    @classmethod
    def is_auto_discovery_enabled(cls) -> bool:
        """
        Determine if automatic module discovery is active for this registry.

        Checks both the class-level configuration option and the fallback
        global settings to decide if submodules should be scanned.

        :returns: True if auto-discovery is enabled, False otherwise.
        """
        if getattr(cls, "registry_auto_discovery", False):
            return True
        return get_settings().registry_auto_discovery

    @classmethod
    def register(
        cls, name: str | Sequence[str] | None = None
    ) -> Callable[[RegisterT], RegisterT]:
        """
        Decorate subclass implementations to register them under name keys.

        Registers the decorated class or object under the specified name or
        list of names. If no name is provided, uses the class name.

        Example:
            .. code-block:: python

                @MyRegistry.register("custom_name")
                class SubComponent:
                    pass

        :param name: Optional registration keys. Can be a single string, a sequence
            of strings, or None to default to the target's name.
        :returns: A decorator function that registers the target object.
        """

        def _decorator(target_object: RegisterT) -> RegisterT:
            cls.register_decorator(target_object, name=name)
            return target_object

        return _decorator

    @classmethod
    def register_decorator(
        cls, target_object: RegisterT, name: str | Sequence[str] | None = None
    ) -> RegisterT:
        """
        Index target objects directly into namespace mappings.

        Performs collision checking to prevent duplicate registration within the
        same namespace.

        Example:
            .. code-block:: python

                MyRegistry.register_decorator(MyService, name="service")

        :param target_object: The class or object instance to register.
        :param name: Optional registration keys. Can be a single string, a sequence
            of strings, or None to default to the target's name.
        :raises ValueError: If the naming format is unsupported or if a key is not
            a string.
        :raises RegistryCollisionError: If a key is already registered.
        :returns: The original target object after successful registration.
        """
        cls._validate_registration_target(target_object)
        with cls._registry_lock:
            if name is None:
                resolved_names: list[str] = [
                    getattr(target_object, "__name__", str(target_object))
                ]
            elif isinstance(name, str):
                resolved_names = [name]
            elif isinstance(name, Sequence):
                resolved_names = list(name)
            else:
                raise ValueError(f"Unsupported naming format provided: {type(name)}")

            for resolved_name in resolved_names:
                if not isinstance(resolved_name, str):
                    raise ValueError(
                        f"Registry keys must explicitly be strings. "
                        f"Got: {type(resolved_name)}"
                    )

                if resolved_name in cls.registry:
                    raise RegistryCollisionError(
                        f"Collision detected: '{resolved_name}' already exists within "
                        f"{cls.__name__} registry."
                    )

                cls.registry[resolved_name] = target_object
                cls._lower_registry[resolved_name.lower()] = target_object

            cls._on_registry_change()
            return target_object

    @classmethod
    def auto_populate_registry(cls) -> bool:
        """
        Scan packages and automatically populate the registry namespace.

        Discovers and imports modules dynamically if auto-discovery is enabled and
        the registry has not been populated yet.

        Example:
            .. code-block:: python

                MyRegistry.auto_populate_registry()

        :raises ValueError: If auto-discovery is disabled on the registry class.
        :returns: True if the registry was newly populated, False if it was
            already populated.
        """
        with cls._registry_lock:
            if not cls.is_auto_discovery_enabled():
                raise ValueError(
                    f"Auto-population rejected: registry_auto_discovery is "
                    f"disabled on {cls.__name__}."
                )

            if cls.registry_populated:
                return False

            cls.auto_import_package_modules()
            cls.registry_populated = True
            cls._on_registry_change()
            return True

    @classmethod
    def registered_objects(cls) -> tuple[RegistryObjT, ...]:
        """
        Retrieve all registered objects in the registry tracking frame.

        Triggers auto-population if auto-discovery is enabled before returning
        the objects.

        Example:
            .. code-block:: python

                objects = MyRegistry.registered_objects()

        :returns: A tuple of all registered objects.
        """
        with cls._registry_lock:
            if cls.is_auto_discovery_enabled():
                cls.auto_populate_registry()
            return tuple(cls.registry.values())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Verify presence of an identifier in the registry.

        Performs case-insensitive checks against the registered keys.

        Example:
            .. code-block:: python

                exists = MyRegistry.is_registered("custom_name")

        :param name: The identifier key to verify.
        :returns: True if the identifier is registered, False otherwise.
        """
        with cls._registry_lock:
            return name in cls.registry or name.lower() in cls._lower_registry

    @classmethod
    def get_registered_object(cls, name: str) -> RegistryObjT | None:
        """
        Look up a registered object by its identifier.

        Looks up the given name directly in the canonical registry, falling back to a
        case-insensitive lookup in the lowercase registry.

        Example:
            .. code-block:: python

                obj = MyRegistry.get_registered_object("custom_name")

        :param name: The identifier key of the registered object.
        :returns: The registered object if found, or None.
        """
        with cls._registry_lock:
            return cls.registry.get(name) or cls._lower_registry.get(name.lower())

    @classmethod
    def clear_registry(cls) -> None:
        """
        Clear all active registrations and reset import states.

        Clears all mappings in canonical and lowercase registries, and resets flags
        so that subsequent operations can re-populate the registry.

        Example:
            .. code-block:: python

                MyRegistry.clear_registry()

        :returns: None.
        """
        with cls._registry_lock:
            cls.registry.clear()
            cls._lower_registry.clear()
            cls.registry_populated = False
            cls.reset_importer_cache()
            cls._on_registry_change()

    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Remove a registered identifier from both tracking mappings.

        Removes from canonical and case-insensitive mapping caches. If it is
        a PydanticClassRegistryMixin, triggers a core schema rebuild of the
        base registry class and its registered hierarchy.

        Example:
            .. code-block:: python

                MyRegistry.unregister("custom_name")

        :param name: The registered identifier/token to remove.
        :raises ValueError: If the token is not present in the registry.
        :returns: None.
        """
        with cls._registry_lock:
            keys_to_remove = [
                key for key in cls.registry if key.lower() == name.lower()
            ]
            if not keys_to_remove:
                raise ValueError(
                    f"Identifier '{name}' is not present in "
                    f"the {cls.__name__} registry."
                )
            for key in keys_to_remove:
                cls.registry.pop(key, None)
                cls._lower_registry.pop(key.lower(), None)
            cls._on_registry_change()

    # 3. Public instance constructors (__init__) and other dunder methods
    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Private hook. Documentation omitted to adhere to visibility constraints.
        super().__init_subclass__(**kwargs)
        cls.registry = {}
        cls._lower_registry = {}
        cls.registry_populated = False
        cls._registry_lock = threading.RLock()

    # 4. Public instance properties (None)

    # 5. Public instance methods (None)

    # 6. Private methods (prefixed with _):
    @classmethod
    def _validate_registration_target(cls, target_object: RegisterT) -> None:
        pass

    @classmethod
    def _on_registry_change(cls) -> None:
        pass


class PydanticClassRegistryMixin(
    ReloadableBaseModel, RegistryMixin[type[BaseModelT]], ABC, Generic[BaseModelT]
):
    """
    Polymorphic serialization wrapper using dynamic tagged unions.

    This class enables dynamic Pydantic model registration and builds tagged
    union schemas. It automatically routes JSON validation to the correct subclass
    using a discriminator key.

    Example:
        .. code-block:: python

            from disdantic.registry import PydanticClassRegistryMixin
            from pydantic import BaseModel

            class BaseMessage(PydanticClassRegistryMixin):
                pass

            @BaseMessage.register("text")
            class TextMessage(BaseMessage):
                content: str

    :var schema_discriminator: The serialized tag field name used to identify the
        target model type.
    """

    # 1. Public static / Class-level attributes and properties
    schema_discriminator: ClassVar[str] = "model_type"
    """The serialized tag field name used to identify the target model type."""

    # 2. Public static / Class methods
    @classmethod
    def get_schema_discriminator(cls) -> str:
        """
        Retrieve the active schema discriminator key.

        Resolves to the class-level 'schema_discriminator' or falls back to the
        global settings default.

        :returns: The string key name of the discriminator.
        """
        if "schema_discriminator" in cls.__dict__:
            return cls.schema_discriminator
        return get_settings().default_schema_discriminator

    @classmethod
    def registered_classes(cls) -> tuple[type[BaseModelT], ...]:
        """
        Return all registered BaseModel subclasses in this registry.

        Triggers auto-discovery on access if enabled.

        Example:
            .. code-block:: python

                classes = BaseMessage.registered_classes()

        :raises ValueError: If no classes are registered in the registry.
        :returns: A tuple of registered subclass types.
        """
        registered = cls.registered_objects()
        if not registered:
            raise ValueError(
                f"No objects are currently present within the {cls.__name__} "
                f"registry setup."
            )
        return registered

    # 3. Public instance constructors (__init__) and other dunder methods
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        # Builds Pydantic core schemas via dynamic tagged unions.
        # Private hook. Documentation omitted to adhere to visibility constraints.
        base_type = cls.__pydantic_schema_base_type__()
        if source_type == base_type:
            if not cls.registry:
                return cls.__pydantic_generate_base_schema__(handler)

            def check_discriminator_lookahead(value: Any) -> Any:
                # Intercepts validation inputs early to map casing schemas safely.
                # Addresses Bug A by mutating key casings to match requirements.
                discriminator_key = cls.get_schema_discriminator()
                if isinstance(value, dict):
                    discriminator_value = value.get(discriminator_key)
                    if discriminator_value is not None:
                        discriminator_str = str(discriminator_value)
                        lower_match = cls._lower_registry.get(discriminator_str.lower())
                        if not lower_match:
                            raise DiscriminatorNotFoundError(
                                discriminator_str, list(cls.registry.keys())
                            )

                        # Apply lookahead casing transformation to satisfy lookups
                        for canonical_name, model_class in cls.registry.items():
                            if model_class is lower_match:
                                value[discriminator_key] = canonical_name
                                break
                return value

            choices = {
                canonical_name: handler(model_class)
                for canonical_name, model_class in cls.registry.items()
            }
            union_schema = core_schema.tagged_union_schema(
                choices=choices,
                discriminator=cls.get_schema_discriminator(),
            )
            return core_schema.no_info_before_validator_function(
                check_discriminator_lookahead, union_schema
            )

        return handler(cls)

    @classmethod
    def __pydantic_schema_base_type__(cls) -> type[BaseModelT]:
        # Identifies the root base type context of the polymorphic schema loop.
        # Private hook. Documentation omitted to adhere to visibility constraints.
        for index, base_class in enumerate(cls.__mro__):
            is_registry = base_class.__name__ == "PydanticClassRegistryMixin"
            is_registry_generic = base_class.__name__.startswith(
                "PydanticClassRegistryMixin["
            )
            if (is_registry or is_registry_generic) and index > 0:
                return cast("type[BaseModelT]", cls.__mro__[index - 1])
        return cast("type[BaseModelT]", cls)

    @classmethod
    def __pydantic_generate_base_schema__(
        cls, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        # Generates base core schema when no subclasses are registered.
        # Private hook. Documentation omitted to adhere to visibility constraints.
        return core_schema.any_schema()

    # 4. Public instance properties (None)

    # 5. Public instance methods (None)

    # 6. Private methods (prefixed with _):
    @classmethod
    def _validate_registration_target(cls, target_object: RegisterT) -> None:
        if not isinstance(target_object, type) or not issubclass(
            target_object, BaseModel
        ):
            raise TypeError(
                f"Cannot register "
                f"'{getattr(target_object, '__name__', str(target_object))}': "
                f"must extend Pydantic BaseModel."
            )

    @classmethod
    def _on_registry_change(cls) -> None:
        cls._trigger_base_rebuild()

    @classmethod
    def _trigger_base_rebuild(cls) -> None:
        # Traverses and triggers schema reloading for the base class.
        # Private hook. Documentation omitted to adhere to visibility constraints.
        if not get_settings().enable_schema_rebuilding:
            return

        base_type = cls.__pydantic_schema_base_type__()
        if issubclass(base_type, ReloadableBaseModel):
            base_type.reload_schema()
        else:
            base_type.model_rebuild(force=True)


class RegistryManager:
    """
    Orchestrate tracking and listing active registry namespaces globally.

    This class scans the runtime subclass tree of RegistryMixin, discovers
    registered classes, and generates maps linking registries to their registered
    components.

    Example:
        .. code-block:: python

            from disdantic.registry import RegistryManager

            registries = RegistryManager.list_registries()
    """

    # 1. Public static / Class-level attributes and properties (None)

    # 2. Public static / Class methods
    @classmethod
    def list_registries(cls) -> dict[str, dict[str, str]]:
        """
        Generate a nested map of all active registries and their contents.

        Scans the runtime subclass tree of RegistryMixin, discovers registered
        classes, and generates maps linking registries to their registered
        components.

        Example:
            .. code-block:: python

                mapping = RegistryManager.list_registries()

        :returns: A dictionary mapping registry class names to a nested dict
            of registered keys and target class paths.
        """
        registries = cls._discover_registries()
        result: dict[str, dict[str, str]] = {}
        for registry_class in registries:
            result[registry_class.__name__] = {
                key: cls._resolve_val_path(registry_class.registry[key])
                for key in sorted(registry_class.registry.keys())
            }
        return result

    # 3. Public instance constructors (__init__) and other dunder methods (None)

    # 4. Public instance properties (None)

    # 5. Public instance methods (None)

    # 6. Private methods (prefixed with _):
    @classmethod
    def _discover_registries(cls) -> list[type[RegistryMixin[Any]]]:
        settings = get_settings()

        if settings.auto_packages:

            class GlobalImporter(AutoImporterMixin):
                pass

            GlobalImporter.auto_import_package_modules()

        all_subs = cls._get_subclasses(RegistryMixin)
        registries = []

        for sub_type in all_subs:
            if sub_type.__name__ in ("RegistryMixin", "PydanticClassRegistryMixin"):
                continue

            sub = cast("type[RegistryMixin[Any]]", sub_type)
            if sub.is_auto_discovery_enabled():
                with contextlib.suppress(Exception):
                    sub.auto_populate_registry()

            is_root = any(
                getattr(getattr(base_class, "__origin__", base_class), "__name__", "")
                in ("RegistryMixin", "PydanticClassRegistryMixin")
                for base_class in sub.__bases__
            )

            if is_root or bool(sub.registry):
                registries.append(sub)

        return sorted(
            registries,
            key=lambda registry_class: registry_class.__name__,
        )

    @staticmethod
    def _get_subclasses(target_class: type) -> set[type]:
        subs = set(target_class.__subclasses__())
        return subs.union(*(RegistryManager._get_subclasses(sub) for sub in subs))

    @staticmethod
    def _resolve_val_path(val: Any) -> str:
        mod = getattr(val, "__module__", None)
        name = getattr(val, "__name__", None)
        if mod and name:
            return f"{mod}.{name}"
        return f"{val.__class__.__module__}.{val.__class__.__name__}"
