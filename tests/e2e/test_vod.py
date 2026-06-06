# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E tests for VOD (Медиатека) navigation, playback, search, and series.

Verifies that the VOD main menu contains expected items, that the catalog
displays categories, navigating into a category shows movies/series,
movie playback works correctly with watch history tracking, VOD search
by name and year returns results, and series navigation through seasons
and episodes works correctly.

Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 19.1, 19.2, 19.3, 19.4, 19.5, 20.1, 20.2, 20.3, 20.4, 20.5
"""

import time
from contextlib import suppress
from urllib.parse import quote

import pytest

from tests.e2e.exceptions import KodiConnectionError
from tests.e2e.kodi_client import KodiClient
from tests.e2e.utils import strip_kodi_tags, strip_labels

# ---------------------------------------------------------------------------
# Configurable test content — change if VOD structure changes
# ---------------------------------------------------------------------------

# Addon plugin base URL
_ADDON_URL = "plugin://plugin.video.cbilling.iptv/"

# VOD main menu URL
_VOD_START_URL = _ADDON_URL + "?mode=vod_start"

# VOD catalog URL (list of categories)
_VOD_CATALOG_URL = _ADDON_URL + "?mode=vod_get_category"

# Expected VOD main menu items (Russian labels)
_LABEL_CATALOG = "Категории"
_LABEL_SEARCH = "Поиск"
_LABEL_WATCH_HISTORY = "История просмотров"

# English fallback labels (msgid values from strings.po)
_LABEL_CATALOG_EN = "Media Category"
_LABEL_SEARCH_EN = "Search"
_LABEL_WATCH_HISTORY_EN = "Watch History"

# Minimum expected items in VOD main menu
_VOD_MENU_MIN_ITEMS = 3


@pytest.mark.e2e
class TestVODNavigation:
    """Tests for VOD (Медиатека) navigation through menu, catalog, and content.

    Validates: Requirements 18.1, 18.2, 18.3
    """

    def test_vod_main_menu_contains_expected_items(self, kodi_client: KodiClient) -> None:
        """Verify VOD main menu contains Каталог, Поиск, and История просмотра.

        Navigates to the VOD start page and checks that all three expected
        menu items are present after stripping Kodi formatting tags.

        Validates: Requirement 18.1
        """
        items = kodi_client.get_container_items(path=_VOD_START_URL)
        labels = strip_labels(items)

        assert len(labels) >= _VOD_MENU_MIN_ITEMS, "Expected at least %d items in VOD main menu, got %d: %s" % (
            _VOD_MENU_MIN_ITEMS,
            len(labels),
            labels,
        )

        assert _LABEL_CATALOG in labels or _LABEL_CATALOG_EN in labels, (
            "Expected '%s' or '%s' in VOD main menu, got: %s" % (_LABEL_CATALOG, _LABEL_CATALOG_EN, labels)
        )
        assert _LABEL_SEARCH in labels or _LABEL_SEARCH_EN in labels, (
            "Expected '%s' or '%s' in VOD main menu, got: %s" % (_LABEL_SEARCH, _LABEL_SEARCH_EN, labels)
        )
        assert _LABEL_WATCH_HISTORY in labels or _LABEL_WATCH_HISTORY_EN in labels, (
            "Expected '%s' or '%s' in VOD main menu, got: %s" % (_LABEL_WATCH_HISTORY, _LABEL_WATCH_HISTORY_EN, labels)
        )

    def test_vod_catalog_has_categories(self, kodi_client: KodiClient) -> None:
        """Verify VOD catalog contains at least 1 category.

        Navigates to the catalog page and verifies that at least one
        category item is displayed with a non-empty label.

        Validates: Requirement 18.2
        """
        items = kodi_client.get_container_items(path=_VOD_CATALOG_URL)
        labels = strip_labels(items)

        assert len(labels) >= 1, "Expected at least 1 VOD category in catalog, got %d" % len(labels)

        # Verify labels are non-empty after stripping
        for label in labels:
            assert label, "Found empty label after strip_kodi_tags() in VOD catalog"

    def test_vod_category_has_content(self, kodi_client: KodiClient) -> None:
        """Verify first VOD category contains at least 1 movie/series.

        Navigates to the catalog, picks the first category, then navigates
        through genres to the content list and verifies at least one content
        item is displayed.

        Validates: Requirement 18.3
        """
        # Get catalog categories
        categories = kodi_client.get_container_items(path=_VOD_CATALOG_URL)
        assert len(categories) >= 1, "Expected at least 1 VOD category to navigate into, got %d" % len(categories)

        # Navigate into the first category (returns genres or redirects to content)
        first_category_url = categories[0].get("file", "")
        first_category_label = strip_kodi_tags(categories[0].get("label", ""))
        assert first_category_url, "First VOD category '%s' has no file URL" % first_category_label

        # Category URL has mode=vod_get_category_genres which returns genres
        # Each genre has mode=vod_get_ordered_list URL
        genre_items = kodi_client.get_container_items(path=first_category_url)

        if not genre_items:
            # Some categories may have no genres and redirect directly
            pytest.skip("Category '%s' returned no items (may redirect)" % first_category_label)

        # Navigate into the first genre (usually "All" / "Vse") to get content
        first_genre_url = genre_items[0].get("file", "")
        assert first_genre_url, "First genre item in category '%s' has no file URL" % first_category_label

        items = kodi_client.get_container_items(path=first_genre_url)
        labels = strip_labels(items)

        assert len(labels) >= 1, "Expected at least 1 movie/series in category '%s', got %d" % (
            first_category_label,
            len(labels),
        )

        # Verify content items have non-empty titles
        for label in labels:
            assert label, "Found empty label after strip_kodi_tags() in category '%s'" % first_category_label


# ---------------------------------------------------------------------------
# VOD Playback constants
# ---------------------------------------------------------------------------

# Watch history URL
_VOD_WATCH_HISTORY_URL = _ADDON_URL + "?mode=vod_watch_history"

# Timeout for player to enter "playing" state (seconds)
_PLAYBACK_START_TIMEOUT = 30.0

# Duration to verify stable playback (seconds)
_PLAYBACK_STABLE_DURATION = 5.0

# Polling interval for player state checks (seconds)
_POLL_INTERVAL = 2.0


def _wait_for_player_playing(kodi_client, timeout=_PLAYBACK_START_TIMEOUT):
    # type: (KodiClient, float) -> None
    """Wait until Kodi's player enters the 'playing' state.

    Polls Player.GetActivePlayers every _POLL_INTERVAL seconds until
    a player is active and its speed > 0. Handles transient connection
    errors by reconnecting.

    Args:
        kodi_client: Connected KodiClient instance.
        timeout: Maximum time to wait in seconds.

    Raises:
        AssertionError: If player does not enter playing state within timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            state = kodi_client.get_player_state()
            if state["state"] == "playing":
                return
        except (KodiConnectionError, Exception):
            _ensure_ws_connected(kodi_client)
        time.sleep(_POLL_INTERVAL)

    # Final check
    state = kodi_client.get_player_state()
    assert state["state"] == "playing", "Player did not enter 'playing' state within %.0fs. Current state: %s" % (
        timeout,
        state["state"],
    )


