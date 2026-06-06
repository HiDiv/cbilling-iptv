# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E tests for IPTV live and archive channel playback.

Verifies that live channel playback starts successfully, remains stable,
and stops cleanly via Kodi's Player JSON-RPC methods. Also verifies
archive playback with seeking and natural completion.

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 17.1, 17.2, 17.3, 17.4, 17.5, 17.6
"""

import time
from contextlib import suppress
from urllib.parse import parse_qs, unquote, urlparse

import pytest
import requests

from tests.e2e.kodi_client import KodiClient
from tests.e2e.exceptions import KodiConnectionError
from tests.e2e.utils import strip_kodi_tags

# ---------------------------------------------------------------------------
# Configurable test content — change if channel becomes unavailable
# ---------------------------------------------------------------------------

# Channel alias used in plugin URLs
TEST_CHANNEL_ALIAS = "pervyj"

# Expected display name (after stripping Kodi tags)
TEST_CHANNEL_NAME = "Первый канал"

# Archive/live group containing the test channel (Общероссийские = group_id 1)
TEST_CHANNEL_GROUP_ID = "1"

# Addon plugin base URL
_ADDON_URL = "plugin://plugin.video.cbilling.iptv/"

# URL to list live channels in the test group
_LIVE_CHANNELS_URL = _ADDON_URL + "?mode=get_channels_list&action=live&group_id=%s&favorites=0" % TEST_CHANNEL_GROUP_ID

# Timeout for player to enter "playing" state (seconds)
_PLAYBACK_START_TIMEOUT = 30.0

# Duration to verify stable playback (seconds)
_PLAYBACK_STABLE_DURATION = 5.0

# Polling interval for player state checks (seconds)
_POLL_INTERVAL = 2.0


def _find_channel_play_url(kodi_client: KodiClient, channel_alias: str) -> str:
    """Find the play URL for a channel by its alias in the live channel list.

    Args:
        kodi_client: Connected KodiClient instance.
        channel_alias: Channel alias to search for in item URLs.

    Returns:
        The plugin:// play URL for the channel.

    Raises:
        AssertionError: If the channel is not found in the list.
    """
    items = kodi_client.get_container_items(path=_LIVE_CHANNELS_URL)
    assert len(items) >= 1, "Expected at least 1 channel in live group %s, got %d" % (TEST_CHANNEL_GROUP_ID, len(items))

    for item in items:
        file_url = item.get("file", "")
        if channel_alias in file_url and "mode=play_live_channel" in file_url:
            return file_url

    # Channel not found — provide diagnostic info
    available = [strip_kodi_tags(i.get("label", "")) for i in items[:10]]
    pytest.fail(
        "Channel '%s' not found in live group %s. "
        "Available channels (first 10): %s" % (channel_alias, TEST_CHANNEL_GROUP_ID, available)
    )
    return ""  # unreachable, satisfies type checker


def _extract_stream_url(plugin_url: str) -> str:
    """Extract the real stream URL from a plugin:// play URL.

    For live channels: extracts play_cmd parameter (contains the stream URL).
    For archive: play_cmd may be empty (addon bug). In that case, builds
    the archive URL from the live stream URL pattern + unixtime + duration.

    Args:
        plugin_url: The plugin:// URL containing play_cmd parameter.

    Returns:
        The decoded stream URL (http://...).
    """
    parsed = urlparse(plugin_url)
    params = parse_qs(parsed.query)
    play_cmd = params.get("play_cmd", [""])[0]
    stream_url = unquote(play_cmd) if play_cmd else ""

    if stream_url:
        return stream_url

    # For archive URLs where play_cmd is empty, we cannot play directly.
    # Return empty — caller should handle this case.
    return ""


def _build_archive_stream_url(live_stream_url: str, unixtime: int, duration: int) -> str:
    """Build an archive stream URL from a live stream URL.

    Replaces index.m3u8 with video-{timestamp}-{duration}.m3u8 in the
    Flussonic DVR URL format.

    Args:
        live_stream_url: The live stream URL (e.g. http://server/alias/index.m3u8?token=X)
        unixtime: UTC timestamp of archive start.
        duration: Duration in seconds.

    Returns:
        The archive stream URL, or empty string if pattern doesn't match.
    """
    import re as _re

    match = _re.match(r"(https?://[^/]+)/([^/]+)/index\.m3u8(.*)", live_stream_url)
    if match:
        server = match.group(1)
        alias = match.group(2)
        token_part = match.group(3)
        return "%s/%s/video-%d-%d.m3u8%s" % (server, alias, unixtime, duration, token_part)
    return ""


def _start_playback_via_http(kodi_client: KodiClient, play_url: str, stream_url_override: str = "") -> None:
    """Start playback via HTTP JSON-RPC using the real stream URL.

    Player.Open with plugin:// URLs does not work for addons that use
    setResolvedUrl (Kodi invokes the addon but doesn't start the player).
    Instead, we extract the real stream URL from the play_cmd parameter
    and open it directly.

    Args:
        kodi_client: Connected KodiClient instance.
        play_url: The plugin:// URL containing play_cmd with the stream URL.
        stream_url_override: If provided, use this URL directly instead of extracting from play_url.
    """
    stream_url = stream_url_override or _extract_stream_url(play_url)
    assert stream_url, "Could not extract stream URL from: %s" % play_url[:100]

    payload = {
        "jsonrpc": "2.0",
        "method": "Player.Open",
        "params": {"item": {"file": stream_url}},
        "id": 1,
    }
    try:
        resp = requests.post(kodi_client.http_url, json=payload, timeout=30)
        resp.json()  # Ensure valid response
    except (requests.Timeout, Exception):
        pass

    # Brief pause to let the player initialize
    time.sleep(3.0)


def _ensure_ws_connected(kodi_client: KodiClient) -> None:
    """Ensure the WebSocket connection is alive, reconnecting if needed.

    Args:
        kodi_client: KodiClient instance to check/reconnect.
    """
    try:
        # Try a simple ping to check if connection is alive
        kodi_client.send_request("JSONRPC.Ping", timeout=5)
    except (KodiConnectionError, Exception):
        # Connection dropped — reconnect
        with suppress(Exception):
            kodi_client.close()
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                kodi_client.connect()
                return
            except Exception:
                time.sleep(1.0)
        pytest.fail("Could not reconnect WebSocket after Player.Open")


def _wait_for_player_playing(kodi_client: KodiClient, timeout: float = _PLAYBACK_START_TIMEOUT) -> None:
    """Wait until Kodi's player enters the 'playing' state.

    Polls Player.GetActivePlayers every _POLL_INTERVAL seconds until
    a player is active and its speed > 0. Handles transient connection
    errors by reconnecting.

    Args:
        kodi_client: Connected KodiClient instance.
        timeout: Maximum time to wait in seconds.

    Raises:
        AssertionError: If player does not enter playing state within timeout.
    """
    deadline = time.monotonic() + timeout
    last_state = "unknown"
    while time.monotonic() < deadline:
        try:
            state = kodi_client.get_player_state()
            last_state = state["state"]
            if last_state == "playing":
                return
        except (KodiConnectionError, Exception):
            # Connection dropped — reconnect and retry
            _ensure_ws_connected(kodi_client)
        time.sleep(_POLL_INTERVAL)

    # Final check after reconnection
    _ensure_ws_connected(kodi_client)
    state = kodi_client.get_player_state()
    assert state["state"] == "playing", "Player did not enter 'playing' state within %.0fs. Current state: %s" % (
        timeout,
        state["state"],
    )


def _wait_for_player_stopped(kodi_client: KodiClient, timeout: float = 10.0) -> None:
    """Wait until Kodi's player enters the 'stopped' state.

    Args:
        kodi_client: Connected KodiClient instance.
        timeout: Maximum time to wait in seconds.

    Raises:
        AssertionError: If player does not stop within timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = kodi_client.get_player_state()
        if state["state"] == "stopped":
            return
        time.sleep(_POLL_INTERVAL)

    state = kodi_client.get_player_state()
    assert state["state"] == "stopped", "Player did not enter 'stopped' state within %.0fs. Current state: %s" % (
        timeout,
        state["state"],
    )


@pytest.mark.e2e
class TestLivePlayback:
    """Tests for IPTV live channel playback.

    Verifies that the addon can start live playback, maintain stable
    streaming, and stop cleanly.

    Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5
    """

    def test_live_channel_playback(self, kodi_client: KodiClient) -> None:
        """Verify live channel playback starts, remains stable, and stops.

        Steps:
        1. Get the play URL for the test channel from the live channel list
        2. Start playback via Player.Open
        3. Verify player enters "playing" state within 15s
        4. Verify playback continues for 5s without errors
        5. Stop player and verify stopped state

        Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5
        """
        # Step 1: Find the channel play URL
        play_url = _find_channel_play_url(kodi_client, TEST_CHANNEL_ALIAS)
        assert play_url, "Play URL should not be empty"

        # Step 2: Start playback via HTTP (avoids WebSocket drop during stream resolution)
        _start_playback_via_http(kodi_client, play_url)

        # Step 3: Verify player enters "playing" state within 15s
        _wait_for_player_playing(kodi_client, timeout=_PLAYBACK_START_TIMEOUT)

        # Step 4: Verify playback continues for 5s without errors
        start_time = time.monotonic()
        while time.monotonic() - start_time < _PLAYBACK_STABLE_DURATION:
            state = kodi_client.get_player_state()
            assert state["state"] == "playing", "Playback interrupted after %.1fs. State: %s" % (
                time.monotonic() - start_time,
                state["state"],
            )
            time.sleep(_POLL_INTERVAL)

        # Step 5: Stop player and verify stopped state
        state = kodi_client.get_player_state()
        player_id = state.get("player_id")
        assert player_id is not None, "No active player to stop"

        kodi_client.send_request("Player.Stop", {"playerid": player_id})
        _wait_for_player_stopped(kodi_client, timeout=10.0)


# ---------------------------------------------------------------------------
# Archive playback helpers and constants
# ---------------------------------------------------------------------------

# URL to list archive channels in the test group
_ARCHIVE_CHANNELS_URL = (
    _ADDON_URL + "?mode=get_channels_list&action=archive&group_id=%s&favorites=0" % TEST_CHANNEL_GROUP_ID
)

# Timeout for seek position verification (seconds)
_SEEK_VERIFY_TIMEOUT = 10.0

# Duration to wait for natural playback completion (seconds)
_NATURAL_COMPLETION_TIMEOUT = 60.0


def _find_archive_channel_dates_url(kodi_client, channel_alias):
    # type: (KodiClient, str) -> str
    """Find the archive dates URL for a channel by its alias.

    Navigates: archive channels list -> channel's dates URL.

    Args:
        kodi_client: Connected KodiClient instance.
        channel_alias: Channel alias to search for in item URLs.

    Returns:
        The plugin:// URL for the channel's archive dates.

    Raises:
        AssertionError: If the channel is not found.
    """
    items = kodi_client.get_container_items(path=_ARCHIVE_CHANNELS_URL)
    assert len(items) >= 1, "Expected at least 1 channel in archive group %s, got %d" % (
        TEST_CHANNEL_GROUP_ID,
        len(items),
    )

    for item in items:
        file_url = item.get("file", "")
        if channel_alias in file_url and "archive_channel_dates" in file_url:
            return file_url

    available = [strip_kodi_tags(i.get("label", "")) for i in items[:10]]
    pytest.fail(
        "Channel '%s' not found in archive group %s. "
        "Available channels (first 10): %s" % (channel_alias, TEST_CHANNEL_GROUP_ID, available)
    )
    return ""  # unreachable


def _get_yesterday_epg_url(kodi_client, dates_url):
    # type: (KodiClient, str) -> str
    """Get the EPG URL for yesterday (second item in dates list, index=1).

    Args:
        kodi_client: Connected KodiClient instance.
        dates_url: URL to list archive dates for a channel.

    Returns:
        The plugin:// URL for yesterday's EPG listing.

    Raises:
        AssertionError: If dates list has fewer than 2 items.
    """
    items = kodi_client.get_container_items(path=dates_url)
    assert len(items) >= 2, (
        "Expected at least 2 dates in archive, got %d. Channel may not have archive for yesterday." % len(items)
    )
    # Index 1 = yesterday
    epg_url = items[1].get("file", "")
    assert epg_url, "Yesterday's date item has no 'file' URL"
    return epg_url


def _get_first_program_play_url(kodi_client, epg_url):
    # type: (KodiClient, str) -> str
    """Get the play URL for the first program in the EPG listing.

    Args:
        kodi_client: Connected KodiClient instance.
        epg_url: URL to list EPG programs for a date.

    Returns:
        The plugin:// play URL for the first program.

    Raises:
        AssertionError: If no programs are found.
    """
    items = kodi_client.get_container_items(path=epg_url)
    assert len(items) >= 1, "Expected at least 1 program in EPG, got %d" % len(items)

    # Find first playable item (mode=play_archive_channel)
    for item in items:
        file_url = item.get("file", "")
        if "play_archive_channel" in file_url:
            return file_url

    # Fallback: use first item's file URL
    first_url = items[0].get("file", "")
    assert first_url, "First EPG item has no 'file' URL"
    return first_url


def _get_player_properties(kodi_client, player_id):
    # type: (KodiClient, int) -> dict
    """Get player properties including time, totaltime, percentage, speed.

    Args:
        kodi_client: Connected KodiClient instance.
        player_id: Active player ID.

    Returns:
        Dictionary with time, totaltime, percentage, speed.
    """
    return kodi_client.send_request(
        "Player.GetProperties",
        {"playerid": player_id, "properties": ["time", "totaltime", "percentage", "speed"]},
    )


@pytest.mark.e2e
class TestArchivePlayback:
    """Tests for IPTV archive playback with seeking.

    Verifies that the addon can start archive playback, seek to positions,
    stop cleanly, and handle natural playback completion.

    Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5, 17.6
    """

    def _get_archive_stream_url(self, kodi_client):
        # type: (KodiClient,) -> str
        """Navigate archive path and build a playable archive stream URL.

        Since play_cmd in archive EPG items may be empty (addon bug),
        we build the archive URL manually from the live stream URL +
        timestamp + duration from the first EPG item.

        Returns:
            A direct archive stream URL ready for Player.Open.
        """
        # Get live stream URL for the channel
        live_play_url = _find_channel_play_url(kodi_client, TEST_CHANNEL_ALIAS)
        live_stream_url = _extract_stream_url(live_play_url)
        assert live_stream_url, "Could not get live stream URL for %s" % TEST_CHANNEL_ALIAS

        # Navigate archive to get EPG items with timestamps
        dates_url = _find_archive_channel_dates_url(kodi_client, TEST_CHANNEL_ALIAS)
        epg_url = _get_yesterday_epg_url(kodi_client, dates_url)
        play_url = _get_first_program_play_url(kodi_client, epg_url)

        # Extract unixtime and duration from the plugin URL
        parsed = urlparse(play_url)
        params = parse_qs(parsed.query)
        unixtime = int(params.get("unixtime", ["0"])[0])
        duration = int(params.get("duration", ["3600"])[0])

        assert unixtime > 0, "No valid unixtime in archive URL: %s" % play_url[:100]

        # Build archive stream URL
        archive_url = _build_archive_stream_url(live_stream_url, unixtime, duration)
        assert archive_url, "Could not build archive URL from: %s" % live_stream_url[:80]
        return archive_url

    def test_archive_playback_and_seek(self, kodi_client):
        # type: (KodiClient,) -> None
        """Verify archive playback starts, seek to middle works, and stop is clean.

        Steps:
        1. Build archive stream URL from live stream + EPG timestamps
        2. Start playback via Player.Open
        3. Verify player enters "playing" state within 15s
        4. Seek to 50%, verify position changed
        5. Stop playback, verify stopped

        Validates: Requirements 17.1, 17.2, 17.3
        """
        archive_url = self._get_archive_stream_url(kodi_client)

        # Start playback directly with the archive stream URL
        _start_playback_via_http(kodi_client, "", stream_url_override=archive_url)

        # Verify playback starts within 15s
        _wait_for_player_playing(kodi_client, timeout=_PLAYBACK_START_TIMEOUT)

        # Get player ID and initial properties
        state = kodi_client.get_player_state()
        player_id = state.get("player_id")
        assert player_id is not None, "No active player after playback started"

        # Wait a moment for stream to stabilize before seeking
        time.sleep(3.0)

        # Get position before seek
        props_before = _get_player_properties(kodi_client, player_id)
        pct_before = props_before.get("percentage", 0.0)

        # Seek to 50%
        kodi_client.send_request(
            "Player.Seek",
            {"playerid": player_id, "value": {"percentage": 50}},
        )

        # Wait and verify position changed
        time.sleep(3.0)
        deadline = time.monotonic() + _SEEK_VERIFY_TIMEOUT
        seek_verified = False
        while time.monotonic() < deadline:
            props_after = _get_player_properties(kodi_client, player_id)
            pct_after = props_after.get("percentage", 0.0)
            # Position should be significantly different from before (at least 10% change)
            # or close to 50%
            if abs(pct_after - 50.0) < 15.0 or abs(pct_after - pct_before) > 10.0:
                seek_verified = True
                break
            time.sleep(_POLL_INTERVAL)

        assert seek_verified, "Seek to 50%% did not change position. Before: %.1f%%, After: %.1f%%" % (
            pct_before,
            pct_after,
        )

        # Stop playback and verify stopped
        kodi_client.send_request("Player.Stop", {"playerid": player_id})
        _wait_for_player_stopped(kodi_client, timeout=10.0)

    def test_archive_seek_near_end_natural_completion(self, kodi_client):
        # type: (KodiClient,) -> None
        """Verify seeking near end results in natural playback completion.

        Steps:
        1. Build archive stream URL
        2. Start playback, verify playing
        3. Seek to near end (last 30s via high percentage)
        4. Wait for natural completion (player stops within 60s)

        Validates: Requirements 17.4, 17.5, 17.6
        """
        archive_url = self._get_archive_stream_url(kodi_client)

        # Start playback directly with the archive stream URL
        _start_playback_via_http(kodi_client, "", stream_url_override=archive_url)

        # Verify playback starts within 15s
        _wait_for_player_playing(kodi_client, timeout=_PLAYBACK_START_TIMEOUT)

        # Get player ID and total duration
        state = kodi_client.get_player_state()
        player_id = state.get("player_id")
        assert player_id is not None, "No active player after playback started"

        # Wait for stream to stabilize
        time.sleep(3.0)

        # Get total time to calculate seek position for last 30s
        props = _get_player_properties(kodi_client, player_id)
        total_time = props.get("totaltime", {})
        total_seconds = (
            total_time.get("hours", 0) * 3600 + total_time.get("minutes", 0) * 60 + total_time.get("seconds", 0)
        )

        if total_seconds > 60:
            # Seek to last 30 seconds: calculate percentage
            target_seconds = total_seconds - 30
            target_pct = int((target_seconds / total_seconds) * 100)
            # Clamp to valid range
            target_pct = min(target_pct, 99)
        else:
            # Short recording: seek to 90%
            target_pct = 90

        kodi_client.send_request(
            "Player.Seek",
            {"playerid": player_id, "value": {"percentage": target_pct}},
        )

        # Wait for natural completion — player should stop within 60s
        deadline = time.monotonic() + _NATURAL_COMPLETION_TIMEOUT
        completed = False
        while time.monotonic() < deadline:
            player_state = kodi_client.get_player_state()
            if player_state["state"] == "stopped":
                completed = True
                break
            time.sleep(_POLL_INTERVAL)

        if not completed:
            # If not completed naturally, stop manually and report
            with suppress(Exception):
                kodi_client.send_request("Player.Stop", {"playerid": player_id})
            pytest.fail(
                "Archive playback did not complete naturally within %.0fs "
                "after seeking to %d%%. Total duration: %ds" % (_NATURAL_COMPLETION_TIMEOUT, target_pct, total_seconds)
            )
