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

"""E2E tests for US-4.2: Module Ignoring & Exclusions."""

from __future__ import annotations

import contextlib
import gc
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
DynamicE2EIgnoringRegistry: Any = None


class TestModuleIgnoringAndExclusions:
    """E2E test suite for US-4.2: Module Ignoring & Exclusions."""

    @pytest.fixture(params=["class_ignore", "settings_ignore", "merged_ignore"])
    def valid_instances(
        self, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[type[PydanticClassRegistryMixin], None, None]:
        """Supply isolated registry classes configured with different ignore rules."""
        # Create a unique temporary package inside the workspace to avoid conflicts.
        base_dir = Path(__file__).parent / "temp_packages_us42"
        base_dir.mkdir(exist_ok=True)

        package_name = f"temp_ignore_pkg_{request.param}"
        package_dir = base_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Write __init__.py
        init_file = package_dir / "__init__.py"
        init_file.write_text("", encoding="utf-8")

        # Write submodule_valid.py
        valid_sub = package_dir / "submodule_valid.py"
        valid_sub.write_text(
            """from __future__ import annotations
from typing import Literal
from tests.e2e.test_module_ignoring_and_exclusions import (
    DynamicE2EIgnoringRegistry,
)

@DynamicE2EIgnoringRegistry.register("ValidSubclass")
class ValidSubclass(DynamicE2EIgnoringRegistry):
    ignoring_type: Literal["ValidSubclass"] = "ValidSubclass"
    value: int
""",
            encoding="utf-8",
        )

        # Write submodule_ignored_class.py
        ignored_class_sub = package_dir / "submodule_ignored_class.py"
        ignored_class_sub.write_text(
            """from __future__ import annotations
from typing import Literal
from tests.e2e.test_module_ignoring_and_exclusions import (
    DynamicE2EIgnoringRegistry,
)

@DynamicE2EIgnoringRegistry.register("IgnoredClassSubclass")
class IgnoredClassSubclass(DynamicE2EIgnoringRegistry):
    ignoring_type: Literal["IgnoredClassSubclass"] = "IgnoredClassSubclass"
    value: int
""",
            encoding="utf-8",
        )

        # Write submodule_ignored_settings.py
        ignored_settings_sub = package_dir / "submodule_ignored_settings.py"
        ignored_settings_sub.write_text(
            """from __future__ import annotations
from typing import Literal
from tests.e2e.test_module_ignoring_and_exclusions import (
    DynamicE2EIgnoringRegistry,
)

@DynamicE2EIgnoringRegistry.register("IgnoredSettingsSubclass")
class IgnoredSettingsSubclass(DynamicE2EIgnoringRegistry):
    ignoring_type: Literal["IgnoredSettingsSubclass"] = "IgnoredSettingsSubclass"
    value: int
""",
            encoding="utf-8",
        )

        # Prep path
        monkeypatch.syspath_prepend(str(base_dir))
        reset_settings()

        # Build dynamic registry base
        class _DynamicE2EIgnoringRegistry(PydanticClassRegistryMixin):
            """Base registry used for US-4.2 E2E tests."""

            schema_discriminator = "ignoring_type"
            ignoring_type: str

        _DynamicE2EIgnoringRegistry.auto_package = package_name
        _DynamicE2EIgnoringRegistry.registry_auto_discovery = True

        # Configure ignores
        class_ignores = []
        settings_ignores = []

        if request.param == "class_ignore":
            class_ignores = [f"{package_name}.submodule_ignored_class"]
        elif request.param == "settings_ignore":
            settings_ignores = [f"{package_name}.submodule_ignored_settings"]
        elif request.param == "merged_ignore":
            class_ignores = [f"{package_name}.submodule_ignored_class"]
            settings_ignores = [f"{package_name}.submodule_ignored_settings"]

        _DynamicE2EIgnoringRegistry.auto_ignore_modules = class_ignores
        settings = get_settings()
        settings.auto_ignore_modules = settings_ignores

        # Expose class on module level dynamically so the submodules can import it
        cur_mod = cast("Any", sys.modules[__name__])
        cur_mod.DynamicE2EIgnoringRegistry = _DynamicE2EIgnoringRegistry

        yield _DynamicE2EIgnoringRegistry

        # Cleanup sys.modules
        for key in list(sys.modules.keys()):
            if key == package_name or key.startswith(f"{package_name}."):
                sys.modules.pop(key, None)

        # Remove exposed class reference
        cur_mod.DynamicE2EIgnoringRegistry = None

        # Remove temp files
        with contextlib.suppress(OSError):
            shutil.rmtree(str(package_dir), ignore_errors=True)
            if base_dir.exists() and not any(base_dir.iterdir()):
                base_dir.rmdir()

        _DynamicE2EIgnoringRegistry.auto_package = None
        _DynamicE2EIgnoringRegistry.auto_ignore_modules = None
        _DynamicE2EIgnoringRegistry.registry_auto_discovery = False
        _DynamicE2EIgnoringRegistry.clear_registry()
        reset_settings()

        # Force garbage collection to purge subclasses of PydanticClassRegistryMixin
        del _DynamicE2EIgnoringRegistry
        gc.collect()

    @pytest.mark.smoke
    def test_contract_and_environment(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Validate structural environment contracts before firing user actions."""
        assert issubclass(valid_instances, PydanticClassRegistryMixin)
        assert hasattr(valid_instances, "auto_package")
        assert hasattr(valid_instances, "auto_ignore_modules")
        assert hasattr(valid_instances, "auto_populate_registry")

    @pytest.mark.smoke
    def test_initialization(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Assert correct initial system wiring and session startup state."""
        assert not valid_instances.registry_populated
        assert len(valid_instances.registry) == 0

    @pytest.mark.sanity
    def test_invalid_initialization_values(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Pass unexpected arguments to verify validation errors."""
        valid_instances.auto_populate_registry()
        subclass_type = valid_instances.get_registered_object("ValidSubclass")
        assert subclass_type is not None

        with pytest.raises(ValidationError):
            subclass_type(value="not_an_int")

    @pytest.mark.sanity
    def test_invalid_initialization_missing(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify that missing mandatory fields raises validation error."""
        valid_instances.auto_populate_registry()
        subclass_type = valid_instances.get_registered_object("ValidSubclass")
        assert subclass_type is not None

        with pytest.raises(ValidationError):
            subclass_type()

    @pytest.mark.smoke
    def test_module_ignoring_behavior(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify that ignores are correctly handled during auto-discovery."""
        # Trigger discovery
        valid_instances.auto_populate_registry()

        # ValidSubclass should always be registered
        assert valid_instances.is_registered("ValidSubclass")

        # Check ignores depending on parameters
        ignores = set(valid_instances.auto_ignore_modules or [])
        ignores.update(get_settings().auto_ignore_modules)

        package_name = valid_instances.auto_package

        if f"{package_name}.submodule_ignored_class" in ignores:
            assert not valid_instances.is_registered("IgnoredClassSubclass")
        else:
            assert valid_instances.is_registered("IgnoredClassSubclass")

        if f"{package_name}.submodule_ignored_settings" in ignores:
            assert not valid_instances.is_registered("IgnoredSettingsSubclass")
        else:
            assert valid_instances.is_registered("IgnoredSettingsSubclass")

    @pytest.mark.regression
    def test_marshalling(
        self, valid_instances: type[PydanticClassRegistryMixin]
    ) -> None:
        """Verify model validation and dump boundaries against the dynamic schema."""
        valid_instances.auto_populate_registry()

        subclass_type = valid_instances.get_registered_object("ValidSubclass")
        assert subclass_type is not None

        # Build payload
        payload = {"ignoring_type": "ValidSubclass", "value": 456}

        # Validate via base class (uses tagged union)
        validated = valid_instances.model_validate(payload)
        assert isinstance(validated, subclass_type)
        assert validated.value == 456

        # Dump model
        dumped = validated.model_dump()
        assert dumped == payload
