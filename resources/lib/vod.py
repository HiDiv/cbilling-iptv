# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""VOD (Video on Demand) navigation, search, and playback."""

import os
from typing import TYPE_CHECKING
from urllib.parse import quote as url_quote
from urllib.parse import unquote as url_unquote

from resources.lib import kodi_helpers
from resources.lib.router import get_param

if TYPE_CHECKING:
    from resources.lib.context import AddonContext

# Adult content unlock code
_XXX_CODE = "GIMMESOMEXXX"


def _get_txt(ctx: "AddonContext", string_id: int) -> str:
    """Get localized string via context settings."""
    return kodi_helpers.get_localized(ctx.settings, string_id)


def _is_xxx_enabled(ctx: "AddonContext") -> bool:
    """Check whether adult content filter is unlocked."""
    return str(kodi_helpers.get_setting(ctx.settings, "xxx_code")) == _XXX_CODE


def _get_viewmode(ctx: "AddonContext") -> str:
    """Get configured view mode, defaulting to '0' (auto)."""
    return kodi_helpers.get_setting(ctx.settings, "viewmode", default="0")


def _apply_viewmode(ctx: "AddonContext") -> None:
    """Apply configured view mode if set."""
    import xbmc

    viewmode = _get_viewmode(ctx)
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)


def _art_paths(ctx: "AddonContext") -> tuple:
    """Return (vod_poster, thumb_browse, fanart_path) resource paths."""
    media_path = os.path.join(ctx.addon_dir, "resources", "media")
    fanart_path = os.path.join(ctx.addon_dir, "resources", "fanart")
    vod_poster = os.path.join(media_path, "vod_poster.png")
    thumb_browse = os.path.join(media_path, "browse.png")
    return vod_poster, thumb_browse, fanart_path


# ---------------------------------------------------------------------------
# Router dispatch handlers — signature: (ctx, params) -> None
# ---------------------------------------------------------------------------


def start(ctx: "AddonContext", params: dict) -> None:
    """VOD main menu: categories, search, watch history."""
    import xbmcgui
    import xbmcplugin

    vod_poster, thumb_browse, fanart_path = _art_paths(ctx)
    fanart_vod = os.path.join(fanart_path, "vod_03.jpg")

    # Categories
    name = "[COLOR white][B]%s[/B][/COLOR]" % _get_txt(ctx, 30067)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt({"poster": vod_poster, "thumb": thumb_browse, "fanart": fanart_vod})
    url = "%s?mode=vod_get_category" % ctx.plugin_url
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    # Search
    name = "[COLOR white][B]%s[/B][/COLOR]" % _get_txt(ctx, 30107)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt({"poster": vod_poster, "thumb": thumb_browse, "fanart": fanart_vod})
    url = "%s?mode=vod_search_page" % ctx.plugin_url
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    # Watch history
    name = "[COLOR white][B]%s[/B][/COLOR]" % _get_txt(ctx, 30143)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt({"poster": vod_poster, "thumb": thumb_browse, "fanart": fanart_vod})
    url = "%s?mode=vod_watch_history" % ctx.plugin_url
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, True)

    xbmcplugin.setContent(ctx.handle, "files")
    _apply_viewmode(ctx)
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)


def get_category(ctx: "AddonContext", params: dict) -> None:
    """List VOD categories from API."""
    import xbmcgui
    import xbmcplugin

    xxx_enabled = _is_xxx_enabled(ctx)
    vod_poster, thumb_browse, fanart_path = _art_paths(ctx)
    fanart_vod = os.path.join(fanart_path, "vod_03.jpg")

    try:
        info = ctx.api.get_vod_categories()
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
    except Exception as e:
        kodi_helpers.debug_log("[vod.get_category] Error: %s" % str(e))
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    if not info:
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    for category in info:
        cat_title = category.get("name", category.get("title", ""))
        cat_censored = int(category.get("adult", 0)) == 1

        if not xxx_enabled and cat_censored:
            continue

        item_name = "[COLOR white][B]%s[/B][/COLOR]" % cat_title
        url = "%s?mode=vod_get_category_genres&cat_id=%s&cat_alias=%s" % (
            ctx.plugin_url,
            category["id"],
            category.get("alias", ""),
        )
        item = xbmcgui.ListItem(item_name, offscreen=True)
        item.setArt({"poster": vod_poster, "thumb": thumb_browse, "fanart": fanart_vod})
        xbmcplugin.addDirectoryItem(ctx.handle, url, item, isFolder=True)

    xbmcplugin.setContent(ctx.handle, "files")
    _apply_viewmode(ctx)
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=True)


