# SPDX-FileCopyrightText: Thamerlan
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Compatibility shim — retained for backward compatibility with existing tests.

All business logic has been extracted to dedicated modules:
  - router.py: URL parameter extraction and dispatch
  - auth.py: credential verification
  - channels.py: channel groups and list rendering
  - epg_db.py: EPG database operations
  - playback.py: stream resolution
  - archive.py: time-shift navigation
  - vod.py: VOD navigation
  - favorites.py: local favorites I/O
  - watch_history.py: watch history I/O
  - kodi_helpers.py: Kodi API wrappers
  - context.py: dependency injection container
"""

import os
import sys
import time

import xbmc
import xbmcaddon
import xbmcgui
from xbmcvfs import translatePath as fsTranslatePath

# ---------------------------------------------------------------------------
# Module-level setup (required by tests that import body)
# ---------------------------------------------------------------------------

addon_handle = int(sys.argv[1])
PLUGIN_ID = "plugin.video.cbilling.iptv"
__addon__ = xbmcaddon.Addon(id=PLUGIN_ID)
__addonname__ = __addon__.getAddonInfo("name")
__addondir__ = fsTranslatePath(__addon__.getAddonInfo("path"))
__addonUserData__ = fsTranslatePath(__addon__.getAddonInfo("profile"))
__addonTempData__ = fsTranslatePath("special://temp")

# Watch history storage file
history_file = os.path.join(__addonUserData__, "watch_history.json")

# Local favorites storage file
fav_file = os.path.join(__addonUserData__, "favorites.json")


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def get_txt(string_id):
    """Get localized string by ID."""
    return __addon__.getLocalizedString(string_id)


def debug_log(line):
    """Log a debug message with [Cbilling] prefix."""
    xbmc.log("[Cbilling] " + str(line), level=xbmc.LOGDEBUG)


def show_msg(msg, time_to_show):
    """Show a Kodi notification."""
    xbmcgui.Dialog().notification(__addonname__, msg, xbmcgui.NOTIFICATION_INFO, time_to_show)


# ---------------------------------------------------------------------------
# Watch history (backward-compatible wrappers for test_watch_history.py)
# ---------------------------------------------------------------------------


def load_watch_history():
    """Load watch history from local JSON file."""
    from resources.lib.watch_history import load_history

    return load_history(history_file)


def save_watch_history(history):
    """Save watch history to local JSON file."""
    from resources.lib.watch_history import save_history

    save_history(history_file, history)
    debug_log("[save_watch_history] Saved %d items" % len(history))


def add_to_watch_history(
    movie_id, season_id, episode_id, title, season_name, episode_name, episode_number, poster, content_type
):
    """Add item to watch history with deduplication."""
    from resources.lib.watch_history import add_entry

    try:
        history_size = int(__addon__.getSetting("history_size"))
        if history_size < 1:
            history_size = 5
    except Exception:
        history_size = 5
    entry = {
        "movie_id": str(movie_id),
        "season_id": str(season_id),
        "episode_id": str(episode_id),
        "title": title,
        "season_name": season_name,
        "episode_name": episode_name,
        "episode_number": episode_number,
        "poster": poster,
        "timestamp": int(time.time()),
        "type": content_type,
    }
    add_entry(history_file, entry, max_size=history_size)
    debug_log("[add_to_watch_history] Added: %s (type=%s)" % (title, content_type))


def clear_watch_history():
    """Clear all watch history."""
    from resources.lib.watch_history import clear_history

    clear_history(history_file)
    debug_log("[clear_watch_history] History cleared")
    return True


def remove_from_watch_history(movie_id, season_id, episode_id):
    """Remove specific item from watch history."""
    from resources.lib.watch_history import remove_entry

    remove_entry(history_file, str(movie_id), str(season_id), str(episode_id))
    debug_log("[remove_from_watch_history] Removed item")
    return True


# ---------------------------------------------------------------------------
# Parameter extraction (legacy compatibility)
# ---------------------------------------------------------------------------


def get_params():
    """Extract URL parameters from sys.argv[2]."""
    from resources.lib.router import extract_params

    return extract_params(sys.argv[2])
