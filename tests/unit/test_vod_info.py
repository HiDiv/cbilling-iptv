# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for VOD info display functionality.

Migrated from: test_vod_info.py
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
def test_movie_info_retrieval():
    from api_client import CbillingAPI

    api = CbillingAPI(
        base_url=os.environ["CBILLING_API_URL"],
        public_key=os.environ["CBILLING_PUBLIC_KEY"],
        timeout=30,
    )
    cats_response = api.get_vod_categories()
    cats = cats_response["data"] if isinstance(cats_response, dict) and "data" in cats_response else cats_response
    assert len(cats) > 0

    cat_id = cats[0].get("id")
    movies = api.get_vod_category_content(cat_id)
    if isinstance(movies, dict) and "data" in movies:
        movies = movies["data"]
    assert len(movies) > 0

    video_info = api.get_video(movies[0]["id"])
    assert video_info is not None
    video_data = video_info.get("data", video_info) if isinstance(video_info, dict) else video_info
    assert "name" in video_data
