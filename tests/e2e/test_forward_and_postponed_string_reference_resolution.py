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

"""End-to-end tests for US-3.2: Forward & Postponed String Reference Resolution."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from disdantic.model import ReloadableBaseModel
from disdantic.settings import reset_settings


class Node(ReloadableBaseModel):
    """Recursive node model referencing itself using string annotations."""

    name: str
    parent: Node | None = None
    children: list[Node] = []


class PostponedChild(ReloadableBaseModel):
    """Child model to test postponed propagation."""

    value: str


class PostponedParent(ReloadableBaseModel):
    """Parent model referencing PostponedChild via string annotation."""

    child: PostponedChild


class TestForwardAndPostponedStringReferenceResolution:
    """End-to-end validation suite for forward and postponed string resolution."""

    @pytest.fixture(autouse=True)
    def clean_test_environment(self) -> Generator[None, None, None]:
        """Ensure a pristine environment state before and after each test."""
        reset_settings()
        yield
        reset_settings()

    @pytest.fixture(
        params=[
            {"name": "root_node", "parent": None, "children": []},
            {
                "name": "child_node",
                "parent": {"name": "root_node"},
                "children": [],
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> Node:
        """Fixture providing configured, valid instances of parent models."""
        return Node.model_validate(request.param)

    @pytest.mark.smoke
    def test_contract(self) -> None:
        """Validate structural environment contracts and class structures."""
        assert issubclass(Node, ReloadableBaseModel)
        assert issubclass(PostponedChild, ReloadableBaseModel)
        assert issubclass(PostponedParent, ReloadableBaseModel)
        assert hasattr(ReloadableBaseModel, "_uses_type")

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: Node) -> None:
        """Verify proper instance initialization and state mapping."""
        assert isinstance(valid_instances, Node)
        assert isinstance(valid_instances.name, str)
        if valid_instances.parent is not None:
            assert isinstance(valid_instances.parent, Node)
            assert valid_instances.parent.name == "root_node"

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify initialization with invalid values raises ValidationError."""
        with pytest.raises(ValidationError):
            # Passing invalid type for parent
            Node(name="node", parent="not-a-node")  # type: ignore

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization with missing required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            Node(parent=None)  # type: ignore # Missing required 'name' field

    @pytest.mark.regression
    def test_marshalling(self, valid_instances: Node) -> None:
        """Verify serialization and validation boundaries against context."""
        dumped_data = valid_instances.model_dump()
        recreated = Node.model_validate(dumped_data)
        assert recreated == valid_instances

    @pytest.mark.smoke
    def test_string_reference_resolution_uses_type(self) -> None:
        """Verify that the internal _uses_type check resolves string
        class annotations.
        """
        # Check string reference to self on parent field
        assert Node._uses_type(Node, Node.model_fields["parent"].annotation)
        # Check string reference to self wrapped in list generic on children field
        assert Node._uses_type(Node, Node.model_fields["children"].annotation)

    @pytest.mark.sanity
    def test_cascade_with_postponed_annotations(self, mocker: MockerFixture) -> None:
        """Verify parent is rebuilt when child is reloaded via postponed
        string annotations.
        """
        rebuild_mock = mocker.patch.object(
            PostponedParent,
            "model_rebuild",
            wraps=PostponedParent.model_rebuild,
        )

        # Triggers schema rebuilding for PostponedChild, which propagates
        # to PostponedParent referencing it by string annotation.
        PostponedChild.reload_schema(parents=True)

        rebuild_mock.assert_called_once_with(force=True)