def get_category_genres(ctx: "AddonContext", params: dict) -> None:
    """List genres within a VOD category."""
    import xbmc
    import xbmcgui
    import xbmcplugin

    cat_id = get_param(params, "cat_id", default="*")

    vod_poster, thumb_browse, fanart_path = _art_paths(ctx)
    fanart_vod = os.path.join(fanart_path, "vod_03.jpg")

    try:
        info = ctx.api.get_vod_category_genres(cat_id)
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
    except Exception as e:
        kodi_helpers.debug_log("[vod.get_category_genres] Error: %s" % str(e))
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    if not info:
        # No genres — redirect directly to content list
        xbmc.executebuiltin(
            'Container.Update("%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=*&page_nr=1&sortby=added")'
            % (ctx.plugin_url, cat_id)
        )
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    # "All" option
    item_name = "[COLOR white][B]%s[/B][/COLOR]" % _get_txt(ctx, 30108)
    url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=*&page_nr=1&sortby=added" % (
        ctx.plugin_url,
        cat_id,
    )
    item = xbmcgui.ListItem(item_name, offscreen=True)
    item.setArt({"poster": vod_poster, "thumb": thumb_browse, "fanart": fanart_vod})
    xbmcplugin.addDirectoryItem(ctx.handle, url, item, isFolder=True)

    for genre in info:
        genre_title = genre.get("name", genre.get("title", ""))
        genre_id = genre.get("id", "")
        item_name = "[COLOR white][B]%s[/B][/COLOR]" % genre_title
        url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=%s&page_nr=1&sortby=added" % (
            ctx.plugin_url,
            cat_id,
            str(genre_id),
        )
        item = xbmcgui.ListItem(item_name, offscreen=True)
        item.setArt({"poster": vod_poster, "thumb": thumb_browse, "fanart": fanart_vod})
        xbmcplugin.addDirectoryItem(ctx.handle, url, item, isFolder=True)

    xbmcplugin.setContent(ctx.handle, "files")
    _apply_viewmode(ctx)
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=True)


