# SPDX-FileCopyrightText: Thamerlan
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys

# Add vendor directory to path for bundled dependencies
vendor_path = os.path.join(os.path.dirname(__file__), "vendor")
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import math

try:  # ordered dictionaries are esential for parsing JSON correctly
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import base64
import datetime
import hashlib
import random
import re
import socket
import time

import requests
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

if sys.version_info[0] >= 3:
    # Python 3+
    unicode = str
    import urllib.request as urllib2
    from urllib.parse import quote as urlQuote
    from urllib.parse import unquote as urlUnquote

    from xbmcvfs import translatePath as fsTranslatePath

    LOG_LEVEL = xbmc.LOGINFO
else:
    # Python 2
    from urllib import quote as urlQuote
    from urllib import unquote as urlUnquote

    import urllib2
    from xbmc import translatePath as fsTranslatePath

    LOG_LEVEL = xbmc.LOGNOTICE

try:
    import simplejson as json
except ImportError:
    import json

try:
    from unidecode import unidecode
except ImportError:
    # Fallback if unidecode is not available
    def unidecode(text):
        return text


from resources.lib.api_adapter import ApiAdapter
from resources.lib.api_client import CbillingAPI, CbillingApiError, CbillingAuthError, CbillingTimeoutError
from resources.lib.cron import CronJob, CronManager
from resources.lib.vod_cache import (
    vod_cache_clear_all,
    vod_cache_clear_old,
    vod_cache_get,
    vod_cache_get_multiple,
    vod_cache_get_stats,
    vod_cache_set,
    vod_cache_set_multiple,
)

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

# defining addon system variables
addon_handle = int(sys.argv[1])
PLUGIN_ID = "plugin.video.cbilling.iptv"
__addon__ = xbmcaddon.Addon(id=PLUGIN_ID)
__addonname__ = __addon__.getAddonInfo("name")
__addondir__ = fsTranslatePath(__addon__.getAddonInfo("path"))
__addonUserData__ = fsTranslatePath(__addon__.getAddonInfo("profile"))
__addonTempData__ = fsTranslatePath("special://temp")


# misc global variables (legacy Stalker references kept for backward compatibility)
config___stalker_url = "https://mag-aura.com"  # DEPRECATED: Stalker Portal is no longer used
STALKER_API = config___stalker_url + "/stalker_portal/"  # DEPRECATED
MEDIA_URL = "special://home/addons/%s/resources/media/" % PLUGIN_ID
XXX_CODE = "GIMMESOMEXXX"
# Debug logging is controlled by Kodi's debug setting (Settings → System → Logging → Enable debug logging)
# Use xbmc.LOGDEBUG for detailed debug info, xbmc.LOGINFO for important events

tv_poster_file = os.path.join(__addondir__, "fanart", "poster_play.png")
vod_poster_file = os.path.join(__addondir__, "fanart", "poster_vod.png")
thumb_play_file = os.path.join(__addondir__, "resources", "thumb_play.png")
thumb_next_file = os.path.join(__addondir__, "resources", "thumb_next.png")
thumb_prev_file = os.path.join(__addondir__, "resources", "thumb_prev.png")
thumb_browse_file = os.path.join(__addondir__, "resources", "thumb_browse.png")


FANART_PATH = os.path.join(__addondir__, "fanart")
epgFile = os.path.join(__addonUserData__, "epg.db")

# New REST API client initialization
config___api_url = (len(str(__addon__.getSetting("api_url"))) > 0 and str(__addon__.getSetting("api_url"))) or ""
config___public_key = (
    len(str(__addon__.getSetting("user_login"))) > 0 and str(__addon__.getSetting("user_login"))
) or ""
config___srv_timeout = (
    len(str(__addon__.getSetting("srv_response_timeout"))) > 0 and int(__addon__.getSetting("srv_response_timeout"))
) or 30

cbAPI = CbillingAPI(base_url=config___api_url, public_key=config___public_key, timeout=config___srv_timeout)
config___stb_timezone = str(__addon__.getSetting("stb_timezone")).strip()
cbAdapter = ApiAdapter(cbAPI, timezone_name=config___stb_timezone)

# Local favorites storage file
favFile = os.path.join(__addonUserData__, "favorites.json")

# Watch history storage file
historyFile = os.path.join(__addonUserData__, "watch_history.json")

# VOD pagination settings
VOD_ITEMS_PER_PAGE = 20  # Number of VOD items to display per page


def load_local_favorites():
    """Load favorite channel IDs from local JSON file."""
    try:
        if os.path.exists(favFile):
            with open(favFile) as f:
                return json.loads(f.read())
    except:
        pass
    # Migration: try to load from old setting
    old_favs = str(__addon__.getSetting("fav_channels"))
    if old_favs:
        try:
            return [x.strip() for x in old_favs.split(",") if x.strip()]
        except:
            pass
    return []


def save_local_favorites(fav_ids):
    """Save favorite channel IDs to local JSON file."""
    try:
        if not os.path.exists(__addonUserData__):
            os.makedirs(__addonUserData__)
        with open(favFile, "w") as f:
            f.write(json.dumps(fav_ids))
    except:
        pass


def load_watch_history():
    """Load watch history from local JSON file."""
    try:
        if os.path.exists(historyFile):
            with open(historyFile, encoding="utf-8") as f:
                data = json.loads(f.read())
                return data.get("history", [])
    except Exception as e:
        debug_log("[load_watch_history] Error: %s" % str(e))
    return []


def save_watch_history(history):
    """Save watch history to local JSON file."""
    try:
        if not os.path.exists(__addonUserData__):
            os.makedirs(__addonUserData__)
        with open(historyFile, "w", encoding="utf-8") as f:
            f.write(json.dumps({"history": history}, ensure_ascii=False, indent=2))
        debug_log("[save_watch_history] Saved %d items" % len(history))
    except Exception as e:
        debug_log("[save_watch_history] Error: %s" % str(e))


def add_to_watch_history(
    movie_id, season_id, episode_id, title, season_name, episode_name, episode_number, poster, content_type
):
    """
    Add item to watch history with deduplication.

    Args:
       movie_id: Movie/series ID
       season_id: Season ID (0 for movies)
       episode_id: Episode ID (0 for movies)
       title: Movie/series title
       season_name: Season name (empty for movies)
       episode_name: Episode name (empty for movies)
       episode_number: Episode number (empty for movies)
       poster: Poster URL
       content_type: 'movie' or 'episode'
    """
    try:
        history = load_watch_history()

        # Get history size limit from settings (default 5)
        try:
            history_size = int(__addon__.getSetting("history_size"))
            if history_size < 1:
                history_size = 5
        except:
            history_size = 5

        # Create new entry
        import time

        new_entry = {
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

        # Check for duplicates (same movie_id + season_id + episode_id)
        existing_index = -1
        for i, item in enumerate(history):
            if (
                item.get("movie_id") == str(movie_id)
                and item.get("season_id") == str(season_id)
                and item.get("episode_id") == str(episode_id)
            ):
                existing_index = i
                break

        # Remove existing entry if found
        if existing_index >= 0:
            history.pop(existing_index)
            debug_log("[add_to_watch_history] Updated existing entry")

        # Add new entry at the beginning
        history.insert(0, new_entry)

        # Trim history to size limit
        if len(history) > history_size:
            history = history[:history_size]

        save_watch_history(history)
        debug_log("[add_to_watch_history] Added: %s (type=%s)" % (title, content_type))
    except Exception as e:
        debug_log("[add_to_watch_history] Error: %s" % str(e))
        import traceback

        debug_log("[add_to_watch_history] Traceback: %s" % traceback.format_exc())


def clear_watch_history():
    """Clear all watch history."""
    try:
        save_watch_history([])
        debug_log("[clear_watch_history] History cleared")
        return True
    except Exception as e:
        debug_log("[clear_watch_history] Error: %s" % str(e))
        return False


def remove_from_watch_history(movie_id, season_id, episode_id):
    """Remove specific item from watch history."""
    try:
        history = load_watch_history()
        new_history = [
            item
            for item in history
            if not (
                item.get("movie_id") == str(movie_id)
                and item.get("season_id") == str(season_id)
                and item.get("episode_id") == str(episode_id)
            )
        ]
        save_watch_history(new_history)
        debug_log("[remove_from_watch_history] Removed item")
        return True
    except Exception as e:
        debug_log("[remove_from_watch_history] Error: %s" % str(e))
        return False


def get_txt(string_id):
    return __addon__.getLocalizedString(string_id)


def debug_log(line):
    # Use LOGDEBUG for detailed debug info - only shown when debug logging is enabled in Kodi
    # Use LOGINFO for important events - always shown
    xbmc.log("[Cbilling] " + str(line), level=xbmc.LOGDEBUG)


def show_msg(msg, time_to_show):
    xbmcgui.Dialog().notification(__addonname__, msg, xbmcgui.NOTIFICATION_INFO, time_to_show)


def show_vod_info(movie_id, movie_name):
    """Show detailed information about a movie/series"""
    try:
        debug_log("Loading detailed info for movie_id=%s" % movie_id)

        # Try to get from cache first
        video_data = vod_cache_get(movie_id)

        if not video_data:
            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create(get_txt(30000), get_txt(30081))  # Loading...

            # Get detailed info from API
            video_info = cbAPI.get_video(movie_id)
            progress.close()

            if not video_info or not isinstance(video_info, dict):
                show_msg(get_txt(30079), 3000)  # Error
                return

            if "data" in video_info:
                video_data = video_info["data"]
            else:
                video_data = video_info

            # Save to cache
            vod_cache_set(movie_id, video_data)
            debug_log("Cached movie_id=%s" % movie_id)
        else:
            debug_log("Using cached data for movie_id=%s" % movie_id)

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

        # Process genres
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
            info_lines.append("[B]%s:[/B] %s" % (get_txt(30135), year))  # Year
        if rating:
            info_lines.append("[B]%s:[/B] %s" % (get_txt(30136), rating))  # Rating
        if duration:
            info_lines.append("[B]%s:[/B] %s %s" % (get_txt(30137), duration, get_txt(30138)))  # Duration: X min
        if country:
            info_lines.append("[B]%s:[/B] %s" % (get_txt(30139), country))  # Country
        if genres_str:
            info_lines.append("[B]%s:[/B] %s" % (get_txt(30140), genres_str))  # Genre

        info_lines.append("")

        if director:
            info_lines.append("[B]%s:[/B] %s" % (get_txt(30141), director))  # Director
        if actors:
            info_lines.append("[B]%s:[/B] %s" % (get_txt(30142), actors))  # Cast

        if description:
            info_lines.append("")
            info_lines.append("[B]%s:[/B]" % get_txt(30134))  # Description
            info_lines.append(description)

        info_text = "[CR]".join(info_lines)

        # Show text dialog
        xbmcgui.Dialog().textviewer(title, info_text)

        debug_log("Detailed info shown successfully")

    except Exception as e:
        debug_log("Error showing VOD info: %s" % str(e))
        import traceback

        debug_log("Traceback: %s" % traceback.format_exc())
        show_msg(get_txt(30079), 3000)  # Error


def cron_log(msg):
    # show_msg(msg, 2000)
    xbmc.log("[Cbilling] Cron: " + str(msg), level=xbmc.LOGINFO)


# Random seed
def get_random_seed():
    unixtime_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    unixtime_now = int(unixtime_now_obj.days * 86400 + unixtime_now_obj.seconds)
    return hashlib.md5((str(unixtime_now) + str(random.randint(1, 999999))).encode("utf-8")).hexdigest()


# Generate a random string of fixed length
# def get_random_string (string_length=10):
#    letters_abc = string.ascii_lowercase
#    return ''.join(random.choice(letters_abc) for i in range(string_length))


# helper function to retrieve remote URL
def build_req(url, for_stalker=False, auth_bearer=False, cookie=None, post_data=None):
    debug_log("Got request for URL: " + url)
    multiroom_device_str = str(
        (len(str(__addon__.getSetting("multiroom_device"))) > 0 and int(__addon__.getSetting("multiroom_device"))) or 1
    )

    req = urllib2.Request(url)

    if for_stalker:  # disguising as different user agents and sending various headers depending on the type of request
        req.add_header(
            "User-Agent",
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        )
        req.add_header("X-User-Agent", "Model: MAG250; Link: WiFi")
        req.add_header("Referer", STALKER_API + "c/")
        req.add_header("Connection", "Keep-Alive")

        # using a md5 hash value of concatenated user+pass string allows to have unique secure sessions for every user
        hash_ready = (
            str(__addon__.getSetting("user_login")) + str(__addon__.getSetting("user_passw")) + multiroom_device_str
        )
        STB_MAC = hashlib.md5(hash_ready.encode("utf-8")).hexdigest()
        # xbmc.log("FAKE MAC: " + STB_MAC, level=xbmc.LOGINFO)
        req.add_header(
            "Cookie", "mac=" + STB_MAC + "; stb_lang=en; timezone=" + str(__addon__.getSetting("stb_timezone"))
        )

        if auth_bearer:
            req.add_header("Authorization", "Bearer " + str(__addon__.getSetting("auth_bearer")))

    else:
        req.add_header(
            "User-Agent",
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        )
        req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,q=0.8")
        req.add_header("Accept-Language", "en-US;q=0.8,en;q=0.6,ru;q=0.4,pl;q=0.2")
        if cookie:
            req.add_header("Cookie", cookie)

    return req


# helper function to retrieve remote URL
def get_url(url, for_stalker=False, auth_bearer=False, cookie=None, post_data=None):

    url_timeout = int(__addon__.getSetting("srv_response_timeout"))
    socket.setdefaulttimeout(url_timeout)
    req = build_req(url, for_stalker=for_stalker, auth_bearer=auth_bearer, cookie=cookie, post_data=post_data)

    try:
        if post_data:
            response = urllib2.urlopen(req, post_data, timeout=url_timeout)
        else:
            response = urllib2.urlopen(req, timeout=url_timeout)

        result = response.read()
    # except IOError as err:
    except socket.timeout:
        debug_log("Socket timeout")
        show_msg("Server timeout", 3000)
        xbmc.sleep(3000)
        result = '{"timeout": "Yes"}'
    finally:
        if response != None:
            response.close()

    return result


# helper function to parse a JSON object
def parse_json(json_str):
    return json.loads(json_str, object_pairs_hook=OrderedDict)


# helper function to retrieve remote JSON data
def retrieve_json_list(vars, moderate=False):

    params = vars + ""
    http_url = STALKER_API + "server/load.php?" + params
    limit = 2
    for tries in range(0, limit):
        try:
            info = get_url(http_url, True, True)
            info = parse_json(info)

            # TLU: TODO: timeout validation doesn't work by some reason...
            if "timeout" in info:
                debug_log("Server timeout")
                # show_msg("Server timeout", 3000)
                continue
            if (moderate and "js" in info) or (info["js"] != None):
                prolong_last_auth_epoch()
                return info
        except Exception:
            __addon__.setSetting("auth_epoch", "2")
            pass

    return None


# Get stream servers list from public API
def get_stream_servers():
    config___user_server = str(__addon__.getSetting("user_server"))
    if len(config___user_server) == 0:
        show_msg("ERROR: Existing stream server name is empty (bad config)", 2000)
        return

    try:
        servers_data = cbAPI.get_servers()

        if servers_data:
            listing = []
            active_pos = 0
            for srv in servers_data:
                item = xbmcgui.ListItem(
                    path=str(srv["name"]), label="%s [%s]" % (str(srv["country"]), str(srv["name"])), offscreen=True
                )
                listing.append(item)
                if config___user_server == str(srv["name"]):
                    active_pos = len(listing) - 1

            dialog = xbmcgui.Dialog()
            ret = dialog.select(get_txt(30128), listing, preselect=active_pos)

            if not (ret == None or ret < 0):
                __addon__.setSetting("user_server", str(listing[ret].getPath()))
                show_msg("%s: %s" % (get_txt(30127), str(listing[ret].getPath())), 2000)

    except:
        show_msg("ERROR: Failed to parse stream servers list from API", 2000)

    return


# Manage VOD cache
def vod_cache_manage():
    """Show VOD cache management dialog"""
    try:
        stats = vod_cache_get_stats()

        options = ["Cache statistics", "Clear old cache entries", "Clear all cache", "Cancel"]

        dialog = xbmcgui.Dialog()
        ret = dialog.select("VOD Cache Management", options)

        if ret == 0:  # Statistics
            msg = "Total entries: %d\nSize: %.2f MB\nOldest: %s\nNewest: %s" % (
                stats["total"],
                stats["size_mb"],
                stats["oldest"] or "N/A",
                stats["newest"] or "N/A",
            )
            dialog.ok("VOD Cache Statistics", msg)

        elif ret == 1:  # Clear old
            ttl_days = int(__addon__.getSetting("vod_cache_ttl_days") or "7")
            count = vod_cache_clear_old(ttl_days)
            show_msg("Cleared %d old entries (>%d days)" % (count, ttl_days), 3000)

        elif ret == 2:  # Clear all
            if dialog.yesno("Confirm", "Clear all VOD cache?"):
                vod_cache_clear_all()
                show_msg("All cache cleared", 2000)

    except Exception as e:
        debug_log("Error managing VOD cache: %s" % str(e))
        show_msg("Error managing cache", 2000)


# Sort favorite groups by priority
def group_sort_favorite(group_name):
    return {
        "armeniia": "X" + group_name,
        "azerbaidzhan": "X" + group_name,
        "belarus'": "X" + group_name,
        "kazakhstan": "X" + group_name,
        "kino": "I" + group_name,
        "moldaviia": "X" + group_name,
        "mul'tfil'my": "K" + group_name,
        "muzykal'nye": "D" + group_name,
        "novosti": "E" + group_name,
        "obshcherossiiskie": "A" + group_name,
        "poznavatel'nye": "B" + group_name,
        "rossiia +2ch": "X" + group_name,
        "sport": "C" + group_name,
        "turtsiia": "X" + group_name,
        "uhd/4k": "L" + group_name,
        "ukraina": "X" + group_name,
        "uzbekistan": "X" + group_name,
    }.get(group_name, "M" + group_name)


# Number of pages
def get_pages(info):
    try:
        total_items = float(info["total_items"])
        max_page_items = float(info["max_page_items"])
        total_pages = int(math.ceil(total_items / max_page_items))
    except:
        total_pages = 1

    return total_pages


def local_b64decode(enc_str):
    # return base64.urlsafe_b64decode(enc_str + b'=' * (4 - (len(enc_str) % 4)))
    # return base64.urlsafe_b64decode(enc_str + '=' * (4 - len(enc_str) % 4)).decode('utf-8')
    return base64.urlsafe_b64decode(enc_str.encode("utf-8") + b"========").decode("utf-8")


# Get UNIX timestamp
def get_epoch():
    unixtime_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    return int(unixtime_now_obj.days * 86400 + unixtime_now_obj.seconds)


# Prolong time to skip re-authorize
def prolong_last_auth_epoch():
    __addon__.setSetting("auth_epoch", str(get_epoch()))


def downloadTsVideo(download_path, ts_url_list):

    progress_bar = xbmcgui.DialogProgress()
    progress_bar.create("Downloading stream ...", download_path)

    for i in range(len(ts_url_list)):
        ts_url = ts_url_list[i]
        try:
            response = requests.get(ts_url, stream=True, verify=False)
        except Exception as e:
            xbmc.log("[Cbilling] Archive download: TS request failed - " + str(e), level=xbmc.LOGERROR)
            progress_bar.close()
            return

        ts_path = download_path + "\\%08d.ts" % (i,)
        with open(ts_path, "wb+") as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
            xbmc.log("[Cbilling] Archive download: TS files download completed", level=xbmc.LOGINFO)

        progress_bar.update(int((i - 1) * 100 / len(ts_url_list)))
    progress_bar.close()


def mergeTsVideo(download_path, merge_path):
    all_ts = os.listdir(download_path)
    all_ts.sort()
    merge_file_path = os.path.join(merge_path, "target.ts")

    progress_bar = xbmcgui.DialogProgress()
    progress_bar.create("Merging stream ...", merge_path)

    with open(merge_file_path, "wb+") as f:
        for i in range(len(all_ts)):
            ts_video_path = os.path.join(download_path, all_ts[i])
            f.write(open(ts_video_path, "rb").read())
            progress_bar.update(int((i - 1) * 100 / len(all_ts)))
    xbmc.log("[Cbilling] Archive download: TS merge completed", level=xbmc.LOGINFO)
    progress_bar.close()

    for f in os.listdir(download_path):
        os.remove(os.path.join(download_path, f))


# trying to authorize on Stalker with given credentials
def authorize_on_stalker(user_login, user_passw):

    # stage 1: acquiring handshake token

    http_url = STALKER_API + "server/load.php?type=stb&action=handshake"

    http_response = ""
    count = 0

    try:
        while count < 3:  # if Portal returns with an empty token response, then we have to keep trying again
            if count > 0:
                debug_log("Retrying handshake: " + str(count))
                xbmc.sleep(1000)  # sleeping for a second
            count = count + 1
            http_response = get_url(http_url, True)
            if b"token" in http_response:
                break
    except:
        return "%s. Stalker URL: %s" % (get_txt(30002), config___stalker_url)

    regex = re.search(
        r'token":"(.*)","random', http_response.decode("utf-8")
    )  # regex'ing soon to be athorization bearer from the handshake response
    if regex:
        auth_bearer = regex.group(1)
    else:
        debug_log("No handshake token in the responce: " + http_response.decode("utf-8"))
        return "No responce from the server during handshake. Check Stalker server URL or try later..."

    debug_log("Stalker handshake token: " + auth_bearer)
    __addon__.setSetting("auth_bearer", auth_bearer)  # saving this authorization bearer

    # stage 2: authorizing to the portal using user credentials
    params = "type=stb&action=do_auth&login=%s&password=%s" % (user_login, user_passw)
    try:
        info = retrieve_json_list(params)
    except:
        return "%s. %s" % (get_txt(30003), get_txt(30005))

    if info and "js" in info:
        if info["js"]:
            debug_log("Stalker authorization is successful.")
            __addon__.setSetting("user_login_working", user_login)  # marking username as working
            __addon__.setSetting("user_passw_working", user_passw)  # marking password as working
            return "true"

        else:  # otherwise removing old token
            __addon__.setSetting("auth_bearer", "")

            if "text" in info:
                # Lets catch error message
                try:
                    find_error = "".join([line.rstrip("\n") for line in info["text"]])
                    regex = re.search(r'.*"error".*string.*"(.*)".*}.*generated.*', find_error)
                    response = regex.group(1)
                    return "%s: %s" % (get_txt(30004), response)
                except:
                    return "%s. %s" % (get_txt(30003), get_txt(30006))
            else:
                return "%s" % get_txt(30003)
    else:
        return "%s. %s" % (get_txt(30003), get_txt(30007))


# checking validity of user credentials via new REST API
def check_credentials(cron_job_request):

    if not config___public_key or len(config___public_key) < 2:
        if cron_job_request:
            cron_log("Missing public key. Check addon settings")
        return get_txt(30017)

    # Skip re-authorize during X seconds after successful authorize
    last_auth_epoch = (
        len(str(__addon__.getSetting("auth_epoch"))) > 0 and int(__addon__.getSetting("auth_epoch"))
    ) or 4
    reauth_seconds = (
        len(str(__addon__.getSetting("reauth_seconds"))) > 0 and int(__addon__.getSetting("reauth_seconds"))
    ) or 120
    if (get_epoch() - last_auth_epoch) < reauth_seconds:
        return "true"

    try:
        auth_info = cbAPI.get_auth_info()
        if auth_info and "public_token" in auth_info:
            prolong_last_auth_epoch()
            # Update server from auth info if available
            if auth_info.get("server"):
                current_server = str(__addon__.getSetting("user_server"))
                if not current_server or len(current_server) < 2:
                    __addon__.setSetting("user_server", auth_info["server"])
            return "true"
        else:
            return get_txt(30003)
    except CbillingAuthError:
        __addon__.setSetting("auth_epoch", "2")
        return "%s: %s" % (get_txt(30004), "Invalid public key")
    except CbillingTimeoutError:
        return "Server timeout"
    except CbillingApiError as e:
        return "%s: %s" % (get_txt(30003), str(e))


# Prepare SQLITE DB with system table/data
def epg_sqlite_create():
    if os.path.exists(epgFile):
        return True

    createSysTable = """CREATE TABLE config(
                         key                 TEXT NOT NULL PRIMARY KEY
                        ,value               TEXT
                        ,inserted_at         TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        ,updated_at          TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """
    multi_sql = [("db version", "1.0"), ("epg last update", str(datetime.datetime.now()))]

    try:
        dbConn = sqlite.connect(epgFile, timeout=10)
        dbCursor = dbConn.cursor()
        try:
            dbCursor.execute("PRAGMA journal_mode=WAL")
        except:
            pass
        dbCursor.execute(createSysTable)
        dbCursor.executemany("INSERT INTO config (key, value) VALUES (?,?)", multi_sql)
        # """ INSERT INTO config (key, value) VALUES (?,?)
        #       ON CONFLICT(key) DO UPDATE SET
        #          value = excluded.value
        #         ,updated_at= datetime('now','localtime')
        # """
        dbConn.commit()
    except:
        show_msg(get_txt(30009), 3000)
        return False
    finally:
        if dbConn:
            dbConn.close()
    return True


# Recreate epg table
def epg_sqlite_create_epg_table():
    if not os.path.exists(epgFile):
        if not epg_sqlite_create():
            return False

    # EPG Table
    dropEpgTable = "DROP TABLE IF EXISTS epg"
    createEpgTable = """CREATE TABLE epg(
                            ch_id               INTEGER NOT NULL
                           ,stop_timestamp      INTEGER
                           ,epg_json            TEXT
                        )
                    """

    # EPG has duplicate events, so we can not use PK!
    # createEpgIndex1 = "CREATE INDEX idx_cid_sts ON epg (stop_timestamp, ch_id)"

    # Genres aka Categories table
    dropGenresTable = "DROP TABLE IF EXISTS genres"
    createGenresTable = """CREATE TABLE genres(
                              id          INTEGER NOT NULL PRIMARY KEY
                             ,title       TEXT NOT NULL
                             ,censored    INTEGER
                        )
                    """

    # Channels
    # dropChannelsTable = "DROP TABLE IF EXISTS channels"
    # createChannelsTable = """CREATE TABLE Channels(
    #                            id             INTEGER NOT NULL
    #                           ,tv_genre_id    INTEGER NOT NULL
    #                           ,channel_json   TEXT
    #                      )
    #
    #                  """
    # createChannelIndex1 = "CREATE INDEX idx_cid_channels ON channels (id)"

    # Config table - ensure it always exists (fixes "no such table: config" after DB corruption)
    createConfigTable = """CREATE TABLE IF NOT EXISTS config(
                         key                 TEXT NOT NULL PRIMARY KEY
                        ,value               TEXT
                        ,inserted_at         TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        ,updated_at          TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """

    try:
        dbConn = sqlite.connect(epgFile, timeout=10)
        dbConn.isolation_level = None
        dbCursor = dbConn.cursor()
        try:
            dbCursor.execute("PRAGMA journal_mode=WAL")
        except:
            pass
        dbCursor.execute(dropEpgTable)
        dbCursor.execute(createEpgTable)
        # dbCursor.execute(createEpgIndex1)
        dbCursor.execute(dropGenresTable)
        dbCursor.execute(createGenresTable)
        # Ensure config table exists (may have been lost due to DB corruption)
        dbCursor.execute(createConfigTable)
        # Seed config rows if missing
        dbCursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", ("db version", "1.0"))
        dbCursor.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", ("epg last update", str(datetime.datetime.now()))
        )
        dbCursor.execute("VACUUM")
    except:
        show_msg(get_txt(30010), 3000)
        return False
    finally:
        if dbConn:
            dbConn.close()

    return True


