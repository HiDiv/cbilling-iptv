---
description: Testing workflow — pytest, conftest, Kodi mocks, run commands
inclusion: always
---

# Testing and Build Workflow

## Test Structure

Tests are organized in the `tests/` directory, split into unit and integration:

```
tests/
├── conftest.py                        # Shared fixtures: Kodi module mocks
├── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_api_adapter.py            # EPG, timezone, archive_days
│   ├── test_api_client.py             # API client (requires .env)
│   ├── test_vod_cache.py              # VOD cache (SQLite)
│   ├── test_vod_info.py               # VOD information
│   ├── test_vod_metadata.py           # VOD metadata
│   ├── test_vod_pagination.py         # VOD pagination
│   ├── test_vod_preload.py            # VOD preloading
│   ├── test_vod_series.py             # VOD series
│   ├── test_watch_history.py          # Watch history
│   ├── test_imports.py                # Import checks
│   ├── test_logging_style.py          # Logging style
│   └── test_urllib3_import.py         # urllib3 import
└── integration/
    ├── __init__.py
    ├── test_sqlite_robustness.py      # SQLite robustness
    └── test_vod_search_pagination.py  # VOD search/year filter pagination (issue #1)
```

## Testing Dependencies

Required packages in `.venv`:

```bash
source .venv/bin/activate
pip install pytest pytest-cov pytz
```

- **pytest** — testing framework
- **pytest-cov** — code coverage
- **pytz** — timezones (needed for api_adapter tests)

## Kodi Module Mocks (conftest.py)

`tests/conftest.py` contains an autouse fixture `mock_kodi_modules` that automatically injects Kodi module mocks into `sys.modules` before each test:

- **MockXBMC** — `xbmc.log()`, `xbmc.getRegion()`, `xbmc.executebuiltin()`, `xbmc.translatePath()`
- **MockXBMCGUI** — `Dialog`, `ListItem`, `Window`, `getCurrentWindowId()`
- **MockXBMCPlugin** — `addDirectoryItem()`, `addDirectoryItems()`, `endOfDirectory()`, `setResolvedUrl()`, `setContent()`
- **MockXBMCAddon** — `Addon` with `getSetting()`, `setSetting()`, `getAddonInfo()`, `getLocalizedString()`
- **MockXBMCVFS** — `translatePath()`, `exists()`, `mkdirs()`, `mkdir()`, `File`

The fixture saves and restores the original `sys.modules` state after each test.

### Extending Mocks

If a test requires additional Kodi API methods not present in conftest.py:
1. Add the method to the corresponding Mock class in `tests/conftest.py`
2. Or create a local fixture in the test file that patches `sys.modules`

Example of a local patch (from `test_vod_cache.py`):
```python
@pytest.fixture
def cache_dir(tmp_path, mock_kodi_modules):
    cache_path = str(tmp_path / "vod_cache")
    os.makedirs(cache_path, exist_ok=True)

    class TmpAddon:
        def getSetting(self, key):
            if key == "vod_cache_ttl_days":
                return "7"
            return ""
        def getAddonInfo(self, key):
            if key == "profile":
                return cache_path
            return ""

    mod = types.ModuleType("xbmcaddon")
    mod.Addon = lambda *a, **kw: TmpAddon()
    sys.modules["xbmcaddon"] = mod

    if "vod_cache" in sys.modules:
        del sys.modules["vod_cache"]

    from vod_cache import vod_cache_init
    vod_cache_init()
    yield cache_path
```

## Importing Addon Modules from Tests

Each test file adds paths to `sys.path` for importing addon modules:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))
```

This allows `from api_client import CbillingAPI` etc.

**IMPORTANT:** These lines must be at module level (not inside a fixture) so paths are available during import.

## API Tests (require .env)

Tests that access the real API are marked with `@pytest.mark.skipif`:

```python
def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, ".env")
    if not os.path.exists(env_path):
        return False
    # ... load variables ...
    return bool(os.environ.get("CBILLING_API_URL")) and bool(os.environ.get("CBILLING_PUBLIC_KEY"))

_HAS_API = _load_env()
requires_api = pytest.mark.skipif(not _HAS_API, reason="API credentials not available (.env)")

@requires_api
def test_streams(api):
    ...
