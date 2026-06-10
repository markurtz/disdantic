# noqa: INP001
"""
Generate the code reference pages and navigation.

This module automates the creation of API reference documentation. It leverages the
``mkdocs-gen-files`` plugin to traverse the ``src/`` directory, generating Markdown
pages for each Python module and constructing a unified navigation structure. This
ensures the project's codebase remains fully documented and accessible.
"""

from pathlib import Path

import mkdocs_gen_files

__all__ = ["generate_api_reference"]


def generate_api_reference() -> None:
    """
    Generate the API reference documentation and navigation structure.

    Iterates through all Python source files in the ``src/`` directory, converting
    their paths into a logical documentation structure. It generates Markdown files
    with appropriate directives to render the API, and produces a literate navigation
    summary.

    Example:
        This function is executed directly when the script is run:

        .. code-block:: python

            generate_api_reference()

    :return: None
    """
    navigation = mkdocs_gen_files.Nav()
    root_directory = Path(__file__).parent.parent.parent
    source_directory = root_directory / "src"
    api_reference_path = Path("reference/api")

    for python_file in sorted(source_directory.rglob("*.py")):
        module_path = python_file.relative_to(source_directory).with_suffix("")
        document_path = python_file.relative_to(source_directory).with_suffix(".md")
        full_document_path = api_reference_path / document_path

        path_parts = tuple(module_path.parts)

        if path_parts[-1] == "__init__":
            path_parts = path_parts[:-1]
            document_path = document_path.with_name("index.md")
            full_document_path = full_document_path.with_name("index.md")
        elif path_parts[-1] == "__main__":
            continue

        if not path_parts:
            continue

        navigation[path_parts] = document_path.as_posix()

        with mkdocs_gen_files.open(full_document_path, "w") as document_file:
            identifier = ".".join(path_parts)
            document_file.write(
                f"::: {identifier}\n"
                "    options:\n"
                "      show_root_heading: true\n"
                "      show_source: true\n"
            )

        mkdocs_gen_files.set_edit_path(full_document_path, python_file)

    summary_file_path = api_reference_path / "SUMMARY.md"
    with mkdocs_gen_files.open(summary_file_path, "w") as navigation_file:
        navigation_file.writelines(navigation.build_literate_nav())


generate_api_reference()
