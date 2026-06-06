# E2E Testing Guide

End-to-end tests for `plugin.video.cbilling.iptv` exercise the addon inside a real Kodi instance running in Docker. Tests communicate with Kodi via JSON-RPC over WebSocket, navigating the UI, verifying API integration, and validating content rendering — all without a physical display.

## Architecture Overview

The e2e testing infrastructure is organized into five layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  Host Machine                                                   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Build Step                                              │   │
│  │  python3 build_addon.py → dist/plugin.video.cbilling*.zip│   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  pytest (tests/e2e/)                                     │   │
│  │  ├── conftest.py (fixtures + addon installer)            │   │
│  │  ├── kodi_client.py (KodiClient, WebSocket)  ─── :9090 ─┼─┐ │
│  │  ├── addon_installer.py (ZIP install + settings)         │ │ │
│  │  ├── utils.py (strip_kodi_tags)                          │ │ │
│  │  ├── test_addon_lifecycle.py                             │ │ │
│  │  ├── test_navigation.py                                  │ │ │
│  │  ├── test_localization.py                                │ │ │
│  │  ├── test_timezone.py                                    │ │ │
│  │  └── artifacts.py (collector)                            │ │ │
│  └──────────────────────────────────────────────────────────┘ │ │
│                                                               │ │
│  ┌────────────────────────────────────────────────────────────▼─┐
│  │  Docker Container (kodi-docker)                              │
│  │  ├── Kodi (headless via Xvfb)                                │
│  │  ├── guisettings.xml (RU locale, TZ, JSON-RPC enabled)       │
│  │  ├── /addons_zip/ (mounted from dist/)                       │
│  │  ├── plugin.video.cbilling.iptv (unzipped at runtime)        │
│  │  ├── JSON-RPC WebSocket :9090                                │
│  │  ├── JSON-RPC HTTP :8080                                     │
│  │  ├── VNC :5900 / noVNC :8000                                 │
│  │  └── kodi.log                                                │
│  └──────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **ZIP-based installation** — The addon is built into a ZIP, mounted at `/addons_zip/` in the container, then unzipped to `/root/.kodi/addons/` and enabled via JSON-RPC. This mirrors the real user installation flow and catches installation-related bugs that volume mounts would miss.

2. **Settings provisioning before activation** — The addon shows a blocking confirmation dialog when `settings.xml` is missing. Pre-creating `settings.xml` in Kodi 20 format prevents this dialog from blocking JSON-RPC responses.

3. **Russian locale as default** — The addon's target audience is Russian-speaking. Testing with Russian locale catches localization issues. The `strip_kodi_tags()` utility removes Kodi formatting tags before label comparison.

4. **Disabled WebSocket keepalive** — When the addon makes API calls, Kodi can take >20s to respond. The default websockets keepalive ping (20s) would drop the connection. Setting `ping_interval=None` prevents this.

5. **Tiered timeouts (30s/60s/120s)** — Individual JSON-RPC requests get 30s, content loading waits get 60s, and `pytest-timeout` enforces a 120s hard limit per test to prevent infinite hangs.

6. **Pre-configured guisettings.xml** — The container's entrypoint automatically configures JSON-RPC and webserver. Russian language is set programmatically via JSON-RPC after addon installation, which forces Kodi to reload localized strings for all addons.

### Docker Containers

The `tests/e2e/docker-compose.yml` defines three service profiles:

| Profile | Image | Kodi Version |
|---------|-------|--------------|
| `kodi19` | `kodi-test:19` | Kodi 19 (Matrix) |
| `kodi20` | `kodi-test:20` | Kodi 20 (Nexus) |
| `kodi21` | `kodi-test:21` | Kodi 21 (Omega) |

Each container:
- Runs Kodi headlessly via Xvfb
- Exposes JSON-RPC on ports 8080 (HTTP) and 9090 (WebSocket)
- Exposes VNC on port 5900 and noVNC on port 8000
- Mounts `dist/` as read-only at `/addons_zip/` (for ZIP-based installation)
- Loads credentials from the project `.env` file
- Sets `TZ=Europe/Moscow` environment variable
- Includes a healthcheck that pings `JSONRPC.Ping` via HTTP
- Entrypoint auto-configures JSON-RPC, webserver, and EventServer

