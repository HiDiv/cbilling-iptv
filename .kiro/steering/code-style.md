---
description: Python code style — imports, logging, SPDX headers, English-only comments
inclusion: fileMatch
fileMatchPattern: "**/*.py"
---

# Code Style and Best Practices

## Python Version
- Target version: Python 3.8+ (Kodi 18+ compatibility)
- Current development: Python 3.10.12
- Do not use Python 2 constructs!

## Virtual Environment (venv)
- **ALWAYS** use venv to run Python scripts
- **DO NOT** use system python3 directly
- Run commands: `bash -c "source venv/bin/activate && python test_script.py"`
- This ensures isolation and correct dependencies

## Imports

### Import Order
1. Standard library
2. Third-party libraries
3. Kodi modules
4. Local modules

```python
# Standard library
import os
import json
from urllib.parse import quote, urlencode

# Third-party libraries
import requests

# Kodi modules
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Local modules
from resources.lib import api_client
from resources.lib import utils
```

## Encoding and Strings

### Always use UTF-8
```python
# At the beginning of the file (if needed)
# -*- coding: utf-8 -*-
```

### Strings
- Use f-strings for formatting (Python 3.6+)
- For URLs use `urllib.parse.quote()`

```python
# Good
message = f"Channel: {channel_name}"
url = f"{base_url}/epg/{quote(alias)}/"

# Bad
message = "Channel: %s" % channel_name
url = base_url + "/epg/" + alias + "/"
```

## Logging

### Use Kodi Logging
```python
import xbmc

# Log levels
xbmc.log("[Cbilling] Debug message", xbmc.LOGDEBUG)
xbmc.log("[Cbilling] Info message", xbmc.LOGINFO)
xbmc.log("[Cbilling] Warning message", xbmc.LOGWARNING)
xbmc.log("[Cbilling] Error message", xbmc.LOGERROR)
```

### Message Format
- Always start with `[Cbilling]` for addon identification
- Include context: function, parameters, result
- Log errors with traceback

```python
try:
    result = api_client.get_channels()
    xbmc.log(f"[Cbilling] Got {len(result)} channels", xbmc.LOGDEBUG)
except Exception as e:
    xbmc.log(f"[Cbilling] Error getting channels: {str(e)}", xbmc.LOGERROR)
    import traceback
    xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
```

## Error Handling

### Always Handle Exceptions
```python
# Good
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.RequestException as e:
    xbmc.log(f"[Cbilling] API error: {e}", xbmc.LOGERROR)
    return None
except json.JSONDecodeError as e:
    xbmc.log(f"[Cbilling] JSON parse error: {e}", xbmc.LOGERROR)
    return None

# Bad
response = requests.get(url)
data = response.json()
```

### Use Fallback Values
```python
# Good
channel_name = channel.get('name', 'Unknown Channel')
logo = channel.get('logo') or 'DefaultVideo.png'

# Bad
channel_name = channel['name']  # KeyError if 'name' is missing
```

## Working with Kodi API

### ListItem
```python
li = xbmcgui.ListItem(label=title)
li.setArt({
    'thumb': logo,
    'icon': logo,
    'fanart': fanart
})
li.setInfo('video', {
    'title': title,
    'plot': description,
    'genre': genre
})
```

### Adding Items to Directory
```python
xbmcplugin.addDirectoryItem(
    handle=addon_handle,
    url=url,
    listitem=li,
    isFolder=True  # True for folders, False for playable items
)
```

### Finishing Directory
```python
xbmcplugin.endOfDirectory(
    addon_handle,
    succeeded=True,
    cacheToDisc=True  # Enable caching
)
```

## Working with Settings

### Reading Settings
```python
addon = xbmcaddon.Addon()
public_key = addon.getSetting('user_login')
api_url = addon.getSetting('api_url')
debug = addon.getSetting('debug') == 'true'
```

### Writing Settings
```python
addon.setSetting('last_update', str(time.time()))
```

## File System

### Paths
```python
import xbmcvfs

# Addon data path
addon_data_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))

# Create directory
if not xbmcvfs.exists(addon_data_path):
    xbmcvfs.mkdirs(addon_data_path)

# Read file
with xbmcvfs.File(file_path, 'r') as f:
    content = f.read()

# Write file
with xbmcvfs.File(file_path, 'w') as f:
    f.write(content)
```

## Performance

### Caching
- Cache data that rarely changes
- Use `cacheToDisc=True` for directories
- Store cache in addon data directory

### Lazy Loading
- Do not load all data at once
- Use pagination where possible
- Load details only when needed

### Timeouts
```python
# Always specify timeout for HTTP requests
response = requests.get(url, timeout=10)
```