def get_ordered_list(ctx: "AddonContext", params: dict) -> None:
    """Paginated movie list with sort/filter support."""
    import xbmcgui
    import xbmcplugin

    from resources.lib.vod_cache import vod_cache_get_multiple, vod_cache_set_multiple

    cat_id = get_param(params, "cat_id", default="*")
    genre_id = get_param(params, "genre_id", default="*")
    page_nr = get_param(params, "page_nr", default=1, transform=int)
    sortby = get_param(params, "sortby", default="added")
    vod_search = get_param(params, "vod_search", default=None)
    vod_year = get_param(params, "vod_year", default=None)

    xxx_enabled = _is_xxx_enabled(ctx)
    vod_preload_enabled = kodi_helpers.get_setting(ctx.settings, "vod_preload_metadata") == "true"
    vod_poster, thumb_browse, fanart_path = _art_paths(ctx)
    fanart_vod = os.path.join(fanart_path, "vod_03.jpg")

    movie_data = []
    api_meta = {}

    dialog = xbmcgui.DialogProgress()
    dialog.create("Cbilling", "%s..." % _get_txt(ctx, 30068))

    try:
        if vod_search is not None:
            search_term = url_unquote(vod_search)
            raw_data = ctx.api.search_by_name(search_term, page=page_nr)
            kodi_helpers.debug_log('[vod.get_ordered_list] Search: "%s", page=%d' % (search_term, page_nr))
        elif vod_year is not None:
            year_val = url_unquote(vod_year)
            raw_data = ctx.api.filter_by_year(year_val, page=page_nr)
            kodi_helpers.debug_log("[vod.get_ordered_list] Year filter: %s, page=%d" % (year_val, page_nr))
        elif genre_id != "*" and genre_id != "0":
            raw_data = ctx.api.get_vod_by_genre(genre_id, page=page_nr)
            kodi_helpers.debug_log("[vod.get_ordered_list] Genre: genre_id=%s, page=%d" % (genre_id, page_nr))
        else:
            raw_data = ctx.api.get_vod_category_content(cat_id, page=page_nr)
            kodi_helpers.debug_log("[vod.get_ordered_list] Category: cat_id=%s, page=%d" % (cat_id, page_nr))

        if isinstance(raw_data, dict) and "data" in raw_data:
            movie_data = raw_data["data"]
            api_meta = raw_data.get("meta", {})
        elif isinstance(raw_data, list):
            movie_data = raw_data
        else:
            movie_data = []

        kodi_helpers.debug_log("[vod.get_ordered_list] Received %d items (page %d)" % (len(movie_data), page_nr))
    except Exception as e:
        kodi_helpers.debug_log("[vod.get_ordered_list] Fetch error: %s" % str(e))

    if not movie_data:
        dialog.close()
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    # Filter adult content
    if not xxx_enabled:
        movie_data = [m for m in movie_data if int(m.get("adult", 0)) != 1]

    # Preload metadata with cache
    if vod_preload_enabled and movie_data:
        movie_ids = [str(m.get("id")) for m in movie_data if m.get("id")]
        cached_data = vod_cache_get_multiple(movie_ids)
        missing_ids = [mid for mid in movie_ids if mid not in cached_data]

        if missing_ids:
            loaded = {}
            for idx, mid in enumerate(missing_ids):
                if dialog.iscanceled():
                    break
                dialog.update(
                    int((idx + 1) * 100 / len(missing_ids)),
                    "%s (%d/%d)..." % (_get_txt(ctx, 30068), idx + 1, len(missing_ids)),
                )
                try:
                    video_info = ctx.api.get_video(mid)
                    if isinstance(video_info, dict) and "data" in video_info:
                        loaded[mid] = video_info["data"]
                    elif video_info:
                        loaded[mid] = video_info
                except Exception as e:
                    kodi_helpers.debug_log("[vod.get_ordered_list] Preload error %s: %s" % (mid, str(e)))

            if loaded:
                vod_cache_set_multiple(loaded)
                cached_data.update(loaded)

    dialog.close()

    # Build directory items
    listing = []
    for movie in movie_data:
        movie_id = str(movie.get("id", "0"))
        title = movie.get("name", movie.get("title", ""))
        poster = movie.get("poster", "")
        year = movie.get("year", "")
        is_series = bool(movie.get("seasons")) or movie.get("type") == "series"

        label = "[COLOR white][B]%s[/B][/COLOR]" % title
        if year:
            label = "[COLOR white][B]%s[/B][/COLOR] [COLOR burlywood](%s)[/COLOR]" % (title, year)

        if is_series:
            url = "%s?mode=vod_get_seasons&movie_id=%s&movie_name=%s&poster_url=%s" % (
                ctx.plugin_url,
                movie_id,
                url_quote(title.encode("utf-8") if isinstance(title, str) else title, safe=""),
                url_quote(poster, safe=""),
            )
            is_folder = True
        else:
            url = "%s?mode=vod_play_movie&movie_id=%s&season_id=0&episode_id=0&movie_name=%s" % (
                ctx.plugin_url,
                movie_id,
                url_quote(title.encode("utf-8") if isinstance(title, str) else title, safe=""),
            )
            is_folder = False

        item = xbmcgui.ListItem(label, offscreen=True)
        item.setArt({"poster": poster, "thumb": poster or thumb_browse, "fanart": fanart_vod})
        item.setInfo(type="video", infoLabels={"title": title, "year": year, "mediatype": "movie"})
        if not is_folder:
            item.setProperty("IsPlayable", "true")

        # Context menu
        context_menu = [
            (
                _get_txt(ctx, 30133),
                "RunPlugin(%s?mode=show_vod_info&movie_id=%s&movie_name=%s)"
                % (ctx.plugin_url, movie_id, url_quote(title.encode("utf-8"), safe="")),
            ),
            (
                _get_txt(ctx, 30128),
                "RunPlugin(%s?mode=get_stream_servers)" % ctx.plugin_url,
            ),
        ]
        item.addContextMenuItems(items=context_menu, replaceItems=True)
        listing.append((url, item, is_folder))

    xbmcplugin.addDirectoryItems(ctx.handle, listing, totalItems=len(listing))

    # Pagination — next page
    total_pages = 1
    if api_meta:
        try:
            total_items = int(api_meta.get("total", api_meta.get("total_items", 0)))
            per_page = int(api_meta.get("per_page", api_meta.get("max_page_items", 20)))
            if per_page > 0:
                total_pages = (total_items + per_page - 1) // per_page
        except (ValueError, TypeError):
            total_pages = 1

    if page_nr < total_pages:
        next_label = "[COLOR burlywood][B]%s >>>[/B][/COLOR]" % _get_txt(ctx, 30069)
        # Build next page URL preserving current filter
        next_url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=%s&page_nr=%d&sortby=%s" % (
            ctx.plugin_url,
            cat_id,
            genre_id,
            page_nr + 1,
            sortby,
        )
        if vod_search is not None:
            next_url += "&vod_search=%s" % url_quote(vod_search, safe="")
        if vod_year is not None:
            next_url += "&vod_year=%s" % url_quote(vod_year, safe="")

        next_item = xbmcgui.ListItem(next_label, offscreen=True)
        next_item.setArt({"poster": vod_poster, "thumb": thumb_browse, "fanart": fanart_vod})
        xbmcplugin.addDirectoryItem(ctx.handle, next_url, next_item, isFolder=True)

    xbmcplugin.setContent(ctx.handle, "movies")
    _apply_viewmode(ctx)
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=True)