### Addon Installation Flow

```
make e2e-build          → python3 build_addon.py (creates ZIP in dist/)
make e2e-start          → docker compose up (container starts)
                        → Kodi starts with default English locale
conftest.py             → Poll healthcheck (JSONRPC.Ping) every 2s
                        → Provision settings.xml (Kodi 20 format)
                        → Extract addon ZIP using python3 zipfile module
                        → kodi-send --action=UpdateLocalAddons (force discovery)
                        → Addons.SetAddonEnabled(enabled=true)
                        → Verify addon enabled (Addons.GetAddons)
                        → Switch language to Russian (reloads addon strings)
                        → Connect KodiClient (ping_interval=None, timeout=30s)
                        → Ready for tests
```

### guisettings.xml Pre-configuration

The container's entrypoint script automatically configures JSON-RPC and webserver settings. Additional settings (Russian locale) are applied programmatically via JSON-RPC after the addon is installed:

| Setting | Method | Purpose |
|---------|--------|---------|
| `services.webserver` | Entrypoint | Enable HTTP JSON-RPC |
| `services.esallinterfaces` | Entrypoint | Listen on all interfaces |
| `services.esenabled` | Entrypoint | Enable WebSocket JSON-RPC |
| `locale.language` | JSON-RPC (after addon install) | Russian UI + addon strings reload |

**Important:** `guisettings.xml` must NOT be mounted as a bind mount — the entrypoint uses `sed -i` which fails on bind mounts. The `addons.unknownsources` setting must NOT be set via JSON-RPC — it triggers a blocking modal dialog.

### KodiClient

`tests/e2e/kodi_client.py` provides a synchronous Python client for Kodi JSON-RPC over WebSocket. It uses `asyncio` internally but exposes synchronous methods, so no `pytest-asyncio` dependency is needed.

Key capabilities:
- **Connection management**: `connect()`, `close()`
- **JSON-RPC requests**: `send_request(method, params, timeout)` — default timeout 30s
- **Navigation**: `input_up()`, `input_down()`, `input_left()`, `input_right()`, `input_select()`, `input_back()`, `input_home()`
- **State queries**: `get_current_window()`, `get_container_items()`, `get_player_state()`
- **Waiting**: `wait_for_window(window_id, timeout)`, `wait_for_content(label_substring, min_items, timeout)` — default timeout 60s
- **Diagnostics**: `take_screenshot(filepath)`

### Timeout Configuration

| Layer | Timeout | Purpose |
|-------|---------|---------|
| KodiClient default | 30s | Individual JSON-RPC request timeout |
| `wait_for_content` | 60s | Polling for content to appear (API round-trips) |
| `pytest-timeout` | 120s | Hard per-test limit to prevent infinite hangs |

These values account for real API calls the addon makes during navigation. The addon contacts the Cbilling API on each menu navigation, which can take 10-20s depending on network conditions.

### strip_kodi_tags Utility

Kodi wraps labels in formatting tags like `[COLOR white][B]Прямой эфир[/B][/COLOR]`. The `strip_kodi_tags()` function from `tests/e2e/utils.py` removes these before assertions:

```python
from tests.e2e.utils import strip_kodi_tags, strip_labels

# Single label
label = strip_kodi_tags("[COLOR white][B]Прямой эфир[/B][/COLOR]")
assert label == "Прямой эфир"

# List of items from get_container_items()
labels = strip_labels(items)
assert "Прямой эфир" in labels
```

Supported tags: `[COLOR ...]`, `[/COLOR]`, `[B]`, `[/B]`, `[I]`, `[/I]`, `[UPPERCASE]`, `[/UPPERCASE]`, `[LOWERCASE]`, `[/LOWERCASE]`, `[LIGHT]`, `[/LIGHT]`, `[CR]`.

### pytest Fixtures

