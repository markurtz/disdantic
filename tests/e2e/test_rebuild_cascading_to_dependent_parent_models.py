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

"""End-to-end tests for US-3.1: Rebuild Cascading to Dependent Parent Models."""

from __future__ import annotations

from collections.abc import Generator
from typing import Literal

import pytest
from pydantic import ValidationError

from disdantic.model import ReloadableBaseModel
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import get_settings, reset_settings


class BasePet(PydanticClassRegistryMixin):
    """Base polymorphic registry class for pets."""

    schema_discriminator = "pet_type"
    pet_type: str


class Shelter(ReloadableBaseModel):
    """Parent model referencing BasePet via list annotation."""

    name: str
    pets: list[BasePet]


class OptionalShelter(ReloadableBaseModel):
    """Parent model referencing BasePet via optional annotation."""

    name: str
    pet: BasePet | None


class UnionShelter(ReloadableBaseModel):
    """Parent model referencing BasePet via union annotation."""

    name: str
    pet: BasePet | str


class Dog(BasePet):
    """Subclass representing a dog."""

    pet_type: Literal["dog"] = "dog"
    bark_volume: int


class Cat(BasePet):
    """Subclass representing a cat."""

    pet_type: Literal["cat"] = "cat"
    meow_frequency: float


class TestRebuildCascadingToDependentParentModels:
    """End-to-end validation suite for rebuild cascading to dependent parents."""

    @pytest.fixture(autouse=True)
    def clean_test_environment(self) -> Generator[None, None, None]:
        """Ensure a pristine environment state before and after each test."""
        reset_settings()
        BasePet.clear_registry()
        yield
        reset_settings()
        BasePet.clear_registry()

    @pytest.fixture(
        params=[
            {"name": "Happy Paws", "pets": [{"pet_type": "dog", "bark_volume": 10}]},
            {"name": "Cozy Cats", "pets": [{"pet_type": "cat", "meow_frequency": 2.5}]},
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> Shelter:
        """Fixture providing configured, valid instances of parent models."""
        BasePet.clear_registry()
        BasePet.register_decorator(Dog, name="dog")
        BasePet.register_decorator(Cat, name="cat")
        return Shelter.model_validate(request.param)

    @pytest.mark.smoke
    def test_contract(self) -> None:
        """Validate structural environment contracts and class structures."""
        assert issubclass(BasePet, PydanticClassRegistryMixin)
        assert issubclass(Shelter, ReloadableBaseModel)
        assert issubclass(OptionalShelter, ReloadableBaseModel)
        assert issubclass(UnionShelter, ReloadableBaseModel)
        assert issubclass(Dog, BasePet)
        assert issubclass(Cat, BasePet)

        settings = get_settings()
        assert settings.enable_schema_rebuilding is True
        assert settings.schema_rebuild_parents is True

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: Shelter) -> None:
        """Verify proper instance initialization and state mapping."""
        assert isinstance(valid_instances, Shelter)
        assert isinstance(valid_instances.name, str)
        assert len(valid_instances.pets) == 1
        pet = valid_instances.pets[0]
        assert isinstance(pet, BasePet)
        if isinstance(pet, Dog):
            assert pet.bark_volume == 10
        elif isinstance(pet, Cat):
            assert pet.meow_frequency == 2.5

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify initialization with invalid values raises ValidationError."""
        BasePet.register_decorator(Dog, name="dog")
        with pytest.raises(ValidationError):
            Shelter(
                name="Invalid Shelter",
                pets=[{"pet_type": "dog", "bark_volume": "extremely-loud"}],  # type: ignore
            )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization with missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            Shelter(pets=[])  # type: ignore # Missing required 'name' field

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: Shelter) -> None:
        """Verify serialization and validation boundaries against context."""
        dumped_data = valid_instances.model_dump()
        recreated = Shelter.model_validate(dumped_data)
        assert recreated == valid_instances

    @pytest.mark.smoke
    def test_dynamic_registry_resolution(self) -> None:
        """Validate that registered keys build and execute properly end-to-end."""
        BasePet.register_decorator(Dog, name="dog")
        BasePet.register_decorator(Cat, name="cat")

        expected_keys = {"dog", "cat"}
        registered_keys = set(BasePet.registry.keys())
        assert expected_keys.issubset(registered_keys)

        dog_payload = {
            "name": "Dog Shelter",
            "pets": [{"pet_type": "dog", "bark_volume": 8}],
        }
        cat_payload = {
            "name": "Cat Shelter",
            "pets": [{"pet_type": "cat", "meow_frequency": 1.2}],
        }

        assert isinstance(Shelter.model_validate(dog_payload).pets[0], Dog)
        assert isinstance(Shelter.model_validate(cat_payload).pets[0], Cat)

    @pytest.mark.smoke
    def test_cascade_on_registration(self) -> None:
        """Verify registering a subclass automatically rebuilds dependent parents."""
        # Register Cat first so it forces the union schema instead of any_schema
        BasePet.register_decorator(Cat, name="cat")

        # Initially, validating a dog payload should fail since 'dog' is not registered.
        dog_payload = {
            "name": "Paws",
            "pets": [{"pet_type": "dog", "bark_volume": 5}],
        }
        with pytest.raises(ValidationError):
            Shelter.model_validate(dog_payload)

        # Register the Dog subclass
        BasePet.register_decorator(Dog, name="dog")

        # Now validation should succeed as Shelter schema auto-rebuilt
        validated = Shelter.model_validate(dog_payload)
        assert isinstance(validated.pets[0], Dog)

    @pytest.mark.sanity
    def test_cascade_on_second_registration(self) -> None:
        """Verify parent schemas rebuild transitively upon additional registrations."""
        BasePet.register_decorator(Dog, name="dog")

        cat_payload = {
            "name": "Mew",
            "pets": [{"pet_type": "cat", "meow_frequency": 3.0}],
        }
        with pytest.raises(ValidationError):
            Shelter.model_validate(cat_payload)

        # Register Cat subclass
        BasePet.register_decorator(Cat, name="cat")

        # Shelter schema should cascade rebuild to accept Cat
        validated = Shelter.model_validate(cat_payload)
        assert isinstance(validated.pets[0], Cat)

    @pytest.mark.sanity
    def test_schema_rebuilding_disabled(self) -> None:
        """Verify schema rebuilding is ignored when globally disabled."""
        BasePet.register_decorator(Cat, name="cat")
        get_settings().enable_schema_rebuilding = False

        # Register Dog subclass
        BasePet.register_decorator(Dog, name="dog")

        # Validating dog payload should still fail because rebuilding is disabled
        dog_payload = {
            "name": "Paws",
            "pets": [{"pet_type": "dog", "bark_volume": 5}],
        }
        with pytest.raises(ValidationError):
            Shelter.model_validate(dog_payload)

    @pytest.mark.sanity
    def test_schema_rebuild_parents_disabled(self) -> None:
        """Verify parent rebuilding is skipped if parent propagation is disabled."""
        BasePet.register_decorator(Cat, name="cat")
        get_settings().schema_rebuild_parents = False

        # Register Dog subclass
        BasePet.register_decorator(Dog, name="dog")

        # BasePet schema might be rebuilt, but Shelter parent should not compile Dog
        dog_payload = {
            "name": "Paws",
            "pets": [{"pet_type": "dog", "bark_volume": 5}],
        }
        with pytest.raises(ValidationError):
            Shelter.model_validate(dog_payload)

    @pytest.mark.regression
    def test_cascade_with_various_annotations(self) -> None:
        """Verify rebuild cascades propagate to parent fields with
        different annotations.
        """
        BasePet.register_decorator(Cat, name="cat")
        optional_payload = {
            "name": "Opt Shelter",
            "pet": {"pet_type": "dog", "bark_volume": 7},
        }
        union_payload = {
            "name": "Union Shelter",
            "pet": {"pet_type": "dog", "bark_volume": 9},
        }

        # Initially validation fails
        with pytest.raises(ValidationError):
            OptionalShelter.model_validate(optional_payload)
        with pytest.raises(ValidationError):
            UnionShelter.model_validate(union_payload)

        # Register subclass
        BasePet.register_decorator(Dog, name="dog")

        # Now both schemas should accept the registered class
        opt_validated = OptionalShelter.model_validate(optional_payload)
        assert isinstance(opt_validated.pet, Dog)

        union_validated = UnionShelter.model_validate(union_payload)
        assert isinstance(union_validated.pet, Dog)