def get_seasons(ctx: "AddonContext", params: dict) -> None:
    """List seasons for a series."""
    import xbmcgui
    import xbmcplugin

    movie_id = get_param(params, "movie_id", default="0")
    movie_name = url_unquote(get_param(params, "movie_name", default="-"))
    poster_url = url_unquote(get_param(params, "poster_url", default=""))

    _vod_poster, thumb_browse, _fanart_path = _art_paths(ctx)

    kodi_helpers.debug_log("[vod.get_seasons] movie_id=%s, name=%s" % (movie_id, movie_name))

    try:
        info = ctx.api.get_video(movie_id)
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
    except Exception as e:
        kodi_helpers.debug_log("[vod.get_seasons] Error: %s" % str(e))
        kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30079), 3000)
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    if not info:
        kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30079), 3000)
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    seasons = info.get("seasons", []) if isinstance(info, dict) else info
    if not isinstance(seasons, list):
        seasons = [info]

    # Filter valid seasons
    valid_seasons = [s for s in seasons if s.get("name") or s.get("title") or s.get("number")]

    kodi_helpers.debug_log("[vod.get_seasons] Valid seasons: %d" % len(valid_seasons))

    # Single season — redirect to episodes
    if len(valid_seasons) == 1:
        season_data = valid_seasons[0]
        season_id = str(season_data.get("id", "0"))
        season_name = season_data.get("name", season_data.get("title", ""))
        if not season_name and season_data.get("number"):
            season_name = "%s %s" % (_get_txt(ctx, 30131), season_data["number"])

        kodi_helpers.debug_log("[vod.get_seasons] Single season, redirecting to episodes")
        # Call get_episodes directly with synthesized params
        ep_params = {
            "movie_id": movie_id,
            "season_id": season_id,
            "movie_name": url_quote(movie_name.encode("utf-8"), safe=""),
            "season_name": url_quote(season_name.encode("utf-8"), safe=""),
            "poster_url": url_quote(poster_url, safe=""),
        }
        get_episodes(ctx, ep_params)
        return

    # Multiple seasons
    listing = []
    for data in valid_seasons:
        season_name = data.get("name", data.get("title", ""))
        season_id = str(data.get("id", "0"))
        season_number = data.get("number", "")
        episodes_count = data.get("count", data.get("season_series", data.get("series_count", "")))

        if not season_name and season_number:
            season_name = "%s %s" % (_get_txt(ctx, 30131), season_number)

        plot_desc = "[B]%s[/B][CR]%s[CR]%s: %s" % (
            movie_name,
            season_name,
            _get_txt(ctx, 30077),
            str(episodes_count),
        )

        item_name = "[COLOR burlywood][B]%s[/B][/COLOR]" % season_name
        list_item = xbmcgui.ListItem(item_name, offscreen=True)
        list_item.setInfo(
            type="video",
            infoLabels={
                "title": season_name,
                "mediatype": "season",
                "Episode": str(episodes_count),
                "plot": plot_desc,
            },
        )
        list_item.setArt({"poster": poster_url, "thumb": thumb_browse, "fanart": poster_url})
        list_item.setProperty("IsPlayable", "false")

        url = "%s?mode=vod_get_episodes&movie_id=%s&season_id=%s&movie_name=%s&season_name=%s&poster_url=%s" % (
            ctx.plugin_url,
            movie_id,
            season_id,
            url_quote(movie_name.encode("utf-8"), safe=""),
            url_quote(season_name.encode("utf-8"), safe=""),
            url_quote(poster_url, safe=""),
        )

        # Context menu
        context_menu = [
            (
                _get_txt(ctx, 30133),
                "RunPlugin(%s?mode=show_vod_info&movie_id=%s&movie_name=%s)"
                % (ctx.plugin_url, movie_id, url_quote(movie_name.encode("utf-8"), safe="")),
            ),
            (
                _get_txt(ctx, 30128),
                "RunPlugin(%s?mode=get_stream_servers)" % ctx.plugin_url,
            ),
        ]
        list_item.addContextMenuItems(items=context_menu, replaceItems=True)
        listing.append((url, list_item, True))

    xbmcplugin.addDirectoryItems(ctx.handle, listing, totalItems=len(listing))
    xbmcplugin.setContent(ctx.handle, "seasons")
    _apply_viewmode(ctx)
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)


