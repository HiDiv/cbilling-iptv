---
description: System restrictions — no host modifications, venv and workspace only
inclusion: always
---

# System Restrictions

## CRITICALLY IMPORTANT

### Do NOT modify the host system

**NEVER do:**
- ❌ Install system packages (`apt install`, `yum install`, `brew install`)
- ❌ Modify system files
- ❌ Install global Python packages (`pip install` without venv)
- ❌ Change system settings
- ❌ Install additional Python versions into the system

**ALWAYS use:**
- ✅ Only the project venv for Python dependencies
- ✅ Only files within the project workspace
- ✅ Only tools already available on the system

## Working with Python Versions

### Installing the required Python version via uv

**Correct approach (used in this project):**
```bash
# uv automatically downloads Python locally into the project
uv venv --python 3.8

# This creates .venv with Python 3.8 WITHOUT modifying the system
# Python is installed in ~/.local/share/uv/python/
```

**Benefits of uv:**
- ✅ No sudo or system privileges required
- ✅ Does not modify the host system
- ✅ Automatically downloads the required Python version
- ✅ Isolated Python versions per project

### If a different Python version is needed (legacy approach)

**Problem:** Need Python 3.8 for testing, but only Python 3.10 is available

**DO NOT:**
```bash
# ❌ FORBIDDEN
sudo apt install python3.8
brew install python@3.8
```

**Correct approach:**
1. Use the available Python version (3.10)
2. Follow Python 3.8 compatibility guidelines
3. Avoid constructs incompatible with Python 3.8
4. Rely on user testing on real systems

### Checking compatibility without Python 3.8

Instead of actual testing on Python 3.8:
- Follow `.kiro/steering/python38-compatibility.md`
- Do not use PEP 585 syntax (`list[str]`)
- Do not use PEP 604 syntax (`str | None`)
- Check vendor libraries for Python 3.8 compatibility
- Use static code analysis

## Working with Dependencies

### Installing dependencies

**Correct:**
```bash
# Activate the project venv
source venv/bin/activate

# Install into venv
pip install package_name
```

**Wrong:**
```bash
# ❌ Installing into the system
sudo pip install package_name
pip install --user package_name
```

## Working with Files

### Allowed operations

- ✅ Creating/modifying files within the project workspace
- ✅ Reading system files (for information only)
- ✅ Using project temporary directories

### Forbidden operations

- ❌ Modifying files outside the workspace
- ❌ Changing system configurations
- ❌ Creating files in system directories

## Using System Tools

### Allowed

- ✅ Using already installed tools (`git`, `grep`, `find`, etc.)
- ✅ Checking versions (`python3 --version`, `git --version`)
- ✅ Reading system information

### Forbidden

- ❌ Installing new tools
- ❌ Updating existing tools
- ❌ Changing tool configuration outside the project

## Examples

### ✅ Correct
```bash
# Working in the project venv
source venv/bin/activate
pip install requests
python3 test_script.py

# Using available tools
git status
grep -r "pattern" .
```

### ❌ Wrong
```bash
# Installing into the system
sudo apt install python3.8
sudo pip install requests

# Modifying system files
sudo nano /etc/hosts
```

## If an unavailable tool is needed

1. Check if you can work without it
2. Use alternatives from available tools
3. If critical — inform the user about the need to install
4. Never install it yourself

## Summary

**Golden rule:** Work only within the project, use only what is already available on the system.
