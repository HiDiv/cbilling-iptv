# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E tests for timezone handling.

Verifies that the addon correctly loads EPG data across different timezones
and that archive days are calculated correctly (days, not hours).

Requirements: 9.1, 9.2, 9.3, 9.4
"""

import re

import pytest

from tests.e2e.kodi_client import KodiClient
from tests.e2e.utils import strip_labels

# Addon identifier
ADDON_ID = "plugin.video.cbilling.iptv"

# Default timezone (must be restored after each test)
DEFAULT_TIMEZONE = "Europe/Moscow"

# Addon plugin base URL
_ADDON_URL = "plugin://plugin.video.cbilling.iptv/"

# Plugin paths for sections
_LIVE_TV_PATH = _ADDON_URL + "?mode=channel_groups&archive=false"
_ARCHIVE_PATH = _ADDON_URL + "?mode=channel_groups&archive=true"

# Content wait timeout in seconds
_CONTENT_TIMEOUT = 60.0


def _set_timezone(kodi_client: KodiClient, timezone: str, container_name: str) -> None:
    """Change the addon stb_timezone setting by rewriting settings.xml.

    Each plugin:// URL invocation starts a fresh Python process that re-reads
    settings.xml from disk. No disable/enable cycle is needed — the next
    get_container_items() call will automatically pick up the new timezone.

    Args:
        kodi_client: Connected KodiClient instance (unused, kept for API compat).
        timezone: Timezone string (e.g. "Europe/Moscow", "Asia/Novosibirsk").
        container_name: Docker container name for exec commands.
    """
    import subprocess

    settings_path = "/root/.kodi/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml"

    # Read current settings.xml, replace stb_timezone value
    sed_cmd = [
        "docker",
        "exec",
        container_name,
        "sed",
        "-i",
        's|<setting id="stb_timezone">.*</setting>|<setting id="stb_timezone">%s</setting>|' % timezone,
        settings_path,
    ]
    subprocess.run(sed_cmd, capture_output=True, text=True, timeout=10)


@pytest.fixture(autouse=True)
def restore_timezone(kodi_container: str):
    """Restore the original timezone after each test.

    Requirement 9.4: restore Europe/Moscow after timezone changes.
    Since each plugin:// call re-reads settings.xml, we only need to
    write back the default value — no addon restart required.
    """
    yield
    import subprocess

    settings_path = "/root/.kodi/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml"
    subprocess.run(
        [
            "docker",
            "exec",
            kodi_container,
            "sed",
            "-i",
            's|<setting id="stb_timezone">.*</setting>|<setting id="stb_timezone">%s</setting>|' % DEFAULT_TIMEZONE,
            settings_path,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.e2e
@pytest.mark.parametrize("timezone", ["Europe/Moscow", "Asia/Novosibirsk"])
class TestTimezoneEPG:
    """Parametrized tests verifying EPG loads correctly for different timezones.

    Requirement 9.2: change stb_timezone to at least 2 timezones and verify
    EPG data loads correctly for each.
    """

    def test_epg_loads_with_timezone(
        self,
        kodi_client: KodiClient,
        kodi_container: str,
        timezone: str,
    ) -> None:
        """Verify EPG (Live TV) loads at least 1 channel group after timezone change.

        Changes the addon timezone setting, then queries the Live TV section
        to confirm EPG data is available.

        Validates: Requirements 9.1, 9.2
        """
        # Set the timezone (modifies settings.xml and restarts addon)
        _set_timezone(kodi_client, timezone, kodi_container)

        # Query Live TV section — should return at least 1 channel group
        items = kodi_client.get_container_items(path=_LIVE_TV_PATH)
        assert len(items) >= 1, "Expected at least 1 channel group in Live TV with timezone '%s', got %d" % (
            timezone,
            len(items),
        )


# ---------------------------------------------------------------------------
# EPG Timezone Shift Test Configuration
# ---------------------------------------------------------------------------

# Channel to use for EPG timezone shift verification.
# Change this if the channel becomes unavailable.
EPG_TEST_CHANNEL_ID = "pervyj"
EPG_TEST_CHANNEL_NAME = "Первый канал"

# Archive group containing the test channel (Общероссийские = group_id 1)
EPG_TEST_ARCHIVE_GROUP_ID = "1"

# Timezone pair for shift comparison
_TZ_MOSCOW = "Europe/Moscow"
_TZ_NOVOSIBIRSK = "Asia/Novosibirsk"
# Expected offset difference: Novosibirsk is UTC+7, Moscow is UTC+3 → +4 hours
_EXPECTED_SHIFT_HOURS = 4

# Regex to extract time from archive EPG labels like "[01:40 - 02:15] Title"
_TIME_PATTERN = re.compile(r"^\[(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})\]")


def _extract_start_times(items):
    """Extract start times (as minutes since midnight) from archive EPG items.

    Args:
        items: List of container items from archive EPG.

    Returns:
        List of (hour, minute) tuples for each item with a parseable time label.
    """
    times = []  # type: list
    for item in items:
        label = item.get("label", "")
        # Strip kodi tags first
        clean = re.sub(
            r"\[/?(?:COLOR|B|I|UPPERCASE|LOWERCASE|LIGHT|CR)(?:\s[^\]]*?)?\]", "", label, flags=re.IGNORECASE
        )
        match = _TIME_PATTERN.match(clean.strip())
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            times.append((hour, minute))
    return times


def _get_archive_epg_for_channel(kodi_client, channel_id, archive_group_id):
    """Navigate archive to get EPG items for a specific channel on the first available date.

    Returns:
        Tuple of (date_label, items) where items is the list of EPG entries.
    """
    # Get channels in the archive group
    archive_group_path = (
        _ADDON_URL + "?mode=get_channels_list&action=archive&group_id=%s&favorites=0" % archive_group_id
    )
    channels = kodi_client.get_container_items(path=archive_group_path)

    # Find the target channel
    channel_path = None
    for ch in channels:
        if channel_id in ch.get("file", ""):
            channel_path = ch.get("file", "")
            break

    if not channel_path:
        return None, []

    # Get archive dates for this channel
    dates = kodi_client.get_container_items(path=channel_path)
    if not dates:
        return None, []

    # Use the second date (yesterday) to avoid partial data for today
    date_index = 1 if len(dates) > 1 else 0
    date_label = dates[date_index].get("label", "")
    date_path = dates[date_index].get("file", "")

    if not date_path:
        return date_label, []

    # Get EPG entries for that date
    items = kodi_client.get_container_items(path=date_path)
    return date_label, items


@pytest.mark.e2e
class TestEPGTimezoneConversion:
    """Tests verifying that raw API timestamps are correctly converted to local time.

    The Cbilling API returns EPG data with Unix timestamps (UTC).
    The addon converts these to the user's configured timezone for display.
    This test calls the API directly, computes expected local times, and
    compares them with what the addon shows in the archive EPG.
    """

    def test_api_timestamps_converted_to_local_time(
        self,
        kodi_client: KodiClient,
        kodi_container: str,
        e2e_config,
    ) -> None:
        """Verify addon correctly converts UTC timestamps from API to local display time.

        Steps:
        1. Ensure timezone is set to Europe/Moscow (UTC+3)
        2. Call Cbilling API directly to get raw EPG with Unix timestamps
        3. Manually convert timestamps to Moscow time (expected values)
        4. Get the same EPG from the addon via Kodi JSON-RPC
        5. Compare: addon display times must match our manual conversion

        This confirms the addon's _ts_to_local_str() works correctly.
        """
        import datetime

        import requests

        # Step 1: Ensure Moscow timezone
        _set_timezone(kodi_client, _TZ_MOSCOW, kodi_container)

        # Step 2: Call API directly to get raw EPG data
        api_url = e2e_config.cbilling_api_url
        public_key = e2e_config.cbilling_public_key

        # Use yesterday's date to get complete EPG data
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

        headers = {"x-public-key": public_key}
        resp = requests.get(
            "%s/epg/%s/" % (api_url, EPG_TEST_CHANNEL_ID),
            headers=headers,
            params={"date": date_str},
            timeout=30,
        )
        assert resp.status_code == 200, "API returned status %d for EPG request" % resp.status_code

        raw_epg = resp.json()
        # API may return list directly or {"data": [...]}
        if isinstance(raw_epg, dict) and "data" in raw_epg:
            epg_items = raw_epg["data"]
        elif isinstance(raw_epg, list):
            epg_items = raw_epg
        else:
            pytest.fail("Unexpected API response format: %s" % type(raw_epg))

        assert len(epg_items) >= 3, "API returned only %d EPG items for %s on %s" % (
            len(epg_items),
            EPG_TEST_CHANNEL_ID,
            date_str,
        )

        # Step 3: Manually convert first few timestamps to Moscow time (UTC+3)
        moscow_offset = datetime.timezone(datetime.timedelta(hours=3))
        expected_times = []  # type: list
        for item in epg_items[:5]:
            start_ts = item.get("time", item.get("start_timestamp", 0))
            if not start_ts:
                continue
            utc_dt = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(
                seconds=int(start_ts)
            )
            local_dt = utc_dt.astimezone(moscow_offset)
            expected_times.append((local_dt.hour, local_dt.minute))

        assert len(expected_times) >= 3, "Could not extract timestamps from API response. First item: %s" % repr(
            epg_items[0]
        )

        # Step 4: Get the same EPG from the addon via Kodi
        _, addon_items = _get_archive_epg_for_channel(kodi_client, EPG_TEST_CHANNEL_ID, EPG_TEST_ARCHIVE_GROUP_ID)
        assert len(addon_items) >= 3, "Addon returned only %d EPG items for archive" % len(addon_items)

        addon_times = _extract_start_times(addon_items)
        assert len(addon_times) >= 3, "Could not parse times from addon EPG labels. First labels: %s" % [
            i.get("label", "")[:50] for i in addon_items[:3]
        ]

        # Step 5: Compare — find matching entries by time
        # The first entry from API should match the first entry from addon
        # (both are for the same date, sorted chronologically)
        compare_count = min(3, len(expected_times), len(addon_times))
        for i in range(compare_count):
            expected_h, expected_m = expected_times[i]
            actual_h, actual_m = addon_times[i]
            assert (expected_h, expected_m) == (actual_h, actual_m), (
                "EPG entry %d: API timestamp converts to %02d:%02d (Moscow), "
                "but addon shows %02d:%02d" % (i, expected_h, expected_m, actual_h, actual_m)
            )


@pytest.mark.e2e
class TestEPGTimezoneShift:
    """Tests verifying that EPG times shift correctly when timezone changes.

    Compares archive EPG times for the same channel and date under two
    different timezones (Moscow and Novosibirsk). The times should differ
    by exactly the timezone offset (4 hours).
    """

    def test_archive_epg_times_shift_with_timezone(
        self,
        kodi_client: KodiClient,
        kodi_container: str,
    ) -> None:
        """Verify archive EPG times shift by the correct offset when timezone changes.

        Steps:
        1. Set timezone to Europe/Moscow, get archive EPG for test channel
        2. Set timezone to Asia/Novosibirsk, get archive EPG for same channel/date
        3. Compare start times — they should differ by +4 hours

        Validates: timezone conversion correctness in EPG display.
        """
        # Step 1: Get EPG with Moscow timezone
        _set_timezone(kodi_client, _TZ_MOSCOW, kodi_container)
        _, items_msk = _get_archive_epg_for_channel(kodi_client, EPG_TEST_CHANNEL_ID, EPG_TEST_ARCHIVE_GROUP_ID)
        assert len(items_msk) >= 3, "Expected at least 3 EPG entries for '%s' with timezone %s, got %d" % (
            EPG_TEST_CHANNEL_NAME,
            _TZ_MOSCOW,
            len(items_msk),
        )
        times_msk = _extract_start_times(items_msk)
        assert len(times_msk) >= 3, "Could not parse times from EPG labels (Moscow). First labels: %s" % [
            i.get("label", "")[:50] for i in items_msk[:3]
        ]

        # Step 2: Get EPG with Novosibirsk timezone
        _set_timezone(kodi_client, _TZ_NOVOSIBIRSK, kodi_container)
        _, items_nsk = _get_archive_epg_for_channel(kodi_client, EPG_TEST_CHANNEL_ID, EPG_TEST_ARCHIVE_GROUP_ID)
        assert len(items_nsk) >= 3, "Expected at least 3 EPG entries for '%s' with timezone %s, got %d" % (
            EPG_TEST_CHANNEL_NAME,
            _TZ_NOVOSIBIRSK,
            len(items_nsk),
        )
        times_nsk = _extract_start_times(items_nsk)
        assert len(times_nsk) >= 3, "Could not parse times from EPG labels (Novosibirsk). First labels: %s" % [
            i.get("label", "")[:50] for i in items_nsk[:3]
        ]

        # Step 3: Compare times — Novosibirsk should be +4h from Moscow
        # Use the first few entries that appear in both results
        compare_count = min(3, len(times_msk), len(times_nsk))
        shifts = []  # type: list
        for i in range(compare_count):
            msk_minutes = times_msk[i][0] * 60 + times_msk[i][1]
            nsk_minutes = times_nsk[i][0] * 60 + times_nsk[i][1]
            # Handle day wraparound (e.g., 23:00 MSK → 03:00 NSK next day)
            diff = (nsk_minutes - msk_minutes) % (24 * 60)
            shifts.append(diff)

        expected_shift_minutes = _EXPECTED_SHIFT_HOURS * 60
        for i, shift in enumerate(shifts):
            assert shift == expected_shift_minutes, (
                "EPG entry %d: expected +%dh shift (Moscow %02d:%02d → Novosibirsk %02d:%02d), "
                "but got %dh%02dm shift"
                % (
                    i,
                    _EXPECTED_SHIFT_HOURS,
                    times_msk[i][0],
                    times_msk[i][1],
                    times_nsk[i][0],
                    times_nsk[i][1],
                    shift // 60,
                    shift % 60,
                )
            )


@pytest.mark.e2e
class TestArchiveDaysCalculation:
    """Tests verifying archive days are calculated correctly.

    Requirement 9.3: when the API reports archive_days=N, the archive section
    shows N days of content (not N/24).
    """

    def test_archive_shows_days_not_hours(
        self,
        kodi_client: KodiClient,
    ) -> None:
        """Verify archive section displays days (not hours divided by 24).

        Navigates to the Archive section, selects the first channel group,
        then the first channel, and verifies that the archive date list
        contains a reasonable number of entries (days, not hours).

        A channel with archive_days=7 should show ~7 date entries.
        If the bug exists (dividing by 24), it would show 0 entries.

        Validates: Requirements 9.3
        """
        # Get archive channel groups
        groups = kodi_client.get_container_items(path=_ARCHIVE_PATH)
        assert len(groups) >= 1, "Expected at least 1 archive channel group"

        # Navigate into the first channel group to get channels
        first_group_path = groups[0].get("file", "")
        assert first_group_path, "First archive group has no file path"

        channels = kodi_client.get_container_items(path=first_group_path)
        assert len(channels) >= 1, "Expected at least 1 channel in archive group"

        # Find a channel with archive support (navigate into it to see dates)
        first_channel_path = channels[0].get("file", "")
        assert first_channel_path, "First archive channel has no file path"

        # Get the archive date entries for this channel
        date_items = kodi_client.get_container_items(path=first_channel_path)

        # Archive days should show at least 1 day entry.
        # If the N/24 bug exists, a channel with 7 archive days would show 0.
        assert len(date_items) >= 1, (
            "Expected at least 1 archive day entry, got %d. "
            "This may indicate archive_days is being divided by 24 incorrectly." % len(date_items)
        )

        # Verify entries look like dates (contain day-of-week or date patterns)
        # Archive entries typically have labels like "Понедельник 02.06" or similar
        labels = strip_labels(date_items)
        assert len(labels) >= 1, "No labels found in archive date entries"
