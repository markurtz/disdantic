from __future__ import annotations

import subprocess
import threading
import time
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, BeforeValidator
from typer.testing import CliRunner

from disdantic.__main__ import app
from disdantic.registry import RegistryMixin
from disdantic.singleton import SingletonMeta


class ConfigService(metaclass=SingletonMeta):
    """A singleton service for testing config lifecycle."""

    def __init__(self, environment: str = "production") -> None:
        self.environment = environment


class DatabaseService(metaclass=SingletonMeta):
    """A singleton service for testing database lifecycle."""

    def __init__(self, host: str = "localhost") -> None:
        self.host = host


class StrictSingleton(metaclass=SingletonMeta):
    """A singleton with validation to test invalid inputs."""

    def __init__(self, score: int) -> None:
        if not isinstance(score, int):
            raise ValueError("Score must be an integer")
        self.score = score


class RequiredArgSingleton(metaclass=SingletonMeta):
    """A singleton requiring arguments to test missing args."""

    def __init__(self, required_val: str) -> None:
        self.required_val = required_val


class ConnectionPool(metaclass=SingletonMeta):
    """A singleton connection pool for Pydantic integration."""

    def __init__(self, size: int = 10) -> None:
        self.size = size


def validate_connection_pool(value: Any) -> ConnectionPool:
    """Validate and coerce input to ConnectionPool singleton."""
    if isinstance(value, ConnectionPool):
        return value
    if isinstance(value, dict):
        return ConnectionPool(**value)
    if isinstance(value, int):
        return ConnectionPool(size=value)
    raise ValueError("Invalid connection pool initialization parameters")


class DatabaseConfig(BaseModel):
    """Pydantic model holding reference to the ConnectionPool singleton."""

    name: str
    pool: Annotated[ConnectionPool, BeforeValidator(validate_connection_pool)]

    model_config = {
        "arbitrary_types_allowed": True,
    }


class TestRegistry(RegistryMixin[type]):
    """Registry for testing singleton integration with RegistryMixin."""


class LockSpy:
    """A lock wrapper for double-checked locking verification.

    Wraps a threading.Lock to count how many times it was acquired.
    """

    def __init__(self, original_lock: threading.Lock) -> None:
        self._original = original_lock
        self.acquire_count = 0

    def __enter__(self) -> bool:
        self.acquire_count += 1
        return self._original.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool | None:
        return self._original.__exit__(exc_type, exc_val, exc_tb)

    def acquire(self, *args: Any, **kwargs: Any) -> bool:
        self.acquire_count += 1
        return self._original.acquire(*args, **kwargs)

    def release(self) -> None:
        self._original.release()