# Load new EPG to the DB
def epg_sqlite_reload(hours_to_preload, background_job):

    # Clear current EPG data
    if not epg_sqlite_create_epg_table():
        return False

    if background_job:
        show_msg(get_txt(30011), 2000)
    else:
        dialog = xbmcgui.DialogProgress()
        dialog.create(__addonname__, get_txt(30012))

    # Get all channels from new API
    try:
        streams = cbAPI.get_streams()
    except:
        streams = None

    if not streams:
        if not background_job:
            show_msg(get_txt(30013), 2000)
            dialog.close()
        else:
            cron_log("No streams data for EPG")
        return False

    # Calculate date range - load only 1 day to speed up
    days_to_load = 1  # Changed from calculating based on hours_to_preload
    total_channels = len(streams)

    try:
        dbConn = sqlite.connect(epgFile, timeout=10)
        dbCursor = dbConn.cursor()
        try:
            dbCursor.execute("PRAGMA journal_mode=WAL")
        except:
            pass

        epg_list = []
        channel_progress = 0

        for stream in streams:
            channel_progress += 1
            alias = stream.get("alias", "")
            if not alias:
                continue

            if not background_job:
                dialog.update(int(channel_progress * 100 / total_channels))
                if dialog.iscanceled():
                    break

            # Load EPG for each day
            for day_offset in range(0, days_to_load):
                date_obj = datetime.datetime.now() + datetime.timedelta(days=day_offset)
                date_str = date_obj.strftime("%Y-%m-%d")

                try:
                    day_epg = cbAdapter.get_day_epg(alias, date=date_str)
                except:
                    continue

                if not day_epg:
                    continue

                for prog in day_epg:
                    epg_block = {
                        "ch_id": alias,
                        "time": prog.get("t_time", ""),
                        "time_to": prog.get("t_time_to", ""),
                        "start_timestamp": prog.get("start_timestamp", ""),
                        "stop_timestamp": prog.get("stop_timestamp", ""),
                        "t_time": prog.get("t_time", ""),
                        "t_time_to": prog.get("t_time_to", ""),
                        "name": prog.get("name", ""),
                        "descr": prog.get("descr", ""),
                        "duration": prog.get("duration", 0),
                    }

                    stop_ts = prog.get("stop_timestamp", "0")
                    epg_list.append([alias, stop_ts, json.dumps(epg_block)])

                    if len(epg_list) > 300:
                        dbCursor.executemany("INSERT INTO epg (ch_id,stop_timestamp,epg_json) VALUES (?,?,?)", epg_list)
                        epg_list = []

        if len(epg_list) > 0:
            dbCursor.executemany("INSERT INTO epg (ch_id,stop_timestamp,epg_json) VALUES (?,?,?)", epg_list)
            epg_list = []

        dbConn.commit()
        dbCursor.execute("CREATE INDEX IF NOT EXISTS idx_cid_sts ON epg (stop_timestamp, ch_id)")

        # Update local Genres from stream categories
        genres_list = []
        try:
            genres = cbAdapter.get_genres()
            for group in genres:
                genres_list.append([group["id"], group["title"], group.get("censored", "0")])

            if len(genres_list) > 0:
                dbCursor.executemany("INSERT INTO genres (id, title, censored) VALUES (?,?,?)", genres_list)
                dbConn.commit()
        except:
            pass

        # Update config - use INSERT OR REPLACE to handle missing rows gracefully
        dbCursor.execute(
            """INSERT INTO config (key, value) VALUES (?, ?)
                          ON CONFLICT(key) DO UPDATE SET
                             value = excluded.value
                            ,updated_at = datetime('now','localtime')
                       """,
            ("epg last update", str(datetime.datetime.now())),
        )
        dbConn.commit()

    except Exception as e:
        debug_log("Failed to save EPG data to the local cache: " + str(e))
        if not background_job:
            show_msg(get_txt(30014) + "\n" + str(e), 6000)
        else:
            cron_log("Failed to save EPG to the local DB: " + str(e))
        return False
    finally:
        if not background_job:
            dialog.close()
        if dbConn:
            dbConn.close()

    if background_job:
        show_msg(get_txt(30015), 2000)
        cron_log("EPG update completed")
    return True


# Check if local EPG cache is still valid
def epg_sqlite_valid(hours_to_preload):
    if not os.path.exists(epgFile):
        if not epg_sqlite_create():
            return False

    # Check if we have enough future EPG data for any channels
    # New API uses string aliases, not numeric IDs, so we check first available channels
    run_sql = """  SELECT Max(next_epg_count) AS max_next_epg_count
                  FROM   ( SELECT ch_id
                                 ,count(*) AS next_epg_count
                           FROM   epg
                           WHERE  stop_timestamp > ?
                           GROUP  BY ch_id
                           LIMIT 5
                         ) t
             """
    do_cache_reload = False

    try:
        dbConn = sqlite.connect(epgFile, timeout=10)
        dbCursor = dbConn.cursor()
        try:
            dbCursor.execute("PRAGMA journal_mode=WAL")
        except:
            pass
        # Check if table already exists
        dbCursor.execute("SELECT count(name) FROM sqlite_master WHERE type = ? AND name = ?", ("table", "epg"))
        if dbCursor.fetchone()[0] == 1:
            dbCursor.execute(run_sql, (int(time.time()),))
            dbRow = dbCursor.fetchone()
            if dbRow is None or dbRow[0] is None:
                do_cache_reload = True
            else:
                if dbRow[0] < int(__addon__.getSetting("next_epg_limit")) + 1:
                    do_cache_reload = True
        else:
            do_cache_reload = True
    except Exception as e:
        debug_log("Failed to check EPG local cache validity: " + str(e))
        show_msg(get_txt(30016) + "\n" + str(e), 4000)
        return False
    finally:
        if dbConn:
            dbConn.close()

    # IMPORTANT: Don't reload cache synchronously during normal UI operations
    # Cache reload should only happen via cron job or explicit user action
    # If cache is invalid, we'll fall back to online EPG for individual channels
    if do_cache_reload:
        debug_log("[epg_sqlite_valid] EPG cache is outdated, will use online EPG fallback")
        return False  # Return False to indicate cache is not valid, but don't block UI

    return True


# Cron Job Initialization
def cron_epg_init():
    CBILLING_init(True)


# initialization
def CBILLING_init(cron_job_request):

    if str(__addon__.getSetting("epg_delete")) == "true":
        __addon__.setSetting("epg_delete", "false")
        if os.path.exists(epgFile):
            try:
                os.remove(epgFile)
            except:
                pass

    if not config___public_key or len(config___public_key) < 2:
        if cron_job_request:
            cron_log("Missing public key. Check addon settings")
        else:
            xbmcgui.Dialog().ok(__addonname__, get_txt(30017))

        return False
    else:
        status__credentials = check_credentials(cron_job_request)
        can_continue = True

        if status__credentials != "true":
            if cron_job_request:
                cron_log("check_credentials failed")

            else:
                try:
                    err_msg = "%s: %s" % (get_txt(30019), status__credentials)
                except:
                    err_msg = get_txt(30018)
                xbmcgui.Dialog().ok(__addonname__, err_msg)

            can_continue = False

        if can_continue:
            if cron_job_request:
                cron_epg_rebuild_cache()
            else:
                cron_epg_add_delete()
                CBILLING_start()

        else:
            return False


# Cron Job: Rebuild Cache
def cron_epg_rebuild_cache():

    if str(__addon__.getSetting("epg_cache")) == "true":
        try:
            epg_cache_hours = int(__addon__.getSetting("epg_cache_hours"))

            if str(__addon__.getSetting("epg_cron_when")) == "1" and epg_cache_hours > 48:
                # Lets limit EPG preload for daily updates
                epg_cache_hours = 48
                __addon__.setSetting("epg_cache_hours", "48")
        except:
            epg_cache_hours = 24

        if not epg_sqlite_reload(epg_cache_hours, True):
            return False
        else:
            __addon__.setSetting("cron_last_time", datetime.datetime.now().strftime("%Y-%b-%d %H:%M:%S"))


# Cron Job: Add or remove job if needed
def cron_epg_add_delete():

    # We need to randomize default Cron start time on the first plugin run to minimize load peaks for the Stalker portal
    try:
        if (
            str(__addon__.getSetting("epg_cron_minute")) == "11"
            and str(__addon__.getSetting("epg_cron_hour")) == "6"
            and str(__addon__.getSetting("epg_cron_prev_crontab")) == ""
        ):
            __addon__.setSetting("epg_cron_hour", str(random.randint(1, 6)))
            __addon__.setSetting("epg_cron_minute", str(random.randint(0, 59)))
    except:
        pass

    try:
        crontab_mask = "%s %s * * %s" % (
            str(__addon__.getSetting("epg_cron_minute")),
            str(__addon__.getSetting("epg_cron_hour")),
            (str(__addon__.getSetting("epg_cron_when")) == "1" and str(__addon__.getSetting("epg_cron_weekday")))
            or "*",
        )
        # Check if crontab was changed
        force_reload_cron = (
            str(__addon__.getSetting("epg_cron_prev_crontab")) != crontab_mask
            and str(__addon__.getSetting("epg_cron")) == "true"
        )

        if not force_reload_cron and str(__addon__.getSetting("epg_cron")) == str(
            __addon__.getSetting("epg_cron_prev_state")
        ):
            # No changes
            return True

        __addon__.setSetting("epg_cron_prev_crontab", crontab_mask)
    except:
        show_msg(get_txt(30021), 3000)
        return True

    try:
        cron_manager = CronManager()
    except:
        show_msg(get_txt(30022), 3000)
        return True

    if (
        str(__addon__.getSetting("epg_cache")) != "true"
        or str(__addon__.getSetting("epg_cron")) != "true"
        or force_reload_cron
    ):
        # Delete cron if exists
        try:
            if not force_reload_cron:
                __addon__.setSetting("epg_cron_prev_state", "false")
            cron_jobs = cron_manager.getJobs()
            for cron_job in list(cron_jobs):
                if cron_job.name == "cbilling":
                    cron_manager.deleteJob(cron_job.id)
        except:
            if not force_reload_cron:
                show_msg(get_txt(30023), 3000)
            else:
                show_msg(get_txt(30024), 3000)
            return True

    if (
        str(__addon__.getSetting("epg_cache")) == "true" and str(__addon__.getSetting("epg_cron")) == "true"
    ) or force_reload_cron:
        # Register new job
        try:
            if not force_reload_cron:
                __addon__.setSetting("epg_cron_prev_state", "true")
            # Check if job already exists
            cron_jobs = cron_manager.getJobs()
            for cron_job in list(cron_jobs):
                if cron_job.name == "cbilling":
                    return True

            cron_job = CronJob()
            cron_job.name = "cbilling"
            cron_job.command = "RunPlugin(%s?mode=cron_epg_init)" % (sys.argv[0])
            # cron_job.command = "Notification(Hello World,Example of notifications,4000)"

            # # 0 - every day; 1 - every week
            # str(__addon__.getSetting('epg_cron_when')) == ''
            #
            # # Hours 0 - 23
            # str(__addon__.getSetting('epg_cron_hour')) == ''
            #
            # # Minute 0 - 59
            # str(__addon__.getSetting('epg_cron_minute')) == ''
            #
            # # Day of the week: 0 (Sunday) - 6 (Saturday)
            # str(__addon__.getSetting('epg_cron_weekday')) == ''
            #
            # # Full crontab record
            # str(__addon__.getSetting('epg_cron_prev_crontab')) == ''

            # .--------------- minute (0 - 59)
            # |   .------------ hour (0 - 23)
            # |   |   .--------- day of month (1 - 31)
            # |   |   |   .------ month (1 - 12) or Jan, Feb ... Dec
            # |   |   |   |  .---- day of week (0 - 6) or Sun(0 or 7), Mon(1) ... Sat(6)
            # V   V   V   V  V
            # *   *   *   *  *
            cron_job.expression = crontab_mask
            cron_job.show_notification = "false"
            cron_manager.addJob(cron_job)
        except:
            show_msg(get_txt(30025), 3000)
            return True

    return True


