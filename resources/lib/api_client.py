# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""
Cbilling.TV REST API Client
Replaces Stalker Portal communication with direct REST API calls.

API Base: configurable via addon settings (api_url)
Auth: x-public-key header with public token (code from Cbilling account)

Endpoints:
  Auth:     POST /auth, GET /auth/info
  Streams:  GET /streams
  EPG:      GET /epg/now/{alias}/, GET /epg/current/{alias}/, GET /epg/{alias}/
  VOD:      GET /, GET /cat/{id}, GET /video/{id}, GET /season/{id}
  Genres:   GET /genres, GET /genres/{id}, GET /cat/{id}/genres
  Filter:   GET /filter/by_name, /filter/new, /filter/year/{y}, /filter/alpha/{l}, /filter/rating/{r}
  Servers:  GET /servers
"""

import os
import sys

# Add vendor directory to path for bundled dependencies
vendor_path = os.path.join(os.path.dirname(__file__), "vendor")
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import requests

# Import quote for URL encoding
if sys.version_info[0] >= 3:
    from urllib.parse import quote
else:
    from urllib import quote

try:
    import simplejson as json
except ImportError:
    pass

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict


class CbillingApiError(Exception):
    """Base exception for API errors."""

    pass


class CbillingAuthError(CbillingApiError):
    """Authentication failed (invalid key, expired subscription)."""

    pass


class CbillingTimeoutError(CbillingApiError):
    """Request timed out."""

    pass


class CbillingAPI:
    """
    REST API client for Cbilling.TV service.

    Usage:
        api = CbillingAPI(base_url='http://your-api-server.com', public_key='YOUR_KEY')
        streams = api.get_streams()
        epg = api.get_epg_current('pervyj', num=5)
        categories = api.get_vod_categories()
    """

    def __init__(self, base_url, public_key="", timeout=30):
        """
        Args:
            base_url: API server URL (from addon settings)
            public_key: Public token from Cbilling account (used as x-public-key header)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.public_key = public_key
        self.timeout = timeout
        # Cached data
        self._streams_cache = None
        self._auth_info_cache = None

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _request(self, path, params=None, method="GET", body=None, auth_required=False):
        """
        Make HTTP request to the API.

        Args:
            path: URL path (e.g. '/streams')
            params: Query parameters dict
            method: HTTP method
            body: JSON body for POST requests
            auth_required: Whether to include x-public-key header

        Returns:
            Parsed JSON response (dict or list)

        Raises:
            CbillingAuthError: If auth fails (404 from auth endpoints)
            CbillingTimeoutError: On timeout
            CbillingApiError: On other errors
        """
        url = self.base_url + path

        headers = {"User-Agent": "Kodi-Cbilling-Addon/2.0", "Accept": "application/json"}

        if auth_required and self.public_key:
            headers["x-public-key"] = self.public_key

        if body is not None:
            headers["Content-Type"] = "application/json"

        try:
            if method == "POST":
                response = requests.post(url, params=params, json=body, headers=headers, timeout=self.timeout)
            else:
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)

            # Check for HTTP errors
            if response.status_code == 404:
                if auth_required:
                    raise CbillingAuthError("Authentication failed. Check your public key.")
                raise CbillingApiError("Not found: %s" % path)

            response.raise_for_status()

            # Parse JSON response
            result = response.json(object_pairs_hook=OrderedDict)
            return result

        except requests.exceptions.Timeout:
            raise CbillingTimeoutError("Request timed out: %s" % path)
        except requests.exceptions.ConnectionError as e:
            raise CbillingApiError("Connection error: %s" % str(e))
        except requests.exceptions.HTTPError:
            raise CbillingApiError("HTTP %d: %s" % (response.status_code, path))
        except ValueError as e:
            raise CbillingApiError("Invalid JSON response: %s" % str(e))
        except Exception as e:
            raise CbillingApiError("Request failed: %s" % str(e))

    # ------------------------------------------------------------------
    # Auth endpoints
    # ------------------------------------------------------------------

    def authenticate(self, code):
        """
        POST /auth - Exchange numeric code for API key.

        Args:
            code: Numeric code from Cbilling account

        Returns:
            dict with api-key
        """
        return self._request("/auth", method="POST", body={"code": str(code)})

    def get_auth_info(self):
        """
        GET /auth/info - Get subscription info.

        Returns:
            dict with keys: public_token, private_token, end_time, end_date,
                           devices_num, server, vod, ssl, disable_adult
        """
        result = self._request("/auth/info", auth_required=True)
        if "data" in result:
            self._auth_info_cache = result["data"]
            return result["data"]
        return result

    # ------------------------------------------------------------------
    # Streams (IPTV channels)
    # ------------------------------------------------------------------

    def get_streams(self, force_refresh=False):
        """
        GET /streams - Get all available IPTV channels.

        Returns:
            list of channel dicts with keys: name, alias, category, sort,
            is_sd, is_hd, is_orig, archive, archive_days, logo, sound_51,
            url, proxy_url
        """
        if self._streams_cache is not None and not force_refresh:
            return self._streams_cache

        result = self._request("/streams", auth_required=True)
        if "data" in result:
            self._streams_cache = result["data"]
            return result["data"]
        return result

    def get_streams_by_category(self, category_name):
        """Get channels filtered by category name."""
        streams = self.get_streams()
        return [s for s in streams if s.get("category") == category_name]

    def get_stream_categories(self):
        """Get unique category names from streams, preserving order."""
        streams = self.get_streams()
        seen = set()
        categories = []
        for s in streams:
            cat = s.get("category", "")
            if cat and cat not in seen:
                seen.add(cat)
                categories.append(cat)
        return categories

    def get_stream_by_alias(self, alias):
        """Find a single stream by its alias."""
        streams = self.get_streams()
        for s in streams:
            if s.get("alias") == alias:
                return s
        return None

    def invalidate_streams_cache(self):
        """Force streams to be re-fetched on next call."""
        self._streams_cache = None

    # ------------------------------------------------------------------
    # EPG endpoints
    # ------------------------------------------------------------------

    def get_epg_now(self, alias):
        """
        GET /epg/now/{alias}/ - Current program for a channel.

        Args:
            alias: Stream alias (e.g. 'pervyj')

        Returns:
            dict with current EPG entry
        """
        return self._request("/epg/now/%s/" % quote(alias, safe=""))

    def get_epg_current(self, alias, num=None):
        """
        GET /epg/current/{alias}/ - Current and upcoming programs.

        Args:
            alias: Stream alias
            num: Number of EPG items to return (optional)

        Returns:
            list of EPG entries
        """
        params = {}
        if num is not None:
            params["num"] = num
        return self._request("/epg/current/%s/" % quote(alias, safe=""), params=params or None)

    def get_epg_day(self, alias, date=None):
        """
        GET /epg/{alias}/ - Full EPG for a day.

        Args:
            alias: Stream alias
            date: Date string 'YYYY-MM-DD' (optional, defaults to today)

        Returns:
            list of EPG entries for the day
        """
        params = {}
        if date:
            params["date"] = date
        return self._request("/epg/%s/" % quote(alias, safe=""), params=params or None)

    def get_epg_duration(self, alias, utc_timestamp):
        """
        GET /epg/duration/ - Get program duration info.

        Args:
            alias: Stream alias
            utc_timestamp: UTC timestamp of program start

        Returns:
            dict with duration info
        """
        return self._request("/epg/duration/", params={"stream": alias, "utc": int(utc_timestamp)})

    # ------------------------------------------------------------------
    # VOD endpoints
    # ------------------------------------------------------------------

    def get_vod_categories(self):
        """
        GET / - Get all VOD categories.

        Returns:
            list of category dicts
        """
        return self._request("/")

    def get_vod_category_content(self, category_id, page=1, per_page=20):
        """
        GET /cat/{category} - Get content from a VOD category.

        Args:
            category_id: Category ID (integer)
            page: Page number (default 1)
            per_page: Number of items per page (default 20)

        Returns:
            dict with 'data' list and 'meta' pagination info
        """
        return self._request("/cat/%s" % str(category_id), params={"page": page, "per_page": per_page})

    def get_vod_category_genres(self, category_id):
        """
        GET /cat/{category}/genres - Get genres within a category.

        Args:
            category_id: Category ID

        Returns:
            list of genre dicts
        """
        return self._request("/cat/%s/genres" % str(category_id))

    def get_vod_genres(self):
        """
        GET /genres - Get all VOD genres.

        Returns:
            list of genre dicts
        """
        return self._request("/genres")

    def get_vod_by_genre(self, genre_id, page=1, per_page=20):
        """
        GET /genres/{genre} - Get videos in a genre.

        Args:
            genre_id: Genre ID
            page: Page number (default 1)
            per_page: Number of items per page (default 20)

        Returns:
            dict with 'data' list and 'meta' pagination info
        """
        return self._request("/genres/%s" % str(genre_id), params={"page": page, "per_page": per_page})

    def get_video(self, video_id):
        """
        GET /video/{video} - Get full video description.

        Args:
            video_id: Video ID

        Returns:
            dict with video details
        """
        return self._request("/video/%s" % str(video_id))

    def get_season(self, season_id):
        """
        GET /season/{season} - Get season info with episodes.

        Args:
            season_id: Season ID

        Returns:
            list of episodes with video links
        """
        return self._request("/season/%s" % str(season_id))

    # ------------------------------------------------------------------
    # Filter / Search endpoints
    # ------------------------------------------------------------------

    def search_by_name(self, name, page=1, per_page=20):
        """
        GET /filter/by_name?name=X - Search videos by name.

        Args:
            name: Search query string
            page: Page number (default 1)
            per_page: Number of items per page (default 20)

        Returns:
            dict with 'data' list and 'meta' pagination info
        """
        return self._request("/filter/by_name", params={"name": name, "page": page, "per_page": per_page})

    def filter_new(self):
        """GET /filter/new - Get recently added videos."""
        return self._request("/filter/new")

    def filter_by_year(self, year, end_year=None, page=1, per_page=20):
        """
        GET /filter/year/{year} or /filter/year/{start}/{end}

        Args:
            year: Year or start year
            end_year: End year (optional, for range)
            page: Page number (default 1)
            per_page: Number of items per page (default 20)
        """
        if end_year:
            return self._request(
                "/filter/year/%s/%s" % (str(year), str(end_year)),
                params={"page": page, "per_page": per_page},
            )
        return self._request("/filter/year/%s" % str(year), params={"page": page, "per_page": per_page})

    def filter_by_letter(self, letter):
        """GET /filter/alpha/{letter} - Filter by first letter."""
        return self._request("/filter/alpha/%s" % quote(letter, safe=""))

    def filter_by_rating(self, min_rating, max_rating=None):
        """
        GET /filter/rating/{min} or /filter/rating/{min}/{max}

        Args:
            min_rating: Minimum rating
            max_rating: Maximum rating (optional)
        """
        if max_rating:
            return self._request("/filter/rating/%s/%s" % (str(min_rating), str(max_rating)))
        return self._request("/filter/rating/%s" % str(min_rating))

    # ------------------------------------------------------------------
    # Servers
    # ------------------------------------------------------------------

    def get_servers(self):
        """
        GET /servers - Get available IPTV servers.

        Returns:
            list of server dicts
        """
        result = self._request("/servers")
        if "data" in result:
            return result["data"]
        return result
