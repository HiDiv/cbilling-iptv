# Technical Debt: Lint Rule Exceptions

This document tracks all Ruff lint rules that are currently disabled for legacy code files
via `per-file-ignores` in `pyproject.toml`. These exceptions exist because the legacy code
was written before strict linting was adopted, and changing it without adequate test coverage
is risky.

**Goal:** Remove all per-file-ignores during the SOLID refactoring phase, making every file
comply with the full Ruff rule set.

**Policy for new code:** All new files and substantial rewrites MUST pass the full Ruff rule
set with zero exceptions. See `.kiro/steering/code-quality-standards.md`.

---

## Global Permanent Ignores

These rules are intentionally disabled project-wide and are **not** technical debt:

| Rule | Description | Reason |
|------|-------------|--------|
| E501 | Line too long | Handled by `ruff format` automatically |
| F403 | Star imports | Kodi addons use `from xbmc import *` by convention |
| F405 | Undefined from star import | Consequence of F403 |
| UP031 | printf-style formatting | Codebase uses `%`-formatting; migration to f-strings is a separate effort |

---

## Per-File Legacy Exceptions

### `default.py`

The addon entry point. Routes URL actions to `body.py` functions via try/except blocks.

| Rule | Count | Description | Refactoring action |
|------|-------|-------------|-------------------|
| E711 | 1 | `== None` instead of `is None` | Replace with `is None` / `is not None` |
| E722 | ~25 | Bare `except:` | Add specific exception types (e.g., `except Exception:`) |
| F821 | 1 | Undefined name `local_b64decode` | Resolve cross-module reference; remove star import dependency |
| N812 | 1 | `import body as cbBody` | Rename to `import body as cb_body` or use direct import |
| SIM105 | 1 | try/except/pass | Replace with `contextlib.suppress()` |

**Priority:** Medium — relatively simple file, good candidate for early refactoring.

### `resources/lib/body.py`

The largest and most complex module (~2500 lines). Contains UI rendering, API integration,
database operations, and navigation logic. This is the primary refactoring target.

| Rule | Count | Description | Refactoring action |
|------|-------|-------------|-------------------|
| B007 | 1 | Unused loop variable | Use `_` for unused variables |
| E402 | ~15 | Imports not at top | Restructure module initialization; move sys.path setup to conftest/entry point |
| E711 | 4 | `== None` comparisons | Replace with `is None` / `is not None` |
| E722 | ~40 | Bare `except:` | Add specific exception types |
| F841 | 1 | Unused variable | Remove or use the variable |
| N802 | 4 | camelCase function names | Rename: `CBILLING_init` → `cbilling_init`, `downloadTsVideo` → `download_ts_video`, etc. |
| N806 | ~15 | camelCase local variables | Rename: `dbConn` → `db_conn`, `dbCursor` → `db_cursor`, etc. |
| N812 | 2 | Non-lowercase import aliases | `urlQuote` → `url_quote`, `urlUnquote` → `url_unquote` |
| N816 | 5 | camelCase globals | Rename: `epgFile` → `epg_file`, `cbAPI` → `cb_api`, etc. |
| RUF001 | 3 | Ambiguous Cyrillic characters | Verify intentional; add `# noqa: RUF001` inline where needed |
| RUF046 | 1 | Unnecessary int() cast | Remove if value is already int |
| SIM102 | 4 | Nested if statements | Combine with `and` where appropriate |
| SIM105 | ~10 | try/except/pass | Replace with `contextlib.suppress()` |
| SIM108 | 1 | if/else instead of ternary | Use ternary where it improves readability |
| SIM115 | 1 | File open without `with` | Use context manager |
| SIM201 | 1 | `not ==` instead of `!=` | Replace with `!=` |
| UP036 | 1 | Python 2/3 compat block | Remove Python 2 code paths |

**Priority:** High — largest file, most violations. Should be split into smaller modules
following Single Responsibility Principle during SOLID refactoring.

**Recommended decomposition:**
- `body.py` → `ui/navigation.py` (menu rendering, directory listing)
- `body.py` → `ui/player.py` (video playback, stream resolution)
- `body.py` → `db/epg.py` (EPG database operations)
- `body.py` → `db/favorites.py` (favorites management)
- `body.py` → `db/history.py` (watch history)
- `body.py` → `vod/browser.py` (VOD catalog browsing)

### `resources/lib/api_client.py`

HTTP client for the Cbilling API. Handles authentication, request signing, and error mapping.

| Rule | Count | Description | Refactoring action |
|------|-------|-------------|-------------------|
| B904 | 5 | `raise` without `from` in except | Add `from err` or `from None` to all re-raises |
| E402 | 1 | Import not at top | Move conditional imports to top with try/except |
| F401 | — | Unused import (conditional) | Restructure conditional simplejson import |
| SIM105 | 1 | try/except/pass | Replace with `contextlib.suppress()` |
| UP036 | 1 | Python 2/3 compat block | Remove Python 2 code paths |

**Priority:** Medium — important module but relatively clean.

### `resources/lib/api_adapter.py`

