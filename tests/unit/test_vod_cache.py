# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for VOD cache functionality.

Migrated from: test_vod_cache.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


@pytest.fixture
def cache_dir(tmp_path, mock_kodi_modules):
    """Set up a temporary cache directory and configure mocks for vod_cache."""
    cache_path = str(tmp_path / "vod_cache")
    os.makedirs(cache_path, exist_ok=True)

    # Patch the xbmcaddon mock so Addon().getAddonInfo('profile') returns tmp dir
    class TmpAddon:
        def getSetting(self, key):
            if key == "vod_cache_ttl_days":
                return "7"
            return ""

        def getAddonInfo(self, key):
            if key == "profile":
                return cache_path
            return ""

    import types

    mod = types.ModuleType("xbmcaddon")
    mod.Addon = lambda *a, **kw: TmpAddon()
    sys.modules["xbmcaddon"] = mod

    # Re-import vod_cache so it picks up the patched mock
    if "vod_cache" in sys.modules:
        del sys.modules["vod_cache"]

    from vod_cache import vod_cache_init

    vod_cache_init()

    yield cache_path


def test_cache_init(cache_dir):
    from vod_cache import vod_cache_get_stats

    stats = vod_cache_get_stats()
    assert stats["total"] == 0


def test_set_and_get(cache_dir):
    from vod_cache import vod_cache_get, vod_cache_set

    movie = {"id": 12345, "name": "Test Movie", "year": 2024, "rating": 8.5}
    assert vod_cache_set(12345, movie)
    cached = vod_cache_get(12345)
    assert cached is not None
    assert cached["name"] == "Test Movie"
    assert cached["rating"] == 8.5


def test_get_nonexistent(cache_dir):
    from vod_cache import vod_cache_get

    assert vod_cache_get(99999) is None


def test_set_multiple_and_get_multiple(cache_dir):
    from vod_cache import vod_cache_get_multiple, vod_cache_set_multiple

    movies = {
        "100": {"id": 100, "name": "Movie 1", "year": 2020},
        "101": {"id": 101, "name": "Movie 2", "year": 2021},
        "102": {"id": 102, "name": "Movie 3", "year": 2022},
    }
    count = vod_cache_set_multiple(movies)
    assert count == 3

    cached = vod_cache_get_multiple([100, 101, 102, 999])
    assert len(cached) == 3


def test_cache_stats(cache_dir):
    from vod_cache import vod_cache_get_stats, vod_cache_set

    for i in range(4):
        vod_cache_set(i, {"id": i, "name": "Movie %d" % i})
    stats = vod_cache_get_stats()
    assert stats["total"] == 4


def test_delete(cache_dir):
    from vod_cache import vod_cache_delete, vod_cache_get, vod_cache_set

    vod_cache_set(100, {"id": 100, "name": "Movie"})
    assert vod_cache_delete(100)
    assert vod_cache_get(100) is None


def test_update_existing(cache_dir):
    from vod_cache import vod_cache_get, vod_cache_set

    vod_cache_set(12345, {"id": 12345, "rating": 8.5})
    vod_cache_set(12345, {"id": 12345, "rating": 9.0})
    cached = vod_cache_get(12345)
    assert cached["rating"] == 9.0


def test_clear_all(cache_dir):
    from vod_cache import vod_cache_clear_all, vod_cache_get_stats, vod_cache_set

    vod_cache_set(1, {"id": 1})
    vod_cache_set(2, {"id": 2})
    assert vod_cache_clear_all()
    stats = vod_cache_get_stats()
    assert stats["total"] == 0


def test_ttl_expiration(cache_dir):
    from vod_cache import vod_cache_get, vod_cache_set

    vod_cache_set(200, {"id": 200, "name": "Old Movie"})
    # max_age_days=0 means expired immediately
    assert vod_cache_get(200, max_age_days=0) is None
    # Still retrievable with longer TTL
    assert vod_cache_get(200, max_age_days=7) is not None


def test_clear_old(cache_dir):
    from vod_cache import vod_cache_clear_old, vod_cache_set

    vod_cache_set(200, {"id": 200})
    count = vod_cache_clear_old(max_age_days=0)
    assert count > 0
