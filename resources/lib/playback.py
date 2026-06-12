# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Live stream resolution and playback handlers."""

import json
import re
import time
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import unquote as url_unquote

if TYPE_CHECKING:
    from resources.lib.context import AddonContext

from resources.lib.kodi_helpers import debug_log, get_localized, get_setting


def _get_epg_from_cache(ctx: "AddonContext", channel_id: str, limit: int) -> tuple:
    """Query local SQLite EPG cache for current programs.

    Returns:
        Tuple of (plot_lines, first_description, rows_found).
    """
    import sqlite3

    from resources.lib.epg_db import _epg_path

    plot_lines = []
    first_descr = ""
    rows_found = 0
    db_path = _epg_path(ctx)

    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cursor = conn.cursor()
        with suppress(Exception):
            cursor.execute("PRAGMA journal_mode=WAL")
        sql = "SELECT epg_json FROM epg WHERE ch_id = ? AND stop_timestamp > ? ORDER BY stop_timestamp LIMIT ?"
        cursor.execute(sql, (channel_id, int(time.time()), limit))
        for row in cursor:
            epg_item = json.loads(row[0])
            plot_lines.append("%s-%s: %s" % (epg_item["t_time"], epg_item["t_time_to"], epg_item["name"]))
            rows_found += 1
            if rows_found == 1:
                first_descr = epg_item.get("descr", "")
        conn.close()
    except Exception as exc:
        debug_log("[_get_epg_from_cache] SQLite error: %s" % str(exc))

    return (plot_lines, first_descr, rows_found)


def _get_epg_from_api(ctx: "AddonContext", channel_id: str, limit: int) -> tuple:
    """Fetch short EPG from remote API.

    Returns:
        Tuple of (plot_lines, first_description).
    """
    plot_lines = []
    first_descr = ""
    try:
        epg_items = ctx.adapter.get_short_epg(channel_id, size=limit)
        debug_log("[_get_epg_from_api] API returned %d items" % len(epg_items))
        for idx, item in enumerate(epg_items):
            plot_lines.append("%s-%s: %s" % (item["t_time"], item["t_time_to"], item["name"]))
            if idx == 0:
                first_descr = item.get("descr", "")
    except Exception as exc:
        debug_log("[_get_epg_from_api] error: %s" % str(exc))

    return (plot_lines, first_descr)


def _build_epg_plot(ctx: "AddonContext", channel_id: str) -> str:
    """Build EPG plot text for the player info screen."""
    limit = 10
    epg_label = get_localized(ctx.settings, 30050)
    plot_epg = "[B]%s:[/B]" % epg_label

    # Try cache first
    use_cache = get_setting(ctx.settings, "epg_cache", default="false", cast=bool)
    plot_lines = []
    first_descr = ""

    if use_cache:
        plot_lines, first_descr, rows_found = _get_epg_from_cache(ctx, channel_id, limit)
        if rows_found > 0:
            debug_log("[_build_epg_plot] SQLite EPG: %d items" % rows_found)

    if not plot_lines:
        plot_lines, first_descr = _get_epg_from_api(ctx, channel_id, limit)

    for line in plot_lines:
        plot_epg += "[CR]%s" % line

    if first_descr:
        plot_epg = "[COLOR white]%s[/COLOR][CR][CR]%s" % (first_descr.strip(), plot_epg)

    return plot_epg


def play_live_channel(ctx: "AddonContext", params: dict) -> None:
    """Resolve and play a live channel stream.

    Extracts the stream URL from params, builds EPG info for the player
    overlay, and hands the resolved URL to Kodi via setResolvedUrl.

    Args:
        ctx: AddonContext with adapter, settings, and handle.
        params: Router parameters dict with play_cmd, name, channel_id.
    """
    import xbmc
    import xbmcgui
    import xbmcplugin

    play_cmd = params.get("play_cmd", "")
    name = params.get("name", "")
    channel_id = params.get("channel_id", "")

    # Save last channel position
    with suppress(Exception):
        curr_item = xbmc.getInfoLabel("Container(id).CurrentItem")
        if curr_item != 0:
            ctx.settings.setSetting("last_channel", str(curr_item))

    debug_log("[play_live_channel] Playing: %s" % name)

    stream_url = url_unquote(play_cmd)
    item = xbmcgui.ListItem(path=stream_url, label=name, offscreen=True)

    # Build EPG plot for info overlay
    plot_epg = _build_epg_plot(ctx, channel_id)
    item.setInfo(type="video", infoLabels={"Title": name, "Plot": plot_epg})

    xbmcplugin.setResolvedUrl(ctx.handle, True, item)


