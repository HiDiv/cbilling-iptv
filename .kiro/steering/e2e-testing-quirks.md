---
description: E2E testing quirks — kodi-docker container behavior, addon installation
inclusion: fileMatch
fileMatchPattern: "tests/e2e/**"
---

# E2E Testing Quirks and Lessons Learned

## Container Image: kodi-test:20

The `kodi-test:20` image has an entrypoint that patches `guisettings.xml` via `sed -i`.
This means:
- **DO NOT mount guisettings.xml as a bind mount** — `sed -i` creates a temp file and renames it, which fails on bind mounts (even without `:ro`)
- The entrypoint already configures: webserver, JSON-RPC, EventServer
- Language, timezone, and other settings must be configured **programmatically via JSON-RPC** after Kodi starts

## Addon Installation Order (CRITICAL)

The correct order for installing and configuring the addon:

1. Start container, wait for healthcheck (JSONRPC.Ping)
2. Provision `settings.xml` (Kodi 20 format) — prevents blocking dialog
3. Extract addon ZIP to `/root/.kodi/addons/` using `python3 -c "import zipfile; ..."`
4. Run `kodi-send --action="UpdateLocalAddons"` — forces Kodi to discover the new addon
5. Wait 5 seconds for addon database update
6. `Addons.SetAddonEnabled(enabled=true)` — enable the addon
7. Verify addon in `Addons.GetAddons` within 15s
8. **Switch language to Russian** via `Settings.SetSettingValue("locale.language", "resource.language.ru_ru")`
9. Wait 5-10 seconds for Kodi to reload UI and addon strings

### Why this order matters:
- Step 3: `unzip` binary is NOT available in the container — use Python's `zipfile` module
- Step 4: Kodi does NOT auto-discover addons placed in `/root/.kodi/addons/` — `UpdateLocalAddons` is required
- Step 8: Language switch MUST happen AFTER addon is installed and enabled. Switching language forces Kodi to reload localized strings for ALL installed addons. If done before addon installation, the addon's strings won't be loaded.

## Settings That Cause Blocking Dialogs

- `addons.unknownsources` — shows a modal "Are you sure?" dialog that blocks JSON-RPC indefinitely
- **DO NOT** set this via `Settings.SetSettingValue` — it will hang
- Not needed anyway: we install the addon by direct file extraction, not through Kodi UI

## Addon Localization Behavior

- `getLocalizedString()` returns empty string if Kodi hasn't loaded the addon's strings.po
- Kodi loads addon strings only during:
  1. Initial Kodi startup (for already-installed addons)
  2. Language switch (reloads strings for ALL addons)
- Simply enabling/disabling an addon does NOT reload its strings
- English strings.po has empty `msgstr` — Kodi returns empty string (not `msgid` as fallback)

## Addon Settings Changes (CRITICAL — No Disable/Enable Needed)

Each `plugin://` URL invocation starts a **fresh Python process** — Kodi runs `default.py` from scratch. This means:
- `body.py` is imported fresh → `xbmcaddon.Addon().getSetting()` reads `settings.xml` from disk
- Settings like `stb_timezone`, `api_url`, `user_login` are picked up on the next `plugin://` call automatically
- **NO disable/enable cycle needed** — just write to `settings.xml` via `docker exec sed -i`

### Correct approach (tested and verified):
```python
import subprocess
settings_path = "/root/.kodi/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml"
subprocess.run([
    "docker", "exec", container_name,
    "sed", "-i",
    "s|<setting id=\"stb_timezone\">.*</setting>|<setting id=\"stb_timezone\">%s</setting>|" % timezone,
    settings_path,
], capture_output=True, text=True, timeout=10)
# Next get_container_items("plugin://...") will use the new value
```

### Why disable/enable is harmful:
- Leaves addon in a broken state where `Files.GetDirectory` returns `[-32602] Invalid params`
- Can drop the WebSocket connection (unreliable reconnect logic)
- Poisons ALL subsequent tests in the session

### Addons.SetAddonSetting JSON-RPC:
- **Does NOT exist in Kodi 20** — returns "Method not found" error
- In Kodi 21+ this method exists but may restart the addon's service.py
- Not needed anyway — direct `sed -i` on `settings.xml` is simpler and more reliable

## Player.Open Behavior (CRITICAL for playback tests)