def get_episodes(ctx: "AddonContext", params: dict) -> None:
    """List episodes for a season."""
    import xbmcgui
    import xbmcplugin

    movie_id = get_param(params, "movie_id", default="0")
    season_id = get_param(params, "season_id", default="0")
    movie_name = url_unquote(get_param(params, "movie_name", default="-"))
    season_name = url_unquote(get_param(params, "season_name", default="-"))
    poster_url = url_unquote(get_param(params, "poster_url", default=""))

    _vod_poster, _thumb_browse, _fanart_path = _art_paths(ctx)
    thumb_play = os.path.join(ctx.addon_dir, "resources", "play.png")

    kodi_helpers.debug_log("[vod.get_episodes] movie_id=%s, season_id=%s" % (movie_id, season_id))

    try:
        info = ctx.api.get_season(season_id)
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
    except Exception as e:
        kodi_helpers.debug_log("[vod.get_episodes] Error: %s" % str(e))
        kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30079), 3000)
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    if not info or not isinstance(info, list):
        kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30079), 3000)
        xbmcplugin.endOfDirectory(ctx.handle)
        return

    listing = []
    for episode in info:
        ep_id = str(episode.get("id", "0"))
        ep_number = episode.get("number", "")
        ep_name = episode.get("name", episode.get("title", ""))

        if not ep_name and ep_number:
            ep_name = "%s %s" % (_get_txt(ctx, 30149), ep_number)
        elif not ep_name:
            ep_name = "Episode %s" % ep_id

        label = "[COLOR white]%s[/COLOR]" % ep_name
        if ep_number:
            label = "[COLOR burlywood]%s.[/COLOR] [COLOR white]%s[/COLOR]" % (ep_number, ep_name)

        url = ("%s?mode=vod_play_movie&movie_id=%s&season_id=%s&episode_id=%s&movie_name=%s&season_name=%s") % (
            ctx.plugin_url,
            movie_id,
            season_id,
            ep_id,
            url_quote(movie_name.encode("utf-8"), safe=""),
            url_quote(season_name.encode("utf-8"), safe=""),
        )

        list_item = xbmcgui.ListItem(label, offscreen=True)
        list_item.setInfo(
            type="video",
            infoLabels={
                "title": ep_name,
                "mediatype": "episode",
                "Episode": str(ep_number),
            },
        )
        list_item.setArt({"poster": poster_url, "thumb": thumb_play, "fanart": poster_url})
        list_item.setProperty("IsPlayable", "true")

        # Context menu
        context_menu = [
            (
                _get_txt(ctx, 30133),
                "RunPlugin(%s?mode=show_vod_info&movie_id=%s&movie_name=%s)"
                % (ctx.plugin_url, movie_id, url_quote(movie_name.encode("utf-8"), safe="")),
            ),
            (
                _get_txt(ctx, 30128),
                "RunPlugin(%s?mode=get_stream_servers)" % ctx.plugin_url,
            ),
        ]
        list_item.addContextMenuItems(items=context_menu, replaceItems=True)
        listing.append((url, list_item, False))

    xbmcplugin.addDirectoryItems(ctx.handle, listing, totalItems=len(listing))
    xbmcplugin.setContent(ctx.handle, "episodes")
    _apply_viewmode(ctx)
    xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)


