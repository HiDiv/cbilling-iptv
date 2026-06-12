# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Dict-based URL parameter extraction and mode dispatch."""

import base64
from typing import Any, Callable, Dict, Optional
from urllib.parse import unquote


def extract_params(argv2: str) -> Dict[str, str]:
    """
    Parse plugin URL query string into a parameter dict.

    Args:
        argv2: sys.argv[2] raw query string

    Returns:
        Dict of parameter name -> decoded value
    """
    if len(argv2) < 2:
        return {}
    cleaned = argv2.lstrip("?").rstrip("/")
    result: Dict[str, str] = {}
    for pair in cleaned.split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            result[parts[0]] = unquote(parts[1])
    return result


def get_param(
    params: Dict[str, str],
    name: str,
    default: Any = "",
    transform: Optional[Callable[[str], Any]] = None,
) -> Any:
    """
    Extract a single parameter with optional transform.

    Args:
        params: parsed parameter dict
        name: parameter name
        default: default if missing or empty
        transform: optional callable to apply to raw value

    Returns:
        Transformed value or default
    """
    raw = params.get(name, "")
    if not raw:
        return default
    if transform is not None:
        try:
            return transform(raw)
        except (ValueError, TypeError):
            return default
    return raw


def local_b64decode(value: str) -> str:
    """Decode URL-safe base64 string with padding."""
    return base64.urlsafe_b64decode(value.encode("utf-8") + b"========").decode("utf-8")


# Parameter name -> (default_value, transform_function)
PARAM_DEFAULTS: Dict[str, tuple] = {
    "mode": (None, None),
    "group_id": ("", None),
    "cat_id": ("*", None),
    "page_nr": (1, int),
    "play_cmd": ("", None),
    "name": ("", local_b64decode),
    "channel_title": ("", None),
    "movie_name": ("-", None),
    "season_name": ("-", None),
    "archive": ("", None),
    "channel_id": ("", None),
    "depth": ("", None),
    "date": ("", None),
    "ts": (0, int),
    "unixtime": ("", None),
    "poster_url": ("", None),
    "duration": (None, None),
    "favorites": ("0", None),
    "action": (None, None),
    "cat_alias": (None, None),
    "genre_id": ("*", None),
    "sortby": ("top", None),
    "movie_id": ("0", None),
    "season_id": ("0", None),
    "episode_id": ("0", None),
    "vod_search": (None, None),
    "vod_year": (None, None),
    "logo_png": (None, None),
    "focus_episode_id": ("0", None),
    "direct": (0, int),
}


def build_dispatch_table():
    # type: () -> Dict[str, Callable]
    """
    Build the mode -> handler mapping.

    Returns:
        Dict mapping mode strings to handler callables.
        Each handler accepts (ctx, params) where ctx is AddonContext
        and params is the extracted parameter dict.
    """
    # Imported lazily to avoid circular imports
    from resources.lib import archive, auth, channels, epg_db, favorites, playback, vod, watch_history

    return {
        "CBILLING_start": channels.main_menu,
        "channel_groups": channels.channel_groups,
        "get_channels_list": channels.get_channels_list,
        "itv_fav_add_remove": favorites.add_remove,
        "play_live_channel": playback.play_live_channel,
        "timepick_live_channel": playback.timepick_live_channel,
        "play_live_event_from_start": playback.play_live_event_from_start,
        "archive_channel_dates": archive.channel_dates,
        "archive_channel_epg": archive.channel_epg,
        "play_archive_channel": archive.play,
        "download_archive_record": archive.download,
        "epg_show": epg_db.epg_show,
        "get_stream_servers": auth.get_stream_servers,
        "cron_epg_init": epg_db.cron_epg_init,
        "vod_start": vod.start,
        "vod_get_category": vod.get_category,
        "vod_get_category_genres": vod.get_category_genres,
        "vod_get_ordered_list": vod.get_ordered_list,
        "vod_get_seasons": vod.get_seasons,
        "vod_get_episodes": vod.get_episodes,
        "vod_play_movie": vod.play_movie,
        "vod_search_page": vod.search_page,
        "vod_watch_history": watch_history.show,
        "vod_history_remove": watch_history.remove,
        "vod_history_clear": watch_history.clear,
        "show_vod_info": vod.show_info,
        "vod_cache_manage": vod.cache_manage,
        "vod_debug": vod.debug,
    }


def dispatch(ctx, argv2):
    # type: (Any, str) -> None
    """
    Main entry point: extract params and dispatch to handler.

    Args:
        ctx: AddonContext instance
        argv2: sys.argv[2] raw query string
    """
    params = extract_params(argv2)
    mode = params.get("mode", None)

    table = build_dispatch_table()

    handler = table.get(mode)
    if handler is not None:
        handler(ctx, params)
    else:
        # Default: show main menu (None, empty, or unrecognized mode)
        from resources.lib import channels

        channels.init_and_start(ctx, cron_job_request=False)
