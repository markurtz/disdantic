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

"""End-to-end tests for US-5.3: YAML Fallback Emitter."""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from disdantic.introspection import InfoMixin


class SimpleConfig(InfoMixin):
    """Simple configuration class for YAML testing."""

    def __init__(self) -> None:
        self.active = True
        self.tags = ["production", "kubernetes"]
        self.empty_list: list[str] = []
        self.empty_dict: dict[str, str] = {}
        self.nested_dict = {"key": "value"}


class ConfigModel(BaseModel, InfoMixin):
    """Pydantic model config for E2E validation."""

    environment: str
    debug: bool = False


class TestYamlFallbackEmitter:
    """E2E test suite for US-5.3: YAML Fallback Emitter."""

    @pytest.fixture(params=["simple_config", "config_model"])
    def valid_instances(self, request: pytest.FixtureRequest) -> InfoMixin:
        """Supply isolated valid execution contexts/personas."""
        if request.param == "simple_config":
            return SimpleConfig()
        return ConfigModel(environment="production", debug=True)

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(InfoMixin, object)
        assert hasattr(InfoMixin, "info_yaml")

        # Verify signature of info_yaml contains indent and sort_keys
        signature_obj = inspect.signature(InfoMixin.info_yaml)
        assert "indent" in signature_obj.parameters
        assert "sort_keys" in signature_obj.parameters

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: InfoMixin) -> None:
        """Assert correct initial system wiring and persona mapping."""
        assert isinstance(valid_instances, InfoMixin)
        if isinstance(valid_instances, SimpleConfig):
            assert valid_instances.active is True
            assert valid_instances.tags == ["production", "kubernetes"]
        elif isinstance(valid_instances, ConfigModel):
            assert valid_instances.environment == "production"
            assert valid_instances.debug is True

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass bad environment parameters to verify system blockages."""
        with pytest.raises(ValidationError):
            ConfigModel(environment="production", debug="not_a_bool")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit critical configurations to verify system boundary defense lines."""
        with pytest.raises(ValidationError):
            ConfigModel(debug=True)  # type: ignore

    @pytest.mark.smoke
    def test_yaml_delegation_when_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify info_yaml() delegates to PyYAML if available."""
        mock_dump_called = False
        mock_dump_data = None

        class MockYaml:
            def dump(self, data: Any, **kwargs: Any) -> str:
                nonlocal mock_dump_called, mock_dump_data
                mock_dump_called = True
                mock_dump_data = data
                return "mocked yaml output"

        monkeypatch.setattr("disdantic.introspection.yaml", MockYaml())

        config = SimpleConfig()
        result = config.info_yaml()
        assert mock_dump_called is True
        assert result == "mocked yaml output"

    @pytest.mark.smoke
    def test_yaml_fallback_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify info_yaml() falls back to custom pure-Python emitter.

        This is triggered when PyYAML is missing.
        """
        monkeypatch.setattr("disdantic.introspection.yaml", None)

        config = SimpleConfig()
        yaml_out = config.info_yaml(sort_keys=True)
        assert "active: true" in yaml_out
        assert '- "production"' in yaml_out or "- production" in yaml_out

    @pytest.mark.regression
    def test_yaml_fallback_formatting_edge_cases(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify fallback formatter correctly handles empty dicts, lists.

        It should also correctly handle special characters.
        """
        monkeypatch.setattr("disdantic.introspection.yaml", None)

        class EdgeCaseObj(InfoMixin):
            def __init__(self) -> None:
                self.empty_dict: dict[str, Any] = {}
                self.empty_list: list[Any] = []
                self.special_key = "value"
                self.special_dict = {
                    "key:with_colon": "value",
                    "key with space": "value",
                }

        obj = EdgeCaseObj()
        yaml_out = obj.info_yaml(sort_keys=True)
        assert "empty_dict: {}" in yaml_out
        assert "empty_list: []" in yaml_out
        assert '"key:with_colon": "value"' in yaml_out
        assert '"key with space": "value"' in yaml_out

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: InfoMixin) -> None:
        """Verify marshalling of data models descending from Pydantic base class."""
        if isinstance(valid_instances, ConfigModel):
            dumped_dict = valid_instances.model_dump()
            assert dumped_dict["environment"] == "production"
            assert dumped_dict["debug"] is True

            validated_instance = ConfigModel.model_validate(dumped_dict)
            assert isinstance(validated_instance, ConfigModel)
            assert validated_instance.environment == "production"
            assert validated_instance.debug is True
