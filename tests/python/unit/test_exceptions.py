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

"""Unit tests for the exceptions module."""

from __future__ import annotations

import inspect

import pytest

from disdantic import exceptions
from disdantic.exceptions import (
    AutoPopulationError,
    DiscriminatorNotFoundError,
    DisdanticError,
    EmptyRegistryError,
    MissingPackagesError,
    RegistryCollisionError,
)


class TestDisdanticError:
    """Suite to test the DisdanticError exception."""

    @pytest.fixture(
        params=[
            (),
            ("generic error message",),
            ("another error message", "with details"),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> DisdanticError:
        """Provide instantiated valid variations of the class across test methods."""
        return DisdanticError(*request.param)

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validate structural contracts, inheritance lineages, and public exposures."""
        assert issubclass(DisdanticError, Exception)
        assert "DisdanticError" in exceptions.__all__

        # Validate class constructor signature (inherits from Exception)
        assert DisdanticError.__init__ is Exception.__init__

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: DisdanticError) -> None:
        """Verify initialization and correct state mapping."""
        assert isinstance(valid_instances, DisdanticError)
        assert isinstance(valid_instances.args, tuple)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        # Exception allows any type in its args
        error_instance = DisdanticError(12345, None)
        assert error_instance.args == (12345, None)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        # DisdanticError has no required arguments, so 0 args should be valid
        error_instance = DisdanticError()
        assert len(error_instance.args) == 0


class TestDiscriminatorNotFoundError:
    """Suite to test the DiscriminatorNotFoundError exception."""

    @pytest.fixture(
        params=[
            ("unknown", ["option_a", "option_b"]),
            ("", []),
            ("missing_key", ["value_one", "value_two", "value_three"]),
        ]
    )
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> DiscriminatorNotFoundError:
        """Provide instantiated valid variations of the class across test methods."""
        rejected, options = request.param
        return DiscriminatorNotFoundError(rejected, options)

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validate structural contracts, inheritance lineages, and public exposures."""
        assert issubclass(DiscriminatorNotFoundError, DisdanticError)
        assert issubclass(DiscriminatorNotFoundError, ValueError)
        assert "DiscriminatorNotFoundError" in exceptions.__all__

        # Verify exact method signature of __init__
        init_method = DiscriminatorNotFoundError.__init__
        signature = inspect.signature(init_method)
        parameters = list(signature.parameters.keys())

        # 'self' is the first argument, followed by rejected_value and valid_options
        assert parameters == ["self", "rejected_value", "valid_options"]

        # Verify type annotations
        assert signature.parameters["rejected_value"].annotation == "str"
        assert signature.parameters["valid_options"].annotation == "list[str]"

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: DiscriminatorNotFoundError) -> None:
        """Verify initialization and correct state mapping."""
        # Verify custom attributes are stored correctly
        assert isinstance(valid_instances.rejected_value, str)
        assert isinstance(valid_instances.valid_options, list)

        # Verify message f-string content
        message = str(valid_instances)
        assert valid_instances.rejected_value in message
        assert str(valid_instances.valid_options) in message
        assert "Failed to resolve polymorphic configuration layer" in message

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        # Pass non-string and non-list inputs to verify formatting handling
        bad_value = 12345
        bad_options = {"not": "a_list"}

        error_instance = DiscriminatorNotFoundError(
            bad_value,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
            bad_options,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        assert error_instance.rejected_value == bad_value
        assert error_instance.valid_options == bad_options

        message = str(error_instance)
        assert str(bad_value) in message
        assert str(bad_options) in message

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        # Omitting required parameters should raise TypeError
        with pytest.raises(TypeError):
            DiscriminatorNotFoundError()  # type: ignore[call-arg]  # ty: ignore[missing-argument]

        with pytest.raises(TypeError):
            DiscriminatorNotFoundError("rejected_only")  # type: ignore[call-arg]  # ty: ignore[missing-argument]


class TestRegistryCollisionError:
    """Suite to test the RegistryCollisionError exception."""

    @pytest.fixture(
        params=[
            ("collision on key 'service_a'",),
            ("registry collision detected",),
            ("",),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> RegistryCollisionError:
        """Provide instantiated valid variations of the class across test methods."""
        return RegistryCollisionError(*request.param)

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validate structural contracts, inheritance lineages, and public exposures."""
        assert issubclass(RegistryCollisionError, DisdanticError)
        assert issubclass(RegistryCollisionError, KeyError)
        assert "RegistryCollisionError" in exceptions.__all__

        # Validate class constructor signature (inherits from KeyError)
        assert RegistryCollisionError.__init__ is KeyError.__init__

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: RegistryCollisionError) -> None:
        """Verify initialization and correct state mapping."""
        assert isinstance(valid_instances, RegistryCollisionError)
        assert isinstance(valid_instances.args, tuple)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        # KeyError allows any type in its args
        error_instance = RegistryCollisionError(98765, None)
        assert error_instance.args == (98765, None)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        # KeyError allows empty initialization
        error_instance = RegistryCollisionError()
        assert len(error_instance.args) == 0


class TestAutoPopulationError:
    """Suite to test the AutoPopulationError exception."""

    @pytest.fixture(
        params=[
            (),
            ("Auto-population rejected: discovery is disabled.",),
            ("another message", "with details"),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> AutoPopulationError:
        """Provide instantiated valid variations of the class across test methods."""
        return AutoPopulationError(*request.param)

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validate structural contracts, inheritance lineages, and public exposures."""
        assert issubclass(AutoPopulationError, DisdanticError)
        assert issubclass(AutoPopulationError, ValueError)
        assert "AutoPopulationError" in exceptions.__all__

        # Validate class constructor signature (inherits from ValueError)
        assert AutoPopulationError.__init__ is ValueError.__init__

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: AutoPopulationError) -> None:
        """Verify initialization and correct state mapping."""
        assert isinstance(valid_instances, AutoPopulationError)
        assert isinstance(valid_instances.args, tuple)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        # ValueError allows any type in its args
        error_instance = AutoPopulationError(11111, None)
        assert error_instance.args == (11111, None)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        # AutoPopulationError has no required arguments, so 0 args should be valid
        error_instance = AutoPopulationError()
        assert len(error_instance.args) == 0


class TestEmptyRegistryError:
    """Suite to test the EmptyRegistryError exception."""

    @pytest.fixture(
        params=[
            (),
            ("No classes present in the registry setup.",),
            ("another empty msg", "with details"),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> EmptyRegistryError:
        """Provide instantiated valid variations of the class across test methods."""
        return EmptyRegistryError(*request.param)

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validate structural contracts, inheritance lineages, and public exposures."""
        assert issubclass(EmptyRegistryError, DisdanticError)
        assert issubclass(EmptyRegistryError, ValueError)
        assert "EmptyRegistryError" in exceptions.__all__

        # Validate class constructor signature (inherits from ValueError)
        assert EmptyRegistryError.__init__ is ValueError.__init__

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: EmptyRegistryError) -> None:
        """Verify initialization and correct state mapping."""
        assert isinstance(valid_instances, EmptyRegistryError)
        assert isinstance(valid_instances.args, tuple)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        # ValueError allows any type in its args
        error_instance = EmptyRegistryError(22222, None)
        assert error_instance.args == (22222, None)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        # EmptyRegistryError has no required arguments, so 0 args should be valid
        error_instance = EmptyRegistryError()
        assert len(error_instance.args) == 0


class TestMissingPackagesError:
    """Suite to test the MissingPackagesError exception."""

    @pytest.fixture(
        params=[
            (),
            ("No packages configured for auto discovery.",),
            ("missing packages details", "with details"),
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> MissingPackagesError:
        """Provide instantiated valid variations of the class across test methods."""
        return MissingPackagesError(*request.param)

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validate structural contracts, inheritance lineages, and public exposures."""
        assert issubclass(MissingPackagesError, DisdanticError)
        assert issubclass(MissingPackagesError, ValueError)
        assert "MissingPackagesError" in exceptions.__all__

        # Validate class constructor signature (inherits from ValueError)
        assert MissingPackagesError.__init__ is ValueError.__init__

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: MissingPackagesError) -> None:
        """Verify initialization and correct state mapping."""
        assert isinstance(valid_instances, MissingPackagesError)
        assert isinstance(valid_instances.args, tuple)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass malformed payloads to verify explicit error handling."""
        # ValueError allows any type in its args
        error_instance = MissingPackagesError(33333, None)
        assert error_instance.args == (33333, None)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit required arguments to verify validation boundaries."""
        # MissingPackagesError has no required arguments, so 0 args should be valid
        error_instance = MissingPackagesError()
        assert len(error_instance.args) == 0
