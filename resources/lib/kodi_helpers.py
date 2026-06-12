# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Thin wrappers around Kodi Python API calls."""


def debug_log(msg: str) -> None:
    """Log debug message to Kodi log."""
    import xbmc

    xbmc.log("[Cbilling] %s" % str(msg), level=xbmc.LOGDEBUG)


def info_log(msg: str) -> None:
    """Log info message to Kodi log."""
    import xbmc

    xbmc.log("[Cbilling] %s" % str(msg), level=xbmc.LOGINFO)


def show_notification(title: str, message: str, duration: int = 4000) -> None:
    """Show Kodi toast notification."""
    import xbmcgui

    xbmcgui.Dialog().notification(title, message, icon="", time=duration)


def get_localized(settings, string_id: int) -> str:
    """Get localized string by ID."""
    return settings.getLocalizedString(string_id)


def get_setting(settings, key: str, default: str = "", cast=None):
    """
    Read a setting value with typed default.

    Args:
        settings: SettingsAccessor (addon or ctx.settings)
        key: setting key
        default: returned if empty or missing
        cast: optional type to cast to (int, float, bool)

    Returns:
        Typed setting value or default
    """
    raw = str(settings.getSetting(key))
    if not raw or len(raw) == 0:
        return default
    if cast is None:
        return raw
    try:
        if cast is bool:
            return raw.lower() == "true"
        return cast(raw)
    except (ValueError, TypeError):
        return default
