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

import asyncio
import json
import multiprocessing
import multiprocessing.connection
import threading
from typing import Any, Literal

import pytest
from pydantic import BaseModel, ValidationError
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.registry import PydanticClassRegistryMixin
from tests.conftest import async_timeout

# ==============================================================================
# Module-level Base registries and subclasses for CLI / import-level checks
# ==============================================================================


class BaseE2EMessage(PydanticClassRegistryMixin):
    """Base message model for E2E testing using default discriminator."""

    schema_discriminator = "model_type"
    model_type: str


@BaseE2EMessage.register("text")
class TextE2EMessage(BaseE2EMessage):
    """Text message subclass for E2E testing."""

    model_type: Literal["text"] = "text"
    content: str


@BaseE2EMessage.register("image")
class ImageE2EMessage(BaseE2EMessage):
    """Image message subclass for E2E testing."""

    model_type: Literal["image"] = "image"
    url: str


class ContainerE2EModel(BaseModel):
    """Container model nesting the polymorphic BaseE2EMessage."""

    message: BaseE2EMessage


# ==============================================================================
# Custom discriminator base registries and subclasses
# ==============================================================================


class BaseCustomMessage(PydanticClassRegistryMixin):
    """Base message model for E2E testing using custom discriminator."""

    schema_discriminator = "msg_type"
    msg_type: str


@BaseCustomMessage.register("text")
class TextCustomMessage(BaseCustomMessage):
    """Text message subclass for E2E testing with custom discriminator."""

    msg_type: Literal["text"] = "text"
    content: str


@BaseCustomMessage.register("image")
class ImageCustomMessage(BaseCustomMessage):
    """Image message subclass for E2E testing with custom discriminator."""

    msg_type: Literal["image"] = "image"
    url: str


class CustomContainerModel(BaseModel):
    """Container model nesting the polymorphic BaseCustomMessage."""

    message: BaseCustomMessage


# ==============================================================================
# Multiprocessing Worker for IPC Testing
# ==============================================================================


def ipc_validation_worker(
    conn: multiprocessing.connection.Connection,
    base_class: type[PydanticClassRegistryMixin],
) -> None:
    """Worker function for multi-process IPC validation."""
    try:
        # Receive serialized JSON payload
        payload_json = conn.recv()
        payload = json.loads(payload_json)

        # Validate payload using the polymorphic base class
        validated_instance = base_class.model_validate(payload)

        # Send back the dumped dictionary along with its type name
        conn.send(
            {
                "success": True,
                "type_name": validated_instance.__class__.__name__,
                "data": validated_instance.model_dump(),
            }
        )
    except Exception as err:  # noqa: BLE001
        conn.send(
            {
                "success": False,
                "error_type": err.__class__.__name__,
                "error_msg": str(err),
            }
        )


# ==============================================================================
# Helper context mapping for parameterized tests
# ==============================================================================


class PolymorphicTestContext:
    """Context object holding base class, subclasses, and discriminator key."""

    def __init__(
        self,
        base_class: type[PydanticClassRegistryMixin],
        text_class: type[BaseModel],
        image_class: type[BaseModel],
        container_class: type[BaseModel],
        discriminator: str,
    ) -> None:
        self.base_class = base_class
        self.text_class = text_class
        self.image_class = image_class
        self.container_class = container_class
        self.discriminator = discriminator


# ==============================================================================
# Main E2E Test Suite
# ==============================================================================


