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
except:
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

vodCacheFile = os.path.join(__addonUserData__, "vod_cache.db")


def debug_log(msg):
    """Log debug message"""
    xbmc.log("[Cbilling] VOD Cache: %s" % str(msg), level=xbmc.LOGDEBUG)


def vod_cache_init():
    """Initialize VOD cache database"""
    if os.path.exists(vodCacheFile):
        return True

    debug_log("Creating VOD cache database")

    createCacheTable = """CREATE TABLE vod_cache (
                            movie_id INTEGER PRIMARY KEY,
                            movie_data TEXT NOT NULL,
                            cached_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL,
                            updated_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """

    createIndex = "CREATE INDEX idx_vod_cached_at ON vod_cache(cached_at)"

    createConfigTable = """CREATE TABLE IF NOT EXISTS config (
                            key TEXT NOT NULL PRIMARY KEY,
                            value TEXT,
                            inserted_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL,
                            updated_at TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()
        dbCursor.execute(createCacheTable)
        dbCursor.execute(createIndex)
        dbCursor.execute(createConfigTable)
        dbCursor.execute("INSERT INTO config (key, value) VALUES (?,?)", ("db_version", "1.0"))
        dbConn.commit()
        debug_log("VOD cache database created successfully")
        return True
    except Exception as e:
        debug_log("Failed to create VOD cache database: %s" % str(e))
        return False
    finally:
        if dbConn:
            dbConn.close()


def vod_cache_get(movie_id, max_age_days=None):
    """
    Get movie metadata from cache if not expired

    Args:
        movie_id: Movie ID
        max_age_days: Maximum age in days (None = use setting)

    Returns:
        dict: Movie metadata or None if not found/expired
    """
    if not os.path.exists(vodCacheFile):
        return None

    if max_age_days is None:
        max_age_days = int(__addon__.getSetting("vod_cache_ttl_days") or "7")

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        # Calculate expiration timestamp
        expiration = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        expiration_str = expiration.strftime("%Y-%m-%d %H:%M:%S")

        dbCursor.execute(
            "SELECT movie_data FROM vod_cache WHERE movie_id = ? AND cached_at > ?", (int(movie_id), expiration_str)
        )

        row = dbCursor.fetchone()
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
        if dbConn:
            dbConn.close()


def vod_cache_set(movie_id, movie_data):
    """
    Save movie metadata to cache

    Args:
        movie_id: Movie ID
        movie_data: Movie metadata dict

    Returns:
        bool: Success status
    """
    if not os.path.exists(vodCacheFile):
        if not vod_cache_init():
            return False

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        movie_json = json.dumps(movie_data, ensure_ascii=False)

        # Insert or replace
        dbCursor.execute(
            """INSERT OR REPLACE INTO vod_cache (movie_id, movie_data, cached_at, updated_at)
               VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'))""",
            (int(movie_id), movie_json),
        )

        dbConn.commit()
        debug_log("Cached movie_id=%s" % movie_id)
        return True

    except Exception as e:
        debug_log("Error writing to cache: %s" % str(e))
        return False
    finally:
        if dbConn:
            dbConn.close()


def vod_cache_get_multiple(movie_ids, max_age_days=None):
    """
    Get multiple movies from cache

    Args:
        movie_ids: List of movie IDs
        max_age_days: Maximum age in days

    Returns:
        dict: {movie_id: movie_data} for found items
    """
    if not os.path.exists(vodCacheFile) or not movie_ids:
        return {}

    if max_age_days is None:
        max_age_days = int(__addon__.getSetting("vod_cache_ttl_days") or "7")

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        expiration = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        expiration_str = expiration.strftime("%Y-%m-%d %H:%M:%S")

        placeholders = ",".join("?" * len(movie_ids))
        query = "SELECT movie_id, movie_data FROM vod_cache WHERE movie_id IN (%s) AND cached_at > ?" % placeholders

        dbCursor.execute(query, [int(mid) for mid in movie_ids] + [expiration_str])

        result = {}
        for row in dbCursor.fetchall():
            result[str(row[0])] = json.loads(row[1])

        debug_log("Cache: found %d/%d movies" % (len(result), len(movie_ids)))
        return result

    except Exception as e:
        debug_log("Error reading multiple from cache: %s" % str(e))
        return {}
    finally:
        if dbConn:
            dbConn.close()


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

    if not os.path.exists(vodCacheFile):
        if not vod_cache_init():
            return 0

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        cached_count = 0
        for movie_id, movie_data in movies_data.items():
            try:
                movie_json = json.dumps(movie_data, ensure_ascii=False)
                dbCursor.execute(
                    """INSERT OR REPLACE INTO vod_cache (movie_id, movie_data, cached_at, updated_at)
                       VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'))""",
                    (int(movie_id), movie_json),
                )
                cached_count += 1
            except:
                pass

        dbConn.commit()
        debug_log("Cached %d movies" % cached_count)
        return cached_count

    except Exception as e:
        debug_log("Error writing multiple to cache: %s" % str(e))
        return 0
    finally:
        if dbConn:
            dbConn.close()


