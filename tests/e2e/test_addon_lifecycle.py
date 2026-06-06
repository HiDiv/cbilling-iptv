# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Addon lifecycle E2E tests.

Verifies that the addon installs correctly from ZIP in Kodi, appears in
Addons.GetAddons with enabled=true, and renders the expected main menu
items with Russian labels.
"""

import subprocess
import time

import pytest

from tests.e2e.kodi_client import KodiClient
from tests.e2e.utils import strip_kodi_tags

# Addon identifier
ADDON_ID = "plugin.video.cbilling.iptv"

# Expected main menu items (Russian locale) — order does not matter
EXPECTED_MENU_ITEMS = [
    "Прямой эфир",
    "Архив",
    "Любимые каналы",
    "Медиатека",
]


def _collect_kodi_log_tail(container_name: str, lines: int = 200) -> str:
    """Collect the last N lines of kodi.log from the container.

    Args:
        container_name: Docker container name or ID.
        lines: Number of lines to retrieve from the end of the log.

    Returns:
        String with the last N lines of kodi.log, or an error message
        if collection fails.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "tail",
                "-n",
                str(lines),
                "/root/.kodi/temp/kodi.log",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout
        return "Failed to collect kodi.log (exit code %d): %s" % (
            result.returncode,
            result.stderr.strip(),
        )
    except Exception as exc:
        return "Failed to collect kodi.log: %s" % exc


@pytest.mark.e2e
class TestAddonLifecycle:
    """Tests for addon ZIP installation and startup in Kodi."""

    def test_addon_enabled_after_zip_install(
        self,
        kodi_client: KodiClient,
        kodi_container: str,
    ) -> None:
        """Verify addon appears in Addons.GetAddons with enabled=true after ZIP install.

        Polls Kodi every 2 seconds until the addon is found with enabled status
        or timeout expires. On failure, attaches the last 200 lines of kodi.log.

        Validates: Requirements 4.5
        """
        deadline = time.monotonic() + 60.0
        addon_found = False
        addon_enabled = False

        while time.monotonic() < deadline:
            result = kodi_client.send_request(
                "Addons.GetAddons",
                {
                    "type": "xbmc.python.pluginsource",
                    "enabled": True,
                    "properties": ["enabled"],
                },
            )
            addons = result.get("addons") or []
            for addon in addons:
                if addon.get("addonid") == ADDON_ID:
                    addon_found = True
                    addon_enabled = addon.get("enabled", False)
                    break
            if addon_found:
                break
            time.sleep(2.0)

        if not addon_found:
            log_tail = _collect_kodi_log_tail(kodi_container)
            pytest.fail(
                "Addon '%s' not found in Addons.GetAddons after 60s.\n\n"
                "--- Last 200 lines of kodi.log ---\n%s" % (ADDON_ID, log_tail)
            )

        assert addon_enabled, "Addon '%s' found but not enabled (enabled=%s)" % (ADDON_ID, addon_enabled)

    def test_addon_main_menu_renders(
        self,
        kodi_client: KodiClient,
        kodi_container: str,
    ) -> None:
        """Verify addon main menu renders at least one item within 60 seconds.

        Queries the addon root directory via Files.GetDirectory and waits
        for at least one item to appear in the directory listing.

        Validates: Requirements 7.1
        """
        try:
            items = kodi_client.wait_for_content(min_items=1, timeout=60.0)
        except Exception:
            log_tail = _collect_kodi_log_tail(kodi_container)
            pytest.fail("Addon main menu not visible within 60s.\n\n--- Last 200 lines of kodi.log ---\n%s" % log_tail)

        assert len(items) >= 1, "Expected at least 1 menu item, got %d" % len(items)

    def test_main_menu_russian_labels(
        self,
        kodi_client: KodiClient,
        kodi_container: str,
    ) -> None:
        """Verify main menu contains all expected Russian-language items.

        Queries the addon root directory and checks that the menu contains:
        "Прямой эфир", "Архив", "Любимые каналы", "Медиатека".
        Labels are stripped of Kodi formatting tags before comparison.

        Validates: Requirements 7.1, 7.3
        """
        try:
            items = kodi_client.wait_for_content(min_items=1, timeout=60.0)
        except Exception:
            log_tail = _collect_kodi_log_tail(kodi_container)
            pytest.fail("Addon main menu not visible within 60s.\n\n--- Last 200 lines of kodi.log ---\n%s" % log_tail)

        # Strip Kodi formatting tags from all labels
        item_labels = [strip_kodi_tags(item.get("label", "")) for item in items]

        # Verify each expected Russian label is present
        missing = []
        for expected in EXPECTED_MENU_ITEMS:
            if expected not in item_labels:
                missing.append(expected)

        if missing:
            log_tail = _collect_kodi_log_tail(kodi_container)
            pytest.fail(
                "Main menu missing expected Russian labels: %s\n"
                "Found labels (after strip_kodi_tags): %s\n\n"
                "--- Last 200 lines of kodi.log ---\n%s" % (missing, item_labels, log_tail)
            )
