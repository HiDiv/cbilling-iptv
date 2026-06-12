# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Dependency-injection context for the addon.

AddonContext bundles all runtime dependencies so that domain modules
can be tested without Kodi runtime.
"""

from typing import Protocol


class SettingsAccessor(Protocol):
    """Protocol for settings access (duck-typed)."""

    def getSetting(self, key: str) -> str:  # noqa: N802
        ...

    def setSetting(self, key: str, value: str) -> None:  # noqa: N802
        ...


class AddonContext:
    """Immutable bag of runtime dependencies passed to all domain modules."""

    def __init__(
        self,
        api_client: object,
        adapter: object,
        addon_handle: int,
        settings: SettingsAccessor,
        addon_dir: str,
        user_data_dir: str,
        temp_dir: str,
        plugin_url: str = "",
    ) -> None:
        if api_client is None:
            raise ValueError("api_client is required")
        if adapter is None:
            raise ValueError("adapter is required")
        if settings is None:
            raise ValueError("settings is required")

        self.api = api_client
        self.adapter = adapter
        self.handle = addon_handle
        self.settings = settings
        self.addon_dir = addon_dir
        self.user_data_dir = user_data_dir
        self.temp_dir = temp_dir
        self.plugin_url = plugin_url
