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

"""End-to-end tests for Registry Discovery & Listing (US-7.3)."""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Generator
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.registry import PydanticClassRegistryMixin, RegistryManager
from disdantic.settings import reset_settings


@pytest.fixture(autouse=True)
def isolate_list_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter out other test registry classes from list_registries discovery."""
    orig_get_subclasses = RegistryManager._get_subclasses

    def filtered_subclasses(target_class: type) -> set[type]:
        subs = orig_get_subclasses(target_class)
        return {
            sub
            for sub in subs
            if not sub.__module__.startswith("tests.e2e.")
            or sub.__module__ == "tests.e2e.test_registry_discovery_and_listing"
        }

    monkeypatch.setattr(RegistryManager, "_get_subclasses", filtered_subclasses)


class BaseE2EListModel(PydanticClassRegistryMixin):
    """Base model class used to test registry listing."""

    schema_discriminator = "list_type"
    list_type: str


@BaseE2EListModel.register("text")
class TextListModel(BaseE2EListModel):
    """Subclass representing text list model."""

    list_type: Literal["text"] = "text"
    body: str


@BaseE2EListModel.register("image")
class ImageListModel(BaseE2EListModel):
    """Subclass representing image list model."""

    list_type: Literal["image"] = "image"
    url: str
    width: int


class TestRegistryDiscoveryAndListing:
    """End-to-end test suite for US-7.3: Registry Discovery & Listing."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        BaseE2EListModel.clear_registry()
        BaseE2EListModel.register_decorator(TextListModel, name="text")
        BaseE2EListModel.register_decorator(ImageListModel, name="image")
        yield
        BaseE2EListModel.clear_registry()
        reset_settings()

    @pytest.fixture(params=["text_instance", "image_instance"])
    def valid_instances(self, request: pytest.FixtureRequest) -> BaseE2EListModel:
        """Fixture supplying properly configured model instances."""
        if request.param == "text_instance":
            return TextListModel(body="Listing test text")
        return ImageListModel(url="https://example.com/list.jpg", width=800)

    @pytest.mark.smoke
    def test_contract_and_environment(self) -> None:
        """Validate structural environment contracts and RegistryManager API."""
        assert hasattr(RegistryManager, "list_registries")
        assert inspect.ismethod(RegistryManager.list_registries)
        assert issubclass(BaseE2EListModel, PydanticClassRegistryMixin)
        assert issubclass(BaseE2EListModel, BaseModel)

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: BaseE2EListModel) -> None:
        """Assert correct initial system wiring and startup state."""
        assert isinstance(valid_instances, BaseE2EListModel)
        assert valid_instances.list_type in ("text", "image")

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify explicit system blockages on invalid construction parameters."""
        with pytest.raises(ValidationError):
            ImageListModel(url="https://example.com/list.jpg", width="invalid_width")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify system boundary defense lines when missing required parameters."""
        with pytest.raises(ValidationError):
            TextListModel()  # type: ignore

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: BaseE2EListModel) -> None:
        """Verify model_dump and model_validate serialization boundaries."""
        dumped_data = valid_instances.model_dump()
        assert isinstance(dumped_data, dict)
        assert dumped_data["list_type"] == valid_instances.list_type

        validated_instance = BaseE2EListModel.model_validate(dumped_data)
        assert validated_instance.list_type == valid_instances.list_type

    @pytest.mark.regression
    def test_dynamic_resolution(self) -> None:
        """Verify dynamic registry listing returns expected dictionary format."""
        registries = RegistryManager.list_registries()
        assert isinstance(registries, dict)
        assert "BaseE2EListModel" in registries
        assert registries["BaseE2EListModel"] == {
            "text": "tests.e2e.test_registry_discovery_and_listing.TextListModel",
            "image": "tests.e2e.test_registry_discovery_and_listing.ImageListModel",
        }


class TestCLIEntrypoint:
    """E2E test suite for 'list' CLI subcommand."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Ensure settings and registries are in a clean state."""
        reset_settings()
        BaseE2EListModel.clear_registry()
        BaseE2EListModel.register_decorator(TextListModel, name="text")
        BaseE2EListModel.register_decorator(ImageListModel, name="image")
        yield
        BaseE2EListModel.clear_registry()
        reset_settings()

    @pytest.mark.smoke
    def test_cli_list_help(self) -> None:
        """Verify list subcommand help option prints usage guidance."""
        runner = CliRunner()
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.stdout)
        assert "--json" in clean_stdout
        assert "List active registries" in clean_stdout

    @pytest.mark.smoke
    def test_cli_list_default_workflow(self) -> None:
        """Verify list command displays a structured directory tree of registries."""
        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "BaseE2EListModel (discriminator: list_type)" in result.stdout
        expected_text = (
            '"text" -> tests.e2e.test_registry_discovery_and_listing.TextListModel'
        )
        assert expected_text in result.stdout

    @pytest.mark.sanity
    def test_cli_list_json_workflow(self) -> None:
        """Verify list command --json prints valid dictionary mappings."""
        runner = CliRunner()
        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        list_dict = json.loads(result.stdout)
        assert "BaseE2EListModel" in list_dict
        assert list_dict["BaseE2EListModel"] == {
            "text": "tests.e2e.test_registry_discovery_and_listing.TextListModel",
            "image": "tests.e2e.test_registry_discovery_and_listing.ImageListModel",
        }

    @pytest.mark.regression
    def test_cli_list_query_error(self, mocker: MockerFixture) -> None:
        """Verify list command handles listing failures and exits with code 1."""
        mocker.patch.object(
            RegistryManager,
            "list_registries",
            side_effect=RuntimeError("Simulated listing query database failure"),
        )
        runner = CliRunner()
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 1
        assert "Error querying registries" in result.stderr