# initial mode selection
def CBILLING_start():

    name = "[COLOR white][B]%s[/B][/COLOR]" % get_txt(30026)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt({"poster": tv_poster_file, "thumb": tv_poster_file, "fanart": os.path.join(FANART_PATH, "live_02.jpg")})
    url = sys.argv[0] + "?mode=channel_groups&archive=false"
    xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    name = "[COLOR burlywood][B]%s[/B][/COLOR]" % get_txt(30027)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {"poster": tv_poster_file, "thumb": tv_poster_file, "fanart": os.path.join(FANART_PATH, "archive_01.jpg")}
    )
    url = sys.argv[0] + "?mode=channel_groups&archive=true"
    xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    name = "[COLOR salmon][B]%s[/B][/COLOR]" % get_txt(30028)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt({"poster": tv_poster_file, "thumb": tv_poster_file, "fanart": os.path.join(FANART_PATH, "fav.jpg")})
    url = sys.argv[0] + "?mode=get_channels_list&group_id=*&favorites=1&action=live"
    xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    name = "[COLOR rosybrown][B]%s[/B][/COLOR]" % get_txt(30029)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {"poster": vod_poster_file, "thumb": vod_poster_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
    )
    url = sys.argv[0] + "?mode=vod_start"
    xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    xbmcplugin.setContent(addon_handle, "files")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    __addon__.setSetting("last_channel", "1")
    __addon__.setSetting("last_window", "0")

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)


# check Genres cache
def sqlite_get_genres():

    if not os.path.exists(epgFile):
        return []

    genres = []

    run_sql = """  SELECT id, title, censored
                  FROM   genres
             """
    try:
        dbConn = sqlite.connect(epgFile, timeout=10)
        dbCursor = dbConn.cursor()
        try:
            dbCursor.execute("PRAGMA journal_mode=WAL")
        except:
            pass
        # Check if table already exists
        dbCursor.execute("SELECT count(name) FROM sqlite_master WHERE type = ? AND name = ?", ("table", "genres"))
        if dbCursor.fetchone()[0] == 1:
            dbCursor.execute(run_sql)
            dbRows = dbCursor.fetchall()
            for dbRow in dbRows:
                genres.append({"id": str(dbRow[0]), "title": dbRow[1], "censored": str(dbRow[2])})

    except:
        show_msg(get_txt(30030), 3000)
        return []
    finally:
        if dbConn:
            dbConn.close()

    return genres


# generating a list of available channel groups
def channel_groups(archive="false"):

    xxx_enabled = (str(__addon__.getSetting("xxx_code")) == XXX_CODE and True) or False
    if xxx_enabled:
        debug_log("Password for censored channel is correct")

    groups = []
    if str(__addon__.getSetting("epg_cache")) == "true":
        try:
            groups = sqlite_get_genres()
        except:
            groups = []

    if groups == []:
        # Get genres from new API (categories extracted from streams)
        try:
            groups = cbAdapter.get_genres()
        except:
            groups = None

        if not groups:
            show_msg(get_txt(30031), 3000)
            xbmcplugin.endOfDirectory(addon_handle)
            return

    groups = sorted(groups, key=lambda arr: group_sort_favorite(unidecode(arr["title"]).lower()))

    for group in groups:
        group_id = group["id"]
        group_title = group["title"]
        group_censored = (str(group.get("censored", "0")) == "1" and True) or False

        if ("*" in str(group_id)) or (not xxx_enabled and group_censored):
            continue

        url = "%s?mode=get_channels_list&action=%s&group_id=%s&favorites=0" % (
            sys.argv[0],
            (archive == "true" and "archive") or "live",
            str(group_id),
        )

        # Create ListItem with clean title - do NOT call setLabel() with COLOR tags
        # Kodi uses label for search/filter, COLOR tags break search
        item = xbmcgui.ListItem(group_title, offscreen=True)

        # Set info for proper indexing and case-insensitive sort
        item.setInfo("video", {"title": group_title, "sorttitle": group_title.lower()})

        if archive == "true":
            item.setArt(
                {
                    "poster": tv_poster_file,
                    "thumb": thumb_browse_file,
                    "fanart": os.path.join(FANART_PATH, "archive_01.jpg"),
                }
            )
        else:
            item.setArt(
                {
                    "poster": tv_poster_file,
                    "thumb": thumb_browse_file,
                    "fanart": os.path.join(FANART_PATH, "live_02.jpg"),
                }
            )

        xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    xbmcplugin.setContent(addon_handle, "files")

    # Add sort methods for Kodi UI
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)


def get_page(params_smart, page_nr):
    params = (page_nr == 1 and params_smart) or params_smart + "&p=" + str(page_nr)
    try:
        info = retrieve_json_list(params)["js"]
    except:
        info = None

    return info


def get_channels_data(genre, fav_only="0"):

    channel_data = []
    fav_ids = load_local_favorites()

    try:
        if genre == "*":
            if fav_only == "1":
                all_channels = cbAdapter.get_all_channels()
                channel_data = cbAdapter.get_favorite_channels(all_channels, fav_ids)
            else:
                channel_data = cbAdapter.get_all_channels()
                cbAdapter.apply_favorites(channel_data, fav_ids)
        else:
            channel_data = cbAdapter.get_channels_by_genre(genre)
            cbAdapter.apply_favorites(channel_data, fav_ids)
    except CbillingApiError as e:
        debug_log("Failed to get channels: %s" % str(e))
        return []

    # Load current EPG for all channels in parallel
    # Priority: 1) SQLite cache (if available), 2) HTTP API (parallel)
    if channel_data:
        # Try to get cur_playing from SQLite cache first
        db_conn_epg = None
        now_ts = int(time.time())
        aliases_need_http = []

        if os.path.exists(epgFile):
            try:
                db_conn_epg = sqlite.connect(epgFile, timeout=10)
                db_cur_epg = db_conn_epg.cursor()
                try:
                    db_cur_epg.execute("PRAGMA journal_mode=WAL")
                except:
                    pass
                sql_cur = """SELECT epg_json FROM epg
                         WHERE ch_id = ? AND stop_timestamp > ?
                         ORDER BY stop_timestamp ASC LIMIT 1"""
                for channel in channel_data:
                    alias = channel.get("id", "")
                    if not alias:
                        continue
                    try:
                        db_cur_epg.execute(sql_cur, (alias, now_ts))
                        row = db_cur_epg.fetchone()
                        if row:
                            epg_entry = json.loads(row[0])
                            # Recalculate t_time from timestamp using addon timezone
                            start_ts = epg_entry.get("start_timestamp", "")
                            t_time = cbAdapter._ts_to_local_str(start_ts) if start_ts else epg_entry.get("t_time", "")
                            name = epg_entry.get("name", "")
                            descr = epg_entry.get("descr", "")
                            channel["cur_playing"] = ("%s %s" % (t_time, name)).strip() if (t_time or name) else ""
                            channel["cur_playing_descr"] = descr
                        else:
                            aliases_need_http.append(channel)
                    except Exception as e:
                        debug_log("[get_channels_data] SQLite EPG lookup error for %s: %s" % (alias, str(e)))
                        aliases_need_http.append(channel)
            except Exception as e:
                debug_log("[get_channels_data] SQLite open error: %s" % str(e))
                aliases_need_http = list(channel_data)
            finally:
                if db_conn_epg:
                    db_conn_epg.close()
        else:
            aliases_need_http = list(channel_data)

        debug_log(
            "[get_channels_data] cur_playing: %d from cache, %d need HTTP"
            % (len(channel_data) - len(aliases_need_http), len(aliases_need_http))
        )

        # For channels not in cache - load via HTTP in parallel
        if aliases_need_http:
            try:
                from concurrent.futures import ThreadPoolExecutor, as_completed

                epg_ok = [0]
                epg_fail = [0]

                # Load 2 programs if EPG display in channel list is enabled (current + next)
                epg_size = 2 if str(__addon__.getSetting("epg_in_channel_list")) == "true" else 1

                def fetch_epg(channel):
                    alias = channel.get("id", "")
                    if alias:
                        try:
                            epg_data = cbAdapter.get_short_epg(alias, size=epg_size)
                            if epg_data and len(epg_data) > 0:
                                entry = epg_data[0]
                                t_time = entry.get("t_time", "")
                                name = entry.get("name", "")
                                descr = entry.get("descr", "")
                                channel["cur_playing"] = ("%s %s" % (t_time, name)).strip() if (t_time or name) else ""
                                channel["cur_playing_descr"] = descr
                                # Store full short_epg for enhanced display
                                channel["short_epg"] = epg_data
                                if channel["cur_playing"]:
                                    epg_ok[0] += 1
                                else:
                                    epg_fail[0] += 1
                            else:
                                channel["cur_playing"] = ""
                                epg_fail[0] += 1
                                debug_log("[get_channels_data] No EPG for alias=%s" % alias)
                        except Exception as e:
                            channel["cur_playing"] = ""
                            epg_fail[0] += 1
                            debug_log("[get_channels_data] EPG fetch error for alias=%s: %s" % (alias, str(e)))
                    return channel

                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = {executor.submit(fetch_epg, ch): ch for ch in aliases_need_http}
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            debug_log("[get_channels_data] EPG fetch error: %s" % str(e))
                debug_log("[get_channels_data] HTTP EPG: %d ok, %d no-data" % (epg_ok[0], epg_fail[0]))
            except Exception as e:
                debug_log("[get_channels_data] EPG parallel load error: %s" % str(e))

    return channel_data


# Add/Remove favorite channel (local storage)
def itv_fav_add_remove(channel_id, action):

    if action == None:
        show_msg(get_txt(30033), 2000)
        return

    fav_ids = load_local_favorites()

    if action == "remove":
        if channel_id in fav_ids:
            fav_ids.remove(channel_id)
        else:
            show_msg(get_txt(30035), 2000)
            return

    elif action == "add":
        if channel_id in fav_ids:
            show_msg(get_txt(30036), 2000)
            return
        fav_ids.append(channel_id)

    save_local_favorites(fav_ids)
    show_msg((action == "add" and get_txt(30038)) or get_txt(30039), 2000)
    if action == "remove":
        xbmc.executebuiltin("Container.Refresh")


