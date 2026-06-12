# Lazy Loading & Introspection Example

## Overview

This example demonstrates how to implement thread-safe lazy-loaded proxies (`LazyProxy`), singleton pattern double-checked locking (`SingletonMeta`), and recursive circular-reference-safe runtime self-introspection (`InfoMixin`) in your applications using `disdantic`. It showcases how to optimize resource consumption via deferred loading while maintaining high-performance thread safety and robust object visualization capabilities.

## Prerequisites & Setup

1. Initialize the Hatch virtual environment and dependencies inside the root workspace:
   ```bash
   hatch env create
   ```
1. Verify that `disdantic` is installed in your python environment.

## Execution Blueprint

To execute this example, run the following command from the root of the repository:

```bash
hatch run python examples/lazy_loading_and_introspection/main.py
```

## Expected Results

When executed, the script should produce output similar to the following:

```text
2026-06-12 12:32:43.672 | INFO     | __main__:__init__:39 - Initializing heavy database connection manager...
Double-checked locking successful! Total manager instances created: 1
Proxy successfully resolved connected status: [True, True, True, True, True]
Alice's Introspection Dict:
Name: Alice
Peer: {'str': '<DeveloperNode object at 0x1073174d0>', 'type': 'DeveloperNode', 'module': '__main__', 'attributes': {'name': 'Bob', 'peer': '<CircularReference: ID 4415742912>'}}

Serialized JSON string:
{
  "str": "<DeveloperNode object at 0x10732e3c0>",
  "type": "DeveloperNode",
  "module": "__main__",
  "attributes": {
    "name": "Alice",
    "peer": {
      "str": "<DeveloperNode object at 0x1073174d0>",
      "type": "DeveloperNode",
      "module": "__main__",
      "attributes": {
        "name": "Bob",
        "peer": "<CircularReference: ID 4415742912>"
      }
    }
  }
}
```

## Troubleshooting

- **Import Errors:** If you encounter `ImportError: No module named disdantic`, ensure you are executing the script using `hatch run python` or from an activated virtual environment where the core package is installed.
- **Lock Contention:** If you simulate extremely high levels of thread concurrency and notice latency, check if your factories are performing long block operations inside the thread-safe locks. Ensure resource initialization tasks are lightweight or properly partitioned.
