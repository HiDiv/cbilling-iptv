# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for vod.py — VOD start menu and paginated movie list."""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


from context import AddonContext


class FakeSettings:
    """Fake settings accessor for testing."""

    def __init__(self):
        self._data = {}

    def getSetting(self, key):  # noqa: N802
        return self._data.get(key, "")

    def setSetting(self, key, value):  # noqa: N802
        self._data[key] = value

    def getLocalizedString(self, string_id):  # noqa: N802
        return "String_%s" % string_id


def _make_ctx(tmp_path):
    """Create an AddonContext with mocked dependencies."""
    api = MagicMock()
    adapter = MagicMock()
    settings = FakeSettings()

    # Create required resource dirs
    media_dir = tmp_path / "resources" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    fanart_dir = tmp_path / "resources" / "fanart"
    fanart_dir.mkdir(parents=True, exist_ok=True)

    ctx = AddonContext(
        api_client=api,
        adapter=adapter,
        addon_handle=1,
        settings=settings,
        addon_dir=str(tmp_path),
        user_data_dir=str(tmp_path / "userdata"),
        temp_dir=str(tmp_path / "temp"),
        plugin_url="plugin://plugin.video.cbilling.iptv/",
    )
    return ctx


class TestVodStart:
    """Test VOD start menu adds 3 items (Categories, Search, History)."""

    def test_start_adds_3_items(self, tmp_path):
        """start should add exactly 3 directory items."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from vod import start

        start(ctx, {})

        assert xbmcplugin.addDirectoryItem.call_count == 3

    def test_start_calls_end_of_directory(self, tmp_path):
        """start should call endOfDirectory."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from vod import start

        start(ctx, {})

        xbmcplugin.endOfDirectory.assert_called_once()


class TestGetOrderedList:
    """Test get_ordered_list handles empty API response gracefully."""

    def test_get_ordered_list_empty_response(self, tmp_path):
        """get_ordered_list should handle empty API response without error."""
        ctx = _make_ctx(tmp_path)

        # API returns empty data
        ctx.api.get_vod_category_content.return_value = {"data": [], "meta": {}}

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItems = MagicMock()
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        # Mock DialogProgress
        mock_dialog = MagicMock()
        mock_dialog.iscanceled.return_value = False
        sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

        from vod import get_ordered_list

        params = {
            "cat_id": "1",
            "genre_id": "*",
            "page_nr": "1",
            "sortby": "added",
        }

        # Should not raise
        get_ordered_list(ctx, params)

        # endOfDirectory should be called (graceful handling)
        xbmcplugin.endOfDirectory.assert_called_once()
        # No items should be added
        xbmcplugin.addDirectoryItems.assert_not_called()

    def test_get_ordered_list_with_items(self, tmp_path):
        """get_ordered_list should add items when API returns data."""
        ctx = _make_ctx(tmp_path)
        ctx.settings._data["vod_preload_metadata"] = "false"

        # API returns movie data
        ctx.api.get_vod_category_content.return_value = {
            "data": [
                {"id": "101", "name": "Movie One", "poster": "", "year": "2023"},
                {"id": "102", "name": "Movie Two", "poster": "", "year": "2024"},
            ],
            "meta": {"total": 2, "per_page": 20},
        }

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItems = MagicMock()
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.iscanceled.return_value = False
        sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

        from vod import get_ordered_list

        params = {
            "cat_id": "1",
            "genre_id": "*",
            "page_nr": "1",
            "sortby": "added",
        }

        get_ordered_list(ctx, params)

        # Should have added items via addDirectoryItems
        xbmcplugin.addDirectoryItems.assert_called_once()
        listing = xbmcplugin.addDirectoryItems.call_args[0][1]
        assert len(listing) == 2
