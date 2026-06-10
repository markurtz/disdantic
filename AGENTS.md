# AGENTS.md — AI Agent & Coding Assistant Guide

> **This file provides repository-specific instructions to AI coding agents** (e.g., OpenAI Codex, GitHub Copilot, Gemini, Claude, Cursor).
> Human contributors should refer to [DEVELOPING.md](DEVELOPING.md).

## Project Context

**`template-python`** is a production-ready Apache 2.0 template repository for bootstrapping modern software projects.
**Primary language:** `Python 3.10+`\
**Package manager:** `Hatch`

## Critical Constraints

> [!CAUTION]
>
> 1. **Never commit secrets.** Do not add API keys, tokens, or credentials anywhere.
> 1. **Do not modify `LICENSE` or `NOTICE`.** These are legally binding.
> 1. **Do not modify workflow trigger conditions** without human review.
> 1. **All new source files must include the Apache 2.0 copyright header.**
> 1. **Use `{{double_braces}}` for template placeholders.** Never hard-code them.

## Repository Layout

- `.github/workflows/`: CI/CD pipelines. Files prefixed with `_` are reusable templates.
- `docs/`: MkDocs Material source.
- `src/`: Primary application source code.
- `tests/`: Organized into `unit/`, `integration/`, and `e2e/`.

## Executable Commands

- **Linting:** `hatch run lint:check` (Ruff & mdformat) and `hatch run types:check` (Mypy)
- **Pre-commit:** `pre-commit run --all-files` (Runs formatting and quality checks)
- **Testing:** `hatch run test:all` (Pytest) and `hatch run test:all-cov` (Coverage)
- **Docs:** `hatch run docs:serve` / `hatch run docs:build`
- **Build:** `hatch build`

## Code Style & Patterns

- **No magic strings or numbers** — define constants.
- **Prefer explicit over implicit.**
- **One responsibility per module.**
- Every public function, class, and module must have a docstring.
- Follow [Conventional Commits](https://www.conventionalcommits.org/).

## GitHub Actions Workflows

- **Reusable Templates (`_*.yml`):** Never trigger directly. Ensure changes are backward-compatible.
- **Lifecycle:**
  - `development.yml`: PR open/sync (unit + smoke)
  - `main.yml`: Push to `main` (unit + integration + sanity)
  - `nightly.yml`, `weekly.yml`, `release.yml`: Standard scheduled/release flows.

## Documentation

- **`docs/`** and **`mkdocs.yml`** control the site. Do not create docs outside the `nav:` tree.
- `docs/index.md` dynamically includes `README.md` via MkDocs snippets.
- Use `{{placeholder}}` variables for templated fields (e.g., `template-python`, `markurtz`).

## Agent Notes

_Add notes here when updating instructions for AI agents._
