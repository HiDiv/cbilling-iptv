# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for resources/lib/router.py."""

import base64
import os
import sys
import types
from typing import ClassVar, List
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


from router import extract_params, get_param, local_b64decode

# ---------------------------------------------------------------------------
# extract_params
# ---------------------------------------------------------------------------


class TestExtractParams:
    """Tests for extract_params with various query strings."""

    def test_valid_query_string(self):
        result = extract_params("?mode=play_live_channel&channel_id=123")
        assert result == {"mode": "play_live_channel", "channel_id": "123"}

    def test_multiple_params(self):
        result = extract_params("?mode=vod_start&cat_id=5&page_nr=2&sortby=top")
        assert result == {"mode": "vod_start", "cat_id": "5", "page_nr": "2", "sortby": "top"}

    def test_empty_string(self):
        result = extract_params("")
        assert result == {}

    def test_single_char(self):
        result = extract_params("?")
        assert result == {}

    def test_no_equals_pairs(self):
        result = extract_params("?modeonly&another")
        assert result == {}

    def test_url_encoded_values(self):
        result = extract_params("?name=hello%20world&path=%2Fsome%2Fpath")
        assert result == {"name": "hello world", "path": "/some/path"}

    def test_trailing_slash_stripped(self):
        result = extract_params("?mode=vod_start&cat_id=1/")
        assert result == {"mode": "vod_start", "cat_id": "1"}

    def test_value_with_equals_sign(self):
        result = extract_params("?url=http://example.com?x=1")
        assert result == {"url": "http://example.com?x=1"}

    def test_empty_value(self):
        result = extract_params("?mode=&channel_id=5")
        assert result == {"mode": "", "channel_id": "5"}


# ---------------------------------------------------------------------------
# get_param
# ---------------------------------------------------------------------------


class TestGetParam:
    """Tests for get_param with transforms, defaults, and error fallback."""

    def test_with_int_transform(self):
        params = {"page_nr": "3"}
        result = get_param(params, "page_nr", default=1, transform=int)
        assert result == 3

    def test_transform_failure_returns_default(self):
        params = {"page_nr": "not_a_number"}
        result = get_param(params, "page_nr", default=1, transform=int)
        assert result == 1

    def test_missing_key_returns_default(self):
        params = {"mode": "play"}
        result = get_param(params, "channel_id", default="0")
        assert result == "0"

    def test_none_transform_returns_raw(self):
        params = {"mode": "vod_start"}
        result = get_param(params, "mode", default=None, transform=None)
        assert result == "vod_start"

    def test_empty_value_returns_default(self):
        params = {"channel_id": ""}
        result = get_param(params, "channel_id", default="unknown")
        assert result == "unknown"

    def test_custom_transform(self):
        params = {"name": "TestValue"}
        result = get_param(params, "name", default="", transform=str.lower)
        assert result == "testvalue"

    def test_type_error_in_transform_returns_default(self):
        def bad_transform(val):
            raise TypeError("bad")

        params = {"key": "value"}
        result = get_param(params, "key", default="fallback", transform=bad_transform)
        assert result == "fallback"


# ---------------------------------------------------------------------------
# local_b64decode
# ---------------------------------------------------------------------------


class TestLocalB64Decode:
    """Tests for local_b64decode round-trip."""

    def test_roundtrip_simple(self):
        original = "Hello World"
        encoded = base64.urlsafe_b64encode(original.encode("utf-8")).decode("utf-8")
        # Strip padding for realistic plugin URL usage
        encoded_stripped = encoded.rstrip("=")
        assert local_b64decode(encoded_stripped) == original

    def test_roundtrip_unicode(self):
        original = "\u041a\u0430\u043d\u0430\u043b \u0422\u0412"  # Cyrillic text
        encoded = base64.urlsafe_b64encode(original.encode("utf-8")).decode("utf-8")
        encoded_stripped = encoded.rstrip("=")
        assert local_b64decode(encoded_stripped) == original

    def test_roundtrip_special_chars(self):
        original = "name/with+special=chars"
        encoded = base64.urlsafe_b64encode(original.encode("utf-8")).decode("utf-8")
        encoded_stripped = encoded.rstrip("=")
        assert local_b64decode(encoded_stripped) == original

    def test_with_full_padding(self):
        original = "test"
        encoded = base64.urlsafe_b64encode(original.encode("utf-8")).decode("utf-8")
        # Keep padding intact — function adds extra padding so it still works
        assert local_b64decode(encoded) == original


