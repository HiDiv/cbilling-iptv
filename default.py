# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Entry point for the Kodi addon — constructs context and dispatches."""

import os
import sys

# Add vendor directory to path for bundled dependencies
vendor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "lib", "vendor")
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import xbmcaddon
from xbmcvfs import translatePath as fs_translate_path  # noqa: N813

from resources.lib.api_adapter import ApiAdapter
from resources.lib.api_client import CbillingAPI
from resources.lib.context import AddonContext
from resources.lib.router import dispatch

PLUGIN_ID = "plugin.video.cbilling.iptv"


def main():
    """Construct AddonContext and dispatch the URL request."""
    addon = xbmcaddon.Addon(id=PLUGIN_ID)
    addon_handle = int(sys.argv[1])
    argv2 = sys.argv[2] if len(sys.argv) > 2 else ""

    addon_dir = fs_translate_path(addon.getAddonInfo("path"))
    user_data_dir = fs_translate_path(addon.getAddonInfo("profile"))
    temp_dir = fs_translate_path("special://temp")
    plugin_url = sys.argv[0]

    # Ensure user data directory exists
    os.makedirs(user_data_dir, exist_ok=True)

    # Construct API client from settings
    api_url = str(addon.getSetting("api_url"))
    public_key = str(addon.getSetting("user_login"))
    api = CbillingAPI(api_url, public_key)

    # Construct adapter with timezone from settings
    timezone_name = str(addon.getSetting("stb_timezone"))
    adapter = ApiAdapter(api, timezone_name=timezone_name)

    # Build context
    ctx = AddonContext(
        api_client=api,
        adapter=adapter,
        addon_handle=addon_handle,
        settings=addon,
        addon_dir=addon_dir,
        user_data_dir=user_data_dir,
        temp_dir=temp_dir,
        plugin_url=plugin_url,
    )

    dispatch(ctx, argv2)


if __name__ == "__main__":
    main()
else:
    main()
