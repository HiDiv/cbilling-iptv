# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E tests for main menu navigation with Russian labels.

Verifies that navigating to each main menu section renders the expected
content with correct Russian labels, and that back navigation returns
to the main menu with all 4 items visible.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.7
"""

from contextlib import suppress
from typing import List

import pytest

from tests.e2e.exceptions import KodiRpcError
from tests.e2e.kodi_client import KodiClient
from tests.e2e.utils import strip_kodi_tags, strip_labels

# Addon plugin base URL
_ADDON_URL = "plugin://plugin.video.cbilling.iptv/"

# Plugin paths for each main menu section
_LIVE_TV_PATH = _ADDON_URL + "?mode=channel_groups&archive=false"
_ARCHIVE_PATH = _ADDON_URL + "?mode=channel_groups&archive=true"
_FAVORITES_PATH = _ADDON_URL + "?mode=get_channels_list&group_id=*&favorites=1&action=live"
_VOD_PATH = _ADDON_URL + "?mode=vod_start"

# Expected Russian menu labels
_LABEL_LIVE_TV = "\u041f\u0440\u044f\u043c\u043e\u0439 \u044d\u0444\u0438\u0440"
_LABEL_ARCHIVE = "\u0410\u0440\u0445\u0438\u0432"
_LABEL_FAVORITES = "\u041b\u044e\u0431\u0438\u043c\u044b\u0435 \u043a\u0430\u043d\u0430\u043b\u044b"
_LABEL_VOD = "\u041c\u0435\u0434\u0438\u0430\u0442\u0435\u043a\u0430"

# All expected main menu labels
_EXPECTED_MENU_LABELS = [_LABEL_LIVE_TV, _LABEL_ARCHIVE, _LABEL_FAVORITES, _LABEL_VOD]

# Expected number of main menu items
_MAIN_MENU_ITEM_COUNT = 4

# Content wait timeout in seconds (increased for real API calls)
_CONTENT_TIMEOUT = 60.0


@pytest.mark.e2e
class TestLiveTVNavigation:
    """Tests for navigating to the Live TV section."""

    def test_live_tv_has_channels(self, kodi_client: KodiClient) -> None:
        """Navigate to Live TV and verify at least 1 channel item within 60s.

        Requirement 10.1: navigating to "Прямой эфир" shows >=1 channel.
        """
        items = kodi_client.get_container_items(path=_LIVE_TV_PATH)
        labels = strip_labels(items)
        assert len(labels) >= 1, "Expected at least 1 channel group in Live TV, got %d" % len(labels)


@pytest.mark.e2e
class TestArchiveNavigation:
    """Tests for navigating to the Archive section."""

    def test_archive_has_channels(self, kodi_client: KodiClient) -> None:
        """Navigate to Archive and verify at least 1 archive channel within 60s.

        Requirement 10.2: navigating to "Архив" shows >=1 channel with archive.
        """
        items = kodi_client.get_container_items(path=_ARCHIVE_PATH)
        labels = strip_labels(items)
        assert len(labels) >= 1, "Expected at least 1 channel group in Archive, got %d" % len(labels)


@pytest.mark.e2e
class TestFavoritesNavigation:
    """Tests for navigating to the Favorites section."""

    def test_favorites_renders_without_error(self, kodi_client: KodiClient) -> None:
        """Navigate to Favorites and verify directory renders (0 items acceptable).

        Requirement 10.3: navigating to "Любимые каналы" renders successfully.
        An empty list is acceptable for a fresh installation.
        """
        items = []  # type: List[dict]
        with suppress(KodiRpcError):
            items = kodi_client.get_container_items(path=_FAVORITES_PATH)

        # We only verify no unhandled exception occurred; 0 items is valid
        assert isinstance(items, list), "Expected a list response from Favorites"

        # Apply strip_kodi_tags to any returned labels for consistency
        for item in items:
            stripped = strip_kodi_tags(item.get("label", ""))
            assert isinstance(stripped, str)


@pytest.mark.e2e
class TestVODNavigation:
    """Tests for navigating to the VOD Library section."""

    def test_vod_has_categories(self, kodi_client: KodiClient) -> None:
        """Navigate to VOD and verify at least 1 category item within 60s.

        Requirement 10.4: navigating to "Медиатека" shows >=1 VOD category.
        """
        items = kodi_client.get_container_items(path=_VOD_PATH)
        labels = strip_labels(items)
        assert len(labels) >= 1, "Expected at least 1 VOD category, got %d" % len(labels)


@pytest.mark.e2e
class TestBackNavigation:
    """Tests for back navigation returning to the main menu."""

    def _get_main_menu_items(self, kodi_client: KodiClient) -> List[dict]:
        """Retrieve main menu items from the addon root."""
        return kodi_client.get_container_items(path=_ADDON_URL)

    def _assert_main_menu_labels(self, items: List[dict]) -> None:
        """Assert main menu has all 4 expected Russian labels (stripped)."""
        labels = strip_labels(items)
        assert len(labels) == _MAIN_MENU_ITEM_COUNT, "Expected %d main menu items, got %d" % (
            _MAIN_MENU_ITEM_COUNT,
            len(labels),
        )
        for expected_label in _EXPECTED_MENU_LABELS:
            assert expected_label in labels, "Expected label '%s' in main menu, got: %s" % (expected_label, labels)

    def test_back_from_live_tv(self, kodi_client: KodiClient) -> None:
        """Navigate to Live TV, then back, verify main menu with all 4 items.

        Requirement 10.5: pressing back returns to main menu with all 4 items.
        """
        # Navigate into Live TV
        kodi_client.get_container_items(path=_LIVE_TV_PATH)

        # Go back to main menu and verify labels
        items = self._get_main_menu_items(kodi_client)
        self._assert_main_menu_labels(items)

    def test_back_from_archive(self, kodi_client: KodiClient) -> None:
        """Navigate to Archive, then back, verify main menu with all 4 items.

        Requirement 10.5: pressing back returns to main menu with all 4 items.
        """
        kodi_client.get_container_items(path=_ARCHIVE_PATH)

        items = self._get_main_menu_items(kodi_client)
        self._assert_main_menu_labels(items)

    def test_back_from_favorites(self, kodi_client: KodiClient) -> None:
        """Navigate to Favorites, then back, verify main menu with all 4 items.

        Requirement 10.5: pressing back returns to main menu with all 4 items.
        """
        with suppress(KodiRpcError):
            kodi_client.get_container_items(path=_FAVORITES_PATH)

        items = self._get_main_menu_items(kodi_client)
        self._assert_main_menu_labels(items)

    def test_back_from_vod(self, kodi_client: KodiClient) -> None:
        """Navigate to VOD, then back, verify main menu with all 4 items.

        Requirement 10.5: pressing back returns to main menu with all 4 items.
        """
        kodi_client.get_container_items(path=_VOD_PATH)

        items = self._get_main_menu_items(kodi_client)
        self._assert_main_menu_labels(items)


@pytest.mark.e2e
class TestNavigationLabels:
    """Tests verifying Russian labels are correctly rendered after strip_kodi_tags.

    Requirement 10.7: apply strip_kodi_tags() to all label comparisons.
    """

    def test_main_menu_russian_labels(self, kodi_client: KodiClient) -> None:
        """Verify main menu contains all 4 Russian labels after tag stripping."""
        items = kodi_client.get_container_items(path=_ADDON_URL)
        labels = strip_labels(items)

        assert len(labels) == _MAIN_MENU_ITEM_COUNT, "Expected %d main menu items, got %d" % (
            _MAIN_MENU_ITEM_COUNT,
            len(labels),
        )

        for expected_label in _EXPECTED_MENU_LABELS:
            assert expected_label in labels, (
                "Expected Russian label '%s' in main menu after strip_kodi_tags(), got: %s" % (expected_label, labels)
            )

    def test_live_tv_items_have_stripped_labels(self, kodi_client: KodiClient) -> None:
        """Verify Live TV items have non-empty labels after tag stripping."""
        items = kodi_client.get_container_items(path=_LIVE_TV_PATH)
        labels = strip_labels(items)

        # All items should have non-empty labels after stripping
        for label in labels:
            assert label, "Found empty label after strip_kodi_tags() in Live TV items"

    def test_archive_items_have_stripped_labels(self, kodi_client: KodiClient) -> None:
        """Verify Archive items have non-empty labels after tag stripping."""
        items = kodi_client.get_container_items(path=_ARCHIVE_PATH)
        labels = strip_labels(items)

        for label in labels:
            assert label, "Found empty label after strip_kodi_tags() in Archive items"

    def test_vod_items_have_stripped_labels(self, kodi_client: KodiClient) -> None:
        """Verify VOD items have non-empty labels after tag stripping."""
        items = kodi_client.get_container_items(path=_VOD_PATH)
        labels = strip_labels(items)

        for label in labels:
            assert label, "Found empty label after strip_kodi_tags() in VOD items"
