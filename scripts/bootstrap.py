#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "click",
#     "pydantic",
# ]
# ///
"""
Template Initialization Script.

Automatically replaces all template placeholders with your actual project values
by providing a set of variables either via the CLI or an interactive prompt.

Example:
    uv run scripts/bootstrap.py --organization my-org --repository my-repo
"""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from re import Pattern
from typing import Annotated, Any

import click
from pydantic import BaseModel, ConfigDict, Field

__all__ = ["IS_INTERACTIVE", "BootstrapConfig", "ReplacementRule", "main"]

IS_INTERACTIVE: Annotated[
    bool,
    "Determines if the script is running in an interactive TTY session "
    "without any CI or test constraints.",
] = (
    sys.stdin.isatty()
    and not os.environ.get("PYTEST_CURRENT_TEST")
    and not os.environ.get("CI")
)

DEFAULT_GLOBAL_BLACKLIST: Annotated[
    tuple[str, ...],
    "Default glob patterns to universally ignore during template replacement.",
] = (
    ".git/**",
    ".venv/**",
    ".tox/**",
    "__pycache__/**",
    "node_modules/**",
    "site/**",
    "build/**",
    "dist/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".ruff_cache/**",
    "scripts/bootstrap.py",
    "*.pyc",
    "*.png",
    "*.svg",
    "*.jpg",
    "*.jpeg",
    "*.ico",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
)


class ReplacementRule(BaseModel):
    """
    Defines a single replacement operation during bootstrapping.

    This class encapsulates the logic for a single search and replace operation,
    allowing for both exact string matching and regular expression substitution
    across the targeted repository files.

    Example:
        rule = ReplacementRule(
            search="old_text",
            replace="new_text",
            whitelist_globs=["*.md"]
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    search: str | Pattern[str] = Field(
        description=(
            "The exact text or compiled regex pattern to search "
            "for within file content."
        )
    )
    replace: Any = Field(
        description=(
            "The replacement string or a callable for regex substitution operations."
        )
    )
    whitelist_globs: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of glob patterns; if provided, only files "
            "matching these globs are processed."
        ),
    )
    blacklist_globs: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of glob patterns; files matching these "
            "globs are explicitly ignored."
        ),
    )


class BootstrapConfig(BaseModel):
    """
    Configuration state for the repository bootstrap process.

    This class acts as the central data structure holding all the necessary
    variables used to template the repository. It includes factory methods
    to evaluate default values and interactively prompt users when needed.

    Example:
        config = BootstrapConfig.create(organization="my-org", repository="my-repo")
        config.apply(Path("."), rules)
    """

    organization: str = Field(
        description="The GitHub organization or username owning the repository."
    )
    repository: str = Field(description="The name of the GitHub repository.")
    project_name: str = Field(
        description="The Python package and project name, typically using underscores."
    )
    project_desc: str = Field(
        description="A short description of the project used in README and packaging."
    )
    env_prefix: str = Field(
        description=(
            "The prefix used for environment variables, typically "
            "uppercase project name."
        )
    )
    disable_github_discussions: bool = Field(
        description="Flag to disable GitHub Discussions links and workflows."
    )
    disable_github_issues: bool = Field(
        description="Flag to disable GitHub Issues links and workflows."
    )
    disable_github_roadmap: bool = Field(
        description="Flag to disable GitHub Roadmap links and workflows."
    )
    disable_pypi: bool = Field(
        description="Flag to disable PyPI publishing workflows and badges."
    )
    docs_url: str | None = Field(
        description="The absolute URL where project documentation is hosted."
    )
    maintainer: str = Field(
        description="The primary maintainer or author of the project."
    )
    support_email: str = Field(
        description=(
            "The primary contact email for support and code of conduct inquiries."
        )
    )
    slack_url: str = Field(
        description="The Slack community URL to display in documentation."
    )
    blog_url: str = Field(
        description="The blog or website URL to display in documentation."
    )
    release_date: str = Field(
        description="The initial release date formatted as YYYY-MM-DD."
    )
    global_blacklist: list[str] = Field(
        description="A list of glob patterns to universally ignore during replacements."
    )

    @classmethod
    def create(cls, **kwargs: Any) -> BootstrapConfig:
        """
        Evaluates the provided configuration, injecting defaults and prompting
        where necessary.

        This factory method constructs the configuration object by evaluating
        provided arguments, attempting to guess defaults via git configuration,
        and optionally prompting the user interactively if the session allows it.

        :param kwargs: The initial keyword arguments provided via CLI or scripts.
        :return: A fully populated configuration instance.
        """
        git_org, git_repo = cls._get_git_origin()
        default_org = git_org or "markurtz"
        default_repo = git_repo or Path.cwd().name
        default_maintainer = cls._get_git_config("user.name") or default_org
        default_desc = (
            "An opinionated, production-ready Apache 2.0 template repository "
            "for bootstrapping modern software projects."
        )
        today = datetime.date.today()
        default_date = today.isoformat()

        if IS_INTERACTIVE:
            click.echo("--- Template Initialization ---")
            click.echo("Please confirm or provide the following values.")

        organization = (
            cls._prompt_if_none(kwargs.get("organization"), "Organization", default_org)
            or default_org
        )
        repository = (
            cls._prompt_if_none(kwargs.get("repository"), "Repository", default_repo)
            or default_repo
        )

        default_project_name = (
            repository.replace("-", "_") if repository else "template_python"
        )
        project_name = (
            cls._prompt_if_none(
                kwargs.get("project_name"), "Project Name", default_project_name
            )
            or default_project_name
        )

        default_env_prefix = project_name.upper() if project_name else "TEMPLATE_PYTHON"
        env_prefix = (
            cls._prompt_if_none(
                kwargs.get("env_prefix"), "Environment Prefix", default_env_prefix
            )
            or default_env_prefix
        )

        project_desc = (
            cls._prompt_if_none(
                kwargs.get("project_desc"), "Project Description", default_desc
            )
            or default_desc
        )

        if not default_maintainer or default_maintainer == default_org:
            default_maintainer = organization

        default_email = ""

        maintainer = (
            cls._prompt_if_none(
                kwargs.get("maintainer"), "Maintainer", default_maintainer
            )
            or default_maintainer
        )

        support_email = cls._prompt_if_none(
            kwargs.get("support_email"), "Support Email", default_email
        )

        slack_url = cls._prompt_if_none(
            kwargs.get("slack_url"), "Slack URL (leave blank to omit)", ""
        )
        blog_url = cls._prompt_if_none(
            kwargs.get("blog_url"), "Blog URL (leave blank to omit)", ""
        )
        release_date = (
            cls._prompt_if_none(
                kwargs.get("release_date"), "Release Date", default_date
            )
            or default_date
        )

        disable_github_discussions = cls._prompt_if_none(
            kwargs.get("disable_github_discussions"),
            "Disable GitHub Discussions?",
            False,
            is_bool=True,
        )
        disable_github_issues = cls._prompt_if_none(
            kwargs.get("disable_github_issues"),
            "Disable GitHub Issues?",
            False,
            is_bool=True,
        )
        disable_github_roadmap = cls._prompt_if_none(
            kwargs.get("disable_github_roadmap"),
            "Disable GitHub Roadmap?",
            False,
            is_bool=True,
        )
        disable_pypi = cls._prompt_if_none(
            kwargs.get("disable_pypi"), "Disable PyPI Publishing?", False, is_bool=True
        )

        default_docs_url = (
            f"https://{organization}.github.io/{repository}/"
            if organization and repository
            else "https://example.com/docs/"
        )
        docs_url_value = kwargs.get("docs_url")
        if docs_url_value is None and not IS_INTERACTIVE:
            docs_url_value = default_docs_url

        docs_url = cls._prompt_if_none(
            docs_url_value, "Docs URL (leave blank to disable)", default_docs_url
        )
        if docs_url is not None and str(docs_url).strip() == "":
            docs_url = None

        init_kwargs = {
            "organization": organization,
            "repository": repository,
            "project_name": project_name,
            "project_desc": project_desc,
            "env_prefix": env_prefix,
            "disable_github_discussions": disable_github_discussions,
            "disable_github_issues": disable_github_issues,
            "disable_github_roadmap": disable_github_roadmap,
            "disable_pypi": disable_pypi,
            "docs_url": docs_url,
            "maintainer": maintainer,
            "support_email": support_email,
            "slack_url": slack_url,
            "blog_url": blog_url,
            "release_date": release_date,
            "global_blacklist": (
                kwargs.get("global_blacklist") or list(DEFAULT_GLOBAL_BLACKLIST)
            ),
        }

        return cls(**init_kwargs)

    @property
    def release_year(self) -> str:
        """
        Retrieves the year from the configured release date.

        :return: A four-digit year string based on the release_date.
        """
        return (
            self.release_date.split("-")[0]
            if "-" in self.release_date
            else str(datetime.date.today().year)
        )

    def apply(self, repo_root: Path, rules: list[ReplacementRule]) -> None:
        """
        Applies all bootstrap replacements and filesystem operations to the
        targeted repository.

        This method coordinates the execution of all provided replacement rules
        across the targeted directory structure, applying renames and cleaning
        up the bootstrap scripts themselves upon successful completion.

        :param repo_root: The root path of the repository to bootstrap.
        :param rules: A list of configured replacement rules to execute.
        """
        if IS_INTERACTIVE:
            click.echo("\nApplying replacements...")

        for file_path in repo_root.rglob("*"):
            self._apply_replacements(file_path, rules)

        # Rename src/template_python directory
        old_pkg_dir = repo_root / "src" / "template_python"
        new_pkg_dir = repo_root / "src" / self.project_name
        if old_pkg_dir.exists() and old_pkg_dir != new_pkg_dir:
            old_pkg_dir.rename(new_pkg_dir)

        if IS_INTERACTIVE:
            click.echo("\nBootstrap complete! Check the repository for changes.")

            if click.confirm(
                "\nWARNING: Do you want to finalize the bootstrap process? "
                "This will permanently DELETE scripts/bootstrap.py "
                "and tests/e2e/test_bootstrap.py.",
                default=True,
            ):
                script_path = repo_root / "scripts" / "bootstrap.py"
                test_path = repo_root / "tests" / "e2e" / "test_bootstrap.py"
                unit_test_path = repo_root / "tests" / "unit" / "test_bootstrap.py"
                if script_path.exists():
                    script_path.unlink()
                if test_path.exists():
                    test_path.unlink()
                if unit_test_path.exists():
                    unit_test_path.unlink()
                click.echo("Bootstrap scripts deleted.")

    @classmethod
    def _get_git_config(cls, key: str) -> str | None:
        """Gets a value from git config."""
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "config", "--get", key],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as exception:  # noqa: BLE001
            click.secho(
                f"Warning: Could not get git config '{key}': {exception}",
                fg="yellow",
                err=True,
            )
        return None

    @classmethod
    def _get_git_origin(cls) -> tuple[str | None, str | None]:
        """Gets organization and repository from git remote origin url."""
        remote_url = cls._get_git_config("remote.origin.url")
        if not remote_url:
            return None, None

        pattern = re.compile(
            r"^(?:https?://[^/]+/|git@[^:]+:)([^/]+)/([^/.]+)(?:\.git)?$"
        )
        match = pattern.match(remote_url)
        if match:
            return match.group(1), match.group(2)

        return None, None

    @classmethod
    def _prompt_if_none(
        cls, value: Any, prompt_text: str, default_value: Any, is_bool: bool = False
    ) -> Any:
        """Prompts the user if the value was not provided via CLI."""
        if value is not None:
            return value

        if not IS_INTERACTIVE:
            return default_value

        try:
            if is_bool:
                return click.confirm(prompt_text, default=default_value)
            return click.prompt(prompt_text, default=default_value)
        except EOFError:
            return default_value

    def _matches_glob(self, path: Path, patterns: list[str]) -> bool:
        path_matcher = PurePosixPath(path.as_posix())
        for pattern in patterns:
            if path_matcher.match(pattern):
                return True
            if pattern.endswith("/**"):
                directory_pattern = pattern[:-3]
                if directory_pattern in path.parts:
                    return True
        return False

    def _should_bootstrap_file(
        self,
        file_path: Path,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
    ) -> bool:
        """Checks whether the file should be targeted for a specific rule."""
        if blacklist and self._matches_glob(file_path, blacklist):
            return False

        return not whitelist or self._matches_glob(file_path, whitelist)

    def _apply_replacements(
        self, file_path: Path, rules: list[ReplacementRule]
    ) -> bool:
        """Applies a list of replacement rules to the specified file."""
        if not file_path.is_file() or self._matches_glob(
            file_path, self.global_blacklist
        ):
            return False

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return False

        original_content = content

        for rule in rules:
            if not self._should_bootstrap_file(
                file_path, rule.whitelist_globs, rule.blacklist_globs
            ):
                continue

            if isinstance(rule.search, Pattern):
                content = rule.search.sub(rule.replace, content)
            elif rule.replace is not None and rule.search != rule.replace:
                content = content.replace(rule.search, rule.replace)

        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            return True

        return False


@click.command()
@click.option(
    "--organization",
    default=None,
    help=(
        "The GitHub organization or user account that will own the repository. "
        "If not provided, attempts to infer from git remote or defaults to 'markurtz'."
    ),
)
@click.option(
    "--repository",
    default=None,
    help=(
        "The exact name of the GitHub repository. "
        "If not provided, attempts to infer from git remote or defaults "
        "to the current working directory."
    ),
)
@click.option(
    "--project-name",
    default=None,
    help=(
        "The Python package name (typically using underscores instead of hyphens). "
        "If not provided, defaults to the repository name with hyphens replaced "
        "by underscores."
    ),
)
@click.option(
    "--project-desc",
    default=None,
    help=(
        "A short, one-sentence description of the project used in README "
        "and package metadata. If not provided, it will be asked interactively."
    ),
)
@click.option(
    "--env-prefix",
    default=None,
    help=(
        "The prefix used for environment variables parsed by Pydantic settings. "
        "If not provided, defaults to the uppercase version of the project name."
    ),
)
@click.option(
    "--disable-github-discussions",
    is_flag=True,
    default=None,
    help=(
        "Removes GitHub Discussions links from the documentation and issues templates. "
        "Defaults to false (enabled)."
    ),
)
@click.option(
    "--disable-github-issues",
    is_flag=True,
    default=None,
    help=(
        "Removes GitHub Issues links from the documentation and disables "
        "issue tracking configurations. Defaults to false (enabled)."
    ),
)
@click.option(
    "--disable-github-roadmap",
    is_flag=True,
    default=None,
    help=(
        "Removes roadmap milestone links from the documentation. "
        "Defaults to false (enabled)."
    ),
)
@click.option(
    "--disable-pypi",
    is_flag=True,
    default=None,
    help=(
        "Disables PyPI publishing workflows and removes PyPI badges from "
        "the documentation. Defaults to false (publishing enabled)."
    ),
)
@click.option(
    "--docs-url",
    default=None,
    help=(
        "The absolute URL where project documentation will be hosted. "
        "Leave blank to completely disable documentation site workflows and links. "
        "If not provided, defaults to 'https://<organization>.github.io/<repository>/'."
    ),
)
@click.option(
    "--maintainer",
    default=None,
    help=(
        "The primary maintainer or author of the project. "
        "If not provided, attempts to infer from git config or defaults "
        "to the organization name."
    ),
)
@click.option(
    "--support-email",
    default=None,
    help=(
        "The primary contact email for support and code of conduct inquiries. "
        "If not provided, defaults to an empty string, removing it and "
        "replacing with a generic reference."
    ),
)
@click.option(
    "--slack-url",
    default=None,
    help=(
        "The Slack community URL to display in documentation. "
        "If not provided, defaults to an empty string, removing it."
    ),
)
@click.option(
    "--blog-url",
    default=None,
    help=(
        "The blog or website URL to display in documentation. "
        "If not provided, defaults to an empty string, removing it."
    ),
)
@click.option(
    "--release-date",
    default=None,
    help=(
        "The initial release date formatted as YYYY-MM-DD. "
        "If not provided, defaults to the current date."
    ),
)
@click.option(
    "--global-blacklist",
    multiple=True,
    default=DEFAULT_GLOBAL_BLACKLIST,
    help=(
        "A list of glob patterns to universally ignore during template "
        "variable replacement."
    ),
)
def main(**kwargs: Any) -> None:  # noqa: C901
    """
    Bootstraps the repository by evaluating configuration and applying
    template variables.

    This function serves as the primary entrypoint for the CLI. It handles
    initialization of the configuration state, defines the core replacement
    rules for enabling/disabling various project features, and applies those
    rules to the repository.

    :param kwargs: Keyword arguments mapped directly from the click CLI options.
    """
    config = BootstrapConfig.create(**kwargs)

    repo_root = Path(__file__).resolve().parent.parent

    # Exact Replacements Map
    rules = []

    def comment_out_match(match: re.Match[str]) -> str:
        lines = match.group(0).splitlines(keepends=True)
        return "".join([f"# {line}" if line.strip() else line for line in lines])

    def uncomment_match(match: re.Match[str]) -> str:
        lines = match.group(0).splitlines(keepends=True)
        return "".join(
            [
                line.replace("# ", "", 1) if line.strip().startswith("#") else line
                for line in lines
            ]
        )

    def remove_html_comments(match: re.Match[str]) -> str:
        return match.group(1)

    def html_comment_out(match: re.Match[str]) -> str:
        return f"<!-- {match.group(1)} -->"

    # 1. PyPI Toggle
    if not config.disable_pypi:
        # Uncomment PyPI
        rules.extend(
            [
                ReplacementRule(
                    search=re.compile(
                        r"<!--\s*(<a href=\"https://pypi.org.*?</a>)\s*-->", re.DOTALL
                    ),
                    replace=remove_html_comments,
                    whitelist_globs=["README.md"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r"^\s*#\s+- name: Publish to PyPI\n(?:\s*#.*\n)*", re.MULTILINE
                    ),
                    replace=uncomment_match,
                    whitelist_globs=[".github/workflows/*.yml"],
                ),
            ]
        )

    # 2. Docs Toggle
    if config.docs_url:
        rules.extend(
            [
                ReplacementRule(
                    search=re.compile(r'(docs_url:\s*)".*?"', re.MULTILINE),
                    replace=f'\\g<1>"{config.docs_url}"',
                    whitelist_globs=["mkdocs.yml"],
                ),
                ReplacementRule(
                    search=re.compile(r'(Documentation = )".*?"', re.MULTILINE),
                    replace=f'\\g<1>"{config.docs_url}"',
                    whitelist_globs=["pyproject.toml"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r'(<a href=")https://markurtz.github.io/template-python'
                        r'(">Documentation</a>)',
                        re.MULTILINE,
                    ),
                    replace=f"\\g<1>{config.docs_url}\\g<2>",
                    whitelist_globs=["README.md"],
                ),
            ]
        )
    else:
        # Comment out Docs blocks
        rules.extend(
            [
                ReplacementRule(
                    search=re.compile(r"^(docs_url:.*\n)", re.MULTILINE),
                    replace=comment_out_match,
                    whitelist_globs=["mkdocs.yml"],
                ),
                ReplacementRule(
                    search=re.compile(r"^(Documentation = .*\n)", re.MULTILINE),
                    replace=comment_out_match,
                    whitelist_globs=["pyproject.toml"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r"^(docs\s*=\s*\[\n(?:[\s\S]*?)\]\n)", re.MULTILINE
                    ),
                    replace=comment_out_match,
                    whitelist_globs=["pyproject.toml"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r"^(\[tool\.hatch\.envs\.docs\]\n"
                        r"(?:[a-zA-Z0-9_\-\.]+\s*=.*\n)*)",
                        re.MULTILINE,
                    ),
                    replace=comment_out_match,
                    whitelist_globs=["pyproject.toml"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r"^(.*?docs:\s*\n(?:\s+.*\n)*?(?=\s*[a-zA-Z0-9_-]+:\s*\n|\Z))",
                        re.MULTILINE,
                    ),
                    replace=comment_out_match,
                    whitelist_globs=[".github/workflows/*.yml"],
                ),
                ReplacementRule(
                    search=re.compile(r"^(\s*- docs\n)", re.MULTILINE),
                    replace=comment_out_match,
                    whitelist_globs=[".github/workflows/*.yml"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r'(<a href="[^"]*">Documentation</a>)', re.MULTILINE
                    ),
                    replace=html_comment_out,
                    whitelist_globs=["README.md"],
                ),
            ]
        )

    # 3. GitHub Feature Toggles
    if config.disable_github_discussions:
        rules.extend(
            [
                ReplacementRule(
                    search=re.compile(
                        r'(<a href="[^"]*/discussions">Discussions</a>)', re.MULTILINE
                    ),
                    replace=html_comment_out,
                    whitelist_globs=["README.md"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r"^(.*and \[Discussions\]\([^)]+\) .*\n)", re.MULTILINE
                    ),
                    replace=comment_out_match,
                    whitelist_globs=[".github/ISSUE_TEMPLATE/*.yml"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r"^(.*For general help and Q&A, please use "
                        r"\[GitHub Discussions\].*?instead\.\n)",
                        re.MULTILINE,
                    ),
                    replace=comment_out_match,
                    whitelist_globs=[".github/ISSUE_TEMPLATE/*.yml"],
                ),
            ]
        )

    if config.disable_github_issues:
        rules.extend(
            [
                ReplacementRule(
                    search=re.compile(
                        r'(<a href="[^"]*/issues">Issues</a>)', re.MULTILINE
                    ),
                    replace=html_comment_out,
                    whitelist_globs=["README.md"],
                ),
                ReplacementRule(
                    search=re.compile(
                        r'^(.*Issues = "https://github.com/[^"]+/issues"\n)',
                        re.MULTILINE,
                    ),
                    replace=comment_out_match,
                    whitelist_globs=["pyproject.toml"],
                ),
            ]
        )

    if config.disable_github_roadmap:
        rules.extend(
            [
                ReplacementRule(
                    search=re.compile(
                        r'(<a href="[^"]*/milestones">Roadmap</a>)', re.MULTILINE
                    ),
                    replace=html_comment_out,
                    whitelist_globs=["README.md"],
                ),
                ReplacementRule(
                    search=re.compile(r"^(.*roadmap_url:.*\n)", re.MULTILINE),
                    replace=comment_out_match,
                    whitelist_globs=["mkdocs.yml"],
                ),
            ]
        )

    # 4. Optional URLs
    if config.slack_url:
        rules.append(
            ReplacementRule(
                search=re.compile(r"^#\s*(slack_url:.*)$", re.MULTILINE),
                replace=f'  slack_url: "{config.slack_url}"',
                whitelist_globs=["mkdocs.yml"],
            )
        )

    if config.blog_url:
        rules.append(
            ReplacementRule(
                search=re.compile(r"^#\s*(blog_url:.*)$", re.MULTILINE),
                replace=f'  blog_url: "{config.blog_url}"',
                whitelist_globs=["mkdocs.yml"],
            )
        )

    rules.extend(
        [
            ReplacementRule(
                search="{{maintainer_username}}", replace=config.maintainer
            ),
            ReplacementRule(
                search="author = {markurtz}",
                replace=f"author = {{{config.maintainer}}}",
            ),
            ReplacementRule(search="template-python", replace=config.repository),
            ReplacementRule(search="template_python", replace=config.project_name),
            ReplacementRule(search="TEMPLATE_PYTHON", replace=config.env_prefix),
            ReplacementRule(search="markurtz", replace=config.organization),
            ReplacementRule(
                search=re.compile(
                    r"An opinionated, production-ready Apache 2\.0 template "
                    r"repository[\s\S]{0,50}modern software projects\."
                ),
                replace=config.project_desc,
            ),
            ReplacementRule(search="conduct@example.com", replace=config.support_email),
            ReplacementRule(search="{{year}}", replace=config.release_year),
        ]
    )

    config.apply(repo_root, rules)


if __name__ == "__main__":
    main()