```

Without a `.env` file, these tests are automatically skipped.

## Test Run Commands

### All tests
```bash
source .venv/bin/activate
python3 -m pytest tests/ --tb=short
```

### With coverage
```bash
python3 -m pytest tests/ --cov=resources/lib --cov-report=term-missing --cov-fail-under=70
```

### Unit tests only
```bash
python3 -m pytest tests/unit/ --tb=short
```

### Integration tests only
```bash
python3 -m pytest tests/integration/ --tb=short
```

### Specific file
```bash
python3 -m pytest tests/unit/test_api_adapter.py -v
```

### Specific test
```bash
python3 -m pytest tests/unit/test_api_adapter.py::test_ts_to_local_str -v
```

## Testing Priority

### 1. Automated tests (first priority)
- Run `python3 -m pytest tests/ --tb=short`
- All 153+ tests should pass
- API-dependent tests are skipped without `.env`
- Integration tests with API: `python3 -m pytest tests/ -m api --tb=short`

### 2. Kodi log analysis (second priority)
- Read `kodi.log` to understand issues
- Search for `[Cbilling]` or addon name entries
- Analyze errors and tracebacks

### 3. Manual testing in Kodi via dev environment (third priority)
- Use `./dev/start.sh` to launch Kodi with addon mounted
- Source code changes apply immediately (next plugin:// call)
- View logs: `./dev/logs.sh addon`
- **ONLY** after fixing all possible errors through automated tests
- **ONLY** with explicit user permission

### 4. E2E tests (before release)
- Run `make e2e` for full cycle (build ZIP → start container → run tests → stop)
- Requires Docker and API credentials

## Dev Environment for Manual Testing

The `dev/` directory provides a self-contained Kodi environment:

```bash
# One-time host setup (X11 access)
./dev/setup-host.sh

# Start Kodi 20 in window
./dev/start.sh

# View addon logs
./dev/logs.sh addon

# Stop
./dev/stop.sh

# Reset all data (clean slate)
./dev/reset.sh
```

**Key details:**
- Docker images: `ghcr.io/hidiv/kodi-docker:kodi20-v0.1.0`
- Addon source mounted read-only (changes picked up on next navigation)
- `dev/kodi_data/` stores persistent data (EPG, cache, settings) — gitignored
- Settings auto-provisioned from `.env` on first run
- Logs always at `dev/kodi_data/temp/kodi.log`

## Writing New Tests

### Unit test template
```python
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for <module_name>."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))

from module_name import function_to_test


def test_basic_case():
    result = function_to_test("input")
    assert result == "expected"


@pytest.mark.parametrize("input_val, expected", [
    ("a", "result_a"),
    ("b", "result_b"),
])
def test_parametrized(input_val, expected):
    assert function_to_test(input_val) == expected
```

### Test writing rules
- Use `assert` instead of `print("PASS")`/`print("FAIL")`
- Use `@pytest.mark.parametrize` for multiple input data
- Use `tmp_path` fixture for temporary files/directories
- Use `mock_kodi_modules` fixture (autouse, connected automatically)
- Mark API-dependent tests with `@requires_api` decorator
- New unit tests go in `tests/unit/`, integration in `tests/integration/`

## Building the Addon

### Build rule
**CRITICALLY IMPORTANT:** Building a new addon package (`python3 build_addon.py`) is allowed **ONLY** after receiving **EXPLICIT CONSENT** from the user!

### Process:
1. Fix issues in code
2. Run tests: `python3 -m pytest tests/ --tb=short`
3. Analyze results
4. Repeat steps 1-3 until all tests pass
5. **Ask permission** to build
6. Only after consent: `python3 build_addon.py`

## Debugging

### Adding debug logging
```python
debug_log('[FunctionName] Variable: %s, value: %s' % (var_name, var_value))
```

### Checking logs
- Kodi logs: `~/.kodi/temp/kodi.log` or `/root/.kodi/temp/kodi.log`
- Search by addon: `grep -i cbilling kodi.log`
- Search by function: `grep "FunctionName" kodi.log`

## Known Quirks

### Re-importing modules when patching mocks
If a test patches `sys.modules["xbmcaddon"]` (or another Kodi module) after the addon module has already been imported, you need to remove the module from `sys.modules` and re-import:

```python
if "vod_cache" in sys.modules:
    del sys.modules["vod_cache"]
from vod_cache import vod_cache_init
```

### tmp_path for filesystem isolation
Tests working with files (SQLite, cache) should use pytest's `tmp_path` fixture for isolation:

```python
def test_something(tmp_path):
    db_path = str(tmp_path / "test.db")
    # ... work with file ...
```
