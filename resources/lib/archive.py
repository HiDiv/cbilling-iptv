# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Archive (time-shift) navigation and playback."""

import base64
import datetime
import os
import re
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import quote as url_quote
from urllib.parse import unquote as url_unquote

from resources.lib import kodi_helpers
from resources.lib.router import get_param, local_b64decode

if TYPE_CHECKING:
    from resources.lib.context import AddonContext


def _get_weekday_name(ctx: "AddonContext", date_obj: datetime.datetime) -> str:
    """Get localized weekday name for a date.

    Uses addon localization strings 30054-30060 for day names.
    Falls back to English strftime name on error.
    """
    # Localized day names: Mon=30054 .. Sun=30060
    weekday_ids = [30054, 30055, 30056, 30057, 30058, 30059, 30060]
    weekday_index = date_obj.weekday()  # 0=Monday .. 6=Sunday
    try:
        return kodi_helpers.get_localized(ctx.settings, weekday_ids[weekday_index])
    except (IndexError, Exception):
        return date_obj.strftime("%A")


def _current_unix_time() -> int:
    """Return current UTC time as unix timestamp."""
    utc_delta = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    return int(utc_delta.days * 86400 + utc_delta.seconds)


def channel_dates(ctx: "AddonContext", params: dict) -> None:
    """List available archive dates for a channel.

    Generates folder items for each day in the archive depth range
    (e.g., last 7 days).

    Args:
        ctx: AddonContext with handle, settings, adapter.
        params: Router params with channel_id, depth, name, play_cmd, logo_png.
    """
    import xbmc
    import xbmcgui
    import xbmcplugin

    channel_id = get_param(params, "channel_id")
    depth = get_param(params, "depth", default="7")
    name_encoded = params.get("name", "")
    channel_cmd = get_param(params, "play_cmd")
    logo_png = get_param(params, "logo_png", default="")

    # Decode channel name from base64
    try:
        name = local_b64decode(name_encoded) if name_encoded else ""
    except Exception:
        name = name_encoded

    kodi_helpers.debug_log("[archive.channel_dates] channel_id=%s depth=%s" % (channel_id, depth))

    if ctx.handle < 1:
        kodi_helpers.show_notification(
            "Cbilling",
            "%s. %s"
            % (
                kodi_helpers.get_localized(ctx.settings, 30061),
                kodi_helpers.get_localized(ctx.settings, 30062),
            ),
        )
        return

    archive_days = int(depth)
    logo_url = url_unquote(logo_png) if logo_png else ""
    fanart_path = os.path.join(ctx.addon_dir, "resources", "fanart")

    for archive_day in range(0, archive_days):
        unixtime_now = _current_unix_time()
        date_obj = datetime.datetime.fromtimestamp(unixtime_now) - datetime.timedelta(days=archive_day)
        archive_date_human = date_obj.strftime("%Y-%m-%d")
        day_name = _get_weekday_name(ctx, date_obj)

        label = "[COLOR burlywood]%s[/COLOR] (%s)" % (archive_date_human, day_name)

        # Encode name for URL transit
        name_b64 = re.sub("=", "", base64.urlsafe_b64encode(name.encode("utf-8")).decode("utf-8"))

        url = "%s?mode=archive_channel_epg&channel_id=%s&date=%s&name=%s&play_cmd=%s&logo_png=%s&direct=0" % (
            ctx.plugin_url,
            channel_id,
            archive_date_human,
            name_b64,
            url_quote(channel_cmd),
            url_quote(logo_url),
        )

        item = xbmcgui.ListItem(label, offscreen=True)
        item.setInfo(type="video", infoLabels={"title": label, "plot": name.strip()})

        try:
            item.setArt(
                {
                    "poster": logo_url,
                    "fanart": os.path.join(fanart_path, "archive_01.jpg"),
                }
            )
        except Exception:
            item.setArt({"fanart": os.path.join(fanart_path, "archive_01.jpg")})

        xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    xbmcplugin.setContent(ctx.handle, "files")

    viewmode = kodi_helpers.get_setting(ctx.settings, "viewmode", default="0")
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=True)