Session-scoped fixtures in `tests/e2e/conftest.py` manage the test environment lifecycle. The container starts once per session, and all tests share the same Kodi instance.

### Test Modules

| Module | Purpose |
|--------|---------|
| `test_addon_lifecycle.py` | ZIP installation, addon startup, main menu verification |
| `test_navigation.py` | Navigation through Live TV, Archive, Favorites, VOD Library |
| `test_localization.py` | Russian labels, English smoke test |
| `test_timezone.py` | Timezone parametrized tests, archive days |

## Prerequisites

| Requirement | Minimum Version |
|-------------|-----------------|
| Docker | 20.10+ |
| docker-compose (v2) | 2.0+ (integrated `docker compose` command) |
| Python | 3.8+ |
| OS | Linux, macOS |

Additional requirements:
- Active Cbilling API credentials (`CBILLING_API_URL`, `CBILLING_PUBLIC_KEY`)
- Network access to `ghcr.io` for pulling Docker images
- Ports 8080, 9090, 5900, 8000 available on localhost

## Setup Instructions

### 1. Install Docker

Follow the official Docker installation guide for your OS:
- Linux: https://docs.docker.com/engine/install/
- macOS: https://docs.docker.com/desktop/install/mac-install/

Verify installation:

```bash
docker --version        # Docker 20.10+
docker compose version  # Docker Compose v2.0+
```

### 2. Configure Environment

Create or update the `.env` file in the project root with your Cbilling credentials:

```bash
cp .env.example .env
```

Edit `.env` and set:

```
CBILLING_API_URL=https://api.cbilling.tv
CBILLING_PUBLIC_KEY=your_public_key_here
```

### 3. Install E2E Dependencies

```bash
source .venv/bin/activate
pip install -r tests/e2e/requirements.txt
```

### 4. Build the Addon ZIP

```bash
make e2e-build
```

This runs `python3 build_addon.py` and creates the addon ZIP in `dist/`. The ZIP is required for the container to install the addon.

### 5. Start the Container

```bash
make e2e-start
```

This starts the default Kodi 20 container and waits for the healthcheck to pass (up to 60 seconds). The container starts with Russian locale and pre-configured settings from `guisettings.xml`.

### 6. Run a Smoke Test

Verify the environment is working by running a single test:

```bash
KODI_VERSION=kodi20 python3 -m pytest -m e2e tests/e2e/test_addon_lifecycle.py::TestAddonLifecycle::test_addon_detected -v
```

If the test passes, the addon was installed from ZIP and detected inside the running Kodi container.

### 7. Stop the Container

```bash
make e2e-stop
```

## Running Tests

### Run All E2E Tests (Full Cycle)

```bash
make e2e
```

This performs the full cycle: build ZIP → start container → run tests → stop container. If tests fail, the container is still stopped before exiting.

### Run All E2E Tests (Manual Steps)

```bash
make e2e-build
make e2e-start
make e2e-test
make e2e-stop
```

### Run a Single Test File

```bash
make e2e-build
make e2e-start
KODI_VERSION=kodi20 python3 -m pytest -m e2e tests/e2e/test_navigation.py -v
make e2e-stop
```

### Run Tests Against a Specific Kodi Version

```bash
make e2e-build
make e2e-start KODI_VERSION=kodi21
make e2e-test KODI_VERSION=kodi21
make e2e-stop KODI_VERSION=kodi21
```

Or as a single command:

```bash
make e2e KODI_VERSION=kodi21
```

### Run a Specific Test

```bash
KODI_VERSION=kodi20 python3 -m pytest -m e2e tests/e2e/test_addon_lifecycle.py::TestAddonLifecycle::test_main_menu_items -v
```

### Verbose Output with Logs

```bash
KODI_VERSION=kodi20 python3 -m pytest -m e2e -v --tb=long
```

## Writing New Tests

### Template Test File

