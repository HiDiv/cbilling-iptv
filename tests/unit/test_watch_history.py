# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for watch history functionality.

Migrated from: test_watch_history.py
"""

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


@pytest.fixture
def history_env(tmp_path, mock_kodi_modules):
    """Set up mocks so body.py can be imported and history uses tmp_path."""
    data_dir = str(tmp_path / "test_data")
    os.makedirs(data_dir, exist_ok=True)

    # Fake sys.argv for body.py
    old_argv = sys.argv[:]
    sys.argv = ["plugin://plugin.video.cbilling.iptv/", "1", ""]

    # Patch xbmcaddon to return our tmp data dir
    class TmpAddon:
        def __init__(self, id=None):
            pass

        def getAddonInfo(self, info_id):
            if info_id == "profile":
                return data_dir
            if info_id == "path":
                return os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
            return ""

        def getSetting(self, setting_id):
            if setting_id == "history_size":
                return "5"
            return ""

    mod_addon = types.ModuleType("xbmcaddon")
    mod_addon.Addon = TmpAddon
    sys.modules["xbmcaddon"] = mod_addon

    # Patch xbmcvfs to use real filesystem
    class RealXBMCVFS:
        @staticmethod
        def exists(path):
            return os.path.exists(path)

        @staticmethod
        def File(path, mode="r"):
            return open(path, mode)

        @staticmethod
        def translatePath(path):
            return path

        @staticmethod
        def mkdirs(path):
            os.makedirs(path, exist_ok=True)

    sys.modules["xbmcvfs"] = RealXBMCVFS()

    # Clear cached body module so it re-imports with our mocks
    for mod_name in list(sys.modules.keys()):
        if "body" in mod_name:
            del sys.modules[mod_name]

    from body import (
        add_to_watch_history,
        clear_watch_history,
        load_watch_history,
        remove_from_watch_history,
        save_watch_history,
    )

    yield {
        "data_dir": data_dir,
        "load": load_watch_history,
        "save": save_watch_history,
        "add": add_to_watch_history,
        "clear": clear_watch_history,
        "remove": remove_from_watch_history,
    }

    sys.argv = old_argv


def test_load_empty_history(history_env):
    history = history_env["load"]()
    assert history == []


def test_add_movie(history_env):
    history_env["add"](
        movie_id="123",
        season_id="0",
        episode_id="0",
        title="Test Movie",
        season_name="",
        episode_name="",
        episode_number="",
        poster="http://example.com/poster.jpg",
        content_type="movie",
    )
    history = history_env["load"]()
    assert len(history) == 1
    assert history[0]["title"] == "Test Movie"
    assert history[0]["type"] == "movie"


def test_add_episode(history_env):
    history_env["add"](
        movie_id="456",
        season_id="1",
        episode_id="101",
        title="Test Series",
        season_name="Season 1",
        episode_name="Episode 1",
        episode_number="1",
        poster="http://example.com/poster.jpg",
        content_type="episode",
    )
    history = history_env["load"]()
    assert len(history) == 1
    assert history[0]["title"] == "Test Series"


def test_deduplication(history_env):
    for _ in range(2):
        history_env["add"](
            movie_id="456",
            season_id="1",
            episode_id="101",
            title="Test Series",
            season_name="S1",
            episode_name="E1",
            episode_number="1",
            poster="",
            content_type="episode",
        )
    history = history_env["load"]()
    assert len(history) == 1


def test_history_size_limit(history_env):
    for i in range(8):
        history_env["add"](
            movie_id="movie_%d" % i,
            season_id="0",
            episode_id="0",
            title="Movie %d" % i,
            season_name="",
            episode_name="",
            episode_number="",
            poster="",
            content_type="movie",
        )
    history = history_env["load"]()
    assert len(history) == 5
    assert history[0]["title"] == "Movie 7"


def test_remove_item(history_env):
    history_env["add"](
        movie_id="100",
        season_id="0",
        episode_id="0",
        title="Movie A",
        season_name="",
        episode_name="",
        episode_number="",
        poster="",
        content_type="movie",
    )
    history_env["add"](
        movie_id="200",
        season_id="0",
        episode_id="0",
        title="Movie B",
        season_name="",
        episode_name="",
        episode_number="",
        poster="",
        content_type="movie",
    )
    history_env["remove"]("200", "0", "0")
    history = history_env["load"]()
    assert len(history) == 1
    assert history[0]["movie_id"] == "100"


def test_clear_history(history_env):
    history_env["add"](
        movie_id="100",
        season_id="0",
        episode_id="0",
        title="Movie",
        season_name="",
        episode_name="",
        episode_number="",
        poster="",
        content_type="movie",
    )
    history_env["clear"]()
    history = history_env["load"]()
    assert history == []
