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

from __future__ import annotations

import json
from typing import ClassVar, Literal

import pytest
from pydantic import ValidationError

import disdantic.introspection
from disdantic.introspection import InfoMixin
from disdantic.model import ReloadableBaseModel
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import get_settings


class UserE2EModel(ReloadableBaseModel, InfoMixin):
    """User model for E2E introspection testing."""

    name: str
    best_friend: UserE2EModel | None = None


class AddressE2EModel(ReloadableBaseModel, InfoMixin):
    """Address model for E2E introspection testing."""

    city: str
    zip_code: str


class ComplexUserE2EModel(ReloadableBaseModel, InfoMixin):
    """Complex user model with nested model."""

    username: str
    address: AddressE2EModel


UserE2EModel.model_rebuild()
AddressE2EModel.model_rebuild()
ComplexUserE2EModel.model_rebuild()


@pytest.mark.smoke
class TestRuntimeIntrospectionAndPrimitiveSerialization:
    """E2E Test Suite for US-08 runtime self-introspection & serialization."""

    @pytest.fixture(params=["simple", "nested", "circular"])
    def valid_instances(self, request: pytest.FixtureRequest) -> InfoMixin:
        """Fixture supplying variations of valid InfoMixin instances."""
        param_value = request.param
        if param_value == "simple":
            return UserE2EModel(name="simple_user")
        elif param_value == "nested":
            address = AddressE2EModel(city="San Francisco", zip_code="94103")
            return ComplexUserE2EModel(username="nested_user", address=address)
        elif param_value == "circular":
            user_inst = UserE2EModel(name="circular_user")
            user_inst.best_friend = user_inst
            return user_inst
        raise ValueError(f"Unknown parameter: {param_value}")

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural module and environment contracts."""
        assert issubclass(UserE2EModel, InfoMixin)
        assert hasattr(InfoMixin, "extract_from_obj")
        assert hasattr(InfoMixin, "info")
        assert hasattr(InfoMixin, "info_json")
        assert hasattr(InfoMixin, "info_yaml")
        assert "info" in get_settings().info_exclude_keys

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: InfoMixin) -> None:
        """Assert correct initialization of valid instances."""
        assert isinstance(valid_instances, InfoMixin)
        if isinstance(valid_instances, UserE2EModel):
            assert valid_instances.name in ("simple_user", "circular_user")
        elif isinstance(valid_instances, ComplexUserE2EModel):
            assert valid_instances.username == "nested_user"
            assert isinstance(valid_instances.address, AddressE2EModel)

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Test validation failures with bad parameters."""
        with pytest.raises(ValidationError):
            # Pass incorrect type (int instead of str)
            UserE2EModel(name=123)  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Test validation failures when required parameters are missing."""
        with pytest.raises(ValidationError):
            # Omit required parameter 'name'
            UserE2EModel()  # type: ignore

    @pytest.mark.smoke
    def test_introspection_circular_reference(self) -> None:
        """Scenario: Introspection property scraping and circular reference handling.

        Given an instance 'user' of a class extending InfoMixin,
        and 'user' has a recursive circular reference linking back to itself,
        when I access 'user.info',
        then it must return a dictionary containing 'str', 'type',
        'module', and 'attributes',
        and the circular reference value in 'attributes' must be resolved
        as string '<CircularReference: ID <id>>',
        and no recursion crash must occur.
        """
        user_inst = UserE2EModel(name="circular_user")
        user_inst.best_friend = user_inst

        # Access info, expecting no recursion crash (RecursionError)
        info_dict = user_inst.info

        # Assert structure
        assert isinstance(info_dict, dict)
        assert "str" in info_dict
        assert "type" in info_dict
        assert "module" in info_dict
        assert "attributes" in info_dict

        # Assert type name
        assert info_dict["type"] == "UserE2EModel"

        # Assert circular reference resolution
        attributes = info_dict["attributes"]
        assert attributes["name"] == "circular_user"
        best_friend_val = attributes["best_friend"]

        expected_ref_prefix = f"<CircularReference: ID {id(user_inst)}>"
        assert best_friend_val == expected_ref_prefix

    @pytest.mark.sanity
    def test_serialization_formats_and_yaml_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Scenario: Introspection serialization formats and PyYAML dependency checking.

        Given an object extending InfoMixin,
        when I call 'instance.info_json(indent=2)',
        then it must return a valid JSON string representing the object's info dict,
        and when I call 'instance.info_yaml()',
        and PyYAML ('yaml') is not installed in the system environment,
        then the call must raise an ImportError.
        """
        user_inst = UserE2EModel(name="yaml_user")

        # Test JSON serialization
        json_str = user_inst.info_json(indent=2)
        assert isinstance(json_str, str)
        parsed_json = json.loads(json_str)
        assert parsed_json["type"] == "UserE2EModel"
        assert parsed_json["attributes"]["name"] == "yaml_user"

        # Test missing YAML module raises ImportError
        monkeypatch.setattr(disdantic.introspection, "yaml", None)

        with pytest.raises(ImportError) as exc_info:
            user_inst.info_yaml(indent=2, sort_keys=True)
        assert "PyYAML is required for YAML serialization" in str(exc_info.value)

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: InfoMixin) -> None:
        """Verify model_dump and model_validate boundaries."""
        if isinstance(valid_instances, ReloadableBaseModel) and not isinstance(
            valid_instances.info.get("attributes", {}).get("best_friend"), str
        ):
            # Verify marshalling on non-circular models
            dumped_dict = valid_instances.model_dump()
            assert isinstance(dumped_dict, dict)

            validated_inst = valid_instances.__class__.model_validate(dumped_dict)
            assert isinstance(validated_inst, valid_instances.__class__)

    @pytest.mark.regression
    def test_dynamic_flow_registry(self) -> None:
        """Verify dynamic registration/factory loading integration with InfoMixin."""

        class RegistryBaseModel(PydanticClassRegistryMixin, InfoMixin):
            schema_discriminator: ClassVar[str] = "kind"

        @RegistryBaseModel.register("child_kind")
        class RegistryChildModel(RegistryBaseModel):
            kind: Literal["child_kind"] = "child_kind"
            payload: str

        RegistryBaseModel.model_rebuild()
        RegistryChildModel.model_rebuild()

        try:
            # Factory validate the subclass
            instance = RegistryBaseModel.model_validate(
                {"kind": "child_kind", "payload": "hello"}
            )
            assert isinstance(instance, RegistryChildModel)

            # Verify introspection
            info_data = instance.info
            assert info_data["type"] == "RegistryChildModel"
            assert info_data["attributes"]["payload"] == "hello"
            assert info_data["attributes"]["kind"] == "child_kind"
        finally:
            RegistryBaseModel.clear_registry()
