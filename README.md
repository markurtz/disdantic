<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/markurtz/template-python/main/docs/assets/branding/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/markurtz/template-python/main/docs/assets/branding/logo-light.svg">
    <img alt="template-python Logo" src="https://raw.githubusercontent.com/markurtz/template-python/main/docs/assets/branding/logo-light.svg" width="400">
  </picture>
</p>

<p align="center">
  <em>An opinionated, production-ready Apache 2.0 template repository for bootstrapping modern software projects.</em>
</p>

<p align="center">
  <!-- Package & Release Status -->
  <a href="https://github.com/markurtz/template-python/releases">
    <img src="https://img.shields.io/github/v/release/markurtz/template-python?label=Release" alt="GitHub Release">
  </a>
<!--   <a href="https://pypi.org/project/template-python/">
    <img src="https://img.shields.io/pypi/v/template-python?label=PyPI" alt="PyPI Release">
  </a> -->

<!--   <a href="https://pypi.org/project/template-python/">
    <img src="https://img.shields.io/pypi/pyversions/template-python?label=Python" alt="Supported Python Versions">
  </a> -->

<br/>
  <!-- CI/CD & Build Status -->
  <a href="https://github.com/markurtz/template-python/actions/workflows/main.yml">
    <img src="https://github.com/markurtz/template-python/actions/workflows/main.yml/badge.svg" alt="CI Status">
  </a>
  <br/>
  <!-- Issues & Support -->
  <a href="https://github.com/markurtz/template-python/issues?q=is%3Aissue+is%3Aclosed">
    <img src="https://img.shields.io/github/issues-closed/markurtz/template-python?label=Issues%20Closed" alt="Closed Issues">
  </a>
  <a href="https://github.com/markurtz/template-python/issues?q=is%3Aissue+is%3Aopen">
    <img src="https://img.shields.io/github/issues/markurtz/template-python?label=Issues%20Open" alt="Open Issues">
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License">
  </a>
</p>

<p align="center">
  <a href="https://markurtz.github.io/template-python">Documentation</a> |
  <a href="https://github.com/markurtz/template-python/milestones">Roadmap</a> |
  <a href="https://github.com/markurtz/template-python/issues">Issues</a> |
  <a href="https://github.com/markurtz/template-python/discussions">Discussions</a>
</p>

______________________________________________________________________

## Overview

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/markurtz/template-python/main/docs/assets/branding/user-flow-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/markurtz/template-python/main/docs/assets/branding/user-flow-light.svg">
    <img alt="User Flow Diagram" src="https://raw.githubusercontent.com/markurtz/template-python/main/docs/assets/branding/user-flow-light.svg" width="800">
  </picture>
</p>

Welcome to the template-python template repository! This template provides a robust foundation for building high-quality, scalable software projects. It includes standard directories, issue templates, CI/CD workflows, and comprehensive placeholder documentation.

To use this template, run the included `scripts/bootstrap.py` script via `uv run` to automatically replace all placeholder variables with your project details. For full setup instructions including GitHub settings, publishing, and docs, see the **[Repository Setup Guide](https://markurtz.github.io/template-python/guides/repository-setup/)**.

### Why Use template-python?

- **Consistency:** Enforces a standardized layout and structure across your organization's repositories.
- **Speed:** Bootstraps your project with pre-configured Actions, badges, and templates so you don't start from scratch.
- **Best Practices:** Baked-in guides for contributing, security, and developer setup.

### Comparisons

When evaluating template-python against other templates, consider the following differences:

| Feature            | template-python Template                                                                                   | Standard GitHub Init | Cookiecutter / Copier      |
| :----------------- | :--------------------------------------------------------------------------------------------------------- | :------------------- | :------------------------- |
| **Setup Speed**    | Very Fast                                                                                                  | Fast                 | Slower (requires CLI tool) |
| **Visual Assets**  | Pre-configured Light/Dark assets                                                                           | None                 | Varies                     |
| **CI/CD Built-in** | Yes (GitHub Actions)                                                                                       | No                   | Optional                   |
| **Complexity**     | Low ([`scripts/bootstrap.py`](https://github.com/markurtz/template-python/blob/main/scripts/bootstrap.py)) | None                 | Medium (Jinja templates)   |

## What's New

**Welcome to the template-python Launch!**

This project has just been instantiated from the template repository. Keep an eye on this section for future release highlights, new features, and community announcements!

<!-- Once your project is active, replace the launch message above with links to your latest release notes or top 3 new features here. -->

## Quick Start

```bash
uv run scripts/bootstrap.py
```

The script will interactively prompt you for your project details (organization, project name, descriptions, and feature toggles) and automatically configure the repository.

For full setup instructions including GitHub settings, publishing, and docs, see the **[Repository Setup Guide](https://markurtz.github.io/template-python/guides/repository-setup/)**.

## Core Concepts

This project is built using modern Python tooling, enforcing strict code quality standards with Ruff and Mypy, and providing a robust Pydantic-driven settings architecture for configuration resolution.

### Component Architecture

The repository is structured to separate documentation, application logic, and testing cleanly:

- `src/template_python/`: The primary application source code.
- `tests/`: Comprehensive test suite ensuring reliability, organized into `unit/`, `integration/`, and `e2e/`.
- `docs/`: Source code for the MkDocs Material documentation site, including step-by-step guides, references, and getting started tutorials.
- `examples/`: Runnable reference projects demonstrating real-world configurations.
- `.github/workflows/`: Advanced CI/CD pipelines governing the project lifecycle, built around reusable workflow templates.

## Advanced Usage

Please check the [`examples/`](https://github.com/markurtz/template-python/tree/main/examples/) directory for advanced examples and configurations.

## General

### Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/markurtz/template-python/blob/main/CONTRIBUTING.md) for more details. For development setup, check out [DEVELOPING.md](https://github.com/markurtz/template-python/blob/main/DEVELOPING.md).
Please ensure you follow our [Code of Conduct](https://github.com/markurtz/template-python/blob/main/CODE_OF_CONDUCT.md) in all interactions.

### Support and Security

- For help and general questions, see [SUPPORT.md](https://github.com/markurtz/template-python/blob/main/SUPPORT.md).
- To report a security vulnerability, please refer to our [Security Policy](https://github.com/markurtz/template-python/blob/main/SECURITY.md).

### AI & LLM Tooling

This repository includes first-class support for agentic and LLM-assisted development workflows:

- **[AGENTS.md](https://github.com/markurtz/template-python/blob/main/AGENTS.md):** Repository-specific instructions for AI coding agents (Codex, Copilot Workspace, Gemini, Claude, Cursor, and similar tools). Contains the authoritative guide for project structure, executable commands, code style, and critical constraints.
- **[llms.txt](https://github.com/markurtz/template-python/blob/main/llms.txt):** A machine-readable index of the project's documentation, following the [llms.txt specification](https://llmstxt.org/). Served at `/llms.txt` on the documentation site to help LLMs quickly locate and consume relevant content.

### License

This project is licensed under the Apache License 2.0. See the [LICENSE](https://github.com/markurtz/template-python/blob/main/LICENSE) file for details.

### Citations

If you use this template or the resulting software in your research, please cite it using the following BibTeX entry:

```bibtex
@software{template-python,
  author = {markurtz},
  title = {template-python},
  year = {{year}},
  url = {https://github.com/markurtz/template-python}
}
```