def play_movie(ctx: "AddonContext", params: dict) -> None:
    """Resolve stream URL and play a VOD item."""
    import re

    import xbmcgui
    import xbmcplugin

    from resources.lib import watch_history

    movie_id = get_param(params, "movie_id", default="0")
    season_id = get_param(params, "season_id", default="0")
    episode_id = get_param(params, "episode_id", default="0")
    movie_name = url_unquote(get_param(params, "movie_name", default="-"))
    season_name = url_unquote(get_param(params, "season_name", default="-"))

    kodi_helpers.debug_log(
        "[vod.play_movie] movie_id=%s, season_id=%s, episode_id=%s" % (movie_id, season_id, episode_id)
    )

    stream_url = None
    video_metadata = None

    try:
        if int(season_id) > 0 and int(episode_id) > 0:
            # Episode playback
            info = ctx.api.get_season(season_id)
            if isinstance(info, dict) and "data" in info:
                info = info["data"]

            if isinstance(info, list):
                for ep in info:
                    if str(ep.get("id", "")) == str(episode_id):
                        files = ep.get("files", [])
                        if files and isinstance(files, list) and len(files) > 0:
                            stream_url = files[0].get("url", "")
                        if not stream_url:
                            stream_url = ep.get("url", ep.get("cmd", ep.get("file", "")))
                        break
                # Fallback to first episode
                if not stream_url and info:
                    ep = info[0]
                    files = ep.get("files", [])
                    if files and isinstance(files, list) and len(files) > 0:
                        stream_url = files[0].get("url", "")
                    if not stream_url:
                        stream_url = ep.get("url", ep.get("cmd", ep.get("file", "")))

            # Get series metadata
            try:
                series_info = ctx.api.get_video(movie_id)
                if isinstance(series_info, dict) and "data" in series_info:
                    video_metadata = series_info["data"]
            except Exception as e:
                kodi_helpers.debug_log("[vod.play_movie] Metadata error: %s" % str(e))
        else:
            # Movie playback
            info = ctx.api.get_video(movie_id)
            if isinstance(info, dict) and "data" in info:
                video_metadata = info["data"]

            if isinstance(video_metadata, dict):
                files = video_metadata.get("files", [])
                if files and isinstance(files, list) and len(files) > 0:
                    stream_url = files[0].get("url", "")
                if not stream_url:
                    stream_url = video_metadata.get("url", video_metadata.get("cmd", video_metadata.get("file", "")))
            elif isinstance(video_metadata, list) and video_metadata:
                stream_url = video_metadata[0].get(
                    "url", video_metadata[0].get("cmd", video_metadata[0].get("file", ""))
                )
    except Exception as e:
        kodi_helpers.debug_log("[vod.play_movie] Error: %s" % str(e))

    if not stream_url:
        kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30079), 3000)
        return

    # Prepend server URL if relative
    if not stream_url.startswith("http"):
        try:
            auth_info = ctx.api.get_auth_info()
            server = auth_info.get("server", "")
            ssl = auth_info.get("ssl", False)
            if server:
                protocol = "https" if ssl else "http"
                stream_url = "%s://%s%s" % (protocol, server, stream_url)
        except Exception as e:
            kodi_helpers.debug_log("[vod.play_movie] Server URL error: %s" % str(e))

    # Clean ffmpeg prefix
    if stream_url.startswith("ffmpeg ") or stream_url.startswith("ffmpeg%20"):
        regex = re.search(r".*(http://.*)", stream_url)
        if regex:
            stream_url = regex.group(1)

    # Add auth token if missing
    if "token=" not in stream_url:
        try:
            auth_info = ctx.api.get_auth_info()
            private_token = auth_info.get("private_token", "")
            if private_token:
                stream_url += "?token=%s" % private_token
        except Exception:
            pass

    kodi_helpers.debug_log("[vod.play_movie] Streaming: %s" % stream_url[:100])

    # Save to watch history
    try:
        history_path = os.path.join(ctx.user_data_dir, watch_history.HISTORY_FILENAME)
        history_poster = ""
        history_type = "movie"
        if isinstance(video_metadata, dict):
            history_poster = video_metadata.get("poster", "")
            if int(episode_id) > 0:
                history_type = "episode"

        entry = {
            "movie_id": movie_id,
            "season_id": season_id,
            "episode_id": episode_id,
            "title": movie_name,
            "season_name": season_name,
            "poster": history_poster,
            "content_type": history_type,
        }
        watch_history.add_entry(history_path, entry)
    except Exception as e:
        kodi_helpers.debug_log("[vod.play_movie] History error: %s" % str(e))

    # Create ListItem and resolve
    item = xbmcgui.ListItem(path=stream_url, offscreen=True)

    if isinstance(video_metadata, dict):
        item.setInfo(
            type="video",
            infoLabels={
                "title": video_metadata.get("name", movie_name),
                "plot": video_metadata.get("description", video_metadata.get("descr", "")),
                "year": video_metadata.get("year", ""),
                "director": video_metadata.get("director", ""),
                "mediatype": "movie",
            },
        )
        poster = video_metadata.get("poster", "")
        if poster:
            item.setArt({"poster": poster, "thumb": poster})

    xbmcplugin.setResolvedUrl(ctx.handle, True, item)