- **`Player.Open` with a `plugin://` URL does NOT start playback** for addons that use `setResolvedUrl`. Kodi invokes the addon but the player never starts (`Player.GetActivePlayers` stays empty).
- **Solution**: extract the real stream URL from the `play_cmd` query parameter and pass that directly to `Player.Open`:
  ```python
  from urllib.parse import urlparse, parse_qs, unquote
  params = parse_qs(urlparse(plugin_url).query)
  stream_url = unquote(params.get("play_cmd", [""])[0])
  ```
- For **live channels**, `play_cmd` contains the full stream URL (e.g. `http://server/alias/index.m3u8?token=X`).
- For **archive**, `play_cmd` is EMPTY in the EPG item URL (addon builds it internally via `setResolvedUrl`). To play archive directly, build the URL manually from the live stream URL:
  ```
  http://server/alias/index.m3u8?token=X  →  http://server/alias/video-{unixtime}-{duration}.m3u8?token=X
  ```
  The `unixtime` and `duration` are available in the archive EPG item's plugin URL query params.

## Live Playback Buffering

- After `Player.Open`, the player may briefly report `speed=0` ("paused") during initial buffering before settling into `speed=1` ("playing").
- Playback verification should tolerate brief "paused" states during the first few seconds — poll for "playing" with a timeout rather than asserting state at a fixed moment.

## Test Ordering and Addon State Pollution (RESOLVED)

**Root cause was identified and fixed:** timezone tests used a disable/enable cycle to apply settings changes, which broke addon state for subsequent tests.

**Fix:** Since each `plugin://` URL starts a fresh Python process that re-reads `settings.xml`, the disable/enable cycle was completely unnecessary. Removing it eliminates the state pollution.

- pytest runs test files **alphabetically**: `test_addon_lifecycle` → `test_favorites` → `test_localization` → `test_navigation` → `test_playback` → `test_settings` → `test_timezone` → `test_vod`.
- Previously `test_vod` would fail after `test_timezone` due to the broken addon state from disable/enable.
- Now timezone tests simply write `settings.xml` via `sed -i` — no addon restart, no state pollution.

## Available Tools in Container

| Tool | Available | Notes |
|------|-----------|-------|
| `python3` | ✅ | Use for zipfile extraction |
| `kodi-send` | ✅ | Use for `--action=UpdateLocalAddons` |
| `curl` | ✅ | Used by healthcheck |
| `unzip` | ❌ | NOT installed |
| `bash` | ✅ | Available for scripting |

## Timeout Recommendations

| Operation | Timeout | Reason |
|-----------|---------|--------|
| Healthcheck polling | 60s | Kodi startup can be slow |
| Language switch wait | 10s | Kodi reloads entire UI |
| UpdateLocalAddons wait | 5s | Database scan |
| Individual JSON-RPC | 30s | Addon makes API calls |
| Content wait (navigation) | 60s | API round-trips |
| Per-test hard limit | 120s | pytest-timeout |

## pygments Compatibility Issue

The `pygments` package installed in .venv is incompatible with Python 3.8 (`functools.cache` requires 3.9+). This causes ERROR messages in pytest output when displaying tracebacks but does NOT affect test results. To fix: `pip install 'pygments<2.18'`.

## API Rate Limiting (HTTP 429)

The Cbilling API enforces rate limits. When running 25+ e2e tests in a single session, each of which makes API calls (get_channels, get_epg, etc.), the API starts returning `HTTP 429: /streams` for subsequent requests. This causes `get_container_items()` to return empty lists.

**Symptoms:**
- Tests passing in isolation but failing when run as part of the full suite
- `[Cbilling] Failed to get channels: HTTP 429: /streams` in kodi.log
- Empty results (0 items) from plugin:// calls that normally return content

**Mitigation:**
- Run test subsets rather than the full suite in one session
- If all tests must run together, restart the container between groups to get fresh rate-limit windows
- Consider adding small delays between test groups that make heavy API calls

## Playback Tests Instability

Playback tests (`test_playback.py`) are inherently flaky due to:
- Network-dependent stream resolution (may not start quickly enough)
- Brief "paused" states during initial buffering (`speed=0` before settling into `speed=1`)
- Stream URLs expiring or being rate-limited by the streaming server
- Player state not cleaning up reliably after failed playback attempts, which can poison subsequent tests in the session

**Current known issue:** The playback stability check asserts `state["state"] == "playing"` every 2s, but during initial buffering the player may briefly report "paused". The tolerance for paused states during the stability window needs to be improved.

---
Last updated: 2026-06-06
