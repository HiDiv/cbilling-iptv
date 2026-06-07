---
description: Addon versioning rule — always ask user before changing version
inclusion: always
---

# Addon Versioning Rule

## CRITICALLY IMPORTANT

**ALWAYS ask the user before changing the addon version!**

## Rules

1. **DO NOT bump the version automatically** after every fix or code change
2. **DO NOT change the version** in `addon.xml`, `changelog.txt` without explicit user consent
3. **ASK the user**: "Bump version to X.X.X or keep current X.X.X?"
4. **Only after receiving explicit consent** change the version in files

## Version Change Process

1. Make code fixes
2. Test the changes
3. **ASK** the user: "Bump version or keep current?"
4. If the user agrees — update version in:
   - `addon.xml` (version attribute)
   - `addon.xml` (news section)
   - `changelog.txt` (first entry)
5. Build the package with the new or current version

## Examples

### ❌ WRONG
```
User: Fix bug X
You: [fix] [bump version to 2.0.4-dev] [build package]
```

### ✅ CORRECT
```
User: Fix bug X
You: [fix] [test]
You: "Fix is ready. Bump version to 2.0.4-dev or keep 2.0.3-dev?"
User: Keep 2.0.3-dev
You: [build package with version 2.0.3-dev]
```

## Exceptions

No exceptions. Always ask the user.

## Current Version

Current version: **2.1.0** (released 2026-06-07)
Last released version: **2.1.0**

Last updated: 2026-06-07
