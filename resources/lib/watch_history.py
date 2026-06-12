# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Watch history management (JSON file I/O with deduplication)."""

import json
import os
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from resources.lib.context import AddonContext

HISTORY_FILENAME = "watch_history.json"


# ---------------------------------------------------------------------------
# Pure data functions (no Kodi imports)
# ---------------------------------------------------------------------------


def load_history(path: str) -> List[Dict]:
    """Load watch history from JSON file.

    Args:
        path: Full path to the watch_history.json file.

    Returns:
        List of history entry dicts, or empty list on error.
    """
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data = json.loads(fh.read())
                return data.get("history", [])
    except (OSError, ValueError):
        pass
    return []


def save_history(path: str, history: List[Dict]) -> bool:
    """Save watch history to JSON file. Creates parent dirs if missing.

    Args:
        path: Full path to the watch_history.json file.
        history: List of history entry dicts.

    Returns:
        True on success, False on I/O error.
    """
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"history": history}, ensure_ascii=False, indent=2))
        return True
    except OSError:
        return False


def add_entry(path: str, entry: Dict, max_size: int = 5) -> bool:
    """Add entry with deduplication on (movie_id, season_id, episode_id).

    Most recent entry is placed at index 0. History is trimmed to max_size.

    Args:
        path: Full path to the watch_history.json file.
        entry: Dict with at least movie_id, season_id, episode_id keys.
        max_size: Maximum number of items to keep.

    Returns:
        True on successful save, False on error.
    """
    history = load_history(path)
    history = [
        item
        for item in history
        if not (
            item.get("movie_id") == entry.get("movie_id")
            and item.get("season_id") == entry.get("season_id")
            and item.get("episode_id") == entry.get("episode_id")
        )
    ]
    history.insert(0, entry)
    if len(history) > max_size:
        history = history[:max_size]
    return save_history(path, history)


def remove_entry(path: str, movie_id: str, season_id: str, episode_id: str) -> bool:
    """Remove a specific entry from watch history.

    Args:
        path: Full path to the watch_history.json file.
        movie_id: Movie/series ID to match.
        season_id: Season ID to match.
        episode_id: Episode ID to match.

    Returns:
        True on successful save, False on error.
    """
    history = load_history(path)
    new_history = [
        item
        for item in history
        if not (
            item.get("movie_id") == movie_id
            and item.get("season_id") == season_id
            and item.get("episode_id") == episode_id
        )
    ]
    return save_history(path, new_history)


def clear_history(path: str) -> bool:
    """Clear all watch history.

    Args:
        path: Full path to the watch_history.json file.

    Returns:
        True on successful save, False on error.
    """
    return save_history(path, [])


# ---------------------------------------------------------------------------
# Router dispatch handlers — signature: (ctx, params) -> None
# ---------------------------------------------------------------------------


def show(ctx: "AddonContext", params: dict) -> None:
    """Render watch history list in Kodi UI.

    Full implementation deferred to task 7.4.
    """
    pass  # pragma: no cover


def remove(ctx: "AddonContext", params: dict) -> None:
    """Remove an entry from watch history and refresh container.

    Extracts movie_id, season_id, episode_id from params and delegates
    to remove_entry with path derived from ctx.user_data_dir.
    """
    import xbmc

    path = os.path.join(ctx.user_data_dir, HISTORY_FILENAME)
    movie_id = params.get("movie_id", "")
    season_id = params.get("season_id", "0")
    episode_id = params.get("episode_id", "0")
    remove_entry(path, movie_id, season_id, episode_id)
    xbmc.executebuiltin("Container.Refresh")


def clear(ctx: "AddonContext", params: dict) -> None:
    """Clear all watch history after confirmation and refresh container.

    Shows a yes/no dialog for user confirmation before clearing.
    """
    import xbmc
    import xbmcgui
    import xbmcplugin

    path = os.path.join(ctx.user_data_dir, HISTORY_FILENAME)
    dialog = xbmcgui.Dialog()
    if dialog.yesno("", ""):
        clear_history(path)
        xbmc.executebuiltin("Container.Refresh")
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)
