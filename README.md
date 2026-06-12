<!--
Copyright 2026 markurtz

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/markurtz/disdantic/main/docs/assets/branding/logo-white.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/markurtz/disdantic/main/docs/assets/branding/logo-black.svg">
    <img alt="disdantic Logo" src="https://raw.githubusercontent.com/markurtz/disdantic/main/docs/assets/branding/logo-black.svg" width="400">
  </picture>
</p>

<p align="center">
  <em>The missing polymorphic engine for Pydantic.</em>
</p>

<p align="center">
  <!-- Package & Release Status -->
  <a href="https://github.com/markurtz/disdantic/releases">
    <img src="https://img.shields.io/github/v/release/markurtz/disdantic?label=Release" alt="GitHub Release">
  </a>
  <a href="https://pypi.org/project/disdantic/">
    <img src="https://img.shields.io/pypi/v/disdantic?label=PyPI" alt="PyPI Release">
  </a>
  <a href="https://pypi.org/project/disdantic/">
    <img src="https://img.shields.io/pypi/pyversions/disdantic?label=Python" alt="Supported Python Versions">
  </a>
  <br/>
  <!-- CI/CD & Build Status -->
  <a href="https://github.com/markurtz/disdantic/actions/workflows/pipeline-main.yml">
    <img src="https://github.com/markurtz/disdantic/actions/workflows/pipeline-main.yml/badge.svg" alt="CI Status">
  </a>
  <br/>
  <!-- Issues & Support -->
  <a href="https://github.com/markurtz/disdantic/issues?q=is%3Aissue+is%3Aopen">
    <img src="https://img.shields.io/github/issues/markurtz/disdantic?label=Issues%20Open" alt="Open Issues">
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License">
  </a>
</p>

<p align="center">
  <a href="https://markurtz.github.io/disdantic/">Documentation</a> |
  <a href="https://github.com/markurtz/disdantic/milestones">Roadmap</a> |
  <a href="https://github.com/markurtz/disdantic/issues">Issues</a> |
  <a href="https://github.com/markurtz/disdantic/discussions">Discussions</a>
</p>

______________________________________________________________________

## Overview

`disdantic` is a lightweight Python toolkit designed to simplify Pydantic subclass registries, dynamic polymorphic unions, and automatic model discovery. By eliminating the manual boilerplate of maintaining union types and tracking child class imports, it allows you to build clean, extensible, and self-updating polymorphic domain models.

### Why Use disdantic?

- **Decoupled Registries:** Fully isolated subclass tracking namespaces prevent collisions between distinct model domains.
- **Dynamic Tagged Unions:** Automatic core schema generation dynamically routes incoming JSON payload validation based on a customizable discriminator key.
- **Topological Schema Rebuilding:** Dynamic subclass registrations trigger cascade schema reloading up the dependent parent MRO trees.
- **Automatic Discovery & Auto-Import:** Traverses folders recursively to discover and import submodules, ensuring subclasses register themselves without manual imports.
- **Robust Object Introspection:** Extracts slots, properties, and attributes into sanitized primitives, handling circular references and lazy loader proxies safely.
- **CLI Diagnostics Suite:** Scans, lists, validates compilation integrity, and exports schemas.

### Comparisons

| Feature                     | Pure Pydantic v2                      | Pydantic + `disdantic`                                |
| :-------------------------- | :------------------------------------ | :---------------------------------------------------- |
| **Union Type Definitions**  | Manual list (e.g., `Union[A, B, C]`)  | Automatic tagged union via registry base class        |
| **New Subclass Adding**     | Modify parent union type and import   | Register via decorator; schema cascades automatically |
| **Dynamic Import Scanning** | Manual `importlib` boilerplate        | Declarative packages scan via `AutoImporterMixin`     |
| **Integrity Auditing**      | Manual script validation              | Programmatic and CLI-based diagnostics                |
| **Schema Generation**       | `model_json_schema()` on static types | Command-line extraction via `disdantic schema`        |

## Quick Start

### Installation

```bash
pip install disdantic
```

For advanced features like YAML serialization, install the optional package extra:

```bash
pip install disdantic[yaml]
```

### Core Usage Example

```python
from typing import Literal
from disdantic import PydanticClassRegistryMixin
from pydantic import BaseModel

# 1. Define a polymorphic base registry class
class Message(PydanticClassRegistryMixin):
    schema_discriminator = "msg_type"  # Custom tag field name
    msg_type: str

# 2. Register subclass implementations dynamically
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
        {"msg_type": "image", "url": "https://example.com/logo.png", "caption": "Logo"}
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

## Component Architecture

- `src/disdantic/`: Library package containing runtime implementations.
  - `registry.py`: Core `RegistryMixin`, `PydanticClassRegistryMixin`, and global `RegistryManager`.
  - `model.py`: Abstract `ReloadableBaseModel` enabling topological cascading rebuilds.
  - `diagnose.py`: Registry integrity check orchestrator and compile validation check.
  - `introspection.py`: Recursively maps complex objects to primitives via `InfoMixin`.
  - `loading.py`: Thread-safe deferred instantiation with `LazyLoader` and `LazyProxy`.
  - `settings.py`: Centralized `Settings` utilizing Pydantic Settings.
- `tests/`: Multi-tiered testing suite (`python/unit/`, `python/integration/`, and `e2e/`).
- `docs/`: Markdown files compiled using Zensical static site generator.
- `examples/`: Self-contained runnable scripts demonstrating configurations.

## Advanced Usage & Documentation

For detailed information on configuration settings, custom handlers, CLI commands, and operational guides, visit the [Documentation Site](https://markurtz.github.io/disdantic/).

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](https://github.com/markurtz/disdantic/blob/main/CONTRIBUTING.md) for guidelines and [DEVELOPING.md](https://github.com/markurtz/disdantic/blob/main/DEVELOPING.md) for development setup instructions.

Ensure you adhere to our [Code of Conduct](https://github.com/markurtz/disdantic/blob/main/CODE_OF_CONDUCT.md) in all community interactions.

## Support & Security

- For help and general questions, see [SUPPORT.md](https://github.com/markurtz/disdantic/blob/main/SUPPORT.md).
- To report a security vulnerability, please refer to our [Security Policy](https://github.com/markurtz/disdantic/blob/main/SECURITY.md).

## License

Licensed under the Apache License 2.0. See the [LICENSE](https://github.com/markurtz/disdantic/blob/main/LICENSE) file for details.

## Citations

If you use this repository or the resulting software in your research, please cite it using the following BibTeX entry:

```bibtex
@software{disdantic,
  author = {markurtz},
  title = {disdantic},
  year = 2026,
  url = {https://github.com/markurtz/disdantic}
}
```
