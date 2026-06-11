"""
Custom Zensical macros for markdown document processing.

This module defines hooks to dynamically modify documentation pages
during Zensical builds, such as conditionally embedding files and
generating links to Rust API reference documentation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

__all__: Annotated[
    list[str],
    "The list of public symbols exported by this module.",
] = [
    "define_env",
]


def define_env(env: Any) -> None:
    """
    Register custom macros in the documentation environment.

    This function hooks into Zensical's build cycle to register dynamic markdown
    macros, enabling conditional file inclusion and API documentation linking.

    Example:
        >>> class MockEnv:
        ...     def macro(self, func): return func
        >>> define_env(MockEnv())

    :param env: The documentation environment instance used to register macros.
    :return: None
    """

    @env.macro
    def include_file_or_placeholder(file_path: str, placeholder: str) -> str:
        target_path = Path(file_path)
        if target_path.exists():
            return target_path.read_text(encoding="utf-8")
        return placeholder
