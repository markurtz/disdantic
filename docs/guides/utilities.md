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

# System & Integration Utilities

This guide details the `disdantic` helper utilities, including runtime self-introspection, lazy loading proxies, thread-safe singletons, structured logging with OpenTelemetry, and settings configurations.

## 1. Runtime Self-Introspection & Serialization

The `InfoMixin` class provides recursive object self-introspection, converting arbitrary object graphs into primitive types safely.

### Object Serialization

Inheriting from `InfoMixin` exposes the `.info` property, which generates a sanitized dictionary mapping, along with JSON and YAML exporters:

```python
from disdantic import InfoMixin

class Resource(InfoMixin):
    def __init__(self, name: str):
        self.name = name

res = Resource("Database")
print(res.info)       # Sanitized dictionary representation
print(res.info_json(indent=2)) # JSON string representation
print(res.info_yaml()) # YAML string (raises ImportError if PyYAML is not installed)
```

### Circular Reference Safety

To prevent infinite loops during traversal, `InfoMixin` tracks visited memory addresses. If a cycle is detected, the traversal halts and logs a `<CircularReference: ID <id>>` placeholder:

```python
from disdantic import InfoMixin

class Resource(InfoMixin):
    def __init__(self, name: str):
        self.name = name

res = Resource("Database")
res.self_reference = res  # Establish cycle
assert "CircularReference" in res.info_json()
```

## 2. Thread-Safe Lazy Loading & Proxying

`disdantic` defers imports or expensive instantiation paths until object attributes are read.

### LazyProxy

`LazyProxy` acts as a placeholder, only calling the initialization factory function when attributes, string representation (`__repr__`), or directory listings (`__dir__`) are requested. Resolution is fully thread-safe:

```python
import types
from disdantic.loading import LazyProxy

def expensive_factory():
    return types.SimpleNamespace(status="ok")

proxy = LazyProxy(expensive_factory)
# Factory is NOT called yet
print(proxy.status)  # Triggers thread-safe resolution and prints: ok
```

### LazyLoader Class Attributes Descriptor

Use `@LazyLoader.class_attributes` to bind lazy properties to class variables:

```python
from disdantic.loading import LazyLoader

@LazyLoader.class_attributes({"sys_mod": "sys"})
class Controller:
    pass

ctrl = Controller()
# 'sys' is only imported when sys_mod is accessed
print(ctrl.sys_mod.version)
```

## 3. Thread-Safe Singleton Lifecycle Management

`SingletonMeta` is a thread-safe singleton metaclass using double-checked locking to enforce single-instance lifecycle constraints.

### Metaclass Instantiation

Classes using `SingletonMeta` share a single instance across all constructor invocations:

```python
from disdantic.singleton import SingletonMeta

class ConfigService(metaclass=SingletonMeta):
    pass

c1 = ConfigService()
c2 = ConfigService()
assert c1 is c2
```

### Instance Eviction & Cleaning

For test isolation, you can evict singleton instances programmatically:

```python
from disdantic.singleton import SingletonMeta

class ConfigService(metaclass=SingletonMeta):
    pass

c1 = ConfigService()

# Evict instance of a specific singleton class
ConfigService.clear_instances()

# Evict all active singletons globally
SingletonMeta.clear_all_singletons()
```

## 4. Structured Logging & Telemetry Instrumentation

Configure global logging and automatically track function execution paths.

### Function Autologging

Decorate functions with `@autolog` to log inputs on entry, results on exit, and exceptions before re-raising:

```python
from disdantic.logging import autolog

@autolog
def divide(a: int, b: int) -> float:
    return a / b

# Optionally configure exception log level
@autolog(exception_log_level="WARNING")
def risky_calculation(x: int) -> int:
    return x * 10
```

### OpenTelemetry JSON Logging

When logging under an active OpenTelemetry span, `disdantic` formats log statements as structured JSON with tracing metadata:

```python
from disdantic.logging import configure_logger, LoggingSettings

configure_logger(
    LoggingSettings(
        enabled=True,
        otel_formatting="enable"  # Enable OTEL-compliant JSON logging
    )
)
```

## 5. Unified Global Configuration Hierarchy

`disdantic` loads and validates configurations dynamically using Pydantic Settings.

### Precedence Priority

Settings resolve variables across the following priority ladder:

1. **Constructor arguments** (e.g. `Settings(environment="production")`)
1. **Environment variables** prefixed with `DISDANTIC__` (e.g. `DISDANTIC__ENVIRONMENT="staging"`)
1. **Dotenv files** (`.env`)
1. **`pyproject.toml`** config table (under `[tool.disdantic]`)
1. **CLI arguments** (prefixed with `disdantic_`)
1. **Defaults** declared in the settings schema

### Settings Singleton Manager

Manage settings globally using double-checked thread-safe loaders:

```python
from disdantic.settings import get_settings, reset_settings

# Retrieve global settings instance
settings = get_settings()

# Wipe active instance and force configuration reload
reset_settings()
```