# ---------------------------------------------------------------------------
# build_dispatch_table
# ---------------------------------------------------------------------------


class TestBuildDispatchTable:
    """Tests for build_dispatch_table — verify all 28 expected mode strings."""

    EXPECTED_MODES: ClassVar[List[str]] = [
        "CBILLING_start",
        "channel_groups",
        "get_channels_list",
        "itv_fav_add_remove",
        "play_live_channel",
        "timepick_live_channel",
        "play_live_event_from_start",
        "archive_channel_dates",
        "archive_channel_epg",
        "play_archive_channel",
        "download_archive_record",
        "epg_show",
        "get_stream_servers",
        "cron_epg_init",
        "vod_start",
        "vod_get_category",
        "vod_get_category_genres",
        "vod_get_ordered_list",
        "vod_get_seasons",
        "vod_get_episodes",
        "vod_play_movie",
        "vod_search_page",
        "vod_watch_history",
        "vod_history_remove",
        "vod_history_clear",
        "show_vod_info",
        "vod_cache_manage",
        "vod_debug",
    ]
    EXPECTED_COUNT: ClassVar[int] = 28

    @patch("router.archive", create=True)
    @patch("router.auth", create=True)
    @patch("router.channels", create=True)
    @patch("router.epg_db", create=True)
    @patch("router.favorites", create=True)
    @patch("router.playback", create=True)
    @patch("router.vod", create=True)
    @patch("router.watch_history", create=True)
    def test_dispatch_table_has_all_modes(self, *mocks):
        """All 27 mode strings must be keys in the dispatch table."""
        # We need to mock the lazy imports inside build_dispatch_table
        mock_modules = {
            "resources.lib.archive": MagicMock(),
            "resources.lib.auth": MagicMock(),
            "resources.lib.channels": MagicMock(),
            "resources.lib.epg_db": MagicMock(),
            "resources.lib.favorites": MagicMock(),
            "resources.lib.playback": MagicMock(),
            "resources.lib.vod": MagicMock(),
            "resources.lib.watch_history": MagicMock(),
        }
        with patch.dict("sys.modules", mock_modules):
            from router import build_dispatch_table

            table = build_dispatch_table()

        assert len(table) == self.EXPECTED_COUNT
        for mode in self.EXPECTED_MODES:
            assert mode in table, "Missing mode: %s" % mode

    @patch("router.archive", create=True)
    @patch("router.auth", create=True)
    @patch("router.channels", create=True)
    @patch("router.epg_db", create=True)
    @patch("router.favorites", create=True)
    @patch("router.playback", create=True)
    @patch("router.vod", create=True)
    @patch("router.watch_history", create=True)
    def test_dispatch_table_values_are_callable(self, *mocks):
        """All values in the dispatch table must be callable."""
        mock_modules = {
            "resources.lib.archive": MagicMock(),
            "resources.lib.auth": MagicMock(),
            "resources.lib.channels": MagicMock(),
            "resources.lib.epg_db": MagicMock(),
            "resources.lib.favorites": MagicMock(),
            "resources.lib.playback": MagicMock(),
            "resources.lib.vod": MagicMock(),
            "resources.lib.watch_history": MagicMock(),
        }
        with patch.dict("sys.modules", mock_modules):
            from router import build_dispatch_table

            table = build_dispatch_table()

        for mode, handler in table.items():
            assert callable(handler), "Handler for '%s' is not callable" % mode


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    """Tests for dispatch function — known modes and fallback."""

    @staticmethod
    def _make_mock_modules(channels_mock=None):
        """Build sys.modules dict with resources.lib package mocks."""

        mock_channels = channels_mock or MagicMock()

        # Create a real module object for resources.lib so that
        # 'from resources.lib import channels' resolves to our mock
        resources_pkg = types.ModuleType("resources")
        resources_lib_pkg = types.ModuleType("resources.lib")
        resources_pkg.lib = resources_lib_pkg

        resources_lib_pkg.archive = MagicMock()
        resources_lib_pkg.auth = MagicMock()
        resources_lib_pkg.channels = mock_channels
        resources_lib_pkg.epg_db = MagicMock()
        resources_lib_pkg.favorites = MagicMock()
        resources_lib_pkg.playback = MagicMock()
        resources_lib_pkg.vod = MagicMock()
        resources_lib_pkg.watch_history = MagicMock()

        return {
            "resources": resources_pkg,
            "resources.lib": resources_lib_pkg,
            "resources.lib.archive": resources_lib_pkg.archive,
            "resources.lib.auth": resources_lib_pkg.auth,
            "resources.lib.channels": mock_channels,
            "resources.lib.epg_db": resources_lib_pkg.epg_db,
            "resources.lib.favorites": resources_lib_pkg.favorites,
            "resources.lib.playback": resources_lib_pkg.playback,
            "resources.lib.vod": resources_lib_pkg.vod,
            "resources.lib.watch_history": resources_lib_pkg.watch_history,
        }

    def test_known_mode_calls_handler(self):
        """dispatch with a known mode should call the corresponding handler."""
        mock_handler = MagicMock()
        mock_ctx = MagicMock()

        mock_channels = MagicMock()
        mock_channels.main_menu = mock_handler

        mock_modules = self._make_mock_modules(channels_mock=mock_channels)

        with patch.dict("sys.modules", mock_modules):
            from router import dispatch

            dispatch(mock_ctx, "?mode=CBILLING_start")

        mock_handler.assert_called_once()
        call_args = mock_handler.call_args[0]
        assert call_args[0] is mock_ctx
        assert call_args[1]["mode"] == "CBILLING_start"

    def test_none_mode_calls_init_and_start(self):
        """dispatch with no mode param calls channels.init_and_start."""
        mock_init = MagicMock()
        mock_ctx = MagicMock()

        mock_channels = MagicMock()
        mock_channels.init_and_start = mock_init

        mock_modules = self._make_mock_modules(channels_mock=mock_channels)

        with patch.dict("sys.modules", mock_modules):
            from router import dispatch

            dispatch(mock_ctx, "")

        mock_init.assert_called_once_with(mock_ctx, cron_job_request=False)

    def test_unknown_mode_calls_init_and_start(self):
        """dispatch with an unknown mode calls channels.init_and_start."""
        mock_init = MagicMock()
        mock_ctx = MagicMock()

        mock_channels = MagicMock()
        mock_channels.init_and_start = mock_init

        mock_modules = self._make_mock_modules(channels_mock=mock_channels)

        with patch.dict("sys.modules", mock_modules):
            from router import dispatch

            dispatch(mock_ctx, "?mode=totally_unknown_mode")

        mock_init.assert_called_once_with(mock_ctx, cron_job_request=False)

    def test_empty_mode_value_calls_init_and_start(self):
        """dispatch with mode= (empty value) calls channels.init_and_start."""
        mock_init = MagicMock()
        mock_ctx = MagicMock()

        mock_channels = MagicMock()
        mock_channels.init_and_start = mock_init

        mock_modules = self._make_mock_modules(channels_mock=mock_channels)

        with patch.dict("sys.modules", mock_modules):
            from router import dispatch

            dispatch(mock_ctx, "?mode=")

        mock_init.assert_called_once_with(mock_ctx, cron_job_request=False)
