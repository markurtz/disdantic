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

import inspect
import json
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.exceptions import RegistryCollisionError
from disdantic.model import ReloadableBaseModel
from disdantic.registry import (
    PydanticClassRegistryMixin,
    RegistryManager,
    RegistryMixin,
)
from disdantic.settings import get_settings, reset_settings


class ConcreteRegistry(RegistryMixin[type]):
    """Concrete registry class used for RegistryMixin integration testing."""


class DummyService:
    """A dummy service class for testing RegistryMixin."""

    def __init__(self, name: str, value: int) -> None:
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        if value < 0:
            raise ValueError("value must be non-negative")
        self.name = name
        self.value = value


class BaseIntegrationModel(PydanticClassRegistryMixin):
    """Base model class used to test PydanticClassRegistryMixin integration."""

    schema_discriminator = "msg_type"
    msg_type: str


@BaseIntegrationModel.register("text")
class TextIntegrationModel(BaseIntegrationModel):
    """Subclass representing the text integration message type."""

    msg_type: Literal["text"] = "text"
    text_content: str


@BaseIntegrationModel.register("image")
class ImageIntegrationModel(BaseIntegrationModel):
    """Subclass representing the image integration message type."""

    msg_type: Literal["image"] = "image"
    image_url: str
    width: int


