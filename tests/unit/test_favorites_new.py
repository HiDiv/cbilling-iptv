# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for resources/lib/favorites.py (pure data functions)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))

from unittest.mock import MagicMock, patch

from favorites import add_remove, load, save


class TestSaveLoadRoundTrip:
    """save then load returns the same list."""

    def test_round_trip_basic(self, tmp_path):
        path = str(tmp_path / "favorites.json")
        fav_ids = ["ch1", "ch2", "ch3"]
        save(path, fav_ids)
        result = load(path)
        assert result == fav_ids

    def test_round_trip_empty_list(self, tmp_path):
        path = str(tmp_path / "favorites.json")
        save(path, [])
        result = load(path)
        assert result == []


class TestLoadMissingFile:
    """load from non-existent file returns []."""

    def test_missing_file(self, tmp_path):
        path = str(tmp_path / "does_not_exist.json")
        result = load(path)
        assert result == []


class TestLoadMalformedJSON:
    """load from file with malformed JSON returns []."""

    def test_invalid_json(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("{not valid json!!")
        result = load(path)
        assert result == []


class TestLoadNonListJSON:
    """load from file with non-list JSON (e.g., dict) returns []."""

    def test_dict_json(self, tmp_path):
        path = str(tmp_path / "dict.json")
        with open(path, "w") as f:
            f.write('{"key": "value"}')
        result = load(path)
        assert result == []

    def test_string_json(self, tmp_path):
        path = str(tmp_path / "string.json")
        with open(path, "w") as f:
            f.write('"just a string"')
        result = load(path)
        assert result == []


class TestSaveCreatesParentDir:
    """save creates parent directory if missing."""

    def test_nested_dir(self, tmp_path):
        path = str(tmp_path / "subdir" / "nested" / "favorites.json")
        result = save(path, ["ch1"])
        assert result is True
        assert os.path.exists(path)
        assert load(path) == ["ch1"]


class TestSaveReturnValue:
    """save returns True on success, False on error."""

    def test_success(self, tmp_path):
        path = str(tmp_path / "favorites.json")
        result = save(path, ["ch1"])
        assert result is True

    def test_error_on_invalid_path(self):
        # /dev/null/impossible is not a valid directory
        path = "/dev/null/impossible/favorites.json"
        result = save(path, ["ch1"])
        assert result is False


class TestAddRemove:
    """Tests for add_remove router handler."""

    def _make_ctx(self, tmp_path):
        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        ctx.settings = MagicMock()
        return ctx

    def test_add_channel(self, tmp_path):
        """add_remove with action=add appends channel_id."""
        ctx = self._make_ctx(tmp_path)
        params = {"channel_id": "ch1", "action": "add"}

        mock_xbmc = MagicMock()
        mock_helpers = MagicMock()
        mock_helpers.get_localized.return_value = "Added"

        with patch.dict("sys.modules", {"xbmc": mock_xbmc}), patch(
            "resources.lib.kodi_helpers.show_notification",
            mock_helpers.show_notification,
        ), patch(
            "resources.lib.kodi_helpers.debug_log",
            mock_helpers.debug_log,
        ), patch(
            "resources.lib.kodi_helpers.get_localized",
            mock_helpers.get_localized,
        ):
            add_remove(ctx, params)

        result = load(str(tmp_path / "favorites.json"))
        assert "ch1" in result

    def test_remove_channel(self, tmp_path):
        """add_remove with action=remove removes channel_id."""
        ctx = self._make_ctx(tmp_path)
        save(str(tmp_path / "favorites.json"), ["ch1", "ch2"])
        params = {"channel_id": "ch1", "action": "remove"}

        mock_xbmc = MagicMock()
        mock_helpers = MagicMock()
        mock_helpers.get_localized.return_value = "Removed"

        with patch.dict("sys.modules", {"xbmc": mock_xbmc}), patch(
            "resources.lib.kodi_helpers.show_notification",
            mock_helpers.show_notification,
        ), patch(
            "resources.lib.kodi_helpers.debug_log",
            mock_helpers.debug_log,
        ), patch(
            "resources.lib.kodi_helpers.get_localized",
            mock_helpers.get_localized,
        ):
            add_remove(ctx, params)

        result = load(str(tmp_path / "favorites.json"))
        assert "ch1" not in result
        assert "ch2" in result
        mock_xbmc.executebuiltin.assert_called_once_with("Container.Refresh")

    def test_add_duplicate_shows_notification(self, tmp_path):
        """add_remove with action=add for existing channel shows notification."""
        ctx = self._make_ctx(tmp_path)
        save(str(tmp_path / "favorites.json"), ["ch1"])
        params = {"channel_id": "ch1", "action": "add"}

        mock_xbmc = MagicMock()
        mock_helpers = MagicMock()
        mock_helpers.get_localized.return_value = "Already exists"

        with patch.dict("sys.modules", {"xbmc": mock_xbmc}), patch(
            "resources.lib.kodi_helpers.show_notification",
            mock_helpers.show_notification,
        ), patch(
            "resources.lib.kodi_helpers.debug_log",
            mock_helpers.debug_log,
        ), patch(
            "resources.lib.kodi_helpers.get_localized",
            mock_helpers.get_localized,
        ):
            add_remove(ctx, params)

        mock_helpers.show_notification.assert_called()

    def test_remove_nonexistent_shows_notification(self, tmp_path):
        """add_remove with action=remove for missing channel shows notification."""
        ctx = self._make_ctx(tmp_path)
        save(str(tmp_path / "favorites.json"), ["ch2"])
        params = {"channel_id": "ch1", "action": "remove"}

        mock_xbmc = MagicMock()
        mock_helpers = MagicMock()
        mock_helpers.get_localized.return_value = "Not found"

        with patch.dict("sys.modules", {"xbmc": mock_xbmc}), patch(
            "resources.lib.kodi_helpers.show_notification",
            mock_helpers.show_notification,
        ), patch(
            "resources.lib.kodi_helpers.debug_log",
            mock_helpers.debug_log,
        ), patch(
            "resources.lib.kodi_helpers.get_localized",
            mock_helpers.get_localized,
        ):
            add_remove(ctx, params)

        mock_helpers.show_notification.assert_called()

    def test_no_action_shows_notification(self, tmp_path):
        """add_remove with no action param shows notification."""
        ctx = self._make_ctx(tmp_path)
        params = {"channel_id": "ch1"}

        mock_xbmc = MagicMock()
        mock_helpers = MagicMock()
        mock_helpers.get_localized.return_value = "No action"

        with patch.dict("sys.modules", {"xbmc": mock_xbmc}), patch(
            "resources.lib.kodi_helpers.show_notification",
            mock_helpers.show_notification,
        ), patch(
            "resources.lib.kodi_helpers.debug_log",
            mock_helpers.debug_log,
        ), patch(
            "resources.lib.kodi_helpers.get_localized",
            mock_helpers.get_localized,
        ):
            add_remove(ctx, params)

        mock_helpers.show_notification.assert_called()
