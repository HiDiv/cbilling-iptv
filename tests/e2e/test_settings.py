# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E tests for addon settings verification.

Verifies that addon settings are correctly provisioned and readable
by inspecting the settings.xml file inside the container via docker exec.
Since Addons.GetAddonSetting is not available in Kodi 20, settings are
read directly from the filesystem.

Requirements: 22.1, 22.2, 22.3, 22.4
"""

import subprocess
import xml.etree.ElementTree as ET

import pytest

from tests.e2e.config import E2EConfig

# Path to addon settings.xml inside the container
_SETTINGS_PATH = "/root/.kodi/userdata/addon_data/plugin.video.cbilling.iptv/settings.xml"


def _read_settings_xml(container_name: str) -> str:
    """Read settings.xml content from the container via docker exec.

    Args:
        container_name: Name of the running Docker container.

    Returns:
        Raw XML content of settings.xml.

    Raises:
        AssertionError: If the file cannot be read from the container.
    """
    result = subprocess.run(
        ["docker", "exec", container_name, "cat", _SETTINGS_PATH],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, "Failed to read settings.xml from container '%s': %s" % (
        container_name,
        result.stderr.strip(),
    )
    return result.stdout


def _parse_settings(xml_content: str) -> dict:
    """Parse Kodi 20 settings.xml into a dictionary.

    Kodi 20 format: <settings version="2"><setting id="key">value</setting></settings>

    Args:
        xml_content: Raw XML string.

    Returns:
        Dictionary mapping setting IDs to their values.
    """
    root = ET.fromstring(xml_content)
    settings = {}  # type: dict
    for setting_elem in root.findall("setting"):
        setting_id = setting_elem.get("id", "")
        setting_value = setting_elem.text or ""
        if setting_id:
            settings[setting_id] = setting_value
    return settings


@pytest.mark.e2e
class TestAddonSettings:
    """Tests for addon settings verification.

    Reads settings.xml from the container and verifies that provisioned
    values are correctly stored.

    Validates: Requirements 22.1, 22.2, 22.3, 22.4
    """

    def test_stb_timezone_setting(self, kodi_container: str) -> None:
        """Verify stb_timezone is set to Europe/Moscow.

        Validates: Requirement 22.1
        """
        xml_content = _read_settings_xml(kodi_container)
        settings = _parse_settings(xml_content)

        assert "stb_timezone" in settings, "Setting 'stb_timezone' not found in settings.xml"
        assert settings["stb_timezone"] == "Europe/Moscow", (
            "Expected stb_timezone='Europe/Moscow', got '%s'" % settings["stb_timezone"]
        )

    def test_api_url_setting(self, kodi_container: str, e2e_config: E2EConfig) -> None:
        """Verify api_url matches the provisioned value.

        Validates: Requirement 22.2
        """
        xml_content = _read_settings_xml(kodi_container)
        settings = _parse_settings(xml_content)

        expected_url = e2e_config.cbilling_api_url
        assert "api_url" in settings, "Setting 'api_url' not found in settings.xml"
        assert settings["api_url"] == expected_url, "Expected api_url='%s', got '%s'" % (
            expected_url,
            settings["api_url"],
        )

    def test_show_vod_setting(self, kodi_container: str) -> None:
        """Verify show_vod is set to true.

        Validates: Requirement 22.3
        """
        xml_content = _read_settings_xml(kodi_container)
        settings = _parse_settings(xml_content)

        assert "show_vod" in settings, "Setting 'show_vod' not found in settings.xml"
        assert settings["show_vod"] == "true", "Expected show_vod='true', got '%s'" % settings["show_vod"]