def timepick_live_channel(ctx: "AddonContext", params: dict) -> None:
    """Time-picker for starting live playback from a specific time.

    Shows a date and time picker dialog. If the user selects a valid
    past time, builds an archive URL and starts playback.

    Args:
        ctx: AddonContext with adapter and settings.
        params: Router parameters dict with play_cmd, name, date.
    """
    import datetime

    import xbmc
    import xbmcgui

    play_cmd = params.get("play_cmd", "")
    name = params.get("name", "")
    date = params.get("date", "")

    stream_url = url_unquote(play_cmd)

    # Show date picker
    if len(str(date)) > 5:
        start_date = re.sub(r"(\d{4})-(\d{1,2})-(\d{1,2})", r"\3/\2/\1", date)
        input_date = xbmcgui.Dialog().numeric(1, get_localized(ctx.settings, 30051), start_date)
    else:
        input_date = xbmcgui.Dialog().numeric(1, get_localized(ctx.settings, 30051))

    input_date = input_date.replace(" ", "")

    if len(re.findall(r"/", input_date)) <= 1:
        return

    # Normalize date parts to 2-digit
    input_date_split = filter(None, input_date.split("/"))
    input_date = "/".join((len(x.strip()) < 2 and "0" + x.strip()) or x for x in input_date_split)

    # Show time picker
    input_time = xbmcgui.Dialog().numeric(2, get_localized(ctx.settings, 30052))
    if len(re.findall(r":", input_time)) == 0:
        return

    # Normalize time parts to 2-digit
    input_time_split = filter(None, input_time.split(":"))
    input_time = ":".join((len(x.strip()) < 2 and "0" + x.strip()) or x for x in input_time_split)

    selected_time = datetime.datetime.fromtimestamp(
        time.mktime(time.strptime("%s %s" % (input_date, input_time), "%d/%m/%Y %H:%M"))
    )
    selected_time_human = selected_time.strftime("%Y-%m-%d %H:%M")
    unixtime = int(time.mktime(selected_time.timetuple()))

    # Check that selected time is in the past
    unix_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    unix_now = int(unix_now_obj.days * 86400 + unix_now_obj.seconds)

    if unixtime > unix_now:
        import xbmcgui as _gui

        _gui.Dialog().notification("Cbilling", get_localized(ctx.settings, 30053), 2000)
        return

    duration = 3600

    item_name = "[COLOR green][B]%s[/B][/COLOR] [COLOR orange]%s[/COLOR]" % (
        name,
        selected_time_human,
    )

    debug_log("[timepick_live_channel] Requesting time: %s" % selected_time_human)

    stream_url_live = ctx.adapter.build_archive_url(stream_url, unixtime, duration)

    item = xbmcgui.ListItem(item_name, offscreen=True)
    item.setInfo("video", {"Title": item_name, "mediatype": "video"})

    video_player = xbmc.Player()
    video_player.play(stream_url_live, item)


def play_live_event_from_start(ctx: "AddonContext", params: dict) -> None:
    """Play current live event from its start timestamp.

    Builds an archive URL using the event start timestamp and launches
    playback via executebuiltin.

    Args:
        ctx: AddonContext with adapter.
        params: Router parameters dict with play_cmd, name, ts.
    """
    import xbmc

    play_cmd = params.get("play_cmd", "")
    name = params.get("name", "")
    ts = params.get("ts", 0)
    if isinstance(ts, str):
        try:
            ts = int(ts)
        except ValueError:
            ts = 0

    # Save last channel position
    with suppress(Exception):
        curr_item = xbmc.getInfoLabel("Container(id).CurrentItem")
        if curr_item != 0:
            ctx.settings.setSetting("last_channel", str(curr_item))

    debug_log("[play_live_event_from_start] ts=%d name=%s" % (ts, name))

    stream_url = url_unquote(play_cmd)
    stream_url_live = ctx.adapter.build_archive_url(stream_url, ts, 3600)

    xbmc.executebuiltin("PlayMedia(%s, resume)" % stream_url_live)
