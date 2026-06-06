# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""
Adapter layer between new Cbilling REST API and existing addon logic.

Converts new API data structures to the format expected by body.py,
so the migration can be done incrementally without rewriting everything at once.

Key transformations:
  - Streams → channel data format (with id, cmd, tv_genre_id, etc.)
  - Categories from streams → genre format (with id, title, censored)
  - EPG from new API → short_epg format (with t_time, t_time_to, name, timestamps)
  - Archive URL construction from stream alias + timestamp
"""

import datetime
import re

try:
    import simplejson as json
except ImportError:
    pass

try:
    from dateutil.tz import gettz, tzutc
except ImportError:
    gettz = None
    tzutc = None


class ApiAdapter:
    """
    Transforms new REST API responses into formats compatible with
    the existing body.py Stalker Portal data structures.
    """

    def __init__(self, api_client, timezone_name=None):
        """
        Args:
            api_client: CbillingAPI instance
            timezone_name: IANA timezone name (e.g. 'Europe/Tallinn') from addon settings.
                           If None or invalid, system local time will be used as fallback.
        """
        self.api = api_client
        self.debug = True  # Enable debug logging
        self._category_map = None  # {category_name: genre_id}
        self._alias_to_stream = None  # {alias: stream_dict}
        self._user_tz = None
        self._tz_fallback = False

        if gettz is None:
            self._log_warn("[ApiAdapter] dateutil.tz not available, using system local time for EPG")
            self._tz_fallback = True
        elif timezone_name:
            tz = gettz(timezone_name)
            if tz is not None:
                self._user_tz = tz
                self._log("[ApiAdapter] EPG timezone set to: %s" % timezone_name)
            else:
                self._log_warn(
                    '[ApiAdapter] Invalid timezone "%s" in addon settings, using system local time for EPG'
                    % timezone_name
                )
                self._tz_fallback = True
        else:
            self._log_warn("[ApiAdapter] No timezone configured in addon settings, using system local time for EPG")
            self._tz_fallback = True

    def _log(self, msg):
        """Log to Kodi if available, otherwise print."""
        try:
            import xbmc

            xbmc.log("[Cbilling] " + str(msg), level=xbmc.LOGDEBUG)
        except ImportError:
            if self.debug:
                print("[Cbilling] " + str(msg))

    def _log_warn(self, msg):
        """Log warning to Kodi if available, otherwise print."""
        try:
            import xbmc

            xbmc.log("[Cbilling] " + str(msg), level=xbmc.LOGWARNING)
        except ImportError:
            print("[Cbilling] WARNING: " + str(msg))

    def _ts_to_local_str(self, unix_ts, fmt="%H:%M"):
        """
        Convert Unix timestamp to formatted local time string using addon timezone.

        Args:
            unix_ts: Unix timestamp (int or str)
            fmt: strftime format string

        Returns:
            Formatted time string or '' on error
        """
        try:
            ts = int(unix_ts)
            if ts <= 0:
                return ""
            if self._user_tz is not None:
                # Convert via UTC -> user timezone
                utc_dt = datetime.datetime(1970, 1, 1, tzinfo=tzutc()) + datetime.timedelta(seconds=ts)
                local_dt = utc_dt.astimezone(self._user_tz)
                return local_dt.strftime(fmt)
            else:
                # Fallback: system local time
                return datetime.datetime.fromtimestamp(ts).strftime(fmt)
        except (ValueError, OSError, OverflowError):
            return ""

    # ------------------------------------------------------------------
    # Category / Genre mapping
    # ------------------------------------------------------------------

    def _build_category_map(self):
        """Build a mapping of category names to synthetic genre IDs."""
        if self._category_map is not None:
            return

        streams = self.api.get_streams()
        seen = {}
        genre_id = 1
        for s in streams:
            cat = s.get("category", "")
            if cat and cat not in seen:
                seen[cat] = str(genre_id)
                genre_id += 1
        self._category_map = seen

    def _build_alias_map(self):
        """Build alias -> stream lookup."""
        if self._alias_to_stream is not None:
            return
        streams = self.api.get_streams()
        self._alias_to_stream = {}
        for s in streams:
            alias = s.get("alias", "")
            if alias:
                self._alias_to_stream[alias] = s

    def get_genres(self):
        """
        Get channel genres/categories in Stalker format.

        Returns list of dicts compatible with body.py channel_groups():
            [{"id": "1", "title": "Category Name", "censored": "0"}, ...]
        """
        self._build_category_map()
        genres = []
        for cat_name, cat_id in self._category_map.items():
            genres.append({"id": cat_id, "title": cat_name, "censored": "0"})
        return genres

    def get_genre_id_for_category(self, category_name):
        """Get synthetic genre ID for a category name."""
        self._build_category_map()
        return self._category_map.get(category_name, "0")

    # ------------------------------------------------------------------
    # Channel data conversion
    # ------------------------------------------------------------------

    def _stream_to_channel(self, stream, index=0):
        """
        Convert a single stream dict from new API to Stalker channel format.

        New API stream:
            {name, alias, category, sort, is_sd, is_hd, archive, archive_days,
             logo, url, proxy_url}

        Stalker channel format expected by body.py:
            {id, name, tv_genre_id, cmd, tv_archive_type, logo, tv_archive_duration,
             censored, fav, open, status, cur_playing}
        """
        alias = stream.get("alias", "")
        category = stream.get("category", "")
        genre_id = self.get_genre_id_for_category(category)

        has_archive = stream.get("archive", 0) == 1
        archive_days = stream.get("archive_days", 0)

        # Build cmd in format expected by play_live_channel
        # The URL is already complete from the API, so we store it directly
        stream_url = stream.get("url", "")

        channel = {
            "id": alias,  # Using alias as ID (new API has no numeric IDs)
            "name": stream.get("name", ""),
            "tv_genre_id": genre_id,
            "cmd": stream_url,  # Direct URL, no create_link needed
            "tv_archive_type": (has_archive and "flussonic_dvr") or "",
            "logo": stream.get("logo", ""),
            "tv_archive_duration": str(archive_days),
            "censored": 0,
            "fav": 0,  # Will be set from local favorites
            "open": 1,
            "status": 1,
            "cur_playing": "",  # Will be populated from EPG
            "sort": stream.get("sort", index),
            # New API specific fields (kept for reference)
            "_alias": alias,
            "_category": category,
            "_is_hd": stream.get("is_hd", 0),
            "_is_sd": stream.get("is_sd", 0),
            "_proxy_url": stream.get("proxy_url", ""),
        }

        return channel

    def get_all_channels(self):
        """
        Get all channels in Stalker format.

        Returns:
            list of channel dicts compatible with body.py get_channels_data()
        """
        streams = self.api.get_streams()
        channels = []
        for i, stream in enumerate(streams):
            channels.append(self._stream_to_channel(stream, i))
        return channels

    def get_channels_by_genre(self, genre_id):
        """
        Get channels for a specific genre/category.

        Args:
            genre_id: Genre ID string (from get_genres())

        Returns:
            list of channel dicts
        """
        self._build_category_map()
        # Find category name by genre_id
        cat_name = None
        for name, gid in self._category_map.items():
            if gid == str(genre_id):
                cat_name = name
                break

        if cat_name is None:
            return []

        streams = self.api.get_streams_by_category(cat_name)
        return [self._stream_to_channel(s, i) for i, s in enumerate(streams)]

    # ------------------------------------------------------------------
    # EPG conversion
    # ------------------------------------------------------------------

    def get_short_epg(self, alias, size=5):
        """
        Get short EPG in Stalker format.

        Stalker format:
            [{"t_time": "20:00", "t_time_to": "21:00", "name": "Program",
              "start_timestamp": 1234567890, "stop_timestamp": 1234567890}, ...]

        Args:
            alias: Channel alias
            size: Number of EPG items

        Returns:
            list of EPG dicts in Stalker format
        """
        try:
            raw_epg = self.api.get_epg_current(alias, num=size)
        except Exception:
            return []

        return self._convert_epg_list(raw_epg)

    def get_day_epg(self, alias, date=None):
        """
        Get full day EPG in Stalker format.

        Args:
            alias: Channel alias
            date: Date string 'YYYY-MM-DD' (optional)

        Returns:
            list of EPG dicts in Stalker format
        """
        try:
            raw_epg = self.api.get_epg_day(alias, date=date)
            if self.debug:
                print(
                    "[ApiAdapter] EPG raw data type: %s, length: %s"
                    % (type(raw_epg), len(raw_epg) if isinstance(raw_epg, (list, dict)) else "N/A")
                )
        except Exception as e:
            if self.debug:
                print("[ApiAdapter] EPG fetch error: %s" % str(e))
            return []

        result = self._convert_epg_list(raw_epg)
        if self.debug:
            print("[ApiAdapter] EPG converted: %d items" % len(result))
        return result

    def get_current_program_text(self, alias):
        """
        Get current program text in Stalker cur_playing format.
        Format: "HH:MM Program Name"

        Args:
            alias: Channel alias

        Returns:
            str like "20:00 Evening News" or "No channel info"
        """
        try:
            raw = self.api.get_epg_now(alias)

            if self.debug:
                self._log(
                    "[get_current_program_text] alias=%s raw type=%s raw=%s"
                    % (alias, type(raw).__name__, str(raw)[:200])
                )

            # Response is a list with one item: [{"date": "...", "time": unix, "name": "..."}]
            if isinstance(raw, list) and len(raw) > 0:
                epg_data = raw[0]
            elif isinstance(raw, dict) and "data" in raw:
                data = raw["data"]
                epg_data = data[0] if isinstance(data, list) and data else data
            elif isinstance(raw, dict):
                epg_data = raw
            else:
                self._log("[get_current_program_text] alias=%s unexpected raw type: %s" % (alias, type(raw).__name__))
                return "No channel info"

            name = epg_data.get("name", "")

            # Get time from Unix timestamp, converted to user's timezone
            t_time = ""
            if "time" in epg_data:
                t_time = self._ts_to_local_str(epg_data["time"])

            # Fallback to 'date' string only if no timestamp available
            if not t_time and "date" in epg_data:
                try:
                    t_time = epg_data["date"].split(" ")[1][:5]
                except (IndexError, AttributeError):
                    pass

            if t_time and name:
                return "%s %s" % (t_time, name)
            elif name:
                return name
            else:
                return "No channel info"
        except Exception as e:
            import traceback as _tb

            self._log("[get_current_program_text] alias=%s error: %s\n%s" % (alias, str(e), _tb.format_exc()))
            return "No channel info"

    def _convert_epg_list(self, raw_epg):
        """
        Convert new API EPG response to Stalker format.

        Handles both list responses and dict with 'data' key.
        """
        if raw_epg is None:
            return []

        # Unwrap 'data' key if present
        if isinstance(raw_epg, dict) and "data" in raw_epg:
            items = raw_epg["data"]
        elif isinstance(raw_epg, list):
            items = raw_epg
        else:
            return []

        result = []
        for item in items:
            entry = self._convert_epg_entry(item)
            if entry:
                result.append(entry)

        return result

    def _convert_epg_entry(self, item):
        """
        Convert a single EPG entry to Stalker format.

        Time is always derived from Unix timestamps (time/time_to fields)
        and converted to the user's configured timezone.
        The string 'date'/'date_to' fields from API are ignored because
        they come in the server's timezone (Moscow) and don't reflect
        the user's local time.

        New API format:
            {"date": "2026-02-15 14:55:00", "date_to": "2026-02-15 18:00:00",
             "time": 1771156500, "time_to": 1771167600,
             "progress": 26, "duration": 11100,
             "name": "Program Name", "descr": "...", "dvr_uri": "/alias/video-ts-dur.m3u8"}

        Stalker format:
            {"t_time": "14:55", "t_time_to": "18:00", "name": "Program Name",
             "start_timestamp": "1771156500", "stop_timestamp": "1771167600"}
        """
        if not item:
            return None

        name = item.get("name", "")

        # Unix timestamps — the single source of truth for time
        start_ts = item.get("time", item.get("start_timestamp", 0))
        stop_ts = item.get("time_to", item.get("stop_timestamp", 0))

        # Convert timestamps to display time in user's timezone
        t_time = self._ts_to_local_str(start_ts) if start_ts else ""
        t_time_to = self._ts_to_local_str(stop_ts) if stop_ts else ""

        return {
            "t_time": t_time,
            "t_time_to": t_time_to,
            "name": name,
            "start_timestamp": str(start_ts) if start_ts else "",
            "stop_timestamp": str(stop_ts) if stop_ts else "",
            "descr": item.get("descr", ""),
            "dvr_uri": item.get("dvr_uri", ""),
            "duration": item.get("duration", 0),
            "progress": item.get("progress", 0),
        }

    # ------------------------------------------------------------------
    # Archive URL construction
    # ------------------------------------------------------------------

    def build_archive_url(self, stream_url, utc_timestamp, duration=None, dvr_uri=None):
        """
        Build archive playback URL from a live stream URL.

        If dvr_uri is provided (from EPG data), use it directly with the server.
        Otherwise, construct from live URL using Flussonic format:
            http://server/channel/index.m3u8?token=XXX  (live)
            http://server/channel/video-{utc}-{duration}.m3u8?token=XXX  (archive)

        Args:
            stream_url: Live stream URL from /streams
            utc_timestamp: UTC timestamp of archive start
            duration: Duration in seconds (optional)
            dvr_uri: DVR URI from EPG (e.g. '/pervyj/video-1771156500-11100.m3u8')

        Returns:
            Archive URL string
        """
        if not stream_url:
            return ""

        # Extract server and token from stream URL
        # Format: http://server.example.com:80/pervyj/index.m3u8?token=XXXXX_1
        match = re.match(r"(https?://[^/]+)(/.+?)(\?.*)?$", stream_url)
        if not match:
            return stream_url

        server = match.group(1)
        token_part = match.group(3) or ""

        if dvr_uri:
            # Use dvr_uri directly: /pervyj/video-1771156500-11100.m3u8
            return "%s%s%s" % (server, dvr_uri, token_part)

        # Construct from alias and timestamps
        utc_str = str(int(utc_timestamp))
        dur_str = str(int(duration)) if duration else "7200"

        # Extract alias from URL path: /pervyj/index.m3u8 -> pervyj
        path_match = re.match(r"/([^/]+)/", match.group(2))
        if path_match:
            alias = path_match.group(1)
            return "%s/%s/video-%s-%s.m3u8%s" % (server, alias, utc_str, dur_str, token_part)

        # Fallback: replace index.m3u8 with video-ts-dur.m3u8
        archive_url = re.sub(r"(index)(\.m3u8)", r"video-%s-%s\2" % (utc_str, dur_str), stream_url)
        return archive_url

    # ------------------------------------------------------------------
    # Favorites (local storage)
    # ------------------------------------------------------------------

    def apply_favorites(self, channels, fav_ids):
        """
        Mark channels as favorites based on local favorites list.

        Args:
            channels: list of channel dicts
            fav_ids: list/set of channel IDs (aliases) that are favorites

        Returns:
            channels list with 'fav' field updated
        """
        fav_set = set(fav_ids) if not isinstance(fav_ids, set) else fav_ids
        for ch in channels:
            ch["fav"] = 1 if ch["id"] in fav_set else 0
        return channels

    def get_favorite_channels(self, channels, fav_ids):
        """Get only favorite channels."""
        fav_set = set(fav_ids) if not isinstance(fav_ids, set) else fav_ids
        result = []
        for ch in channels:
            if ch["id"] in fav_set:
                ch["fav"] = 1
                result.append(ch)
        return result

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate_cache(self):
        """Clear all cached data."""
        self.api.invalidate_streams_cache()
        self._category_map = None
        self._alias_to_stream = None
