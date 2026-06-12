# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for archive.py — channel_dates listing and play resolution."""

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


class TestChannelDates:
    """Test channel_dates lists dates as directory items."""

    def test_channel_dates_adds_directory_items(self, tmp_path):
        """channel_dates should add directory items for each archive day."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from archive import channel_dates

        params = {
            "channel_id": "ch123",
            "depth": "5",
            "name": "",
            "play_cmd": "http://stream.example.com/live/ch123.m3u8",
            "logo_png": "",
        }

        channel_dates(ctx, params)

        # Should add 5 items (one per day in the archive depth)
        assert xbmcplugin.addDirectoryItem.call_count == 5

    def test_channel_dates_calls_end_of_directory(self, tmp_path):
        """channel_dates should call endOfDirectory after listing."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        from archive import channel_dates

        params = {
            "channel_id": "ch123",
            "depth": "3",
            "name": "",
            "play_cmd": "http://stream.example.com/live/ch123.m3u8",
            "logo_png": "",
        }

        channel_dates(ctx, params)

        xbmcplugin.endOfDirectory.assert_called_once()


class TestArchivePlay:
    """Test archive play resolves URL via setResolvedUrl."""

    def test_play_calls_set_resolved_url(self, tmp_path):
        """play should call setResolvedUrl with the archive stream URL."""
        ctx = _make_ctx(tmp_path)

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.setResolvedUrl = MagicMock()

        from archive import play

        archive_url = "http://stream.example.com/archive/ch123/1700000000/3600.m3u8"
        params = {
            "play_cmd": archive_url,
            "unixtime": "1700000000",
            "duration": "3600",
        }

        play(ctx, params)

        xbmcplugin.setResolvedUrl.assert_called_once()
        call_args = xbmcplugin.setResolvedUrl.call_args
        # setResolvedUrl(handle, succeeded, listitem)
        assert call_args[0][0] == 1  # handle
        assert call_args[0][1] is True  # resolved=True
