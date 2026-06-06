# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for VOD series identification.

Migrated from: test_vod_series.py
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
def test_vod_categories_exist():
    from api_client import CbillingAPI

    api = CbillingAPI(
        base_url=os.environ["CBILLING_API_URL"],
        public_key=os.environ["CBILLING_PUBLIC_KEY"],
    )
    categories = api.get_vod_categories()
    if isinstance(categories, dict) and "data" in categories:
        categories = categories["data"]
    assert isinstance(categories, list)
    assert len(categories) > 0


@requires_api
def test_vod_category_content():
    from api_client import CbillingAPI

    api = CbillingAPI(
        base_url=os.environ["CBILLING_API_URL"],
        public_key=os.environ["CBILLING_PUBLIC_KEY"],
    )
    categories = api.get_vod_categories()
    if isinstance(categories, dict) and "data" in categories:
        categories = categories["data"]

    cat_id = categories[0]["id"]
    content = api.get_vod_category_content(cat_id)
    if isinstance(content, dict) and "data" in content:
        content = content["data"]
    assert isinstance(content, list)
    assert len(content) > 0
    assert "name" in content[0]
