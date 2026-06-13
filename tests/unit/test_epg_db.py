# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for epg_db.py — SQLite EPG database management and queries."""

import json
import os
import sqlite3
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


# --- Helpers ---


class FakeSettings:
    """Minimal settings accessor for AddonContext."""

    def getSetting(self, key):  # noqa: N802
        return ""

    def setSetting(self, key, value):  # noqa: N802
        pass

    def getAddonInfo(self, key):  # noqa: N802
        return ""

    def getLocalizedString(self, string_id):  # noqa: N802
        return "String_%s" % string_id


def _make_ctx(tmp_path):
    """Build a minimal AddonContext-like object pointing at tmp_path."""
    ctx = MagicMock()
    ctx.user_data_dir = str(tmp_path)
    ctx.settings = FakeSettings()
    return ctx


# --- db_connection tests ---


class TestDbConnection:
    """Test the db_connection context manager."""

    def test_yields_conn_and_cursor(self, tmp_path):
        """db_connection yields a (connection, cursor) tuple."""
        db_path = str(tmp_path / "test.db")
        from epg_db import db_connection

        with db_connection(db_path) as (conn, cursor):
            assert conn is not None
            assert cursor is not None
            # Verify they are sqlite3 types
            assert hasattr(conn, "commit")
            assert hasattr(cursor, "execute")

    def test_sets_wal_pragma(self, tmp_path):
        """db_connection sets WAL journal mode."""
        db_path = str(tmp_path / "wal_test.db")
        from epg_db import db_connection

        with db_connection(db_path) as (_conn, cursor):
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode == "wal"

    def test_connection_closed_after_block(self, tmp_path):
        """Connection is closed in finally block after with-block exits."""
        db_path = str(tmp_path / "close_test.db")
        from epg_db import db_connection

        with db_connection(db_path) as (conn, _cursor):
            # Connection is open inside the block
            conn.execute("SELECT 1")

        # After exiting, the connection should be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_logs_error_on_exception(self, tmp_path):
        """db_connection logs error via kodi_helpers.debug_log on exception."""
        from unittest.mock import patch

        db_path = str(tmp_path / "err_test.db")
        from epg_db import db_connection

        with patch("resources.lib.kodi_helpers.debug_log") as mock_debug_log:
            with pytest.raises(RuntimeError), db_connection(db_path) as (_conn, _cursor):
                raise RuntimeError("test error")

            # kodi_helpers.debug_log should have been called
            mock_debug_log.assert_called_once()
            call_arg = mock_debug_log.call_args[0][0]
            assert "test error" in call_arg


# --- create_db tests ---


