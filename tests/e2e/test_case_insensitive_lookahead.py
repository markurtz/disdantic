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

"""End-to-end tests for Case-Insensitive Lookahead validation (US-2.2)."""

from __future__ import annotations

import inspect
from collections.abc import Generator
from typing import Literal

import pytest
from pydantic import ValidationError

from disdantic.exceptions import DiscriminatorNotFoundError
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import reset_settings


class MessageBase(PydanticClassRegistryMixin):
    """Base model for case-insensitive lookahead E2E testing."""

    schema_discriminator = "message_type"
    message_type: str


@MessageBase.register("SlackMessage")
class SlackMessage(MessageBase):
    """Subclass representing a Slack message with mixed casing key."""

    message_type: Literal["SlackMessage"] = "SlackMessage"
    channel: str


@MessageBase.register("email_message")
class EmailMessage(MessageBase):
    """Subclass representing an email message with lowercase key."""

    message_type: Literal["email_message"] = "email_message"
    recipient: str


class TestCaseInsensitiveLookahead:
    """End-to-end test suite for US-2.2: Case-Insensitive Lookahead Validation."""

    @pytest.fixture(autouse=True)
    def setup_registry_cleaner(self) -> Generator[None, None, None]:
        """Ensure MessageBase registry is initialized and cleaned up."""
        reset_settings()
        MessageBase.clear_registry()
        MessageBase.register_decorator(SlackMessage, name="SlackMessage")
        MessageBase.register_decorator(EmailMessage, name="email_message")
        yield
        MessageBase.clear_registry()
        reset_settings()

    @pytest.fixture(params=["slack", "email"])
    def valid_instances(self, request: pytest.FixtureRequest) -> MessageBase:
        """Fixture supplying properly initialized subclass instances."""
        if request.param == "slack":
            return SlackMessage(channel="general")
        return EmailMessage(recipient="user@example.com")

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(MessageBase, PydanticClassRegistryMixin)
        assert hasattr(MessageBase, "register")
        assert hasattr(MessageBase, "get_schema_discriminator")
        assert hasattr(MessageBase, "registered_classes")
        assert hasattr(MessageBase, "clear_registry")

        # Verify signatures
        register_signature = inspect.signature(MessageBase.register)
        assert "name" in register_signature.parameters

        discriminator_sig = inspect.signature(MessageBase.get_schema_discriminator)
        assert len(discriminator_sig.parameters) == 0 or (
            len(discriminator_sig.parameters) == 1
            and "cls" in discriminator_sig.parameters
        )

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: MessageBase) -> None:
        """Verify model instances are successfully created."""
        assert isinstance(valid_instances, MessageBase)
        if isinstance(valid_instances, SlackMessage):
            assert valid_instances.channel == "general"
            assert valid_instances.message_type == "SlackMessage"
        elif isinstance(valid_instances, EmailMessage):
            assert valid_instances.recipient == "user@example.com"
            assert valid_instances.message_type == "email_message"

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify validation errors are raised for invalid types."""
        with pytest.raises(ValidationError):
            SlackMessage(channel=12345)  # type: ignore

        with pytest.raises(ValidationError):
            EmailMessage(recipient=True)  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify validation errors are raised for missing mandatory fields."""
        with pytest.raises(ValidationError):
            SlackMessage()  # type: ignore

        with pytest.raises(ValidationError):
            EmailMessage()  # type: ignore

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: MessageBase) -> None:
        """Verify Pydantic serialization and validation pipelines."""
        # Test model_dump
        dumped_dict = valid_instances.model_dump()
        assert dumped_dict["message_type"] in ("SlackMessage", "email_message")

        # Test model_validate
        validated_instance = MessageBase.model_validate(dumped_dict)
        assert isinstance(validated_instance, MessageBase)
        assert validated_instance.message_type == valid_instances.message_type

        # Verify round-trip preserves equality
        assert validated_instance.model_dump() == dumped_dict

    @pytest.mark.regression
    def test_dynamic_flow_registry(self) -> None:
        """Verify dynamic resolution and schema compilation for all registered keys."""
        classes = MessageBase.registered_classes()
        assert len(classes) == 2
        assert SlackMessage in classes
        assert EmailMessage in classes

        assert MessageBase.get_registered_object("SlackMessage") is SlackMessage
        assert MessageBase.get_registered_object("email_message") is EmailMessage

    @pytest.mark.sanity
    def test_casing_lookahead_coercion(self) -> None:
        """Validate dynamic lookahead parsing and casing coercion from dict payloads."""
        # Test lowercase input for SlackMessage (canonical: "SlackMessage")
        slack_payload_lower = {"message_type": "slackmessage", "channel": "random"}
        validated_slack_lower = MessageBase.model_validate(slack_payload_lower)
        assert isinstance(validated_slack_lower, SlackMessage)
        assert validated_slack_lower.channel == "random"
        assert validated_slack_lower.message_type == "SlackMessage"

        # Test uppercase input for SlackMessage
        slack_payload_upper = {
            "message_type": "SLACKMESSAGE",
            "channel": "announcements",
        }
        validated_slack_upper = MessageBase.model_validate(slack_payload_upper)
        assert isinstance(validated_slack_upper, SlackMessage)
        assert validated_slack_upper.channel == "announcements"
        assert validated_slack_upper.message_type == "SlackMessage"

        # Test mixed case input for email_message (canonical: "email_message")
        email_payload_mixed = {
            "message_type": "eMAIl_MeSSagE",
            "recipient": "test@example.com",
        }
        validated_email_mixed = MessageBase.model_validate(email_payload_mixed)
        assert isinstance(validated_email_mixed, EmailMessage)
        assert validated_email_mixed.recipient == "test@example.com"
        assert validated_email_mixed.message_type == "email_message"

    @pytest.mark.regression
    def test_casing_lookahead_coercion_invalid(self) -> None:
        """Verify unmatched casing values raise a ValidationError."""

        invalid_payload = {"message_type": "DiscordMessage", "channel": "lobby"}
        with pytest.raises(ValidationError) as error_info:
            MessageBase.model_validate(invalid_payload)

        # Assert exception message contains the custom error details
        assert "Failed to resolve polymorphic configuration layer" in str(
            error_info.value
        )
        assert "DiscordMessage" in str(error_info.value)
        assert "SlackMessage" in str(error_info.value)
        assert "email_message" in str(error_info.value)

        # Directly verify the exception instantiation and attributes to satisfy the
        # custom error type contract
        custom_error = DiscriminatorNotFoundError(
            "DiscordMessage", ["SlackMessage", "email_message"]
        )
        assert custom_error.rejected_value == "DiscordMessage"
        assert custom_error.valid_options == ["SlackMessage", "email_message"]
