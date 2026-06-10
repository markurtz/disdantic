"""Unit tests for the bootstrap.py script."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import bootstrap  # noqa: E402
from scripts.bootstrap import (  # noqa: E402
    IS_INTERACTIVE,
    BootstrapConfig,
    ReplacementRule,
    main,
)


@pytest.fixture(autouse=True)
def _mock_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure IS_INTERACTIVE is False for all tests to prevent blocking prompts."""
    monkeypatch.setattr(bootstrap, "IS_INTERACTIVE", False)


class TestIsInteractive:
    """Test suite for the IS_INTERACTIVE parameter."""

    @pytest.mark.sanity
    def test_is_interactive(self) -> None:
        """Validates the type and value of the IS_INTERACTIVE parameter."""
        assert isinstance(IS_INTERACTIVE, bool)


class TestReplacementRule:
    """Test suite for the ReplacementRule class."""

    @pytest.fixture
    def valid_instances(self) -> list[dict[str, Any]]:
        """Provides valid data for creating ReplacementRule instances."""
        return [
            {"search": "foo", "replace": "bar"},
            {
                "search": re.compile(r"foo"),
                "replace": "bar",
                "whitelist_globs": ["*.md"],
            },
            {
                "search": "foo",
                "replace": "bar",
                "blacklist_globs": ["*.txt"],
            },
        ]

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validates the class signature and fields."""
        assert "search" in ReplacementRule.model_fields
        assert "replace" in ReplacementRule.model_fields
        assert "whitelist_globs" in ReplacementRule.model_fields
        assert "blacklist_globs" in ReplacementRule.model_fields

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: list[dict[str, Any]]) -> None:
        """Tests successful initialization of the class."""
        for instance_data in valid_instances:
            rule = ReplacementRule(**instance_data)
            assert rule.search == instance_data["search"]
            assert rule.replace == instance_data["replace"]

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Tests initialization with invalid values."""
        with pytest.raises(ValidationError):
            ReplacementRule(search=123, replace="bar")  # type: ignore[arg-type]

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Tests initialization with missing required fields."""
        with pytest.raises(ValidationError):
            ReplacementRule()  # type: ignore[call-arg]

    @pytest.mark.sanity
    def test_marshalling(self, valid_instances: list[dict[str, Any]]) -> None:
        """Tests pydantic model_dump and model_validate."""
        for instance_data in valid_instances:
            rule = ReplacementRule.model_validate(instance_data)
            assert rule.search == instance_data["search"]


class TestBootstrapConfig:
    """Test suite for the BootstrapConfig class."""

    @pytest.fixture
    def valid_instances(self) -> list[dict[str, Any]]:
        """Provides valid data for creating BootstrapConfig instances."""
        return [
            {
                "organization": "my-org",
                "repository": "my-repo",
                "project_name": "my_project",
                "project_desc": "A desc",
                "env_prefix": "MY_PROJ",
                "disable_github_discussions": False,
                "disable_github_issues": False,
                "disable_github_roadmap": False,
                "disable_pypi": False,
                "docs_url": "https://docs",
                "maintainer": "me",
                "support_email": "me@me.com",
                "slack_url": "slack",
                "blog_url": "blog",
                "release_date": "2023-01-01",
                "global_blacklist": [],
            }
        ]

    @pytest.mark.sanity
    def test_signature(self) -> None:
        """Validates the class signature and fields."""
        assert hasattr(BootstrapConfig, "create")
        assert hasattr(BootstrapConfig, "apply")
        assert hasattr(BootstrapConfig, "release_year")

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: list[dict[str, Any]]) -> None:
        """Tests successful initialization of the class."""
        for instance_data in valid_instances:
            config = BootstrapConfig(**instance_data)
            assert config.organization == instance_data["organization"]

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Tests initialization with invalid values."""
        with pytest.raises(ValidationError):
            BootstrapConfig(  # type: ignore[call-arg]
                organization=123,  # type: ignore[arg-type]
                repository="repo",
                project_name="proj",
                project_desc="desc",
                env_prefix="env",
                disable_github_discussions="not-bool",  # type: ignore[arg-type]
                disable_github_issues=False,
                disable_github_roadmap=False,
                disable_pypi=False,
                docs_url="url",
                maintainer="main",
                support_email="email",
                slack_url="slack",
                blog_url="blog",
                release_date="date",
                global_blacklist=[],
            )

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Tests initialization with missing required fields."""
        with pytest.raises(ValidationError):
            BootstrapConfig()  # type: ignore[call-arg]

    @pytest.mark.sanity
    def test_marshalling(self, valid_instances: list[dict[str, Any]]) -> None:
        """Tests pydantic model_dump and model_validate."""
        for instance_data in valid_instances:
            config = BootstrapConfig.model_validate(instance_data)
            dumped_config = config.model_dump()
            assert dumped_config["organization"] == instance_data["organization"]

    @pytest.mark.smoke
    def test_create(self) -> None:
        """Tests the create classmethod factory."""
        config = BootstrapConfig.create(
            organization="test-org",
            repository="test-repo",
            project_name="test_proj",
            project_desc="desc",
            env_prefix="TEST",
            disable_github_discussions=False,
            disable_github_issues=False,
            disable_github_roadmap=False,
            disable_pypi=False,
            docs_url="url",
            maintainer="me",
            support_email="me@me.com",
            slack_url="slack",
            blog_url="blog",
            release_date="2023-01-01",
            global_blacklist=[],
        )
        assert config.organization == "test-org"

    @pytest.mark.smoke
    def test_apply(self, tmp_path: Path, valid_instances: list[dict[str, Any]]) -> None:
        """Tests applying configuration across files."""
        config = BootstrapConfig(**valid_instances[0])
        package_directory = tmp_path / "src" / "template_python"
        package_directory.mkdir(parents=True)
        test_file = tmp_path / "test.txt"
        test_file.write_text("template-python")

        rule = ReplacementRule(search="template-python", replace="my-repo")
        config.apply(tmp_path, [rule])

        assert test_file.read_text() == "my-repo"
        assert (tmp_path / "src" / "my_project").exists()

    @pytest.mark.sanity
    def test_release_year(self, valid_instances: list[dict[str, Any]]) -> None:
        """Tests the release_year property logic."""
        config = BootstrapConfig(**valid_instances[0])
        assert config.release_year == "2023"

    @pytest.mark.regression
    def test_matches_glob_with_directory_qualified_patterns(self) -> None:
        """Ensures directory-qualified glob patterns match repository file paths."""
        config = BootstrapConfig.create(
            organization="test-org",
            repository="test-repo",
            project_name="test_repo",
            project_desc="desc",
            env_prefix="TEST_REPO",
            disable_github_discussions=False,
            disable_github_issues=False,
            disable_github_roadmap=False,
            disable_pypi=False,
            docs_url="https://example.com/docs/",
            maintainer="maintainer",
            support_email="maintainer@example.com",
            slack_url="",
            blog_url="",
            release_date="2023-01-01",
            global_blacklist=[],
        )

        assert config._matches_glob(
            Path("/workspace/repo/.github/workflows/development.yml"),
            [".github/workflows/*.yml"],
        )
        assert config._matches_glob(
            Path("/workspace/repo/.github/ISSUE_TEMPLATE/bug_report.yml"),
            [".github/ISSUE_TEMPLATE/*.yml"],
        )
        assert config._matches_glob(
            Path("/workspace/repo/scripts/bootstrap.py"),
            ["scripts/bootstrap.py"],
        )
        assert not config._matches_glob(
            Path("/workspace/repo/.github/workflows/development.yml"),
            [".github/ISSUE_TEMPLATE/*.yml"],
        )
        assert not config._matches_glob(
            Path("/workspace/repo/docs/index.md"),
            [".github/workflows/*.yml"],
        )


class TestMain:
    """Test suite for the main bootstrap function."""

    @pytest.mark.sanity
    def test_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tests invalid arguments for main invocation."""
        with pytest.raises(ValidationError):
            main.callback(organization=123)  # type: ignore[misc]
