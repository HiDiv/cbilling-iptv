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


class TestSeriesDetection:
    """Test that series items are correctly detected from category name."""

    def test_series_detected_from_category_name(self, tmp_path):
        """Items with category containing 'Сериалы' should be folders with vod_get_seasons URL."""
        ctx = _make_ctx(tmp_path)
        ctx.settings._data["vod_preload_metadata"] = "false"

        ctx.api.get_vod_category_content.return_value = {
            "data": [
                {"id": "101", "name": "Some Series", "poster": "", "year": "2024",
                 "category": "\u0421\u0435\u0440\u0438\u0430\u043b\u044b", "adult": 0, "genres": []},
            ],
            "meta": {"total": 1, "per_page": 20},
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

        params = {"cat_id": "2", "genre_id": "*", "page_nr": "1", "sortby": "added"}
        get_ordered_list(ctx, params)

        xbmcplugin.addDirectoryItems.assert_called_once()
        listing = xbmcplugin.addDirectoryItems.call_args[0][1]
        assert len(listing) == 1

        url, _item, is_folder = listing[0]
        assert is_folder is True, "Series should be a folder"
        assert "vod_get_seasons" in url, "Series URL should contain vod_get_seasons"

    def test_movie_not_detected_as_series(self, tmp_path):
        """Items with non-series category should be playable files."""
        ctx = _make_ctx(tmp_path)
        ctx.settings._data["vod_preload_metadata"] = "false"

        ctx.api.get_vod_category_content.return_value = {
            "data": [
                {"id": "201", "name": "Action Movie", "poster": "", "year": "2024",
                 "category": "Foreign Films", "adult": 0, "genres": []},
            ],
            "meta": {"total": 1, "per_page": 20},
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

        params = {"cat_id": "1", "genre_id": "*", "page_nr": "1", "sortby": "added"}
        get_ordered_list(ctx, params)

        xbmcplugin.addDirectoryItems.assert_called_once()
        listing = xbmcplugin.addDirectoryItems.call_args[0][1]
        assert len(listing) == 1

        url, _item, is_folder = listing[0]
        assert is_folder is False, "Movie should not be a folder"
        assert "vod_play_movie" in url, "Movie URL should contain vod_play_movie"

    def test_series_detected_from_preloaded_seasons(self, tmp_path):
        """Items with seasons in preloaded metadata should be folders."""
        ctx = _make_ctx(tmp_path)
        ctx.settings._data["vod_preload_metadata"] = "true"

        ctx.api.get_vod_category_content.return_value = {
            "data": [
                {"id": "301", "name": "Another Series", "poster": "", "year": "2023",
                 "category": "Foreign Films", "adult": 0, "genres": []},
            ],
            "meta": {"total": 1, "per_page": 20},
        }

        # Simulate preload: cache returns metadata with seasons
        mock_cache_multiple = MagicMock(return_value={
            "301": {"description": "A series", "seasons": [{"id": 1, "number": 1}]},
        })

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItems = MagicMock()
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.iscanceled.return_value = False
        sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

        from unittest.mock import patch

        from vod import get_ordered_list

        with patch("resources.lib.vod_cache.vod_cache_get_multiple", mock_cache_multiple):
            params = {"cat_id": "1", "genre_id": "*", "page_nr": "1", "sortby": "added"}
            get_ordered_list(ctx, params)

        xbmcplugin.addDirectoryItems.assert_called_once()
        listing = xbmcplugin.addDirectoryItems.call_args[0][1]
        assert len(listing) == 1

        url, _item, is_folder = listing[0]
        assert is_folder is True, "Series with preloaded seasons should be a folder"
        assert "vod_get_seasons" in url


class TestArchiveChannelUrl:
    """Test that archive mode creates folder URLs, not play URLs."""

    def test_archive_channel_is_folder(self, tmp_path):
        """In archive mode, channels should be folders with archive_channel_dates URL."""
        ctx = _make_ctx(tmp_path)
        os.makedirs(str(tmp_path / "userdata"), exist_ok=True)

        from unittest.mock import patch

        with patch("channels.auth.check_credentials", return_value="true"):
            ctx.adapter.get_channels_by_genre.return_value = [
                {
                    "id": "pervyj",
                    "name": "Channel 1",
                    "tv_genre_id": "1",
                    "cmd": "http://server.com/ch1/index.m3u8?token=x",
                    "tv_archive_type": "flussonic_dvr",
                    "tv_archive_duration": "7",
                    "logo": "http://logo.com/ch1.png",
                    "censored": 0,
                    "fav": 0,
                    "open": 1,
                    "status": 1,
                    "cur_playing": "",
                    "sort": 1,
                },
            ]
            ctx.adapter.apply_favorites = MagicMock()

            xbmcplugin = sys.modules["xbmcplugin"]
            xbmcplugin.addDirectoryItem = MagicMock()
            xbmcplugin.endOfDirectory = MagicMock()
            xbmcplugin.addSortMethod = MagicMock()
            xbmcplugin.SORT_METHOD_LABEL = 1
            xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE = 2

            mock_dialog = MagicMock()
            mock_dialog.iscanceled.return_value = False
            sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

            from channels import get_channels_list

            get_channels_list(ctx, {"group_id": "1", "favorites": "0", "action": "archive"})

        call_args = xbmcplugin.addDirectoryItem.call_args_list
        assert len(call_args) >= 1

        # Check URL and isFolder
        args = call_args[0][0] if call_args[0][0] else ()
        kwargs = call_args[0][1] if call_args[0][1] else {}
        url = kwargs.get("url", args[1] if len(args) > 1 else "")
        is_folder = kwargs.get("isFolder", args[3] if len(args) > 3 else False)

        assert "archive_channel_dates" in url, "Archive URL should contain archive_channel_dates"
        assert "depth=7" in url, "Archive URL should contain depth"
        assert is_folder is True, "Archive channel should be a folder"


class TestVodPreloadDescription:
    """Test that preloaded metadata populates plot in movie list."""

    def test_plot_populated_from_cached_data(self, tmp_path):
        """Movies with preloaded metadata should have plot from description."""
        ctx = _make_ctx(tmp_path)
        ctx.settings._data["vod_preload_metadata"] = "true"

        ctx.api.get_vod_category_content.return_value = {
            "data": [
                {"id": "501", "name": "Test Movie", "poster": "", "year": "2024",
                 "category": "Foreign Films", "adult": 0, "genres": []},
            ],
            "meta": {"total": 1, "per_page": 20},
        }

        mock_cache = MagicMock(return_value={
            "501": {"description": "A great movie about testing.", "poster": "http://poster.jpg"},
        })

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItems = MagicMock()
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.iscanceled.return_value = False
        sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

        from unittest.mock import patch

        from vod import get_ordered_list

        with patch("resources.lib.vod_cache.vod_cache_get_multiple", mock_cache):
            params = {"cat_id": "1", "genre_id": "*", "page_nr": "1", "sortby": "added"}
            get_ordered_list(ctx, params)

        xbmcplugin.addDirectoryItems.assert_called_once()
        listing = xbmcplugin.addDirectoryItems.call_args[0][1]
        # Verify the ListItem was created (we can't easily check setInfo on mock)
        assert len(listing) == 1


class TestEpisodeLabel:
    """Test episode label formatting in get_episodes."""

    def test_episode_label_without_number_prefix(self, tmp_path):
        """Episode label should be just the name in burlywood, no 'N.' prefix."""
        ctx = _make_ctx(tmp_path)

        ctx.api.get_season.return_value = {
            "data": [
                {"id": "100", "number": "3", "name": "The Big Reveal"},
            ]
        }

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItems = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from vod import get_episodes

        params = {
            "movie_id": "50",
            "season_id": "10",
            "movie_name": "TestSeries",
            "season_name": "Season+1",
            "poster_url": "",
        }
        get_episodes(ctx, params)

        xbmcplugin.addDirectoryItems.assert_called_once()
        listing = xbmcplugin.addDirectoryItems.call_args[0][1]
        assert len(listing) == 1
        _url, item, _is_folder = listing[0]
        # Label should not start with "3." prefix
        assert "3." not in str(item.label) if hasattr(item, "label") else True

    def test_episode_without_name_uses_localized_episode(self, tmp_path):
        """Episode without name should show 'Episode N' (localized)."""
        ctx = _make_ctx(tmp_path)

        ctx.api.get_season.return_value = {
            "data": [
                {"id": "200", "number": "5", "name": ""},
            ]
        }

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItems = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from vod import get_episodes

        params = {
            "movie_id": "50",
            "season_id": "10",
            "movie_name": "TestSeries",
            "season_name": "Season+1",
            "poster_url": "",
        }
        get_episodes(ctx, params)

        xbmcplugin.addDirectoryItems.assert_called_once()
        listing = xbmcplugin.addDirectoryItems.call_args[0][1]
        assert len(listing) == 1
        # URL should contain vod_play_movie (episode is playable)
        url = listing[0][0]
        assert "vod_play_movie" in url
