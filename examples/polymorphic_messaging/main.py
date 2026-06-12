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

"""Entrypoint execution script for the polymorphic messaging example.

This script registers message subclasses and performs lookahead deserialization
routing and dynamic cascading schema rebuilding checks.
"""

from __future__ import annotations

from typing import Literal

from disdantic.logging import LoggingSettings, configure_logger, logger
from examples.polymorphic_messaging.models import (
    BaseMessage,
    ChatSession,
    ImageMessage,
    TextMessage,
)

__all__ = ["main"]


def main() -> None:
    """Execute the polymorphic messaging validation scenarios."""
    # Initialize logger configuration
    logging_config = LoggingSettings(
        enabled=True,
        level="INFO",
        clear_loggers=True,
        otel_formatting="disable",
        filter=None,
    )
    configure_logger(logging_config)

    # Register core models
    BaseMessage.register("text")(TextMessage)
    BaseMessage.register("image")(ImageMessage)

    # 1. Verify Lookahead Deserialization (US-02)
    payloads = [
        {"model_type": "TEXT", "content": "Hello World!"},
        {"model_type": "image", "url": "https://placehold.co/150.png"},
    ]

    for payload in payloads:
        msg = BaseMessage.model_validate(payload)
        logger.info(
            f"Successfully validated message type: "
            f"{type(msg).__name__} (type={msg.model_type})"
        )

    # 2. Verify Nested Schema & Rebuilding (US-03)
    # Define a new dynamic class after ChatSession has compiled its core schema
    @BaseMessage.register("video")
    class VideoMessage(BaseMessage):
        """Dynamic video message payload."""

        model_type: Literal["video"] = "video"
        duration: int

    # Trigger rebuilding of schemas down the chain
    VideoMessage.reload_schema()

    # ChatSession should now accept the new video message schema
    session_payload = {
        "session_id": "session-123",
        "messages": [
            {"model_type": "text", "content": "Watch this video:"},
            {"model_type": "video", "duration": 42},
        ],
    }

    session = ChatSession.model_validate(session_payload)
    logger.success(
        f"ChatSession successfully validated containing "
        f"{len(session.messages)} polymorphic messages!"
    )


if __name__ == "__main__":
    main()
