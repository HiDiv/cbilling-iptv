---
description: Recent bug fix log — series, archive, VOD
inclusion: auto
fileMatchPattern: "body.py"
---

# Recent Bug Fixes

## 2026-02-18 (evening): Series and Archive Fixes

### 1. Series with one season (re-fix)
**Problem:** "Next page" line was shown instead of episode list
**Cause:** `if len(seasons) == 1:` check failed due to invalid seasons
**Solution:**
- A `valid_seasons` list is created, filtering by presence of `name` or `number`
- Check `if len(valid_seasons) == 1:` calls `vod_get_episodes()` directly
- `valid_seasons` is used for iteration instead of `seasons`

### 2. Season names
**Problem:** Seasons may not have a `name` field, only `number`
**Solution:** Name is generated from number: "Season {number}"

### 3. Archive — number of days
**Problem:** API returns `archive_days=7`, but only 1 day is shown
**Status:** Debugging in progress — logging added to identify the issue

## 2026-02-18 (morning): Post-testing Fixes

### 1. Series with one season
**Problem:** Only "next page" line was shown
**Cause:** Kodi did not automatically navigate to episodes
**Solution:** Added check in `vod_get_seasons()` — if only one season, `vod_get_episodes()` is called directly

### 2. Archive shows only 1 day
**Problem:** Instead of 7 days, only 1 was shown
**Cause:** `archive_days` was divided by 24 (as if it were hours)
**Solution:** Removed division by 24, used directly

### 3. Slow EPG loading
**Problem:** EPG took long to load when entering archive
**Cause:** EPG was loaded for multiple days for all channels
**Solution:** Set `days_to_load = 1` in `epg_sqlite_reload()`

## Important Notes

### archive_days vs archive_hours
- API returns `archive_days` (days)
- Old Stalker used hours
- DO NOT convert days to hours!

### EPG Optimization
- Load only the current day
- Full load only on demand
- Use SQLite indexes

---
Last updated: 2026-02-18