class TestSingletonMeta:
    """E2E test suite for SingletonMeta metaclass boundaries."""

    @pytest.fixture(
        params=[
            ConfigService,
            DatabaseService,
        ]
    )
    def valid_instances(self, request: pytest.FixtureRequest) -> type:
        """Fixture providing valid variations of integrated singleton classes."""
        return request.param

    @pytest.mark.smoke
    def test_contract_validation(self) -> None:
        """Validate structural contracts, method signatures, and class variables."""
        assert issubclass(SingletonMeta, type)
        assert hasattr(SingletonMeta, "_instances")
        assert hasattr(SingletonMeta, "_lock")
        assert hasattr(SingletonMeta, "clear_instances")
        assert hasattr(SingletonMeta, "clear_all_singletons")

    @pytest.mark.smoke
    def test_initialization(self, valid_instances: type) -> None:
        """Verify happy-path initialization intercepts and caches the instance."""
        SingletonMeta.clear_all_singletons()

        instance_one = valid_instances()
        instance_two = valid_instances()

        assert instance_one is instance_two

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify that validation failures inside init raise errors and don't cache."""
        SingletonMeta.clear_all_singletons()

        with pytest.raises(ValueError, match="Score must be an integer"):
            StrictSingleton("not_an_int")

        assert StrictSingleton not in SingletonMeta._instances

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify initialization with missing parameters raises TypeError."""
        SingletonMeta.clear_all_singletons()

        with pytest.raises(TypeError):
            RequiredArgSingleton()

        assert RequiredArgSingleton not in SingletonMeta._instances

    @pytest.mark.smoke
    def test_concurrent_double_checked_locking(self) -> None:
        """Verify double-checked locking thread-safety and lock bypass."""
        SingletonMeta.clear_all_singletons()

        original_lock = SingletonMeta._lock
        spy_lock = LockSpy(original_lock)
        SingletonMeta._lock = spy_lock  # type: ignore

        # Ensure class is not cached yet
        assert ConfigService not in SingletonMeta._instances

        # First instantiation: enters slow path, acquires lock
        instance_one = ConfigService("development")
        assert spy_lock.acquire_count == 1

        # Second instantiation: fast path, lock is NOT acquired
        instance_two = ConfigService("production")
        assert instance_one is instance_two
        assert instance_two.environment == "development"  # Init not re-run
        assert spy_lock.acquire_count == 1

        # Now test concurrent instantiation with many threads
        SingletonMeta.clear_all_singletons()
        spy_lock.acquire_count = 0

        class SlowInitService(metaclass=SingletonMeta):
            init_count = 0
            init_lock = threading.Lock()

            def __init__(self) -> None:
                with SlowInitService.init_lock:
                    SlowInitService.init_count += 1
                time.sleep(0.02)

        instances_list: list[SlowInitService] = []
        list_lock = threading.Lock()

        def worker() -> None:
            inst = SlowInitService()
            with list_lock:
                instances_list.append(inst)

        # Spawn concurrent threads
        thread_count = 40
        threads = [threading.Thread(target=worker) for idx in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(instances_list) == thread_count
        first_instance = instances_list[0]
        for instance in instances_list:
            assert instance is first_instance

        # Concurrency check: __init__ should have run exactly once
        assert SlowInitService.init_count == 1

        # Reset lock
        SingletonMeta._lock = original_lock

    @pytest.mark.regression
    def test_clear_instances(self) -> None:
        """Verify clear_instances evicts a specific class instance from the cache."""
        SingletonMeta.clear_all_singletons()

        instance_one = ConfigService("initial")
        assert ConfigService in SingletonMeta._instances

        ConfigService.clear_instances()
        assert ConfigService not in SingletonMeta._instances

        instance_two = ConfigService("new_value")
        assert instance_one is not instance_two
        assert instance_two.environment == "new_value"

    @pytest.mark.regression
    def test_clear_all_singletons(self) -> None:
        """Verify clear_all_singletons wipes all tracked singleton instances."""
        SingletonMeta.clear_all_singletons()

        instance_a = ConfigService()
        instance_b = DatabaseService()

        assert ConfigService in SingletonMeta._instances
        assert DatabaseService in SingletonMeta._instances

        SingletonMeta.clear_all_singletons()

        assert len(SingletonMeta._instances) == 0

        new_instance_a = ConfigService()
        new_instance_b = DatabaseService()

        assert instance_a is not new_instance_a
        assert instance_b is not new_instance_b

    @pytest.mark.regression
    def test_marshalling(self) -> None:
        """Verify singleton behavior inside Pydantic models via dump and validate."""
        SingletonMeta.clear_all_singletons()

        # Validate from primitive
        model_a = DatabaseConfig.model_validate({"name": "db_main", "pool": 15})
        assert isinstance(model_a.pool, ConnectionPool)
        assert model_a.pool.size == 15

        # Validate another model using a dictionary
        model_b = DatabaseConfig.model_validate(
            {"name": "db_replica", "pool": {"size": 25}}
        )

        # Because ConnectionPool is a singleton, it returns the cached instance
        assert model_b.pool is model_a.pool
        assert model_b.pool.size == 15

        # Verify serialization
        dump_data = model_a.model_dump()
        assert dump_data["name"] == "db_main"
        assert dump_data["pool"] is model_a.pool

    @pytest.mark.regression
    def test_dynamic_flow_registry(self) -> None:
        """Verify integration with RegistryMixin, testing registration and lookup."""
        SingletonMeta.clear_all_singletons()
        TestRegistry.clear_registry()

        # Register services
        TestRegistry.register_decorator(ConfigService, name="config_srv")
        TestRegistry.register_decorator(DatabaseService, name="db_srv")

        # Retrieve and instantiate
        resolved_config = TestRegistry.get_registered_object("config_srv")
        resolved_db = TestRegistry.get_registered_object("db_srv")

        assert resolved_config is ConfigService
        assert resolved_db is DatabaseService

        instance_c1 = resolved_config()
        instance_c2 = resolved_config()
        instance_d1 = resolved_db()
        instance_d2 = resolved_db()

        assert instance_c1 is instance_c2
        assert instance_d1 is instance_d2
        assert instance_c1 is not instance_d1


class TestCLIEntrypoint:
    """E2E test suite for the command-line interface entrypoints."""

    @pytest.mark.smoke
    def test_cli_help_flag(self) -> None:
        """Test invoking help flag via Typer CliRunner."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Disdantic" in result.stdout

    @pytest.mark.smoke
    def test_cli_version_flag(self) -> None:
        """Test invoking version flag via Typer CliRunner."""
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "disdantic" in result.stdout

    @pytest.mark.sanity
    def test_cli_default_execution(self) -> None:
        """Test invoking CLI without arguments."""
        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == 0

    @pytest.mark.sanity
    def test_cli_invalid_arguments(self) -> None:
        """Test invoking CLI with invalid arguments."""
        runner = CliRunner()
        result = runner.invoke(app, ["--invalid-flag"])
        assert result.exit_code != 0

    @pytest.mark.regression
    def test_cli_subprocess_help(self) -> None:
        """Test invoking the installed disdantic command via subprocess."""
        result = subprocess.run(
            ["disdantic", "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.returncode == 0
        assert "Disdantic" in result.stdout
