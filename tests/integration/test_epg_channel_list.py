# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Integration tests for EPG display in channel list (issue #3).

Verifies that the API returns EPG data suitable for enhanced
channel list display (current + next program with timestamps).

Regression test for: https://github.com/HiDiv/cbilling-iptv/issues/3
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


def _load_env():
    """Load .env file into os.environ. Returns True if API credentials are available."""
    env_path = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, ".env")
    if not os.path.exists(env_path):
        return False
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()
    return bool(os.environ.get("CBILLING_API_URL")) and bool(os.environ.get("CBILLING_PUBLIC_KEY"))


_HAS_API = _load_env()

requires_api = pytest.mark.api
skip_no_creds = pytest.mark.skipif(not _HAS_API, reason="API credentials not available (.env)")


@pytest.fixture
def api():
    from api_client import CbillingAPI

    return CbillingAPI(
        base_url=os.environ.get("CBILLING_API_URL", ""),
        public_key=os.environ.get("CBILLING_PUBLIC_KEY", ""),
        timeout=15,
    )


@pytest.fixture
def adapter(api):
    from api_adapter import ApiAdapter

    return ApiAdapter(api)


@requires_api
@skip_no_creds
class TestEpgForChannelList:
    """Tests for EPG data retrieval for channel list display (issue #3)."""

    def test_get_short_epg_returns_current_program(self, adapter, api):
        """get_short_epg(alias, size=1) should return at least the current program."""
        streams = api.get_streams()
        assert len(streams) > 0, "No streams available"

        # Find first channel with an alias
        alias = streams[0].get("alias", "")
        assert alias, "First stream has no alias"

        epg = adapter.get_short_epg(alias, size=1)

        # EPG may be empty for some channels — that's OK
        if epg:
            assert isinstance(epg, list)
            assert len(epg) >= 1
            entry = epg[0]
            assert "name" in entry, "EPG entry must have 'name'"
            assert "t_time" in entry, "EPG entry must have 't_time'"
            assert "start_timestamp" in entry, "EPG entry must have 'start_timestamp'"
            assert "stop_timestamp" in entry, "EPG entry must have 'stop_timestamp'"

    def test_get_short_epg_returns_next_program(self, adapter, api):
        """get_short_epg(alias, size=2) should return current + next program."""
        streams = api.get_streams()
        assert len(streams) > 0

        # Try multiple channels — not all may have EPG
        found_next = False
        for stream in streams[:10]:
            alias = stream.get("alias", "")
            if not alias:
                continue

            epg = adapter.get_short_epg(alias, size=2)
            if epg and len(epg) >= 2:
                found_next = True
                current = epg[0]
                next_prog = epg[1]

                # Current program
                assert current.get("name"), "Current program must have name"
                assert current.get("t_time"), "Current program must have start time"

                # Next program
                assert next_prog.get("name"), "Next program must have name"
                assert next_prog.get("t_time"), "Next program must have start time"

                # Next must start after current
                curr_stop = int(current.get("stop_timestamp", 0))
                next_start = int(next_prog.get("start_timestamp", 0))
                if curr_stop and next_start:
                    assert next_start >= curr_stop, "Next program start (%d) must be >= current stop (%d)" % (
                        next_start,
                        curr_stop,
                    )
                break

        assert found_next, (
            "Could not find any channel with 2+ EPG entries among first 10 streams. "
            "This may be normal if EPG data is limited."
        )

    def test_epg_timestamps_are_valid(self, adapter, api):
        """EPG timestamps should be valid Unix timestamps (reasonable range)."""
        import time

        streams = api.get_streams()
        assert len(streams) > 0

        now = int(time.time())
        one_day = 86400

        for stream in streams[:5]:
            alias = stream.get("alias", "")
            if not alias:
                continue

            epg = adapter.get_short_epg(alias, size=2)
            if not epg:
                continue

            for entry in epg:
                start_ts = int(entry.get("start_timestamp", 0))
                stop_ts = int(entry.get("stop_timestamp", 0))

                if start_ts:
                    # Timestamp should be within 1 day of now
                    assert abs(now - start_ts) < one_day * 2, "start_timestamp %d is too far from now %d" % (
                        start_ts,
                        now,
                    )
                if stop_ts:
                    assert stop_ts > start_ts, "stop_timestamp (%d) must be > start_timestamp (%d)" % (
                        stop_ts,
                        start_ts,
                    )

    def test_channels_without_epg_do_not_crash(self, adapter, api):
        """Channels without EPG data should return empty list, not error."""
        # Use a non-existent alias to simulate channel without EPG
        epg = adapter.get_short_epg("nonexistent_channel_xyz", size=2)

        # Should return empty list or None, not raise
        assert epg is None or isinstance(epg, list)
