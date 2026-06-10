# Testing Guide

This directory contains the testing suite for `template-python`. We use `pytest` as our testing framework and `hatch` to manage test environments and execution.

## Test Tiers

Tests are categorized into three distinct tiers, each located in its respective subdirectory:

| Test Tier       | Directory            | Description                                                                                                               |
| :-------------- | :------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| **Unit**        | `tests/unit/`        | Fast, isolated tests for individual functions and classes. These tests should not rely on external services or databases. |
| **Integration** | `tests/integration/` | Slower tests that verify interactions between multiple components or modules within the application.                      |
| **End-to-End**  | `tests/e2e/`         | Full-stack tests simulating real user workflows, from entry points to expected outcomes.                                  |

## Pytest Markers

We use custom `pytest` markers to categorize test scope and intent. Every test should be decorated with appropriate markers.

| Marker                    | Purpose                                                               | Example Use Case                                                                                    |
| :------------------------ | :-------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------- |
| `@pytest.mark.smoke`      | Quick tests to check basic functionality.                             | A crucial happy-path test that must pass for the system to be considered fundamentally operational. |
| `@pytest.mark.sanity`     | Detailed tests to ensure major functions work correctly.              | Testing key business logic and typical user flows.                                                  |
| `@pytest.mark.regression` | Tests to ensure that new changes do not break existing functionality. | Tests written specifically to prevent known bugs from reoccurring.                                  |

> [!NOTE]
> Every test should be decorated with one of the above markers to indicate its role in the testing pipeline.

## Running Tests

We recommend using `hatch` to run tests, as it automatically manages the required virtual environments and dependencies.

### Standard Test Runs

```bash
# Run all tests
hatch run test:all

# Run only unit tests
hatch run test:unit

# Run tests with a specific marker
hatch run test:all -m "smoke"

# Run tests in a specific file
hatch run test:all tests/unit/test_version.py
```

### Coverage Reports

To generate coverage reports, use the `-cov` suffixed commands. These will output both a terminal report and an HTML report located in `docs/coverage/`.

```bash
# Run all tests with coverage
hatch run test:all-cov

# Run only unit tests with coverage
hatch run test:unit-cov
```

## Adding New Tests

When creating new tests, ensure they are placed in the appropriate tier directory (`unit/`, `integration/`, or `e2e/`) and include the necessary markers.

### Example Unit Test

```python
"""Unit tests for my_module."""

from __future__ import annotations

import pytest

from template_python import my_module


@pytest.mark.smoke
def test_my_function() -> None:
    """Verify my_function behaves as expected."""
    result = my_module.my_function()
    assert result is True
```

> [!TIP]
> **Type Hints:** Ensure all test functions are fully type-hinted (e.g., `-> None:` for test return types) to satisfy our strict `mypy` configuration.