class TestPolymorphicUnion:
    """E2E test suite for validating polymorphic tagged unions."""

    @pytest.fixture(params=["default_discriminator", "custom_discriminator"])
    def valid_instances(self, request: pytest.FixtureRequest) -> PolymorphicTestContext:
        """Fixture supplying clean polymorphic test contexts."""
        if request.param == "default_discriminator":
            return PolymorphicTestContext(
                base_class=BaseE2EMessage,
                text_class=TextE2EMessage,
                image_class=ImageE2EMessage,
                container_class=ContainerE2EModel,
                discriminator="model_type",
            )
        else:
            return PolymorphicTestContext(
                base_class=BaseCustomMessage,
                text_class=TextCustomMessage,
                image_class=ImageCustomMessage,
                container_class=CustomContainerModel,
                discriminator="msg_type",
            )

    @pytest.mark.smoke
    def test_environment_contract(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify the basic type hierarchies are set up correctly."""
        assert issubclass(valid_instances.base_class, PydanticClassRegistryMixin)
        assert issubclass(valid_instances.text_class, valid_instances.base_class)
        assert issubclass(valid_instances.image_class, valid_instances.base_class)
        assert issubclass(valid_instances.container_class, BaseModel)

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: PolymorphicTestContext) -> None:
        """Validate registry class initialization and discriminator tags."""
        base_cls = valid_instances.base_class
        assert base_cls.get_schema_discriminator() == valid_instances.discriminator
        assert "text" in base_cls.registry
        assert "image" in base_cls.registry

    @pytest.mark.regression
    def test_invalid_initialization_values(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify that invalid discriminator values block deserialization."""
        base_cls = valid_instances.base_class
        disc_key = valid_instances.discriminator
        # 1. Invalid data type for discriminator (integer)
        payload_int = {disc_key: 123}
        with pytest.raises(ValidationError) as exc_info:
            base_cls.model_validate(payload_int)
        assert "Failed to resolve polymorphic" in str(exc_info.value)

        # 2. Empty string discriminator
        payload_empty = {disc_key: ""}
        with pytest.raises(ValidationError) as exc_info:
            base_cls.model_validate(payload_empty)
        assert "Failed to resolve polymorphic" in str(exc_info.value)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify that omitting the discriminator key blocks validation."""
        payload_missing = {"content": "missing discriminator"}
        with pytest.raises(ValidationError):
            valid_instances.base_class.model_validate(payload_missing)

    @pytest.mark.smoke
    def test_polymorphic_deserialization_default_discriminator(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Validate polymorphic validation with happy-path payloads."""
        disc_key = valid_instances.discriminator
        payload_text = {disc_key: "text", "content": "hello"}
        result_text: Any = valid_instances.base_class.model_validate(payload_text)
        assert isinstance(result_text, valid_instances.text_class)
        assert result_text.content == "hello"

        payload_image = {
            disc_key: "image",
            "url": "https://example.com/pic.png",
        }
        result_image: Any = valid_instances.base_class.model_validate(payload_image)
        assert isinstance(result_image, valid_instances.image_class)
        assert result_image.url == "https://example.com/pic.png"

    @pytest.mark.sanity
    def test_case_insensitive_lookahead_routing(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify case-insensitive lookahead discriminator routing."""
        disc_key = valid_instances.discriminator
        # Test uppercase
        payload_upper = {disc_key: "TEXT", "content": "uppercase hello"}
        result_upper: Any = valid_instances.base_class.model_validate(payload_upper)
        assert isinstance(result_upper, valid_instances.text_class)
        assert result_upper.content == "uppercase hello"

        # Test mixed case
        payload_mixed = {
            disc_key: "ImAgE",
            "url": "https://example.com/mixed.png",
        }
        result_mixed: Any = valid_instances.base_class.model_validate(payload_mixed)
        assert isinstance(result_mixed, valid_instances.image_class)
        assert result_mixed.url == "https://example.com/mixed.png"

    @pytest.mark.smoke
    def test_unregistered_discriminator_handling(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify unregistered discriminator types yield precise options."""
        disc_key = valid_instances.discriminator
        payload_unregistered = {disc_key: "video", "path": "/media"}
        with pytest.raises(ValidationError) as exc_info:
            valid_instances.base_class.model_validate(payload_unregistered)

        err_msg = str(exc_info.value)
        assert "Failed to resolve polymorphic" in err_msg
        assert "video" in err_msg
        assert "text" in err_msg
        assert "image" in err_msg

    @pytest.mark.regression
    def test_multithreaded_validation(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify polymorphic validation remains thread-safe."""
        exceptions_list: list[Exception] = []
        disc_key = valid_instances.discriminator

        def thread_worker() -> None:
            try:
                for idx in range(10):
                    payload = {
                        disc_key: "TEXT",
                        "content": f"thread-{idx}",
                    }
                    result: Any = valid_instances.base_class.model_validate(payload)
                    assert isinstance(result, valid_instances.text_class)
                    assert result.content == f"thread-{idx}"
            except Exception as err:  # noqa: BLE001
                exceptions_list.append(err)

        threads = [threading.Thread(target=thread_worker) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not exceptions_list, f"Exceptions encountered: {exceptions_list}"

    @pytest.mark.regression
    @async_timeout(5.0)
    async def test_async_validation(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify polymorphic validation operates in async event loops."""
        disc_key = valid_instances.discriminator

        async def validate_task(index: int) -> Any:
            payload = {disc_key: "TEXT", "content": f"async-{index}"}
            await asyncio.sleep(0.001)
            return valid_instances.base_class.model_validate(payload)

        tasks = [validate_task(idx) for idx in range(20)]
        results = await asyncio.gather(*tasks)
        for idx, result in enumerate(results):
            assert isinstance(result, valid_instances.text_class)
            assert result.content == f"async-{idx}"

    @pytest.mark.regression
    def test_multiprocess_ipc_validation(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify polymorphic validation is robust across IPC boundaries."""
        parent_conn, child_conn = multiprocessing.Pipe()
        process = multiprocessing.Process(
            target=ipc_validation_worker,
            args=(child_conn, valid_instances.base_class),
        )
        process.start()

        # Send serialized payload over IPC
        disc_key = valid_instances.discriminator
        payload = {disc_key: "TEXT", "content": "ipc-message"}
        parent_conn.send(json.dumps(payload))

        # Wait for the response
        response = parent_conn.recv()
        process.join()

        # Assert validations performed successfully in the child process
        assert response["success"] is True, (
            f"IPC validation failed: {response.get('error_msg')}"
        )
        assert response["type_name"] in ("TextE2EMessage", "TextCustomMessage")
        assert response["data"]["content"] == "ipc-message"

    @pytest.mark.sanity
    def test_marshalling(self, valid_instances: PolymorphicTestContext) -> None:
        """Verify roundtrip marshalling (direct and nested container properties)."""
        disc_key = valid_instances.discriminator
        # 1. Direct model roundtrip
        text_instance = valid_instances.text_class(content="direct data")
        dumped_dict = text_instance.model_dump()
        assert dumped_dict[disc_key] == "text"

        validated: Any = valid_instances.base_class.model_validate(dumped_dict)
        assert isinstance(validated, valid_instances.text_class)
        assert validated.content == "direct data"

        # 2. Nested container roundtrip (Base Case Nested Properties)
        container_instance = valid_instances.container_class(message=text_instance)
        container_dump = container_instance.model_dump()
        assert "message" in container_dump
        assert container_dump["message"][disc_key] == "text"
        assert container_dump["message"]["content"] == "direct data"

        container_validated: Any = valid_instances.container_class.model_validate(
            container_dump
        )
        assert isinstance(container_validated, valid_instances.container_class)
        message_validated = container_validated.message
        assert isinstance(message_validated, valid_instances.text_class)
        assert message_validated.content == "direct data"

    @pytest.mark.regression
    def test_dynamic_flow_registry(
        self, valid_instances: PolymorphicTestContext
    ) -> None:
        """Verify dynamic discovery of registered subclasses."""
        registered = valid_instances.base_class.registered_classes()
        assert len(registered) == 2
        assert valid_instances.text_class in registered
        assert valid_instances.image_class in registered


# ==============================================================================
# CLI Entrypoint E2E Tests
# ==============================================================================


@pytest.mark.sanity
class TestCLIEntrypoint:
    """E2E test suite for validating CLI entrypoints."""

    def test_cli_list(self) -> None:
        """Verify disdantic list displays registries and their elements."""
        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "BaseE2EMessage" in result.stdout
        assert "BaseCustomMessage" in result.stdout
        assert "text" in result.stdout
        assert "image" in result.stdout

    def test_cli_list_json(self) -> None:
        """Verify list --json prints a valid registry dictionary map."""
        runner = CliRunner()
        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "BaseE2EMessage" in data
        assert "BaseCustomMessage" in data
        expected_text = "tests.e2e.test_polymorphic_union.TextE2EMessage"
        expected_image = "tests.e2e.test_polymorphic_union.ImageE2EMessage"
        assert data["BaseE2EMessage"]["text"] == expected_text
        assert data["BaseE2EMessage"]["image"] == expected_image

    def test_cli_schema(self) -> None:
        """Verify generating schema for module-level registry base classes."""
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["schema", "tests.e2e.test_polymorphic_union.BaseE2EMessage"],
        )
        assert result.exit_code == 0
        schema_dict = json.loads(result.stdout)
        assert "$defs" in schema_dict
        assert "TextE2EMessage" in schema_dict["$defs"]
        assert "ImageE2EMessage" in schema_dict["$defs"]
