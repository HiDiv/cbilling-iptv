# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""SQLite EPG database management and queries."""

import contextlib
import datetime
import json
import os
import time
from typing import TYPE_CHECKING, Dict, Generator, List, Tuple

if TYPE_CHECKING:
    from resources.lib.context import AddonContext


@contextlib.contextmanager
def db_connection(db_path: str) -> Generator[Tuple, None, None]:
    """
    SQLite connection context manager.

    Handles: connect, WAL pragma, yield (conn, cursor), close.
    Logs errors via kodi_helpers.debug_log.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        Tuple of (connection, cursor).
    """
    conn = None
    try:
        from sqlite3 import dbapi2 as sqlite

        conn = sqlite.connect(db_path, timeout=10)
        cursor = conn.cursor()
        with contextlib.suppress(Exception):
            cursor.execute("PRAGMA journal_mode=WAL")
        yield conn, cursor
    except Exception as exc:
        from resources.lib import kodi_helpers

        kodi_helpers.debug_log("SQLite error on %s: %s" % (db_path, str(exc)))
        raise
    finally:
        if conn is not None:
            conn.close()


def _epg_path(ctx: "AddonContext") -> str:
    """Return the path to the EPG SQLite database."""
    return os.path.join(ctx.user_data_dir, "epg.db")


def create_db(ctx: "AddonContext") -> bool:
    """
    Create EPG database with config table if it does not exist.

    Args:
        ctx: AddonContext with user_data_dir for DB path.

    Returns:
        True on success or if DB already exists, False on error.
    """
    db_path = _epg_path(ctx)
    if os.path.exists(db_path):
        return True

    create_config_sql = """CREATE TABLE config(
                         key                 TEXT NOT NULL PRIMARY KEY
                        ,value               TEXT
                        ,inserted_at         TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        ,updated_at          TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """
    seed_rows = [
        ("db version", "1.0"),
        ("epg last update", str(datetime.datetime.now())),
    ]

    try:
        with db_connection(db_path) as (conn, cursor):
            cursor.execute(create_config_sql)
            cursor.executemany("INSERT INTO config (key, value) VALUES (?,?)", seed_rows)
            conn.commit()
    except Exception:
        from resources.lib import kodi_helpers

        kodi_helpers.show_notification(kodi_helpers.get_localized(ctx.settings, 30009), "", 3000)
        return False
    return True


def create_epg_table(ctx: "AddonContext") -> bool:
    """
    Drop and recreate epg + genres tables. Ensures config table exists.

    Args:
        ctx: AddonContext with user_data_dir for DB path.

    Returns:
        True on success, False on error.
    """
    db_path = _epg_path(ctx)
    if not os.path.exists(db_path) and not create_db(ctx):
        return False

    drop_epg = "DROP TABLE IF EXISTS epg"
    create_epg = """CREATE TABLE epg(
                            ch_id               INTEGER NOT NULL
                           ,stop_timestamp      INTEGER
                           ,epg_json            TEXT
                        )
                    """

    drop_genres = "DROP TABLE IF EXISTS genres"
    create_genres = """CREATE TABLE genres(
                              id          INTEGER NOT NULL PRIMARY KEY
                             ,title       TEXT NOT NULL
                             ,censored    INTEGER
                        )
                    """

    create_config_if_missing = """CREATE TABLE IF NOT EXISTS config(
                         key                 TEXT NOT NULL PRIMARY KEY
                        ,value               TEXT
                        ,inserted_at         TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        ,updated_at          TIMESTAMP DEFAULT (datetime('now','localtime')) NOT NULL
                        )
                    """

    try:
        with db_connection(db_path) as (conn, cursor):
            conn.isolation_level = None
            cursor.execute(drop_epg)
            cursor.execute(create_epg)
            cursor.execute(drop_genres)
            cursor.execute(create_genres)
            cursor.execute(create_config_if_missing)
            cursor.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                ("db version", "1.0"),
            )
            cursor.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                ("epg last update", str(datetime.datetime.now())),
            )
            cursor.execute("VACUUM")
    except Exception:
        from resources.lib import kodi_helpers

        kodi_helpers.show_notification(kodi_helpers.get_localized(ctx.settings, 30010), "", 3000)
        return False
    return True


