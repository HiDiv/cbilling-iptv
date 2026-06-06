---
description: Code quality standards — strict Ruff rules for new code, technical debt for legacy
inclusion: fileMatch
fileMatchPattern: "**/*.py"
---

# Code Quality Standards for New and Refactored Code

## CRITICALLY IMPORTANT

The project has two levels of linting rules:

1. **Strict rules** — apply to all **new files** and **substantially refactored** files
2. **Legacy exceptions** — temporarily disabled for specific old files via `per-file-ignores` in `pyproject.toml`

**Full list of legacy exceptions and elimination plan:** see `docs/technical-debt.md`

## Rules for New Code

When writing a **new file** or **substantially refactoring** an existing file, the code MUST comply with ALL Ruff rules without exceptions, even if those rules are disabled for legacy files.

### Naming (PEP 8)

```python
# ✅ CORRECT — snake_case for functions and variables
def get_channel_list():
    db_conn = sqlite.connect(db_file)
    db_cursor = db_conn.cursor()

# ❌ WRONG — camelCase (acceptable only in legacy code)
def getChannelList():
    dbConn = sqlite.connect(dbFile)
    dbCursor = dbConn.cursor()
```

**Exception:** Kodi API mocks in tests MUST use camelCase to match the real Kodi API (`getSetting`, `addDirectoryItem`, etc.). In such cases, add `# noqa: N802` to the specific line.

### Error Handling

```python
# ✅ CORRECT — specific exception type
try:
    data = json.loads(response)
except json.JSONDecodeError as e:
    xbmc.log(f"[Cbilling] JSON parse error: {e}", xbmc.LOGERROR)

# ✅ CORRECT — raise with from
try:
    result = api.get_channels()
except ConnectionError as err:
    raise ApiError("Failed to fetch channels") from err

# ✅ CORRECT — contextlib.suppress for ignoring errors
from contextlib import suppress
with suppress(FileNotFoundError):
    os.remove(cache_file)

# ❌ WRONG — bare except (acceptable only in legacy code)
try:
    data = json.loads(response)
except:
    pass
```

### Comparisons

```python
# ✅ CORRECT
if value is None:
if value is not None:
if not found:

# ❌ WRONG (acceptable only in legacy code)
if value == None:
if value != None:
if not value == True:
```

### Imports

```python
# ✅ CORRECT — imports at the top of the file
import os
import json
from contextlib import suppress

# ❌ WRONG — import not at the top (acceptable only in legacy code with sys.path)
sys.path.insert(0, some_path)
import my_module
```

### Default Arguments

```python
# ✅ CORRECT — immutable default values
def process_items(items=None):
    if items is None:
        items = []

# ❌ WRONG — mutable object as default value
def process_items(items=[]):
    ...
```

### Code Simplification

```python
# ✅ CORRECT — combined conditions
if not os.path.exists(cache_file) and not initialize_cache():
    return False

# ❌ WRONG — nested if (acceptable only in legacy code)
if not os.path.exists(cache_file):
    if not initialize_cache():
        return False
```

## When a File is Considered "New"

- File created from scratch
- File rewritten by more than 50%
- File extracted from body.py during decomposition (SOLID refactoring)

## When a File is Considered "Legacy"

- File is listed in `per-file-ignores` in `pyproject.toml`
- Only point fixes (bug fixes) are made without substantial refactoring

**Important:** Even when making point fixes in legacy files, **new code within the file** should follow strict rules as much as possible without refactoring surrounding code.

## Verification

Before committing, ensure:

```bash
# Linting — zero errors
ruff check .

# Formatting — zero differences
ruff format --check .

# Tests — all pass
python3 -m pytest tests/ --tb=short
```

## Process for Removing Legacy Exceptions

When refactoring a legacy file:

1. Ensure the file has ≥70% test coverage
2. Fix all Ruff rule violations in the file
3. Remove the file from `per-file-ignores` in `pyproject.toml`
4. Update `docs/technical-debt.md` — mark rules as resolved
5. Run `ruff check .` and `python3 -m pytest tests/` — everything must pass