```python
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Description of what this test module covers."""

import pytest

from tests.e2e.kodi_client import KodiClient
from tests.e2e.utils import strip_kodi_tags, strip_labels


@pytest.mark.e2e
class TestFeatureName:
    """Tests for a specific feature."""

    def test_basic_scenario(
        self,
        kodi_client: KodiClient,
        kodi_container: str,
    ) -> None:
        """Describe what this test verifies.

        Validates: Requirements X.Y
        """
        # Activate the addon
        kodi_client.send_request(
            "Addons.ExecuteAddon",
            {"addonid": "plugin.video.cbilling.iptv"},
        )

        # Wait for content to load (60s timeout for API calls)
        items = kodi_client.wait_for_content(min_items=1, timeout=60.0)

        # Strip Kodi formatting tags before comparing labels
        labels = strip_labels(items)
        assert "Прямой эфир" in labels

    @pytest.mark.skip_kodi_version("kodi19")
    def test_kodi20_plus_feature(
        self,
        kodi_client: KodiClient,
    ) -> None:
        """Test a feature only available in Kodi 20+.

        Validates: Requirements X.Z
        """
        # This test is skipped when KODI_VERSION=kodi19
        pass
```

### Available Fixtures

| Fixture | Scope | Purpose | Usage |
|---------|-------|---------|-------|
| `kodi_client` | session | Connected KodiClient instance (30s timeout) | Use to send commands, navigate UI, query state |
| `kodi_container` | session | Running Docker container name (e.g. `kodi-e2e-kodi20`) | Use for `docker exec` commands to access container internals |
| `addon_settings` | session | Dictionary with `api_url`, `public_key`, `kodi_version` | Use to access credentials or version info in tests |
| `e2e_config` | session | Full `E2EConfig` dataclass with all configuration | Use for advanced configuration access |
| `collect_artifacts_on_failure` | function (autouse) | Automatically captures screenshot and kodi.log on test failure | No explicit usage needed — runs automatically |

### Key Patterns

**Navigate to a menu section:**

```python
# Get items from the addon root
items = kodi_client.get_container_items("plugin://plugin.video.cbilling.iptv/")

# Navigate to a specific section by path
section_items = kodi_client.get_container_items(
    "plugin://plugin.video.cbilling.iptv/live"
)
```

**Wait for content with timeout:**

```python
items = kodi_client.wait_for_content(
    label_substring="Прямой эфир",
    min_items=1,
    timeout=60.0,
)
```

**Strip tags before assertion:**

```python
from tests.e2e.utils import strip_kodi_tags, strip_labels

labels = strip_labels(items)
assert "Прямой эфир" in labels
assert "Архив" in labels
assert "Любимые каналы" in labels
assert "Медиатека" in labels
```

**Check player state:**

```python
state = kodi_client.get_player_state()
assert state["state"] == "playing"
```

## Interpreting Results

### Reading Kodi Logs

When a test fails, the `collect_artifacts_on_failure` fixture automatically saves the Kodi log to the artifacts directory. You can also manually retrieve logs from a running container:

```bash
docker exec kodi-e2e-kodi20 tail -200 /root/.kodi/temp/kodi.log
```

Look for:
- `[Cbilling]` entries — addon-specific log messages
- `ERROR` level messages — exceptions and failures
- `WARNING` level messages — non-fatal issues
- Python tracebacks — unhandled exceptions in the addon

### Using Screenshots and Video

On test failure, a screenshot is automatically captured and saved. If `E2E_RECORD_VIDEO=1` is set, the entire test session is recorded.

To manually connect via VNC for live debugging:

```bash
# Using a VNC client
vncviewer localhost:5900

# Or via browser (noVNC)
open http://localhost:8000
```

### Artifact Directory and Naming

All artifacts are stored in `tests/e2e/artifacts/` (gitignored).

File naming convention:

```
{test_name}_{kodi_version}_{YYYYMMDD_HHMMSS}.{ext}
```

Examples:
- `test_addon_detected_kodi20_20260115_143022.png` — screenshot
- `test_addon_detected_kodi20_20260115_143022.log` — kodi.log snapshot
- `session_kodi20_20260115_143000.mp4` — video recording (if enabled)

