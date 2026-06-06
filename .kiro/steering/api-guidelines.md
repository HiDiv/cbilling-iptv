---
description: Cbilling API guide — base URL, endpoints, request format
inclusion: fileMatch
fileMatchPattern: "**/*api*.py"
---

# API Usage Guide

## New API Server

### Base URL
Specified in addon settings (settings → API URL) or in `.env` file for testing.

### Authorization
```python
headers = {
    'x-public-key': PUBLIC_KEY  # Access code from personal account
}
```

**Important:** Do not use the old handshake + bearer token method!

## Main Endpoints

### Authorization and Info
- `POST /auth` — get api-key (if needed)
- `GET /auth/info` — subscription information

### IPTV Channels
- `GET /streams` — list of all channels with ready stream URLs
- Returns channels filtered by device settings

### EPG (TV Guide)
- `GET /epg/now/{alias}/` — current program for a channel
- `GET /epg/current/{alias}/?num=5` — several programs
- `GET /epg/{alias}/?date=YYYY-MM-DD` — full EPG for a day
- `GET /epg/duration/?stream={alias}&utc={timestamp}` — program duration

**Important:** Use channel `alias` (string), not `id` (number)!

### VOD (Movies and Series)
- `GET /` — list of all categories
- `GET /cat/{category}` — category content
- `GET /cat/{category}/genres` — category genres
- `GET /genres` — all genres
- `GET /genres/{genre}` — content by genre
- `GET /video/{video}` — video information
- `GET /season/{season}` — season episode list

### Search and Filters
- `GET /filter/by_name?name={query}` — search by name
- `GET /filter/year/{year}` — filter by year
- `GET /filter/rating/{min}` — filter by rating
- `GET /filter/alpha/{letter}` — by first letter
- `GET /filter/new` — new releases

### Servers
- `GET /servers` — list of available IPTV servers

## Stalker → New API Mapping

### Authorization
- ❌ `?action=handshake` + `?action=do_auth`
- ✅ `POST /auth` with `x-public-key` header

### Channel List
- ❌ `?type=itv&action=get_all_channels`
- ✅ `GET /streams`

### EPG
- ❌ `?type=itv&action=get_short_epg&ch_id=123`
- ✅ `GET /epg/current/{alias}/`

### VOD Categories
- ❌ `?type=vod&action=get_categories`
- ✅ `GET /`

### Stream Link Creation
- ❌ `?type=itv&action=create_link`
- ✅ Links are already included in `/streams`

### Favorites
- ❌ `?action=get_fav_ids`, `?action=set_fav`
- ✅ Stored locally in `favorites.json`

## Key Differences from Stalker

### 1. Channel Identification
- Stalker: `channel_id` (number)
- New API: `alias` (string, e.g. "pervyj")

### 2. Stream Links
- Stalker: need to call `create_link` for each channel
- New API: links are already in `/streams`, no additional requests needed

### 3. Favorites
- Stalker: stored on server
- New API: no endpoints, stored locally

### 4. Authorization
- Stalker: two-step (handshake + do_auth), bearer token
- New API: single-step, x-public-key in header

## Error Handling

### Common Errors
- 401 Unauthorized — invalid or missing public key
- 404 Not Found — wrong endpoint or ID
- 500 Internal Server Error — server-side issue

### Recommendations
- Always check the response status code
- Log errors for debugging
- Use fallback values when data is missing
- Cache data that rarely changes (EPG, channel list)

## Usage Examples

### Getting the channel list
```python
response = requests.get(
    f"{API_BASE_URL}/streams",
    headers={'x-public-key': PUBLIC_KEY}
)
channels = response.json()
```

### Getting EPG
```python
from urllib.parse import quote

alias = "pervyj"
response = requests.get(
    f"{API_BASE_URL}/epg/current/{quote(alias)}/",
    headers={'x-public-key': PUBLIC_KEY},
    params={'num': 10}
)
epg_data = response.json()
```

### Getting video information
```python
video_id = "12345"
response = requests.get(
    f"{API_BASE_URL}/video/{video_id}",
    headers={'x-public-key': PUBLIC_KEY}
)
video_info = response.json()
```

## Caching

### What to cache
- ✅ Channel list (refresh every hour)
- ✅ EPG (refresh every 30 minutes)
- ✅ VOD category list (refresh daily)
- ❌ Stream links (may contain time-limited tokens)

### How to cache in Kodi
```python
# Enable caching for directory
xbmcplugin.addDirectoryItem(
    handle=addon_handle,
    url=url,
    listitem=li,
    isFolder=True
)
xbmcplugin.endOfDirectory(
    addon_handle,
    cacheToDisc=True  # Enable caching
)
```

## Debugging

### Logging
```python
import xbmc

xbmc.log(f"[Cbilling] API request: {url}", xbmc.LOGDEBUG)
xbmc.log(f"[Cbilling] API response: {response.text}", xbmc.LOGDEBUG)
```

### Testing without Kodi
Use test scripts in the tests/ directory:
- `tests/unit/test_api_client.py`
- `tests/unit/test_api_adapter.py`
