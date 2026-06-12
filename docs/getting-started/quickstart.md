# Quick Start

This guide helps you write your first code using `disdantic` in under 5 minutes.

## Prerequisites

Before starting, ensure you have installed `disdantic`:

```bash
pip install disdantic
```

## Step 1 — Define the polymorphic base registry class

Extend `PydanticClassRegistryMixin` to create a registry namespace. This mixin establishes the registry base and sets the serialized tag field name using `schema_discriminator`.

```python
from disdantic import PydanticClassRegistryMixin

# Establish the polymorphic base registry
class Message(PydanticClassRegistryMixin):
    schema_discriminator = "msg_type"  # Field name in JSON payload
    msg_type: str
```

## Step 2 — Register subclass implementations

Use the `@Message.register` decorator to dynamically register subclasses. If no key is provided, the registry defaults to the subclass name.

```python
from typing import Literal
from disdantic import PydanticClassRegistryMixin

class Message(PydanticClassRegistryMixin):
    schema_discriminator = "msg_type"
    msg_type: str

@Message.register("text")
class TextMessage(Message):
    msg_type: Literal["text"] = "text"
    content: str

@Message.register("image")
class ImageMessage(Message):
    msg_type: Literal["image"] = "image"
    url: str
    caption: str | None = None
```

## Step 3 — Define parent models and validate payloads

Define Pydantic parent models that reference the registry base class as a field. `disdantic` automatically detects subclass additions and rebuilds the parent validation schemas. Finally, validate the polymorphic JSON payload using the parent model.

```python
from typing import Literal
from disdantic import PydanticClassRegistryMixin
from pydantic import BaseModel

class Message(PydanticClassRegistryMixin):
    schema_discriminator = "msg_type"
    msg_type: str

@Message.register("text")
class TextMessage(Message):
    msg_type: Literal["text"] = "text"
    content: str

@Message.register("image")
class ImageMessage(Message):
    msg_type: Literal["image"] = "image"
    url: str
    caption: str | None = None

# 3. Parents automatically rebuild to accommodate new subtypes
class ChatRoom(BaseModel):
    room_name: str
    messages: list[Message]  # Polymorphic union field

# 4. Incoming payloads validate dynamically to correct subclass types
payload = {
    "room_name": "General Chat",
    "messages": [
        {"msg_type": "text", "content": "Hello world!"},
        {"msg_type": "image", "url": "https://placehold.co/150.png", "caption": "Logo"}
    ]
}

room = ChatRoom.model_validate(payload)
assert isinstance(room.messages[0], TextMessage)
assert isinstance(room.messages[1], ImageMessage)

# 5. Full marshalling flow (serialization and deserialization)
room_data = room.model_dump()
# msg_type is automatically included in the serialized output!
assert room_data["messages"][0]["msg_type"] == "text"
assert room_data["messages"][1]["msg_type"] == "image"

restored_room = ChatRoom.model_validate(room_data)
assert isinstance(restored_room.messages[0], TextMessage)
assert isinstance(restored_room.messages[1], ImageMessage)
```

______________________________________________________________________

## Local Development & Contributing

If you want to contribute to the `disdantic` codebase, run tests, or build the documentation locally:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/markurtz/disdantic.git
   cd disdantic
   ```
1. **Setup the Environment:**
   We use **[uv](https://docs.astral.sh/uv/)** to manage Python packages and **[Hatch](https://hatch.pypa.io/)** for workflows:
   ```bash
   uv sync --all-groups --all-extras
   ```
1. **Run Quality Checks and Tests:**
   ```bash
   hatch run python:lint
   hatch run python:tests-unit
   ```

For detailed contributor guidelines, see the [Developer Setup Guide](../community/developing.md).