class TestRegistryMixin:
    """Integration test suite for validating RegistryMixin."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensure clean settings and registry before and after tests."""
        reset_settings()
        ConcreteRegistry.clear_registry()
        yield
        ConcreteRegistry.clear_registry()
        reset_settings()

    @pytest.fixture(params=["service_alpha", "service_beta"])
    def valid_instances(self, request: pytest.FixtureRequest) -> DummyService:
        """Fixture supplying properly initialized dummy service instances."""
        if request.param == "service_alpha":
            return DummyService(name="alpha", value=42)
        return DummyService(name="beta", value=100)

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate structural contracts across integrated boundaries."""
        assert issubclass(ConcreteRegistry, RegistryMixin)
        assert hasattr(ConcreteRegistry, "registry")
        assert hasattr(ConcreteRegistry, "_lower_registry")
        assert hasattr(ConcreteRegistry, "registry_auto_discovery")
        assert hasattr(ConcreteRegistry, "registry_populated")

        # Check parameter signatures for key methods
        assert inspect.isroutine(ConcreteRegistry.is_auto_discovery_enabled)
        assert inspect.isroutine(ConcreteRegistry.register)
        assert inspect.isroutine(ConcreteRegistry.register_decorator)
        assert inspect.isroutine(ConcreteRegistry.auto_populate_registry)
        assert inspect.isroutine(ConcreteRegistry.registered_objects)
        assert inspect.isroutine(ConcreteRegistry.is_registered)
        assert inspect.isroutine(ConcreteRegistry.get_registered_object)
        assert inspect.isroutine(ConcreteRegistry.clear_registry)
        assert inspect.isroutine(ConcreteRegistry.unregister)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: DummyService) -> None:
        """Verify dummy service instances are successfully created."""
        assert isinstance(valid_instances, DummyService)
        assert valid_instances.name in {"alpha", "beta"}
        assert valid_instances.value in {42, 100}

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify that passing invalid values during construction raises errors."""
        with pytest.raises(ValueError, match="value must be non-negative"):
            DummyService(name="negative", value=-1)

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify that omitting mandatory fields raises TypeError."""
        with pytest.raises(TypeError):
            DummyService()  # type: ignore

    @pytest.mark.sanity
    def test_register_decorator(self) -> None:
        """Verify subclass registration works dynamically with name variations."""

        # Test no name default registration
        @ConcreteRegistry.register()
        class AutoNamedService:
            pass

        expected = AutoNamedService
        assert ConcreteRegistry.get_registered_object("AutoNamedService") is expected
        assert "AutoNamedService" in ConcreteRegistry.registry

        # Test string name registration
        @ConcreteRegistry.register("custom")
        class CustomNamedService:
            pass

        assert ConcreteRegistry.get_registered_object("custom") is CustomNamedService
        assert "custom" in ConcreteRegistry.registry

        # Test list of names registration
        @ConcreteRegistry.register(["alias_one", "alias_two"])
        class MultiNamedService:
            pass

        assert ConcreteRegistry.get_registered_object("alias_one") is MultiNamedService
        assert ConcreteRegistry.get_registered_object("alias_two") is MultiNamedService
        assert "alias_one" in ConcreteRegistry.registry
        assert "alias_two" in ConcreteRegistry.registry

    @pytest.mark.sanity
    def test_register_decorator_invalid_name_format(self) -> None:
        """Verify registry decorator rejects unsupported name types."""
        with pytest.raises(ValueError, match="Unsupported naming format"):
            ConcreteRegistry.register_decorator(DummyService, name=123)  # type: ignore

    @pytest.mark.sanity
    def test_register_decorator_non_string_sequence(self) -> None:
        """Verify registry decorator rejects non-string sequence items."""
        err_msg = "Registry keys must explicitly be strings"
        with pytest.raises(ValueError, match=err_msg):
            ConcreteRegistry.register_decorator(DummyService, name=["valid", 456])  # type: ignore

    @pytest.mark.regression
    def test_clear_registry(self) -> None:
        """Verify clear_registry resets active registries and flags."""
        ConcreteRegistry.register_decorator(DummyService, name="temp")
        ConcreteRegistry.registry_populated = True
        assert len(ConcreteRegistry.registry) > 0

        ConcreteRegistry.clear_registry()
        assert len(ConcreteRegistry.registry) == 0
        assert len(ConcreteRegistry._lower_registry) == 0
        assert ConcreteRegistry.registry_populated is False

    @pytest.mark.smoke
    def test_unregister(self) -> None:
        """Verify unregister programmatically removes mappings."""
        ConcreteRegistry.register_decorator(DummyService, name="temp_service")
        assert ConcreteRegistry.is_registered("temp_service")

        ConcreteRegistry.unregister("temp_service")
        assert not ConcreteRegistry.is_registered("temp_service")
        assert "temp_service" not in ConcreteRegistry.registry
        assert "temp_service" not in ConcreteRegistry._lower_registry

    @pytest.mark.sanity
    def test_unregister_not_found(self) -> None:
        """Verify unregister raises ValueError for missing key."""
        err_msg = "is not present in the ConcreteRegistry registry"
        with pytest.raises(ValueError, match=err_msg):
            ConcreteRegistry.unregister("non_existent_key")

    @pytest.mark.regression
    def test_auto_populate_registry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify auto-population dynamically imports modules."""
        package_dir = tmp_path / "temp_discovery_mixin_pkg"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

        submodule_file = package_dir / "dynamic_mixin_sub.py"
        submodule_content = """from __future__ import annotations
from tests.python.integration.test_registry import ConcreteRegistry, DummyService

@ConcreteRegistry.register("mixin_dynamic")
class MixinDynamicService(DummyService):
    def __init__(self) -> None:
        super().__init__("mixin_dynamic", 999)
"""
        submodule_file.write_text(submodule_content, encoding="utf-8")

        monkeypatch.syspath_prepend(str(tmp_path))

        monkeypatch.setattr(ConcreteRegistry, "registry_auto_discovery", True)
        monkeypatch.setattr(
            ConcreteRegistry, "auto_package", "temp_discovery_mixin_pkg"
        )

        reset_settings()

        # Trigger auto populate
        assert ConcreteRegistry.auto_populate_registry() is True
        assert ConcreteRegistry.is_registered("mixin_dynamic")

        # Clean up imported sys.modules
        sys.modules.pop("temp_discovery_mixin_pkg", None)
        sys.modules.pop("temp_discovery_mixin_pkg.dynamic_mixin_sub", None)

    @pytest.mark.regression
    def test_auto_populate_registry_already_populated(self) -> None:
        """Verify auto-population returns False if already populated."""
        ConcreteRegistry.registry_auto_discovery = True
        ConcreteRegistry.registry_populated = True
        assert ConcreteRegistry.auto_populate_registry() is False

    @pytest.mark.sanity
    def test_auto_populate_disabled(self) -> None:
        """Verify auto-population is rejected when auto discovery is disabled."""
        ConcreteRegistry.registry_auto_discovery = False
        get_settings().registry_auto_discovery = False

        with pytest.raises(ValueError, match="Auto-population rejected"):
            ConcreteRegistry.auto_populate_registry()