Transforms raw API responses into Kodi-friendly data structures.

| Rule | Count | Description | Refactoring action |
|------|-------|-------------|-------------------|
| F401 | — | Unused import (conditional) | Restructure conditional simplejson import |
| SIM105 | 2 | try/except/pass | Replace with `contextlib.suppress()` |

**Priority:** Low — only 2 issues.

### `resources/lib/utils.py`

Utility functions: logging, settings access, string encoding.

| Rule | Count | Description | Refactoring action |
|------|-------|-------------|-------------------|
| B006 | 1 | Mutable default argument `["dateshort"]` | Change to `None` with `if dateformat is None: dateformat = ["dateshort"]` |
| F821 | 2 | Undefined name `encode` | Resolve cross-module reference; define locally or import explicitly |
| N802 | 5 | camelCase function names | Rename: `getSetting` → `get_setting`, `getString` → `get_string`, etc. |
| N806 | 1 | camelCase local variable | Rename: `aFormat` → `a_format` |

**Priority:** Medium — small file, but functions are used everywhere. Renaming requires
updating all call sites.

### `resources/lib/vod_cache.py`

SQLite-based VOD metadata cache.

| Rule | Count | Description | Refactoring action |
|------|-------|-------------|-------------------|
| E722 | 2 | Bare `except:` | Add specific exception types (sqlite.Error, etc.) |
| N806 | ~15 | camelCase local variables | Rename: `dbConn` → `db_conn`, `dbCursor` → `db_cursor`, etc. |
| N816 | 1 | camelCase global `vodCacheFile` | Rename to `vod_cache_file` |
| SIM102 | 2 | Nested if statements | Combine with `and` |

**Priority:** Medium — well-structured module, straightforward to clean up.

### `resources/lib/cron.py`

Cron job scheduler (originally by Thamerlan, unmodified).

| Rule | Count | Description | Refactoring action |
|------|-------|-------------|-------------------|
| E722 | 1 | Bare `except:` | Add specific exception type |
| N802 | ~8 | camelCase method names | Rename all public methods to snake_case |
| N803 | ~4 | camelCase argument names | Rename: `jId` → `job_id`, `cronJob` → `cron_job` |
| N806 | ~8 | camelCase local variables | Rename to snake_case |
| RUF012 | 1 | Mutable class attribute | Add `ClassVar` annotation or move to `__init__` |
| SIM118 | 1 | `key in dict.keys()` | Replace with `key in dict` |

**Priority:** Low — Thamerlan's code, works correctly, rarely modified.

### Test files

| File | Rule | Description | Refactoring action |
|------|------|-------------|-------------------|
| `tests/conftest.py` | N802, N803 | camelCase mock methods/args | Cannot change — must match Kodi API naming |
| `tests/conftest.py` | SIM115 | File open without `with` | Refactor mock File class |
| `tests/unit/test_vod_cache.py` | N802 | camelCase mock methods | Cannot change — must match Kodi API naming |
| `tests/unit/test_vod_preload.py` | N802 | camelCase mock methods | Cannot change — must match Kodi API naming |
| `tests/unit/test_watch_history.py` | N802 | camelCase mock methods | Cannot change — must match Kodi API naming |

**Note:** N802/N803 in test files are **permanent exceptions** — Kodi API mock methods must
match the real Kodi API naming (camelCase). These should use inline `# noqa: N802` comments
rather than per-file-ignores after refactoring, to make the intent explicit.

---

## Refactoring Roadmap

### Phase 1: Quick wins (low risk, high impact)
1. Fix all `E711` — replace `== None` with `is None` (mechanical, safe)
2. Fix all `SIM102` — combine nested ifs (mechanical, safe)
3. Fix all `SIM118` — remove `.keys()` calls (mechanical, safe)
4. Fix all `B006` — mutable default arguments (1 instance in utils.py)
5. Fix all `RUF046` — remove unnecessary casts (1 instance in body.py)

### Phase 2: Naming conventions (medium risk, requires updating call sites)
1. Rename camelCase functions in `utils.py` → snake_case (used everywhere)
2. Rename camelCase local variables in `vod_cache.py` (self-contained)
3. Rename camelCase variables in `body.py` (largest scope)

### Phase 3: Error handling (medium risk)
1. Replace bare `except:` with specific exception types across all files
2. Add `from err` to all re-raises in `api_client.py`
3. Replace try/except/pass with `contextlib.suppress()` where appropriate

### Phase 4: SOLID decomposition (high risk, requires comprehensive tests first)
1. Split `body.py` into focused modules (see recommended decomposition above)
2. Remove Python 2/3 compatibility code (`UP036`)
3. Resolve cross-module star import dependencies (`F821`)
4. Restructure conditional imports (`E402`)

### Prerequisites for each phase
- **Phase 1:** Current test coverage (~19% total, but 57-78% on testable modules) is sufficient
- **Phase 2:** Add tests for all renamed functions before renaming
- **Phase 3:** Add tests for error handling paths
- **Phase 4:** Achieve ≥85% coverage on body.py before splitting
