# Testing Guide

This directory contains the testing suite for `disdantic`. We use `pytest` as our testing framework and `hatch` to manage test environments and execution.

## Test Tiers

Tests are categorized into three distinct tiers, each located in its respective subdirectory:

| **Unit** | `tests/python/unit/` | Fast, isolated tests for individual functions and classes. These tests should not rely on external services or systems. |
| **Integration** | `tests/python/integration/` | Slower tests that verify interactions between multiple components or modules within the application. |
| **End-to-End** | `tests/e2e/` | Full-stack tests simulating real user workflows, from entry points to expected outcomes. |

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
# Run all Python tests (global cascade)
hatch run all:tests

# Run all Python tests
hatch run python:tests

# Run only Python unit tests
hatch run python:tests-unit

# Run Python integration tests
hatch run python:tests-int

# Run Python tests with a specific marker
hatch run python:tests -m "smoke"

# Run Python tests in a specific file
hatch run python:tests tests/python/unit/test_version.py

# Run system end-to-end (e2e) tests
hatch run project:tests-e2e
```

### Coverage Reports

To generate coverage reports, use the `-cov` suffixed commands. These will output both a terminal report and an HTML report located in `docs/coverage/`.

```bash
# Run all Python tests with coverage
hatch run python:tests-cov

# Run only Python unit tests with coverage
hatch run python:tests-unit-cov
```

## Adding New Tests

When creating new tests, ensure they are placed in the appropriate tier directory (`python/unit/`, `python/integration/`, or `e2e/`) and include the necessary markers.

### Example Unit Test

<!--phmdoctest-skip-->

```python
"""Unit tests for my_module."""

from __future__ import annotations

import pytest

from disdantic import my_module


@pytest.mark.smoke
def test_my_function() -> None:
    """Verify my_function behaves as expected."""
    result = my_module.my_function()
    assert result is True
```

> [!TIP]
> **Type Hints:** Ensure all test functions are fully type-hinted (e.g., `-> None:` for test return types) to satisfy our strict type-checking configuration.
