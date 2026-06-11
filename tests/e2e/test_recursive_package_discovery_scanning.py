# Copyright 2026 markurtz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""E2E tests for US-4.1: Recursive Package Discovery scanning."""

from __future__ import annotations

import contextlib
import gc
import inspect
import shutil
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import get_settings, reset_settings

# Expose at module level for submodule imports
DynamicE2ERecursiveRegistry: Any = None


class TestRecursivePackageDiscoveryScanning:
    """E2E test suite for US-4.1: Recursive Package Discovery scanning."""

    @pytest.fixture(params=["class_level", "settings_level"])
    def valid_instances(
        self, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[type[PydanticClassRegistryMixin], None, None]:
        """Supply isolated registry classes configured in different ways."""
        # Create a unique temporary package inside the workspace to avoid conflicts.
        base_dir = Path(__file__).parent / "temp_packages_us41"
        base_dir.mkdir(exist_ok=True)

        package_name = f"temp_discovery_pkg_{request.param}"
        package_dir = base_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Write __init__.py
        init_file = package_dir / "__init__.py"
        init_file.write_text("", encoding="utf-8")

        # Write a submodule containing a registered class
        submodule_file = package_dir / "submodule.py"
        submodule_content = """from __future__ import annotations
from typing import Literal
from tests.e2e.test_recursive_package_discovery_scanning import (
    DynamicE2ERecursiveRegistry,
)

@DynamicE2ERecursiveRegistry.register("DummySubclass")
class DummySubclass(DynamicE2ERecursiveRegistry):
    dummy_type: Literal["DummySubclass"] = "DummySubclass"
    value: int
"""
        submodule_file.write_text(submodule_content, encoding="utf-8")

        # Prep path
        monkeypatch.syspath_prepend(str(base_dir))
        reset_settings()

        # Build dynamic registry base
        class _DynamicE2ERecursiveRegistry(PydanticClassRegistryMixin):
            """Base registry used for US-4.1 E2E tests."""

            schema_discriminator = "dummy_type"
            dummy_type: str

        _DynamicE2ERecursiveRegistry.auto_package = package_name

        if request.param == "class_level":
            _DynamicE2ERecursiveRegistry.registry_auto_discovery = True
        else:
            # settings_level
            _DynamicE2ERecursiveRegistry.registry_auto_discovery = False
            settings = get_settings()
            settings.registry_auto_discovery = True

        # Expose class on module level so the submodule can import it
        cur_mod = cast("Any", sys.modules[__name__])
        cur_mod.DynamicE2ERecursiveRegistry = _DynamicE2ERecursiveRegistry

        alias_added = False
        alias_name = "tests.e2e.test_recursive_package_discovery_scanning"
        if alias_name not in sys.modules:
            sys.modules[alias_name] = cur_mod
            alias_added = True

        yield _DynamicE2ERecursiveRegistry

        # Cleanup sys.modules
        for key in list(sys.modules.keys()):
            if key == package_name or key.startswith(f"{package_name}."):
                sys.modules.pop(key, None)

        if alias_added:
            sys.modules.pop(alias_name, None)
        # Remove exposed class reference
        cur_mod.DynamicE2ERecursiveRegistry = None

        # Remove temp files
        with contextlib.suppress(OSError):
            shutil.rmtree(str(package_dir), ignore_errors=True)
            if base_dir.exists() and not any(base_dir.iterdir()):
                base_dir.rmdir()

        _DynamicE2ERecursiveRegistry.auto_package = None
        _DynamicE2ERecursiveRegistry.registry_auto_discovery = False
        _DynamicE2ERecursiveRegistry.clear_registry()
        reset_settings()

        # Force garbage collection to purge subclasses of PydanticClassRegistryMixin
        del _DynamicE2ERecursiveRegistry
        gc.collect()

    @pytest.mark.smoke
    def test_contract_and_environment(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(valid_instances, PydanticClassRegistryMixin)
        assert hasattr(valid_instances, "auto_package")
        assert hasattr(valid_instances, "auto_populate_registry")
        assert hasattr(valid_instances, "is_auto_discovery_enabled")
        assert inspect.isroutine(valid_instances.auto_populate_registry)

    @pytest.mark.smoke
    def test_initialization(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Assert correct initial system wiring and session startup state."""
        # Auto-discovery is lazy, so registry should be empty before first access
        assert not valid_instances.registry_populated
        assert len(valid_instances.registry) == 0

    @pytest.mark.sanity
    def test_invalid_initialization_values(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Pass unexpected arguments to verify validation errors."""
        # Trigger discovery first
        valid_instances.auto_populate_registry()
        subclass_type = valid_instances.get_registered_object("DummySubclass")
        assert subclass_type is not None

        with pytest.raises(ValidationError):
            subclass_type(value="not_an_int")

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify that missing mandatory fields raises validation error."""
        # Trigger discovery first
        valid_instances.auto_populate_registry()
        subclass_type = valid_instances.get_registered_object("DummySubclass")
        assert subclass_type is not None

        with pytest.raises(ValidationError):
            subclass_type()

    @pytest.mark.smoke
    def test_lazy_discovery_registered_objects(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify lazy population triggers on calling registered_objects()."""
        # Execute first registry access
        objects = valid_instances.registered_objects()

        # Assert populated
        assert valid_instances.registry_populated
        assert len(objects) > 0
        assert any(obj_type.__name__ == "DummySubclass" for obj_type in objects)

    @pytest.mark.smoke
    def test_lazy_discovery_is_registered(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify lazy population triggers on calling is_registered()."""
        # Execute registry access
        is_reg = valid_instances.is_registered("DummySubclass")
        assert valid_instances.registry_populated
        assert is_reg is True

    @pytest.mark.sanity
    def test_lazy_discovery_get_registered_object(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify lazy population triggers on calling get_registered_object()."""
        # Execute registry access
        obj_class = valid_instances.get_registered_object("DummySubclass")

        # Assert populated
        assert valid_instances.registry_populated
        assert obj_class is not None
        assert obj_class.__name__ == "DummySubclass"

    @pytest.mark.sanity
    def test_disabled_auto_discovery_raises_value_error(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify ValueError is raised if discovery is disabled."""
        # Disable discovery
        valid_instances.registry_auto_discovery = False
        reset_settings()
        settings = get_settings()
        settings.registry_auto_discovery = False

        # Attempting populate throws ValueError
        with pytest.raises(ValueError, match="Auto-population rejected"):
            valid_instances.auto_populate_registry()

    @pytest.mark.sanity
    def test_non_existent_package_raises_import_error(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify scanning a non-existent package raises ImportError."""
        valid_instances.auto_package = "completely_non_existent_pkg_name"

        # If auto-discovery is enabled, first access triggers populate,
        # raising ImportError.
        with pytest.raises(ImportError, match="could not be resolved"):
            valid_instances.registered_objects()

    @pytest.mark.regression
    def test_empty_package_completed_safely(
        self,
        valid_instances: type[PydanticClassRegistryMixin],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify that scanning an empty package completes successfully."""
        base_dir = Path(__file__).parent / "temp_packages_us41"
        base_dir.mkdir(exist_ok=True)

        empty_pkg_name = "temp_empty_pkg_e2e"
        empty_pkg_dir = base_dir / empty_pkg_name
        empty_pkg_dir.mkdir(parents=True, exist_ok=True)
        (empty_pkg_dir / "__init__.py").write_text("", encoding="utf-8")

        valid_instances.auto_package = empty_pkg_name

        # Trigger lazy scanning
        objects = valid_instances.registered_objects()

        # Assert scanned but empty
        assert valid_instances.registry_populated
        assert len(objects) == 0

        # Cleanup sys.modules
        sys.modules.pop(empty_pkg_name, None)

        with contextlib.suppress(OSError):
            shutil.rmtree(str(empty_pkg_dir), ignore_errors=True)

    @pytest.mark.regression
    def test_marshalling(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify model validation and dump boundaries against the dynamic schema."""
        # Trigger discovery first
        valid_instances.auto_populate_registry()

        subclass_type = valid_instances.get_registered_object("DummySubclass")
        assert subclass_type is not None

        # Build payload
        payload = {"dummy_type": "DummySubclass", "value": 123}

        # Validate via base class (uses tagged union)
        validated = valid_instances.model_validate(payload)
        assert isinstance(validated, subclass_type)
        assert validated.value == 123

        # Dump model
        dumped = validated.model_dump()
        assert dumped == payload