def reload(ctx: "AddonContext", hours_to_preload: int, background_job: bool) -> bool:
    """
    Full EPG reload from API into SQLite.

    Fetches streams, then loads one day of EPG data per channel.
    Updates genres and config timestamp on success.

    Args:
        ctx: AddonContext with adapter, api, settings, user_data_dir.
        hours_to_preload: Hours of future EPG to preload (used for config).
        background_job: If True, show notification instead of progress dialog.

    Returns:
        True on success, False on error.
    """
    from resources.lib import kodi_helpers

    # Clear current EPG data
    if not create_epg_table(ctx):
        return False

    db_path = _epg_path(ctx)
    dialog = None

    if background_job:
        kodi_helpers.show_notification(kodi_helpers.get_localized(ctx.settings, 30011), "", 2000)
    else:
        import xbmcgui

        dialog = xbmcgui.DialogProgress()
        dialog.create(
            "",
            kodi_helpers.get_localized(ctx.settings, 30012),
        )

    # Get all channels from API
    try:
        streams = ctx.api.get_streams()
    except Exception:
        streams = None

    if not streams:
        if not background_job:
            kodi_helpers.show_notification(kodi_helpers.get_localized(ctx.settings, 30013), "", 2000)
            if dialog is not None:
                dialog.close()
        else:
            kodi_helpers.debug_log("No streams data for EPG")
        return False

    days_to_load = 1
    total_channels = len(streams)

    try:
        with db_connection(db_path) as (conn, cursor):
            epg_list = []  # type: List[list]
            channel_progress = 0

            for stream in streams:
                channel_progress += 1
                alias = stream.get("alias", "")
                if not alias:
                    continue

                if not background_job and dialog is not None:
                    dialog.update(int(channel_progress * 100 / total_channels))
                    if dialog.iscanceled():
                        break

                for day_offset in range(0, days_to_load):
                    date_obj = datetime.datetime.now() + datetime.timedelta(days=day_offset)
                    date_str = date_obj.strftime("%Y-%m-%d")

                    try:
                        day_epg = ctx.adapter.get_day_epg(alias, date=date_str)
                    except Exception:
                        continue

                    if not day_epg:
                        continue

                    for prog in day_epg:
                        epg_block = {
                            "ch_id": alias,
                            "time": prog.get("t_time", ""),
                            "time_to": prog.get("t_time_to", ""),
                            "start_timestamp": prog.get("start_timestamp", ""),
                            "stop_timestamp": prog.get("stop_timestamp", ""),
                            "t_time": prog.get("t_time", ""),
                            "t_time_to": prog.get("t_time_to", ""),
                            "name": prog.get("name", ""),
                            "descr": prog.get("descr", ""),
                            "duration": prog.get("duration", 0),
                        }
                        stop_ts = prog.get("stop_timestamp", "0")
                        epg_list.append([alias, stop_ts, json.dumps(epg_block)])

                        if len(epg_list) > 300:
                            cursor.executemany(
                                "INSERT INTO epg (ch_id,stop_timestamp,epg_json) VALUES (?,?,?)",
                                epg_list,
                            )
                            epg_list = []

            if len(epg_list) > 0:
                cursor.executemany(
                    "INSERT INTO epg (ch_id,stop_timestamp,epg_json) VALUES (?,?,?)",
                    epg_list,
                )
                epg_list = []

            conn.commit()
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cid_sts ON epg (stop_timestamp, ch_id)")

            # Update genres from stream categories
            genres_list = []  # type: List[list]
            try:
                genres = ctx.adapter.get_genres()
                for group in genres:
                    genres_list.append([group["id"], group["title"], group.get("censored", "0")])
                if len(genres_list) > 0:
                    cursor.executemany(
                        "INSERT INTO genres (id, title, censored) VALUES (?,?,?)",
                        genres_list,
                    )
                    conn.commit()
            except Exception:
                pass

            # Update config timestamp
            cursor.execute(
                """INSERT INTO config (key, value) VALUES (?, ?)
                          ON CONFLICT(key) DO UPDATE SET
                             value = excluded.value
                            ,updated_at = datetime('now','localtime')
                       """,
                ("epg last update", str(datetime.datetime.now())),
            )
            conn.commit()

    except Exception as exc:
        kodi_helpers.debug_log("Failed to save EPG data to the local cache: %s" % str(exc))
        if not background_job:
            kodi_helpers.show_notification(
                kodi_helpers.get_localized(ctx.settings, 30014),
                str(exc),
                6000,
            )
        else:
            kodi_helpers.debug_log("Failed to save EPG to the local DB: %s" % str(exc))
        return False
    finally:
        if not background_job and dialog is not None:
            dialog.close()

    if background_job:
        kodi_helpers.show_notification(kodi_helpers.get_localized(ctx.settings, 30015), "", 2000)
        kodi_helpers.debug_log("EPG update completed")
    return True