def vod_cache_clear_old(max_age_days=None):
    """
    Clear old cache entries

    Args:
        max_age_days: Maximum age in days (None = use setting)

    Returns:
        int: Number of deleted entries
    """
    if not os.path.exists(vodCacheFile):
        return 0

    if max_age_days is None:
        max_age_days = int(__addon__.getSetting("vod_cache_ttl_days") or "7")

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        expiration = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
        expiration_str = expiration.strftime("%Y-%m-%d %H:%M:%S")

        dbCursor.execute("DELETE FROM vod_cache WHERE cached_at <= ?", (expiration_str,))
        deleted = dbCursor.rowcount

        dbConn.commit()

        if deleted > 0:
            debug_log("Cleared %d old cache entries" % deleted)
            # Vacuum to reclaim space
            dbCursor.execute("VACUUM")

        return deleted

    except Exception as e:
        debug_log("Error clearing old cache: %s" % str(e))
        return 0
    finally:
        if dbConn:
            dbConn.close()


def vod_cache_clear_all():
    """
    Clear all cache entries

    Returns:
        bool: Success status
    """
    if not os.path.exists(vodCacheFile):
        return True

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        dbCursor.execute("DELETE FROM vod_cache")
        deleted = dbCursor.rowcount

        dbConn.commit()

        debug_log("Cleared all cache (%d entries)" % deleted)

        # Vacuum to reclaim space
        dbCursor.execute("VACUUM")

        return True

    except Exception as e:
        debug_log("Error clearing all cache: %s" % str(e))
        return False
    finally:
        if dbConn:
            dbConn.close()


def vod_cache_delete(movie_id):
    """
    Delete specific movie from cache

    Args:
        movie_id: Movie ID

    Returns:
        bool: Success status
    """
    if not os.path.exists(vodCacheFile):
        return True

    try:
        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        dbCursor.execute("DELETE FROM vod_cache WHERE movie_id = ?", (int(movie_id),))
        dbConn.commit()

        debug_log("Deleted movie_id=%s from cache" % movie_id)
        return True

    except Exception as e:
        debug_log("Error deleting from cache: %s" % str(e))
        return False
    finally:
        if dbConn:
            dbConn.close()


def vod_cache_get_stats():
    """
    Get cache statistics

    Returns:
        dict: {total: int, size_mb: float, oldest: str, newest: str}
    """
    if not os.path.exists(vodCacheFile):
        return {"total": 0, "size_mb": 0, "oldest": None, "newest": None}

    try:
        # File size
        size_bytes = os.path.getsize(vodCacheFile)
        size_mb = size_bytes / (1024.0 * 1024.0)

        dbConn = sqlite.connect(vodCacheFile, timeout=10)
        dbCursor = dbConn.cursor()

        # Total count
        dbCursor.execute("SELECT COUNT(*) FROM vod_cache")
        total = dbCursor.fetchone()[0]

        # Oldest and newest
        dbCursor.execute("SELECT MIN(cached_at), MAX(cached_at) FROM vod_cache")
        row = dbCursor.fetchone()
        oldest = row[0] if row[0] else None
        newest = row[1] if row[1] else None

        return {"total": total, "size_mb": round(size_mb, 2), "oldest": oldest, "newest": newest}

    except Exception as e:
        debug_log("Error getting cache stats: %s" % str(e))
        return {"total": 0, "size_mb": 0, "oldest": None, "newest": None}
    finally:
        if dbConn:
            dbConn.close()
