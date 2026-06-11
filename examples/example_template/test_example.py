"""
Test suite for the example template.
"""

from __future__ import annotations

from examples.example_template.main import main


def test_example_runs() -> None:
    """
    Ensure that the example's main function executes without raising errors.
    """
    # Simply run the main function to verify it works
    main()
