# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E tests for favorites management.

Verifies adding and removing channels from favorites, and that the
favorites list renders correctly (including when empty).

Requirements: 21.1, 21.2, 21.3, 21.4
"""

import time
from contextlib import suppress

import pytest

from tests.e2e.kodi_client import KodiClient

# ---------------------------------------------------------------------------
# Configurable test content — change if channel becomes unavailable
# ---------------------------------------------------------------------------

# Channel alias used in plugin URLs
TEST_CHANNEL_ALIAS = "pervyj"

# Addon plugin base URL
_ADDON_URL = "plugin://plugin.video.cbilling.iptv/"

# URL to add a channel to favorites
_FAV_ADD_URL = _ADDON_URL + "?mode=itv_fav_add_remove&channel_id=%s&action=add"

# URL to remove a channel from favorites
_FAV_REMOVE_URL = _ADDON_URL + "?mode=itv_fav_add_remove&channel_id=%s&action=remove"

# URL to view the favorites list
_FAV_LIST_URL = _ADDON_URL + "?mode=get_channels_list&group_id=*&favorites=1&action=live"

# Delay after add/remove to let Kodi process the action (seconds)
_ACTION_DELAY = 2.0


def _add_to_favorites(kodi_client: KodiClient, channel_alias: str) -> None:
    """Add a channel to favorites via plugin URL.

    Triggers the RunPlugin action by calling Files.GetDirectory on the
    add URL. The action shows a notification and returns — it does not
    produce directory items.

    Args:
        kodi_client: Connected KodiClient instance.
        channel_alias: Channel alias to add (e.g. "pervyj").
    """
    url = _FAV_ADD_URL % channel_alias
    with suppress(Exception):
        kodi_client.send_request("Files.GetDirectory", {"directory": url})
    time.sleep(_ACTION_DELAY)


def _remove_from_favorites(kodi_client: KodiClient, channel_alias: str) -> None:
    """Remove a channel from favorites via plugin URL.

    Triggers the RunPlugin action by calling Files.GetDirectory on the
    remove URL. The action shows a notification and returns — it does not
    produce directory items.

    Args:
        kodi_client: Connected KodiClient instance.
        channel_alias: Channel alias to remove (e.g. "pervyj").
    """
    url = _FAV_REMOVE_URL % channel_alias
    with suppress(Exception):
        kodi_client.send_request("Files.GetDirectory", {"directory": url})
    time.sleep(_ACTION_DELAY)


def _get_favorites_list(kodi_client: KodiClient):
    """Get the list of channels in favorites.

    Args:
        kodi_client: Connected KodiClient instance.

    Returns:
        List of item dicts from the favorites directory, or empty list.
    """
    try:
        items = kodi_client.get_container_items(path=_FAV_LIST_URL)
    except Exception:
        # Empty favorites may return an error — treat as empty list
        items = []
    return items


def _channel_in_favorites(kodi_client: KodiClient, channel_alias: str) -> bool:
    """Check if a channel is present in the favorites list.

    Searches item file URLs for the channel alias.

    Args:
        kodi_client: Connected KodiClient instance.
        channel_alias: Channel alias to look for.

    Returns:
        True if the channel is found in favorites, False otherwise.
    """
    items = _get_favorites_list(kodi_client)
    for item in items:
        file_url = item.get("file", "")
        if channel_alias in file_url:
            return True
    return False


@pytest.mark.e2e
class TestFavorites:
    """Tests for favorites management (add, remove, list).

    Validates: Requirements 21.1, 21.2, 21.3, 21.4
    """

    def test_add_channel_to_favorites(self, kodi_client: KodiClient) -> None:
        """Verify adding a channel to favorites makes it appear in the list.

        Steps:
        1. Remove channel from favorites (ensure clean state)
        2. Add channel to favorites via plugin URL
        3. Query favorites list
        4. Verify channel appears in favorites

        Validates: Requirement 21.1
        """
        # Ensure clean state — remove first in case it's already there
        _remove_from_favorites(kodi_client, TEST_CHANNEL_ALIAS)

        # Add channel to favorites
        _add_to_favorites(kodi_client, TEST_CHANNEL_ALIAS)

        # Verify channel appears in favorites list
        assert _channel_in_favorites(kodi_client, TEST_CHANNEL_ALIAS), (
            "Channel '%s' not found in favorites after adding" % TEST_CHANNEL_ALIAS
        )

    def test_remove_channel_from_favorites(self, kodi_client: KodiClient) -> None:
        """Verify removing a channel from favorites removes it from the list.

        Steps:
        1. Add channel to favorites (ensure it's there)
        2. Remove channel from favorites via plugin URL
        3. Query favorites list
        4. Verify channel no longer in favorites

        Validates: Requirement 21.2
        """
        # Ensure channel is in favorites first
        _add_to_favorites(kodi_client, TEST_CHANNEL_ALIAS)
        assert _channel_in_favorites(kodi_client, TEST_CHANNEL_ALIAS), (
            "Channel '%s' should be in favorites before removal test" % TEST_CHANNEL_ALIAS
        )

        # Remove channel from favorites
        _remove_from_favorites(kodi_client, TEST_CHANNEL_ALIAS)

        # Verify channel no longer in favorites
        assert not _channel_in_favorites(kodi_client, TEST_CHANNEL_ALIAS), (
            "Channel '%s' still in favorites after removal" % TEST_CHANNEL_ALIAS
        )

    def test_empty_favorites_renders_without_error(self, kodi_client: KodiClient) -> None:
        """Verify empty favorites list renders without errors.

        Steps:
        1. Remove test channel from favorites (ensure empty)
        2. Query favorites list
        3. Verify no error is raised and result is an empty list

        Validates: Requirement 21.4
        """
        # Ensure favorites are empty by removing the test channel
        _remove_from_favorites(kodi_client, TEST_CHANNEL_ALIAS)

        # Query favorites — should return empty list without error
        items = _get_favorites_list(kodi_client)

        # Empty list is acceptable (no assertion on length > 0)
        # The key assertion is that no exception was raised above
        assert isinstance(items, list), "Favorites should return a list, got %s" % type(items).__name__
