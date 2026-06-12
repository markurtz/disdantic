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

# Subclass Registries & Schema Rebuilding

This guide covers how to design and manage polymorphic model registries, prevent namespace collisions, configure case-insensitive tagged union schemas, handle validation errors, execute schema rebuilding cascades, and enable recursive package auto-discovery.

## 1. Registry Management

`disdantic` provides isolated registry namespaces to prevent class registration collisions between unrelated domains.

### Standard vs. Pydantic Registries

- **`RegistryMixin`**: Extends standard Python classes or objects.
- **`PydanticClassRegistryMixin`**: Extends Pydantic models to enable dynamic polymorphic JSON deserialization.

### Class Decoration and Custom Keys

Decorating a class registers it using its class name or explicit custom keys:

```python
from disdantic import RegistryMixin

class ProcessorRegistry(RegistryMixin[type]):
    pass

# Registers under the default key "DefaultProcessor"
@ProcessorRegistry.register()
class DefaultProcessor:
    pass

# Registers under a custom key or sequence of keys
@ProcessorRegistry.register("email_sender")
@ProcessorRegistry.register(["mail", "smtp"])
class EmailProcessor:
    pass
```

### Unregistration and Collision Prevention

Registries protect against accidental key overwrites by raising a `RegistryCollisionError` when multiple subclasses attempt to register under the same name. Registries can be cleaned up using `unregister()` or `clear_registry()`:

```python
from disdantic import RegistryMixin
from disdantic.exceptions import RegistryCollisionError

class ProcessorRegistry(RegistryMixin[type]):
    pass

@ProcessorRegistry.register("email_sender")
class EmailProcessor:
    pass

# Prevention of collisions
try:
    @ProcessorRegistry.register("email_sender")
    class AnotherEmailProcessor:
        pass
except RegistryCollisionError as error:
    print(f"Collision prevented: {error}")

# Unregistering a tag
ProcessorRegistry.unregister("email_sender")

# Attempting to unregister a non-existent tag raises ValueError
try:
    ProcessorRegistry.unregister("email_sender")
except ValueError:
    pass

# Purge all registrations and reset registry state
ProcessorRegistry.clear_registry()
```

## 2. Polymorphic Tagged Unions

`PydanticClassRegistryMixin` dynamically maps registered subclasses into Pydantic tagged union schemas.

### Customizing the Discriminator Key

Set the `schema_discriminator` class variable on the base registry class to determine the key used in JSON payloads:

```python
from disdantic import PydanticClassRegistryMixin

class Message(PydanticClassRegistryMixin):
    schema_discriminator = "msg_type"  # Custom tag key in payload
    msg_type: str
```

### Lookahead Case-Insensitive Validation

By default, payload tag resolution is case-insensitive. If a lowercase or uppercase value matches a registered key, the validator transforms the tag value to the canonical registered casing before running validation:

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

# Validates correctly even though 'TEXT' is in uppercase
message = Message.model_validate({"msg_type": "TEXT", "content": "hello"})
assert isinstance(message, TextMessage)
```

### Missing or Unregistered Discriminator Handling

If a payload has a missing or unregistered discriminator, validation fails, raising a `ValidationError` wrapping a `DiscriminatorNotFoundError` that specifies the rejected key and lists the valid options:

```python
from typing import Literal
from pydantic import ValidationError
from disdantic import PydanticClassRegistryMixin
from disdantic.exceptions import DiscriminatorNotFoundError

class Message(PydanticClassRegistryMixin):
    schema_discriminator = "msg_type"
    msg_type: str

@Message.register("text")
class TextMessage(Message):
    msg_type: Literal["text"] = "text"
    content: str

try:
    Message.model_validate({"msg_type": "video", "url": "/media"})
except ValidationError as error:
    # Under the hood, error wraps a DiscriminatorNotFoundError
    print(error)
```

## 3. Schema Rebuilding Cascades

When new subclasses are registered at runtime, dependent parent schemas referencing the registry base class must rebuild to recognize the new types.

### `ReloadableBaseModel` and Cascading Rebuilds

`PydanticClassRegistryMixin` inherits from `ReloadableBaseModel`, which tracks model references and subclass trees. Rebuilding a child schema automatically traverses the dependency graph using Kahn's topological sorting algorithm and rebuilds all parent models:

```python
from disdantic import ReloadableBaseModel
from pydantic import BaseModel

class ChildModel(ReloadableBaseModel):
    name: str

class ParentModel(ReloadableBaseModel):
    child: ChildModel

# Rebuilds ChildModel and cascades up to rebuild ParentModel schema
ChildModel.reload_schema()
```

### String-Postponed Annotations and Union Traversal

The cascading schema resolver evaluates string-postponed annotations (e.g. `"ChildModel"`) and wraps within nested unions like `Optional[ChildModel]`. It traverses these references using the internal `_uses_type` utility to guarantee schema alignment:

```python
from disdantic import ReloadableBaseModel

class ChildModel(ReloadableBaseModel):
    name: str

class PostponedParent(ReloadableBaseModel):
    child: ChildModel | None  # Evaluated and reloaded automatically

ChildModel.reload_schema()
```

### Rebuild Controls

Configure schema rebuilding via global [Settings](../reference/python_api/settings.md):

- `enable_schema_rebuilding` (default: `True`): Controls whether schema rebuilding is allowed.
- `schema_rebuild_parents` (default: `True`): Determines if updates cascade up dependent trees.

## 4. Recursive Auto-Discovery & Importing

To avoid writing verbose manual import statements for every subclass module, registries can scan and import modules dynamically using `AutoImporterMixin`.

### Package Auto-Discovery

Set `auto_package` on your registry class. When `auto_import_package_modules()` is called, `disdantic` walks the package directory recursively, importing submodules and triggering subclass decorator registrations:

```python
from disdantic import PydanticClassRegistryMixin

class AppRegistry(PydanticClassRegistryMixin):
    auto_package = "myapp.models"
    auto_ignore_modules = ["myapp.models.experimental"]

# Walk and load all submodules in myapp/models/
AppRegistry.auto_import_package_modules()
```

### Module Cache Wiping for Test Isolation

Dynamic module imports cache themselves in `sys.modules`. In test suites where you need clean isolation between test runs, wipe the importer cache:

```python
from disdantic import PydanticClassRegistryMixin

class AppRegistry(PydanticClassRegistryMixin):
    auto_package = "myapp.models"

# Unloads dynamically imported modules from sys.modules
AppRegistry.reset_importer_cache()
```

### Missing Packages Configuration Error

If `auto_import_package_modules()` is invoked on a registry without an `auto_package` variable declared and no global `auto_packages` settings are configured, a `MissingPackagesError` is raised:

```python
from disdantic import PydanticClassRegistryMixin
from disdantic.exceptions import MissingPackagesError

class MisconfiguredRegistry(PydanticClassRegistryMixin):
    pass

try:
    MisconfiguredRegistry.auto_import_package_modules()
except MissingPackagesError as error:
    print(f"Configuration error: {error}")
```
