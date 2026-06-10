"""Unit tests for the version module."""

from __future__ import annotations

import pytest

from template_python import version


class TestVersionMetadata:
    """Test suite for the VersionMetadata NamedTuple."""

    @pytest.fixture(
        params=[
            {
                "major": 0,
                "minor": 1,
                "patch": 0,
                "pre": None,
                "post": None,
                "dev": 1,
                "local": "abc",
            },
            {
                "major": 1,
                "minor": 0,
                "patch": 0,
                "pre": ("a", 1),
                "post": 2,
                "dev": None,
                "local": None,
            },
        ]
    )
    def valid_instances(
        self, request: pytest.FixtureRequest
    ) -> version.VersionMetadata:
        """Fixture providing valid instances of VersionMetadata."""
        return version.VersionMetadata(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify class signature."""
        assert issubclass(version.VersionMetadata, tuple)
        assert hasattr(version.VersionMetadata, "major")

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: version.VersionMetadata) -> None:
        """Test proper initialization."""
        assert isinstance(valid_instances.major, int)
        assert isinstance(valid_instances.minor, int)


class TestGitMetadata:
    """Test suite for the GitMetadata NamedTuple."""

    @pytest.fixture(
        params=[
            {
                "hash": "abc",
                "branch": "main",
                "tag": "",
                "dirty": [],
                "commit_count": 1,
                "commit_message": "msg",
                "distance_from_head": 0,
                "is_head_commit": True,
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> version.GitMetadata:
        """Fixture providing valid instances of GitMetadata."""
        return version.GitMetadata(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify class signature."""
        assert issubclass(version.GitMetadata, tuple)
        assert hasattr(version.GitMetadata, "hash")

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: version.GitMetadata) -> None:
        """Test proper initialization."""
        assert isinstance(valid_instances.hash, str)


class TestBuildMetadata:
    """Test suite for the BuildMetadata NamedTuple."""

    @pytest.fixture(
        params=[
            {
                "timestamp": "2026",
                "host": "localhost",
                "python_version": "3.14",
                "id": "123",
            },
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> version.BuildMetadata:
        """Fixture providing valid instances of BuildMetadata."""
        return version.BuildMetadata(**request.param)

    @pytest.mark.smoke
    def test_signature(self) -> None:
        """Verify class signature."""
        assert issubclass(version.BuildMetadata, tuple)
        assert hasattr(version.BuildMetadata, "timestamp")

    @pytest.mark.sanity
    def test_initialization(self, valid_instances: version.BuildMetadata) -> None:
        """Test proper initialization."""
        assert isinstance(valid_instances.timestamp, str)


@pytest.mark.smoke
def test___version__() -> None:
    """Validate __version__ param/type."""
    assert isinstance(version.__version__, str)


@pytest.mark.smoke
def test_version() -> None:
    """Validate version param/type."""
    assert version.version == version.__version__
    assert isinstance(version.version, str)


@pytest.mark.sanity
def test___version_metadata__() -> None:
    """Validate __VERSION_METADATA__ param/type."""
    assert isinstance(version.__VERSION_METADATA__, version.VersionMetadata)


@pytest.mark.sanity
def test___git_metadata__() -> None:
    """Validate __GIT_METADATA__ param/type."""
    assert isinstance(version.__GIT_METADATA__, version.GitMetadata)


@pytest.mark.sanity
def test___build_metadata__() -> None:
    """Validate __BUILD_METADATA__ param/type."""
    assert isinstance(version.__BUILD_METADATA__, version.BuildMetadata)