The test name is sanitized: only alphanumeric characters, underscores, and hyphens are kept, truncated to 100 characters maximum.

### Artifact paths in output

When a test fails, artifact paths are printed directly in the pytest output:

```
FAILED tests/e2e/test_navigation.py::TestNavigation::test_live_tv
  Artifact (screenshot): /absolute/path/to/tests/e2e/artifacts/test_live_tv_kodi20_20260115_143022.png
  Artifact (kodi.log): /absolute/path/to/tests/e2e/artifacts/test_live_tv_kodi20_20260115_143022.log
```

## Bug-First Workflow

The recommended workflow for fixing bugs found in the addon:

### 1. Write a Failing E2E Test

Create a test that reproduces the bug. The test should fail on the current code:

```python
@pytest.mark.e2e
class TestBugFix:
    def test_archive_navigation_does_not_crash(
        self,
        kodi_client: KodiClient,
    ) -> None:
        """Regression test: navigating to Archive should not raise an error.

        Bug: Navigating to Archive with an expired channel list causes
        an unhandled KeyError in api_adapter.py.

        Validates: Requirements 5.2
        """
        # Navigate to Archive section
        items = kodi_client.get_container_items(
            "plugin://plugin.video.cbilling.iptv/archive"
        )

        # Should return items without crashing
        assert len(items) >= 1, "Archive should contain at least one channel"
```

### 2. Verify the Test Fails

```bash
make e2e-build
make e2e-start
KODI_VERSION=kodi20 python3 -m pytest -m e2e tests/e2e/test_bug_fix.py -v
# Expected: FAILED
make e2e-stop
```

### 3. Fix the Code

Make the necessary code changes in the addon source.

### 4. Verify the Test Passes

```bash
make e2e
# Expected: PASSED
```

### 5. Run the Full Suite

Ensure no regressions:

```bash
make e2e
python3 -m pytest tests/unit/ tests/integration/ --tb=short
```

## Troubleshooting

### Container Fails to Start

**Symptoms:** `make e2e-start` exits with an error, or `docker compose up` fails.

**Diagnostic steps:**

```bash
# Check if Docker daemon is running
docker info

# Check if the image can be pulled
docker pull ghcr.io/hidiv/kodi-docker:kodi20

# Check for port conflicts
lsof -i :8080
lsof -i :9090

# Check container logs
docker compose -f tests/e2e/docker-compose.yml --profile kodi20 logs
```

**Common solutions:**
- Start the Docker daemon (`sudo systemctl start docker` on Linux)
- Authenticate to ghcr.io if the image is private: `docker login ghcr.io`
- Stop other services using ports 8080, 9090, 5900, or 8000
- Remove stale containers: `docker compose -f tests/e2e/docker-compose.yml --profile kodi20 down -v`

### Connection Refused on JSON-RPC Port

**Symptoms:** Tests skip with "Could not connect KodiClient within 30s" or `KodiConnectionError` is raised.

**Diagnostic steps:**

```bash
# Check if container is running
docker ps | grep kodi-e2e

# Check container health status
docker inspect --format='{{.State.Health.Status}}' kodi-e2e-kodi20

# Test HTTP JSON-RPC manually
curl -sf -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}' \
  http://localhost:8080/jsonrpc

# Check container logs for startup errors
docker logs kodi-e2e-kodi20 --tail 50
```

**Common solutions:**
- Wait longer — Kodi may still be starting (start_period is 30s)
- Check that the `.env` file exists and contains valid credentials
- Verify no firewall rules blocking localhost connections
- Restart the container: `make e2e-stop && make e2e-start`

### Healthcheck Timeout

**Symptoms:** `make e2e-start` prints "ERROR: Healthcheck timeout after 60s for kodi20" and exits with code 1. Container logs are saved to `tests/e2e/artifacts/container_logs_kodi20_timeout.txt`.

**Diagnostic steps:**

