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

    # Load EPG data from cache if available
    if action != "archive":
        aliases = [ch.get("id", "") for ch in channels if ch.get("id")]
        epg_map = epg_db.get_current_epg(ctx, aliases)
    else:
        epg_map = {}

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

        # Get EPG info for this channel
        cur_epg = ""
        epg_entry = epg_map.get(channel_id, {})
        if epg_entry:
            t_time = epg_entry.get("t_time", "")
            epg_name = epg_entry.get("name", "")
            if t_time or epg_name:
                cur_epg = ("%s %s" % (t_time, epg_name)).strip()

        # Fallback to cur_playing from streams data
        if not cur_epg:
            cur_epg = channel.get("cur_playing", "")

        # Create list item
        item = xbmcgui.ListItem(channel_name, offscreen=True)
        if cur_epg:
            item.setLabel2(cur_epg)

        # Set artwork
        logo = channel.get("logo", "")
        item.setArt({"thumb": logo, "icon": logo})
        item.setInfo("video", {"title": channel_name})

        # Build URL
        url = "%s?mode=play_live_channel&channel_id=%s&group_id=%s" % (
            ctx.plugin_url,
            channel_id,
            group_id,
        )

        item.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(ctx.handle, url, item, False)

    dialog.close()

    xbmcplugin.setContent(ctx.handle, "videos")
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


def _get_epg_cache_hours(ctx):
    """Read EPG cache hours from settings with fallback."""
    try:
        hours = int(ctx.settings.getSetting("epg_cache_hours"))
    except (ValueError, TypeError):
        hours = 24
    return hours
