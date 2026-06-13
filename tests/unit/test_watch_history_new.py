# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for resources/lib/watch_history.py (pure data functions)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))

from unittest.mock import MagicMock, patch

from watch_history import (
    add_entry,
    clear,
    clear_history,
    load_history,
    remove,
    remove_entry,
    save_history,
    show,
)


class TestSaveLoadRoundTrip:
    """save_history/load_history round-trip."""

    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        history = [
            {"movie_id": "m1", "season_id": "0", "episode_id": "0", "title": "Movie 1"},
            {"movie_id": "m2", "season_id": "0", "episode_id": "0", "title": "Movie 2"},
        ]
        save_history(path, history)
        result = load_history(path)
        assert result == history

    def test_round_trip_empty(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        save_history(path, [])
        result = load_history(path)
        assert result == []


class TestAddEntryInsertsAtIndex0:
    """add_entry inserts at index 0."""

    def test_new_entry_first(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        entry1 = {"movie_id": "m1", "season_id": "0", "episode_id": "0", "title": "First"}
        entry2 = {"movie_id": "m2", "season_id": "0", "episode_id": "0", "title": "Second"}
        add_entry(path, entry1)
        add_entry(path, entry2)
        result = load_history(path)
        assert result[0]["movie_id"] == "m2"
        assert result[1]["movie_id"] == "m1"


class TestAddEntryDeduplicates:
    """add_entry deduplicates (same movie_id/season_id/episode_id)."""

    def test_same_entry_twice(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        entry = {"movie_id": "m1", "season_id": "1", "episode_id": "5", "title": "Ep5"}
        add_entry(path, entry)
        add_entry(path, entry)
        result = load_history(path)
        assert len(result) == 1

    def test_updated_title_keeps_latest(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        entry_v1 = {"movie_id": "m1", "season_id": "1", "episode_id": "5", "title": "Old"}
        entry_v2 = {"movie_id": "m1", "season_id": "1", "episode_id": "5", "title": "New"}
        add_entry(path, entry_v1)
        add_entry(path, entry_v2)
        result = load_history(path)
        assert len(result) == 1
        assert result[0]["title"] == "New"


class TestAddEntryTrimsToMaxSize:
    """add_entry trims to max_size."""

    def test_trims_oldest(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        for i in range(7):
            entry = {"movie_id": "m%d" % i, "season_id": "0", "episode_id": "0"}
            add_entry(path, entry, max_size=5)
        result = load_history(path)
        assert len(result) == 5
        # Most recent should be first
        assert result[0]["movie_id"] == "m6"
        # Oldest kept should be m2 (m0, m1 trimmed)
        assert result[4]["movie_id"] == "m2"


class TestRemoveEntry:
    """remove_entry removes matching entry."""

    def test_removes_matching(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        entries = [
            {"movie_id": "m1", "season_id": "0", "episode_id": "0", "title": "A"},
            {"movie_id": "m2", "season_id": "0", "episode_id": "0", "title": "B"},
        ]
        save_history(path, entries)
        remove_entry(path, "m1", "0", "0")
        result = load_history(path)
        assert len(result) == 1
        assert result[0]["movie_id"] == "m2"

    def test_non_existent_entry_no_crash(self, tmp_path):
        """remove_entry with non-existent entry doesn't crash."""
        path = str(tmp_path / "watch_history.json")
        entry = {"movie_id": "m1", "season_id": "0", "episode_id": "0"}
        save_history(path, [entry])
        # Remove something that doesn't exist
        result = remove_entry(path, "m99", "0", "0")
        assert result is True
        loaded = load_history(path)
        assert len(loaded) == 1


class TestClearHistory:
    """clear_history empties the list."""

    def test_clears_all(self, tmp_path):
        path = str(tmp_path / "watch_history.json")
        entries = [
            {"movie_id": "m1", "season_id": "0", "episode_id": "0"},
            {"movie_id": "m2", "season_id": "0", "episode_id": "0"},
        ]
        save_history(path, entries)
        clear_history(path)
        result = load_history(path)
        assert result == []


class TestLoadHistoryMissingFile:
    """load_history from missing file returns []."""

    def test_missing_file(self, tmp_path):
        path = str(tmp_path / "no_such_file.json")
        result = load_history(path)
        assert result == []


class TestLoadHistoryMalformedFile:
    """load_history from malformed file returns []."""

    def test_invalid_json(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("not json at all {{{")
        result = load_history(path)
        assert result == []

    def test_wrong_structure(self, tmp_path):
        """JSON without 'history' key returns []."""
        path = str(tmp_path / "wrong.json")
        with open(path, "w") as f:
            f.write('{"items": [1, 2, 3]}')
        result = load_history(path)
        assert result == []


class TestSaveHistoryCreatesParentDir:
    """save_history creates parent directories if missing."""

    def test_nested_dir(self, tmp_path):
        path = str(tmp_path / "sub" / "nested" / "watch_history.json")
        history = [{"movie_id": "m1", "season_id": "0", "episode_id": "0"}]
        result = save_history(path, history)
        assert result is True
        assert os.path.exists(path)
        assert load_history(path) == history

    def test_error_on_invalid_path(self):
        path = "/dev/null/impossible/watch_history.json"
        result = save_history(path, [])
        assert result is False


class TestRemoveHandler:
    """Tests for the remove() router dispatch handler."""

    def test_remove_handler_removes_entry(self, tmp_path):
        """remove(ctx, params) removes the matching entry and refreshes."""
        path = str(tmp_path / "watch_history.json")
        entries = [
            {"movie_id": "m1", "season_id": "0", "episode_id": "0"},
            {"movie_id": "m2", "season_id": "0", "episode_id": "0"},
        ]
        save_history(path, entries)

        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        params = {"movie_id": "m1", "season_id": "0", "episode_id": "0"}

        mock_xbmc = MagicMock()
        with patch.dict("sys.modules", {"xbmc": mock_xbmc}):
            remove(ctx, params)

        result = load_history(path)
        assert len(result) == 1
        assert result[0]["movie_id"] == "m2"
        mock_xbmc.executebuiltin.assert_called_once_with("Container.Refresh")


class TestClearHandler:
    """Tests for the clear() router dispatch handler."""

    def test_clear_handler_confirmed(self, tmp_path):
        """clear(ctx, params) clears history when user confirms."""
        path = str(tmp_path / "watch_history.json")
        entries = [{"movie_id": "m1", "season_id": "0", "episode_id": "0"}]
        save_history(path, entries)

        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        ctx.handle = 1

        mock_xbmc = MagicMock()
        mock_xbmcgui = MagicMock()
        mock_xbmcplugin = MagicMock()
        mock_dialog = MagicMock()
        mock_dialog.yesno.return_value = True
        mock_xbmcgui.Dialog.return_value = mock_dialog

        with patch.dict(
            "sys.modules",
            {
                "xbmc": mock_xbmc,
                "xbmcgui": mock_xbmcgui,
                "xbmcplugin": mock_xbmcplugin,
            },
        ):
            clear(ctx, {})

        result = load_history(path)
        assert result == []
        mock_xbmc.executebuiltin.assert_called_once_with("Container.Refresh")

    def test_clear_handler_cancelled(self, tmp_path):
        """clear(ctx, params) does NOT clear when user cancels."""
        path = str(tmp_path / "watch_history.json")
        entries = [{"movie_id": "m1", "season_id": "0", "episode_id": "0"}]
        save_history(path, entries)

        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        ctx.handle = 1

        mock_xbmc = MagicMock()
        mock_xbmcgui = MagicMock()
        mock_xbmcplugin = MagicMock()
        mock_dialog = MagicMock()
        mock_dialog.yesno.return_value = False
        mock_xbmcgui.Dialog.return_value = mock_dialog

        with patch.dict(
            "sys.modules",
            {
                "xbmc": mock_xbmc,
                "xbmcgui": mock_xbmcgui,
                "xbmcplugin": mock_xbmcplugin,
            },
        ):
            clear(ctx, {})

        result = load_history(path)
        assert len(result) == 1


class TestShowHandler:
    """Tests for the show() router dispatch handler."""

    def test_show_renders_history_items(self, tmp_path):
        """show(ctx, params) renders history entries as directory items."""
        path = str(tmp_path / "watch_history.json")
        entries = [
            {"movie_id": "101", "season_id": "0", "episode_id": "0",
             "title": "Movie One", "season_name": "-", "poster": "http://p1.jpg",
             "content_type": "movie"},
            {"movie_id": "202", "season_id": "55", "episode_id": "999",
             "title": "Series Two", "season_name": "Season 2",
             "episode_name": "Finale", "episode_number": "10",
             "poster": "http://p2.jpg", "content_type": "episode"},
        ]
        save_history(path, entries)

        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        ctx.handle = 1
        ctx.plugin_url = "plugin://plugin.video.cbilling.iptv/"
        ctx.addon_dir = str(tmp_path)
        ctx.settings = MagicMock()
        ctx.settings.getLocalizedString.side_effect = lambda sid: "String_%s" % sid

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()

        show(ctx, {})

        assert xbmcplugin.addDirectoryItem.call_count == 2

    def test_show_episode_display_includes_episode_name(self, tmp_path):
        """Episode entries in history should include episode name in label."""
        path = str(tmp_path / "watch_history.json")
        entries = [
            {"movie_id": "303", "season_id": "77", "episode_id": "888",
             "title": "My Series", "season_name": "Season 1",
             "episode_name": "Pilot", "episode_number": "1",
             "poster": "", "content_type": "episode"},
        ]
        save_history(path, entries)

        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        ctx.handle = 1
        ctx.plugin_url = "plugin://plugin.video.cbilling.iptv/"
        ctx.addon_dir = str(tmp_path)
        ctx.settings = MagicMock()
        ctx.settings.getLocalizedString.side_effect = lambda sid: "String_%s" % sid

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()

        # Track ListItem labels
        labels = []
        original_li = sys.modules["xbmcgui"].ListItem

        class TrackLI:
            def __init__(self, label="", **kwargs):
                self.label = label
                labels.append(label)

            def setArt(self, *a, **kw):  # noqa: N802
                pass

            def setInfo(self, *a, **kw):  # noqa: N802
                pass

            def setProperty(self, *a, **kw):  # noqa: N802
                pass

            def addContextMenuItems(self, *a, **kw):  # noqa: N802
                pass

        sys.modules["xbmcgui"].ListItem = TrackLI

        show(ctx, {})

        sys.modules["xbmcgui"].ListItem = original_li

        assert len(labels) == 1
        assert "Pilot" in labels[0], "Episode name should be in label, got: %s" % labels[0]

    def test_show_episode_url_has_focus_episode_id(self, tmp_path):
        """Episode entries should have focus_episode_id in URL."""
        path = str(tmp_path / "watch_history.json")
        entries = [
            {"movie_id": "404", "season_id": "88", "episode_id": "777",
             "title": "Show", "season_name": "S1",
             "episode_name": "", "episode_number": "",
             "poster": "", "content_type": "episode"},
        ]
        save_history(path, entries)

        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        ctx.handle = 1
        ctx.plugin_url = "plugin://plugin.video.cbilling.iptv/"
        ctx.addon_dir = str(tmp_path)
        ctx.settings = MagicMock()
        ctx.settings.getLocalizedString.side_effect = lambda sid: "String_%s" % sid

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.addDirectoryItem = MagicMock()
        xbmcplugin.endOfDirectory = MagicMock()

        show(ctx, {})

        call_args = xbmcplugin.addDirectoryItem.call_args_list[0]
        url = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("url", "")
        assert "focus_episode_id=777" in url, "URL should contain focus_episode_id"

    def test_clear_dialog_has_text(self, tmp_path):
        """clear() dialog should show confirmation text, not empty strings."""
        path = str(tmp_path / "watch_history.json")
        save_history(path, [{"movie_id": "1", "season_id": "0", "episode_id": "0"}])

        ctx = MagicMock()
        ctx.user_data_dir = str(tmp_path)
        ctx.handle = 1
        ctx.settings = MagicMock()
        ctx.settings.getLocalizedString.side_effect = lambda sid: "String_%s" % sid

        xbmcplugin = sys.modules["xbmcplugin"]
        xbmcplugin.endOfDirectory = MagicMock()

        mock_dialog = MagicMock()
        mock_dialog.yesno.return_value = False
        sys.modules["xbmcgui"].Dialog = MagicMock(return_value=mock_dialog)

        clear(ctx, {})

        # Verify yesno was called with non-empty strings
        mock_dialog.yesno.assert_called_once()
        call_args = mock_dialog.yesno.call_args[0]
        assert call_args[0] != "", "Dialog title should not be empty"
        assert call_args[1] != "", "Dialog text should not be empty"
