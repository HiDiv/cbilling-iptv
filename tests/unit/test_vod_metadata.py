# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for VOD metadata from API.

Migrated from: test_vod_metadata.py
All tests require live API credentials.
"""

import os
import sys

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
def test_vod_category_content_has_metadata():
    from api_client import CbillingAPI

    api = CbillingAPI(os.environ["CBILLING_API_URL"], os.environ["CBILLING_PUBLIC_KEY"])
    categories = api.get_vod_categories()
    cat_list = categories["data"] if isinstance(categories, dict) and "data" in categories else categories
    assert len(cat_list) > 0

    content = api.get_vod_category_content(cat_list[0]["id"])
    items = content["data"] if isinstance(content, dict) and "data" in content else content
    assert len(items) > 0

    item = items[0]
    # At least name should be present
    assert "name" in item
    # Check that a reasonable number of metadata fields are present
    critical_fields = [
        "name",
        "description",
        "descr",
        "poster",
        "year",
        "o_name",
        "original_name",
        "genres_str",
        "genre",
        "country",
        "rating_imdb",
        "rating",
        "actors",
        "director",
        "time",
        "duration",
    ]
    present = [f for f in critical_fields if item.get(f)]
    assert len(present) >= 5, "Expected at least 5 metadata fields, got %d: %s" % (len(present), present)
