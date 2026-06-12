# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Integration tests for Router → Context → Handler → Kodi mock dispatch.

Verifies that the Router correctly dispatches URL parameters through
AddonContext to the appropriate handler, producing expected Kodi API calls.

Requirements: 7.2, 7.5
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


@pytest.fixture
def mock_settings():
    """Create a mock settings accessor matching SettingsAccessor protocol."""
    settings = MagicMock()
    settings.getSetting.return_value = ""
    settings.setSetting.return_value = None
    settings.getLocalizedString.side_effect = lambda sid: "String_%s" % sid
    return settings


@pytest.fixture
def mock_api():
    """Create a mock API client."""
    api = MagicMock()
    api.get_auth_info.return_value = {"public_token": "abc123", "server": "srv1"}
    return api


@pytest.fixture
def mock_adapter():
    """Create a mock API adapter."""
    return MagicMock()


@pytest.fixture
def ctx(mock_api, mock_adapter, mock_settings, tmp_path):
    """Create a real AddonContext with mock dependencies."""
    from context import AddonContext

    addon_dir = str(tmp_path / "addon")
    user_data_dir = str(tmp_path / "userdata")
    temp_dir = str(tmp_path / "temp")

    # Create fanart directory structure needed by main_menu
    fanart_dir = os.path.join(addon_dir, "fanart")
    os.makedirs(fanart_dir, exist_ok=True)
    os.makedirs(os.path.join(addon_dir, "resources"), exist_ok=True)
    os.makedirs(user_data_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    return AddonContext(
        api_client=mock_api,
        adapter=mock_adapter,
        addon_handle=1,
        settings=mock_settings,
        addon_dir=addon_dir,
        user_data_dir=user_data_dir,
        temp_dir=temp_dir,
        plugin_url="plugin://plugin.video.cbilling.iptv",
    )


class TestRouterDispatchMainMenu:
    """Test Router dispatches CBILLING_start mode to channels.main_menu."""

    def test_cbilling_start_adds_four_directory_items(self, ctx):
        """Router dispatches ?mode=CBILLING_start and main_menu adds 4 items."""
        from router import dispatch

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        dispatch(ctx, "?mode=CBILLING_start")

        assert xbmcplugin.addDirectoryItem.call_count == 4, (
            "main_menu should add exactly 4 directory items (Live TV, Archive, Favorites, VOD)"
        )

    def test_cbilling_start_calls_end_of_directory(self, ctx):
        """Router dispatches ?mode=CBILLING_start and main_menu calls endOfDirectory."""
        from router import dispatch

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        dispatch(ctx, "?mode=CBILLING_start")

        xbmcplugin.endOfDirectory.assert_called_once()


class TestRouterDispatchDefault:
    """Test Router default dispatch (no mode) calls init_and_start flow."""

    def test_empty_mode_calls_check_credentials(self, ctx, mock_settings):
        """Router with empty argv2 calls auth.check_credentials via init_and_start."""
        from router import dispatch

        # Configure settings so check_credentials proceeds
        mock_settings.getSetting.side_effect = lambda key: {
            "user_login": "test_user_key",
            "auth_epoch": "4",
            "reauth_seconds": "120",
        }.get(key, "")

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()
        xbmcplugin.setContent = MagicMock()

        with patch("resources.lib.auth.check_credentials", return_value="true") as mock_check:
            dispatch(ctx, "")
            mock_check.assert_called_once_with(ctx, False)
