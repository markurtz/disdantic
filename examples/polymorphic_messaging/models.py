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

"""Polymorphic data schemas for the messaging example.

This module defines the message schemas registered in a polymorphic class registry
backed by disdantic's PydanticClassRegistryMixin and ReloadableBaseModel.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from disdantic.model import ReloadableBaseModel
from disdantic.registry import PydanticClassRegistryMixin

__all__ = ["BaseMessage", "ChatSession", "ImageMessage", "TextMessage"]


class BaseMessage(PydanticClassRegistryMixin, ReloadableBaseModel):
    """Polymorphic base message class.

    All messaging subclasses register with this class to enable
    polymorphic validation and lookahead routing.
    """

    schema_discriminator = "model_type"
    model_type: str


class TextMessage(BaseMessage):
    """Simple text message payload containing string content."""

    model_type: Literal["text"] = "text"
    content: str


class ImageMessage(BaseMessage):
    """Image message payload containing a source URL."""

    model_type: Literal["image"] = "image"
    url: str


class ChatSession(ReloadableBaseModel):
    """A collection of polymorphic messages representing a chat session.

    This model dynamically reloads its core schemas when child message schemas
    are modified or newly registered at runtime.
    """

    session_id: str
    messages: list[BaseMessage] = Field(default_factory=list)
