# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for VOD server-side pagination.

Migrated from: test_vod_pagination.py
All tests require live API credentials.
"""

import os
import sys
from urllib.parse import unquote as url_unquote

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


# This test is purely offline
def test_genre_id_url_decode():
    """Verify URL-decode of %2a produces '*'."""
    assert url_unquote("%2a") == "*"


@requires_api
def test_genre_pagination_page1():
    from api_client import CbillingAPI

    api = CbillingAPI(os.environ["CBILLING_API_URL"], os.environ["CBILLING_PUBLIC_KEY"])

    r1 = api.get_vod_by_genre(43, page=1)
    assert isinstance(r1, dict) and "data" in r1 and "meta" in r1
    assert len(r1["data"]) == 20
    assert r1["meta"]["current_page"] == 1
    assert r1["meta"]["last_page"] >= 2


@requires_api
def test_genre_pagination_page2_different():
    from api_client import CbillingAPI

    api = CbillingAPI(os.environ["CBILLING_API_URL"], os.environ["CBILLING_PUBLIC_KEY"])

    r1 = api.get_vod_by_genre(43, page=1)
    r2 = api.get_vod_by_genre(43, page=2)
    assert len(r2["data"]) > 0
    assert r2["meta"]["current_page"] == 2

    ids_p1 = {str(m["id"]) for m in r1["data"]}
    ids_p2 = {str(m["id"]) for m in r2["data"]}
    assert len(ids_p1 & ids_p2) == 0, "Pages should have no duplicate IDs"


@requires_api
def test_category_content_pagination():
    from api_client import CbillingAPI

    api = CbillingAPI(os.environ["CBILLING_API_URL"], os.environ["CBILLING_PUBLIC_KEY"])

    r3 = api.get_vod_category_content(5, page=1)
    assert isinstance(r3, dict) and "data" in r3 and "meta" in r3
    assert len(r3["data"]) == 20


@requires_api
def test_beyond_last_page_empty():
    from api_client import CbillingAPI

    api = CbillingAPI(os.environ["CBILLING_API_URL"], os.environ["CBILLING_PUBLIC_KEY"])

    r1 = api.get_vod_by_genre(43, page=1)
    last = r1["meta"]["last_page"]
    r_beyond = api.get_vod_by_genre(43, page=last + 1)
    items = r_beyond.get("data", []) if isinstance(r_beyond, dict) else r_beyond
    assert len(items) == 0