def search_page(ctx: "AddonContext", params: dict) -> None:
    """VOD search interface — prompts user for search type and query."""
    import xbmcgui
    import xbmcplugin

    search_list = [_get_txt(ctx, 30109), _get_txt(ctx, 30110)]
    search_by = ["vod_search", "vod_year"]

    dialog = xbmcgui.Dialog()
    ret = dialog.select(_get_txt(ctx, 30111), search_list)

    if ret is None or ret < 0:
        xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)
        return

    if search_by[ret] == "vod_year":
        search_word = dialog.input(_get_txt(ctx, 30112), type=xbmcgui.INPUT_NUMERIC)
    else:
        search_word = dialog.input(_get_txt(ctx, 30113), type=xbmcgui.INPUT_ALPHANUM)

    if not search_word:
        xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)
        return

    # Validate input
    try:
        if search_by[ret] == "vod_year":
            if int(search_word) < 1900 or int(search_word) > 2050:
                kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30114), 3000)
                xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)
                return
        elif len(search_word) < 3:
            kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30115), 3000)
            xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)
            return
    except (ValueError, TypeError):
        kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30116), 3000)
        xbmcplugin.endOfDirectory(ctx.handle, cacheToDisc=False)
        return

    search_word_encoded = url_quote(search_word, safe="")

    kodi_helpers.debug_log("[vod.search_page] search_by=%s, word=%s" % (search_by[ret], search_word))

    # Call get_ordered_list directly
    search_params = {
        "cat_id": "*",
        "genre_id": "*",
        "page_nr": "1",
        "sortby": "name",
        search_by[ret]: search_word_encoded,
    }
    get_ordered_list(ctx, search_params)


