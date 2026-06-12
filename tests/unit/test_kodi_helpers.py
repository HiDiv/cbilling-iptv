# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for kodi_helpers module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))

from kodi_helpers import debug_log, get_localized, get_setting, info_log, show_notification


class FakeSettings:
    """Fake settings accessor for testing."""

    def __init__(self, data=None):
        self._data = data or {}
        self._strings = {}

    def getSetting(self, key):
        return self._data.get(key, "")

    def getLocalizedString(self, string_id):
        return self._strings.get(string_id, "String %d" % string_id)


class TestDebugLog:
    def test_calls_xbmc_log(self, mock_kodi_modules):
        # Verify no exception is raised when calling debug_log
        debug_log("test message")

    def test_handles_non_string(self, mock_kodi_modules):
        debug_log(42)


class TestInfoLog:
    def test_calls_xbmc_log(self, mock_kodi_modules):
        info_log("info message")

    def test_handles_non_string(self, mock_kodi_modules):
        info_log(None)


class TestShowNotification:
    def test_shows_notification(self, mock_kodi_modules):
        show_notification("Title", "Message")

    def test_custom_duration(self, mock_kodi_modules):
        show_notification("Title", "Message", duration=2000)


class TestGetLocalized:
    def test_returns_localized_string(self):
        settings = FakeSettings()
        settings._strings[30001] = "Live TV"
        result = get_localized(settings, 30001)
        assert result == "Live TV"

    def test_returns_default_format(self):
        settings = FakeSettings()
        result = get_localized(settings, 99999)
        assert result == "String 99999"


class TestGetSetting:
    def test_returns_string_value(self):
        settings = FakeSettings({"server": "http://example.com"})
        result = get_setting(settings, "server")
        assert result == "http://example.com"

    def test_returns_default_for_empty(self):
        settings = FakeSettings({"empty_key": ""})
        result = get_setting(settings, "empty_key", default="fallback")
        assert result == "fallback"

    def test_returns_default_for_missing(self):
        settings = FakeSettings({})
        result = get_setting(settings, "missing", default="fallback")
        assert result == "fallback"

    def test_cast_to_int(self):
        settings = FakeSettings({"port": "8080"})
        result = get_setting(settings, "port", cast=int)
        assert result == 8080

    def test_cast_to_float(self):
        settings = FakeSettings({"ratio": "1.5"})
        result = get_setting(settings, "ratio", cast=float)
        assert result == 1.5

    def test_cast_to_bool_true(self):
        settings = FakeSettings({"enabled": "true"})
        result = get_setting(settings, "enabled", cast=bool)
        assert result is True

    def test_cast_to_bool_false(self):
        settings = FakeSettings({"enabled": "false"})
        result = get_setting(settings, "enabled", cast=bool)
        assert result is False

    def test_cast_failure_returns_default(self):
        settings = FakeSettings({"port": "not_a_number"})
        result = get_setting(settings, "port", default="0", cast=int)
        assert result == "0"

    def test_no_cast_returns_raw_string(self):
        settings = FakeSettings({"value": "42"})
        result = get_setting(settings, "value")
        assert result == "42"
        assert isinstance(result, str)
