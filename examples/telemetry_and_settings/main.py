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

"""Telemetry and Settings example entrypoint.

This script demonstrates:
1. Loading configuration options from a pyproject.toml configuration file.
2. The settings resolution order (Constructor > Environment > pyproject.toml).
3. Defining a polymorphic registry that falls back to the configured
   default_schema_discriminator from pyproject.toml.
4. Setting up structured JSON telemetry logging with OpenTelemetry formatting.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from disdantic.logging import LoggingSettings, autolog, configure_logger, logger
from disdantic.model import ReloadableBaseModel
from disdantic.registry import PydanticClassRegistryMixin
from disdantic.settings import Settings, get_settings, reset_settings

__all__ = ["BaseTask", "EmailTask", "SMSTask", "main", "process_data"]


# 1. Define a Polymorphic Registry that falls back to settings.
class BaseTask(PydanticClassRegistryMixin, ReloadableBaseModel):
    """Base polymorphic task model.

    This class does not define a class-level 'schema_discriminator' attribute.
    Instead, it dynamically falls back to the 'default_schema_discriminator'
    configured in the active Settings.
    """


@BaseTask.register("email")
class EmailTask(BaseTask):
    """Email notification task."""

    custom_type: Literal["email"] = "email"
    recipient: str
    body: str


@BaseTask.register("sms")
class SMSTask(BaseTask):
    """SMS notification task."""

    custom_type: Literal["sms"] = "sms"
    phone_number: str
    message: str


# 2. Decorate a function with autolog for telemetry hooks (US-11)
@autolog
def process_data(value: int) -> int:
    """Process a data value and double it.

    Logs entry, exit, and raises ValueError if the value is negative.
    """
    if value < 0:
        raise ValueError("Value cannot be negative!")
    return value * 2


def load_dotenv(env_path: Path) -> None:
    """Load variables from a .env file into os.environ.

    This is used to simulate environment-based priority configurations.
    """
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


def main() -> None:
    """Execute the settings resolution and logging telemetry workflow."""
    # Isolate project root to this directory to load the local pyproject.toml
    example_root = Path(__file__).parent.resolve()
    os.chdir(example_root)
    os.environ["DISDANTIC__PROJECT_ROOT"] = str(example_root)

    # Load local dotenv variables to simulate environment variable overrides
    load_dotenv(example_root / ".env")

    # 1. Reset settings to force a fresh load of our isolated project config
    reset_settings()

    # 2. Verify settings resolution pathways (US-12)
    # default context should load DISDANTIC__ENVIRONMENT=staging from the local .env
    # and default_schema_discriminator=custom_type from pyproject.toml
    settings = get_settings()
    print(f"Loaded Settings Environment: {settings.environment}")
    print(f"Loaded Discriminator from TOML: {settings.default_schema_discriminator}")

    # Rebuild BaseTask schema so it picks up the newly loaded settings discriminator key
    BaseTask.reload_schema()

    # Verify that the registry class correctly resolved the discriminator key
    discriminator_key = BaseTask.get_schema_discriminator()
    print(f"Registry resolved discriminator key: {discriminator_key}")

    # Validate model deserialization using the fallback discriminator key
    email_payload = {
        "custom_type": "email",
        "recipient": "user@example.com",
        "body": "Your disdantic build is passing!",
    }
    validated_task = BaseTask.model_validate(email_payload)
    print(f"Successfully validated task type: {type(validated_task).__name__}")

    # Verify constructor override has highest priority
    override_settings = Settings(environment="production")
    print(f"Overridden Settings Environment: {override_settings.environment}")

    # 3. Configure structured logging with OpenTelemetry formatting
    logging_config = LoggingSettings(
        enabled=True,
        level="DEBUG",
        otel_formatting="enable",
        clear_loggers=True,
        filter=None,
        sink=sys.stderr,
        enqueue=False,
    )
    configure_logger(logging_config)

    # 4. Trigger autolog events
    try:
        logger.info("Starting calculation cycle...")
        result = process_data(10)
        logger.info(f"Calculation output: {result}")

        # Test error logging telemetry
        process_data(-5)
    except ValueError:
        logger.warning("Caught expected telemetry exception.")


if __name__ == "__main__":
    main()
