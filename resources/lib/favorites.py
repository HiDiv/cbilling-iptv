# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Local favorites management (JSON file I/O)."""

import json
import os
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from resources.lib.context import AddonContext


def load(path: str) -> List[str]:
    """
    Load favorite channel IDs from JSON file.

    Returns empty list on any I/O or parse error.
    """
    try:
        if os.path.exists(path):
            with open(path) as f:
                data = json.loads(f.read())
                if isinstance(data, list):
                    return data
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return []


def save(path: str, fav_ids: List[str]) -> bool:
    """
    Save favorite IDs to JSON file.

    Creates parent directories if missing.
    Returns True on success, False on error.
    """
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent)
        with open(path, "w") as f:
            f.write(json.dumps(fav_ids))
        return True
    except OSError:
        return False


def add_remove(ctx: "AddonContext", params: dict) -> None:
    """Handle add/remove favorite from router dispatch."""
    import xbmc

    from resources.lib.kodi_helpers import debug_log, get_localized, show_notification

    channel_id = params.get("channel_id")
    action = params.get("action")

    addon_name = "Cbilling"

    if action is None:
        # 30033: "No action specified"
        show_notification(addon_name, get_localized(ctx.settings, 30033), 2000)
        return

    fav_path = os.path.join(ctx.user_data_dir, "favorites.json")
    fav_ids = load(fav_path)

    if action == "remove":
        if channel_id in fav_ids:
            fav_ids.remove(channel_id)
        else:
            # 30035: "Channel not in favorites"
            show_notification(addon_name, get_localized(ctx.settings, 30035), 2000)
            return

    elif action == "add":
        if channel_id in fav_ids:
            # 30036: "Channel already in favorites"
            show_notification(addon_name, get_localized(ctx.settings, 30036), 2000)
            return
        fav_ids.append(channel_id)

    save(fav_path, fav_ids)

    # 30038: "Added to favorites", 30039: "Removed from favorites"
    msg = get_localized(ctx.settings, 30038) if action == "add" else get_localized(ctx.settings, 30039)
    show_notification(addon_name, msg, 2000)

    if action == "remove":
        xbmc.executebuiltin("Container.Refresh")

    debug_log("[add_remove] channel_id=%s action=%s" % (channel_id, action))
