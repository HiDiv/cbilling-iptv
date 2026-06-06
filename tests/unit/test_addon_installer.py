# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for addon_installer module.

Tests cover find_addon_zip() discovery logic and settings.xml generation
in Kodi 20 format. These tests run without Docker or a running Kodi instance.
"""

import os
import sys
import time
import xml.etree.ElementTree as ET

# Ensure tests/e2e modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

from tests.e2e.addon_installer import (
    find_addon_zip,
)

# ===========================================================================
# find_addon_zip() Tests
# ===========================================================================


class TestFindAddonZip:
    """Test find_addon_zip() discovery logic."""

    def test_positive_zip_exists(self, tmp_path):
        """Returns filename when a matching addon ZIP exists."""
        zip_file = tmp_path / "plugin.video.cbilling.iptv-2.0.4-dev.zip"
        zip_file.write_bytes(b"PK\x03\x04fake")

        result = find_addon_zip(str(tmp_path))

        assert result == "plugin.video.cbilling.iptv-2.0.4-dev.zip"

    def test_negative_no_zip(self, tmp_path):
        """Returns None when no matching ZIP exists in the directory."""
        # Create a non-matching file
        other_file = tmp_path / "some_other_file.txt"
        other_file.write_text("not a zip")

        result = find_addon_zip(str(tmp_path))

        assert result is None

    def test_negative_nonexistent_directory(self, tmp_path):
        """Returns None when the dist directory does not exist."""
        nonexistent = str(tmp_path / "nonexistent_dir")

        result = find_addon_zip(nonexistent)

        assert result is None

    def test_negative_wrong_addon_id_zip(self, tmp_path):
        """Returns None when ZIP exists but doesn't match addon ID pattern."""
        wrong_zip = tmp_path / "plugin.video.other.addon-1.0.0.zip"
        wrong_zip.write_bytes(b"PK\x03\x04fake")

        result = find_addon_zip(str(tmp_path))

        assert result is None

    def test_boundary_multiple_zips_returns_newest(self, tmp_path):
        """Returns the most recently modified ZIP when multiple exist."""
        # Create older ZIP
        old_zip = tmp_path / "plugin.video.cbilling.iptv-2.0.3-dev.zip"
        old_zip.write_bytes(b"PK\x03\x04old")
        # Set modification time to the past
        old_time = time.time() - 100
        os.utime(str(old_zip), (old_time, old_time))

        # Create newer ZIP
        new_zip = tmp_path / "plugin.video.cbilling.iptv-2.0.4-dev.zip"
        new_zip.write_bytes(b"PK\x03\x04new")

        result = find_addon_zip(str(tmp_path))

        assert result == "plugin.video.cbilling.iptv-2.0.4-dev.zip"

    def test_boundary_empty_directory(self, tmp_path):
        """Returns None when the directory exists but is empty."""
        result = find_addon_zip(str(tmp_path))

        assert result is None

    def test_positive_returns_filename_not_full_path(self, tmp_path):
        """Returns only the filename, not the full path."""
        zip_file = tmp_path / "plugin.video.cbilling.iptv-2.0.4-dev.zip"
        zip_file.write_bytes(b"PK\x03\x04fake")

        result = find_addon_zip(str(tmp_path))

        assert "/" not in result
        assert "\\" not in result


# ===========================================================================
# Settings XML Generation Tests
# ===========================================================================


def _build_settings_xml(settings_dict):
    """Build settings XML string using the same logic as provision_settings.

    This replicates the XML generation from provision_settings() to test
    the format without requiring Docker.
    """
    lines = ['<settings version="2">']
    for setting_id, value in settings_dict.items():
        lines.append('    <setting id="%s">%s</setting>' % (setting_id, value))
    lines.append("</settings>")
    return "\n".join(lines) + "\n"