```bash
# Read the saved container logs
cat tests/e2e/artifacts/container_logs_kodi20_timeout.txt

# Check if Kodi process is running inside the container
docker exec kodi-e2e-kodi20 ps aux | grep kodi

# Check if Xvfb display is available
docker exec kodi-e2e-kodi20 ls /tmp/.X99-lock

# Check Kodi log for startup errors
docker exec kodi-e2e-kodi20 cat /root/.kodi/temp/kodi.log | tail -50
```

**Common solutions:**
- Increase timeout: edit `HEALTHCHECK_TIMEOUT` in the Makefile (default: 60s)
- Check available system resources (RAM, disk space) — Kodi needs at least 512MB RAM
- Verify the Docker image is not corrupted: `docker pull ghcr.io/hidiv/kodi-docker:kodi20`
- Check that `guisettings.xml` is valid XML — a malformed file can prevent Kodi from starting

### Addon Shows Confirmation Dialog (Settings Not Provisioned)

**Symptoms:** Tests hang or timeout after addon is enabled. The addon appears in `Addons.GetAddons` but navigation to the addon root returns no items or times out. VNC shows a dialog asking the user to confirm settings.

**Root cause:** The addon's `settings.xml` was not provisioned before enabling the addon. Without `settings.xml`, the addon shows a blocking confirmation dialog on first launch that cannot be dismissed via JSON-RPC.

**Diagnostic steps:**

```bash
# Check if settings.xml exists in the container
docker exec kodi-e2e-kodi20 cat /root/.kodi/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml

# Connect via VNC to see the dialog
open http://localhost:8000
```

**Solutions:**
- Ensure `conftest.py` provisions `settings.xml` before calling `Addons.SetAddonEnabled`
- Verify the settings file uses Kodi 20 format: `<setting id="key">value</setting>` (not the old `<setting id="key" value="val"/>` format)
- Check that `CBILLING_API_URL` and `CBILLING_PUBLIC_KEY` are set in `.env` — these are written to `settings.xml`
- If running manually, provision settings before enabling: create the file at `/root/.kodi/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml` with the required fields

### WebSocket Connection Drops (Keepalive Ping Issue)
**Symptoms:** Tests fail intermittently with `KodiConnectionError: WebSocket connection closed` or `ConnectionClosedError`. The failure typically occurs during navigation to content-heavy sections (Live TV, Archive) where the addon makes API calls that take >20s.

**Root cause:** The `websockets` library sends keepalive pings every 20s by default. When Kodi is busy processing an addon API call, it cannot respond to the ping within the timeout, causing the library to close the connection.

**Diagnostic steps:**

```bash
# Check if the issue is timing-related (run the failing test in isolation)
KODI_VERSION=kodi20 python3 -m pytest -m e2e tests/e2e/test_navigation.py::TestNavigation::test_live_tv -v

# Check KodiClient connection parameters
grep -n "ping_interval" tests/e2e/kodi_client.py
```

**Solutions:**
- Verify `KodiClient` connects with `ping_interval=None, ping_timeout=None` — this disables the keepalive mechanism entirely
- If you see `ping_interval=20` or no explicit setting, update the `_async_connect` method:
  ```python
  self._ws = await websockets.connect(
      self._ws_url,
      ping_interval=None,
      ping_timeout=None,
  )
  ```
- Do NOT set `ping_interval` to a non-None value — addon API calls routinely take 10-25s

### Tests Skip with "Required environment variables not set"

**Symptoms:** All e2e tests are skipped with a message about missing `CBILLING_API_URL` or `CBILLING_PUBLIC_KEY`.

**Solution:**

Ensure your `.env` file in the project root contains:

```
CBILLING_API_URL=https://api.cbilling.tv
CBILLING_PUBLIC_KEY=your_key_here
```

Or export them directly:

```bash
export CBILLING_API_URL=https://api.cbilling.tv
export CBILLING_PUBLIC_KEY=your_key_here
```

### Addon ZIP Not Found

**Symptoms:** All e2e tests are skipped with "Addon ZIP not found in dist/" message.

**Solution:**

Build the addon ZIP before starting tests:

```bash
make e2e-build
```

Or run the full cycle which includes the build step:

```bash
make e2e
```

### Player Does Not Start (Player.Open returns OK but player stays empty)

