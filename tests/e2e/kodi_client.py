# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Synchronous Python client for Kodi JSON-RPC over WebSocket.

This module provides the core KodiClient class that communicates with a
running Kodi instance via JSON-RPC 2.0 over WebSocket. It exposes synchronous
methods but uses asyncio internally for Python 3.8 compatibility.

Usage::

    client = KodiClient()
    client.connect()
    try:
        result = client.send_request("JSONRPC.Ping")
        print(result)  # "pong"
    finally:
        client.close()
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import websockets

from tests.e2e.exceptions import (
    KodiConnectionError,
    KodiRpcError,
    KodiTimeoutError,
)

logger = logging.getLogger(__name__)


class KodiClient:
    """Synchronous Python client for Kodi JSON-RPC over WebSocket.

    The client uses ``asyncio.get_event_loop().run_until_complete()`` internally
    to bridge async websockets calls into synchronous methods, ensuring
    compatibility with Python 3.8 and standard pytest (no pytest-asyncio needed).

    Args:
        ws_url: WebSocket URL for JSON-RPC (default: ws://localhost:9090/jsonrpc).
        http_url: HTTP URL for JSON-RPC healthcheck and screenshots
            (default: http://localhost:8080/jsonrpc).
        timeout: Default timeout in seconds for JSON-RPC requests (default: 30.0).
    """

    def __init__(
        self,
        ws_url: str = "ws://localhost:9090/jsonrpc",
        http_url: str = "http://localhost:8080/jsonrpc",
        timeout: float = 30.0,
    ) -> None:
        self.ws_url = ws_url
        self.http_url = http_url
        self.timeout = timeout

        self._ws = None  # type: Optional[Any]
        self._request_id = 0
        self._loop = None  # type: Optional[asyncio.AbstractEventLoop]

        # Parse host and port from ws_url for error reporting
        parsed = urlparse(ws_url)
        self._host = parsed.hostname or "localhost"
        self._port = parsed.port or 9090

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for synchronous execution."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
                if self._loop.is_closed():
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _next_id(self) -> int:
        """Generate the next auto-incrementing request ID."""
        self._request_id += 1
        return self._request_id

    def connect(self) -> None:
        """Establish WebSocket connection to Kodi JSON-RPC.

        Raises:
            KodiConnectionError: If the connection cannot be established.
        """
        loop = self._get_loop()
        try:
            self._ws = loop.run_until_complete(self._async_connect())
        except Exception as exc:
            raise KodiConnectionError(
                host=self._host,
                port=self._port,
                original_error=exc,
            ) from exc
        logger.info("Connected to Kodi at %s", self.ws_url)

    async def _async_connect(self) -> Any:
        """Async coroutine to establish WebSocket connection."""
        return await websockets.connect(self.ws_url, ping_interval=None, ping_timeout=None)

    def close(self) -> None:
        """Close the WebSocket connection and release resources."""
        if self._ws is not None:
            loop = self._get_loop()
            try:
                loop.run_until_complete(self._ws.close())
            except Exception:
                pass  # Best-effort close
            finally:
                self._ws = None
            logger.info("Disconnected from Kodi at %s", self.ws_url)

    def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a JSON-RPC request and return the result.

        Args:
            method: The JSON-RPC method name (e.g. "JSONRPC.Ping").
            params: Optional dictionary of method parameters.
            timeout: Request timeout in seconds. Uses the client default if None.

        Returns:
            The ``result`` field from the JSON-RPC response.

        Raises:
            KodiConnectionError: If the WebSocket is not connected or disconnects.
            KodiRpcError: If the response contains a JSON-RPC error.
            KodiTimeoutError: If no response is received within the timeout.
        """
        if self._ws is None:
            raise KodiConnectionError(
                host=self._host,
                port=self._port,
                original_error=RuntimeError("Not connected. Call connect() first."),
            )

        effective_timeout = timeout if timeout is not None else self.timeout
        loop = self._get_loop()

        try:
            return loop.run_until_complete(self._async_send_request(method, params, effective_timeout))
        except KodiRpcError:
            raise
        except KodiTimeoutError:
            raise
        except KodiConnectionError:
            raise
        except Exception as exc:
            raise KodiConnectionError(
                host=self._host,
                port=self._port,
                original_error=exc,
            ) from exc

    async def _async_send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]],
        timeout: float,
    ) -> Any:
        """Async coroutine to send request and await response."""
        request_id = self._next_id()

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }  # type: Dict[str, Any]
        if params is not None:
            payload["params"] = params

        request_json = json.dumps(payload)
        logger.debug("Sending: %s", request_json)

        try:
            await self._ws.send(request_json)
        except Exception as exc:
            raise KodiConnectionError(
                host=self._host,
                port=self._port,
                original_error=exc,
            ) from exc

        try:
            response_raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            raise KodiTimeoutError(
                condition=f"response to {method} (id={request_id})",
                elapsed=timeout,
            ) from None
        except Exception as exc:
            raise KodiConnectionError(
                host=self._host,
                port=self._port,
                original_error=exc,
            ) from exc

        logger.debug("Received: %s", response_raw)

        try:
            response = json.loads(response_raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise KodiRpcError(
                method=method,
                code=-1,
                message=f"Malformed JSON response: {response_raw!r}",
            ) from exc

        # Check for JSON-RPC error
        if "error" in response:
            error = response["error"]
            code = error.get("code", -1)
            message = error.get("message", "Unknown error")
            raise KodiRpcError(method=method, code=code, message=message)

        return response.get("result")

    # ------------------------------------------------------------------
    # Navigation methods
    # ------------------------------------------------------------------

    def input_up(self) -> None:
        """Send 'up' navigation action to Kodi."""
        self.send_request("Input.ExecuteAction", {"action": "up"})

    def input_down(self) -> None:
        """Send 'down' navigation action to Kodi."""
        self.send_request("Input.ExecuteAction", {"action": "down"})

    def input_left(self) -> None:
        """Send 'left' navigation action to Kodi."""
        self.send_request("Input.ExecuteAction", {"action": "left"})

    def input_right(self) -> None:
        """Send 'right' navigation action to Kodi."""
        self.send_request("Input.ExecuteAction", {"action": "right"})

    def input_select(self) -> None:
        """Send 'select' (enter) navigation action to Kodi."""
        self.send_request("Input.ExecuteAction", {"action": "select"})

    def input_back(self) -> None:
        """Send 'back' navigation action to Kodi."""
        self.send_request("Input.ExecuteAction", {"action": "back"})

    def input_home(self) -> None:
        """Navigate to the Kodi home screen."""
        self.send_request("Input.Home")

    # ------------------------------------------------------------------
    # State query methods
    # ------------------------------------------------------------------

    def get_current_window(self) -> Dict[str, Any]:
        """Retrieve the current window ID and label.

        Returns:
            Dictionary with keys ``id`` (int) and ``label`` (str).
        """
        result = self.send_request("GUI.GetProperties", {"properties": ["currentwindow"]})
        window = result.get("currentwindow", {})
        return {"id": window.get("id", 0), "label": window.get("label", "")}

    def get_container_items(self, path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve items from a directory listing.

        Args:
            path: Plugin or filesystem path to list. If not provided, uses
                the addon plugin URL ``plugin://plugin.video.cbilling.iptv/``.

        Returns:
            List of item dictionaries with at least ``label`` and ``file`` keys.
        """
        if path is None:
            path = "plugin://plugin.video.cbilling.iptv/"

        result = self.send_request(
            "Files.GetDirectory",
            {
                "directory": path,
                "media": "files",
                "properties": ["file"],
            },
        )
        if not isinstance(result, dict):
            return []
        files = result.get("files") or []
        items = []  # type: List[Dict[str, Any]]
        for f in files:
            items.append(
                {
                    "label": f.get("label", ""),
                    "file": f.get("file", ""),
                    "filetype": f.get("filetype", "file"),
                    "type": f.get("type", "unknown"),
                }
            )
        return items

    def get_player_state(self) -> Dict[str, Any]:
        """Retrieve the current player state.

        Returns:
            Dictionary with keys:
            - ``state``: one of ``"playing"``, ``"paused"``, ``"stopped"``
            - ``player_id``: active player ID or None
            - ``media_url``: URL of the currently playing media or None
            - ``speed``: playback speed (0 when paused/stopped)
        """
        players = self.send_request("Player.GetActivePlayers")

        if not players or not isinstance(players, list):
            return {
                "state": "stopped",
                "player_id": None,
                "media_url": None,
                "speed": 0,
            }

        player = players[0]
        if not isinstance(player, dict):
            return {
                "state": "stopped",
                "player_id": None,
                "media_url": None,
                "speed": 0,
            }
        player_id = player.get("playerid", 0)

        # Get playback speed
        props = self.send_request(
            "Player.GetProperties",
            {"playerid": player_id, "properties": ["speed"]},
        )
        speed = props.get("speed", 0) if isinstance(props, dict) else 0

        # Get currently playing item
        item_result = self.send_request(
            "Player.GetItem",
            {"playerid": player_id, "properties": ["file"]},
        )
        item = item_result.get("item", {}) if isinstance(item_result, dict) else {}
        media_url = item.get("file", None) if isinstance(item, dict) else None

        state = "playing" if speed > 0 else "paused"

        return {
            "state": state,
            "player_id": player_id,
            "media_url": media_url,
            "speed": speed,
        }

    # ------------------------------------------------------------------
    # Wait methods
    # ------------------------------------------------------------------

    def wait_for_window(self, window_id: int, timeout: Optional[float] = None) -> None:
        """Wait until the current window matches the expected window ID.

        Polls ``get_current_window()`` every 500ms until the window ID matches
        or the timeout expires.

        Args:
            window_id: The expected Kodi window ID to wait for.
            timeout: Maximum wait time in seconds. Uses the client default if None.

        Raises:
            KodiTimeoutError: If the expected window does not appear within timeout.
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        deadline = time.monotonic() + effective_timeout

        while True:
            current = self.get_current_window()
            if current.get("id") == window_id:
                return

            if time.monotonic() >= deadline:
                raise KodiTimeoutError(
                    condition=f"window id={window_id} (current: id={current.get('id')})",
                    elapsed=effective_timeout,
                )
            time.sleep(0.5)

    def wait_for_content(
        self,
        label_substring: Optional[str] = None,
        min_items: int = 1,
        timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Wait until container items meet the expected criteria.

        Polls ``get_container_items()`` every 500ms until at least ``min_items``
        items are found. If ``label_substring`` is provided, only items whose
        label contains the substring (case-insensitive) are counted.

        Args:
            label_substring: Optional substring to filter items by label.
                If None, all items are counted.
            min_items: Minimum number of matching items required (default: 1).
            timeout: Maximum wait time in seconds. Uses the client default if None.

        Returns:
            The list of matching items when the condition is met.

        Raises:
            KodiTimeoutError: If the content condition is not met within timeout.
        """
        effective_timeout = timeout if timeout is not None else self.timeout
        deadline = time.monotonic() + effective_timeout

        while True:
            try:
                items = self.get_container_items()
            except (KodiRpcError, KodiConnectionError):
                # Directory may not be ready yet; keep polling
                items = []

            if label_substring is not None:
                needle = label_substring.lower()
                matching = [i for i in items if needle in i.get("label", "").lower()]
            else:
                matching = items

            if len(matching) >= min_items:
                return matching

            if time.monotonic() >= deadline:
                condition = f"min_items={min_items}"
                if label_substring is not None:
                    condition += f" matching '{label_substring}'"
                condition += f" (found: {len(matching)})"
                raise KodiTimeoutError(
                    condition=condition,
                    elapsed=effective_timeout,
                )
            time.sleep(0.5)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def take_screenshot(self, filepath: str) -> None:
        """Capture a screenshot of the current Kodi display and save to file.

        Triggers a screenshot via the Kodi JSON-RPC HTTP interface and saves
        the resulting image to the specified local path.

        Args:
            filepath: Local filesystem path where the screenshot will be saved.

        Raises:
            KodiConnectionError: If the screenshot cannot be captured.
        """
        # Use the HTTP JSON-RPC endpoint to trigger a screenshot capture
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "XBMC.TakeScreenshot",
            "params": {"screenshoturl": filepath},
        }

        try:
            response = requests.post(
                self.http_url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            raise KodiConnectionError(
                host=self._host,
                port=self._port,
                original_error=exc,
            ) from exc

        logger.info("Screenshot saved to %s", filepath)
