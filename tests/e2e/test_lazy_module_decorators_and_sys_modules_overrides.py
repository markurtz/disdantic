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

"""End-to-end tests for Lazy Module Decorators & sys.modules Overrides (US-6.2)."""

from __future__ import annotations

import importlib
import sys
import types
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from disdantic.loading import LazyLoader
from disdantic.registry import RegistryMixin


class TestLazyModuleDecoratorsAndSysModulesOverrides:
    """E2E test suite validating lazy module decorators and overrides."""

    @pytest.fixture(params=["lazy_mock_pkg_alpha", "lazy_mock_pkg_beta"])
    def valid_instances(
        self, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[tuple[str, types.ModuleType], None, None]:
        """Provide isolated mock package names and module objects for E2E tests."""
        package_name = request.param
        mock_package = types.ModuleType(package_name)
        monkeypatch.setitem(sys.modules, package_name, mock_package)

        yield package_name, mock_package

        if package_name in sys.modules:
            del sys.modules[package_name]

    @pytest.mark.smoke
    def test_contract_and_environment(
        self,
        valid_instances: tuple[str, types.ModuleType],
    ) -> None:
        """Validate structural environment contracts of LazyLoader."""
        _package_name, _mock_package = valid_instances
        assert hasattr(LazyLoader, "module")
        assert hasattr(LazyLoader, "class_attributes")
        assert hasattr(LazyLoader, "definition")
        assert hasattr(LazyLoader, "load_module_proxy")

    @pytest.mark.smoke
    def test_initialization(
        self,
        valid_instances: tuple[str, types.ModuleType],
    ) -> None:
        """Verify lazy module decorator overrides sys.modules on initialization."""
        package_name, mock_package = valid_instances
        decorator = LazyLoader.module(package_name)
        lazy_module = decorator(mock_package)

        assert sys.modules[package_name] is lazy_module
        assert type(lazy_module).__name__ == "LazyModule"

    @pytest.mark.sanity
    def test_invalid_initialization_values(self) -> None:
        """Verify explicit system blockages when invalid import targets are specified.

        Expect ModuleNotFoundError when loading a completely fictional module.
        """
        with pytest.raises(ModuleNotFoundError):
            LazyLoader.load_module_proxy("non_existent_module_path_abc_123")

    @pytest.mark.sanity
    def test_invalid_initialization_missing(self) -> None:
        """Verify default constructors/methods raise TypeError on missing arguments.

        Ensure validation checks boundaries when parameters are omitted.
        """
        with pytest.raises(TypeError):
            LazyLoader.load_module_proxy()  # type: ignore
        with pytest.raises(TypeError):
            LazyLoader.module()  # type: ignore

    @pytest.mark.sanity
    def test_module_attributes_lazy_load(
        self,
        valid_instances: tuple[str, types.ModuleType],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Assert submodules are imported dynamically only upon querying attributes."""
        package_name, mock_package = valid_instances
        decorator = LazyLoader.module(package_name)
        lazy_module = decorator(mock_package)

        submodule_name = f"{package_name}.sub_element"
        mock_submodule: Any = types.ModuleType(submodule_name)
        mock_submodule.val_test = "resolved_value"

        import_calls: list[str] = []

        def mock_import(name: str) -> types.ModuleType:
            import_calls.append(name)
            if name == submodule_name:
                return mock_submodule
            raise ImportError(f"No module named {name}")

        monkeypatch.setattr(importlib, "import_module", mock_import)

        assert len(import_calls) == 0

        resolved_attr = lazy_module.sub_element
        assert resolved_attr is mock_submodule
        assert resolved_attr.val_test == "resolved_value"
        assert import_calls == [submodule_name]

    @pytest.mark.sanity
    def test_load_module_proxy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test loading a module lazily using load_module_proxy."""
        temp_dir = tmp_path / "custom_dir"
        temp_dir.mkdir()
        module_file = temp_dir / "my_lazy_test_module.py"
        module_file.write_text("DUMMY_VAR = 'correct_data'\n")

        monkeypatch.syspath_prepend(str(temp_dir))
        monkeypatch.delitem(sys.modules, "my_lazy_test_module", raising=False)

        lazy_module = LazyLoader.load_module_proxy("my_lazy_test_module")
        assert "my_lazy_test_module" in sys.modules

        assert lazy_module.DUMMY_VAR == "correct_data"

    @pytest.mark.regression
    def test_class_attributes_binding(self) -> None:
        """Verify class attributes bind lazy property descriptors to target class."""
        call_count = 0

        def test_factory() -> str:
            nonlocal call_count
            call_count += 1
            return "lazy_value"

        @LazyLoader.class_attributes(
            {
                "math_module": "math",
                "fact_val": test_factory,
            }
        )
        class TargetClass:
            math_module: Any
            fact_val: Any

        instance = TargetClass()
        assert call_count == 0

        assert instance.math_module is sys.modules["math"]
        assert instance.fact_val == "lazy_value"
        assert call_count == 1

        assert instance.fact_val == "lazy_value"
        assert call_count == 1

    @pytest.mark.sanity
    def test_marshalling(self) -> None:
        """Verify Pydantic model serialization and deserialization boundaries."""

        class TestModel(BaseModel):
            name: str
            data: list[str]

        call_count = 0

        def model_factory() -> TestModel:
            nonlocal call_count
            call_count += 1
            return TestModel(name="lazy_model", data=["alpha", "beta"])

        model_proxy = LazyLoader.definition(model_factory)
        assert call_count == 0

        dumped = model_proxy.model_dump()
        assert call_count == 1
        assert dumped["name"] == "lazy_model"
        assert dumped["data"] == ["alpha", "beta"]

        validated = TestModel.model_validate(dumped)
        assert isinstance(validated, TestModel)
        assert validated.name == "lazy_model"

    @pytest.mark.sanity
    def test_dynamic_resolution(self) -> None:
        """Verify dynamic resolution under dynamic registries with lazy decorators."""

        class CustomRegistry(RegistryMixin[type]):
            """Dynamic registry for lazy module testing."""

        def class_factory() -> type:

            @CustomRegistry.register("resolved_target")
            class ResolvedClass:
                def speak(self) -> str:
                    return "hello"

            return ResolvedClass

        @LazyLoader.class_attributes({"target_class": class_factory})
        class Runner:
            target_class: Any

        runner_instance = Runner()
        assert CustomRegistry.is_registered("resolved_target") is False

        resolved_class = runner_instance.target_class
        assert CustomRegistry.is_registered("resolved_target") is True
        assert CustomRegistry.get_registered_object("resolved_target") is resolved_class

        CustomRegistry.clear_registry()
