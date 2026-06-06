#!/usr/bin/python
# SPDX-FileCopyrightText: Thamerlan
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

from resources.lib import body as cbBody

# Parsing and defining addon routing parameters
input_params = cbBody.get_params()
try:
    mode = input_params["mode"]
except:
    mode = None
try:
    group_id = input_params["group_id"]
except:
    group_id = ""
try:
    cat_id = input_params["cat_id"]
except:
    cat_id = "*"
try:
    page_nr = input_params["page_nr"]
except:
    page_nr = 1
try:
    play_cmd = input_params["play_cmd"]
except:
    play_cmd = ""
try:
    name = local_b64decode(input_params["name"])
except:
    name = ""
try:
    channel_title = input_params["channel_title"]
except:
    channel_title = ""
try:
    movie_name = input_params["movie_name"]
except:
    movie_name = "-"
try:
    season_name = input_params["season_name"]
except:
    season_name = "-"
try:
    archive = input_params["archive"]
except:
    archive = ""
try:
    channel_id = input_params["channel_id"]
except:
    channel_id = ""
try:
    depth = input_params["depth"]
except:
    depth = ""
try:
    date = input_params["date"]
except:
    date = ""
try:
    ts = input_params["ts"]
except:
    ts = 0
try:
    unixtime = input_params["unixtime"]
except:
    unixtime = ""
try:
    poster_url = input_params["poster_url"]
except:
    poster_url = ""
try:
    duration = input_params["duration"]
except:
    pass
try:
    favorites = input_params["favorites"]
except:
    favorites = "0"
try:
    action = input_params["action"]
except:
    action = None
try:
    cat_alias = input_params["cat_alias"]
except:
    cat_alias = None
try:
    genre_id = input_params["genre_id"]
except:
    genre_id = "*"
try:
    sortby = input_params["sortby"]
except:
    sortby = "top"
try:
    movie_id = input_params["movie_id"]
except:
    movie_id = "0"
try:
    season_id = input_params["season_id"]
except:
    season_id = "0"
try:
    episode_id = input_params["episode_id"]
except:
    episode_id = "0"
try:
    vod_search = input_params["vod_search"]
except:
    vod_search = None
try:
    vod_year = input_params["vod_year"]
except:
    vod_year = None
try:
    logo_png = input_params["logo_png"]
except:
    logo_png = None
try:
    focus_episode_id = input_params["focus_episode_id"]
except:
    focus_episode_id = "0"
try:
    direct = input_params["direct"]
except:
    direct = 0

# performing different actions based on requested mode
if mode == "CBILLING_start":
    cbBody.CBILLING_start()
elif mode == "show_vod_info":
    cbBody.show_vod_info(movie_id, movie_name)
elif mode == "vod_cache_manage":
    cbBody.vod_cache_manage()
elif mode == "channel_groups":
    cbBody.channel_groups(archive)
elif mode == "itv_fav_add_remove":
    cbBody.itv_fav_add_remove(channel_id, action)
elif mode == "get_channels_list":
    cbBody.get_channels_list(group_id, favorites, action)
elif mode == "play_live_channel":
    cbBody.play_live_channel(play_cmd, name, channel_id)
elif mode == "timepick_live_channel":
    cbBody.timepick_live_channel(play_cmd, name, date)
elif mode == "archive_channel_dates":
    cbBody.archive_channel_dates(channel_id, name, depth, play_cmd, logo_png)
elif mode == "epg_show":
    cbBody.epg_show(channel_id, channel_title)
elif mode == "get_stream_servers":
    cbBody.get_stream_servers()
elif mode == "archive_channel_epg":
    cbBody.archive_channel_epg(channel_id, date, name, play_cmd, logo_png, direct)
elif mode == "play_archive_channel":
    cbBody.play_archive_channel(play_cmd, unixtime, duration)
elif mode == "download_archive_record":
    cbBody.download_archive_record(play_cmd, unixtime, duration)
elif mode == "play_live_event_from_start":
    cbBody.play_live_event_from_start(play_cmd, name, ts)
elif mode == "cron_epg_init":
    cbBody.cron_epg_init()
elif mode == "vod_start":
    cbBody.vod_start()
elif mode == "vod_get_category":
    cbBody.vod_get_category()
elif mode == "vod_search_page":
    cbBody.vod_search_page()
elif mode == "vod_watch_history":
    cbBody.vod_watch_history()
elif mode == "vod_history_remove":
    cbBody.vod_history_remove(movie_id, season_id, episode_id)
elif mode == "vod_history_clear":
    cbBody.vod_history_clear()
elif mode == "vod_get_category_genres":
    cbBody.vod_get_category_genres(cat_id, cat_alias)
elif mode == "vod_get_ordered_list":
    cbBody.vod_get_ordered_list(cat_id, genre_id, page_nr, sortby, vod_search, vod_year)
elif mode == "vod_get_seasons":
    cbBody.vod_get_seasons(movie_id, movie_name, poster_url)
elif mode == "vod_get_episodes":
    cbBody.vod_get_episodes(movie_id, season_id, movie_name, season_name, poster_url, focus_episode_id)
elif mode == "vod_play_movie":
    cbBody.vod_play_movie(movie_id, season_id, episode_id, movie_name, season_name)
elif mode == "vod_debug":
    cbBody.vod_debug(play_cmd)
elif mode == "" or mode == None:
    cbBody.CBILLING_init(False)
