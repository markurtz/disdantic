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

"""End-to-end tests for US-5.2: Introspection Safe Boundaries."""

from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel, ValidationError

from disdantic.introspection import InfoMixin


class CyclicNode(InfoMixin):
    """A node class that can form circular reference loops."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.neighbor: CyclicNode | None = None

    @property
    def error_property(self) -> str:
        """Simulated property that raises an extraction error."""
        raise ValueError("Simulated DB connection timeout")


class CyclicConfig(BaseModel, InfoMixin):
    """Pydantic model containing cyclic structures and errors."""

    name: str
    value: int

    @property
    def bad_property(self) -> str:
        """Simulated bad property that raises an error."""
        raise RuntimeError("Pydantic extraction error")


class TestSafeIntrospectionWithErrorAndCircularReferenceBoundaries:
    """E2E test suite for US-5.2.

    Validates safe introspection under cyclic topologies and errors.
    """

    @pytest.fixture(params=["simple_node", "simple_config"])
    def valid_instances(self, request: pytest.FixtureRequest) -> InfoMixin:
        """Supply isolated valid execution contexts/personas."""
        if request.param == "simple_node":
            return CyclicNode("SingleNode")
        return CyclicConfig(name="SingleConfig", value=42)

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(InfoMixin, object)
        assert hasattr(InfoMixin, "info")
        assert hasattr(InfoMixin, "extract_from_obj")

        # Verify signature of extract_from_obj contains visited parameter
        signature_obj = inspect.signature(InfoMixin.extract_from_obj)
        assert "visited" in signature_obj.parameters

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: InfoMixin) -> None:
        """Assert correct initial system wiring and persona mapping."""
        assert isinstance(valid_instances, InfoMixin)
        if isinstance(valid_instances, CyclicNode):
            assert valid_instances.name == "SingleNode"
            assert valid_instances.neighbor is None
        elif isinstance(valid_instances, CyclicConfig):
            assert valid_instances.name == "SingleConfig"
            assert valid_instances.value == 42

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Pass bad environment parameters to verify system blockages."""
        with pytest.raises(ValidationError):
            CyclicConfig(name="SingleConfig", value="not_an_integer")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Omit critical configurations to verify system boundary defense lines."""
        with pytest.raises(ValidationError):
            CyclicConfig(name="SingleConfig")  # type: ignore

    @pytest.mark.smoke
    def test_circular_reference(self) -> None:
        """Verify cycle detection outputs circular reference messages.

        It should output this instead of raising a RecursionError.
        """
        node_a = CyclicNode("Node A")
        node_b = CyclicNode("Node B")

        # Construct loop
        node_a.neighbor = node_b
        node_b.neighbor = node_a

        info_dict = node_a.info
        neighbor_info = info_dict["attributes"]["neighbor"]
        loopback_info = neighbor_info["attributes"]["neighbor"]

        assert "CircularReference" in str(loopback_info)

    @pytest.mark.sanity
    def test_extraction_error(self, valid_instances: InfoMixin) -> None:
        """Verify property evaluation failure is caught and replaced.

        The value should be replaced by an extraction error message.
        """
        info_dict = valid_instances.info
        if isinstance(valid_instances, CyclicNode):
            err_value = info_dict["attributes"]["error_property"]
            assert "Extraction Error" in err_value
            assert "ValueError" in err_value
        elif isinstance(valid_instances, CyclicConfig):
            err_value = info_dict["attributes"]["bad_property"]
            assert "Extraction Error" in err_value
            assert "RuntimeError" in err_value

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: InfoMixin) -> None:
        """Verify marshalling of data models descending from Pydantic base class."""
        if isinstance(valid_instances, CyclicConfig):
            dumped_dict = valid_instances.model_dump()
            assert dumped_dict["name"] == "SingleConfig"
            assert dumped_dict["value"] == 42

            validated_instance = CyclicConfig.model_validate(dumped_dict)
            assert isinstance(validated_instance, CyclicConfig)
            assert validated_instance.name == "SingleConfig"
            assert validated_instance.value == 42
