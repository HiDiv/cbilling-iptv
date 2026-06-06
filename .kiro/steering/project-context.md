---
description: Cbilling IPTV project context — status, architecture, current tasks
inclusion: auto
---

# Cbilling IPTV Kodi Addon — Project Context

## Current Status

**Version:** 2.0.4-dev
**Status:** New API migration complete, preparing for GitHub publication

## Architecture

### Main Components

```
resources/lib/
├── api_client.py      # REST API client (URL from settings)
├── api_adapter.py     # Data adapter (API → Stalker format)
├── body.py            # Main addon logic
├── cron.py            # Task scheduler
├── croniter.py        # Cron library
├── vod_cache.py       # VOD cache (SQLite)
└── utils.py           # Utilities
```

### Entry Points

- `default.py` — main entry point for UI
- `service.py` — background service for cron tasks

## API

### Authorization

- **Method:** Header `x-public-key: YOUR_CODE`
- **Setting:** `user_login` in settings.xml
- **URL:** Specified in addon settings (settings → API URL)

### Main Endpoints

- `GET /streams` — channel list with ready URLs
- `GET /epg/{alias}/` — EPG for a day
- `GET /epg/current/{alias}/` — current EPG
- `GET /` — VOD categories
- `GET /video/{id}` — video/series information
- `GET /season/{id}` — season episode list
- `GET /servers` — server list

## Key Features

### Favorites
Stored locally in favorites.json (no API endpoint)

### Archive
- Archive depth: archive_days from API (in days, not hours!)
- URL formed via api_adapter.build_archive_url()

### EPG Caching
- SQLite database: epg.db
- Loads only 1 day for speed
- Updated via cron

## Known Issues (resolved)

1. ✅ Series with 1 season — now shows episodes directly
2. ✅ Archive showed 1 day instead of 7 — day calculation fixed
3. ✅ Slow EPG loading — now loads only 1 day

## Development Commands

```bash
# Activate venv
source .venv/bin/activate

# Run tests
python3 -m pytest tests/ --tb=short

# Run tests with coverage
python3 -m pytest tests/ --cov=resources/lib --cov-report=term-missing --cov-fail-under=70

# Build addon
python3 build_addon.py
```

---
Last updated: 2026-02-18