class TestPydanticClassRegistryMixin:
    """Integration test suite for validating PydanticClassRegistryMixin."""

    @pytest.fixture(autouse=True)
    def setup_registry_cleaner(self) -> Generator[None, None, None]:
        """Ensure BaseIntegrationModel registry is initialized and cleaned up."""
        reset_settings()
        BaseIntegrationModel.clear_registry()
        BaseIntegrationModel.register_decorator(TextIntegrationModel, name="text")
        BaseIntegrationModel.register_decorator(ImageIntegrationModel, name="image")
        yield
        BaseIntegrationModel.clear_registry()
        reset_settings()

    @pytest.fixture(params=["text", "image"])
    def valid_instances(self, request: pytest.FixtureRequest) -> BaseIntegrationModel:
        """Fixture supplying properly initialized subclass instances."""
        if request.param == "text":
            return TextIntegrationModel(text_content="hello world")
        return ImageIntegrationModel(image_url="http://image.png", width=640)

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Validate structural contracts across integrated boundaries."""
        assert issubclass(BaseIntegrationModel, PydanticClassRegistryMixin)
        assert issubclass(BaseIntegrationModel, ReloadableBaseModel)
        assert issubclass(BaseIntegrationModel, RegistryMixin)

        assert hasattr(BaseIntegrationModel, "register")
        assert hasattr(BaseIntegrationModel, "get_schema_discriminator")
        assert hasattr(BaseIntegrationModel, "registered_classes")
        assert hasattr(BaseIntegrationModel, "clear_registry")

        # Check parameter signatures
        register_signature = inspect.signature(BaseIntegrationModel.register)
        assert "name" in register_signature.parameters

        get_discriminator_signature = inspect.signature(
            BaseIntegrationModel.get_schema_discriminator
        )
        assert len(get_discriminator_signature.parameters) == 0 or (
            len(get_discriminator_signature.parameters) == 1
            and "cls" in get_discriminator_signature.parameters
        )

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: BaseIntegrationModel) -> None:
        """Verify model instances are successfully created."""
        assert isinstance(valid_instances, BaseIntegrationModel)
        if isinstance(valid_instances, TextIntegrationModel):
            assert valid_instances.text_content == "hello world"
        elif isinstance(valid_instances, ImageIntegrationModel):
            assert valid_instances.image_url == "http://image.png"
            assert valid_instances.width == 640

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify validation errors are raised for invalid types and options."""
        with pytest.raises(ValidationError):
            ImageIntegrationModel(image_url="http://image.png", width="not_an_int")  # type: ignore

        with pytest.raises(ValidationError):
            ImageIntegrationModel(image_url=None, width=123)  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify validation errors are raised for missing mandatory fields."""
        with pytest.raises(ValidationError):
            TextIntegrationModel()  # type: ignore

    @pytest.mark.sanity
    def test_register_decorator(self) -> None:
        """Verify class registration works dynamically with name variations."""
        BaseIntegrationModel.clear_registry()

        # Test single name registration
        @BaseIntegrationModel.register("json")
        class JsonModel(BaseIntegrationModel):
            json_content: str

        assert BaseIntegrationModel.get_registered_object("json") is JsonModel
        assert "json" in BaseIntegrationModel.registry
        assert "json" in BaseIntegrationModel._lower_registry

        # Test list of names registration
        @BaseIntegrationModel.register(["json_data", "JSON"])
        class JsonDataModel(BaseIntegrationModel):
            data: dict[str, str]

        assert BaseIntegrationModel.get_registered_object("json_data") is JsonDataModel
        assert BaseIntegrationModel.get_registered_object("JSON") is JsonDataModel
        assert "json_data" in BaseIntegrationModel.registry
        assert "json" in BaseIntegrationModel._lower_registry

    @pytest.mark.sanity
    def test_register_collision(self) -> None:
        """Verify duplicate class registrations raise RegistryCollisionError."""
        with pytest.raises(RegistryCollisionError):

            @BaseIntegrationModel.register("text")
            class DuplicateTextModel(BaseIntegrationModel):
                other: str

    @pytest.mark.sanity
    def test_register_invalid_type(self) -> None:
        """Verify registry decorator rejects non-BaseModel subclass types."""
        with pytest.raises(TypeError, match="must extend Pydantic BaseModel"):

            @BaseIntegrationModel.register("raw_class")
            class RawClass:
                pass

    @pytest.mark.regression
    def test_auto_populate_registry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify auto-population dynamically traverses packages."""
        package_directory = tmp_path / "temp_discovery_pkg"
        package_directory.mkdir()
        (package_directory / "__init__.py").write_text("", encoding="utf-8")

        submodule_file = package_directory / "dynamic_submodule.py"
        submodule_content = """from __future__ import annotations
from typing import Literal
from tests.python.integration.test_registry import BaseIntegrationModel

@BaseIntegrationModel.register("dynamic_text")
class DynamicTextModel(BaseIntegrationModel):
    msg_type: Literal["dynamic_text"] = "dynamic_text"
    dynamic_field: str
"""
        submodule_file.write_text(submodule_content, encoding="utf-8")

        monkeypatch.syspath_prepend(str(tmp_path))

        BaseIntegrationModel.clear_registry()
        monkeypatch.setattr(BaseIntegrationModel, "registry_auto_discovery", True)
        monkeypatch.setattr(BaseIntegrationModel, "auto_package", "temp_discovery_pkg")

        reset_settings()

        classes = BaseIntegrationModel.registered_classes()
        assert any(cls.__name__ == "DynamicTextModel" for cls in classes)
        assert BaseIntegrationModel.is_registered("dynamic_text")

        dumped_data = {"msg_type": "dynamic_text", "dynamic_field": "hello"}
        validated = BaseIntegrationModel.model_validate(dumped_data)
        assert validated.msg_type == "dynamic_text"
        assert getattr(validated, "dynamic_field") == "hello"  # noqa: B009

        sys.modules.pop("temp_discovery_pkg", None)
        sys.modules.pop("temp_discovery_pkg.dynamic_submodule", None)

    @pytest.mark.sanity
    def test_auto_populate_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify auto-population is rejected when auto discovery is disabled."""
        monkeypatch.setattr(BaseIntegrationModel, "registry_auto_discovery", False)
        reset_settings()
        get_settings().registry_auto_discovery = False

        with pytest.raises(ValueError, match="Auto-population rejected"):
            BaseIntegrationModel.auto_populate_registry()

    @pytest.mark.regression
    def test_clear_registry(self) -> None:
        """Verify clear_registry resets active registries and clears schema cache."""
        assert len(BaseIntegrationModel.registry) > 0

        BaseIntegrationModel.clear_registry()
        assert len(BaseIntegrationModel.registry) == 0
        assert len(BaseIntegrationModel._lower_registry) == 0
        assert BaseIntegrationModel.registry_populated is False

        validated_any = BaseIntegrationModel.model_validate({"arbitrary": "data"})
        assert validated_any == {"arbitrary": "data"}

    @pytest.mark.regression
    def test_marshalling(self) -> None:
        """Verify Pydantic serialization and validation pipelines."""
        text_instance = TextIntegrationModel(text_content="integration payload")
        dumped_dict = text_instance.model_dump()
        assert dumped_dict["msg_type"] == "text"
        assert dumped_dict["text_content"] == "integration payload"

        validated = BaseIntegrationModel.model_validate(dumped_dict)
        assert isinstance(validated, TextIntegrationModel)
        assert validated.text_content == "integration payload"
        assert validated.msg_type == "text"

        cased_dict = {"msg_type": "TeXt", "text_content": "cased payload"}
        validated_cased = BaseIntegrationModel.model_validate(cased_dict)
        assert isinstance(validated_cased, TextIntegrationModel)
        assert validated_cased.text_content == "cased payload"
        assert validated_cased.msg_type == "text"

    @pytest.mark.regression
    def test_registry_and_factory_integration(self) -> None:
        """Verify factory integration and discriminator lookup resolution logic."""
        resolved_text = BaseIntegrationModel.get_registered_object("text")
        assert resolved_text is TextIntegrationModel

        resolved_image_cased = BaseIntegrationModel.get_registered_object("IMAGE")
        assert resolved_image_cased is ImageIntegrationModel

        resolved_missing = BaseIntegrationModel.get_registered_object("nonexistent")
        assert resolved_missing is None

        with pytest.raises(ValidationError) as error_info:
            BaseIntegrationModel.model_validate({"msg_type": "nonexistent"})
        assert "Failed to resolve polymorphic configuration layer" in str(
            error_info.value
        )

    @pytest.mark.regression
    def test_schema_rebuilding_cascade(self, mocker: MockerFixture) -> None:
        """Verify schema rebuild propagation cascades to dependent parent models."""

        class ParentModel(ReloadableBaseModel):
            message: BaseIntegrationModel

        rebuild_mock = mocker.patch.object(
            ParentModel, "model_rebuild", wraps=ParentModel.model_rebuild
        )

        @BaseIntegrationModel.register("cascade_child")
        class CascadeChildModel(BaseIntegrationModel):
            cascade_field: str

        assert rebuild_mock.call_count >= 1
        rebuild_mock.assert_called_with(force=True)

    @pytest.mark.smoke
    def test_get_schema_discriminator_fallback(self) -> None:
        """Verify fallback behavior for resolving schema discriminator."""

        class DefaultDiscModel(PydanticClassRegistryMixin):
            pass

        assert DefaultDiscModel.get_schema_discriminator() == "model_type"

        get_settings().default_schema_discriminator = "fallback_disc"
        assert DefaultDiscModel.get_schema_discriminator() == "fallback_disc"

    @pytest.mark.sanity
    def test_registered_classes_empty(self) -> None:
        """Verify registered_classes raises ValueError when empty."""

        class EmptyClassModel(PydanticClassRegistryMixin):
            pass

        with pytest.raises(ValueError, match="No objects are currently present"):
            EmptyClassModel.registered_classes()

    @pytest.mark.sanity
    def test_trigger_base_rebuild_disabled(self, mocker: MockerFixture) -> None:
        """Verify base rebuilding is skipped if disabled in settings."""
        get_settings().enable_schema_rebuilding = False
        spy_reload = mocker.spy(BaseIntegrationModel, "reload_schema")

        BaseIntegrationModel._trigger_base_rebuild()
        spy_reload.assert_not_called()

    @pytest.mark.regression
    def test_trigger_base_rebuild_non_reloadable(self, mocker: MockerFixture) -> None:
        """Verify model_rebuild is called directly on plain BaseModel classes."""

        class PlainBaseModel(BaseModel):
            pass

        mocker.patch.object(
            BaseIntegrationModel,
            "__pydantic_schema_base_type__",
            return_value=PlainBaseModel,
        )
        spy_rebuild = mocker.patch.object(PlainBaseModel, "model_rebuild")

        BaseIntegrationModel._trigger_base_rebuild()
        spy_rebuild.assert_called_once_with(force=True)

    @pytest.mark.regression
    def test_unregister(self) -> None:
        """Verify unregistration programmatically resets validation pipelines."""
        assert BaseIntegrationModel.is_registered("text")
        valid_payload = {"msg_type": "text", "text_content": "test unregister"}

        # Validates correctly before unregister
        validated = BaseIntegrationModel.model_validate(valid_payload)
        assert isinstance(validated, TextIntegrationModel)
        assert validated.text_content == "test unregister"

        # Unregister the text model
        BaseIntegrationModel.unregister("text")
        assert not BaseIntegrationModel.is_registered("text")

        # Now validation should fail
        with pytest.raises(ValidationError):
            BaseIntegrationModel.model_validate(valid_payload)


class TestRegistryManager:
    """Integration test suite for validating RegistryManager."""

    @pytest.fixture(autouse=True)
    def clean_settings_fixture(self) -> Generator[None, None, None]:
        """Ensure clean settings before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.mark.smoke
    def test_interface_signature_validation(self) -> None:
        """Verify structural contracts and signatures of RegistryManager."""
        assert hasattr(RegistryManager, "list_registries")
        assert inspect.isroutine(RegistryManager.list_registries)

    @pytest.mark.smoke
    def test_list_registries(self) -> None:
        """Verify list_registries returns mapped registry class names and paths."""
        ConcreteRegistry.clear_registry()
        BaseIntegrationModel.clear_registry()

        ConcreteRegistry.register_decorator(DummyService, name="test_service")
        BaseIntegrationModel.register_decorator(TextIntegrationModel, name="test_text")

        registries_map = RegistryManager.list_registries()
        assert "ConcreteRegistry" in registries_map
        assert registries_map["ConcreteRegistry"] == {
            "test_service": "tests.python.integration.test_registry.DummyService"
        }
        assert "BaseIntegrationModel" in registries_map
        assert registries_map["BaseIntegrationModel"] == {
            "test_text": "tests.python.integration.test_registry.TextIntegrationModel"
        }

    @pytest.mark.regression
    def test_list_registries_fallback(self) -> None:
        """Verify path resolution fallback for objects without __name__ attribute."""
        ConcreteRegistry.clear_registry()
        # Register a class instance object which doesn't have __name__
        fallback_target = DummyService("fallback", 42)
        ConcreteRegistry.register_decorator(fallback_target, name="fallback_item")

        registries_map = RegistryManager.list_registries()
        expected_path = f"{DummyService.__module__}.{DummyService.__name__}"
        assert registries_map["ConcreteRegistry"]["fallback_item"] == expected_path

    @pytest.mark.smoke
    def test_discover_registries(self) -> None:
        """Verify discover_registries routine finds active subclasses."""
        ConcreteRegistry.clear_registry()
        BaseIntegrationModel.clear_registry()

        registries = RegistryManager._discover_registries()
        registry_names = {registry_class.__name__ for registry_class in registries}
        assert "ConcreteRegistry" in registry_names
        assert "BaseIntegrationModel" in registry_names

    @pytest.mark.regression
    def test_discover_registries_with_auto_discovery(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify discover_registries routine handles auto_packages.

        Also checks auto_populate routine.
        """
        ConcreteRegistry.clear_registry()
        BaseIntegrationModel.clear_registry()

        monkeypatch.setattr(ConcreteRegistry, "registry_auto_discovery", True)
        monkeypatch.setattr(
            ConcreteRegistry, "auto_package", "tests.python.integration"
        )
        get_settings().auto_packages = ["tests.python.integration"]

        registries = RegistryManager._discover_registries()
        registry_names = {registry_class.__name__ for registry_class in registries}
        assert "ConcreteRegistry" in registry_names


class TestCLIEntrypoint:
    """Integration test suite for the CLI entrypoint list command."""

    @pytest.fixture(autouse=True)
    def clean_registries_fixture(self) -> Generator[None, None, None]:
        """Ensure clean registries and settings around CLI tests."""
        reset_settings()
        ConcreteRegistry.clear_registry()
        BaseIntegrationModel.clear_registry()
        yield
        ConcreteRegistry.clear_registry()
        BaseIntegrationModel.clear_registry()
        reset_settings()

    @pytest.mark.smoke
    def test_list_command_tree(self) -> None:
        """Test invoking list command via Typer CliRunner to check tree output."""
        BaseIntegrationModel.register_decorator(TextIntegrationModel, name="text")
        BaseIntegrationModel.register_decorator(ImageIntegrationModel, name="image")

        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "BaseIntegrationModel (discriminator: msg_type)" in result.stdout
        expected_text = (
            '"text" -> tests.python.integration.test_registry.TextIntegrationModel'
        )
        assert expected_text in result.stdout
        expected_image = (
            '"image" -> tests.python.integration.test_registry.ImageIntegrationModel'
        )
        assert expected_image in result.stdout

    @pytest.mark.smoke
    def test_list_command_json(self) -> None:
        """Test invoking list command with --json flag to check JSON output."""
        BaseIntegrationModel.register_decorator(TextIntegrationModel, name="text")
        BaseIntegrationModel.register_decorator(ImageIntegrationModel, name="image")

        runner = CliRunner()
        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "BaseIntegrationModel" in data
        assert data["BaseIntegrationModel"] == {
            "image": "tests.python.integration.test_registry.ImageIntegrationModel",
            "text": "tests.python.integration.test_registry.TextIntegrationModel",
        }

    @pytest.mark.sanity
    def test_list_command_invalid_arguments(self) -> None:
        """Test invoking list CLI command with invalid flag parameters."""
        runner = CliRunner()
        result = runner.invoke(app, ["list", "--invalid-flag"])
        assert result.exit_code != 0
        # Typer/Click prints option parsing errors to stderr
        assert "No such option" in result.stderr or "Error" in result.stderr

    @pytest.mark.sanity
    def test_list_command_error_handling(self, mocker: MockerFixture) -> None:
        """Test list command error handling when list_registries fails."""
        mocker.patch.object(
            RegistryManager,
            "list_registries",
            side_effect=Exception("Database connection error"),
        )
        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code != 0
        # typer.echo with err=True prints to stderr
        assert "Error querying registries: Database connection error" in result.stderr