def is_valid(ctx: "AddonContext", hours_to_preload: int) -> bool:
    """
    Check if local EPG cache has sufficient future data.

    Args:
        ctx: AddonContext with settings, user_data_dir.
        hours_to_preload: Hours of future data expected.

    Returns:
        True if cache is valid, False if stale or missing.
    """
    from resources.lib import kodi_helpers

    db_path = _epg_path(ctx)
    if not os.path.exists(db_path) and not create_db(ctx):
        return False

    run_sql = """  SELECT Max(next_epg_count) AS max_next_epg_count
                  FROM   ( SELECT ch_id
                                 ,count(*) AS next_epg_count
                           FROM   epg
                           WHERE  stop_timestamp > ?
                           GROUP  BY ch_id
                           LIMIT 5
                         ) t
             """
    do_cache_reload = False

    try:
        with db_connection(db_path) as (_conn, cursor):
            # Check if epg table exists
            cursor.execute(
                "SELECT count(name) FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "epg"),
            )
            if cursor.fetchone()[0] == 1:
                cursor.execute(run_sql, (int(time.time()),))
                db_row = cursor.fetchone()
                if db_row is None or db_row[0] is None:
                    do_cache_reload = True
                else:
                    next_epg_limit = int(ctx.settings.getSetting("next_epg_limit") or "3")
                    if db_row[0] < next_epg_limit + 1:
                        do_cache_reload = True
            else:
                do_cache_reload = True
    except Exception as exc:
        kodi_helpers.debug_log("Failed to check EPG local cache validity: %s" % str(exc))
        kodi_helpers.show_notification(kodi_helpers.get_localized(ctx.settings, 30016), str(exc), 4000)
        return False

    if do_cache_reload:
        kodi_helpers.debug_log("[is_valid] EPG cache is outdated, will use online EPG fallback")
        return False

    return True


def get_genres(ctx: "AddonContext") -> List[dict]:
    """
    Read genres from SQLite EPG cache.

    Args:
        ctx: AddonContext with user_data_dir.

    Returns:
        List of genre dicts with id, title, censored keys.
        Empty list on error or if DB is missing.
    """
    db_path = _epg_path(ctx)
    if not os.path.exists(db_path):
        return []

    result = []  # type: List[dict]
    try:
        with db_connection(db_path) as (_conn, cursor):
            cursor.execute("SELECT id, title, censored FROM genres")
            rows = cursor.fetchall()
            for row in rows:
                result.append({"id": row[0], "title": row[1], "censored": row[2]})
    except Exception:
        pass
    return result