## Compatibility

### Kodi Versions
- Support minimum Kodi 18 (Leia)
- Test on Kodi 20 (Nexus)
- Use `xbmc.python` version 3.0.0+

### Dependencies
- All dependencies must be available as Kodi modules
- Specify dependencies in `addon.xml`
- Do not use pip install at runtime!

## Security

### Do Not Store Secrets in Code
```python
# Good
public_key = addon.getSetting('user_login')

# Bad
public_key = "hardcoded_key_here"
```

### Input Validation
```python
# Validate API data
if not isinstance(channels, list):
    xbmc.log("[Cbilling] Invalid channels data", xbmc.LOGERROR)
    return []

# Check required fields
if 'id' not in channel or 'name' not in channel:
    xbmc.log(f"[Cbilling] Invalid channel data: {channel}", xbmc.LOGWARNING)
    continue
```

## SPDX License Headers

### Mandatory Requirement

**All new and modified Python files MUST contain an SPDX header** at the very beginning of the file.

### Header Format

For files authored by HiDiv:
```python
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
```

For files with two authors (Thamerlan + HiDiv):
```python
# SPDX-FileCopyrightText: Thamerlan
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
```

### Rules

- The header must be the **first lines** of the file (before any imports and docstrings)
- Do not add SPDX headers to vendored libraries (`resources/lib/vendor/`)
- When creating a new `.py` file — always add an SPDX header
- When substantially modifying a file — verify the header is present

## Documentation

### Docstrings
```python
def get_channels(category_id=None):
    """
    Get the list of channels.

    Args:
        category_id (str, optional): Category ID for filtering

    Returns:
        list: List of channels or empty list on error

    Example:
        channels = get_channels(category_id="1")
    """
    pass
```

### Comments

**All comments and documentation in source code — ENGLISH ONLY.**

- Explain "why", not "what"
- Comment complex logic
- Update comments when code changes
- Docstrings — in English
- Inline comments — in English
- TODO/FIXME/HACK — in English

```python
# Good
# API returns empty name for seasons, generate from number
if not season_name:
    season_name = f"Season {season_number}"

# Bad — Russian comments not allowed
# Проверяем season_name
if not season_name:
    season_name = f"Season {season_number}"
```

### Exceptions for Russian in Code

- String literals for user interface (UI strings) may be in Russian
- Localization files (`resources/language/`) contain Russian text

## Localization (CRITICALLY IMPORTANT)

### Mandatory Requirement

**ALL user-visible text MUST use the localization mechanism (`get_txt()` / `getLocalizedString()`).**

### Rules

1. **NEVER hardcode** user-visible strings (labels, messages, plot text) directly in Python code
2. **ALWAYS** add new strings to both `resources/language/resource.language.ru_ru/strings.po` and `resources/language/resource.language.en_gb/strings.po`
3. **Use `get_txt(XXXXX)`** where XXXXX is the string ID from strings.po
4. **During code review** — reject any code that contains hardcoded Russian or English text shown to the user
5. String IDs must be sequential, starting from the last used ID

### What MUST be localized

- Menu item labels
- Dialog messages and titles
- EPG format labels ("Сейчас:", "Далее:", etc.)
- Time format strings ("мин.", "через", etc.)
- Error messages shown to user
- Setting labels (referenced by ID in settings.xml)

### What does NOT need localization

- Debug log messages (only visible to developers)
- Code comments
- Internal variable names
- API parameters

### Example

```python
# ❌ WRONG — hardcoded Russian text
plot_parts.append("[B]Сейчас:[/B] %s" % title)
plot_parts.append("(%d мин. идёт)" % elapsed)

# ✅ CORRECT — localized strings
plot_parts.append("[B]%s[/B] %s" % (get_txt(30156), title))
plot_parts.append("(%s)" % (get_txt(30159) % elapsed))
```

### Adding a New String

1. Find the last used ID in strings.po (e.g., 30160)
2. Add to `resources/language/resource.language.ru_ru/strings.po`:
   ```
   msgctxt "#30161"
   msgid "New label"
   msgstr "Новый лейбл"
   ```
3. Add to `resources/language/resource.language.en_gb/strings.po`:
   ```
   msgctxt "#30161"
   msgid "New label"
   msgstr ""
   ```
4. Use in code: `get_txt(30161)`

## Testing

### Test Scripts
- Create test scripts for verification without Kodi
- Use venv for isolation
- Store tests in the `tests/` directory

### Debugging
- Enable debug mode in settings
- Check Kodi logs: `~/.kodi/temp/kodi.log`
- Use `xbmc.log()` for debug messages
