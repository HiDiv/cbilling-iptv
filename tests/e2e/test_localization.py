# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Localization E2E tests.

Verifies that the addon renders correctly with Russian locale (default)
and performs a smoke test with English locale to ensure basic compatibility.
"""

import time

import pytest

from tests.e2e.kodi_client import KodiClient
from tests.e2e.utils import strip_kodi_tags, strip_labels

# Addon identifier
ADDON_ID = "plugin.video.cbilling.iptv"

# Expected Russian main menu labels
EXPECTED_RU_LABELS = [
    "Прямой эфир",
    "Архив",
    "Любимые каналы",
    "Медиатека",
]

# Content wait timeout in seconds
CONTENT_TIMEOUT = 60.0

# Delay after locale switch for Kodi to reload
LOCALE_SWITCH_DELAY = 5.0


@pytest.mark.e2e
class TestLocalizationRussian:
    """Tests for Russian locale label rendering."""

    def test_main_menu_russian_labels(
        self,
        kodi_client: KodiClient,
    ) -> None:
        """Verify main menu renders with Russian labels after strip_kodi_tags().

        Launches the addon and checks that all expected Russian labels
        are present in the main menu directory listing.

        Validates: Requirements 7.1
        """
        # Launch addon to ensure it is active
        kodi_client.send_request(
            "Addons.ExecuteAddon",
            {"addonid": ADDON_ID},
        )

        # Wait for main menu content to appear
        items = kodi_client.wait_for_content(min_items=1, timeout=CONTENT_TIMEOUT)

        # Strip Kodi formatting tags from labels
        labels = [strip_kodi_tags(item.get("label", "")) for item in items]

        # Verify each expected Russian label is present
        missing = [label for label in EXPECTED_RU_LABELS if label not in labels]

        assert not missing, "Main menu missing expected Russian labels: %s\nFound labels: %s" % (missing, labels)


@pytest.mark.e2e
class TestLocalizationEnglish:
    """Smoke test for English locale compatibility."""

    def test_english_locale_smoke(
        self,
        kodi_client: KodiClient,
    ) -> None:
        """Switch to English locale, verify addon renders, restore Russian.

        Switches Kodi language to resource.language.en_gb, launches the
        addon, verifies the main menu renders at least one item without
        errors, then restores Russian locale.

        Validates: Requirements 7.4, 7.5
        """
        try:
            # Switch to English locale
            kodi_client.send_request(
                "Settings.SetSettingValue",
                {"setting": "locale.language", "value": "resource.language.en_gb"},
            )

            # Wait for Kodi to reload after locale switch
            time.sleep(LOCALE_SWITCH_DELAY)

            # Navigate home first to reset state
            kodi_client.input_home()
            time.sleep(1.0)

            # Launch addon in English locale
            kodi_client.send_request(
                "Addons.ExecuteAddon",
                {"addonid": ADDON_ID},
            )

            # Verify addon renders at least one menu item
            items = kodi_client.wait_for_content(min_items=1, timeout=CONTENT_TIMEOUT)
            labels = strip_labels(items)

            assert len(labels) >= 1, (
                "Addon main menu did not render in English locale. Expected at least 1 item, got %d" % len(labels)
            )

        finally:
            # Always restore Russian locale to avoid affecting subsequent tests
            kodi_client.send_request(
                "Settings.SetSettingValue",
                {"setting": "locale.language", "value": "resource.language.ru_ru"},
            )

            # Wait for Kodi to reload after restoring locale
            time.sleep(LOCALE_SWITCH_DELAY)
