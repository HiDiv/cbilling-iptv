# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""
VOD metadata cache management using SQLite
"""

import datetime
import json
import os

try:
    from sqlite3 import dbapi2 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

import xbmc
import xbmcaddon
import xbmcvfs

__addon__ = xbmcaddon.Addon(id="plugin.video.cbilling.iptv")

# Get addon user data path
if hasattr(xbmcvfs, "translatePath"):
    __addonUserData__ = xbmcvfs.translatePath(__addon__.getAddonInfo("profile"))
else:
    __addonUserData__ = xbmc.translatePath(__addon__.getAddonInfo("profile"))

vod_cache_file = os.path.join(__addonUserData__, "vod_cache.db")


def debug_log(msg):
    """Log debug message"""
    xbmc.log("[Cbilling] VOD Cache: %s" % str(msg), level=xbmc.LOGDEBUG)


def vod_cache_init():
    """Initialize VOD cache database"""
    if os.path.exists(vod_cache_file):
        return True

    debug_log("Creating VOD cache database")

    create_cache_sql = """CREATE TABLE vod_cache (
                            movie_id INTEGER PRIMARY KEY,
                            movie_data TEXT NOT NULL,
                            cached_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL,
                            updated_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """

    create_index_sql = "CREATE INDEX idx_vod_cached_at ON vod_cache(cached_at)"

    create_config_sql = """CREATE TABLE IF NOT EXISTS config (
                            key TEXT NOT NULL PRIMARY KEY,
                            value TEXT,
                            inserted_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL,
                            updated_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()
        db_cursor.execute(create_cache_sql)
        db_cursor.execute(create_index_sql)
        db_cursor.execute(create_config_sql)
        db_cursor.execute("INSERT INTO config (key, value) VALUES (?,?)", ("db_version", "1.0"))
        db_conn.commit()
        debug_log("VOD cache database created successfully")
        return True
    except Exception as e:
        debug_log("Failed to create VOD cache database: %s" % str(e))
        return False
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_get(movie_id, max_age_days=None):
    """
    Get movie metadata from cache if not expired

    Args:
        movie_id: Movie ID
        max_age_days: Maximum age in days (None = use setting)

    Returns:
        dict: Movie metadata or None if not found/expired
    """
    if not os.path.exists(vod_cache_file):
        return None

    if max_age_days is None:
        max_age_days = int(__addon__.getSetting("vod_cache_ttl_days") or "7")

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        # Calculate expiration timestamp
        expiration = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        expiration_str = expiration.strftime("%Y-%m-%d %H:%M:%S")

        db_cursor.execute(
            "SELECT movie_data FROM vod_cache WHERE movie_id = ? AND cached_at > ?", (int(movie_id), expiration_str)
        )

        row = db_cursor.fetchone()
        if row:
            debug_log("Cache HIT for movie_id=%s" % movie_id)
            return json.loads(row[0])
        else:
            debug_log("Cache MISS for movie_id=%s" % movie_id)
            return None

    except Exception as e:
        debug_log("Error reading from cache: %s" % str(e))
        return None
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_set(movie_id, movie_data):
    """
    Save movie metadata to cache

    Args:
        movie_id: Movie ID
        movie_data: Movie metadata dict

    Returns:
        bool: Success status
    """
    if not os.path.exists(vod_cache_file) and not vod_cache_init():
        return False

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        movie_json = json.dumps(movie_data, ensure_ascii=False)

        # Insert or replace
        db_cursor.execute(
            """INSERT OR REPLACE INTO vod_cache (movie_id, movie_data, cached_at, updated_at)
               VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'))""",
            (int(movie_id), movie_json),
        )

        db_conn.commit()
        debug_log("Cached movie_id=%s" % movie_id)
        return True

    except Exception as e:
        debug_log("Error writing to cache: %s" % str(e))
        return False
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_get_multiple(movie_ids, max_age_days=None):
    """
    Get multiple movies from cache

    Args:
        movie_ids: List of movie IDs
        max_age_days: Maximum age in days

    Returns:
        dict: {movie_id: movie_data} for found items
    """
    if not os.path.exists(vod_cache_file) or not movie_ids:
        return {}

    if max_age_days is None:
        max_age_days = int(__addon__.getSetting("vod_cache_ttl_days") or "7")

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        expiration = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        expiration_str = expiration.strftime("%Y-%m-%d %H:%M:%S")

        placeholders = ",".join("?" * len(movie_ids))
        query = "SELECT movie_id, movie_data FROM vod_cache WHERE movie_id IN (%s) AND cached_at > ?" % placeholders

        db_cursor.execute(query, [int(mid) for mid in movie_ids] + [expiration_str])

        result = {}
        for row in db_cursor.fetchall():
            result[str(row[0])] = json.loads(row[1])

        debug_log("Cache: found %d/%d movies" % (len(result), len(movie_ids)))
        return result

    except Exception as e:
        debug_log("Error reading multiple from cache: %s" % str(e))
        return {}
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_set_multiple(movies_data):
    """
    Save multiple movies to cache

    Args:
        movies_data: dict {movie_id: movie_data}

    Returns:
        int: Number of cached items
    """
    if not movies_data:
        return 0

    if not os.path.exists(vod_cache_file) and not vod_cache_init():
        return 0

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        cached_count = 0
        for movie_id, movie_data in movies_data.items():
            try:
                movie_json = json.dumps(movie_data, ensure_ascii=False)
                db_cursor.execute(
                    """INSERT OR REPLACE INTO vod_cache (movie_id, movie_data, cached_at, updated_at)
                       VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'))""",
                    (int(movie_id), movie_json),
                )
                cached_count += 1
            except (ValueError, TypeError, sqlite.Error):
                pass

        db_conn.commit()
        debug_log("Cached %d movies" % cached_count)
        return cached_count

    except Exception as e:
        debug_log("Error writing multiple to cache: %s" % str(e))
        return 0
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_clear_old(max_age_days=None):
    """
    Clear old cache entries

    Args:
        max_age_days: Maximum age in days (None = use setting)

    Returns:
        int: Number of deleted entries
    """
    if not os.path.exists(vod_cache_file):
        return 0

    if max_age_days is None:
        max_age_days = int(__addon__.getSetting("vod_cache_ttl_days") or "7")

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        expiration = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        expiration_str = expiration.strftime("%Y-%m-%d %H:%M:%S")

        db_cursor.execute("DELETE FROM vod_cache WHERE cached_at <= ?", (expiration_str,))
        deleted = db_cursor.rowcount

        db_conn.commit()

        if deleted > 0:
            debug_log("Cleared %d old cache entries" % deleted)
            # Vacuum to reclaim space
            db_cursor.execute("VACUUM")

        return deleted

    except Exception as e:
        debug_log("Error clearing old cache: %s" % str(e))
        return 0
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_clear_all():
    """
    Clear all cache entries

    Returns:
        bool: Success status
    """
    if not os.path.exists(vod_cache_file):
        return True

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        db_cursor.execute("DELETE FROM vod_cache")
        deleted = db_cursor.rowcount

        db_conn.commit()

        debug_log("Cleared all cache (%d entries)" % deleted)

        # Vacuum to reclaim space
        db_cursor.execute("VACUUM")

        return True

    except Exception as e:
        debug_log("Error clearing all cache: %s" % str(e))
        return False
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_delete(movie_id):
    """
    Delete specific movie from cache

    Args:
        movie_id: Movie ID

    Returns:
        bool: Success status
    """
    if not os.path.exists(vod_cache_file):
        return True

    db_conn = None
    try:
        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        db_cursor.execute("DELETE FROM vod_cache WHERE movie_id = ?", (int(movie_id),))
        db_conn.commit()

        debug_log("Deleted movie_id=%s from cache" % movie_id)
        return True

    except Exception as e:
        debug_log("Error deleting from cache: %s" % str(e))
        return False
    finally:
        if db_conn:
            db_conn.close()


def vod_cache_get_stats():
    """
    Get cache statistics

    Returns:
        dict: {total: int, size_mb: float, oldest: str, newest: str}
    """
    if not os.path.exists(vod_cache_file):
        return {"total": 0, "size_mb": 0, "oldest": None, "newest": None}

    db_conn = None
    try:
        # File size
        size_bytes = os.path.getsize(vod_cache_file)
        size_mb = size_bytes / (1024.0 * 1024.0)

        db_conn = sqlite.connect(vod_cache_file, timeout=10)
        db_cursor = db_conn.cursor()

        # Total count
        db_cursor.execute("SELECT COUNT(*) FROM vod_cache")
        total = db_cursor.fetchone()[0]

        # Oldest and newest
        db_cursor.execute("SELECT MIN(cached_at), MAX(cached_at) FROM vod_cache")
        row = db_cursor.fetchone()
        oldest = row[0] if row[0] else None
        newest = row[1] if row[1] else None

        return {"total": total, "size_mb": round(size_mb, 2), "oldest": oldest, "newest": newest}

    except Exception as e:
        debug_log("Error getting cache stats: %s" % str(e))
        return {"total": 0, "size_mb": 0, "oldest": None, "newest": None}
    finally:
        if db_conn:
            db_conn.close()