# generating a list of channels belonging to requested group to be viewed in live mode
def get_channels_list(group_id, favorites, action):
    import time as time_module

    start_time = time_module.time()
    debug_log("[get_channels_list] START: group_id=%s, favorites=%s, action=%s" % (group_id, favorites, action))

    status__credentials = check_credentials(False)
    debug_log("[get_channels_list] check_credentials took %.2f sec" % (time_module.time() - start_time))

    if status__credentials != "true":
        try:
            err_msg = "%s: %s" % (get_txt(30019), status__credentials)
        except:
            err_msg = get_txt(30018)

        xbmcgui.Dialog().ok(__addonname__, err_msg)
        return False

    # Do we need to show Short EPG
    try:
        if str(__addon__.getSetting("load_next_epg")) == "true":
            next_epg_limit = int(__addon__.getSetting("next_epg_limit")) + 1
        else:
            next_epg_limit = 0
    except:
        next_epg_limit = 0

    # Do we need to cache EPG
    epg_check_start = time_module.time()
    try:
        if next_epg_limit > 0 and str(__addon__.getSetting("epg_cache")) == "true":
            epg_cache_hours = int(__addon__.getSetting("epg_cache_hours"))
            # Check if cache is valid, if not - fall back to online EPG
            if not epg_sqlite_valid(epg_cache_hours):
                debug_log("[get_channels_list] EPG cache is invalid, using online EPG")
                epg_cache_hours = 0
            else:
                run_sql = """  SELECT epg_json
                           FROM   epg
                           WHERE  ch_id = ?
                             AND  stop_timestamp > ?
                           ORDER BY stop_timestamp
                           LIMIT ?
                      """
        else:
            epg_cache_hours = 0
    except:
        epg_cache_hours = 0
    debug_log(
        "[get_channels_list] EPG cache check took %.2f sec, epg_cache_hours=%d"
        % (time_module.time() - epg_check_start, epg_cache_hours)
    )

    if action == "archive":
        epg_cache_hours = 0
        next_epg_limit = 0

    channels_start = time_module.time()
    channels = get_channels_data(group_id, favorites)
    debug_log(
        "[get_channels_list] get_channels_data took %.2f sec, got %d channels"
        % (time_module.time() - channels_start, len(channels) if channels else 0)
    )

    if channels == None or len(channels) == 0:
        show_msg(get_txt(30040), 3000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    try:
        channels = sorted(channels, reverse=False, key=lambda x: (-x["fav"], x.get("sort", 0), x["name"]))
    except:
        pass

    debug_log(
        "[get_channels_list] Before dialog create, total time so far: %.2f sec" % (time_module.time() - start_time)
    )

    # Open DB for local EPG
    dbConn = None
    if epg_cache_hours > 0:
        try:
            dbConn = sqlite.connect(epgFile, timeout=10)
            dbCursor = dbConn.cursor()
            try:
                dbCursor.execute("PRAGMA journal_mode=WAL")
            except:
                pass
        except:
            epg_cache_hours = 0
            if dbConn:
                dbConn.close()

    listing = []

    dialog = xbmcgui.DialogProgress()
    dialog.create(__addonname__, get_txt(30041))
    debug_log("[get_channels_list] Dialog created at %.2f sec" % (time_module.time() - start_time))

    total_items = len(channels)
    items_number = 0
    loop_start = time_module.time()

    for channel in channels:
        channel_start = time_module.time()
        items_number += 1
        channel_id = channel["id"]  # This is now the alias
        group_id = channel["tv_genre_id"]
        channel_cmd = channel["cmd"]  # This is now the direct stream URL
        channel_has_archive = (channel["tv_archive_type"] == "flussonic_dvr" and True) or False
        channel_archive_depth = str(channel["tv_archive_duration"])
        debug_log(
            "[get_channels_list] Channel: %s, archive_depth: %s, has_archive: %s"
            % (channel["name"], channel_archive_depth, channel_has_archive)
        )
        channel_title = channel["name"].upper()
        channel_title_visual = channel["name"]
        # Logo from new API - direct URL
        tv_logo_original = channel.get("logo", "")
        tv_logo_small = tv_logo_original

        # Get current program text
        # Current program should already be in channel data from /streams API
        channel_curr_epg = channel.get("cur_playing", "")
        # IMPORTANT: Don't load current program for each channel via API
        # This would cause 50+ HTTP requests and block UI for a long time
        # Current program is already included in /streams response
        # if not channel_curr_epg and next_epg_limit > 0:
        #    try:
        #        channel_curr_epg = cbAdapter.get_current_program_text(channel_id)
        #    except:
        #        channel_curr_epg = ''

        # Fetch event's start time
        unixtime_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
        unixtime_now = int(unixtime_now_obj.days * 86400 + unixtime_now_obj.seconds)
        try:
            event_start_time_hour = channel_curr_epg[0:2]
            event_start_time_min = channel_curr_epg[3:5]

            date_yesterday = (
                datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
                - datetime.timedelta(days=1)
                + datetime.timedelta(hours=int(event_start_time_hour))
                + datetime.timedelta(minutes=int(event_start_time_min))
            )
            ts_yesterday = int(time.mktime(date_yesterday.timetuple()))

            date_today = (
                datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
                + datetime.timedelta(hours=int(event_start_time_hour))
                + datetime.timedelta(minutes=int(event_start_time_min))
            )
            ts_today = int(time.mktime(date_today.timetuple()))

            ts = (ts_today < unixtime_now and ts_today) or ts_yesterday
        except:
            ts = unixtime_now

        # Get short EPG
        if next_epg_limit > 0 and len(channel_id) > 0:
            skip_online_epg = False

            if epg_cache_hours > 0:
                dbEPG = []
                try:
                    dbCursor.execute(run_sql, (channel_id, int(time.time()), next_epg_limit))
                    for dbRow in dbCursor:
                        dbEPG.append(json.loads(dbRow[0]))

                    channel.update({"short_epg": dbEPG})
                    skip_online_epg = True
                except:
                    pass

            # IMPORTANT: Don't load online EPG for each channel if cache is disabled
            # This would cause 50+ HTTP requests and block UI for a long time
            # User should enable EPG cache and wait for scheduled update
            # Online EPG is still available via context menu for individual channels
            if not skip_online_epg and epg_cache_hours > 0:
                # Load EPG from new API only if cache is enabled but data is missing
                try:
                    epg_data = cbAdapter.get_short_epg(channel_id, size=next_epg_limit)
                    if epg_data:
                        channel.update({"short_epg": epg_data})
                except:
                    pass

        # Process short epg
        epg_counter = 0
        plot_epg = ""
        plot_desc = ""
        epg_current_program = ""
        epg_next_program = ""

        if "short_epg" in channel:
            for epg_data in channel["short_epg"]:
                epg_counter += 1
                if epg_counter == 1:
                    # First entry = current program
                    epg_current_program = epg_data
                elif epg_counter == 2:
                    # Second entry = next program
                    epg_next_program = epg_data
                    plot_epg += "[CR]%s: %s" % (epg_data["t_time"], epg_data["name"])
                else:
                    plot_epg += "[CR]%s: %s" % (epg_data["t_time"], epg_data["name"])

        # Build EPG info for label2 and inline label display
        channel_curr_epg_title = ""
        channel_curr_epg_start = ""
        epg_label2 = ""
        epg_progress_prc = None
        epg_inline_text = ""

        # Try to get EPG from short_epg cache first (primary source)
        if epg_current_program and action != "archive":
            try:
                channel_curr_epg_start = epg_current_program.get("t_time", "")
                channel_curr_epg_title = epg_current_program.get("name", "")
                t_time_to = epg_current_program.get("t_time_to", "")
                start_ts = int(epg_current_program.get("start_timestamp", 0))
                stop_ts = int(epg_current_program.get("stop_timestamp", 0))

                # Calculate progress percentage
                if start_ts and stop_ts and stop_ts > start_ts:
                    now_ts = int(time.mktime(time.localtime()))
                    epg_progress_prc = int(((now_ts - start_ts) * 100) / (stop_ts - start_ts))
                    if epg_progress_prc < 0:
                        epg_progress_prc = 0
                    elif epg_progress_prc > 100:
                        epg_progress_prc = 100

                # Build label2 text
                if channel_curr_epg_start and channel_curr_epg_title:
                    if epg_progress_prc is not None and t_time_to:
                        epg_label2 = "%s - %s (%s%%) | %s" % (
                            channel_curr_epg_start,
                            t_time_to,
                            str(epg_progress_prc),
                            channel_curr_epg_title.strip(),
                        )
                    else:
                        epg_label2 = "%s | %s" % (channel_curr_epg_start, channel_curr_epg_title.strip())

                # Build inline EPG text (for embedding in label)
                if channel_curr_epg_start and channel_curr_epg_title:
                    epg_inline_text = "%s %s" % (channel_curr_epg_start, channel_curr_epg_title.strip())
                    if epg_next_program:
                        next_time = epg_next_program.get("t_time", "")
                        next_name = epg_next_program.get("name", "")
                        if next_time and next_name:
                            epg_inline_text += "  |  %s %s" % (next_time, next_name.strip())
            except:
                pass

        # Fallback: parse from cur_playing text if short_epg was not available
        elif channel_curr_epg and "NO CHANNEL INFO" not in channel_curr_epg.upper() and action != "archive":
            regex = re.search(r"(\d{2}:\d{2})(.*)", channel_curr_epg)
            if regex:
                try:
                    channel_curr_epg_start = regex.group(1)
                    channel_curr_epg_title = regex.group(2)
                    epg_label2 = "%s | %s" % (channel_curr_epg_start, channel_curr_epg_title.strip())
                    epg_inline_text = "%s %s" % (channel_curr_epg_start, channel_curr_epg_title.strip())
                except:
                    pass

        # Determine if EPG should be shown inline (in the channel label)
        show_epg_in_list = str(__addon__.getSetting("epg_in_channel_list")) == "true"

        # EPG display in standard Estuary WideList is limited to the info panel (left side)
        # The label stays clean for search/filter compatibility
        channel_label = channel_title_visual

        # Create ListItem
        list_item = xbmcgui.ListItem(channel_label, offscreen=True)
        if epg_label2:
            list_item.setLabel2(epg_label2)

        # DIAGNOSTIC: Log label details for first 5 channels to debug search/filter
        if items_number <= 5:
            debug_log(
                "[DIAG_SEARCH] Channel #%d: name=%s, label(visual)=%s, label_type=%s, label_repr=%s"
                % (
                    items_number,
                    channel["name"],
                    channel_title_visual,
                    type(channel_title_visual).__name__,
                    repr(channel_title_visual),
                )
            )
            debug_log(
                "[DIAG_SEARCH] Channel #%d: lower=%s, upper=%s"
                % (items_number, channel_title_visual.lower(), channel_title_visual.upper())
            )
            # Check if getLabel returns what we set
            try:
                actual_label = list_item.getLabel()
                debug_log(
                    "[DIAG_SEARCH] Channel #%d: getLabel()=%s, getLabel_repr=%s, match=%s"
                    % (items_number, actual_label, repr(actual_label), str(actual_label == channel_title_visual))
                )
            except Exception as e:
                debug_log("[DIAG_SEARCH] Channel #%d: getLabel() error: %s" % (items_number, str(e)))

        # Build context menu
        context_menu = []
        plot_desc = ""  # Initialize here to avoid NameError

        # Get EPG description from short_epg or from cached cur_playing_descr
        epg_descr = ""
        if channel.get("short_epg"):
            epg_descr = channel["short_epg"][0].get("descr", "")
        if not epg_descr:
            epg_descr = channel.get("cur_playing_descr", "")

        # Debug: log EPG description source for first 3 channels
        if items_number <= 3:
            has_short_epg = "short_epg" in channel and bool(channel.get("short_epg"))
            has_cur_descr = bool(channel.get("cur_playing_descr", ""))
            debug_log(
                "[DIAG_EPG_DESCR] Channel #%d (%s): short_epg=%s, cur_playing_descr=%s, epg_descr=%s"
                % (
                    items_number,
                    channel.get("name", "?"),
                    "yes (%d chars)" % len(channel["short_epg"][0].get("descr", "")) if has_short_epg else "no",
                    "yes (%d chars)" % len(channel.get("cur_playing_descr", "")) if has_cur_descr else "no",
                    "yes (%d chars)" % len(epg_descr) if epg_descr else "no",
                )
            )

        if channel_has_archive:
            if action == "live":
                show_epg_in_list = str(__addon__.getSetting("epg_in_channel_list")) == "true"
                if show_epg_in_list and channel_curr_epg_title.strip():
                    # Enhanced EPG format for info panel
                    plot_parts = []
                    plot_parts.append(
                        "[COLOR moccasin][B]%s[/B] %s[/COLOR]" % (get_txt(30156), channel_curr_epg_title.strip())
                    )
                    if channel_curr_epg_start:
                        time_info = "%s %s" % (get_txt(30158), channel_curr_epg_start)
                        if epg_current_program:
                            t_time_to = epg_current_program.get("t_time_to", "")
                            if t_time_to:
                                time_info = "%s — %s" % (channel_curr_epg_start, t_time_to)
                            start_ts = int(epg_current_program.get("start_timestamp", 0))
                            stop_ts = int(epg_current_program.get("stop_timestamp", 0))
                            if start_ts and stop_ts and stop_ts > start_ts:
                                now_ts = int(time.mktime(time.localtime()))
                                elapsed_min = (now_ts - start_ts) // 60
                                if elapsed_min > 0:
                                    time_info += " (%s)" % (get_txt(30159) % elapsed_min)
                        plot_parts.append("[COLOR grey]%s[/COLOR]" % time_info)

                    # Next program (shown before description)
                    if epg_next_program:
                        next_name = epg_next_program.get("name", "")
                        next_start = epg_next_program.get("t_time", "")
                        next_end = epg_next_program.get("t_time_to", "")
                        if next_name:
                            starts_in_str = ""
                            next_start_ts = int(epg_next_program.get("start_timestamp", 0))
                            if next_start_ts:
                                now_ts = int(time.mktime(time.localtime()))
                                starts_in_min = (next_start_ts - now_ts) // 60
                                if starts_in_min > 0:
                                    starts_in_str = " (%s)" % (get_txt(30160) % starts_in_min)
                            plot_parts.append("")
                            plot_parts.append("[COLOR burlywood][B]%s[/B] %s[/COLOR]" % (get_txt(30157), next_name))
                            next_time = ""
                            if next_start and next_end:
                                next_time = "%s — %s" % (next_start, next_end)
                            elif next_start:
                                next_time = "%s %s" % (get_txt(30158), next_start)
                            if next_time:
                                plot_parts.append("[COLOR grey]%s%s[/COLOR]" % (next_time, starts_in_str))

                    # Description last
                    if epg_descr:
                        plot_parts.append("")
                        plot_parts.append(epg_descr.strip())

                    plot_desc = "[CR]".join(plot_parts)
                else:
                    # Original format
                    plot_desc = "[COLOR moccasin][B]%s[/B]: %s[/COLOR]" % (
                        get_txt(30042),
                        channel_curr_epg_title.strip(),
                    )
                    if epg_descr:
                        plot_desc += "[CR][CR][COLOR white]%s[/COLOR]" % epg_descr.strip()
                context_menu.append(
                    (
                        "[B]%s[/B]" % get_txt(30125),
                        'Container.Update("%s?mode=archive_channel_epg&channel_id=%s&date=%s&name=%s&play_cmd=%s&logo_png=%s&direct=1")'
                        % (
                            sys.argv[0],
                            channel_id,
                            datetime.date.today().strftime("%Y-%m-%d"),
                            re.sub("=", "", base64.urlsafe_b64encode(channel_title.encode("utf-8")).decode("utf-8")),
                            urlQuote(channel_cmd),
                            urlQuote(tv_logo_original),
                        ),
                    )
                )
                context_menu.append(
                    (
                        "[B]%s[/B]" % get_txt(30043),
                        'Container.Update("%s?mode=archive_channel_dates&channel_id=%s&name=%s&depth=%s&play_cmd=%s&logo_png=%s")'
                        % (
                            sys.argv[0],
                            channel_id,
                            re.sub("=", "", base64.urlsafe_b64encode(channel_title.encode("utf-8")).decode("utf-8")),
                            str(channel["tv_archive_duration"]),
                            urlQuote(channel_cmd),
                            urlQuote(tv_logo_original),
                        ),
                    )
                )

                if ts != unixtime_now:
                    context_menu.append(
                        (
                            "[B]%s[/B]" % get_txt(30123),
                            "RunPlugin(%s?mode=play_live_event_from_start&play_cmd=%s&name=%s&ts=%s)"
                            % (
                                sys.argv[0],
                                urlQuote(channel_cmd),
                                urlQuote(channel_title.encode("utf-8"), safe=""),
                                ts,
                            ),
                        )
                    )
        else:
            if channel_curr_epg and "NO CHANNEL INFO" not in channel_curr_epg.upper() and action == "live":
                show_epg_in_list = str(__addon__.getSetting("epg_in_channel_list")) == "true"
                if show_epg_in_list:
                    # Enhanced format: time range + remaining + description
                    plot_parts = []
                    plot_parts.append("[COLOR moccasin][B]Сейчас:[/B] %s[/COLOR]" % channel_curr_epg_title.strip())
                    if channel_curr_epg_start:
                        time_info = channel_curr_epg_start
                        # Add end time and remaining from short_epg if available
                        if epg_current_program:
                            t_time_to = epg_current_program.get("t_time_to", "")
                            if t_time_to:
                                time_info = "%s — %s" % (channel_curr_epg_start, t_time_to)
                            start_ts = int(epg_current_program.get("start_timestamp", 0))
                            stop_ts = int(epg_current_program.get("stop_timestamp", 0))
                            if start_ts and stop_ts and stop_ts > start_ts:
                                now_ts = int(time.mktime(time.localtime()))
                                remaining_min = (stop_ts - now_ts) // 60
                                if remaining_min > 0:
                                    time_info += " (%d мин. ост.)" % remaining_min
                        plot_parts.append("[COLOR grey]%s[/COLOR]" % time_info)

                    if epg_descr:
                        plot_parts.append("")
                        plot_parts.append(epg_descr.strip())

                    # Next program from plot_epg or epg_next_program
                    if epg_next_program:
                        next_name = epg_next_program.get("name", "")
                        next_start = epg_next_program.get("t_time", "")
                        next_end = epg_next_program.get("t_time_to", "")
                        if next_name:
                            starts_in_str = ""
                            next_start_ts = int(epg_next_program.get("start_timestamp", 0))
                            if next_start_ts:
                                now_ts = int(time.mktime(time.localtime()))
                                starts_in_min = (next_start_ts - now_ts) // 60
                                if starts_in_min > 0:
                                    starts_in_str = " (через %d мин.)" % starts_in_min
                            plot_parts.append("")
                            plot_parts.append("[COLOR burlywood][B]Далее:[/B] %s[/COLOR]" % next_name)
                            next_time = ""
                            if next_start and next_end:
                                next_time = "%s — %s" % (next_start, next_end)
                            elif next_start:
                                next_time = next_start
                            if next_time:
                                plot_parts.append("[COLOR grey]%s%s[/COLOR]" % (next_time, starts_in_str))
                    elif plot_epg:
                        plot_parts.append("")
                        plot_parts.append("[B]%s[/B]:%s" % (get_txt(30048), plot_epg))

                    plot_desc = "[CR]".join(plot_parts)
                else:
                    # Original compact format
                    plot_desc = "[COLOR moccasin][B]%s[/B]: %s[/COLOR]" % (
                        get_txt(30042),
                        channel_curr_epg_title.strip(),
                    )
                    if epg_descr:
                        plot_desc += "[CR][CR][COLOR white]%s[/COLOR]" % epg_descr.strip()

        context_menu.append(
            (
                "[B]%s[/B]" % get_txt(30119),
                "RunPlugin(%s?mode=epg_show&channel_id=%s&channel_title=%s)"
                % (sys.argv[0], channel_id, urlQuote(channel_title.encode("utf-8"), safe="")),
            )
        )

        if channel_has_archive:
            context_menu.append(
                (
                    "%s" % get_txt(30044),
                    "RunPlugin(%s?mode=timepick_live_channel&play_cmd=%s&name=%s)"
                    % (
                        sys.argv[0],
                        urlQuote(channel_cmd),
                        re.sub("=", "", base64.urlsafe_b64encode(channel_title.encode("utf-8")).decode("utf-8")),
                    ),
                )
            )

        context_menu.append(("%s" % get_txt(30124), "Container.Refresh"))

        if action == "live":
            context_menu.append((get_txt(30045), "Action(Info)"))

        if favorites == "1":
            context_menu.append(
                (
                    get_txt(30046),
                    "RunPlugin(%s?mode=itv_fav_add_remove&channel_id=%s&action=remove)" % (sys.argv[0], channel_id),
                )
            )
        else:
            context_menu.append(
                (
                    get_txt(30047),
                    "RunPlugin(%s?mode=itv_fav_add_remove&channel_id=%s&action=add)" % (sys.argv[0], channel_id),
                )
            )

        # Stream servers
        context_menu.append(("%s" % get_txt(30128), "RunPlugin(%s?mode=get_stream_servers)" % (sys.argv[0])))

        list_item.addContextMenuItems(items=context_menu, replaceItems=True)

        # Info and beauty
        if action == "live":
            if len(plot_epg) > 1 and not plot_desc:
                plot_desc += "[CR][CR][B]%s[/B]:%s" % (get_txt(30048), plot_epg)

            # Use clean channel name for search/filter, sorttitle for case-insensitive sorting
            list_item.setInfo(
                type="video",
                infoLabels={
                    "Title": channel_title_visual,  # Clean title for search
                    "sorttitle": channel_title_visual.lower(),  # Lowercase for case-insensitive sorting
                    "mediatype": "video",
                    "Plot": plot_desc,
                },
            )
            # DIAGNOSTIC: Log what setInfo did to the label
            if items_number <= 5:
                try:
                    label_after_setinfo = list_item.getLabel()
                    debug_log(
                        "[DIAG_SEARCH] Channel #%d AFTER setInfo: getLabel()=%s, repr=%s"
                        % (items_number, label_after_setinfo, repr(label_after_setinfo))
                    )
                    debug_log(
                        "[DIAG_SEARCH] Channel #%d setInfo Title=%s, sorttitle=%s"
                        % (items_number, channel_title_visual, channel_title_visual.lower())
                    )
                except Exception as e:
                    debug_log("[DIAG_SEARCH] Channel #%d AFTER setInfo error: %s" % (items_number, str(e)))
            try:
                list_item.setArt(
                    {
                        "thumb": tv_logo_small,
                        "fanart": os.path.join(FANART_PATH, "live_02.jpg"),
                    }
                )
            except:
                list_item.setArt(
                    {
                        "thumb": thumb_play_file,
                        "fanart": os.path.join(FANART_PATH, "live_02.jpg"),
                    }
                )

            list_item.setProperty("IsPlayable", "true")
            url = sys.argv[0] + "?mode=play_live_channel&play_cmd=%s&name=%s&channel_id=%s&random=%s" % (
                urlQuote(channel_cmd),
                re.sub("=", "", base64.urlsafe_b64encode(channel_title.encode("utf-8")).decode("utf-8")),
                channel_id,
                get_random_seed(),
            )
            is_folder = False
        else:
            try:
                list_item.setArt(
                    {
                        "poster": tv_logo_original,
                        "fanart": os.path.join(FANART_PATH, "archive_01.jpg"),
                        "thumb": tv_logo_small,
                    }
                )
            except:
                list_item.setArt(
                    {"poster": tv_poster_file, "fanart": os.path.join(FANART_PATH, "archive_01.jpg"), "thumb": ""}
                )

            url = sys.argv[0] + "?mode=archive_channel_dates&channel_id=%s&name=%s&depth=%s&play_cmd=%s&logo_png=%s" % (
                str(channel_id),
                re.sub("=", "", base64.urlsafe_b64encode(channel_title.encode("utf-8")).decode("utf-8")),
                channel_archive_depth,
                urlQuote(channel_cmd),
                urlQuote(tv_logo_original),
            )
            is_folder = True

        listing.append((url, list_item, is_folder))

        # Log timing for first 3 channels and every 10th channel
        if items_number <= 3 or items_number % 10 == 0:
            debug_log(
                "[get_channels_list] Channel #%d (%s) took %.3f sec"
                % (items_number, channel["name"], time_module.time() - channel_start)
            )

        if dialog.iscanceled():
            break

        dialog.update(int((items_number - 1) * 100 / total_items))

    debug_log(
        "[get_channels_list] Channel loop took %.2f sec for %d channels (avg %.3f sec/channel)"
        % (
            time_module.time() - loop_start,
            items_number,
            (time_module.time() - loop_start) / items_number if items_number > 0 else 0,
        )
    )

    dialog.close()
    if epg_cache_hours > 0:
        if dbConn:
            dbConn.close()

    xbmcplugin.addDirectoryItems(addon_handle, listing, totalItems=len(listing))

    # Add sort methods for Kodi UI
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    # DIAGNOSTIC: Log sort methods and locale info
    debug_log(
        "[DIAG_SEARCH] Sort methods added: SORT_METHOD_LABEL(%d), SORT_METHOD_LABEL_IGNORE_THE(%d)"
        % (xbmcplugin.SORT_METHOD_LABEL, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    )
    debug_log("[DIAG_SEARCH] Total items in listing: %d" % len(listing))
    try:
        import locale

        debug_log("[DIAG_SEARCH] Python locale: %s" % str(locale.getlocale()))
        debug_log("[DIAG_SEARCH] Python default encoding: %s" % sys.getdefaultencoding())
        debug_log("[DIAG_SEARCH] Python filesystem encoding: %s" % sys.getfilesystemencoding())
    except Exception as e:
        debug_log("[DIAG_SEARCH] Locale info error: %s" % str(e))
    # Test: does Python lower() work for cyrillic?
    test_cyr = "НТВ"
    debug_log('[DIAG_SEARCH] Python cyrillic lower test: "%s".lower() = "%s"' % (test_cyr, test_cyr.lower()))
    test_cyr2 = "Первый Канал"
    debug_log('[DIAG_SEARCH] Python cyrillic lower test: "%s".lower() = "%s"' % (test_cyr2, test_cyr2.lower()))

    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)

    # Try to set focus based on the previous selection
    xbmc.sleep(400)
    try:
        total_list_items = int(xbmc.getInfoLabel("Container(id).NumItems"))
    except Exception:
        total_list_items = 0

    win_id = xbmcgui.getCurrentWindowId()
    win = xbmcgui.Window(win_id)
    cid = win.getFocusId()

    try:
        last_channel_position = 0
        last_window = int(__addon__.getSetting("last_window"))
        if last_window == win_id:
            last_channel_position = int(__addon__.getSetting("last_channel"))
            if total_list_items >= last_channel_position:
                xbmc.executebuiltin("SetFocus(%s, %s, absolute)" % (cid, last_channel_position))

        if win_id != last_window:
            __addon__.setSetting("last_window", str(win_id))

        if last_channel_position == 0:
            xbmc.executebuiltin("SetFocus(%s, %s, absolute)" % (cid, 1))
        __addon__.setSetting("last_channel", str(0))
    except Exception:
        pass


# launching live stream
def play_live_channel(play_cmd, name, channel_id):

    # Save previous windows item position
    try:
        curr_item = xbmc.getInfoLabel("Container(id).CurrentItem")
        if curr_item != 0:
            __addon__.setSetting("last_channel", curr_item)
    except Exception:
        pass

    info_epg_limit = 10

    debug_log("Playing live channel: " + name)

    # play_cmd now contains the direct stream URL from /streams API
    stream_url_live = urlUnquote(play_cmd)

    item = xbmcgui.ListItem(path=stream_url_live, label=name, offscreen=True)

    # Lets show EPG for the Info button
    plot_epg = "[B]%s:[/B]" % get_txt(30050)

    # Do we need to cache EPG
    dbConn = None
    skip_online_epg = False
    first_descr = ""
    try:
        if str(__addon__.getSetting("epg_cache")) == "true":
            run_sql = """  SELECT epg_json
                        FROM   epg
                        WHERE  ch_id = ?
                          AND  stop_timestamp > ?
                        ORDER BY stop_timestamp
                        LIMIT ?
                   """
            dbConn = sqlite.connect(epgFile, timeout=10)
            dbCursor = dbConn.cursor()
            try:
                dbCursor.execute("PRAGMA journal_mode=WAL")
            except:
                pass
            dbCursor.execute(run_sql, (channel_id, int(time.time()), info_epg_limit))
            first_row = True
            rows_found = 0
            for dbRow in dbCursor:
                dbEPG = json.loads(dbRow[0])
                plot_epg += "[CR]%s-%s: %s" % (dbEPG["t_time"], dbEPG["t_time_to"], dbEPG["name"])
                rows_found += 1
                if first_row:
                    first_descr = dbEPG.get("descr", "")
                    first_row = False
            # Only skip online EPG if we actually found data in cache
            if rows_found > 0:
                skip_online_epg = True
                debug_log(
                    "[play_live_channel] SQLite EPG: %d items, descr=%s" % (rows_found, "yes" if first_descr else "no")
                )
            else:
                debug_log("[play_live_channel] SQLite EPG: 0 items for channel_id=%s, will try API" % channel_id)
        else:
            debug_log("[play_live_channel] EPG cache disabled, will try API")
    except Exception as e:
        debug_log("[play_live_channel] SQLite EPG error: %s" % str(e))
        skip_online_epg = False
    finally:
        if dbConn:
            dbConn.close()

    if not skip_online_epg:
        # Load EPG from new API
        debug_log("[play_live_channel] Loading EPG from API for channel_id=%s" % channel_id)
        try:
            epg_items = cbAdapter.get_short_epg(channel_id, size=info_epg_limit)
            debug_log("[play_live_channel] API returned %d EPG items" % len(epg_items))
            first_item = True
            for short_epg in epg_items:
                plot_epg += "[CR]%s-%s: %s" % (short_epg["t_time"], short_epg["t_time_to"], short_epg["name"])
                if first_item:
                    first_descr = short_epg.get("descr", "")
                    first_item = False
        except Exception as e:
            debug_log("[play_live_channel] API EPG error: %s" % str(e))
            import traceback

            debug_log("[play_live_channel] API EPG traceback: %s" % traceback.format_exc())

    # Add description of current program if available
    if first_descr:
        plot_epg = "[COLOR white]%s[/COLOR][CR][CR]%s" % (first_descr.strip(), plot_epg)

    debug_log(
        "[play_live_channel] EPG plot built, descr=%s" % ("yes (%d chars)" % len(first_descr) if first_descr else "no")
    )

    item.setInfo(type="video", infoLabels={"Title": name, "Plot": plot_epg})
    xbmcplugin.setResolvedUrl(addon_handle, True, item)


# invoking time picker dialog to start playing archive from any given time
def timepick_live_channel(play_cmd, name, date=""):

    # play_cmd now contains the direct stream URL
    stream_url = urlUnquote(play_cmd)

    if len(str(date)) > 5:
        start_date = re.sub(r"(\d{4})-(\d{1,2})-(\d{1,2})", r"\3/\2/\1", date)
        input_date = xbmcgui.Dialog().numeric(1, get_txt(30051), start_date).replace(" ", "")
    else:
        input_date = xbmcgui.Dialog().numeric(1, get_txt(30051)).replace(" ", "")

    if len(re.findall(r"/", input_date)) > 1:
        input_date_split = filter(None, input_date.split("/"))
        input_date = "/".join(map(lambda x: (len(x.strip()) < 2 and "0" + x.strip()) or x, input_date_split))

        input_time = xbmcgui.Dialog().numeric(2, get_txt(30052))
        if len(re.findall(r":", input_time)) > 0:
            input_time_split = filter(None, input_time.split(":"))
            input_time = ":".join(map(lambda x: (len(x.strip()) < 2 and "0" + x.strip()) or x, input_time_split))
        else:
            return False
    else:
        return False

    selected_time = datetime.datetime.fromtimestamp(
        time.mktime(time.strptime(f"{input_date} {input_time}", "%d/%m/%Y %H:%M"))
    ) - datetime.timedelta(seconds=0)
    selected_time_human = selected_time.strftime("%Y-%m-%d %H:%M")
    unixtime = int(time.mktime(selected_time.timetuple()))

    unix_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    unix_now = int(unix_now_obj.days * 86400 + unix_now_obj.seconds)

    duration = 3600

    if unixtime > unix_now:
        show_msg(get_txt(30053), 2000)
        return False

    item_name = "[COLOR green][B]%s[/B][/COLOR] [COLOR orange]%s[/COLOR]" % (name, selected_time_human)

    debug_log("Requesting time: " + selected_time_human)

    # Build archive URL from stream URL
    stream_url_live = cbAdapter.build_archive_url(stream_url, unixtime, duration)

    item = xbmcgui.ListItem(item_name, offscreen=True)
    item.setInfo("video", {"Title": item_name, "mediatype": "video"})

    video_player = xbmc.Player()
    video_player.play(stream_url_live, item)


# generating date folders as symlinks to access EPG for the requested channel
def archive_channel_dates(channel_id, name, depth, channel_cmd, logo_png):

    # Save previous windows item position
    try:
        curr_item = xbmc.getInfoLabel("Container(id).CurrentItem")
        if (xbmcgui.getCurrentWindowId() == int(__addon__.getSetting("last_window"))) and (curr_item != 0):
            if int(__addon__.getSetting("last_channel")) == 0:
                __addon__.setSetting("last_channel", curr_item)
    except Exception:
        pass

    debug_log("Displaying date symlinks for channel: " + name)
    debug_log("[archive_channel_dates] Received depth parameter: %s" % depth)

    if addon_handle < 1:
        show_msg("%s. %s" % (get_txt(30061), get_txt(30062)), 2000)
        return False

    # depth is already in days, not hours
    archive_days = int(depth)
    debug_log("[archive_channel_dates] archive_days after int(): %d" % archive_days)

    # logo_png is now a full URL (or URL-encoded)
    logo_url = urlUnquote(logo_png) if logo_png else ""

    def rusWeekDayName(weekday):
        days = [
            get_txt(30054),
            get_txt(30055),
            get_txt(30056),
            get_txt(30057),
            get_txt(30058),
            get_txt(30059),
            get_txt(30060),
        ]
        return days[["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(weekday)]

    for archive_day in range(0, archive_days):
        unixtime_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
        unixtime_now = int(unixtime_now_obj.days * 86400 + unixtime_now_obj.seconds)

        date_obj = datetime.datetime.fromtimestamp(unixtime_now) - datetime.timedelta(days=archive_day)
        archive_date_human = date_obj.strftime("%Y-%m-%d")

        try:
            archive_day_name = rusWeekDayName(date_obj.strftime("%A"))
        except:
            archive_day_name = date_obj.strftime("%A")

        name1 = "[COLOR burlywood]%s[/COLOR] (%s)" % (archive_date_human, archive_day_name)

        url = sys.argv[
            0
        ] + "?mode=archive_channel_epg&channel_id=%s&date=%s&name=%s&play_cmd=%s&logo_png=%s&direct=0" % (
            channel_id,
            archive_date_human,
            re.sub("=", "", base64.urlsafe_b64encode(name.encode("utf-8")).decode("utf-8")),
            channel_cmd,
            urlQuote(logo_url),
        )

        item = xbmcgui.ListItem(name1, offscreen=True)
        item.setInfo(type="video", infoLabels={"title": name1, "plot": name.strip()})

        try:
            item.setArt({"poster": logo_url, "fanart": os.path.join(FANART_PATH, "archive_01.jpg")})
        except:
            item.setArt({"poster": tv_poster_file, "fanart": os.path.join(FANART_PATH, "archive_01.jpg")})

        xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    xbmcplugin.setContent(addon_handle, "files")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)


# Show fast EPG
def epg_show(channel_id, channel_title):

    debug_log("Activate fast EPG window for channel [%s] " % (channel_id))

    # WINDOW_DIALOG_TEXT_VIEWER = 10147
    xbmc.executebuiltin("ActivateWindow(%d)" % 10147)
    window = xbmcgui.Window(10147)

    unixtime_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    unixtime_now = int(unixtime_now_obj.days * 86400 + unixtime_now_obj.seconds)
    channel_data = []

    for epg_day in range(0, 2):
        date_obj = datetime.datetime.fromtimestamp(unixtime_now) + datetime.timedelta(days=epg_day)
        archive_date_human = date_obj.strftime("%Y-%m-%d")

        try:
            day_epg = cbAdapter.get_day_epg(channel_id, date=archive_date_human)
            if day_epg:
                channel_data += day_epg
        except:
            continue

    if not channel_data:
        show_msg(get_txt(30065), 2000)
        return

    # Sort by stop_timestamp
    try:
        channel_data = sorted(channel_data, key=lambda arr: int(arr.get("stop_timestamp", 0)))
    except:
        pass

    try:
        chName = "%s" % (
            (sys.version_info[0] >= 3 and urlUnquote(channel_title)) or unicode(urlUnquote(channel_title), "utf-8")
        )
    except:
        chName = ""

    text = ""
    date_str = ""

    def dayStepNames(step_index):
        daysAre = [get_txt(30120), get_txt(30121), get_txt(30122)]
        return daysAre[
            [
                (datetime.datetime.fromtimestamp(unixtime_now) + datetime.timedelta(days=0)).strftime("%d-%m-%Y"),
                (datetime.datetime.fromtimestamp(unixtime_now) + datetime.timedelta(days=1)).strftime("%d-%m-%Y"),
                (datetime.datetime.fromtimestamp(unixtime_now) + datetime.timedelta(days=2)).strftime("%d-%m-%Y"),
            ].index(step_index)
        ]

    for epg_data in channel_data:
        # Skip passed events
        ts = int(epg_data.get("stop_timestamp", 0))
        if ts < unixtime_now:
            continue

        # Get date from start_timestamp, converted to user timezone
        start_ts = int(epg_data.get("start_timestamp", 0))
        if start_ts:
            epg_date_str = cbAdapter._ts_to_local_str(start_ts, "%d-%m-%Y")
            if not epg_date_str:
                continue
        else:
            continue

        if date_str != epg_date_str:
            date_str = epg_date_str
            try:
                day_step = " (%s)" % (dayStepNames(date_str))
            except:
                day_step = ""

            if text != "":
                text += "\r\n\r\n"
            text += "[B]%s[/B]%s" % (date_str, day_step)
            text += "\r\n%s" % ("~" * 40)

        epg_event_title = epg_data.get("name", "")
        start_time = epg_data.get("t_time", "")
        end_time = epg_data.get("t_time_to", "")
        text += "\r\n%s - %s | %s " % (start_time, end_time, epg_event_title)

    xbmc.sleep(100)
    window.getControl(1).setLabel(chName)
    window.getControl(5).setText(text)


# generating a list of channel's EPG events for the requested date
def archive_channel_epg(channel_id, date, name, channel_cmd, logo_png, direct):

    try:
        curr_item = xbmc.getInfoLabel("Container(id).CurrentItem")
        if xbmcgui.getCurrentWindowId() == int(__addon__.getSetting("last_window")) and curr_item != 0:
            if int(__addon__.getSetting("last_channel")) == 0:
                __addon__.setSetting("last_channel", curr_item)
    except Exception:
        pass

    debug_log("Printing channel's [%s] EPG for date %s" % (channel_id, date))

    dialog = xbmcgui.DialogProgress()
    dialog.create(__addonname__, get_txt(30063))

    # Try to get EPG from SQLite cache first
    channel_data = None
    use_sqlite_cache = str(__addon__.getSetting("epg_cache")) == "true"

    if use_sqlite_cache and os.path.exists(epgFile):
        import time

        cache_start_time = time.time()
        debug_log("[EPG_CACHE] Trying SQLite cache for channel=%s, date=%s" % (channel_id, date))

        dbConn = None
        try:
            # Calculate timestamp range for the requested date
            date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
            start_ts = int((date_obj - datetime.datetime(1970, 1, 1)).total_seconds())
            end_ts = start_ts + 86400  # +24 hours

            dbConn = sqlite.connect(epgFile, timeout=10)
            if dbConn is None:
                raise Exception("sqlite.connect returned None")
            dbCursor = dbConn.cursor()
            try:
                dbCursor.execute("PRAGMA journal_mode=WAL")
            except:
                pass

            run_sql = """SELECT epg_json
                      FROM epg
                      WHERE ch_id = ?
                        AND stop_timestamp >= ?
                        AND stop_timestamp < ?
                      ORDER BY stop_timestamp"""

            dbCursor.execute(run_sql, (channel_id, start_ts, end_ts))
            rows = dbCursor.fetchall()

            if rows and len(rows) > 0:
                channel_data = []
                for row in rows:
                    try:
                        epg_item = json.loads(row[0])
                        # Recalculate display time from timestamps using addon timezone
                        cached_start_ts = epg_item.get("start_timestamp", "")
                        cached_stop_ts = epg_item.get("stop_timestamp", "")
                        if cached_start_ts:
                            recalc = cbAdapter._ts_to_local_str(cached_start_ts)
                            if recalc:
                                epg_item["t_time"] = recalc
                        if cached_stop_ts:
                            recalc = cbAdapter._ts_to_local_str(cached_stop_ts)
                            if recalc:
                                epg_item["t_time_to"] = recalc
                        channel_data.append(epg_item)
                    except:
                        pass

                cache_elapsed = time.time() - cache_start_time
                debug_log("[EPG_CACHE] SQLite HIT: %d items in %.3f sec" % (len(channel_data), cache_elapsed))
            else:
                cache_elapsed = time.time() - cache_start_time
                debug_log("[EPG_CACHE] SQLite MISS: no data in %.3f sec" % cache_elapsed)
                channel_data = None

        except Exception as e:
            cache_elapsed = time.time() - cache_start_time
            debug_log("[EPG_CACHE] SQLite error after %.3f sec: %s" % (cache_elapsed, str(e)))
            channel_data = None
        finally:
            if dbConn:
                try:
                    dbConn.close()
                except:
                    pass

    # If no cache or cache miss, fetch from API
    if channel_data is None:
        import time

        api_start_time = time.time()
        debug_log("[EPG_TIMING] Fetching EPG from API for channel=%s, date=%s" % (channel_id, date))

        try:
            channel_data = cbAdapter.get_day_epg(channel_id, date=date)
            api_elapsed = time.time() - api_start_time
            debug_log(
                "[EPG_TIMING] API fetch completed in %.3f seconds, items: %d"
                % (api_elapsed, len(channel_data) if channel_data else 0)
            )
        except Exception as e:
            api_elapsed = time.time() - api_start_time
            debug_log("[EPG_TIMING] API fetch failed after %.3f seconds: %s" % (api_elapsed, str(e)))
            channel_data = []

    dialog.close()

    if not channel_data:
        debug_log("No EPG data available for channel %s on %s" % (channel_id, date))
        show_msg(get_txt(30065), 2000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    # Sort by stop_timestamp
    try:
        channel_data = sorted(channel_data, key=lambda arr: int(arr.get("stop_timestamp", 0)))
    except:
        pass

    # logo_png is now a full URL
    logo_url = urlUnquote(logo_png) if logo_png else ""
    # channel_cmd is now the direct stream URL
    stream_url = urlUnquote(channel_cmd) if channel_cmd else ""

    listing = []
    is_folder = False
    future_events = 0
    items_counter = 1
    divider_position = 0
    thumb_noplay_file = os.path.join(__addondir__, "resources", "clock.png")
    thumb_divider = os.path.join(__addondir__, "resources", "direction.png")

    unixtime_now_obj = datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)
    unixtime_now = int(unixtime_now_obj.days * 86400 + unixtime_now_obj.seconds)

    for epg_data in channel_data:
        epg_event_title = epg_data.get("name", "")
        start_date = str(date)
        start_time = epg_data.get("t_time", "")
        end_time = epg_data.get("t_time_to", "")
        start_ts = int(epg_data.get("start_timestamp", 0))
        stop_ts = int(epg_data.get("stop_timestamp", 0))
        duration = epg_data.get("duration", 0)
        if not duration and stop_ts and start_ts:
            duration = stop_ts - start_ts
        event_duration = str(duration)

        # Build archive URL using adapter
        archive_url = cbAdapter.build_archive_url(stream_url, start_ts, duration, dvr_uri=epg_data.get("dvr_uri"))
        url = sys.argv[0] + "?mode=play_archive_channel&play_cmd=%s&unixtime=%s&duration=%s" % (
            urlQuote(archive_url),
            str(start_ts),
            event_duration,
        )

        # Check if event is in the past (playable) or future
        is_past = stop_ts < unixtime_now

        if not is_past:
            # Not yet playable
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
            "[COLOR white][B]%s[/B][/COLOR][CR][COLOR rosybrown][B]%s[/B][/COLOR][CR]%s[CR][COLOR burlywood]%s[/COLOR]"
            % (start_date, name, epg_event_title.strip(), descr.strip())
        )
        item.setInfo(type="video", infoLabels={"title": item_name, "mediatype": "video", "plot": plot_desc})

        try:
            tham_tools = str(__addon__.getSetting("tham_tools")) == "true"
        except:
            tham_tools = False

        if not is_past:
            item.setArt(
                {"poster": logo_url, "thumb": thumb_noplay_file, "fanart": os.path.join(FANART_PATH, "archive_01.jpg")}
            )
            item.setProperty("IsPlayable", "false")
        else:
            item.setArt(
                {"poster": logo_url, "thumb": thumb_play_file, "fanart": os.path.join(FANART_PATH, "archive_01.jpg")}
            )
            item.setProperty("IsPlayable", "true")

            # Build context menu
            context_menu = []
            context_menu.append(("%s" % get_txt(30128), "RunPlugin(%s?mode=get_stream_servers)" % (sys.argv[0])))

            if tham_tools:
                context_menu.append(
                    (
                        "Download",
                        "RunPlugin(%s?mode=download_archive_record&play_cmd=%s&unixtime=%s&duration=%s)"
                        % (sys.argv[0], urlQuote(archive_url), str(start_ts), event_duration),
                    )
                )

            item.addContextMenuItems(items=context_menu, replaceItems=True)

        if future_events == 1:
            item_name_extra = "[COLOR lightsteelblue][B]%s:[/B][/COLOR]" % get_txt(30066)
            item_extra = xbmcgui.ListItem(item_name_extra, offscreen=True)
            item_extra.setArt(
                {"poster": logo_url, "thumb": thumb_divider, "fanart": os.path.join(FANART_PATH, "archive_01.jpg")}
            )
            item_extra.setProperty("IsPlayable", "false")
            listing.append((url, item_extra, is_folder))
            divider_position = items_counter

        listing.append((url, item, is_folder))
        items_counter += 1

    xbmcplugin.addDirectoryItems(addon_handle, listing, totalItems=len(listing))

    xbmcplugin.setContent(addon_handle, "videos")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)
    # Enable caching for EPG to avoid reloading on every navigation
    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)

    xbmc.sleep(250)
    win = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    cid = win.getFocusId()
    try:
        if int(xbmc.getInfoLabel("Container(id).CurrentItem")) == 0:
            xbmc.executebuiltin("SetFocus(%s, %s, absolute)" % (cid, divider_position - 1))
    except Exception:
        pass


