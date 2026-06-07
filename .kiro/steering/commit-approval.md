---
description: Commit approval rule — always ask before committing
inclusion: auto
---

# Commit Approval Rule

## CRITICALLY IMPORTANT

**ALWAYS ask the user for explicit permission before creating a git commit!**

## Rules

1. **DO NOT commit automatically** after making code changes
2. **DO NOT commit** without explaining what the commit includes
3. **BEFORE committing**, tell the user:
   - What changes will be included (files list)
   - Why this commit is needed (purpose)
   - Proposed commit message
4. **Only after receiving explicit consent** run `git add` and `git commit`

## Process

1. Make code changes
2. Run tests / linting to verify changes
3. **ASK the user:**
   - "Ready to commit. Here's what it includes: ..."
   - "Proposed message: `type(scope): description`"
   - "Shall I commit?"
4. Wait for explicit "yes" / "да" / consent
5. Only then: `git add .` → `git commit -m "..."`

## Examples

### ❌ WRONG
```
You: [fix code] [run tests] [git add . && git commit -m "fix(vod): ..."]
```

### ✅ CORRECT
```
You: [fix code] [run tests]
You: "Fix is ready, tests pass. Ready to commit with the following changes:
  - resources/lib/api_client.py — added page param
  - resources/lib/body.py — pass page_nr to search
  - tests/integration/test_vod_search_pagination.py — new regression tests
  Proposed message: fix(vod): pass page parameter to search and year filter API calls
  Shall I commit?"
User: "Yes" / "Да"
You: [git add . && git commit]
```

## Exceptions

No exceptions. Always ask the user before any `git commit`.
