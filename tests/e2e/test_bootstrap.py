"""End-to-end tests for the bootstrap.py script."""

from __future__ import annotations

import asyncio
import shutil
import sys
from functools import wraps
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import bootstrap  # noqa: E402
from scripts.bootstrap import BootstrapConfig, main  # noqa: E402


def async_timeout(delay: float) -> Any:
    """Decorator to timeout asyncio tests."""

    def decorator(func: Any) -> Any:
        @wraps(func)
        async def new_func(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=delay)

        return new_func

    return decorator


@pytest.fixture(autouse=True)
def _mock_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure IS_INTERACTIVE is False for all tests to prevent blocking prompts."""
    monkeypatch.setattr(bootstrap, "IS_INTERACTIVE", False)


def generate_test_cases() -> list[dict[str, Any]]:
    """Generates all test case variations for CLI arguments."""
    cases: list[dict[str, Any]] = []

    # Default state (all defaults)
    cases.append({})

    # String argument cases
    str_args = [
        "organization",
        "repository",
        "project_name",
        "project_desc",
        "env_prefix",
        "docs_url",
        "maintainer",
        "support_email",
        "slack_url",
        "blog_url",
        "release_date",
    ]
    for arg in str_args:
        # Empty string case
        cases.append({arg: ""})
        # Custom value case
        cases.append({arg: f"custom_{arg}"})

    # Boolean argument cases
    bool_args = [
        "disable_github_discussions",
        "disable_github_issues",
        "disable_github_roadmap",
        "disable_pypi",
    ]
    for arg in bool_args:
        cases.append({arg: True})

    return cases


class TestMain:
    """Test suite for the main bootstrap function."""

    @pytest.mark.regression
    @pytest.mark.parametrize("cli_arguments", generate_test_cases())
    def test_invocation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        cli_arguments: dict[str, Any],
    ) -> None:
        """Tests bootstrap script with various arguments, verifying all files."""
        repository_root = Path(__file__).resolve().parent.parent.parent
        target_directory = tmp_path / "repo"

        # Copy repo excluding temp/cache/git directories
        shutil.copytree(
            repository_root,
            target_directory,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                ".tox",
                "__pycache__",
                "node_modules",
                "site",
                "build",
                "dist",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            ),
        )

        class MockPath:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self._path = Path(*args, **kwargs)

            def resolve(self) -> Any:
                class MockResolved:
                    @property
                    def parent(self) -> Any:
                        class MockParent:
                            @property
                            def parent(self) -> Path:
                                return target_directory

                        return MockParent()

                return MockResolved()

            @classmethod
            def cwd(cls) -> Path:
                return target_directory

        monkeypatch.setattr(bootstrap, "Path", MockPath)

        # Merge defaults so the test config is fully populated like the click app would
        base_args = {
            "global_blacklist": bootstrap.main.params[-1].default,
        }
        test_args = {**base_args, **cli_arguments}

        # Determine expected state
        config = BootstrapConfig.create(**test_args)

        # Run script
        main.callback(**test_args)  # type: ignore[misc]

        self._verify_repo_state(target_directory, config)

    def _verify_repo_state(self, target_dir: Path, config: BootstrapConfig) -> None:
        """Thoroughly checks the target directory against the expected state."""
        assert (target_dir / "src" / config.project_name).exists()
        if config.project_name != "template_python":
            assert not (target_dir / "src" / "template_python").exists()

        placeholders = self._build_placeholders(config)

        for file_path in target_dir.rglob("*"):
            self._verify_file(file_path, target_dir, config, placeholders)

    def _build_placeholders(self, config: BootstrapConfig) -> list[str]:
        """Builds the list of placeholders expected to be absent."""
        placeholders = ["{{maintainer_username}}"]
        if config.repository != "template-python":
            placeholders.append("template-python")
        if config.project_name != "template_python":
            placeholders.append("template_python")
        if config.env_prefix != "TEMPLATE_PYTHON":
            placeholders.append("TEMPLATE_PYTHON")
        if config.support_email != "conduct@example.com":
            placeholders.append("conduct@example.com")
        if config.project_desc != (
            "An opinionated, production-ready Apache 2.0 template repository "
            "for bootstrapping modern software projects."
        ):
            placeholders.append(
                "An opinionated, production-ready Apache 2.0 template repository"
            )
        if config.organization != "markurtz" and config.maintainer != "markurtz":
            placeholders.append("markurtz")
        return placeholders

    def _verify_file(
        self,
        file_path: Path,
        target_dir: Path,
        config: BootstrapConfig,
        placeholders: list[str],
    ) -> None:
        """Verifies an individual file for placeholders and specific logic."""
        if not file_path.is_file():
            return

        ignore_dirs = {
            ".git",
            ".venv",
            ".tox",
            "__pycache__",
            "node_modules",
            "site",
            "build",
            "dist",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        }
        if any(part in ignore_dirs for part in file_path.parts):
            return

        # Skip testing scripts since they contain placeholders
        if file_path.name in ("bootstrap.py", "test_bootstrap.py"):
            return

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return

        for ph in placeholders:
            assert ph not in content, f"Placeholder '{ph}' found in {file_path}"

        self._verify_file_specific_content(file_path, target_dir, config, content)

    def _verify_file_specific_content(
        self, file_path: Path, target_dir: Path, config: BootstrapConfig, content: str
    ) -> None:
        """Verifies specific configuration changes in specific files."""
        if file_path.name == "README.md" and file_path.parent == target_dir:
            if config.docs_url:
                assert config.docs_url in content

            if config.disable_github_discussions:
                assert "<!--" in content
                assert "Discussions</a>" in content
            else:
                assert "Discussions</a>" in content

        if file_path.name == "pyproject.toml":
            assert config.project_name in content
            assert config.project_desc in content
            if config.docs_url:
                assert config.docs_url in content
            if config.disable_github_issues:
                assert "# Issues =" in content or "Issues =" not in content

        if file_path.name == "CODEOWNERS":
            assert config.maintainer in content
