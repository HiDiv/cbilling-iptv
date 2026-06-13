# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for channels.py — main menu, channel groups, and init flow."""

import os
import sys
from unittest.mock import MagicMock, patch

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

    # Create required dirs for fanart paths
    fanart_dir = tmp_path / "fanart"
    fanart_dir.mkdir(exist_ok=True)
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir(exist_ok=True)

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


class TestMainMenu:
    """Test main_menu adds exactly 4 items and calls endOfDirectory."""

    def test_main_menu_adds_4_items(self, tmp_path):
        """main_menu should add exactly 4 directory items."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from channels import main_menu

        main_menu(ctx, {})

        assert xbmcplugin.addDirectoryItem.call_count == 4

    def test_main_menu_calls_end_of_directory(self, tmp_path):
        """main_menu should call endOfDirectory at the end."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from channels import main_menu

        main_menu(ctx, {})

        xbmcplugin.endOfDirectory.assert_called_once()


class TestChannelGroups:
    """Test channel_groups calls adapter.get_genres()."""

    def test_channel_groups_calls_adapter_get_genres(self, tmp_path):
        """channel_groups should call ctx.adapter.get_genres() as fallback."""
        ctx = _make_ctx(tmp_path)
        ctx.adapter.get_genres.return_value = [
            {"id": "1", "title": "News"},
            {"id": "2", "title": "Sport"},
        ]

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()
        xbmcplugin.addSortMethod = MagicMock()
        xbmcplugin.SORT_METHOD_LABEL = 1
        xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE = 2

        from channels import channel_groups

        channel_groups(ctx, {"archive": "false"})

        ctx.adapter.get_genres.assert_called_once()