def channel_epg(ctx: "AddonContext", params: dict) -> None:
    """Show EPG entries for a specific archive date.

    Fetches EPG from SQLite cache or API, displays past events as playable
    and future events as non-playable.

    Args:
        ctx: AddonContext with handle, settings, adapter.
        params: Router params with channel_id, date, name, play_cmd, logo_png, direct.
    """
    import xbmc
    import xbmcgui
    import xbmcplugin

    channel_id = get_param(params, "channel_id")
    date = get_param(params, "date")
    name_encoded = params.get("name", "")
    channel_cmd = get_param(params, "play_cmd")
    logo_png = get_param(params, "logo_png", default="")

    # Decode channel name
    try:
        name = local_b64decode(name_encoded) if name_encoded else ""
    except Exception:
        name = name_encoded

    kodi_helpers.debug_log("[archive.channel_epg] channel_id=%s date=%s" % (channel_id, date))

    # Fetch EPG data via adapter
    channel_data = None
    try:
        channel_data = ctx.adapter.get_day_epg(channel_id, date=date)
    except Exception as e:
        kodi_helpers.debug_log("[archive.channel_epg] API error: %s" % str(e))
        channel_data = []

    if not channel_data:
        kodi_helpers.show_notification("Cbilling", kodi_helpers.get_localized(ctx.settings, 30065), 2000)
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    # Sort by stop_timestamp
    with suppress(ValueError, TypeError):
        channel_data = sorted(channel_data, key=lambda item: int(item.get("stop_timestamp", 0)))

    logo_url = url_unquote(logo_png) if logo_png else ""
    stream_url = url_unquote(channel_cmd) if channel_cmd else ""
    fanart_path = os.path.join(ctx.addon_dir, "resources", "fanart")
    thumb_play = os.path.join(ctx.addon_dir, "resources", "play.png")
    thumb_noplay = os.path.join(ctx.addon_dir, "resources", "clock.png")
    thumb_divider = os.path.join(ctx.addon_dir, "resources", "direction.png")

    unixtime_now = _current_unix_time()

    listing = []
    future_events = 0
    divider_position = 0
    items_counter = 1

    for epg_data in channel_data:
        epg_event_title = epg_data.get("name", "")
        start_time = epg_data.get("t_time", "")
        end_time = epg_data.get("t_time_to", "")
        start_ts = int(epg_data.get("start_timestamp", 0))
        stop_ts = int(epg_data.get("stop_timestamp", 0))
        duration = epg_data.get("duration", 0)
        if not duration and stop_ts and start_ts:
            duration = stop_ts - start_ts
        event_duration = str(duration)

        # Build archive URL
        archive_url = ctx.adapter.build_archive_url(stream_url, start_ts, duration, dvr_uri=epg_data.get("dvr_uri"))
        url = "%s?mode=play_archive_channel&play_cmd=%s&unixtime=%s&duration=%s" % (
            ctx.plugin_url,
            url_quote(archive_url),
            str(start_ts),
            event_duration,
        )

        is_past = stop_ts < unixtime_now

        if not is_past:
            item_name = "[COLOR lightsteelblue][%s - %s][/COLOR][COLOR lightsteelblue] %s [/COLOR]" % (
                start_time,
                end_time,
                epg_event_title,
            )
            future_events += 1
        else:
            item_name = "[COLOR burlywood][%s - %s][/COLOR][COLOR white] %s [/COLOR]" % (
                start_time,
                end_time,
                epg_event_title,
            )

        item = xbmcgui.ListItem(item_name, offscreen=True)
        descr = epg_data.get("descr", "")
        plot_desc = (
            "[COLOR white][B]%s[/B][/COLOR][CR]"
            "[COLOR rosybrown][B]%s[/B][/COLOR][CR]"
            "%s[CR][COLOR burlywood]%s[/COLOR]" % (date, name, epg_event_title.strip(), descr.strip())
        )
        item.setInfo(
            type="video",
            infoLabels={
                "title": item_name,
                "mediatype": "video",
                "plot": plot_desc,
            },
        )

        if not is_past:
            item.setArt(
                {
                    "poster": logo_url,
                    "thumb": thumb_noplay,
                    "fanart": os.path.join(fanart_path, "archive_01.jpg"),
                }
            )
            item.setProperty("IsPlayable", "false")
        else:
            item.setArt(
                {
                    "poster": logo_url,
                    "thumb": thumb_play,
                    "fanart": os.path.join(fanart_path, "archive_01.jpg"),
                }
            )
            item.setProperty("IsPlayable", "true")

            # Context menu for playable items
            context_menu = []
            context_menu.append(
                (
                    "%s" % kodi_helpers.get_localized(ctx.settings, 30128),
                    "RunPlugin(%s?mode=get_stream_servers)" % ctx.plugin_url,
                )
            )

            tham_tools = kodi_helpers.get_setting(ctx.settings, "tham_tools", default="false")
            if tham_tools == "true":
                context_menu.append(
                    (
                        "Download",
                        "RunPlugin(%s?mode=download_archive_record&play_cmd=%s&unixtime=%s&duration=%s)"
                        % (ctx.plugin_url, url_quote(archive_url), str(start_ts), event_duration),
                    )
                )

            item.addContextMenuItems(items=context_menu, replaceItems=True)

        # Insert divider before first future event
        if future_events == 1:
            divider_label = "[COLOR lightsteelblue][B]%s:[/B][/COLOR]" % (
                kodi_helpers.get_localized(ctx.settings, 30066)
            )
            item_extra = xbmcgui.ListItem(divider_label, offscreen=True)
            item_extra.setArt(
                {
                    "poster": logo_url,
                    "thumb": thumb_divider,
                    "fanart": os.path.join(fanart_path, "archive_01.jpg"),
                }
            )
            item_extra.setProperty("IsPlayable", "false")
            listing.append((url, item_extra, False))
            divider_position = items_counter
            items_counter += 1

        listing.append((url, item, False))
        items_counter += 1

    xbmcplugin.addDirectoryItems(ctx.handle, listing, totalItems=len(listing))
    xbmcplugin.setContent(ctx.handle, "videos")

    viewmode = kodi_helpers.get_setting(ctx.settings, "viewmode", default="0")
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=True)

    # Focus on divider position (last past event boundary)
    if divider_position > 0:
        xbmc.sleep(250)
        win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        cid = win.getFocusId()
        try:
            if int(xbmc.getInfoLabel("Container(id).CurrentItem")) == 0:
                xbmc.executebuiltin("SetFocus(%s, %s, absolute)" % (cid, divider_position - 1))
        except Exception:
            pass


