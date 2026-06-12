# Polymorphic Messaging Example

## Overview

This example demonstrates the usage of `PydanticClassRegistryMixin` and `ReloadableBaseModel` within the `disdantic` library. It showcases how to set up dynamic subclass registration, execute case-insensitive lookahead discriminator routing, and trigger cascading validation schema rebuilding to support runtime polymorphic expansions.

## Prerequisites & Setup

Ensure you have initialized the virtual environment and have `pydantic` installed.

```bash
# Setup the virtual environment and dependencies
.venv/bin/hatch env create
```

## Execution Blueprint

Execute the example using `hatch` run to activate the environment:

```bash
.venv/bin/hatch run python examples/polymorphic_messaging/main.py
```

## Expected Results

You should see the following console log output:

```text
12:32:39 | INFO     | __main__:main - Successfully validated message type: TextMessage (type=text)
12:32:39 | INFO     | __main__:main - Successfully validated message type: ImageMessage (type=image)
12:32:39 | SUCCESS  | __main__:main - ChatSession successfully validated containing 2 polymorphic messages!
```

## Troubleshooting

- **ModuleNotFoundError**: Ensure you run the script using the virtualenv wrapper command `.venv/bin/hatch run python ...` or activate the environment before execution so that the `disdantic` package is correctly resolved.
- **Schema Rebuilding Disabled**: If the schema is not updated at runtime, verify that schema rebuilding is not globally disabled in settings.
