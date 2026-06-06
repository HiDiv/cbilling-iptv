# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-03-15

### Fixed
- EPG timezone: display time now respects `stb_timezone` addon setting
- EPG time derived from Unix timestamps only (API `date` field in server TZ ignored)
- EPG cache recalculates `t_time`/`t_time_to` from timestamps on read (TZ change works instantly)
- SQLite "no such table: config" crash when config table lost from existing EPG database
- SQLite "NoneType is not callable" race condition between cron and UI threads
- All SQLite connections now use `timeout=10` and WAL journal mode for concurrent access
- EPG config table uses `CREATE IF NOT EXISTS` + `INSERT OR IGNORE` for safe recovery
- EPG reload uses `INSERT ON CONFLICT UPDATE` instead of plain `UPDATE` for missing rows
- Added `None` connection guard in `archive_channel_epg` to prevent NoneType errors
- VOD cache SQLite connections also updated with `timeout=10`

### Added
- Watch history: episodes now navigate to season's episode list instead of direct playback
- Episode list auto-positions cursor on the watched episode via `Action(Down)` emulation
- Works correctly for single-season series (bypasses season selection)

### Changed
- Uses `dateutil.tz` from existing vendor for timezone conversion (no new dependencies)
- Warning logged once at startup if timezone setting is empty or invalid (fallback to system time)

## [2.0.4-dev] - 2026-03-07

### Added
- Watch History feature for VOD (configurable size, default 5 items)
- Context menu for history items (remove, clear all)
- Settings for history management
- Client-side pagination (20 items per page)
- Debug logging for VOD operations

### Fixed
- IPTV channel sorting to respect server order
- VOD pagination — now showing all items with "Next page" button
- "All genres" folder now displays content correctly
- urllib3 compatibility with Python 3.8 (Kodi 19.4)

### Changed
- Improve episode/season name display (auto-generate when missing)

## [2.0.3-dev] - 2026-02-24

### Fixed
- EPG cache performance optimization
- Remove blocking EPG reload on channel list open
- EPG now loads instantly, cache updates in background

## [2.0.2-dev] - 2026-02-24

### Fixed
- Python 3.8 compatibility (Kodi 19/20)
- urllib3 type hints for older Python versions

### Changed
- Tested with Kodi 19.4 (Matrix) and Kodi 20 (Nexus)

## [2.0.1-dev] - 2025-02-17

### Changed
- Development version for testing API migration
- This is a pre-release version

## [2.0.0] - 2025-02-17

### Added
- New API client (`api_client.py`) and data adapter (`api_adapter.py`)
- Auth via `x-public-key` header (replaces Stalker handshake + bearer)
- Stream URLs included directly from `/streams` (no `create_link` needed)
- EPG from new API endpoints (`/epg/now`, `/epg/current`, `/epg/{alias}`)
- VOD from new API (`/`, `/cat/`, `/video/`, `/season/`)
- Local favorites storage (`favorites.json`)

### Removed
- Stalker Portal dependency (`mag-aura.com`)
- `ijson` and `dateutil` dependencies
- Login/password settings (replaced by public key)

## [XX.3.0]

### Fixed
- Interface speed optimization
- VOD opening (added to the favorites) after token expiration

## [XX.2.7]

### Fixed
- Improve auth error messaging

## [1X.2.6]

### Fixed
- API server URL (add option to modify it)

## [1X.2.5]

### Fixed
- EPG timeout issue

### Added
- Response timeout selection in config
- Stream server selection in context menu

## [1X.2.4]

### Added
- Stalker URL to configs

## [1X.2.3]

### Fixed
- Performance optimization
- Minor fixes

## [1X.2.2]

### Changed
- Internal tech release

## [1X.2.1]

### Fixed
- Local EPG cache validation (K19)

### Added
- Fast EPG for next several days
- Play live stream from the beginning
- Fast switch to today's archive from menu
- Focus last selected live channel on return

## [1X.2.0]

### Fixed
- A lot of small fixes (mainly for Kodi 19)

### Changed
- Code merge between Kodi 18 and Kodi 19

## [19.1.0]

### Changed
- Improve visibility and adopt addon to have a more original Kodi style look

## [19.0.9]

### Fixed
- Wrong server selection in VoD
- Sort beloved channels in alphabetical order

## [19.0.8]

### Fixed
- Issue with EPG reload even if is not active
- Minor fixes for new Kodi 19 beta1

### Changed
- New versioning model to support multiple Kodi versions

## [2.0.7]

### Fixed
- Issue with cyrillic week day names for some devices

## [2.0.6]

### Fixed
- Issues with multiroom subscription during interface operations

## [2.0.5]

### Added
- Watched status icons in VoD
- Option to delete local EPG cache file

### Removed
- Progress bar during channels load due to timeout issues

## [2.0.4]

### Added
- Aggressive EPG load

### Fixed
- Crash in VoD due to wrong data in poster path

## [2.0.3]

### Added
- Search in VoD
- Language files

### Fixed
- VoD playback with short tokens

## [2.0.2]

### Added
- VoD support

## [2.0.1]

### Added
- Use server side favorites

### Fixed
- Code optimization and minor fixes

## [2.0.0]

This version is based on the original "Cbilling IPTV" plugin.

### Added
- Advanced EPG for live channels with local cache to speed-up load
- Favorite channels
- Full day EPG for today's archive channel
- Channel logos
- EPG during playback (use I icon)
- New context menu for the live channels
- Some beautifications

## [1.0.8]

### Changed
- Check original "Cbilling IPTV" plugin history
