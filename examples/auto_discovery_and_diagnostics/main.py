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

"""
Main execution script for the Auto-Discovery and Diagnostics example.
"""

from __future__ import annotations

from disdantic.diagnose import verify_registries
from disdantic.registry import RegistryManager
from disdantic.settings import get_settings
from examples.auto_discovery_and_diagnostics.core_registry import PluginRegistry


def main() -> None:
    """
    Execute the auto-discovery, registry listing, and diagnostics report workflow.
    """
    # 1. Programmatic Discovery & Importing
    # Set the target package dynamically
    PluginRegistry.auto_package = "examples.auto_discovery_and_diagnostics.plugins"

    # We ignore the broken_plugin to perform a healthy discovery pass first
    PluginRegistry.auto_ignore_modules = [
        "examples.auto_discovery_and_diagnostics.plugins.broken_plugin"
    ]
    PluginRegistry.auto_import_package_modules()

    # 2. List Active Registries
    registries = RegistryManager.list_registries()
    print("Discovered Registries:", registries)

    # 3. Diagnostics Run
    # Reset ignore list and importer cache to include the broken plugin
    # to test diagnostics
    PluginRegistry.reset_importer_cache()
    PluginRegistry.auto_ignore_modules = []

    # Run audit diagnostics
    settings = get_settings()
    report = verify_registries(settings=settings)
    print(f"Diagnostics Health: {'Healthy' if report.is_healthy else 'Unhealthy'}")

    for registry_report in report.registries:
        print(f"Registry: {registry_report.registry_name}")
        for model_report in registry_report.models:
            print(
                f"  - Model '{model_report.key}': "
                f"status={model_report.compilation_status}"
            )
            if model_report.error_detail:
                # Format the error message slightly to match signature
                print(f"    Error: {model_report.error_detail}")


if __name__ == "__main__":
    main()
