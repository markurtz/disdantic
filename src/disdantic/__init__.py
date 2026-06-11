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
Core initialization module for the disdantic package.

This module serves as the primary entry point for the library, exposing the public
API components such as logging settings, application configuration, and version
metadata for convenient access by downstream consumers.
"""

from __future__ import annotations

from .logging import LoggingSettings, configure_logger, logger
from .settings import Settings
from .version import __version__

__all__ = [
    "LoggingSettings",
    "Settings",
    "__version__",
    "configure_logger",
    "logger",
]

configure_logger()
