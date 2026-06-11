<!--
Copyright 2026 markurtz

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/markurtz/disdantic/main/docs/assets/branding/logo-white.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/markurtz/disdantic/main/docs/assets/branding/logo-black.svg">
    <img alt="disdantic Logo" src="https://raw.githubusercontent.com/markurtz/disdantic/main/docs/assets/branding/logo-black.svg" width="400">
  </picture>
</p>

<p align="center">
  <em>A lightweight collection of utilities and mixins for Pydantic.</em>
</p>

<p align="center">
  <!-- Package & Release Status -->
  <a href="https://github.com/markurtz/disdantic/releases">
    <img src="https://img.shields.io/github/v/release/markurtz/disdantic?label=Release" alt="GitHub Release">
  </a>
  <a href="https://pypi.org/project/disdantic/">
    <img src="https://img.shields.io/pypi/v/disdantic?label=PyPI" alt="PyPI Release">
  </a>
  <a href="https://pypi.org/project/disdantic/">
    <img src="https://img.shields.io/pypi/pyversions/disdantic?label=Python" alt="Supported Python Versions">
  </a>
  <br/>
  <!-- CI/CD & Build Status -->
  <a href="https://github.com/markurtz/disdantic/actions/workflows/main.yml">
    <img src="https://github.com/markurtz/disdantic/actions/workflows/main.yml/badge.svg" alt="CI Status">
  </a>
  <br/>
  <!-- Issues & Support -->
  <a href="https://github.com/markurtz/disdantic/issues?q=is%3Aissue+is%3Aopen">
    <img src="https://img.shields.io/github/issues/markurtz/disdantic?label=Issues%20Open" alt="Open Issues">
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License">
  </a>
</p>

<p align="center">
  <a href="https://markurtz.github.io/disdantic/">Documentation</a> |
  <a href="https://github.com/markurtz/disdantic/milestones">Roadmap</a> |
  <a href="https://github.com/markurtz/disdantic/issues">Issues</a> |
  <a href="https://github.com/markurtz/disdantic/discussions">Discussions</a>
</p>

______________________________________________________________________

## Overview

Welcome to the disdantic repository!

### Why Use disdantic?

Coming soon!

### Comparisons

Coming soon!

## What's New

**Welcome to the disdantic Launch!**

This project has just been instantiated from the template repository. Keep an eye on this section for future release highlights, new features, and community announcements!

<!-- Once your project is active, replace the launch message above with links to your latest release notes or top 3 new features here. -->

## Quick Start

Coming soon!

## Core Concepts

This project is built using modern Python tooling, enforcing strict code quality standards with Ruff and Astral's ty, and providing a robust Pydantic-driven settings architecture for configuration resolution.

### Component Architecture

The repository is structured to separate documentation, application logic, and testing cleanly:

- `src/disdantic/`: The primary application source code.
- `tests/`: Comprehensive test suite ensuring reliability, organized into `python/unit/`, `python/integration/`, and `e2e/`.
- `docs/`: Source code for the Zensical documentation site, including step-by-step guides, references, and getting started tutorials.
- `examples/`: Runnable reference projects demonstrating real-world configurations.
- `.github/workflows/`: Advanced CI/CD pipelines governing the project lifecycle, built around reusable workflow templates.

## Advanced Usage

Please check the [`examples/`](https://github.com/markurtz/disdantic/tree/main/examples/) directory for advanced examples and configurations.

## General

### Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/markurtz/disdantic/blob/main/CONTRIBUTING.md) for more details. For development setup, check out [DEVELOPING.md](https://github.com/markurtz/disdantic/blob/main/DEVELOPING.md).
Please ensure you follow our [Code of Conduct](https://github.com/markurtz/disdantic/blob/main/CODE_OF_CONDUCT.md) in all interactions.

### Support and Security

- For help and general questions, see [SUPPORT.md](https://github.com/markurtz/disdantic/blob/main/SUPPORT.md).
- To report a security vulnerability, please refer to our [Security Policy](https://github.com/markurtz/disdantic/blob/main/SECURITY.md).

### AI & LLM Tooling

This repository includes first-class support for agentic and LLM-assisted development workflows:

- **[AGENTS.md](https://github.com/markurtz/disdantic/blob/main/AGENTS.md):** Repository-specific instructions for AI coding agents (Codex, Copilot Workspace, Gemini, Claude, Cursor, and similar tools). Contains the authoritative guide for project structure, executable commands, code style, and critical constraints.
- **[llms.txt](https://github.com/markurtz/disdantic/blob/main/llms.txt):** A machine-readable index of the project's documentation, following the [llms.txt specification](https://llmstxt.org/). Served at `/llms.txt` on the documentation site to help LLMs quickly locate and consume relevant content.

### License

This project is licensed under the Apache License 2.0. See the [LICENSE](https://github.com/markurtz/disdantic/blob/main/LICENSE) file for details.

### Citations

If you use this repository or the resulting software in your research, please cite it using the following BibTeX entry:

```bibtex
@software{disdantic,
  author = {markurtz},
  title = {disdantic},
  year = 2026,
  url = {https://github.com/markurtz/disdantic}
}
```