**Symptoms:** A playback test calls `Player.Open` with a `plugin://` URL, gets `"result": "OK"`, but `Player.GetActivePlayers` returns an empty list. The test fails with "Player did not enter 'playing' state".

**Root cause:** `Player.Open` with a `plugin://` URL does not work for addons that resolve streams via `setResolvedUrl`. Kodi invokes the addon but does not start the player from a JSON-RPC `Player.Open` call.

**Solution:** Extract the real stream URL from the `play_cmd` query parameter and pass it directly to `Player.Open`:

```python
from urllib.parse import urlparse, parse_qs, unquote
params = parse_qs(urlparse(plugin_url).query)
stream_url = unquote(params.get("play_cmd", [""])[0])
# Player.Open with stream_url (http://...) works
```

For archive playback, `play_cmd` is empty in the EPG item URL — build the archive URL manually from the live stream URL by replacing `index.m3u8` with `video-{unixtime}-{duration}.m3u8`.

### Tests Fail with "Invalid params" After Timezone Tests (RESOLVED)

**Symptoms:** VOD or navigation tests fail with `Files.GetDirectory: [-32602] Invalid params` when run as part of the full suite, but pass in isolation.

**Root cause (identified and fixed):** Timezone tests previously used a disable/enable cycle (`Addons.SetAddonEnabled`) to apply settings changes. This left the addon in a broken state where `Files.GetDirectory` calls would fail. Since pytest runs files alphabetically, `test_vod` ran after `test_timezone` and inherited the broken state.

**Fix applied:** Each `plugin://` URL invocation starts a fresh Python process that re-reads `settings.xml` from disk. The disable/enable cycle was completely unnecessary. Now timezone tests simply write `settings.xml` via `docker exec sed -i` — no addon restart, no state pollution.

### Tests Fail with Empty Results (0 Items) in Full Suite

**Symptoms:** Tests pass in isolation but return 0 items when run as part of the full e2e suite (25+ tests). Kodi log shows `[Cbilling] Failed to get channels: HTTP 429: /streams`.

**Root cause:** The Cbilling API enforces rate limits. After 25+ tests each making API calls, the API returns HTTP 429 (Too Many Requests), causing the addon to return empty results.

**Mitigation:**
- Run test subsets rather than the full suite in one session
- Restart the container between test groups to get fresh rate-limit windows
- Consider adding small delays between test groups that make heavy API calls

## Project Structure Reference

```
tests/e2e/
├── __init__.py
├── addon_installer.py      # ZIP installation and settings provisioning
├── artifacts/              # Test artifacts (gitignored)
├── artifacts.py            # ArtifactCollector class
├── config.py               # E2EConfig dataclass and loader
├── conftest.py             # pytest fixtures and hooks
├── docker-compose.yml      # Container definitions (ZIP mount + guisettings)
├── exceptions.py           # KodiError hierarchy
├── guisettings.xml         # Kodi pre-configuration (RU locale, JSON-RPC)
├── kodi_client.py          # KodiClient (WebSocket JSON-RPC, 30s timeout)
├── requirements.txt        # E2E-specific dependencies
├── test_addon_lifecycle.py # Addon install/activate tests
├── test_localization.py    # Russian labels, English smoke test
├── test_navigation.py      # Menu navigation tests
├── test_timezone.py        # Timezone parametrized tests
└── utils.py                # strip_kodi_tags, strip_labels utilities
```

## Makefile Targets

| Target | Description | Example |
|--------|-------------|---------|
| `make e2e-build` | Build addon ZIP via `python3 build_addon.py` | `make e2e-build` |
| `make e2e-start` | Start container, wait for healthcheck | `make e2e-start KODI_VERSION=kodi21` |
| `make e2e-test` | Run e2e tests against running container | `make e2e-test KODI_VERSION=kodi20` |
| `make e2e-stop` | Stop container, remove anonymous volumes | `make e2e-stop` |
| `make e2e` | Full cycle: build → start → test → stop | `make e2e KODI_VERSION=kodi19` |