# launching stream of an archived event
def play_archive_channel(play_cmd, unixtime, duration):

    # play_cmd now contains the pre-built archive URL
    stream_url_live = urlUnquote(play_cmd)
    debug_log("Playing archive URL: " + stream_url_live)

    item = xbmcgui.ListItem(path=stream_url_live, offscreen=True)
    xbmcplugin.setResolvedUrl(addon_handle, True, item)


# Download record
def download_archive_record(play_cmd, unixtime, duration):

    # play_cmd now contains the pre-built archive URL
    stream_url_live = urlUnquote(play_cmd)
    debug_log("Downloading archive URL: " + stream_url_live)
    debug_log("Archive stream URL: " + stream_url_live)

    ts_url_list = []
    regex2 = re.search("(^http://.+/).+.m3u8.*", stream_url_live)
    if not regex2:
        show_msg("ERROR: Can not parse stream URL", 3000)
        return False
    baseUrl = regex2.group(1)

    # get first playlist
    new_Url = None
    with urllib2.urlopen(stream_url_live) as f:
        m3u8Init = f.read().decode("utf-8").split("\n")
        for content in m3u8Init:
            if content.startswith("tracks"):
                new_Url = baseUrl + content
                debug_log("Archive: Found new m3u8 URL: " + new_Url)

    if new_Url:
        with urllib2.urlopen(new_Url) as f:
            m3u8Contents = f.read().decode("utf-8").split("\n")
            for content in m3u8Contents:
                ts_line = re.search("(^http://.+ts.+)", content)
                if ts_line != None:
                    ts_url_list.append(ts_line.group(1))
                    debug_log("Archive: Found TS segment: " + ts_line.group(1))

    now_time = datetime.datetime.utcnow()
    now_time_str = now_time.strftime("%Y-%m-%d-%H-%M-%S")

    download_dir = now_time_str + "_dl"
    download_merge_dir = now_time_str + "_merge"

    download_path = os.path.join(__addonTempData__, download_dir)
    download_merge_path = os.path.join(__addonTempData__, download_merge_dir)

    mode = 0o666
    os.mkdir(download_path, mode)
    os.mkdir(download_merge_path, mode)

    downloadTsVideo(download_path, ts_url_list)
    mergeTsVideo(download_path, download_merge_path)


