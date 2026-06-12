# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for context.py — AddonContext dependency injection container."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))


from context import AddonContext


class FakeAPIClient:
    """Fake API client for testing."""

    def get_channels(self):
        return []


class FakeAdapter:
    """Fake adapter for testing."""

    def adapt(self, data):
        return data


class FakeSettings:
    """Fake settings accessor for testing."""

    def getSetting(self, key):  # noqa: N802
        return ""

    def setSetting(self, key, value):  # noqa: N802
        pass


class TestAddonContextConstruction:
    """Test AddonContext construction with mock dependencies."""

    def test_construction_with_all_dependencies(self):
        """AddonContext constructs successfully with all required dependencies."""
        ctx = AddonContext(
            api_client=FakeAPIClient(),
            adapter=FakeAdapter(),
            addon_handle=1,
            settings=FakeSettings(),
            addon_dir="/addon",
            user_data_dir="/userdata",
            temp_dir="/tmp",
            plugin_url="plugin://plugin.video.cbilling.iptv/",
        )
        assert ctx is not None

    def test_construction_with_minimal_required(self):
        """AddonContext constructs with defaults for optional params."""
        ctx = AddonContext(
            api_client=FakeAPIClient(),
            adapter=FakeAdapter(),
            addon_handle=0,
            settings=FakeSettings(),
            addon_dir="/addon",
            user_data_dir="/userdata",
            temp_dir="/tmp",
        )
        assert ctx.plugin_url == ""


class TestAddonContextFieldAccess:
    """Test that all fields are accessible after construction."""

    @pytest.fixture()
    def ctx(self):
        """Create a fully populated AddonContext."""
        return AddonContext(
            api_client=FakeAPIClient(),
            adapter=FakeAdapter(),
            addon_handle=42,
            settings=FakeSettings(),
            addon_dir="/path/to/addon",
            user_data_dir="/path/to/userdata",
            temp_dir="/path/to/temp",
            plugin_url="plugin://plugin.video.cbilling.iptv/?mode=main",
        )

    def test_api_field(self, ctx):
        """api field returns the injected api_client."""
        assert isinstance(ctx.api, FakeAPIClient)

    def test_adapter_field(self, ctx):
        """adapter field returns the injected adapter."""
        assert isinstance(ctx.adapter, FakeAdapter)

    def test_handle_field(self, ctx):
        """handle field returns the injected addon_handle."""
        assert ctx.handle == 42

    def test_settings_field(self, ctx):
        """settings field returns the injected settings accessor."""
        assert isinstance(ctx.settings, FakeSettings)

    def test_addon_dir_field(self, ctx):
        """addon_dir field returns the injected path."""
        assert ctx.addon_dir == "/path/to/addon"

    def test_user_data_dir_field(self, ctx):
        """user_data_dir field returns the injected path."""
        assert ctx.user_data_dir == "/path/to/userdata"

    def test_temp_dir_field(self, ctx):
        """temp_dir field returns the injected path."""
        assert ctx.temp_dir == "/path/to/temp"

    def test_plugin_url_field(self, ctx):
        """plugin_url field returns the injected URL."""
        assert ctx.plugin_url == "plugin://plugin.video.cbilling.iptv/?mode=main"


class TestAddonContextValidation:
    """Test that missing required dependencies raise ValueError."""

    def test_none_api_client_raises(self):
        """None api_client raises ValueError."""
        with pytest.raises(ValueError, match="api_client is required"):
            AddonContext(
                api_client=None,
                adapter=FakeAdapter(),
                addon_handle=1,
                settings=FakeSettings(),
                addon_dir="/addon",
                user_data_dir="/userdata",
                temp_dir="/tmp",
            )

    def test_none_adapter_raises(self):
        """None adapter raises ValueError."""
        with pytest.raises(ValueError, match="adapter is required"):
            AddonContext(
                api_client=FakeAPIClient(),
                adapter=None,
                addon_handle=1,
                settings=FakeSettings(),
                addon_dir="/addon",
                user_data_dir="/userdata",
                temp_dir="/tmp",
            )

    def test_none_settings_raises(self):
        """None settings raises ValueError."""
        with pytest.raises(ValueError, match="settings is required"):
            AddonContext(
                api_client=FakeAPIClient(),
                adapter=FakeAdapter(),
                addon_handle=1,
                settings=None,
                addon_dir="/addon",
                user_data_dir="/userdata",
                temp_dir="/tmp",
            )
