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

"""End-to-end tests for Dynamic Tagged Union validation (US-2.1)."""

from __future__ import annotations

import inspect
from collections.abc import Generator
from typing import Literal

import pytest
from pydantic import ValidationError

from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import reset_settings


class ContentItemBase(PydanticClassRegistryMixin):
    """Base model for dynamic tagged union E2E testing."""

    schema_discriminator = "item_type"
    item_type: str


@ContentItemBase.register("text")
class TextContentItem(ContentItemBase):
    """Subclass representing text content."""

    item_type: Literal["text"] = "text"
    body: str


@ContentItemBase.register("image")
class ImageContentItem(ContentItemBase):
    """Subclass representing image content."""

    item_type: Literal["image"] = "image"
    url: str
    width: int


class TestDynamicTaggedUnion:
    """End-to-end test suite for US-2.1: Dynamic Tagged Union Generation."""

    @pytest.fixture(autouse=True)
    def setup_registry_cleaner(self) -> Generator[None, None, None]:
        """Ensure ContentItemBase registry is initialized and cleaned up."""
        reset_settings()
        ContentItemBase.clear_registry()
        ContentItemBase.register_decorator(TextContentItem, name="text")
        ContentItemBase.register_decorator(ImageContentItem, name="image")
        yield
        ContentItemBase.clear_registry()
        reset_settings()

    @pytest.fixture(params=["text", "image"])
    def valid_instances(self, request: pytest.FixtureRequest) -> ContentItemBase:
        """Fixture supplying properly initialized subclass instances."""
        if request.param == "text":
            return TextContentItem(body="hello world")
        return ImageContentItem(url="https://example.com/img.png", width=1024)

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(ContentItemBase, PydanticClassRegistryMixin)
        assert hasattr(ContentItemBase, "register")
        assert hasattr(ContentItemBase, "get_schema_discriminator")
        assert hasattr(ContentItemBase, "registered_classes")
        assert hasattr(ContentItemBase, "clear_registry")

        # Verify signatures
        register_signature = inspect.signature(ContentItemBase.register)
        assert "name" in register_signature.parameters

        discriminator_sig = inspect.signature(ContentItemBase.get_schema_discriminator)
        assert len(discriminator_sig.parameters) == 0 or (
            len(discriminator_sig.parameters) == 1
            and "cls" in discriminator_sig.parameters
        )

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: ContentItemBase) -> None:
        """Verify model instances are successfully created."""
        assert isinstance(valid_instances, ContentItemBase)
        if isinstance(valid_instances, TextContentItem):
            assert valid_instances.body == "hello world"
            assert valid_instances.item_type == "text"
        elif isinstance(valid_instances, ImageContentItem):
            assert valid_instances.url == "https://example.com/img.png"
            assert valid_instances.width == 1024
            assert valid_instances.item_type == "image"

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify validation errors are raised for invalid types."""
        with pytest.raises(ValidationError):
            ImageContentItem(url="https://example.com/img.png", width="not_an_int")  # type: ignore

        with pytest.raises(ValidationError):
            TextContentItem(body=12345)  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify validation errors are raised for missing mandatory fields."""
        with pytest.raises(ValidationError):
            TextContentItem()  # type: ignore

        with pytest.raises(ValidationError):
            ImageContentItem(url="https://example.com/img.png")  # type: ignore

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: ContentItemBase) -> None:
        """Verify Pydantic serialization and validation pipelines."""
        # Test model_dump
        dumped_dict = valid_instances.model_dump()
        assert dumped_dict["item_type"] in ("text", "image")

        # Test model_validate
        validated_instance = ContentItemBase.model_validate(dumped_dict)
        assert isinstance(validated_instance, ContentItemBase)
        assert validated_instance.item_type == valid_instances.item_type

        # Verify round-trip preserves equality
        assert validated_instance.model_dump() == dumped_dict

    @pytest.mark.regression
    def test_dynamic_flow_registry(self) -> None:
        """Verify dynamic resolution and schema compilation for all registered keys."""
        classes = ContentItemBase.registered_classes()
        assert len(classes) == 2
        assert TextContentItem in classes
        assert ImageContentItem in classes

        assert ContentItemBase.get_registered_object("text") is TextContentItem
        assert ContentItemBase.get_registered_object("image") is ImageContentItem

    @pytest.mark.sanity
    def test_deserialize_polymorphic_payload(self) -> None:
        """Validate dynamic tagged union parsing from dictionaries."""
        text_payload = {"item_type": "text", "body": "polymorphic text payload"}
        validated_text = ContentItemBase.model_validate(text_payload)
        assert isinstance(validated_text, TextContentItem)
        assert validated_text.body == "polymorphic text payload"

        image_payload = {
            "item_type": "image",
            "url": "https://example.com/poly.png",
            "width": 800,
        }
        validated_image = ContentItemBase.model_validate(image_payload)
        assert isinstance(validated_image, ImageContentItem)
        assert validated_image.url == "https://example.com/poly.png"
        assert validated_image.width == 800

    @pytest.mark.regression
    def test_fallback_schema_when_empty(self) -> None:
        """Verify fallback behavior when no subclasses are registered."""

        # Define a test-specific empty registry class
        class EmptyBase(PydanticClassRegistryMixin):
            schema_discriminator = "type"

        EmptyBase.clear_registry()
        # Verify it falls back safely to general schema validation
        empty_payload = {"type": "arbitrary", "any_field": "any_value"}
        validated_empty = EmptyBase.model_validate(empty_payload)
        assert validated_empty == empty_payload
