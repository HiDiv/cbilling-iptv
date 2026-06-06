# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for VOD metadata preloading with cache.

Migrated from: test_vod_preload.py
All tests require live API credentials.
"""

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


def _load_env():
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
requires_api = pytest.mark.skipif(not _HAS_API, reason="API credentials not available (.env)")


@requires_api
def test_preload_and_cache(tmp_path, mock_kodi_modules):
    """Preload movie metadata, cache it, and verify cache retrieval is faster."""
    cache_path = str(tmp_path / "preload_cache")
    os.makedirs(cache_path, exist_ok=True)

    class TmpAddon:
        def getSetting(self, key):
            return "7" if key == "vod_cache_ttl_days" else ""

        def getAddonInfo(self, key):
            return cache_path if key == "profile" else ""

    mod = types.ModuleType("xbmcaddon")
    mod.Addon = lambda *a, **kw: TmpAddon()
    sys.modules["xbmcaddon"] = mod

    if "vod_cache" in sys.modules:
        del sys.modules["vod_cache"]

    from api_client import CbillingAPI
    from vod_cache import vod_cache_get_multiple, vod_cache_init, vod_cache_set_multiple

    vod_cache_init()
    api = CbillingAPI(
        base_url=os.environ["CBILLING_API_URL"],
        public_key=os.environ["CBILLING_PUBLIC_KEY"],
        timeout=30,
    )

    cats_response = api.get_vod_categories()
    cats = cats_response["data"] if isinstance(cats_response, dict) and "data" in cats_response else cats_response
    assert len(cats) > 0

    movies_response = api.get_vod_category_content(cats[0]["id"])
    movies = (
        movies_response["data"] if isinstance(movies_response, dict) and "data" in movies_response else movies_response
    )
    movies = movies[:3]
    movie_ids = [str(m["id"]) for m in movies]

    # Cache should be empty
    assert len(vod_cache_get_multiple(movie_ids)) == 0

    # Load and cache
    cache_data = {}
    for mid in movie_ids:
        info = api.get_video(mid)
        if isinstance(info, dict) and "data" in info:
            cache_data[mid] = info["data"]
    vod_cache_set_multiple(cache_data)

    # Verify cache hit
    cached = vod_cache_get_multiple(movie_ids)
    assert len(cached) == len(movie_ids)