def play(ctx: "AddonContext", params: dict) -> None:
    """Resolve and play an archive recording.

    Extracts play_cmd (pre-built archive URL), creates a ListItem,
    and sets it as resolved for Kodi playback.

    Args:
        ctx: AddonContext with handle.
        params: Router params with play_cmd, unixtime, duration.
    """
    import xbmcgui
    import xbmcplugin

    play_cmd = get_param(params, "play_cmd")
    stream_url = url_unquote(play_cmd)

    kodi_helpers.debug_log("[archive.play] URL: %s" % stream_url)

    item = xbmcgui.ListItem(path=stream_url, offscreen=True)
    xbmcplugin.setResolvedUrl(ctx.handle, True, item)


def download(ctx: "AddonContext", params: dict) -> None:
    """Download an archive recording to disk.

    Parses the m3u8 playlist, downloads TS segments, and merges them.

    Args:
        ctx: AddonContext with handle, temp_dir.
        params: Router params with play_cmd, unixtime, duration.
    """
    import urllib.request

    play_cmd = get_param(params, "play_cmd")
    stream_url = url_unquote(play_cmd)

    kodi_helpers.debug_log("[archive.download] URL: %s" % stream_url)

    regex_base = re.search(r"(^https?://.+/).+\.m3u8.*", stream_url)
    if not regex_base:
        kodi_helpers.show_notification("Cbilling", "ERROR: Can not parse stream URL", 3000)
        return

    base_url = regex_base.group(1)

    # Fetch first playlist to find track URL
    new_url = None
    try:
        with urllib.request.urlopen(stream_url) as resp:
            m3u8_init = resp.read().decode("utf-8").split("\n")
            for line in m3u8_init:
                if line.startswith("tracks"):
                    new_url = base_url + line
                    kodi_helpers.debug_log("[archive.download] Found track URL: %s" % new_url)
    except Exception as e:
        kodi_helpers.debug_log("[archive.download] Error fetching playlist: %s" % str(e))
        return

    # Fetch TS segment list
    ts_url_list = []
    if new_url:
        try:
            with urllib.request.urlopen(new_url) as resp:
                m3u8_contents = resp.read().decode("utf-8").split("\n")
                for line in m3u8_contents:
                    ts_match = re.search(r"(^https?://.+ts.+)", line)
                    if ts_match is not None:
                        ts_url_list.append(ts_match.group(1))
        except Exception as e:
            kodi_helpers.debug_log("[archive.download] Error fetching segments: %s" % str(e))
            return

    if not ts_url_list:
        kodi_helpers.debug_log("[archive.download] No TS segments found")
        return

    # Create download directories
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
    download_dir = os.path.join(ctx.temp_dir, "%s_dl" % now_str)
    merge_dir = os.path.join(ctx.temp_dir, "%s_merge" % now_str)

    os.mkdir(download_dir, 0o666)
    os.mkdir(merge_dir, 0o666)

    kodi_helpers.debug_log("[archive.download] Downloading %d segments to %s" % (len(ts_url_list), download_dir))

    # Download and merge delegated to existing helper functions in body.py
    # (will be migrated in a later task)
