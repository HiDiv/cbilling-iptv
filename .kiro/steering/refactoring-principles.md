---
description: SOLID refactoring principles — never blindly port old code
inclusion: always
---

# SOLID Refactoring Principles

## CRITICALLY IMPORTANT

**The goal of this refactoring is NOT to copy old code into new files.**

The goal is:
1. **Improve code structure** — single responsibility, clear interfaces
2. **Improve testability** — every module testable in isolation without Kodi
3. **Improve extensibility** — new features without modifying existing code
4. **Follow SOLID principles** strictly

## Before Porting Any Logic

When moving functionality from `body.py` (or any old code) to a new module:

1. **Analyze** — does this logic belong in this module? Does it violate SRP?
2. **Simplify** — can the logic be made clearer, shorter, more robust?
3. **Abstract** — should this be split into a pure function + a UI wrapper?
4. **Test** — write the test FIRST, then implement to pass it
5. **Verify** — does the result match behavioral equivalence requirements?

## DO NOT

- ❌ Copy-paste old code verbatim into new modules
- ❌ Preserve old patterns that violate SOLID (e.g., mixing data loading with UI rendering)
- ❌ Add complexity without understanding WHY the old code did it
- ❌ Skip writing tests because "it worked before"

## DO

- ✅ Separate concerns: data loading → processing → UI rendering
- ✅ Make pure functions where possible (no side effects, no Kodi imports)
- ✅ Use dependency injection (ctx parameter) for all external dependencies
- ✅ Write unit tests for logic, e2e tests for integration
- ✅ Verify behavioral equivalence via both automated tests AND manual comparison with v2.1.0

## Example: EPG Loading in Channel List

**Old approach (body.py):** 200+ lines mixing SQLite queries, HTTP requests, ThreadPoolExecutor, channel dict mutation, and ListItem creation all in one function.

**SOLID approach:**
1. `_load_epg_for_channels(ctx, channels)` — data loading (SQLite + HTTP fallback)
2. `_build_epg_plot(epg_data)` — pure function: EPG data → formatted string
3. `get_channels_list(ctx, params)` — UI: creates ListItems using the above

Each part is independently testable.

## Verification Checklist

After every fix, ask:
- [ ] Is this the simplest correct implementation?
- [ ] Is the logic separated from the UI?
- [ ] Can I unit-test the core logic without mocking Kodi?
- [ ] Does the e2e behavior match v2.1.0?
- [ ] Did I add a test that would have caught this bug?

Last updated: 2026-06-13