# Play live event from the beginning
def play_live_event_from_start(play_cmd, name, ts):

    # Save previous windows item position
    try:
        curr_item = xbmc.getInfoLabel("Container(id).CurrentItem")
        if curr_item != 0:
            __addon__.setSetting("last_channel", curr_item)
    except Exception:
        pass

    debug_log("Playing live event from start, ts: " + str(ts))

    # play_cmd now contains the direct stream URL
    stream_url = urlUnquote(play_cmd)

    # Build archive URL for the event start
    stream_url_live = cbAdapter.build_archive_url(stream_url, ts, 3600)

    xbmc.executebuiltin("PlayMedia(%s, resume)" % (stream_url_live))


# load Video on Demand (vod) aka Mediateka


def vod_start():
    # xbmc.log("DBG %s: %s" % (datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], 'start-a'), level=xbmc.LOGINFO);

    name = "[COLOR white][B]%s[/B][/COLOR]" % get_txt(30067)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {"poster": vod_poster_file, "thumb": thumb_browse_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
    )
    url = sys.argv[0] + "?mode=vod_get_category"
    xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    name = "[COLOR white][B]%s[/B][/COLOR]" % get_txt(30107)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {"poster": vod_poster_file, "thumb": thumb_browse_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
    )
    url = sys.argv[0] + "?mode=vod_search_page"
    xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    # Watch History
    name = "[COLOR white][B]%s[/B][/COLOR]" % get_txt(30143)
    item = xbmcgui.ListItem(name, offscreen=True)
    item.setArt(
        {"poster": vod_poster_file, "thumb": thumb_browse_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
    )
    url = sys.argv[0] + "?mode=vod_watch_history"
    xbmcplugin.addDirectoryItem(addon_handle, url, item, True)

    xbmcplugin.setContent(addon_handle, "files")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)


def vod_search_page():

    # search_list = ['Name/Actor/Director/Year', 'Category', 'Genre', 'Years', 'ABC']
    search_list = [get_txt(30109), get_txt(30110)]
    search_by = ["vod_search", "vod_year"]
    dialog = xbmcgui.Dialog()
    ret = dialog.select(get_txt(30111), search_list)

    if ret == None or ret < 0:
        xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
        return

    dialog = xbmcgui.Dialog()

    if search_by[ret] == "vod_year":
        search_word = dialog.input(get_txt(30112), type=xbmcgui.INPUT_NUMERIC)
    else:
        search_word = dialog.input(get_txt(30113), type=xbmcgui.INPUT_ALPHANUM)

    if not search_word:
        xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
        return

    try:
        if search_by[ret] == "vod_year":
            if int(search_word) < 1900 or int(search_word) > 2050:
                show_msg(get_txt(30114), 3000)
                xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
                return
        else:
            if len(search_word) < 3:
                show_msg(get_txt(30115), 3000)
                xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
                return
    except:
        show_msg(get_txt(30116), 3000)
        xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
        return

    if sys.version_info[0] >= 3:
        search_word = urlQuote(search_word, safe="")
    else:
        search_word = unicode(search_word, "utf-8")
        search_word = urlQuote(search_word.encode("utf-8"), safe="")

    nav_url = "%s?mode=vod_get_ordered_list&page_nr=%s&sortby=%s&%s=%s" % (
        sys.argv[0],
        1,
        "name",
        search_by[ret],
        search_word,
    )
    debug_log("[vod_search_page] Search params: search_by=%s, search_word=%s" % (search_by[ret], search_word))
    debug_log("[vod_search_page] Calling vod_get_ordered_list directly instead of Container.Update")

    # Call vod_get_ordered_list directly - Container.Update causes issues in Kodi Matrix
    vod_get_ordered_list(
        cat_id="*",
        genre_id="*",
        page_nr=1,
        sortby="name",
        vod_search=search_word if search_by[ret] == "vod_search" else None,
        vod_year=search_word if search_by[ret] == "vod_year" else None,
    )


def vod_watch_history():
    """Display watch history."""
    debug_log("[vod_watch_history] Loading watch history")

    history = load_watch_history()

    if not history:
        # Show empty message
        show_msg(get_txt(30146), 3000)  # "History is empty"
        xbmcplugin.endOfDirectory(addon_handle)
        return

    debug_log("[vod_watch_history] Found %d items in history" % len(history))

    for item_data in history:
        try:
            movie_id = item_data.get("movie_id", "")
            season_id = item_data.get("season_id", "0")
            episode_id = item_data.get("episode_id", "0")
            title = item_data.get("title", "")
            season_name = item_data.get("season_name", "")
            episode_name = item_data.get("episode_name", "")
            episode_number = item_data.get("episode_number", "")
            poster = item_data.get("poster", "")
            content_type = item_data.get("type", "movie")

            # Build display name
            if content_type == "episode":
                # Format: "Series Title - Season 1. Episode 5: Episode Title"
                display_name = title

                # Add season info
                if season_name:
                    display_name += " - %s" % season_name
                elif season_id and int(season_id) > 0:
                    # Try to extract season number from season_id or use it directly
                    display_name += " - %s %s" % (get_txt(30148), season_id)  # "Season"

                # Add episode info
                if episode_name:
                    if episode_number and not episode_name.startswith(get_txt(30149)):
                        # Only add "Episode N:" prefix if episode_name is a real name, not generated "Episode N"
                        display_name += ". %s %s: %s" % (get_txt(30149), episode_number, episode_name)  # "Episode"
                    else:
                        display_name += ". %s" % episode_name
                elif episode_number:
                    display_name += ". %s %s" % (get_txt(30149), episode_number)  # "Episode"
            else:
                # For movies, just use title
                display_name = title

            # Create ListItem
            list_item = xbmcgui.ListItem(display_name, offscreen=True)

            # Set artwork
            if poster:
                list_item.setArt({"poster": poster, "thumb": poster, "fanart": poster})
            else:
                list_item.setArt(
                    {
                        "poster": vod_poster_file,
                        "thumb": thumb_play_file,
                        "fanart": os.path.join(FANART_PATH, "vod_03.jpg"),
                    }
                )

            # Get description from VOD cache, fallback to API
            plot_text = ""
            try:
                cached_data = vod_cache_get(movie_id)

                # If not in cache, try loading from API
                if not cached_data and movie_id:
                    debug_log("[vod_watch_history] Cache miss for movie_id=%s, loading from API" % movie_id)
                    try:
                        video_info = cbAPI.get_video(movie_id)
                        if isinstance(video_info, dict) and "data" in video_info:
                            cached_data = video_info["data"]
                        elif isinstance(video_info, dict):
                            cached_data = video_info
                        # Save to cache for next time
                        if cached_data:
                            vod_cache_set(movie_id, cached_data)
                            debug_log("[vod_watch_history] Loaded and cached movie_id=%s from API" % movie_id)
                    except Exception as api_e:
                        debug_log("[vod_watch_history] API load failed for movie_id=%s: %s" % (movie_id, str(api_e)))

                if cached_data and isinstance(cached_data, dict):
                    description = cached_data.get("description", cached_data.get("descr", ""))
                    year = cached_data.get("year", "")
                    rating = cached_data.get("rating", cached_data.get("rating_imdb", ""))
                    country = cached_data.get("country", "")

                    parts = []
                    if year:
                        parts.append(str(year))
                    if country:
                        parts.append(str(country))
                    if rating:
                        parts.append("IMDb: %s" % str(rating))

                    if parts:
                        plot_text = "[COLOR burlywood]%s[/COLOR]" % " | ".join(parts)
                    if description:
                        if plot_text:
                            plot_text += "[CR][CR]"
                        plot_text += str(description)

                    debug_log(
                        "[vod_watch_history] movie_id=%s plot: year=%s, country=%s, rating=%s, descr=%s"
                        % (
                            movie_id,
                            year,
                            country,
                            rating,
                            "yes (%d chars)" % len(description) if description else "no",
                        )
                    )
                else:
                    debug_log("[vod_watch_history] No data available for movie_id=%s" % movie_id)
            except Exception as e:
                debug_log("[vod_watch_history] Error getting data for movie_id=%s: %s" % (movie_id, str(e)))

            # Set video info with plot
            info_labels = {
                "title": display_name,
                "mediatype": "video",
            }
            if plot_text:
                info_labels["plot"] = plot_text
            list_item.setInfo(type="video", infoLabels=info_labels)

            # Episodes navigate to season's episode list; movies play directly
            if content_type == "episode" and season_id and int(season_id) > 0:
                list_item.setProperty("IsPlayable", "false")
                url = (
                    "%s?mode=vod_get_episodes&movie_id=%s&season_id=%s&movie_name=%s&season_name=%s&poster_url=%s&focus_episode_id=%s"
                    % (
                        sys.argv[0],
                        movie_id,
                        season_id,
                        urlQuote(title.encode("utf-8"), safe=""),
                        urlQuote(season_name.encode("utf-8"), safe="") if season_name else "-",
                        urlQuote(poster, safe="") if poster else "",
                        episode_id,
                    )
                )
                is_folder = True
            else:
                list_item.setProperty("IsPlayable", "true")
                url = "%s?mode=vod_play_movie&movie_id=%s&season_id=%s&episode_id=%s&movie_name=%s&season_name=%s" % (
                    sys.argv[0],
                    movie_id,
                    season_id,
                    episode_id,
                    urlQuote(title.encode("utf-8"), safe=""),
                    urlQuote(season_name.encode("utf-8"), safe="") if season_name else "-",
                )
                is_folder = False

            # Build context menu
            context_menu = []

            # Remove from history
            context_menu.append(
                (
                    get_txt(30144),  # "Remove from history"
                    "RunPlugin(%s?mode=vod_history_remove&movie_id=%s&season_id=%s&episode_id=%s)"
                    % (sys.argv[0], movie_id, season_id, episode_id),
                )
            )

            # Clear all history
            context_menu.append(
                (
                    get_txt(30145),  # "Clear all history"
                    "RunPlugin(%s?mode=vod_history_clear)" % sys.argv[0],
                )
            )

            list_item.addContextMenuItems(items=context_menu, replaceItems=False)

            # Add to directory (episodes are folders, movies are playable)
            xbmcplugin.addDirectoryItem(addon_handle, url, list_item, is_folder)

        except Exception as e:
            debug_log("[vod_watch_history] Error processing item: %s" % str(e))
            import traceback

            debug_log("[vod_watch_history] Traceback: %s" % traceback.format_exc())

    xbmcplugin.setContent(addon_handle, "movies")
    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)


def vod_history_remove(movie_id, season_id, episode_id):
    """Remove item from watch history."""
    debug_log(
        "[vod_history_remove] Removing: movie_id=%s, season_id=%s, episode_id=%s" % (movie_id, season_id, episode_id)
    )

    if remove_from_watch_history(movie_id, season_id, episode_id):
        show_msg(get_txt(30150), 2000)  # "Removed from history"
        xbmc.executebuiltin("Container.Refresh")
    else:
        show_msg(get_txt(30033), 2000)  # "Something went wrong"


def vod_history_clear():
    """Clear all watch history."""
    debug_log("[vod_history_clear] Clearing all history")

    # Ask for confirmation
    dialog = xbmcgui.Dialog()
    if dialog.yesno(get_txt(30145), get_txt(30151)):  # "Clear all history", "Are you sure?"
        if clear_watch_history():
            show_msg(get_txt(30147), 2000)  # "History cleared"
            xbmc.executebuiltin("Container.Refresh")
        else:
            show_msg(get_txt(30033), 2000)  # "Something went wrong"
    # xbmc.executebuiltin( 'Container.Update("%s?mode=vod_get_ordered_list&page_nr=%s&sortby=%s&%s=%s")' % (sys.argv[0], 1, "name", search_by[ret], search_word) )

    # bug: https://forum.kodi.tv/showthread.php?tid=344882
    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)


def vod_get_category():

    xxx_enabled = (str(__addon__.getSetting("xxx_code")) == XXX_CODE and True) or False

    try:
        info = cbAPI.get_vod_categories()
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
    except:
        xbmcplugin.endOfDirectory(addon_handle)
        return

    if not info:
        xbmcplugin.endOfDirectory(addon_handle)
        return

    for category in info:
        cat_title = category.get("name", category.get("title", ""))
        cat_censored = int(category.get("adult", 0)) == 1

        if not xxx_enabled and cat_censored:
            continue
        item_name = "[COLOR white][B]%s[/B][/COLOR]" % (cat_title)

        url = "%s?mode=vod_get_category_genres&cat_id=%s&cat_alias=%s" % (
            sys.argv[0],
            category["id"],
            category.get("alias", ""),
        )
        item = xbmcgui.ListItem(item_name, offscreen=True)
        item.setArt(
            {"poster": vod_poster_file, "thumb": thumb_browse_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
        )

        xbmcplugin.addDirectoryItem(addon_handle, url, item, isFolder=True)

    xbmcplugin.setContent(addon_handle, "files")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)


# Get genres
def vod_get_category_genres(cat_id, cat_alias):

    try:
        info = cbAPI.get_vod_category_genres(cat_id)
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
    except:
        xbmcplugin.endOfDirectory(addon_handle)
        return

    if not info:
        # If no genres, go directly to content list
        xbmc.executebuiltin(
            'Container.Update("%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=*&page_nr=1&sortby=added")'
            % (sys.argv[0], cat_id)
        )
        xbmcplugin.endOfDirectory(addon_handle)
        return

    # Add "All" option first
    item_name = "[COLOR white][B]%s[/B][/COLOR]" % get_txt(30108)
    url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=*&page_nr=1&sortby=%s" % (sys.argv[0], cat_id, "added")
    item = xbmcgui.ListItem(item_name, offscreen=True)
    item.setArt(
        {"poster": vod_poster_file, "thumb": thumb_browse_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
    )
    xbmcplugin.addDirectoryItem(addon_handle, url, item, isFolder=True)

    for genre in info:
        genre_title = genre.get("name", genre.get("title", ""))
        genre_id = genre.get("id", "")

        item_name = "[COLOR white][B]%s[/B][/COLOR]" % (genre_title)
        url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=%s&page_nr=1&sortby=%s" % (
            sys.argv[0],
            cat_id,
            str(genre_id),
            "added",
        )

        item = xbmcgui.ListItem(item_name, offscreen=True)
        item.setArt(
            {"poster": vod_poster_file, "thumb": thumb_browse_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
        )

        xbmcplugin.addDirectoryItem(addon_handle, url, item, isFolder=True)

    xbmcplugin.setContent(addon_handle, "files")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)


