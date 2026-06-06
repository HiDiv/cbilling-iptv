# Contributing to Cbilling.TV IPTV

Thank you for your interest in contributing! This document explains how to get involved.

## Getting Started

1. Fork the repository.
2. Clone your fork locally.
3. Create a feature branch from `develop` (see [Branch Naming](#branch-naming)).
4. Make your changes.
5. Run linting and tests (see [Development Workflow](#development-workflow)).
6. Open a pull request against `develop`.

## Branch Naming

Use the following prefixes:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/epg-improvements` |
| `fix/` | Bug fixes | `fix/vod-pagination` |
| `docs/` | Documentation changes | `docs/update-readme` |

## Commit Messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/). All commit messages must be in English.

Format: `type(scope): description`

**Types:**

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructuring |
| `test` | Adding or updating tests |
| `chore` | Build, CI, or tooling changes |
| `ci` | CI/CD configuration |

**Examples:**

```
feat(vod): add watch history feature
fix(epg): correct timezone handling for cached entries
docs: update installation instructions
test: add unit tests for api_adapter
chore(lint): configure ruff ignore rules
```

## Coding Standards

### Language

- All code comments must be in **English**.
- All commit messages must be in **English**.
- Documentation files are in English (with Russian translations where provided).

### Linting and Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check for lint errors
ruff check .

# Auto-format code
ruff format .
```

Key settings (from `pyproject.toml`):
- Target: Python 3.8
- Line length: 120 characters
- Quote style: double quotes

### SPDX License Headers

All new or modified Python files must include SPDX headers:

```python
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
```

### Python Compatibility

The addon must remain compatible with **Python 3.8** (Kodi 19 Matrix). Avoid:

- PEP 585 generics in annotations (`list[str]` — use `List[str]` from `typing`)
- PEP 604 union syntax (`str | None` — use `Optional[str]` from `typing`)
- Walrus operator (`:=`)
- `match` / `case` statements

## Development Workflow

### Running Tests

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run all tests
python3 -m pytest tests/

# Run with coverage
python3 -m pytest tests/ --cov=resources/lib --cov-report=term-missing
```

### Before Submitting a PR

1. Run `ruff check .` — must produce zero errors.
2. Run `ruff format --check .` — must report no differences.
3. Run `python3 -m pytest tests/` — all tests must pass.
4. Verify SPDX headers are present in any new or modified `.py` files.

## Pull Request Process

1. Fill out the PR template completely.
2. Ensure CI checks pass (lint, test, addon-check).
3. Keep PRs focused — one feature or fix per PR.
4. Update documentation if your change affects user-facing behavior.
5. A maintainer will review and merge your PR.

## Reporting Issues

Use the [GitHub issue templates](https://github.com/HiDiv/cbilling-iptv/issues/new/choose) to report bugs or request features. Include Kodi version, OS, and relevant log output when reporting bugs.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.
