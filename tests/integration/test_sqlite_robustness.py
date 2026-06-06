# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Integration tests for SQLite robustness: config table recovery, WAL mode, timeout.

Migrated from: test_sqlite_robustness.py
"""

import sqlite3


def test_config_table_recovery(tmp_path):
    """Config table is recreated with CREATE IF NOT EXISTS after corruption."""
    db_path = str(tmp_path / "epg.db")

    # Create DB with config table
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE config("
        "key TEXT NOT NULL PRIMARY KEY, value TEXT, "
        "inserted_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL, "
        "updated_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL)"
    )
    cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", ("db version", "1.0"))
    conn.commit()
    conn.close()

    # Drop config table (simulate corruption)
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE config")
    conn.commit()
    conn.close()

    # Verify it's gone
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='config'")
    assert cur.fetchone()[0] == 0
    conn.close()

    # Recreate with CREATE IF NOT EXISTS (the fix)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.isolation_level = None
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS config("
        "key TEXT NOT NULL PRIMARY KEY, value TEXT, "
        "inserted_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL, "
        "updated_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL)"
    )
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", ("db version", "1.0"))
    cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", ("epg last update", "2026-03-15"))
    conn.close()

    # Verify recovery
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='config'")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT value FROM config WHERE key='epg last update'")
    assert cur.fetchone()[0] == "2026-03-15"
    conn.close()


def test_config_upsert(tmp_path):
    """INSERT ON CONFLICT UPDATE works for config table."""
    db_path = str(tmp_path / "epg.db")

    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE config("
        "key TEXT NOT NULL PRIMARY KEY, value TEXT, "
        "inserted_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL, "
        "updated_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL)"
    )
    cur.execute("INSERT INTO config (key, value) VALUES (?, ?)", ("epg last update", "2026-03-15"))
    conn.commit()

    cur.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
        "updated_at = datetime('now','localtime')",
        ("epg last update", "2026-03-15 12:00:00"),
    )
    conn.commit()
    cur.execute("SELECT value FROM config WHERE key='epg last update'")
    assert cur.fetchone()[0] == "2026-03-15 12:00:00"
    conn.close()


def test_wal_mode(tmp_path):
    """WAL mode allows concurrent reads."""
    db_path = str(tmp_path / "epg.db")

    conn1 = sqlite3.connect(db_path, timeout=10)
    cur1 = conn1.cursor()
    cur1.execute("PRAGMA journal_mode=WAL")
    mode = cur1.fetchone()[0]
    assert mode == "wal"

    cur1.execute("CREATE TABLE epg(ch_id INTEGER, stop_timestamp INTEGER, epg_json TEXT)")
    cur1.execute('INSERT INTO epg VALUES (1, 1000, \'{"name":"test"}\')')
    conn1.commit()

    # Second connection can read while first is open
    conn2 = sqlite3.connect(db_path, timeout=10)
    cur2 = conn2.cursor()
    cur2.execute("SELECT * FROM epg")
    assert len(cur2.fetchall()) == 1

    # Writer inserts more; reader sees it after commit
    cur1.execute('INSERT INTO epg VALUES (2, 2000, \'{"name":"test2"}\')')
    conn1.commit()
    cur2.execute("SELECT * FROM epg")
    assert len(cur2.fetchall()) == 2

    conn2.close()
    conn1.close()


def test_timeout(tmp_path):
    """Connection with timeout parameter works."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path, timeout=10)
    cur = conn.cursor()
    cur.execute("CREATE TABLE test(id INTEGER)")
    cur.execute("INSERT INTO test VALUES (1)")
    conn.commit()
    conn.close()


def test_none_connection_guard():
    """sqlite3.connect never returns None for in-memory DB."""
    conn = sqlite3.connect(":memory:", timeout=10)
    assert conn is not None
    cur = conn.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone()[0] == 1
    conn.close()