# Get VOD single page
def get_vod_page(params_smart, page_nr):
    params = params_smart + "&p=" + str(page_nr)
    try:
        info = retrieve_json_list(params)["js"]
    except:
        info = None

    return info


# Get movies list
def vod_get_ordered_list(cat_id, genre_id, page_nr, sortby, vod_search, vod_year):

    xxx_enabled = (str(__addon__.getSetting("xxx_code")) == XXX_CODE and True) or False
    vod_preload_enabled = str(__addon__.getSetting("vod_preload_metadata")) == "true"

    listing = []
    movie_data = []
    page_nr = int(page_nr)

    func_smart = "cat_id=%s&genre_id=%s" % (cat_id, genre_id)

    dialog = xbmcgui.DialogProgress()
    dialog.create(__addonname__, "%s..." % get_txt(30068))

    try:
        if vod_search != None:
            search_term = (sys.version_info[0] >= 3 and urlUnquote(vod_search)) or unicode(
                urlUnquote(vod_search), "utf-8"
            )
            raw_data = cbAPI.search_by_name(search_term, page=page_nr)
            func_smart = "vod_search=%s" % vod_search
            debug_log('[vod_get_ordered_list] Search mode: "%s", page=%d' % (search_term, page_nr))
        elif vod_year != None:
            year_val = urlUnquote(vod_year)
            raw_data = cbAPI.filter_by_year(year_val, page=page_nr)
            func_smart = "vod_year=%s" % vod_year
            debug_log("[vod_get_ordered_list] Year filter mode: %s, page=%d" % (year_val, page_nr))
        elif genre_id != "*" and genre_id != "0":
            raw_data = cbAPI.get_vod_by_genre(genre_id, page=page_nr)
            debug_log("[vod_get_ordered_list] Genre mode: genre_id=%s, page=%d" % (genre_id, page_nr))
        else:
            raw_data = cbAPI.get_vod_category_content(cat_id, page=page_nr)
            debug_log(
                "[vod_get_ordered_list] Category mode: cat_id=%s, genre_id=%s (All genres), page=%d"
                % (cat_id, genre_id, page_nr)
            )

        # Extract data and pagination meta from API response
        if isinstance(raw_data, dict) and "data" in raw_data:
            movie_data = raw_data["data"]
            api_meta = raw_data.get("meta", {})
        elif isinstance(raw_data, list):
            movie_data = raw_data
            api_meta = {}
        else:
            movie_data = []
            api_meta = {}

        debug_log("[vod_get_ordered_list] Received %d items from API (page %d)" % (len(movie_data), page_nr))
    except Exception as e:
        debug_log("VOD fetch error: %s" % str(e))

    if not movie_data:
        dialog.close()
        xbmcplugin.endOfDirectory(addon_handle)
        return

    # Filter adult content
    if not xxx_enabled:
        movie_data = [m for m in movie_data if not int(m.get("adult", 0)) == 1]

    # Preload metadata with cache
    detailed_metadata = {}
    if vod_preload_enabled and movie_data:
        debug_log("VOD preload: checking cache for %d movies" % len(movie_data))

        # Get movie IDs
        movie_ids = [str(m.get("id")) for m in movie_data if m.get("id")]

        # Check cache first
        cached_data = vod_cache_get_multiple(movie_ids)
        debug_log("VOD preload: found %d/%d in cache" % (len(cached_data), len(movie_ids)))

        # Find movies not in cache
        missing_ids = [mid for mid in movie_ids if mid not in cached_data]

        if missing_ids:
            import time

            start_time = time.time()
            debug_log("VOD preload: loading %d movies from API" % len(missing_ids))
            dialog.update(0, "%s (%d/%d)..." % (get_txt(30068), 0, len(missing_ids)))

            # Load missing movies (with threading for speed)
            try:
                from concurrent.futures import ThreadPoolExecutor, as_completed

                debug_log("VOD preload: using ThreadPoolExecutor with 5 workers")

                # Create API client with shorter timeout for preloading (10 seconds)
                # This prevents slow movies from blocking the entire preload process
                preload_api = CbillingAPI(base_url=config___api_url, public_key=config___public_key, timeout=10)

                def load_movie(movie_id):
                    try:
                        movie_start = time.time()
                        video_info = preload_api.get_video(movie_id)
                        movie_time = time.time() - movie_start
                        debug_log("VOD preload: loaded movie %s in %.2f sec" % (movie_id, movie_time))
                        if isinstance(video_info, dict) and "data" in video_info:
                            return (movie_id, video_info["data"])
                        return (movie_id, video_info)
                    except CbillingTimeoutError:
                        movie_time = time.time() - movie_start
                        debug_log("VOD preload: timeout loading movie %s after %.2f sec" % (movie_id, movie_time))
                        return (movie_id, None)
                    except Exception as e:
                        movie_time = time.time() - movie_start
                        debug_log(
                            "VOD preload: failed to load movie %s after %.2f sec: %s" % (movie_id, movie_time, str(e))
                        )
                        return (movie_id, None)

                loaded_count = 0
                new_cache_data = {}
                timeout_count = 0

                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {executor.submit(load_movie, mid): mid for mid in missing_ids}

                    for future in as_completed(futures):
                        loaded_count += 1
                        if loaded_count % 5 == 0 or loaded_count == len(missing_ids):
                            dialog.update(
                                int(loaded_count * 100 / len(missing_ids)),
                                "%s (%d/%d)..." % (get_txt(30068), loaded_count, len(missing_ids)),
                            )

                        movie_id, data = future.result()
                        if data:
                            new_cache_data[movie_id] = data
                        else:
                            # Count timeouts/failures
                            timeout_count += 1

                total_time = time.time() - start_time
                if timeout_count > 0:
                    debug_log("VOD preload: %d movies failed/timed out" % timeout_count)
                debug_log(
                    "VOD preload: loaded %d/%d movies in %.2f sec (avg %.2f sec/movie)"
                    % (
                        len(new_cache_data),
                        len(missing_ids),
                        total_time,
                        total_time / len(missing_ids) if missing_ids else 0,
                    )
                )

                # Save to cache
                if new_cache_data:
                    vod_cache_set_multiple(new_cache_data)
                    debug_log("VOD preload: cached %d new movies" % len(new_cache_data))
                    cached_data.update(new_cache_data)

            except ImportError:
                # Fallback without threading
                import time

                start_time = time.time()
                debug_log("VOD preload: ThreadPoolExecutor not available, loading sequentially")
                new_cache_data = {}
                for i, movie_id in enumerate(missing_ids):
                    dialog.update(
                        int(i * 100 / len(missing_ids)), "%s (%d/%d)..." % (get_txt(30068), i + 1, len(missing_ids))
                    )
                    try:
                        movie_start = time.time()
                        video_info = cbAPI.get_video(movie_id)
                        movie_time = time.time() - movie_start
                        debug_log("VOD preload: loaded movie %s in %.2f sec" % (movie_id, movie_time))
                        if isinstance(video_info, dict) and "data" in video_info:
                            new_cache_data[movie_id] = video_info["data"]
                        elif video_info:
                            new_cache_data[movie_id] = video_info
                    except Exception as e:
                        debug_log("VOD preload: failed to load movie %s: %s" % (movie_id, str(e)))
                        pass

                total_time = time.time() - start_time
                debug_log(
                    "VOD preload: loaded %d movies sequentially in %.2f sec (avg %.2f sec/movie)"
                    % (len(missing_ids), total_time, total_time / len(missing_ids) if missing_ids else 0)
                )

                if new_cache_data:
                    vod_cache_set_multiple(new_cache_data)
                    cached_data.update(new_cache_data)

        detailed_metadata = cached_data
        debug_log("VOD preload: total %d movies with metadata" % len(detailed_metadata))

    dialog.close()

    # Server-side pagination: API already returns the correct page
    # Use meta from API response if available, otherwise assume single page
    total_items = api_meta.get("total", len(movie_data)) if api_meta else len(movie_data)
    last_page = api_meta.get("last_page", 1) if api_meta else 1
    has_next_page = page_nr < last_page

    debug_log(
        "[vod_get_ordered_list] Total items: %d, Page: %d/%d, Items on page: %d"
        % (total_items, page_nr, last_page, len(movie_data))
    )

    page_items = movie_data

    for movie_item in page_items:
        movie_id = str(movie_item.get("id", ""))
        movie_name = movie_item.get("name", "")
        Is_Folder = False

        # Get detailed metadata from cache if available
        if movie_id in detailed_metadata:
            detailed = detailed_metadata[movie_id]
            # Merge detailed data with list data (detailed takes priority)
            movie_item = dict(movie_item, **detailed)
            debug_log("VOD item: using cached metadata for %s" % movie_name[:30])

        # Poster URL
        poster_url = movie_item.get("poster", "")

        # Build item name
        year = movie_item.get("year", "")
        o_name = movie_item.get("o_name", movie_item.get("original_name", ""))
        try:
            if not o_name or movie_name == o_name:
                item_name = "[B]%s[/B] [%s]" % (movie_name, str(year))
            else:
                item_name = "[B]%s[/B] [COLOR burlywood](%s)[/COLOR] [%s]" % (movie_name, o_name, str(year))
        except:
            item_name = "[B]%s[/B]" % (movie_name)

        item = xbmcgui.ListItem(item_name, offscreen=True)

        description = movie_item.get("description", movie_item.get("descr", ""))

        # Process genres - API returns array of objects, not string
        genres = movie_item.get("genres", [])
        if isinstance(genres, list):
            genres_str = ", ".join([g.get("title", "") for g in genres if isinstance(g, dict) and g.get("title")])
        else:
            genres_str = movie_item.get("genres_str", movie_item.get("genre", ""))

        country = movie_item.get("country", "")
        rating = movie_item.get("rating_imdb", movie_item.get("rating", ""))
        actors = movie_item.get("actors", "")
        director = movie_item.get("director", "")
        duration = movie_item.get("time", movie_item.get("duration", ""))

        # Check if it's a series (has seasons)
        # API may return: is_series (bool), seasons (list/int), or category indicating series
        is_series = movie_item.get("is_series", False)
        if not is_series:
            seasons = movie_item.get("seasons")
            if seasons:
                is_series = True
        if not is_series:
            # Check if category name indicates series
            category_name = movie_item.get("category", "")
            if category_name and (
                "сериал" in category_name.lower()
                or "serial" in category_name.lower()
                or "tv-шоу" in category_name.lower()
            ):
                is_series = True

        if is_series:
            try:
                item.setInfo(
                    type="video",
                    infoLabels={
                        "title": movie_name,
                        "originaltitle": o_name,
                        "mediatype": "tvshow",
                        "plot": description,
                        "genre": [x.strip() for x in genres_str.split(",")] if genres_str else [],
                        "country": [x.strip() for x in country.split(",")] if country else [],
                        "year": year,
                        "rating": rating,
                        "cast": [x.strip() for x in actors.split(",")] if actors else [],
                        "director": [x.strip() for x in director.split(",")] if director else [],
                        "duration": duration,
                    },
                )
            except:
                item.setInfo(type="video", infoLabels={"title": movie_name, "plot": description})

            item.setArt({"poster": poster_url, "thumb": thumb_browse_file, "fanart": poster_url})
            Is_Folder = True
            item.setProperty("IsPlayable", "false")
            url = "%s?mode=vod_get_seasons&movie_id=%s&movie_name=%s&poster_url=%s" % (
                sys.argv[0],
                movie_item["id"],
                urlQuote(movie_name.encode("utf-8"), safe=""),
                urlQuote(poster_url, safe=""),
            )

        else:
            try:
                item.setInfo(
                    type="video",
                    infoLabels={
                        "title": movie_name,
                        "originaltitle": o_name,
                        "mediatype": "movie",
                        "plot": description,
                        "genre": [x.strip() for x in genres_str.split(",")] if genres_str else [],
                        "country": [x.strip() for x in country.split(",")] if country else [],
                        "year": year,
                        "rating": rating,
                        "cast": [x.strip() for x in actors.split(",")] if actors else [],
                        "director": [x.strip() for x in director.split(",")] if director else [],
                        "duration": duration,
                    },
                )
            except:
                item.setInfo(type="video", infoLabels={"title": movie_name, "mediatype": "movie", "plot": description})

            item.setArt({"poster": poster_url, "thumb": thumb_play_file, "fanart": poster_url})
            item.setProperty("IsPlayable", "true")
            url = "%s?mode=vod_play_movie&movie_id=%s&movie_name=%s" % (
                sys.argv[0],
                movie_item["id"],
                urlQuote(movie_name.encode("utf-8"), safe=""),
            )

        # Build context menu
        context_menu = []
        context_menu.append(
            (
                get_txt(30133),
                "RunPlugin(%s?mode=show_vod_info&movie_id=%s&movie_name=%s)"
                % (sys.argv[0], movie_item["id"], urlQuote(movie_name.encode("utf-8"), safe="")),
            )
        )
        context_menu.append((get_txt(30045), "XBMC.Action(Info)"))
        context_menu.append(("%s" % get_txt(30128), "RunPlugin(%s?mode=get_stream_servers)" % (sys.argv[0])))
        item.addContextMenuItems(items=context_menu, replaceItems=True)
        listing.append((url, item, Is_Folder))

    # Add "Next page" item if there are more items
    if has_next_page:
        next_page_nr = page_nr + 1
        item_name = "[COLOR white][B]%s[/B][/COLOR]" % get_txt(30076)  # "Next page"

        # Build URL with same parameters but incremented page number
        if vod_search:
            url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=%s&page_nr=%d&sortby=%s&vod_search=%s" % (
                sys.argv[0],
                cat_id,
                genre_id,
                next_page_nr,
                sortby,
                vod_search,
            )
        elif vod_year:
            url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=%s&page_nr=%d&sortby=%s&vod_year=%s" % (
                sys.argv[0],
                cat_id,
                genre_id,
                next_page_nr,
                sortby,
                vod_year,
            )
        else:
            url = "%s?mode=vod_get_ordered_list&cat_id=%s&genre_id=%s&page_nr=%d&sortby=%s" % (
                sys.argv[0],
                cat_id,
                genre_id,
                next_page_nr,
                sortby,
            )

        item = xbmcgui.ListItem(item_name, offscreen=True)
        item.setArt(
            {"poster": vod_poster_file, "thumb": thumb_next_file, "fanart": os.path.join(FANART_PATH, "vod_03.jpg")}
        )
        listing.append((url, item, True))
        debug_log('[vod_get_ordered_list] Added "Next page" button for page %d' % next_page_nr)

    xbmcplugin.addDirectoryItems(addon_handle, listing, totalItems=len(listing))
    xbmcplugin.setContent(addon_handle, "movies")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)

    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=True)


# Get seasons list
def vod_get_seasons(movie_id, movie_name, poster_url):

    listing = []
    poster_url = urlUnquote(poster_url)
    movie_name = (sys.version_info[0] >= 3 and urlUnquote(movie_name)) or unicode(urlUnquote(movie_name), "utf-8")

    debug_log("Getting seasons for movie_id=%s, name=%s" % (movie_id, movie_name))

    try:
        info = cbAPI.get_video(movie_id)
        debug_log("get_video returned type: %s" % type(info).__name__)
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
            debug_log("Extracted data, type: %s" % type(info).__name__)
    except Exception as e:
        debug_log("Error getting video info: %s" % str(e))
        info = None

    if not info:
        debug_log("No video info available")
        show_msg(get_txt(30079), 3000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    # Check if info has seasons
    seasons = info.get("seasons", []) if isinstance(info, dict) else info
    debug_log(
        "Seasons data type: %s, length: %s"
        % (type(seasons).__name__, len(seasons) if isinstance(seasons, list) else "N/A")
    )

    if not isinstance(seasons, list):
        debug_log("Seasons is not a list, wrapping in list")
        seasons = [info]

    # Count valid seasons (with name or number)
    valid_seasons = []
    for data in seasons:
        season_name = data.get("name", data.get("title", ""))
        season_number = data.get("number", "")
        if season_name or season_number:
            valid_seasons.append(data)

    debug_log("Valid seasons count: %d" % len(valid_seasons))

    # If only one valid season, redirect directly to episodes
    if len(valid_seasons) == 1:
        season_data = valid_seasons[0]
        season_id = season_data.get("id", "0")
        season_name = season_data.get("name", season_data.get("title", ""))
        season_number = season_data.get("number", "")

        if not season_name and season_number:
            season_name = "%s %s" % (get_txt(30131), season_number)

        debug_log("Only one season found, redirecting to episodes: season_id=%s, name=%s" % (season_id, season_name))
        vod_get_episodes(movie_id, season_id, movie_name, season_name, poster_url)
        return

    # Use valid_seasons for iteration
    for data in valid_seasons:
        season_name = data.get("name", data.get("title", ""))
        season_id = data.get("id", "0")
        season_number = data.get("number", "")
        episodes_count = data.get("count", data.get("season_series", data.get("series_count", "")))

        debug_log(
            "Processing season: id=%s, number=%s, name=%s, episodes=%s"
            % (season_id, season_number, season_name, episodes_count)
        )

        # If season has no name, generate one from number
        if not season_name and season_number:
            season_name = "%s %s" % (get_txt(30131), season_number)  # "Season N"

        try:
            plot_desc = "[B]%s[/B][CR]%s[CR]%s: %s" % (movie_name, season_name, get_txt(30077), str(episodes_count))
        except:
            plot_desc = "%s: %s" % (get_txt(30077), str(episodes_count))

        item_name = "[COLOR burlywood][B]%s[/B][/COLOR]" % (season_name)
        list_item = xbmcgui.ListItem(item_name, offscreen=True)
        list_item.setInfo(
            type="video",
            infoLabels={"title": season_name, "mediatype": "season", "Episode": str(episodes_count), "plot": plot_desc},
        )

        list_item.setArt({"poster": poster_url, "thumb": thumb_browse_file, "fanart": poster_url})
        list_item.setProperty("IsPlayable", "false")
        url = "%s?mode=vod_get_episodes&movie_id=%s&season_id=%s&movie_name=%s&season_name=%s&poster_url=%s" % (
            sys.argv[0],
            movie_id,
            season_id,
            urlQuote(movie_name.encode("utf-8"), safe=""),
            urlQuote(season_name.encode("utf-8"), safe=""),
            urlQuote(poster_url, safe=""),
        )

        # Add context menu
        context_menu = []
        context_menu.append(
            (
                get_txt(30133),
                "RunPlugin(%s?mode=show_vod_info&movie_id=%s&movie_name=%s)"
                % (sys.argv[0], movie_id, urlQuote(movie_name.encode("utf-8"), safe="")),
            )
        )
        context_menu.append(("%s" % get_txt(30128), "RunPlugin(%s?mode=get_stream_servers)" % (sys.argv[0])))
        list_item.addContextMenuItems(items=context_menu, replaceItems=True)

        listing.append((url, list_item, True))

    debug_log("Total seasons added to listing: %d" % len(listing))

    xbmcplugin.addDirectoryItems(addon_handle, listing, totalItems=len(listing))
    xbmcplugin.setContent(addon_handle, "seasons")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)
    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)


