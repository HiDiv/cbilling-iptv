# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Shared pytest fixtures for Kodi addon testing."""

import os
import sys

import pytest

# --- Kodi module mocks ---


class MockXBMC:
    LOGDEBUG = 0
    LOGINFO = 1
    LOGWARNING = 2
    LOGERROR = 3
    LOGFATAL = 4

    @staticmethod
    def log(msg, level=0):
        pass  # Suppress in tests

    @staticmethod
    def getRegion(region_id):
        return "%H:%M"

    @staticmethod
    def executebuiltin(cmd):
        pass

    @staticmethod
    def translatePath(path):
        return path


class MockXBMCGUI:
    class Dialog:
        def notification(self, *args, **kwargs):
            pass

        def ok(self, *args, **kwargs):
            pass

        def yesno(self, *args, **kwargs):
            return True

        def select(self, *args, **kwargs):
            return 0

    class ListItem:
        def __init__(self, label="", label2="", path="", **kwargs):
            self.label = label
            self.path = path

        def setArt(self, art):
            pass

        def setInfo(self, type, info=None, **kwargs):
            # Accept both positional and keyword arg styles
            pass

        def addContextMenuItems(self, items, **kwargs):
            pass

        def setProperty(self, key, value):
            pass

        def setLabel2(self, label2):
            pass

    class Window:
        def __init__(self, *args):
            pass

        def getFocusId(self):
            return 0

    @staticmethod
    def getCurrentWindowId():
        return 0


class MockXBMCPlugin:
    @staticmethod
    def addDirectoryItem(handle, url, listitem, isFolder=False, totalItems=0):
        pass

    @staticmethod
    def addDirectoryItems(handle, items, totalItems=0):
        pass

    @staticmethod
    def endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True):
        pass

    @staticmethod
    def setResolvedUrl(handle, succeeded, listitem):
        pass

    @staticmethod
    def setContent(handle, content):
        pass


class MockXBMCAddon:
    class Addon:
        def __init__(self, id=None):
            self._settings = {}

        def getSetting(self, key):
            return self._settings.get(key, "")

        def setSetting(self, key, value):
            self._settings[key] = value

        def getAddonInfo(self, key):
            info = {
                "id": "plugin.video.cbilling.iptv",
                "version": "2.1.0",
                "path": os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "profile": "/tmp/test_addon_data",
            }
            return info.get(key, "")

        def getLocalizedString(self, id):
            return "String_%s" % id


class MockXBMCVFS:
    @staticmethod
    def translatePath(path):
        return path

    @staticmethod
    def exists(path):
        return os.path.exists(path)

    @staticmethod
    def mkdirs(path):
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def mkdir(path):
        os.makedirs(path, exist_ok=True)

    class File:
        def __init__(self, path, mode="r"):
            self._file = open(path, mode)

        def read(self):
            return self._file.read()

        def write(self, data):
            self._file.write(data)

        def close(self):
            self._file.close()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()


@pytest.fixture(autouse=True)
def mock_kodi_modules():
    """Inject Kodi module mocks into sys.modules before each test."""
    saved = {}
    mod_names = ["xbmc", "xbmcgui", "xbmcplugin", "xbmcaddon", "xbmcvfs"]
    for name in mod_names:
        saved[name] = sys.modules.get(name)

    sys.modules["xbmc"] = MockXBMC()
    sys.modules["xbmcgui"] = MockXBMCGUI()
    sys.modules["xbmcplugin"] = MockXBMCPlugin()
    sys.modules["xbmcaddon"] = MockXBMCAddon()
    sys.modules["xbmcvfs"] = MockXBMCVFS()

    yield

    # Restore original state
    for name in mod_names:
        if saved[name] is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved[name]


@pytest.fixture
def addon_root():
    """Return the addon root directory path."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
