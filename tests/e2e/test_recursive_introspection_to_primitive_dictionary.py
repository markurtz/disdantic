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

"""End-to-end tests for US-5.1: Recursive Introspection to Primitive Dict."""

from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel, ValidationError

from disdantic.introspection import InfoMixin
from disdantic.settings import get_settings, reset_settings


class UserProfile(InfoMixin):
    """User profile for E2E testing."""

    def __init__(self, username: str, email: str, role: str = "user") -> None:
        self.username = username
        self.email = email
        self.role = role
        self._secret_hash = "f128bcde"

    @property
    def display_name(self) -> str:
        """Return a formatted display name containing the role."""
        return f"{self.username} ({self.role})"

    def do_action(self) -> None:
        """Simulate a public action method that should be excluded."""


class UserConfig(BaseModel, InfoMixin):
    """Pydantic model mixed with InfoMixin for E2E marshalling tests."""

    username: str
    email: str
    role: str = "user"

    @property
    def display_name(self) -> str:
        """Return a formatted display name containing the role."""
        return f"{self.username} ({self.role})"

    def do_action(self) -> None:
        """Simulate a public action method that should be excluded."""


class TestRecursiveIntrospectionToPrimitiveDictionary:
    """E2E test suite for US-5.1.

    Validates recursive introspection of objects to primitive dicts.
    """

    @pytest.fixture(params=["user_profile", "user_config"])
    def valid_instances(self, request: pytest.FixtureRequest) -> InfoMixin:
        """Supply isolated valid execution contexts/personas."""
        if request.param == "user_profile":
            return UserProfile("mjkurtz", "mark@kurtz.com", role="admin")
        return UserConfig(username="mjkurtz", email="mark@kurtz.com", role="admin")

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(InfoMixin, object)
        assert hasattr(InfoMixin, "info")
        assert hasattr(InfoMixin, "extract_from_obj")
        assert hasattr(InfoMixin, "info_json")
        assert hasattr(InfoMixin, "info_yaml")

        # Verify signature of extract_from_obj
        signature_obj = inspect.signature(InfoMixin.extract_from_obj)
        assert "obj" in signature_obj.parameters

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: InfoMixin) -> None:
        """Assert correct initial system wiring and persona mapping."""
        assert isinstance(valid_instances, InfoMixin)
        # Using getattr to avoid branch merging by linter
        assert valid_instances.username == "mjkurtz"  # type: ignore
        assert valid_instances.email == "mark@kurtz.com"  # type: ignore
        assert valid_instances.role == "admin"  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass bad environment parameters to verify system blockages."""
        with pytest.raises(ValidationError):
            UserConfig(username="mjkurtz", email=12345, role="admin")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit critical configurations to verify system boundary defense lines."""
        with pytest.raises(ValidationError):
            UserConfig(username="mjkurtz")  # type: ignore

    @pytest.mark.smoke
    def test_recursive_introspection(self, valid_instances: InfoMixin) -> None:
        """Verify recursive introspection to primitive dictionary."""
        info_dict = valid_instances.info
        assert info_dict["type"] in ("UserProfile", "UserConfig")
        assert info_dict["attributes"]["username"] == "mjkurtz"
        assert info_dict["attributes"]["email"] == "mark@kurtz.com"
        assert info_dict["attributes"]["display_name"] == "mjkurtz (admin)"

        # Exclude hidden properties and methods
        assert "_secret_hash" not in info_dict["attributes"]
        assert "do_action" not in info_dict["attributes"]

    @pytest.mark.regression
    def test_exclude_keys_configuration(self) -> None:
        """Verify custom attributes exclusion via settings."""
        settings = get_settings()
        original_excludes = list(settings.info_exclude_keys)
        settings.info_exclude_keys = original_excludes + ["role", "display_name"]

        try:
            profile = UserProfile("mjkurtz", "mark@kurtz.com", role="admin")
            info_dict = profile.info
            assert "username" in info_dict["attributes"]
            assert "role" not in info_dict["attributes"]
            assert "display_name" not in info_dict["attributes"]
        finally:
            reset_settings()

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: InfoMixin) -> None:
        """Verify marshalling of data models descending from Pydantic base class."""
        if isinstance(valid_instances, UserConfig):
            dumped_dict = valid_instances.model_dump()
            assert dumped_dict["username"] == "mjkurtz"
            assert dumped_dict["email"] == "mark@kurtz.com"

            validated_instance = UserConfig.model_validate(dumped_dict)
            assert isinstance(validated_instance, UserConfig)
            assert validated_instance.username == "mjkurtz"