# Get episodes list
def vod_get_episodes(movie_id, season_id, movie_name, season_name, poster_url, focus_episode_id="0"):

    listing = []
    poster_url = urlUnquote(poster_url)
    movie_name = (sys.version_info[0] >= 3 and urlUnquote(movie_name)) or unicode(urlUnquote(movie_name), "utf-8")
    season_name = (sys.version_info[0] >= 3 and urlUnquote(season_name)) or unicode(urlUnquote(season_name), "utf-8")

    debug_log("Getting episodes for movie_id=%s, season_id=%s, season_name=%s" % (movie_id, season_id, season_name))

    try:
        info = cbAPI.get_season(season_id)
        debug_log("get_season returned type: %s" % type(info).__name__)
        if isinstance(info, dict) and "data" in info:
            info = info["data"]
            debug_log("Extracted data, type: %s" % type(info).__name__)
    except Exception as e:
        debug_log("Error getting season info: %s" % str(e))
        info = None

    if not info:
        debug_log("No season info available")
        show_msg(get_txt(30079), 3000)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    episodes = info if isinstance(info, list) else [info]
    debug_log("Episodes data type: %s, length: %d" % (type(episodes).__name__, len(episodes)))

    added_count = 0
    focus_index = -1
    for data in episodes:
        episode_name = data.get("name", data.get("title", ""))
        episode_id = data.get("id", "0")
        episode_number = data.get("series_number", data.get("number", ""))

        debug_log("Processing episode: id=%s, name=%s, number=%s" % (episode_id, episode_name, episode_number))

        # If episode has no name, generate one from number
        if not episode_name and episode_number:
            episode_name = "%s %s" % (get_txt(30132), episode_number)  # "Episode N"
            debug_log("Generated episode name: %s" % episode_name)

        if not episode_name:
            debug_log("Skipping episode with empty name and no number")
            continue

        try:
            plot_desc = "[B]%s[/B][CR]%s[CR]%s" % (movie_name, season_name, episode_name)
        except:
            plot_desc = ""

        item_name = "[COLOR burlywood][B]%s[/B][/COLOR]" % (episode_name)
        list_item = xbmcgui.ListItem(item_name, offscreen=True)
        list_item.setInfo(
            type="video",
            infoLabels={
                "title": episode_name,
                "mediatype": "episode",
                "Episode": str(episode_number),
                "plot": plot_desc,
            },
        )

        list_item.setArt({"poster": poster_url, "fanart": poster_url})
        list_item.setProperty("IsPlayable", "true")

        url = "%s?mode=vod_play_movie&movie_id=%s&season_id=%s&episode_id=%s&movie_name=%s&season_name=%s" % (
            sys.argv[0],
            movie_id,
            season_id,
            episode_id,
            urlQuote(movie_name.encode("utf-8"), safe=""),
            urlQuote(season_name.encode("utf-8"), safe=""),
        )

        context_menu = []
        context_menu.append(
            (
                get_txt(30133),
                "RunPlugin(%s?mode=show_vod_info&movie_id=%s&movie_name=%s)"
                % (sys.argv[0], movie_id, urlQuote(movie_name.encode("utf-8"), safe="")),
            )
        )
        context_menu.append(("%s" % get_txt(30128), "RunPlugin(%s?mode=get_stream_servers)" % (sys.argv[0])))
        list_item.addContextMenuItems(items=context_menu, replaceItems=True)

        listing.append((url, list_item, False))
        added_count += 1

        # Track focus position for watch history navigation
        if str(focus_episode_id) != "0" and str(episode_id) == str(focus_episode_id):
            focus_index = added_count - 1
            debug_log("[vod_get_episodes] Focus episode found at index %d: episode_id=%s" % (focus_index, episode_id))

    debug_log("Total episodes added to listing: %d" % added_count)

    xbmcplugin.addDirectoryItems(addon_handle, listing, totalItems=len(listing))
    xbmcplugin.setContent(addon_handle, "episodes")
    viewmode = (len(str(__addon__.getSetting("viewmode"))) > 0 and str(__addon__.getSetting("viewmode"))) or "0"
    if viewmode != "0":
        xbmc.executebuiltin("Container.SetViewMode(%s)" % viewmode)
    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)

    # Position cursor on the episode from watch history
    # After endOfDirectory, cursor is on ".." (parent dir) at position 0
    # We emulate Down key presses to move to the target episode
    # This works because Action(Down) navigates within the already-focused list
    # just like a user pressing Down on keyboard/remote
    if focus_index >= 0:
        has_parent = xbmc.getCondVisibility("System.GetBool(filelists.showparentdiritems)")
        # If parent dir (..) is shown, we need +1 extra Down press to skip it
        total_downs = focus_index + (1 if has_parent else 0)
        debug_log(
            "[vod_get_episodes] Focus: index=%d, has_parent=%s, total_downs=%d" % (focus_index, has_parent, total_downs)
        )

        if total_downs > 0:
            # Wait for the directory listing to be rendered
            xbmc.sleep(500)

            # Check if this is a fresh entry (from watch history) or a return from player
            # On fresh entry, cursor is at position 0 (on ".." parent dir)
            # On return from player, Kodi restores the previous cursor position (not 0)
            cur_item_before = int(xbmc.getInfoLabel("Container.CurrentItem") or "0")
            num_items = int(xbmc.getInfoLabel("Container.NumItems") or "0")
            debug_log(
                "[vod_get_episodes] Container.NumItems=%d, CurrentItem=%d, CurrentControlId=%s"
                % (num_items, cur_item_before, xbmc.getInfoLabel("System.CurrentControlId"))
            )

            if cur_item_before > 1:
                # Cursor is not at the top — this is a return from player, skip navigation
                debug_log(
                    "[vod_get_episodes] Skipping focus navigation: already at item %d (return from player)"
                    % cur_item_before
                )
            else:
                # Fresh entry from watch history — navigate to the target episode
                for i in range(total_downs):
                    xbmc.executebuiltin("Action(Down)")
                    xbmc.sleep(50)

                xbmc.sleep(200)
                cur_item = xbmc.getInfoLabel("Container.CurrentItem")
                cur_pos = xbmc.getInfoLabel("Container(50).Position")
                debug_log(
                    "[vod_get_episodes] After %d x Action(Down): CurrentItem=%s, Position=%s"
                    % (total_downs, cur_item, cur_pos)
                )


# Play movie
def vod_play_movie(movie_id, season_id, episode_id, movie_name="-", season_name="-"):

    config___user_server = str(__addon__.getSetting("user_server"))

    debug_log("VOD play movie: movie_id=%s, season_id=%s, episode_id=%s" % (movie_id, season_id, episode_id))

    # Get video info from new API
    video_metadata = None  # Will store metadata for ListItem
    try:
        if int(season_id) > 0 and int(episode_id) > 0:
            # Playing an episode - get season data to find the episode URL
            debug_log("Getting season info for season_id=%s" % season_id)
            info = cbAPI.get_season(season_id)
            debug_log("Season info type: %s" % type(info))
            if isinstance(info, dict) and "data" in info:
                info = info["data"]

            stream_url = None
            episode_data = None
            if isinstance(info, list):
                debug_log("Season info is list with %d episodes" % len(info))
                for ep in info:
                    if str(ep.get("id", "")) == str(episode_id):
                        episode_data = ep  # Save episode data for metadata
                        # Try to get URL from 'files' array first (new API format)
                        files = ep.get("files", [])
                        if files and isinstance(files, list) and len(files) > 0:
                            stream_url = files[0].get("url", "")
                            debug_log(
                                "Episode stream URL from files array: %s" % (stream_url[:50] if stream_url else "None")
                            )

                        # Fallback to old format
                        if not stream_url:
                            stream_url = ep.get("url", ep.get("cmd", ep.get("file", "")))
                            debug_log("Episode stream URL from dict: %s" % (stream_url[:50] if stream_url else "None"))
                        break
                # If not found by id, try first episode
                if not stream_url and info:
                    ep = info[0]
                    episode_data = ep
                    files = ep.get("files", [])
                    if files and isinstance(files, list) and len(files) > 0:
                        stream_url = files[0].get("url", "")
                    else:
                        stream_url = ep.get("url", ep.get("cmd", ep.get("file", "")))

            # For episodes, also get series metadata from get_video
            if episode_data:
                try:
                    series_info = cbAPI.get_video(movie_id)
                    if isinstance(series_info, dict) and "data" in series_info:
                        video_metadata = series_info["data"].copy()
                        # Add episode-specific data
                        video_metadata["episode_number"] = episode_data.get("number", "")
                        video_metadata["episode_name"] = episode_data.get("name", "")
                        debug_log("Got series metadata for episode")
                except Exception as e:
                    debug_log("Error getting series metadata: %s" % str(e))
        else:
            # Playing a movie - get video data
            debug_log("Getting video info for movie_id=%s" % movie_id)
            info = cbAPI.get_video(movie_id)
            debug_log("Video info type: %s, keys: %s" % (type(info), info.keys() if isinstance(info, dict) else "N/A"))
            if isinstance(info, dict) and "data" in info:
                video_metadata = info["data"]
                debug_log("Video data type: %s" % type(video_metadata))

            stream_url = None
            if isinstance(video_metadata, dict):
                # Try to get URL from 'files' array first (new API format)
                files = video_metadata.get("files", [])
                if files and isinstance(files, list) and len(files) > 0:
                    stream_url = files[0].get("url", "")
                    debug_log("Stream URL from files array: %s" % (stream_url[:50] if stream_url else "None"))

                # Fallback to old format
                if not stream_url:
                    stream_url = video_metadata.get("url", video_metadata.get("cmd", video_metadata.get("file", "")))
                    debug_log("Stream URL from dict: %s" % (stream_url[:50] if stream_url else "None"))
            elif isinstance(video_metadata, list) and video_metadata:
                stream_url = video_metadata[0].get(
                    "url", video_metadata[0].get("cmd", video_metadata[0].get("file", ""))
                )
                debug_log("Stream URL from list: %s" % (stream_url[:50] if stream_url else "None"))
            else:
                stream_url = None
                debug_log("No stream URL found, info type: %s" % type(video_metadata))
    except Exception as e:
        debug_log("VOD play error: %s" % str(e))
        import traceback

        debug_log("Traceback: %s" % traceback.format_exc())
        stream_url = None

    if not stream_url:
        debug_log("No stream URL available")
        show_msg(get_txt(30079), 3000)
        return False

    # If URL is relative, prepend server URL
    if stream_url and not stream_url.startswith("http"):
        # Get server URL from auth info
        try:
            auth_info = cbAPI.get_auth_info()
            server = auth_info.get("server", "")
            ssl = auth_info.get("ssl", False)

            if server:
                # Build full server URL with protocol
                protocol = "https" if ssl else "http"
                server_url = "%s://%s" % (protocol, server)
                stream_url = server_url + stream_url
                debug_log("Prepended server URL: %s" % server_url)
            else:
                debug_log("No server found in auth_info")
        except Exception as e:
            debug_log("Error getting server URL: %s" % str(e))

    debug_log("Final stream URL: " + stream_url[:100])

    # Clean up URL if needed
    if stream_url.startswith("ffmpeg ") or stream_url.startswith("ffmpeg%20"):
        regex = re.search(r".*(http://.*)", stream_url)
        if regex:
            stream_url = regex.group(1)

    # Add token from auth info if URL doesn't have one
    if "?token=" not in stream_url and "token=" not in stream_url:
        try:
            auth_info = cbAPI.get_auth_info()
            private_token = auth_info.get("private_token", "")
            if private_token:
                stream_url += "?token=%s" % private_token
                debug_log("Added token to URL")
        except:
            pass

    debug_log("Streaming vod using URL: " + stream_url)

    # Save to watch history before playback
    try:
        # Decode URL-encoded parameters
        history_title = (sys.version_info[0] >= 3 and urlUnquote(movie_name)) or unicode(
            urlUnquote(movie_name), "utf-8"
        )
        history_season_name = (sys.version_info[0] >= 3 and urlUnquote(season_name)) or unicode(
            urlUnquote(season_name), "utf-8"
        )
        history_episode_name = ""
        history_episode_number = ""
        history_poster = ""
        history_type = "movie"

        # Get poster and episode details from metadata
        if isinstance(video_metadata, dict):
            history_poster = video_metadata.get("poster", "")

            # Check if it's an episode
            if episode_id and int(episode_id) > 0:
                history_type = "episode"
                history_episode_number = video_metadata.get("episode_number", "")
                history_episode_name = video_metadata.get("episode_name", "")

                # If episode has no name but has number, generate name
                if not history_episode_name and history_episode_number:
                    history_episode_name = "%s %s" % (get_txt(30149), history_episode_number)  # "Episode N"

                # If season name is empty or default, try to get from season_id
                if not history_season_name or history_season_name == "-":
                    # Try to extract season number from season data
                    try:
                        season_info = cbAPI.get_season(season_id)
                        if isinstance(season_info, dict) and "data" in season_info:
                            season_data = season_info["data"]
                            if isinstance(season_data, list) and season_data:
                                season_data = season_data[0]
                            if isinstance(season_data, dict):
                                season_num = season_data.get("season_number", "")
                                if season_num:
                                    history_season_name = "%s %s" % (get_txt(30148), season_num)  # "Season N"
                    except:
                        pass

        # Add to history
        add_to_watch_history(
            movie_id=movie_id,
            season_id=season_id if season_id else "0",
            episode_id=episode_id if episode_id else "0",
            title=history_title,
            season_name=history_season_name,
            episode_name=history_episode_name,
            episode_number=history_episode_number,
            poster=history_poster,
            content_type=history_type,
        )
    except Exception as e:
        debug_log("[vod_play_movie] Error saving to history: %s" % str(e))

    # Create ListItem with metadata from video info
    item = xbmcgui.ListItem(path=stream_url, offscreen=True)

    # Add metadata if we have video info
    if isinstance(video_metadata, dict):
        video_name = video_metadata.get("name", "")
        video_desc = video_metadata.get("description", video_metadata.get("descr", ""))
        video_year = video_metadata.get("year", "")
        video_rating = video_metadata.get("rating", video_metadata.get("rating_imdb", ""))
        video_director = video_metadata.get("director", "")
        video_actors = video_metadata.get("actors", "")
        video_country = video_metadata.get("country", "")
        video_duration = video_metadata.get("time", video_metadata.get("duration", ""))
        video_original = video_metadata.get("original_name", video_metadata.get("o_name", ""))
        video_poster = video_metadata.get("poster", "")

        # For episodes, use episode-specific name if available
        episode_number = video_metadata.get("episode_number", "")
        episode_name = video_metadata.get("episode_name", "")
        if episode_name:
            video_name = episode_name
        elif episode_number:
            video_name = "Episode %s" % episode_number

        # Process genres
        genres_list = []
        genres = video_metadata.get("genres", [])
        if isinstance(genres, list):
            genres_list = [g.get("title", "") for g in genres if isinstance(g, dict) and g.get("title")]
        elif isinstance(genres, str):
            genres_list = [x.strip() for x in genres.split(",") if x.strip()]

        # Process actors
        cast_list = []
        if video_actors:
            cast_list = [x.strip() for x in video_actors.split(",") if x.strip()]

        # Process directors
        director_list = []
        if video_director:
            director_list = [x.strip() for x in video_director.split(",") if x.strip()]

        # Determine media type
        is_episode = episode_id is not None and int(episode_id) > 0
        media_type = "episode" if is_episode else "movie"

        # Build infoLabels
        info_labels = {
            "title": video_name,
            "mediatype": media_type,
        }

        if video_original:
            info_labels["originaltitle"] = video_original
        if video_desc:
            info_labels["plot"] = video_desc
        if video_year:
            info_labels["year"] = video_year
        if video_rating:
            try:
                info_labels["rating"] = float(video_rating)
            except:
                pass
        if video_duration:
            try:
                info_labels["duration"] = int(video_duration) * 60  # Convert minutes to seconds
            except:
                pass
        if genres_list:
            info_labels["genre"] = genres_list
        if video_country:
            info_labels["country"] = [x.strip() for x in video_country.split(",") if x.strip()]
        if cast_list:
            info_labels["cast"] = cast_list
        if director_list:
            info_labels["director"] = director_list
        if is_episode and episode_number:
            try:
                info_labels["episode"] = int(episode_number)
            except:
                pass

        item.setInfo("video", info_labels)

        # For Kodi 20+, also use new InfoTagVideo API
        try:
            video_tag = item.getVideoInfoTag()
            video_tag.setTitle(video_name)
            video_tag.setMediaType(media_type)
            if video_original:
                video_tag.setOriginalTitle(video_original)
            if video_desc:
                video_tag.setPlot(video_desc)
            if video_year:
                video_tag.setYear(int(video_year))
            if video_rating:
                video_tag.setRating(float(video_rating))
            if video_duration:
                video_tag.setDuration(int(video_duration) * 60)
            if genres_list:
                video_tag.setGenres(genres_list)
            if video_country:
                video_tag.setCountries([x.strip() for x in video_country.split(",") if x.strip()])
            if cast_list:
                # Create Actor objects for Kodi 20+
                import xbmc

                actors = []
                for actor_name in cast_list:
                    actor = xbmc.Actor(actor_name)
                    actors.append(actor)
                video_tag.setCast(actors)
            if director_list:
                video_tag.setDirectors(director_list)
            if is_episode and episode_number:
                video_tag.setEpisode(int(episode_number))
            debug_log("VOD metadata set via InfoTagVideo API")
        except Exception as e:
            debug_log("InfoTagVideo API not available or error: %s" % str(e))

        # Set artwork
        if video_poster:
            item.setArt({"poster": video_poster, "thumb": video_poster, "fanart": video_poster})

        debug_log(
            "VOD metadata added: title=%s, plot_length=%d, cast=%d, genres=%d"
            % (video_name[:30] if video_name else "N/A", len(video_desc), len(cast_list), len(genres_list))
        )
    else:
        debug_log("No video metadata available (type: %s)" % type(video_metadata))

    xbmcplugin.setResolvedUrl(addon_handle, True, item)
    return True


def vod_debug(play_cmd):

    config___user_server = str(__addon__.getSetting("user_server"))

    params = "type=vod&action=create_link&JsHttpRequest=1-xml&cmd=" + play_cmd
    info = retrieve_json_list(params)

    debug_log("VOD info: " + str(json.dumps(info, indent=3)))
    return False


# helper function for addon parameter parsing
def get_params():

    param = []
    paramstring = sys.argv[2]

    if len(paramstring) >= 2:
        params = sys.argv[2]
        cleanedparams = params.replace("?", "")

        if params[len(params) - 1] == "/":
            params = params[0 : len(params) - 2]

        pairsofparams = cleanedparams.split("&")

        param = {}

        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split("=")

            if (len(splitparams)) == 2:
                # URL-decode values to handle encoded characters like %2a -> *
                param[splitparams[0]] = urlUnquote(splitparams[1])

    return param