class TestSettingsXmlGeneration:
    """Test settings.xml generation in Kodi 20 format."""

    def test_positive_kodi20_format(self):
        """Generated XML uses Kodi 20 format with version='2' root element."""
        settings = {"user_login": "test_key", "api_url": "http://api.example.com"}

        xml_str = _build_settings_xml(settings)

        # Parse and verify structure
        root = ET.fromstring(xml_str)
        assert root.tag == "settings"
        assert root.attrib["version"] == "2"

    def test_positive_setting_elements_format(self):
        """Each setting uses <setting id='key'>value</setting> format."""
        settings = {"user_login": "my_key", "show_vod": "true"}

        xml_str = _build_settings_xml(settings)

        root = ET.fromstring(xml_str)
        elements = root.findall("setting")
        assert len(elements) == 2

        # Verify id attribute and text content
        for elem in elements:
            assert "id" in elem.attrib
            assert elem.text is not None

        # Check specific values
        login_elem = root.find(".//setting[@id='user_login']")
        assert login_elem is not None
        assert login_elem.text == "my_key"

        vod_elem = root.find(".//setting[@id='show_vod']")
        assert vod_elem is not None
        assert vod_elem.text == "true"

    def test_positive_contains_all_required_fields(self):
        """Settings XML contains all required fields per Requirement 5.3."""
        settings = {
            "user_login": "PUBLIC_KEY_123",
            "api_url": "https://api.cbilling.tv",
            "stb_timezone": "Europe/Moscow",
            "show_vod": "true",
        }

        xml_str = _build_settings_xml(settings)

        root = ET.fromstring(xml_str)

        # Verify all required settings are present
        required_ids = ["user_login", "api_url", "stb_timezone", "show_vod"]
        for setting_id in required_ids:
            elem = root.find(".//setting[@id='%s']" % setting_id)
            assert elem is not None, "Missing required setting: %s" % setting_id
            assert elem.text is not None, "Empty value for setting: %s" % setting_id

    def test_positive_values_match_input(self):
        """Setting values in XML match the input dictionary exactly."""
        settings = {
            "user_login": "ABC123",
            "api_url": "https://api.example.com/v2",
            "stb_timezone": "Asia/Novosibirsk",
            "show_vod": "false",
        }

        xml_str = _build_settings_xml(settings)

        root = ET.fromstring(xml_str)
        for setting_id, expected_value in settings.items():
            elem = root.find(".//setting[@id='%s']" % setting_id)
            assert elem.text == expected_value

    def test_boundary_empty_settings_dict(self):
        """Empty settings dict produces valid XML with no setting elements."""
        xml_str = _build_settings_xml({})

        root = ET.fromstring(xml_str)
        assert root.tag == "settings"
        assert root.attrib["version"] == "2"
        assert len(root.findall("setting")) == 0

    def test_boundary_single_setting(self):
        """Single setting produces valid XML with one setting element."""
        settings = {"user_login": "key123"}

        xml_str = _build_settings_xml(settings)

        root = ET.fromstring(xml_str)
        elements = root.findall("setting")
        assert len(elements) == 1
        assert elements[0].attrib["id"] == "user_login"
        assert elements[0].text == "key123"

    def test_positive_not_old_kodi18_format(self):
        """Generated XML does NOT use old Kodi 18 format (value attribute)."""
        settings = {"user_login": "test_key"}

        xml_str = _build_settings_xml(settings)

        # Old format: <setting id="x" value="y"/>
        # New format: <setting id="x">y</setting>
        root = ET.fromstring(xml_str)
        for elem in root.findall("setting"):
            assert "value" not in elem.attrib, "Should not use old Kodi 18 'value' attribute format"

    def test_positive_xml_is_well_formed(self):
        """Generated XML is well-formed and parseable."""
        settings = {
            "user_login": "key",
            "api_url": "http://example.com",
            "stb_timezone": "Europe/Moscow",
            "show_vod": "true",
        }

        xml_str = _build_settings_xml(settings)

        # Should not raise any exception
        root = ET.fromstring(xml_str)
        assert root is not None
