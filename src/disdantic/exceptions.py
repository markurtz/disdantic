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

"""Custom structural error classifications for disdantic polymorphism.

This module defines the core exception hierarchy used to represent anomalies
during registry lookup, automatic discovery, and class mapping operations. By
classifying structural errors distinctly, the package guarantees that developers
can handle setup configuration errors separate from normal runtime validation issues.

The primary interfaces include DisdanticError, the base class of this system,
and specific exceptions for unresolved registry keys and registry key collisions.
"""

from __future__ import annotations

__all__ = [
    "DiscriminatorNotFoundError",
    "DisdanticError",
    "RegistryCollisionError",
]


class DisdanticError(Exception):
    """Base exception for all anomalies encountered within disdantic.

    This exception serves as the root class for all error states raised by the
    registry system. Catching this base class allows handlers to intercept all
    polymorphic resolving issues or configuration mismatches.

    Example:
        .. code-block:: python

            from disdantic.exceptions import DisdanticError

            try:
                # Intercept any registry configuration anomaly
                pass
            except DisdanticError as error:
                # Handle package-specific issue
                print(f"Disdantic error caught: {error}")
    """


class DiscriminatorNotFoundError(DisdanticError, ValueError):
    """Raised when a discriminator token cannot be found in the registry.

    This exception occurs during deserialization or runtime registry lookups when
    a discriminator key or token is provided that does not match any registered
    model. It allows the calling code to inspect the incorrect key and access the
    valid choices for graceful recovery or detailed reporting.

    Example:
        .. code-block:: python

            from disdantic.exceptions import DiscriminatorNotFoundError

            try:
                # Attempt to resolve an unregistered type token
                raise DiscriminatorNotFoundError("unknown", ["a", "b"])
            except DiscriminatorNotFoundError as error:
                print(f"Rejected: {error.rejected_value}")
                print(f"Valid choices: {error.valid_options}")
    """

    rejected_value: str
    valid_options: list[str]

    def __init__(self, rejected_value: str, valid_options: list[str]) -> None:
        """Initialize the exception with the rejected value and list of valid options.

        :param rejected_value: The key or token that was not found in the registry.
        :param valid_options: The list of all registered discriminator tokens.
        :returns: None
        """
        self.rejected_value = rejected_value
        self.valid_options = valid_options
        message = (
            f"Failed to resolve polymorphic configuration layer: "
            f"'{rejected_value}' is not a recognized mapping target. "
            f"Supported valid choices are: {valid_options}."
        )
        super().__init__(message)


class RegistryCollisionError(DisdanticError, KeyError):
    """Raised when an entry mapping path collides with a registered ID.

    This exception is raised during model registration when a developer attempts
    to register multiple models under the same discriminator token, or when a name
    clash occurs in the registry.

    Example:
        .. code-block:: python

            from disdantic.exceptions import RegistryCollisionError

            try:
                # Registering a model under an already registered token
                raise RegistryCollisionError("Duplicate mapping token 'type_a'.")
            except RegistryCollisionError as error:
                print(f"Collision: {error}")
    """