class TestCreateDb:
    """Test create_db function."""

    def test_creates_config_table(self, tmp_path):
        """create_db creates a database with config table."""
        from epg_db import create_db

        ctx = _make_ctx(tmp_path)
        result = create_db(ctx)
        assert result is True

        # Verify the database exists and has config table
        db_path = os.path.join(str(tmp_path), "epg.db")
        assert os.path.exists(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='config'")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_returns_true_if_db_exists(self, tmp_path):
        """create_db returns True immediately if DB file already exists."""
        from epg_db import create_db

        ctx = _make_ctx(tmp_path)
        # Create the DB first
        create_db(ctx)
        # Second call should return True without re-creating
        result = create_db(ctx)
        assert result is True


# --- create_epg_table tests ---


class TestCreateEpgTable:
    """Test create_epg_table function."""

    def test_creates_epg_and_genres_tables(self, tmp_path):
        """create_epg_table creates epg and genres tables."""
        from epg_db import create_epg_table

        ctx = _make_ctx(tmp_path)
        result = create_epg_table(ctx)
        assert result is True

        db_path = os.path.join(str(tmp_path), "epg.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check epg table exists
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='epg'")
        assert cursor.fetchone()[0] == 1

        # Check genres table exists
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='genres'")
        assert cursor.fetchone()[0] == 1
        conn.close()


# --- get_genres tests ---


class TestGetGenres:
    """Test get_genres function."""

    def test_returns_list_of_dicts(self, tmp_path):
        """get_genres returns list of dicts from genres table."""
        from epg_db import create_epg_table, get_genres

        ctx = _make_ctx(tmp_path)
        create_epg_table(ctx)

        # Insert test genres
        db_path = os.path.join(str(tmp_path), "epg.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO genres (id, title, censored) VALUES (?, ?, ?)",
            [(1, "Action", 0), (2, "Comedy", 0), (3, "Adult", 1)],
        )
        conn.commit()
        conn.close()

        result = get_genres(ctx)
        assert len(result) == 3
        assert result[0] == {"id": 1, "title": "Action", "censored": 0}
        assert result[2] == {"id": 3, "title": "Adult", "censored": 1}

    def test_returns_empty_if_db_missing(self, tmp_path):
        """get_genres returns [] if DB file doesn't exist."""
        from epg_db import get_genres

        ctx = _make_ctx(tmp_path)
        result = get_genres(ctx)
        assert result == []


# --- get_current_epg tests ---


class TestGetCurrentEpg:
    """Test get_current_epg function."""

    def test_returns_dict_for_matching_aliases(self, tmp_path):
        """get_current_epg returns dict for matching channel aliases."""
        from epg_db import create_epg_table, get_current_epg

        ctx = _make_ctx(tmp_path)
        create_epg_table(ctx)

        # Insert EPG data with future stop_timestamp
        future_ts = int(time.time()) + 3600
        epg_data = json.dumps(
            {
                "ch_id": "channel1",
                "name": "Test Show",
                "time": "20:00",
                "time_to": "21:00",
            }
        )

        db_path = os.path.join(str(tmp_path), "epg.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO epg (ch_id, stop_timestamp, epg_json) VALUES (?, ?, ?)",
            ("channel1", future_ts, epg_data),
        )
        conn.commit()
        conn.close()

        result = get_current_epg(ctx, ["channel1"])
        assert "channel1" in result
        assert result["channel1"]["name"] == "Test Show"

    def test_returns_empty_for_empty_aliases(self, tmp_path):
        """get_current_epg returns {} for empty aliases list."""
        from epg_db import create_epg_table, get_current_epg

        ctx = _make_ctx(tmp_path)
        create_epg_table(ctx)

        result = get_current_epg(ctx, [])
        assert result == {}


# --- is_valid tests ---


class TestIsValid:
    """Test is_valid function."""

    def test_returns_false_when_no_db(self, tmp_path):
        """is_valid returns False when DB does not exist and create_db fails."""
        from unittest.mock import patch

        from epg_db import is_valid

        ctx = _make_ctx(tmp_path)
        # Make create_db fail by mocking it
        with patch("epg_db.create_db", return_value=False), patch("epg_db.os.path.exists", return_value=False):
            result = is_valid(ctx, hours_to_preload=6)
        assert result is False

    def test_returns_false_when_epg_table_missing(self, tmp_path):
        """is_valid returns False when epg table does not exist."""
        from epg_db import create_db, is_valid

        ctx = _make_ctx(tmp_path)
        # Create DB but don't create epg table
        create_db(ctx)

        result = is_valid(ctx, hours_to_preload=6)
        assert result is False

    def test_returns_false_when_no_future_epg(self, tmp_path):
        """is_valid returns False when EPG data is all in the past."""
        from epg_db import create_epg_table, is_valid

        ctx = _make_ctx(tmp_path)
        create_epg_table(ctx)

        # Insert only past EPG data
        past_ts = int(time.time()) - 3600
        db_path = os.path.join(str(tmp_path), "epg.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO epg (ch_id, stop_timestamp, epg_json) VALUES (?, ?, ?)",
            ("ch1", past_ts, '{"name": "Old Show"}'),
        )
        conn.commit()
        conn.close()

        result = is_valid(ctx, hours_to_preload=6)
        assert result is False

    def test_returns_true_when_sufficient_future_epg(self, tmp_path):
        """is_valid returns True when enough future EPG exists."""
        from epg_db import create_epg_table, is_valid

        ctx = _make_ctx(tmp_path)
        # Override getSetting to return next_epg_limit
        ctx.settings.getSetting = lambda key: "3" if key == "next_epg_limit" else ""
        create_epg_table(ctx)

        # Insert multiple future EPG entries per channel
        future_ts = int(time.time()) + 3600
        db_path = os.path.join(str(tmp_path), "epg.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for i in range(5):
            cursor.execute(
                "INSERT INTO epg (ch_id, stop_timestamp, epg_json) VALUES (?, ?, ?)",
                ("ch1", future_ts + i * 1800, '{"name": "Show %d"}' % i),
            )
        conn.commit()
        conn.close()

        result = is_valid(ctx, hours_to_preload=6)
        assert result is True


# --- reload tests ---


class TestReload:
    """Test reload function — full EPG load from mocked API into SQLite."""

    def test_reload_success_inserts_epg_data(self, tmp_path):
        """reload with mocked API stores EPG entries in SQLite."""
        from epg_db import get_current_epg, reload

        ctx = _make_ctx(tmp_path)

        # Mock API: 2 channels with EPG data
        future_ts = int(time.time()) + 7200
        ctx.api = MagicMock()
        ctx.api.get_streams.return_value = [
            {"alias": "channel_a", "name": "Channel A"},
            {"alias": "channel_b", "name": "Channel B"},
        ]
        ctx.adapter = MagicMock()
        ctx.adapter.get_day_epg.return_value = [
            {
                "t_time": "20:00",
                "t_time_to": "21:00",
                "start_timestamp": str(future_ts - 3600),
                "stop_timestamp": str(future_ts),
                "name": "Test Program",
                "descr": "Description",
                "duration": 3600,
            },
        ]
        ctx.adapter.get_genres.return_value = [
            {"id": 1, "title": "News", "censored": "0"},
        ]

        result = reload(ctx, hours_to_preload=24, background_job=True)
        assert result is True

        # Verify data was actually written to SQLite
        epg_result = get_current_epg(ctx, ["channel_a", "channel_b"])
        assert "channel_a" in epg_result
        assert epg_result["channel_a"]["name"] == "Test Program"

    def test_reload_no_streams_returns_false(self, tmp_path):
        """reload returns False when API returns no streams."""
        from epg_db import reload

        ctx = _make_ctx(tmp_path)
        ctx.api = MagicMock()
        ctx.api.get_streams.return_value = None
        ctx.adapter = MagicMock()

        result = reload(ctx, hours_to_preload=24, background_job=True)
        assert result is False

    def test_reload_api_exception_returns_false(self, tmp_path):
        """reload returns False when API raises an exception."""
        from epg_db import reload

        ctx = _make_ctx(tmp_path)
        ctx.api = MagicMock()
        ctx.api.get_streams.side_effect = Exception("Network error")
        ctx.adapter = MagicMock()

        result = reload(ctx, hours_to_preload=24, background_job=True)
        assert result is False

    def test_reload_skips_channels_without_alias(self, tmp_path):
        """reload skips channels that have no alias field."""
        from epg_db import reload

        ctx = _make_ctx(tmp_path)
        future_ts = int(time.time()) + 7200
        ctx.api = MagicMock()
        ctx.api.get_streams.return_value = [
            {"alias": "", "name": "No Alias"},
            {"alias": "good_ch", "name": "Good Channel"},
        ]
        ctx.adapter = MagicMock()
        ctx.adapter.get_day_epg.return_value = [
            {
                "t_time": "10:00",
                "t_time_to": "11:00",
                "start_timestamp": str(future_ts - 3600),
                "stop_timestamp": str(future_ts),
                "name": "Morning Show",
                "descr": "",
                "duration": 3600,
            },
        ]
        ctx.adapter.get_genres.return_value = []

        result = reload(ctx, hours_to_preload=24, background_job=True)
        assert result is True
        # get_day_epg should only be called for "good_ch", not the empty alias
        ctx.adapter.get_day_epg.assert_called_once()
        call_alias = ctx.adapter.get_day_epg.call_args[0][0]
        assert call_alias == "good_ch"

    def test_reload_handles_adapter_exception_per_channel(self, tmp_path):
        """reload continues when get_day_epg raises for one channel."""
        from epg_db import get_genres, reload

        ctx = _make_ctx(tmp_path)
        ctx.api = MagicMock()
        ctx.api.get_streams.return_value = [
            {"alias": "fail_ch", "name": "Failing"},
            {"alias": "ok_ch", "name": "OK Channel"},
        ]
        future_ts = int(time.time()) + 7200

        def side_effect_epg(alias, date=None):
            if alias == "fail_ch":
                raise Exception("timeout")
            return [
                {
                    "t_time": "12:00",
                    "t_time_to": "13:00",
                    "start_timestamp": str(future_ts - 3600),
                    "stop_timestamp": str(future_ts),
                    "name": "Good Program",
                    "descr": "",
                    "duration": 3600,
                },
            ]

        ctx.adapter = MagicMock()
        ctx.adapter.get_day_epg.side_effect = side_effect_epg
        ctx.adapter.get_genres.return_value = [{"id": 5, "title": "Sport", "censored": "0"}]

        result = reload(ctx, hours_to_preload=24, background_job=True)
        assert result is True

        # Genres should still be saved even if one channel failed
        genres = get_genres(ctx)
        assert len(genres) == 1
        assert genres[0]["title"] == "Sport"

    def test_reload_with_interactive_dialog(self, tmp_path):
        """reload with background_job=False uses DialogProgress."""
        import xbmcgui
        from epg_db import reload

        ctx = _make_ctx(tmp_path)
        future_ts = int(time.time()) + 7200
        ctx.api = MagicMock()
        ctx.api.get_streams.return_value = [
            {"alias": "ch1", "name": "Channel 1"},
        ]
        ctx.adapter = MagicMock()
        ctx.adapter.get_day_epg.return_value = [
            {
                "t_time": "14:00",
                "t_time_to": "15:00",
                "start_timestamp": str(future_ts - 3600),
                "stop_timestamp": str(future_ts),
                "name": "Afternoon Show",
                "descr": "",
                "duration": 3600,
            },
        ]
        ctx.adapter.get_genres.return_value = []

        # Mock DialogProgress
        mock_dialog = MagicMock()
        mock_dialog.iscanceled.return_value = False
        xbmcgui.DialogProgress = MagicMock(return_value=mock_dialog)

        result = reload(ctx, hours_to_preload=24, background_job=False)
        assert result is True

        # Dialog should have been created and closed
        xbmcgui.DialogProgress.assert_called_once()
        mock_dialog.create.assert_called_once()
        mock_dialog.close.assert_called_once()
        mock_dialog.update.assert_called()

    def test_reload_batch_insert_over_300(self, tmp_path):
        """reload flushes batch when epg_list exceeds 300 items."""
        from epg_db import reload

        ctx = _make_ctx(tmp_path)
        future_ts = int(time.time()) + 7200
        ctx.api = MagicMock()
        ctx.api.get_streams.return_value = [{"alias": "big_ch", "name": "Big"}]

        # Return 350 programs to trigger batch flush
        programs = []
        for i in range(350):
            programs.append(
                {
                    "t_time": "%02d:00" % (i % 24),
                    "t_time_to": "%02d:30" % (i % 24),
                    "start_timestamp": str(future_ts + i * 1800),
                    "stop_timestamp": str(future_ts + (i + 1) * 1800),
                    "name": "Program %d" % i,
                    "descr": "",
                    "duration": 1800,
                }
            )

        ctx.adapter = MagicMock()
        ctx.adapter.get_day_epg.return_value = programs
        ctx.adapter.get_genres.return_value = []

        result = reload(ctx, hours_to_preload=24, background_job=True)
        assert result is True

        # Verify all 350 entries were inserted
        db_path = os.path.join(str(tmp_path), "epg.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM epg")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 350
