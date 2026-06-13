# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Channel groups and list rendering module.

Handles main menu construction, channel group listing,
and channel list display with EPG data.
"""

import contextlib
import os

from resources.lib import auth, epg_db, kodi_helpers

# Sort priority mapping for channel groups (transliterated names)
_GROUP_SORT_PRIORITY = {
    "armeniia": "X",
    "azerbaidzhan": "X",
    "belarus'": "X",
    "kazakhstan": "X",
    "kino": "I",
    "moldaviia": "X",
    "mul'tfil'my": "K",
    "muzykal'nye": "D",
    "novosti": "E",
    "obshcherossiiskie": "A",
    "poznavatel'nye": "B",
    "rossiia +2ch": "X",
    "sport": "C",
    "turtsiia": "X",
    "uhd/4k": "L",
    "ukraina": "X",
    "uzbekistan": "X",
}


def build_epg_plot(short_epg, now_ts, label_now, label_next, label_elapsed, label_starts_in):
    """Build formatted EPG plot string from short_epg data.

    Pure function — no Kodi imports, no side effects.

    Args:
        short_epg: List of EPG entry dicts (current, next, ...).
        now_ts: Current unix timestamp (int).
        label_now: Localized "Now:" string (e.g. "Сейчас:").
        label_next: Localized "Next:" string (e.g. "Далее:").
        label_elapsed: Localized "%d min. elapsed" template (e.g. "%d мин. идёт").
        label_starts_in: Localized "in %d min." template (e.g. "через %d мин.").

    Returns:
        Formatted plot string with Kodi color tags, or empty string.
    """
    if not short_epg:
        return ""

    epg_current = short_epg[0] if len(short_epg) > 0 else {}
    epg_next = short_epg[1] if len(short_epg) > 1 else {}

    if not epg_current:
        return ""

    current_name = epg_current.get("name", "")
    if not current_name:
        return ""

    t_time = epg_current.get("t_time", "")
    t_time_to = epg_current.get("t_time_to", "")
    start_ts = int(epg_current.get("start_timestamp", 0) or 0)
    descr = epg_current.get("descr", "")

    plot_parts = []

    # Current program
    plot_parts.append(
        "[COLOR moccasin][B]%s[/B] %s[/COLOR]" % (label_now, current_name.strip())
    )

    # Time range with elapsed
    if t_time and t_time_to:
        elapsed_min = (now_ts - start_ts) // 60 if start_ts else 0
        if elapsed_min > 0:
            elapsed_str = label_elapsed % elapsed_min
            time_info = "[COLOR grey]%s \u2014 %s (%s)[/COLOR]" % (t_time, t_time_to, elapsed_str)
        else:
            time_info = "[COLOR grey]%s \u2014 %s[/COLOR]" % (t_time, t_time_to)
        plot_parts.append(time_info)

    # Next program
    if epg_next:
        next_name = epg_next.get("name", "")
        next_start = epg_next.get("t_time", "")
        next_end = epg_next.get("t_time_to", "")
        next_start_ts = int(epg_next.get("start_timestamp", 0) or 0)
        if next_name:
            starts_in_str = ""
            if next_start_ts:
                starts_in_min = (next_start_ts - now_ts) // 60
                if starts_in_min > 0:
                    starts_in_str = " (%s)" % (label_starts_in % starts_in_min)
            plot_parts.append("")
            plot_parts.append(
                "[COLOR burlywood][B]%s[/B] %s[/COLOR]" % (label_next, next_name)
            )
            next_time = ""
            if next_start and next_end:
                next_time = "%s \u2014 %s" % (next_start, next_end)
            elif next_start:
                next_time = next_start
            if next_time:
                plot_parts.append("[COLOR grey]%s%s[/COLOR]" % (next_time, starts_in_str))

    # Description
    if descr:
        plot_parts.append("")
        plot_parts.append("[COLOR white]%s[/COLOR]" % descr.strip())

    return "[CR]".join(plot_parts)


def _group_sort_key(group_name):
    """Return sort key for a channel group name."""
    prefix = _GROUP_SORT_PRIORITY.get(group_name, "M")
    return prefix + group_name


def main_menu(ctx, params):
    """Render the main start menu with 4 items: Live TV, Archive, Favorites, VOD.

    Args:
        ctx: AddonContext instance.
        params: Router parameters dict (unused).
    """
    import xbmc
    import xbmcgui
    import xbmcplugin

    fanart_path = os.path.join(ctx.addon_dir, "fanart")
    tv_poster = os.path.join(ctx.addon_dir, "fanart", "poster_play.png")
    vod_poster = os.path.join(ctx.addon_dir, "fanart", "poster_vod.png")
    get_txt = kodi_helpers.get_localized

    # Live TV
    name = "[COLOR white][B]%s[/B][/COLOR]" % get_txt(ctx.settings, 30026)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {
            "poster": tv_poster,
            "thumb": tv_poster,
            "fanart": os.path.join(fanart_path, "live_02.jpg"),
        }
    )
    url = "%s?mode=channel_groups&archive=false" % ctx.plugin_url
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    # Archive
    name = "[COLOR burlywood][B]%s[/B][/COLOR]" % get_txt(ctx.settings, 30027)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {
            "poster": tv_poster,
            "thumb": tv_poster,
            "fanart": os.path.join(fanart_path, "archive_01.jpg"),
        }
    )
    url = "%s?mode=channel_groups&archive=true" % ctx.plugin_url
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    # Favorites
    name = "[COLOR salmon][B]%s[/B][/COLOR]" % get_txt(ctx.settings, 30028)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {
            "poster": tv_poster,
            "thumb": tv_poster,
            "fanart": os.path.join(fanart_path, "fav.jpg"),
        }
    )
    url = "%s?mode=get_channels_list&group_id=*&favorites=1&action=live" % ctx.plugin_url
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    # VOD
    name = "[COLOR rosybrown][B]%s[/B][/COLOR]" % get_txt(ctx.settings, 30029)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {
            "poster": vod_poster,
            "thumb": vod_poster,
            "fanart": os.path.join(fanart_path, "vod_03.jpg"),
        }
    )
    url = "%s?mode=vod_start" % ctx.plugin_url
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    xbmcplugin.setContent(ctx.handle, "files")

    viewmode = kodi_helpers.get_setting(ctx.settings, "viewmode", default="0")
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    ctx.settings.setSetting("last_channel", "1")
    ctx.settings.setSetting("last_window", "0")

    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)


def init_and_start(ctx, cron_job_request):
    """Check credentials, manage cron jobs, then show main menu.

    Args:
        ctx: AddonContext instance.
        cron_job_request: If True, this is a cron-initiated call.
    """
    import xbmcgui

    get_txt = kodi_helpers.get_localized

    # Handle EPG delete request
    if kodi_helpers.get_setting(ctx.settings, "epg_delete", default="false") == "true":
        ctx.settings.setSetting("epg_delete", "false")
        epg_path = os.path.join(ctx.user_data_dir, "epg.db")
        if os.path.exists(epg_path):
            with contextlib.suppress(OSError):
                os.remove(epg_path)

    # Verify credentials
    status = auth.check_credentials(ctx, cron_job_request)

    if status != "true":
        if cron_job_request:
            kodi_helpers.info_log("check_credentials failed")
        else:
            try:
                err_msg = "%s: %s" % (get_txt(ctx.settings, 30019), status)
            except (TypeError, ValueError):
                err_msg = get_txt(ctx.settings, 30018)
            xbmcgui.Dialog().ok(
                kodi_helpers.get_setting(ctx.settings, "addon_name", default="Cbilling"),
                err_msg,
            )
        return False

    if cron_job_request:
        # Cron mode: rebuild EPG cache
        epg_db.reload(ctx, _get_epg_cache_hours(ctx), True)
    else:
        # Interactive mode: manage cron job and show menu
        main_menu(ctx, {})

    return None


def channel_groups(ctx, params):
    """List available channel groups/categories.

    Args:
        ctx: AddonContext instance.
        params: Router parameters dict (expects 'archive' key).
    """
    import xbmc
    import xbmcgui
    import xbmcplugin

    archive = params.get("archive", "false")
    get_txt = kodi_helpers.get_localized

    # Check if adult content is unlocked
    xxx_code = "GIMMESOMEXXX"
    xxx_enabled = kodi_helpers.get_setting(ctx.settings, "xxx_code") == xxx_code

    # Try to get genres from EPG cache first
    groups = []
    if kodi_helpers.get_setting(ctx.settings, "epg_cache", default="false") == "true":
        try:
            groups = epg_db.get_genres(ctx)
        except Exception:
            groups = []

    # Fallback to adapter API
    if not groups:
        try:
            groups = ctx.adapter.get_genres()
        except Exception:
            groups = None

        if not groups:
            kodi_helpers.show_notification(get_txt(ctx.settings, 30031), "", 3000)
            xbmcplugin.endOfDirectory(ctx.handle)
            return

    # Sort groups by priority
    try:
        from unidecode import unidecode as _unidecode
    except ImportError:

        def _unidecode(text):
            return text

    groups = sorted(groups, key=lambda g: _group_sort_key(_unidecode(g["title"]).lower()))

    fanart_path = os.path.join(ctx.addon_dir, "fanart")
    tv_poster = os.path.join(ctx.addon_dir, "fanart", "poster_play.png")
    thumb_browse = os.path.join(ctx.addon_dir, "resources", "thumb_browse.png")

    for group in groups:
        group_id = group["id"]
        group_title = group["title"]
        group_censored = str(group.get("censored", "0")) == "1"

        # Skip wildcard IDs and censored groups when not unlocked
        if "*" in str(group_id) or (not xxx_enabled and group_censored):
            continue

        action = "archive" if archive == "true" else "live"
        url = "%s?mode=get_channels_list&action=%s&group_id=%s&favorites=0" % (
            ctx.plugin_url,
            action,
            str(group_id),
        )

        item = xbmcgui.ListItem(group_title, offscreen=True)
        item.setInfo("video", {"title": group_title, "sorttitle": group_title.lower()})

        if archive == "true":
            item.setArt(
                {
                    "poster": tv_poster,
                    "thumb": thumb_browse,
                    "fanart": os.path.join(fanart_path, "archive_01.jpg"),
                }
            )
        else:
            item.setArt(
                {
                    "poster": tv_poster,
                    "thumb": thumb_browse,
                    "fanart": os.path.join(fanart_path, "live_02.jpg"),
                }
            )

        xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    xbmcplugin.setContent(ctx.handle, "files")
    xbmcplugin.addSortMethod(ctx.handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(ctx.handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    viewmode = kodi_helpers.get_setting(ctx.settings, "viewmode", default="0")
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=True)


def get_channels_list(ctx, params):
    """List channels for a given group with EPG data.

    Args:
        ctx: AddonContext instance.
        params: Router parameters dict (expects group_id, favorites, action).
    """
    import xbmcgui
    import xbmcplugin

    group_id = params.get("group_id", "")
    favorites = params.get("favorites", "0")
    action = params.get("action", "live")
    get_txt = kodi_helpers.get_localized

    # Verify credentials
    status = auth.check_credentials(ctx, False)
    if status != "true":
        try:
            err_msg = "%s: %s" % (get_txt(ctx.settings, 30019), status)
        except (TypeError, ValueError):
            err_msg = get_txt(ctx.settings, 30018)
        xbmcgui.Dialog().ok("Cbilling", err_msg)
        return False

    # Get channel data from adapter
    channels = _get_channels_data(ctx, group_id, favorites)

    if not channels:
        kodi_helpers.show_notification(get_txt(ctx.settings, 30040), "", 3000)
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    # Sort channels: favorites first, then by sort order and name
    with contextlib.suppress(KeyError, TypeError):
        channels = sorted(channels, reverse=False, key=lambda x: (-x["fav"], x.get("sort", 0), x["name"]))

    # Load EPG data for channels (SQLite cache → HTTP fallback)
    if action != "archive":
        _load_epg_for_channels(ctx, channels)

    # Build directory listing
    addon_name = kodi_helpers.get_setting(ctx.settings, "addon_name", default="Cbilling")

    dialog = xbmcgui.DialogProgress()
    dialog.create(addon_name, get_txt(ctx.settings, 30041))

    total_items = len(channels)

    for idx, channel in enumerate(channels):
        dialog.update(int((idx + 1) * 100 / total_items))
        if dialog.iscanceled():
            break

        channel_id = channel.get("id", "")
        channel_name = channel.get("name", "")

        # Get EPG info from pre-loaded data
        cur_epg = channel.get("cur_playing", "")
        short_epg = channel.get("short_epg", [])

        # Build EPG plot for info panel
        plot_desc = ""
        if action == "live" and short_epg:
            import time as time_mod

            plot_desc = build_epg_plot(
                short_epg=short_epg,
                now_ts=int(time_mod.time()),
                label_now=kodi_helpers.get_localized(ctx.settings, 30156),
                label_next=kodi_helpers.get_localized(ctx.settings, 30157),
                label_elapsed=kodi_helpers.get_localized(ctx.settings, 30159),
                label_starts_in=kodi_helpers.get_localized(ctx.settings, 30160),
            )

        # Create list item
        item = xbmcgui.ListItem(channel_name, offscreen=True)
        if cur_epg:
            item.setLabel2(cur_epg)

        # Set artwork
        logo = channel.get("logo", "")
        fanart_live = os.path.join(ctx.addon_dir, "fanart", "live_02.jpg")
        thumb_play = os.path.join(ctx.addon_dir, "resources", "thumb_play.png")
        if logo:
            item.setArt({"thumb": logo, "icon": logo, "fanart": fanart_live})
        else:
            item.setArt({"thumb": thumb_play, "icon": thumb_play, "fanart": fanart_live})
        item.setInfo("video", {
            "title": channel_name,
            "sorttitle": channel_name.lower(),
            "Plot": plot_desc,
        })

        # Build URL with stream command and encoded name
        import base64
        import re
        from urllib.parse import quote as url_quote

        channel_cmd = channel.get("cmd", "")
        channel_has_archive = channel.get("tv_archive_type") == "flussonic_dvr"
        name_b64 = re.sub(
            "=", "",
            base64.urlsafe_b64encode(channel_name.encode("utf-8")).decode("utf-8"),
        )
        url = "%s?mode=play_live_channel&play_cmd=%s&name=%s&channel_id=%s" % (
            ctx.plugin_url,
            url_quote(channel_cmd),
            name_b64,
            channel_id,
        )

        # Context menu
        context_menu = []

        # EPG show
        context_menu.append((
            "[B]%s[/B]" % get_txt(ctx.settings, 30119),
            "RunPlugin(%s?mode=epg_show&channel_id=%s&channel_title=%s)"
            % (ctx.plugin_url, channel_id, url_quote(channel_name.encode("utf-8"), safe="")),
        ))

        # Watch from start (if channel has archive and we have EPG start timestamp)
        if channel_has_archive and short_epg:
            epg_start_ts = short_epg[0].get("start_timestamp", 0) if short_epg else 0
            if epg_start_ts:
                context_menu.append((
                    get_txt(ctx.settings, 30161),
                    "RunPlugin(%s?mode=play_live_event_from_start&play_cmd=%s&name=%s&ts=%s)"
                    % (ctx.plugin_url, url_quote(channel_cmd), name_b64, str(epg_start_ts)),
                ))

        # Refresh
        context_menu.append((
            "%s" % get_txt(ctx.settings, 30124),
            "Container.Refresh",
        ))

        # Info (live mode)
        if action == "live":
            context_menu.append((
                get_txt(ctx.settings, 30045),
                "Action(Info)",
            ))

        # Favorites add/remove
        if favorites == "1":
            context_menu.append((
                get_txt(ctx.settings, 30046),
                "RunPlugin(%s?mode=itv_fav_add_remove&channel_id=%s&action=remove)"
                % (ctx.plugin_url, channel_id),
            ))
        else:
            context_menu.append((
                get_txt(ctx.settings, 30047),
                "RunPlugin(%s?mode=itv_fav_add_remove&channel_id=%s&action=add)"
                % (ctx.plugin_url, channel_id),
            ))

        # Stream servers
        context_menu.append((
            "%s" % get_txt(ctx.settings, 30128),
            "RunPlugin(%s?mode=get_stream_servers)" % ctx.plugin_url,
        ))

        item.addContextMenuItems(items=context_menu, replaceItems=True)
        item.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(ctx.handle, url, item, False)

    dialog.close()

    xbmcplugin.addSortMethod(ctx.handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(ctx.handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)
    return None


def _get_channels_data(ctx, group_id, favorites):
    """Fetch channel data from adapter with favorites applied.

    Args:
        ctx: AddonContext instance.
        group_id: Genre/group ID or "*" for all.
        favorites: "1" to filter favorites only, "0" for all.

    Returns:
        List of channel dicts or empty list on error.
    """
    from resources.lib import favorites as fav_mod

    fav_path = os.path.join(ctx.user_data_dir, "favorites.json")
    fav_ids = fav_mod.load(fav_path)

    try:
        if group_id == "*":
            if favorites == "1":
                all_channels = ctx.adapter.get_all_channels()
                channels = ctx.adapter.get_favorite_channels(all_channels, fav_ids)
            else:
                channels = ctx.adapter.get_all_channels()
                ctx.adapter.apply_favorites(channels, fav_ids)
        else:
            channels = ctx.adapter.get_channels_by_genre(group_id)
            ctx.adapter.apply_favorites(channels, fav_ids)
    except Exception as exc:
        kodi_helpers.debug_log("Failed to get channels: %s" % str(exc))
        return []

    return channels


def _load_epg_for_channels(ctx, channels):
    """Load current EPG for channels from SQLite cache or HTTP API.

    Fills channel["cur_playing"], channel["cur_playing_descr"],
    channel["short_epg"] for each channel.

    Priority: 1) SQLite cache, 2) HTTP API via get_short_epg (parallel).
    """
    import time as time_mod
    from concurrent.futures import ThreadPoolExecutor

    now_ts = int(time_mod.time())
    aliases_need_http = []

    # Try SQLite cache first
    epg_db_path = os.path.join(ctx.user_data_dir, "epg.db")
    if os.path.exists(epg_db_path):
        try:
            from resources.lib.epg_db import db_connection

            with db_connection(epg_db_path) as (_conn, cursor):
                # Check if epg table exists
                cursor.execute(
                    "SELECT count(name) FROM sqlite_master WHERE type = ? AND name = ?",
                    ("table", "epg"),
                )
                if cursor.fetchone()[0] == 1:
                    sql = (
                        "SELECT epg_json FROM epg WHERE ch_id = ? "
                        "AND stop_timestamp > ? ORDER BY stop_timestamp ASC LIMIT 1"
                    )
                    for channel in channels:
                        alias = channel.get("id", "")
                        if not alias:
                            continue
                        try:
                            cursor.execute(sql, (alias, now_ts))
                            row = cursor.fetchone()
                            if row:
                                import json

                                epg_entry = json.loads(row[0])
                                t_time = ctx.adapter._ts_to_local_str(
                                    epg_entry.get("start_timestamp", "")
                                ) if epg_entry.get("start_timestamp") else epg_entry.get("t_time", "")
                                name = epg_entry.get("name", "")
                                descr = epg_entry.get("descr", "")
                                channel["cur_playing"] = ("%s %s" % (t_time, name)).strip()
                                channel["cur_playing_descr"] = descr
                                channel["short_epg"] = [epg_entry]
                            else:
                                aliases_need_http.append(channel)
                        except Exception:
                            aliases_need_http.append(channel)
                else:
                    aliases_need_http = list(channels)
        except Exception:
            aliases_need_http = list(channels)
    else:
        aliases_need_http = list(channels)

    # For channels not in cache — load via HTTP
    if aliases_need_http:
        epg_size = 2 if kodi_helpers.get_setting(ctx.settings, "epg_in_channel_list", default="false") == "true" else 1

        def fetch_epg(channel):
            alias = channel.get("id", "")
            if not alias:
                return
            try:
                epg_data = ctx.adapter.get_short_epg(alias, size=epg_size)
                if epg_data and len(epg_data) > 0:
                    entry = epg_data[0]
                    t_time = entry.get("t_time", "")
                    name = entry.get("name", "")
                    descr = entry.get("descr", "")
                    channel["cur_playing"] = ("%s %s" % (t_time, name)).strip()
                    channel["cur_playing_descr"] = descr
                    channel["short_epg"] = epg_data
                else:
                    channel["cur_playing"] = ""
            except Exception:
                channel["cur_playing"] = ""

        with ThreadPoolExecutor(max_workers=8) as executor:
            executor.map(fetch_epg, aliases_need_http)


def _get_epg_cache_hours(ctx):
    """Read EPG cache hours from settings with fallback."""
    try:
        hours = int(ctx.settings.getSetting("epg_cache_hours"))
    except (ValueError, TypeError):
        hours = 24
    return hours
