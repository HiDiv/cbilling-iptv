# SPDX-FileCopyrightText: Thamerlan
# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
import xbmc
import xbmcaddon
import xbmcgui

try:
    # Python 3+
    from xbmcvfs import translatePath as fsTranslatePath
except ImportError:
    # Python 2
    from xbmc import translatePath as fsTranslatePath

__addon_id__ = "plugin.video.cbilling.iptv"
__Addon = xbmcaddon.Addon()


def addon_id():
    return __Addon.getAddonInfo("id")


def data_dir():
    return __Addon.getAddonInfo("profile")


def addon_dir():
    return __Addon.getAddonInfo("path")


def log(message, loglevel=xbmc.LOGDEBUG):
    xbmc.log(str(__addon_id__ + "-" + __Addon.getAddonInfo("version") + " : " + message), level=loglevel)


def showNotification(title, message):
    xbmcgui.Dialog().notification(
        encode(getString(30000)),
        encode(message),
        time=4000,
        icon=fsTranslatePath(__Addon.getAddonInfo("path") + "/icon.png"),
        sound=False,
    )


def setSetting(name, value):
    __Addon.setSetting(name, value)


def getSetting(name):
    return __Addon.getSetting(name)


def getString(string_id):
    return __Addon.getLocalizedString(string_id)


def getRegionalTimestamp(date_time, dateformat=["dateshort"]):
    result = ""

    for aFormat in dateformat:
        result = result + ("%s " % date_time.strftime(xbmc.getRegion(aFormat)))

    return result.strip()
