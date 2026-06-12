# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for playback.py — live stream resolution and setResolvedUrl."""

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
    settings._data["epg_cache"] = "false"

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


class TestPlayLiveChannel:
    """Test play_live_channel resolves URL and sets resolved."""

    def test_play_live_channel_calls_set_resolved_url(self, tmp_path):
        """play_live_channel should call setResolvedUrl with resolved=True."""
        ctx = _make_ctx(tmp_path)

        # Mock adapter to return empty short EPG
        ctx.adapter.get_short_epg.return_value = []

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.setResolvedUrl = MagicMock()

        # Mock xbmc.getInfoLabel
        xbmc_mod = sys.modules["xbmc"]
        xbmc_mod.getInfoLabel = MagicMock(return_value="1")

        from playback import play_live_channel

        params = {
            "play_cmd": "http://stream.example.com/live/ch1.m3u8",
            "name": "Test Channel",
            "channel_id": "ch1",
        }

        play_live_channel(ctx, params)

        xbmcplugin.setResolvedUrl.assert_called_once()
        call_args = xbmcplugin.setResolvedUrl.call_args
        # setResolvedUrl(handle, succeeded, listitem)
        assert call_args[0][0] == 1  # handle
        assert call_args[0][1] is True  # resolved=True

    def test_play_live_channel_creates_listitem_with_stream_url(self, tmp_path):
        """play_live_channel should create ListItem with correct stream URL path."""
        ctx = _make_ctx(tmp_path)

        ctx.adapter.get_short_epg.return_value = []

        # Track ListItem creation
        created_items = []
        original_listitem = sys.modules["xbmcgui"].ListItem

        class TrackingListItem:
            def __init__(self, label="", label2="", path="", offscreen=False):
                self.label = label
                self.path = path
                created_items.append(self)

            def setArt(self, art):  # noqa: N802
                pass

            def setInfo(self, type, infoLabels=None, **kwargs):  # noqa: N802, N803
                pass

            def setProperty(self, key, value):  # noqa: N802
                pass

        sys.modules["xbmcgui"].ListItem = TrackingListItem

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.setResolvedUrl = MagicMock()

        xbmc_mod = sys.modules["xbmc"]
        xbmc_mod.getInfoLabel = MagicMock(return_value="1")

        from playback import play_live_channel

        stream_url = "http://stream.example.com/live/ch1.m3u8"
        params = {
            "play_cmd": stream_url,
            "name": "Test Channel",
            "channel_id": "ch1",
        }

        play_live_channel(ctx, params)

        # Verify the ListItem was created with the stream URL as path
        assert len(created_items) > 0
        assert created_items[-1].path == stream_url

        # Restore original
        sys.modules["xbmcgui"].ListItem = original_listitem
