---
description: Git workflow rules — conventional commits, git add ., commit order
inclusion: always
---

# Git Workflow Rules

## Creating Commits

### Commit Message Format (Conventional Commits)

**All commit messages MUST be in English** and follow the Conventional Commits format:

```
type(scope): description
```

**Allowed types:**

| Type | Description |
|------|-------------|
| `feat` | New functionality |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Formatting, whitespace, semicolons, etc. (does not affect logic) |
| `refactor` | Code refactoring (not fix and not feat) |
| `test` | Adding or modifying tests |
| `chore` | Project maintenance (build, CI, dependencies) |
| `ci` | CI/CD configuration changes |

**Examples:**
```bash
# ✅ Correct
git commit -m "feat(vod): add series pagination support"
git commit -m "fix(epg): correct timezone offset calculation"
git commit -m "docs: update README with installation guide"
git commit -m "chore(lint): add pyproject.toml with Ruff config"
git commit -m "test: migrate tests to pytest under tests/"

# ❌ Wrong
git commit -m "исправил баг"
git commit -m "updated files"
git commit -m "WIP"
git commit -m "fix"
```

**Rules:**
- Description starts with lowercase
- No period at the end
- Brief description (up to 72 characters)
- Scope in parentheses is optional but recommended
- Language — **English only**

### ALWAYS use `git add .`

**Correct:**
```bash
git add .
git commit -m "change description"
```

**WRONG:**
```bash
# ❌ Manual file listing
git add file1.py file2.py file3.py
```

### Managing Exclusions via .gitignore

If a file should NOT be included in a commit — add it to `.gitignore`.
Do not use manual `git add` for selective file addition.

### What Should Be in a Commit

- ✅ All modified code files
- ✅ All test scripts (except temporary one-off scripts)
- ✅ All documentation
- ✅ Configuration files
- ✅ Steering files (.kiro/)

### Temporary Files

If a test script was created to verify a one-off hypothesis and is no longer needed — **delete it** before committing, don't ignore it.

### Documentation

All project documentation should be in the commit. If a document is not needed by anyone — it should not exist in the project at all. Delete the unnecessary file rather than excluding it from the commit.

## Task Execution Order for Spec Tasks

If a task (or group of subtasks) ends with a commit — **first mark the task as completed** in `tasks.md`, and **then** do `git add .` and `git commit`. This ensures the updated task status is included in the commit along with other changes.

### Order:
1. Complete all subtasks (code, documentation, etc.)
2. Update task/subtask status in `tasks.md` to `completed`
3. `git add .`
4. `git commit -m "description"`

### ❌ WRONG
```
1. Complete subtasks
2. git add . && git commit
3. Update task status  ← status NOT included in commit
```

### ✅ CORRECT
```
1. Complete subtasks
2. Update task status in tasks.md
3. git add . && git commit  ← status included in commit
```

## Before Committing

1. Check `git status` — make sure there are no unwanted files
2. If there are unnecessary files — delete them or add to `.gitignore`
3. `git add .`
4. `git commit -m "description"`

## .gitignore

Should contain:
- `.env` — secrets and API keys
- `.venv/` — virtual environment
- `dist/` — built packages
- `__pycache__/` — Python cache
- `*.pyc` — compiled files
- Other build and IDE artifacts
