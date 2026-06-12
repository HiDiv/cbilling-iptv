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