def get_current_epg(ctx: "AddonContext", aliases: List[str]) -> Dict[str, dict]:
    """
    Query current EPG data for a list of channel aliases.

    For each alias, finds the first program whose stop_timestamp
    is greater than the current time.

    Args:
        ctx: AddonContext with user_data_dir.
        aliases: List of channel alias strings.

    Returns:
        Dict mapping alias to parsed EPG JSON dict.
        Missing aliases are omitted from the result.
    """
    db_path = _epg_path(ctx)
    if not os.path.exists(db_path):
        return {}

    if not aliases:
        return {}

    result = {}  # type: Dict[str, dict]
    now_ts = int(time.time())

    try:
        with db_connection(db_path) as (_conn, cursor):
            # Check if epg table exists
            cursor.execute(
                "SELECT count(name) FROM sqlite_master WHERE type = ? AND name = ?",
                ("table", "epg"),
            )
            if cursor.fetchone()[0] != 1:
                return {}

            for alias in aliases:
                cursor.execute(
                    "SELECT epg_json FROM epg WHERE ch_id = ? AND stop_timestamp > ? ORDER BY stop_timestamp ASC LIMIT 1",
                    (alias, now_ts),
                )
                row = cursor.fetchone()
                if row is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        result[alias] = json.loads(row[0])
    except Exception:
        pass
    return result


def epg_show(ctx: "AddonContext", params: dict) -> None:
    """Show full EPG for a specific channel in a text viewer dialog.

    Fetches 2 days of EPG via adapter and displays future events
    in a TextViewer window.

    Args:
        ctx: AddonContext instance.
        params: Router parameter dict (contains channel_id, channel_title).
    """
    import datetime
    import time as time_mod
    from urllib.parse import unquote as url_unquote

    import xbmc
    import xbmcgui

    from resources.lib import kodi_helpers

    channel_id = params.get("channel_id", "")
    channel_title_raw = params.get("channel_title", "")
    channel_title = url_unquote(channel_title_raw) if channel_title_raw else ""

    kodi_helpers.debug_log("[epg_show] channel_id=%s" % channel_id)

    # Open text viewer window
    xbmc.executebuiltin("ActivateWindow(%d)" % 10147)
    window = xbmcgui.Window(10147)

    now_ts = int(time_mod.time())
    channel_data = []

    # Fetch 2 days of EPG
    for day_offset in range(0, 2):
        date_obj = datetime.datetime.fromtimestamp(now_ts) + datetime.timedelta(days=day_offset)
        date_str = date_obj.strftime("%Y-%m-%d")
        try:
            day_epg = ctx.adapter.get_day_epg(channel_id, date=date_str)
            if day_epg:
                channel_data += day_epg
        except Exception:
            continue

    if not channel_data:
        kodi_helpers.show_notification("Cbilling", kodi_helpers.get_localized(ctx.settings, 30065), 2000)
        return

    # Sort by stop_timestamp
    with contextlib.suppress(ValueError, TypeError):
        channel_data = sorted(channel_data, key=lambda x: int(x.get("stop_timestamp", 0)))

    # Build text
    text = ""
    current_date = ""

    for epg_data in channel_data:
        stop_ts = int(epg_data.get("stop_timestamp", 0) or 0)
        if stop_ts < now_ts:
            continue

        start_ts = int(epg_data.get("start_timestamp", 0) or 0)
        if start_ts:
            epg_date = ctx.adapter._ts_to_local_str(start_ts, "%d-%m-%Y")
        else:
            continue

        if current_date != epg_date:
            current_date = epg_date
            if text:
                text += "\r\n\r\n"
            text += "[B]%s[/B]" % epg_date
            text += "\r\n%s" % ("~" * 40)

        t_time = epg_data.get("t_time", "")
        t_time_to = epg_data.get("t_time_to", "")
        name = epg_data.get("name", "")
        text += "\r\n%s - %s | %s " % (t_time, t_time_to, name)

    xbmc.sleep(100)
    window.getControl(1).setLabel(channel_title)
    window.getControl(5).setText(text)


def cron_epg_init(ctx: "AddonContext", params: dict) -> None:
    """
    Entry point for cron-triggered EPG rebuild (router dispatch handler).

    This is a stub. Full implementation will delegate to auth check
    and reload when the channels module is done.

    Args:
        ctx: AddonContext instance.
        params: Router parameter dict.
    """
    pass