def show_info(ctx: "AddonContext", params: dict) -> None:
    """Show detailed movie/series info dialog."""
    import xbmcgui

    from resources.lib.vod_cache import vod_cache_get, vod_cache_set

    movie_id = get_param(params, "movie_id", default="0")
    movie_name = url_unquote(get_param(params, "movie_name", default="-"))

    kodi_helpers.debug_log("[vod.show_info] movie_id=%s" % movie_id)

    # Try cache first
    video_data = vod_cache_get(movie_id)

    if not video_data:
        progress = xbmcgui.DialogProgress()
        progress.create(_get_txt(ctx, 30000), _get_txt(ctx, 30081))

        try:
            video_info = ctx.api.get_video(movie_id)
            progress.close()

            if not video_info or not isinstance(video_info, dict):
                kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30079), 3000)
                return

            video_data = video_info.get("data", video_info)
            vod_cache_set(movie_id, video_data)
        except Exception as e:
            progress.close()
            kodi_helpers.debug_log("[vod.show_info] Error: %s" % str(e))
            kodi_helpers.show_notification("Cbilling", _get_txt(ctx, 30079), 3000)
            return

    # Extract metadata
    title = video_data.get("name", movie_name)
    original_title = video_data.get("original_name", "")
    description = video_data.get("description", video_data.get("descr", ""))
    year = video_data.get("year", "")
    rating = video_data.get("rating", video_data.get("rating_imdb", ""))
    director = video_data.get("director", "")
    actors = video_data.get("actors", "")
    country = video_data.get("country", "")
    duration = video_data.get("time", video_data.get("duration", ""))

    genres = video_data.get("genres", [])
    if isinstance(genres, list):
        genres_str = ", ".join([g.get("title", "") for g in genres if isinstance(g, dict) and g.get("title")])
    else:
        genres_str = str(genres)

    # Build info text
    info_lines = []
    info_lines.append("[B]%s[/B]" % title)
    if original_title and original_title != title:
        info_lines.append("[I]%s[/I]" % original_title)
    info_lines.append("")

    if year:
        info_lines.append("[B]%s:[/B] %s" % (_get_txt(ctx, 30135), year))
    if rating:
        info_lines.append("[B]%s:[/B] %s" % (_get_txt(ctx, 30136), rating))
    if duration:
        info_lines.append("[B]%s:[/B] %s %s" % (_get_txt(ctx, 30137), duration, _get_txt(ctx, 30138)))
    if country:
        info_lines.append("[B]%s:[/B] %s" % (_get_txt(ctx, 30139), country))
    if genres_str:
        info_lines.append("[B]%s:[/B] %s" % (_get_txt(ctx, 30140), genres_str))

    info_lines.append("")

    if director:
        info_lines.append("[B]%s:[/B] %s" % (_get_txt(ctx, 30141), director))
    if actors:
        info_lines.append("[B]%s:[/B] %s" % (_get_txt(ctx, 30142), actors))

    if description:
        info_lines.append("")
        info_lines.append(description)

    dialog = xbmcgui.Dialog()
    dialog.textviewer(title, "\n".join(info_lines))


def cache_manage(ctx: "AddonContext", params: dict) -> None:
    """VOD cache management UI."""
    import xbmcgui

    from resources.lib.vod_cache import vod_cache_clear_all, vod_cache_clear_old, vod_cache_get_stats

    try:
        stats = vod_cache_get_stats()
        options = ["Cache statistics", "Clear old cache entries", "Clear all cache", "Cancel"]

        dialog = xbmcgui.Dialog()
        ret = dialog.select("VOD Cache Management", options)

        if ret == 0:
            msg = "Total entries: %d\nSize: %.2f MB\nOldest: %s\nNewest: %s" % (
                stats["total"],
                stats["size_mb"],
                stats["oldest"] or "N/A",
                stats["newest"] or "N/A",
            )
            dialog.ok("VOD Cache Statistics", msg)
        elif ret == 1:
            ttl_days = kodi_helpers.get_setting(ctx.settings, "vod_cache_ttl_days", default="7", cast=int)
            count = vod_cache_clear_old(ttl_days)
            kodi_helpers.show_notification("Cbilling", "Cleared %d old entries (>%d days)" % (count, ttl_days), 3000)
        elif ret == 2:
            if dialog.yesno("Confirm", "Clear all VOD cache?"):
                vod_cache_clear_all()
                kodi_helpers.show_notification("Cbilling", "All cache cleared", 2000)
    except Exception as e:
        kodi_helpers.debug_log("[vod.cache_manage] Error: %s" % str(e))
        kodi_helpers.show_notification("Cbilling", "Error managing cache", 2000)


def debug(ctx: "AddonContext", params: dict) -> None:
    """Debug VOD playback — log stream info."""
    import json

    play_cmd = get_param(params, "play_cmd", default="")

    kodi_helpers.debug_log("[vod.debug] play_cmd=%s" % play_cmd)

    try:
        # Attempt to get video info for debugging
        movie_id = get_param(params, "movie_id", default="0")
        if movie_id != "0":
            info = ctx.api.get_video(movie_id)
            kodi_helpers.debug_log("[vod.debug] Video info: %s" % json.dumps(info, indent=2))
    except Exception as e:
        kodi_helpers.debug_log("[vod.debug] Error: %s" % str(e))