class TestInitAndStart:
    """Test init_and_start calls auth.check_credentials."""

    def test_init_and_start_calls_check_credentials(self, tmp_path):
        """init_and_start should verify credentials via auth.check_credentials."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        with patch("channels.auth.check_credentials", return_value="true") as mock_auth:
            from channels import init_and_start

            init_and_start(ctx, cron_job_request=False)

            mock_auth.assert_called_once_with(ctx, False)


class TestGetChannelsListLogos:
    """Test that get_channels_list sets channel logos in artwork."""

    def test_channel_logo_set_in_thumb(self, tmp_path):
        """Each channel's logo URL must be set as 'thumb' in setArt."""
        ctx = _make_ctx(tmp_path)

        # Create userdata dir for favorites
        os.makedirs(str(tmp_path / "userdata"), exist_ok=True)

        # Mock auth to pass
        with patch("channels.auth.check_credentials", return_value="true"):
            # Mock adapter to return channels with logos
            ctx.adapter.get_channels_by_genre.return_value = [
                {
                    "id": "pervyj",
                    "name": "Первый канал",
                    "tv_genre_id": "1",
                    "cmd": "http://stream.example.com/pervyj/index.m3u8",
                    "tv_archive_type": "",
                    "logo": "http://static.example.com/pervyj.png",
                    "tv_archive_duration": "0",
                    "censored": 0,
                    "fav": 0,
                    "open": 1,
                    "status": 1,
                    "cur_playing": "",
                    "sort": 1,
                },
                {
                    "id": "rossija1",
                    "name": "Россия 1",
                    "tv_genre_id": "1",
                    "cmd": "http://stream.example.com/rossija1/index.m3u8",
                    "tv_archive_type": "",
                    "logo": "http://static.example.com/rossija1.png",
                    "tv_archive_duration": "0",
                    "censored": 0,
                    "fav": 0,
                    "open": 1,
                    "status": 1,
                    "cur_playing": "",
                    "sort": 2,
                },
            ]
            ctx.adapter.apply_favorites = MagicMock()

            xbmcplugin = sys.modules["xbmcplugin"]
            xbmcplugin.addDirectoryItem = MagicMock()
            xbmcplugin.endOfDirectory = MagicMock()
            xbmcplugin.setContent = MagicMock()

            # Track setArt calls
            art_calls = []
            original_listitem = sys.modules["xbmcgui"].ListItem

            class TrackingListItem:
                def __init__(self, label="", label2="", path="", offscreen=False):
                    self.label = label

                def setArt(self, art):  # noqa: N802
                    art_calls.append(art)

                def setInfo(self, type, info=None, **kwargs):  # noqa: N802
                    pass

                def setLabel2(self, label2):  # noqa: N802
                    pass

                def setProperty(self, key, value):  # noqa: N802
                    pass

                def addContextMenuItems(self, items, **kwargs):  # noqa: N802
                    pass

            sys.modules["xbmcgui"].ListItem = TrackingListItem
            # Mock DialogProgress
            mock_dialog = MagicMock()
            mock_dialog.iscanceled.return_value = False
            sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

            from channels import get_channels_list

            get_channels_list(ctx, {"group_id": "1", "favorites": "0", "action": "live"})

            sys.modules["xbmcgui"].ListItem = original_listitem

        # Verify logos were set as 'thumb' in setArt
        assert len(art_calls) >= 2, "Expected at least 2 setArt calls, got %d" % len(art_calls)
        assert art_calls[0]["thumb"] == "http://static.example.com/pervyj.png"
        assert art_calls[1]["thumb"] == "http://static.example.com/rossija1.png"

    def test_channel_without_logo_uses_fallback(self, tmp_path):
        """Channel with empty logo should use fallback thumb_play.png."""
        ctx = _make_ctx(tmp_path)
        os.makedirs(str(tmp_path / "userdata"), exist_ok=True)

        with patch("channels.auth.check_credentials", return_value="true"):
            ctx.adapter.get_channels_by_genre.return_value = [
                {
                    "id": "no_logo_ch",
                    "name": "No Logo",
                    "tv_genre_id": "1",
                    "cmd": "http://stream.example.com/nologoch/index.m3u8",
                    "tv_archive_type": "",
                    "logo": "",
                    "tv_archive_duration": "0",
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
            xbmcplugin.setContent = MagicMock()

            art_calls = []
            original_listitem = sys.modules["xbmcgui"].ListItem

            class TrackingListItem:
                def __init__(self, label="", label2="", path="", offscreen=False):
                    self.label = label

                def setArt(self, art):  # noqa: N802
                    art_calls.append(art)

                def setInfo(self, type, info=None, **kwargs):  # noqa: N802
                    pass

                def setLabel2(self, label2):  # noqa: N802
                    pass

                def setProperty(self, key, value):  # noqa: N802
                    pass

                def addContextMenuItems(self, items, **kwargs):  # noqa: N802
                    pass

            sys.modules["xbmcgui"].ListItem = TrackingListItem
            mock_dialog = MagicMock()
            mock_dialog.iscanceled.return_value = False
            sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

            from channels import get_channels_list

            get_channels_list(ctx, {"group_id": "1", "favorites": "0", "action": "live"})

            sys.modules["xbmcgui"].ListItem = original_listitem

        # Without logo, thumb should be the fallback thumb_play.png path
        assert len(art_calls) >= 1
        assert "thumb_play.png" in art_calls[0]["thumb"]


class TestBuildEpgPlot:
    """Test build_epg_plot pure function for EPG plot formatting."""

    def test_empty_epg_returns_empty(self):
        """Empty short_epg list returns empty string."""
        from channels import build_epg_plot

        result = build_epg_plot([], 1000000, "Now:", "Next:", "%d min", "in %d min")
        assert result == ""

    def test_current_program_shown(self):
        """Current program name appears in plot."""
        from channels import build_epg_plot

        epg = [{"name": "News", "t_time": "12:00", "t_time_to": "12:30",
                "start_timestamp": "1000000", "stop_timestamp": "1001800", "descr": ""}]
        result = build_epg_plot(epg, 1000600, "Now:", "Next:", "%d min", "in %d min")
        assert "News" in result
        assert "Now:" in result

    def test_elapsed_time_shown(self):
        """Elapsed minutes shown when program started in past."""
        from channels import build_epg_plot

        # Program started 600 seconds (10 min) ago
        start_ts = 1000000
        now_ts = 1000600
        epg = [{"name": "Show", "t_time": "10:00", "t_time_to": "11:00",
                "start_timestamp": str(start_ts), "stop_timestamp": str(start_ts + 3600), "descr": ""}]
        result = build_epg_plot(epg, now_ts, "Now:", "Next:", "%d min", "in %d min")
        assert "10 min" in result

    def test_next_program_shown(self):
        """Next program name and time appear in plot."""
        from channels import build_epg_plot

        now_ts = 1000600
        epg = [
            {"name": "Current", "t_time": "10:00", "t_time_to": "11:00",
             "start_timestamp": "1000000", "stop_timestamp": "1003600", "descr": ""},
            {"name": "Next Show", "t_time": "11:00", "t_time_to": "12:00",
             "start_timestamp": "1003600", "stop_timestamp": "1007200", "descr": ""},
        ]
        result = build_epg_plot(epg, now_ts, "Now:", "Next:", "%d min", "in %d min")
        assert "Next Show" in result
        assert "Next:" in result

    def test_starts_in_shown_for_next(self):
        """'in X min' shown for next program."""
        from channels import build_epg_plot

        now_ts = 1000000
        next_start_ts = 1000000 + 900  # 15 min from now
        epg = [
            {"name": "Current", "t_time": "10:00", "t_time_to": "10:15",
             "start_timestamp": str(now_ts - 60), "stop_timestamp": str(now_ts + 840), "descr": ""},
            {"name": "Next", "t_time": "10:15", "t_time_to": "11:00",
             "start_timestamp": str(next_start_ts), "stop_timestamp": str(next_start_ts + 2700), "descr": ""},
        ]
        result = build_epg_plot(epg, now_ts, "Now:", "Next:", "%d min", "in %d min")
        assert "in 15 min" in result

    def test_description_shown(self):
        """Program description appears in plot."""
        from channels import build_epg_plot

        epg = [{"name": "Movie", "t_time": "20:00", "t_time_to": "22:00",
                "start_timestamp": "1000000", "stop_timestamp": "1007200",
                "descr": "A great movie about something."}]
        result = build_epg_plot(epg, 1000600, "Now:", "Next:", "%d min", "in %d min")
        assert "A great movie about something." in result

    def test_no_name_returns_empty(self):
        """EPG entry without name returns empty plot."""
        from channels import build_epg_plot

        epg = [{"name": "", "t_time": "12:00", "t_time_to": "12:30",
                "start_timestamp": "1000000", "stop_timestamp": "1001800", "descr": ""}]
        result = build_epg_plot(epg, 1000600, "Now:", "Next:", "%d min", "in %d min")
        assert result == ""

    def test_no_duplicate_colons(self):
        """Localized labels already contain colon — no double colon in output."""
        from channels import build_epg_plot

        # Russian-style labels already have colon
        epg = [{"name": "News", "t_time": "12:00", "t_time_to": "12:30",
                "start_timestamp": "1000000", "stop_timestamp": "1001800", "descr": ""}]
        result = build_epg_plot(epg, 1000600, "Сейчас:", "Далее:", "%d мин. идёт", "через %d мин.")
        # Should NOT have "::" (double colon)
        assert "::" not in result
        assert "Сейчас:" in result


class TestGetChannelsListPlayUrl:
    """Test that channel play URLs contain play_cmd with stream URL."""

    def test_play_url_contains_play_cmd(self, tmp_path):
        """Channel URL must contain play_cmd with the stream address."""
        ctx = _make_ctx(tmp_path)
        os.makedirs(str(tmp_path / "userdata"), exist_ok=True)

        with patch("channels.auth.check_credentials", return_value="true"):
            ctx.adapter.get_channels_by_genre.return_value = [
                {
                    "id": "pervyj",
                    "name": "Первый канал",
                    "tv_genre_id": "1",
                    "cmd": "http://server.com/pervyj/index.m3u8?token=abc",
                    "tv_archive_type": "flussonic_dvr",
                    "logo": "http://logo.com/pervyj.png",
                    "tv_archive_duration": "7",
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

            get_channels_list(ctx, {"group_id": "1", "favorites": "0", "action": "live"})

        # Check the URL passed to addDirectoryItem
        call_args = xbmcplugin.addDirectoryItem.call_args_list
        assert len(call_args) >= 1
        url = call_args[0][1]["url"] if "url" in (call_args[0][1] or {}) else call_args[0][0][1]
        assert "play_cmd=" in url, "URL must contain play_cmd parameter"
        assert "server.com" in url, "play_cmd must contain stream server URL"
        assert "name=" in url, "URL must contain encoded channel name"


class TestGetChannelsListContextMenu:
    """Test that channel items have context menu with expected items."""

    def test_context_menu_has_epg_and_favorites(self, tmp_path):
        """Context menu must include EPG show and favorites toggle."""
        ctx = _make_ctx(tmp_path)
        os.makedirs(str(tmp_path / "userdata"), exist_ok=True)

        with patch("channels.auth.check_credentials", return_value="true"):
            ctx.adapter.get_channels_by_genre.return_value = [
                {
                    "id": "ntv",
                    "name": "NTV",
                    "tv_genre_id": "1",
                    "cmd": "http://server.com/ntv/index.m3u8?token=x",
                    "tv_archive_type": "flussonic_dvr",
                    "logo": "",
                    "tv_archive_duration": "7",
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

            # Track addContextMenuItems calls
            menu_calls = []
            original_listitem = sys.modules["xbmcgui"].ListItem

            class TrackingListItem:
                def __init__(self, *args, **kwargs):
                    pass

                def setArt(self, art):  # noqa: N802
                    pass

                def setInfo(self, *args, **kwargs):  # noqa: N802
                    pass

                def setLabel2(self, *args):  # noqa: N802
                    pass

                def setProperty(self, *args):  # noqa: N802
                    pass

                def addContextMenuItems(self, items, **kwargs):  # noqa: N802
                    menu_calls.append({"items": items, "kwargs": kwargs})

            sys.modules["xbmcgui"].ListItem = TrackingListItem
            mock_dialog = MagicMock()
            mock_dialog.iscanceled.return_value = False
            sys.modules["xbmcgui"].DialogProgress = MagicMock(return_value=mock_dialog)

            from channels import get_channels_list

            get_channels_list(ctx, {"group_id": "1", "favorites": "0", "action": "live"})

            sys.modules["xbmcgui"].ListItem = original_listitem

        assert len(menu_calls) >= 1, "At least one item should have context menu"
        menu_items = menu_calls[0]["items"]
        menu_commands = [item[1] for item in menu_items]

        # Verify replaceItems=True
        assert menu_calls[0]["kwargs"].get("replaceItems") is True

        # Verify EPG show present
        assert any("epg_show" in cmd for cmd in menu_commands), (
            "Context menu must have epg_show command"
        )

        # Verify favorites present
        assert any("itv_fav_add_remove" in cmd for cmd in menu_commands), (
            "Context menu must have favorites command"
        )

        # Verify stream servers present
        assert any("get_stream_servers" in cmd for cmd in menu_commands), (
            "Context menu must have stream servers command"
        )

        # Verify Container.Refresh present
        assert any("Container.Refresh" in cmd for cmd in menu_commands), (
            "Context menu must have Refresh command"
        )


class TestTimezoneSettingKey:
    """Test that default.py reads timezone from correct setting key."""

    def test_stb_timezone_key_used(self):
        """default.py must read 'stb_timezone', not 'timezone'."""
        with open("default.py") as f:
            content = f.read()
        assert 'getSetting("stb_timezone")' in content, (
            "default.py must use getSetting('stb_timezone')"
        )
        assert 'getSetting("timezone")' not in content, (
            "default.py must NOT use getSetting('timezone') — wrong key"
        )
