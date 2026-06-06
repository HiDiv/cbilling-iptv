# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for CbillingAPI client.

Migrated from: test_new_api_client.py
All tests require live API credentials and are skipped when .env is absent.
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

# Mark for explicit opt-in: run with `pytest -m api`
# Also skip if credentials are missing even when explicitly requested
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
def test_auth_info(api):
    info = api.get_auth_info()
    assert "public_token" in info or "server" in info


@requires_api
@skip_no_creds
def test_streams(api):
    streams = api.get_streams()
    assert len(streams) > 0
    s = streams[0]
    assert "name" in s
    assert "alias" in s


@requires_api
@skip_no_creds
def test_genres(adapter):
    genres = adapter.get_genres()
    assert len(genres) > 0
    assert "id" in genres[0]
    assert "title" in genres[0]


@requires_api
@skip_no_creds
def test_channels_stalker_format(adapter):
    channels = adapter.get_all_channels()
    assert len(channels) > 0
    ch = channels[0]
    assert "id" in ch
    assert "name" in ch
    assert "cmd" in ch


@requires_api
@skip_no_creds
def test_epg_current(adapter):

    short = adapter.get_short_epg("pervyj", size=3)
    assert isinstance(short, list)


@requires_api
@skip_no_creds
def test_vod_categories(api):
    cats = api.get_vod_categories()
    if isinstance(cats, dict) and "data" in cats:
        cats = cats["data"]
    assert isinstance(cats, list)
    assert len(cats) > 0


@requires_api
@skip_no_creds
def test_servers(api):
    servers = api.get_servers()
    assert isinstance(servers, list)
    assert len(servers) > 0


@requires_api
@skip_no_creds
def test_search(api):
    results = api.search_by_name("Брат")
    if isinstance(results, dict) and "data" in results:
        results = results["data"]
    assert isinstance(results, list)


@requires_api
@skip_no_creds
def test_favorites(adapter):
    channels = adapter.get_all_channels()[:5]
    fav_ids = {channels[0]["id"], channels[2]["id"]}
    adapter.apply_favorites(channels, fav_ids)
    assert channels[0]["fav"] == 1
    assert channels[1]["fav"] == 0
    assert channels[2]["fav"] == 1
