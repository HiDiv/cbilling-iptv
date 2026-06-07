# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Integration tests for VOD search and year filter pagination.

Verifies that search_by_name() and filter_by_year() correctly pass
page/per_page parameters to the API and return different results
on different pages.

Regression test for: https://github.com/HiDiv/cbilling-iptv/issues/1
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


@requires_api
@skip_no_creds
class TestSearchPagination:
    """Tests for search_by_name pagination (issue #1)."""

    def test_search_returns_paginated_response(self, api):
        """search_by_name should return a dict with 'data' and 'meta' keys."""
        result = api.search_by_name("день", page=1, per_page=5)

        assert isinstance(result, dict), "Expected dict response with 'data' key"
        assert "data" in result, "Response must contain 'data' key"
        assert isinstance(result["data"], list), "'data' must be a list"

    def test_search_meta_contains_pagination_info(self, api):
        """search_by_name response meta should contain pagination fields."""
        result = api.search_by_name("день", page=1, per_page=5)

        assert "meta" in result, "Response must contain 'meta' key"
        meta = result["meta"]
        assert "total" in meta, "Meta must contain 'total'"
        assert "last_page" in meta, "Meta must contain 'last_page'"

    def test_search_per_page_limits_results(self, api):
        """search_by_name should respect per_page parameter."""
        result = api.search_by_name("день", page=1, per_page=3)

        data = result.get("data", result if isinstance(result, list) else [])
        assert len(data) <= 3, "per_page=3 should return at most 3 items"

    def test_search_page2_differs_from_page1(self, api):
        """Page 2 results must differ from page 1 results."""
        result_p1 = api.search_by_name("день", page=1, per_page=5)
        result_p2 = api.search_by_name("день", page=2, per_page=5)

        data_p1 = result_p1.get("data", result_p1 if isinstance(result_p1, list) else [])
        data_p2 = result_p2.get("data", result_p2 if isinstance(result_p2, list) else [])

        # Both pages should have results
        assert len(data_p1) > 0, "Page 1 should have results"
        assert len(data_p2) > 0, "Page 2 should have results"

        # Extract IDs to compare
        ids_p1 = {item.get("id") for item in data_p1}
        ids_p2 = {item.get("id") for item in data_p2}

        # Pages must contain different items
        assert ids_p1 != ids_p2, (
            "Page 1 and page 2 must return different results. Got same IDs on both pages: %s" % ids_p1
        )

        # No overlap between pages
        overlap = ids_p1 & ids_p2
        assert len(overlap) == 0, "Pages should not overlap. Found %d common items: %s" % (len(overlap), overlap)


@requires_api
@skip_no_creds
class TestYearFilterPagination:
    """Tests for filter_by_year pagination (issue #1)."""

    def test_year_filter_returns_paginated_response(self, api):
        """filter_by_year should return a dict with 'data' and 'meta' keys."""
        result = api.filter_by_year("2023", page=1, per_page=5)

        assert isinstance(result, dict), "Expected dict response with 'data' key"
        assert "data" in result, "Response must contain 'data' key"

    def test_year_filter_meta_contains_pagination_info(self, api):
        """filter_by_year response meta should contain pagination fields."""
        result = api.filter_by_year("2023", page=1, per_page=5)

        assert "meta" in result, "Response must contain 'meta' key"
        meta = result["meta"]
        assert "total" in meta, "Meta must contain 'total'"
        assert "last_page" in meta, "Meta must contain 'last_page'"

    def test_year_filter_page2_differs_from_page1(self, api):
        """Page 2 results must differ from page 1 for year filter."""
        result_p1 = api.filter_by_year("2023", page=1, per_page=5)
        result_p2 = api.filter_by_year("2023", page=2, per_page=5)

        data_p1 = result_p1.get("data", result_p1 if isinstance(result_p1, list) else [])
        data_p2 = result_p2.get("data", result_p2 if isinstance(result_p2, list) else [])

        assert len(data_p1) > 0, "Page 1 should have results"
        assert len(data_p2) > 0, "Page 2 should have results"

        ids_p1 = {item.get("id") for item in data_p1}
        ids_p2 = {item.get("id") for item in data_p2}

        assert ids_p1 != ids_p2, (
            "Page 1 and page 2 must return different results. Got same IDs on both pages: %s" % ids_p1
        )
