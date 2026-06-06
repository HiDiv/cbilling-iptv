---
description: GitHub repository conventions — SPDX, disclaimer, English-only, conventional commits
inclusion: always
---

# GitHub Repository Conventions

This file describes mandatory rules for maintaining the quality of the public GitHub repository `plugin.video.cbilling.iptv`.

## 1. SPDX License Headers

### Mandatory Requirement

All new and modified Python files (`.py`) **MUST** contain an SPDX header at the very beginning of the file.

### Format

For files authored by HiDiv:
```python
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
```

For files with two authors (Thamerlan + HiDiv):
```python
# SPDX-FileCopyrightText: Thamerlan
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
```

### Exceptions

- Vendored libraries (`resources/lib/vendor/`) — not modified, retain their original licenses
- `__init__.py` files — HiDiv only header

## 2. Disclaimer

### Required Locations

The disclaimer **MUST** be present in three places:

1. **`addon.xml`** — `<disclaimer lang="en">` and `<disclaimer lang="ru">` tags inside `<extension point="xbmc.addon.metadata">`
2. **`README.md`** — "Disclaimer" section with full English text
3. **`DISCLAIMER.md`** — separate file with full text in English and Russian

### Three Disclaimer Areas

Each disclaimer must cover:
- **No Warranty** — the addon is provided "as is" without warranties
- **Limitation of Liability** — authors are not liable for data loss
- **Content** — the addon does not host media content, users are responsible for legal compliance

### When Updating the Disclaimer

If the disclaimer text is updated — update **all three** locations simultaneously.

## 3. Comments and Documentation Language

### Mandatory Requirement

**All comments and documentation in source code — ENGLISH ONLY.**

### What must be in English

- Inline comments (`# comment`)
- Docstrings (`"""docstring"""`)
- TODO / FIXME / HACK comments
- README.md (main)
- CONTRIBUTING.md
- CHANGELOG.md
- SECURITY.md
- CODE_OF_CONDUCT.md
- Issue and PR templates (`.github/`)

### Exceptions (Russian allowed)

- `README.ru.md` — Russian version of README
- `DISCLAIMER.md` — contains Russian translation
- `addon.xml` — tags with `lang="ru"`
- Localization files (`resources/language/resource.language.ru_ru/`)
- UI strings in code intended for Russian-speaking users

## 4. Conventional Commits

### Mandatory Requirement

**All commit messages — ENGLISH ONLY** in Conventional Commits format:

```
type(scope): description
```

### Allowed Types

| Type | When to use |
|------|-------------|
| `feat` | New functionality |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Formatting (does not affect logic) |
| `refactor` | Refactoring (not fix and not feat) |
| `test` | Tests |
| `chore` | Maintenance (build, CI, dependencies) |
| `ci` | CI/CD configuration |

### Rules

- Description starts with lowercase
- No period at the end
- Brief description (up to 72 characters)
- Scope is optional but recommended
- Language — **English only**

### Examples

```bash
# ✅ Correct
git commit -m "feat(vod): add series pagination support"
git commit -m "fix(epg): correct timezone offset calculation"
git commit -m "docs: update README with installation guide"

# ❌ Wrong
git commit -m "исправил баг в EPG"
git commit -m "updated stuff"
```

## 5. Pre-Commit Checklist

Before each commit, verify:

- [ ] New/modified `.py` files contain SPDX header
- [ ] Code comments are in English
- [ ] Commit message is in English in `type(scope): description` format
- [ ] If disclaimer was changed — all three locations are updated
- [ ] `ruff check .` passes with zero errors
- [ ] `ruff format --check .` passes with zero errors
- [ ] `python3 -m pytest tests/ --tb=short` — all tests pass
