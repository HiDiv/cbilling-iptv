---
description: Venv and Python usage rules — activation, python3, uv
inclusion: always
---

# Venv and Python Usage Rules

## Project Configuration

**Current venv:** `.venv` (created via `uv venv --python 3.8`)
**Python version:** 3.8.20
**Working directory:** `/home/hidiv/work/docker/cbilling-iptv` (NEVER change it)
**Reason:** Compatibility with Kodi 19.4 (Python 3.8)

## CRITICALLY IMPORTANT

### 0. NEVER use `cd` to the project directory

**We are ALWAYS in `/home/hidiv/work/docker/cbilling-iptv`.**

```bash
# ❌ ABSOLUTELY FORBIDDEN — never do this
cd /home/hidiv/work/docker/cbilling-iptv && source .venv/bin/activate && python3 ...

# ✅ CORRECT — we are already there
source .venv/bin/activate && python3 ...
```

**DO NOT prefix commands with `cd /home/hidiv/work/docker/cbilling-iptv`.**
All commands run in the project root by default.

### 1. ALWAYS activate venv before python

**Every command that invokes `python3` MUST be preceded by `source .venv/bin/activate`:**

```bash
source .venv/bin/activate && python3 -m pytest tests/ --tb=short
source .venv/bin/activate && python3 build_addon.py
source .venv/bin/activate && ruff check .
```

This is required because each `execute_bash` call starts a fresh shell — the venv is NOT preserved between calls.

### 2. Running Python

**ALWAYS use `python3`:**
```bash
python3 script.py
python3 -m pytest
python3 build_addon.py
```

**NEVER use `python`:**
```bash
# ❌ WRONG
python script.py

# ✅ CORRECT
python3 script.py
```

## Correct Usage Examples

### First run in a session
```bash
# Activate .venv (Python 3.8)
source .venv/bin/activate

# Run commands
python3 test_urllib3_import.py
python3 test_new_api_client.py
python3 test_vod_series.py
```

### Subsequent commands in the same session
```bash
# venv is already activated, just run
python3 test_epg.py
python3 test_archive_days.py
```

### New terminal session
```bash
# Terminal was closed and reopened
# Activate .venv again
source .venv/bin/activate

# Run commands
python3 test_new_api_client.py
```

## Checking venv activation

If unsure whether venv is activated:
```bash
which python3
# Should show: /path/to/project/.venv/bin/python3

python3 --version
# Should show: Python 3.8.20
```

Or check the prompt — should have `(venv)` prefix:
```bash
(venv) user@host:~/project$
```

## Common Mistakes

### ❌ Activating with every command
```bash
# WRONG — redundant activation
bash -c "source venv/bin/activate && python3 test1.py"
bash -c "source venv/bin/activate && python3 test2.py"
bash -c "source venv/bin/activate && python3 test3.py"
```

### ✅ Correct approach
```bash
# CORRECT — activate once
source .venv/bin/activate
python3 test1.py
python3 test2.py
python3 test3.py
```

### ❌ Using python instead of python3
```bash
# WRONG
source venv/bin/activate
python test_script.py  # May not find the command
```

### ✅ Correct approach
```bash
# CORRECT
source .venv/bin/activate
python3 test_script.py
```

## Managing Python Versions via uv

### Creating a new venv with the required Python version

```bash
# uv automatically downloads and installs the required Python version
uv venv --python 3.8   # Python 3.8.x
uv venv --python 3.9   # Python 3.9.x
uv venv --python 3.10  # Python 3.10.x
```

### Benefits of uv

- Automatic Python installation without modifying the system
- Fast operation (written in Rust)
- Isolated Python versions per project
- No sudo or system privileges required

## Exceptions

The only case where `bash -c "source .venv/bin/activate && python3 ..."` is acceptable:
- When a command needs to run in a new shell process
- When the current terminal state is unknown
- In automated scripts

In interactive work, always activate .venv once at the start of the session.
