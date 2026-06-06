# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for ApiAdapter: EPG timezone conversion, EPG data, archive days.

Migrated from: test_epg_timezone.py, test_epg.py, test_archive_days.py
"""

import os
import sys

import pytest

# Ensure resources/lib and vendor are on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))

from api_adapter import ApiAdapter


class FakeAPI:
    """Minimal fake API client for offline testing."""

    def get_streams(self):
        return []

    def get_epg_current(self, alias, num=5):
        return []

    def get_epg_day(self, alias, date=None):
        return []

    def get_epg_now(self, alias):
        return []

    def invalidate_streams_cache(self):
        pass


# ---------------------------------------------------------------------------
# _ts_to_local_str timezone conversion (from test_epg_timezone.py)
# ---------------------------------------------------------------------------

# Known timestamp: 2026-03-15 12:00:00 UTC
_TS_MARCH_15 = 1773576000


@pytest.mark.parametrize(
    "tz_name, expected_time",
    [
        ("Europe/Moscow", "15:00"),
        ("Europe/Tallinn", "14:00"),
        ("Europe/Kaliningrad", "14:00"),
        ("Europe/London", "12:00"),
        ("America/New_York", "08:00"),
        ("Asia/Tokyo", "21:00"),
        ("Europe/Berlin", "13:00"),
    ],
)
def test_ts_to_local_str(tz_name, expected_time):
    adapter = ApiAdapter(FakeAPI(), timezone_name=tz_name)
    assert adapter._ts_to_local_str(_TS_MARCH_15) == expected_time


# ---------------------------------------------------------------------------
# _convert_epg_entry timezone conversion (from test_epg_timezone.py)
# ---------------------------------------------------------------------------

_EPG_ITEM = {
    "date": "2026-03-15 15:00:00",
    "date_to": "2026-03-15 16:00:00",
    "time": _TS_MARCH_15,
    "time_to": _TS_MARCH_15 + 3600,
    "name": "Test Program",
    "descr": "Test description",
    "duration": 3600,
    "progress": 50,
}


def test_convert_epg_entry_tallinn():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Tallinn")
    entry = adapter._convert_epg_entry(_EPG_ITEM)
    assert entry["t_time"] == "14:00"
    assert entry["t_time_to"] == "15:00"
    assert entry["start_timestamp"] == str(_TS_MARCH_15)
    assert entry["stop_timestamp"] == str(_TS_MARCH_15 + 3600)


def test_convert_epg_entry_moscow():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    entry = adapter._convert_epg_entry(_EPG_ITEM)
    assert entry["t_time"] == "15:00"


def test_convert_epg_entry_tokyo_ignores_date_field():
    """Verify that the 'date' string field is ignored in favor of Unix timestamps."""
    adapter = ApiAdapter(FakeAPI(), timezone_name="Asia/Tokyo")
    entry = adapter._convert_epg_entry(_EPG_ITEM)
    assert entry["t_time"] == "21:00"


# ---------------------------------------------------------------------------
# Fallback behavior when no timezone is configured
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tz_input",
    [None, "", "Invalid/Timezone"],
)
def test_fallback_no_timezone(tz_input):
    adapter = ApiAdapter(FakeAPI(), timezone_name=tz_input)
    assert adapter._tz_fallback is True


def test_valid_timezone_no_fallback():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    assert adapter._tz_fallback is False
    assert adapter._user_tz is not None


def test_fallback_produces_valid_time():
    adapter = ApiAdapter(FakeAPI(), timezone_name=None)
    result = adapter._ts_to_local_str(1773756000)
    assert result and len(result) == 5 and ":" in result


# ---------------------------------------------------------------------------
# Edge cases (from test_epg_timezone.py)
# ---------------------------------------------------------------------------


def test_ts_zero_returns_empty():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    assert adapter._ts_to_local_str(0) == ""


def test_ts_negative_returns_empty():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    assert adapter._ts_to_local_str(-1) == ""


def test_ts_string_timestamp():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    assert adapter._ts_to_local_str("1773576000") == "15:00"


def test_ts_empty_string_returns_empty():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    assert adapter._ts_to_local_str("") == ""


def test_convert_epg_entry_none_returns_none():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    assert adapter._convert_epg_entry(None) is None


def test_convert_epg_entry_no_timestamps():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    result = adapter._convert_epg_entry({"name": "Test"})
    assert result["t_time"] == ""
    assert result["t_time_to"] == ""


def test_ts_custom_format():
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Moscow")
    assert adapter._ts_to_local_str(1773576000, "%Y-%m-%d %H:%M") == "2026-03-15 15:00"


# ---------------------------------------------------------------------------
# Cache recalculation simulation (from test_epg_timezone.py)
# ---------------------------------------------------------------------------


def test_cache_recalculation():
    """Cached EPG data with Moscow t_time gets recalculated for Tallinn."""
    adapter = ApiAdapter(FakeAPI(), timezone_name="Europe/Tallinn")
    recalc_start = adapter._ts_to_local_str("1773576000")
    recalc_stop = adapter._ts_to_local_str("1773579600")
    assert recalc_start == "14:00"
    assert recalc_stop == "15:00"


# ---------------------------------------------------------------------------
# API-dependent tests (from test_epg.py, test_archive_days.py)
# These require live API credentials and are skipped when .env is absent.
# ---------------------------------------------------------------------------


def _load_env():
    """Load .env file and return True if API credentials are available."""
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

# Mark for explicit opt-in: run with `pytest -m api`
# Also skip if credentials are missing even when explicitly requested
requires_api = pytest.mark.api
skip_no_creds = pytest.mark.skipif(not _HAS_API, reason="API credentials not available (.env)")


@requires_api
@skip_no_creds
def test_epg_day_returns_data():
    """Smoke test: EPG day endpoint returns a list of entries."""
    import datetime

    from api_client import CbillingAPI

    api = CbillingAPI(
        base_url=os.environ["CBILLING_API_URL"],
        public_key=os.environ["CBILLING_PUBLIC_KEY"],
    )
    adapter = ApiAdapter(api)
    streams = api.get_streams()
    assert len(streams) > 0, "No streams returned"

    alias = streams[0].get("alias")
    today = datetime.date.today().strftime("%Y-%m-%d")
    epg = adapter.get_day_epg(alias, date=today)
    assert isinstance(epg, list)


@requires_api
@skip_no_creds
def test_archive_days_values():
    """Smoke test: streams with archive have positive archive_days."""
    from api_client import CbillingAPI

    api = CbillingAPI(
        base_url=os.environ["CBILLING_API_URL"],
        public_key=os.environ["CBILLING_PUBLIC_KEY"],
    )
    streams = api.get_streams()
    archive_streams = [s for s in streams if s.get("archive") == 1]
    assert len(archive_streams) > 0, "No archive streams found"
    for s in archive_streams[:5]:
        assert s.get("archive_days", 0) > 0, "archive_days should be > 0 for %s" % s.get("alias")