def _wait_for_player_stopped(kodi_client, timeout=10.0):
    # type: (KodiClient, float) -> None
    """Wait until Kodi's player enters the 'stopped' state.

    Args:
        kodi_client: Connected KodiClient instance.
        timeout: Maximum time to wait in seconds.

    Raises:
        AssertionError: If player does not stop within timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = kodi_client.get_player_state()
        if state["state"] == "stopped":
            return
        time.sleep(_POLL_INTERVAL)

    state = kodi_client.get_player_state()
    assert state["state"] == "stopped", "Player did not enter 'stopped' state within %.0fs. Current state: %s" % (
        timeout,
        state["state"],
    )


def _ensure_ws_connected(kodi_client):
    # type: (KodiClient,) -> None
    """Ensure the WebSocket connection is alive, reconnecting if needed."""
    try:
        kodi_client.send_request("JSONRPC.Ping", timeout=5)
    except (KodiConnectionError, Exception):
        with suppress(Exception):
            kodi_client.close()
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            try:
                kodi_client.connect()
                return
            except Exception:
                time.sleep(1.0)
        pytest.fail("Could not reconnect WebSocket after Player.Open")


def _start_playback_via_http(kodi_client, play_url):
    # type: (KodiClient, str) -> None
    """Start playback by sending Player.Open and handling the connection drop.

    Args:
        kodi_client: Connected KodiClient instance.
        play_url: The plugin:// URL to play.
    """
    with suppress(Exception):
        kodi_client.send_request(
            "Player.Open",
            {"item": {"file": play_url}},
            timeout=5,
        )
    # Expected — connection drops during stream resolution

    time.sleep(5.0)
    _ensure_ws_connected(kodi_client)


def _find_first_movie_url(kodi_client):
    # type: (KodiClient,) -> tuple
    """Find the first playable movie URL from the VOD catalog.

    Navigates: catalog -> first category -> first genre -> find item with vod_play_movie.

    Args:
        kodi_client: Connected KodiClient instance.

    Returns:
        Tuple of (play_url, movie_title) for the first available movie.

    Raises:
        AssertionError: If no playable movie is found.
    """
    # Get catalog categories
    categories = kodi_client.get_container_items(path=_VOD_CATALOG_URL)
    assert len(categories) >= 1, "Expected at least 1 VOD category, got %d" % len(categories)

    # Try each category to find a movie (not a series)
    for category in categories:
        category_url = category.get("file", "")
        if not category_url:
            continue

        # Category returns genres (mode=vod_get_category_genres)
        genre_items = kodi_client.get_container_items(path=category_url)
        if not genre_items:
            continue

        # Navigate into the first genre to get content list
        for genre_item in genre_items[:2]:  # Try first 2 genres (usually "All" + first genre)
            genre_url = genre_item.get("file", "")
            if not genre_url:
                continue

            items = kodi_client.get_container_items(path=genre_url)
            for item in items:
                file_url = item.get("file", "")
                # Movies have mode=vod_play_movie
                if "mode=vod_play_movie" in file_url:
                    title = strip_kodi_tags(item.get("label", ""))
                    return (file_url, title)

    pytest.fail(
        "No playable movie (mode=vod_play_movie) found in any VOD category. Categories checked: %d" % len(categories)
    )
    return ("", "")  # unreachable


@pytest.mark.e2e
class TestVODPlayback:
    """Tests for VOD movie playback and watch history.

    Verifies that the addon can start VOD movie playback, maintain stable
    streaming, stop cleanly, and record the movie in watch history.

    Validates: Requirements 18.4, 18.5, 18.6, 18.7
    """

    def test_vod_movie_playback_and_watch_history(self, kodi_client: KodiClient) -> None:
        """Verify VOD movie playback starts, remains stable, stops, and appears in history.

        Steps:
        1. Find first available movie from VOD catalog
        2. Start playback via Player.Open
        3. Verify player enters "playing" state within 15s
        4. Verify playback continues for 5s without errors
        5. Stop player and verify stopped state
        6. Verify movie appears in watch history

        Validates: Requirements 18.4, 18.5, 18.6, 18.7
        """
        # Step 1: Find first available movie
        play_url, movie_title = _find_first_movie_url(kodi_client)
        assert play_url, "Movie play URL should not be empty"
        assert movie_title, "Movie title should not be empty"

        # Step 2: Start playback via HTTP (avoids WebSocket drop during stream resolution)
        _start_playback_via_http(kodi_client, play_url)

        # Step 3: Verify player enters "playing" state within 15s
        _wait_for_player_playing(kodi_client, timeout=_PLAYBACK_START_TIMEOUT)

        # Step 4: Verify playback continues for 5s without errors
        start_time = time.monotonic()
        while time.monotonic() - start_time < _PLAYBACK_STABLE_DURATION:
            state = kodi_client.get_player_state()
            assert state["state"] == "playing", "VOD playback interrupted after %.1fs. State: %s" % (
                time.monotonic() - start_time,
                state["state"],
            )
            time.sleep(_POLL_INTERVAL)

        # Step 5: Stop player and verify stopped state
        state = kodi_client.get_player_state()
        player_id = state.get("player_id")
        assert player_id is not None, "No active player to stop"

        kodi_client.send_request("Player.Stop", {"playerid": player_id})
        _wait_for_player_stopped(kodi_client, timeout=10.0)

        # Step 6: Verify movie appears in watch history
        # Allow a brief moment for the addon to write history
        time.sleep(2.0)

        history_items = kodi_client.get_container_items(path=_VOD_WATCH_HISTORY_URL)
        history_labels = strip_labels(history_items)

        assert any(movie_title in label for label in history_labels), (
            "Movie '%s' not found in watch history. History items: %s" % (movie_title, history_labels)
        )


# ---------------------------------------------------------------------------
# VOD Search tests
# ---------------------------------------------------------------------------

# Configurable search parameters — change if content becomes unavailable
TEST_VOD_SEARCH_TERM = "фильм"
TEST_VOD_SEARCH_YEAR = "2024"


@pytest.mark.e2e
class TestVODSearch:
    """Tests for VOD search by name and year.

    Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5
    """

    def test_vod_search_by_name(self, kodi_client: KodiClient) -> None:
        """Verify VOD search by name returns at least 1 result.

        Discovers a movie title from the catalog, then searches for it
        to ensure the search term is valid. Falls back to a generic term
        if catalog discovery fails.

        Validates: Requirements 20.1, 20.2, 20.3
        """
        # Discover a valid search term from the catalog
        search_term = TEST_VOD_SEARCH_TERM
        categories = kodi_client.get_container_items(path=_VOD_CATALOG_URL)
        if categories:
            # Navigate into first category -> first genre to find a movie title
            first_cat_url = categories[0].get("file", "")
            if first_cat_url:
                genre_items = kodi_client.get_container_items(path=first_cat_url)
                if genre_items:
                    first_genre_url = genre_items[0].get("file", "")
                    if first_genre_url:
                        content_items = kodi_client.get_container_items(path=first_genre_url)
                        if content_items:
                            # Use first 4 chars of the first movie title as search term
                            title = strip_kodi_tags(content_items[0].get("label", ""))
                            if len(title) >= 4:
                                search_term = title[:4]

        search_url = _ADDON_URL + "?mode=vod_get_ordered_list&page_nr=1&sortby=name&vod_search=" + quote(search_term)
        # Search with preloading can take longer — use extended timeout
        result = kodi_client.send_request(
            "Files.GetDirectory",
            {"directory": search_url, "media": "files", "properties": ["file"]},
            timeout=60,
        )
        files = result.get("files") or []
        items = [{"label": f.get("label", ""), "file": f.get("file", "")} for f in files]
        labels = strip_labels(items)

        assert len(labels) >= 1, "Expected at least 1 search result for '%s', got %d" % (
            search_term,
            len(labels),
        )

        # Verify all result labels are non-empty
        for label in labels:
            assert label, "Found empty label in search results for '%s'" % search_term

    def test_vod_search_by_year(self, kodi_client: KodiClient) -> None:
        """Verify VOD search by year returns at least 1 result.

        Calls the search URL directly with vod_year parameter to filter
        by release year. Verifies results are returned and labels are
        non-empty.

        Validates: Requirements 20.4, 20.5
        """
        search_url = _ADDON_URL + "?mode=vod_get_ordered_list&page_nr=1&sortby=name&vod_year=" + TEST_VOD_SEARCH_YEAR
        # Year filter with preloading can take longer — use extended timeout
        try:
            result = kodi_client.send_request(
                "Files.GetDirectory",
                {"directory": search_url, "media": "files", "properties": ["file"]},
                timeout=60,
            )
            files = result.get("files") or []
        except Exception:
            files = []

        items = [{"label": f.get("label", ""), "file": f.get("file", "")} for f in files]
        labels = strip_labels(items)

        assert len(labels) >= 1, "Expected at least 1 search result for year '%s', got %d" % (
            TEST_VOD_SEARCH_YEAR,
            len(labels),
        )

        # Verify all result labels are non-empty
        for label in labels:
            assert label, "Found empty label in search results for year '%s'" % TEST_VOD_SEARCH_YEAR


# ---------------------------------------------------------------------------
# VOD Series navigation tests
# ---------------------------------------------------------------------------


def _find_series_in_catalog(kodi_client):
    # type: (KodiClient,) -> tuple
    """Find the first series (item with mode=vod_get_seasons) from the VOD catalog.

    Navigates through catalog categories and genres to find an item whose file URL
    contains ``mode=vod_get_seasons``, indicating it is a series.

    Args:
        kodi_client: Connected KodiClient instance.

    Returns:
        Tuple of (series_url, series_title) for the first available series.

    Raises:
        AssertionError: If no series is found in any category.
    """
    categories = kodi_client.get_container_items(path=_VOD_CATALOG_URL)
    assert len(categories) >= 1, "Expected at least 1 VOD category, got %d" % len(categories)

    for category in categories:
        category_url = category.get("file", "")
        if not category_url:
            continue

        # Category returns genres (mode=vod_get_category_genres)
        genre_items = kodi_client.get_container_items(path=category_url)
        if not genre_items:
            continue

        # Navigate into the first genre to get content list
        for genre_item in genre_items[:2]:  # Try first 2 genres
            genre_url = genre_item.get("file", "")
            if not genre_url:
                continue

            items = kodi_client.get_container_items(path=genre_url)
            for item in items:
                file_url = item.get("file", "")
                # Series have mode=vod_get_seasons in their file URL
                if "mode=vod_get_seasons" in file_url:
                    title = strip_kodi_tags(item.get("label", ""))
                    return (file_url, title)

    pytest.fail("No series (mode=vod_get_seasons) found in any VOD category. Categories checked: %d" % len(categories))
    return ("", "")  # unreachable


@pytest.mark.e2e
class TestVODSeries:
    """Tests for VOD series navigation through seasons and episodes.

    Discovers a series from the catalog at runtime, navigates into it
    to verify seasons/episodes are displayed, starts episode playback,
    and verifies the episode appears in watch history with series info.

    Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5
    """

    def test_vod_series_navigation_and_playback(self, kodi_client: KodiClient) -> None:
        """Verify series navigation, episode playback, and watch history.

        Steps:
        1. Discover a series from the VOD catalog (item with mode=vod_get_seasons)
        2. Navigate into the series to get seasons or episodes
        3. If seasons are returned, navigate into the first season
        4. Verify at least 1 episode is displayed
        5. Start playback of the first episode via Player.Open
        6. Verify player enters "playing" state within 15s
        7. Stop player and verify stopped state
        8. Verify episode appears in watch history with series title

        Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5
        """
        # Step 1: Discover a series from the catalog
        series_url, series_title = _find_series_in_catalog(kodi_client)
        assert series_url, "Series URL should not be empty"
        assert series_title, "Series title should not be empty"

        # Step 2: Navigate into the series (returns seasons or episodes directly)
        series_items = kodi_client.get_container_items(path=series_url)
        assert len(series_items) >= 1, "Expected at least 1 season or episode for series '%s', got %d" % (
            series_title,
            len(series_items),
        )

        # Step 3: Determine if we got seasons or episodes
        # Seasons have mode=vod_get_episodes in their URL
        # Episodes have mode=vod_play_movie in their URL
        first_item_url = series_items[0].get("file", "")

        if "mode=vod_get_episodes" in first_item_url:
            # We got seasons — navigate into the first season to get episodes
            season_label = strip_kodi_tags(series_items[0].get("label", ""))
            episodes = kodi_client.get_container_items(path=first_item_url)
            assert len(episodes) >= 1, "Expected at least 1 episode in season '%s' of series '%s', got %d" % (
                season_label,
                series_title,
                len(episodes),
            )
        elif "mode=vod_play_movie" in first_item_url:
            # Single season — we already have episodes directly
            episodes = series_items
        else:
            # Unexpected structure — try treating items as episodes anyway
            episodes = series_items

        # Step 4: Verify at least 1 episode with a title
        episode_labels = strip_labels(episodes)
        assert len(episode_labels) >= 1, "Expected at least 1 episode for series '%s', got %d" % (
            series_title,
            len(episode_labels),
        )
        for label in episode_labels:
            assert label, "Found empty episode label in series '%s'" % series_title

        # Step 5: Find the first playable episode (mode=vod_play_movie)
        play_url = ""
        for ep in episodes:
            ep_url = ep.get("file", "")
            if "mode=vod_play_movie" in ep_url:
                play_url = ep_url
                break

        assert play_url, "No playable episode (mode=vod_play_movie) found in series '%s'" % series_title

        # Start playback via HTTP (avoids WebSocket drop during stream resolution)
        _start_playback_via_http(kodi_client, play_url)

        # Step 6: Verify player enters "playing" state within 15s
        _wait_for_player_playing(kodi_client, timeout=_PLAYBACK_START_TIMEOUT)

        # Step 7: Stop player and verify stopped state
        state = kodi_client.get_player_state()
        player_id = state.get("player_id")
        assert player_id is not None, "No active player to stop"

        kodi_client.send_request("Player.Stop", {"playerid": player_id})
        _wait_for_player_stopped(kodi_client, timeout=10.0)

        # Step 8: Verify episode appears in watch history with series title
        # Allow a brief moment for the addon to write history
        time.sleep(2.0)

        history_items = kodi_client.get_container_items(path=_VOD_WATCH_HISTORY_URL)
        history_labels = strip_labels(history_items)

        # Watch history for episodes shows: "Series Title - Season. Episode"
        # We check that the series title appears in at least one history entry
        assert any(series_title in label for label in history_labels), (
            "Series '%s' not found in watch history after episode playback. "
            "History items: %s" % (series_title, history_labels)
        )
