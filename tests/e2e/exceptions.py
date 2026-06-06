# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Exception hierarchy for the Kodi E2E test client.

Exception tree::

    KodiError (base)
    ├── KodiConnectionError   — WebSocket connection failure
    ├── KodiRpcError          — JSON-RPC error response from Kodi
    └── KodiTimeoutError      — Operation timed out waiting for expected state
"""

from typing import Optional


class KodiError(Exception):
    """Base exception for all Kodi client errors."""


class KodiConnectionError(KodiError):
    """WebSocket connection failure.

    Attributes:
        host: Target host that was unreachable.
        port: Target port that was unreachable.
        original_error: The underlying exception that caused the failure.
    """

    def __init__(
        self,
        host: str,
        port: int,
        original_error: Optional[Exception] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.original_error = original_error
        msg = "Failed to connect to Kodi at %s:%d" % (host, port)
        if original_error is not None:
            msg += " (%s)" % original_error
        super().__init__(msg)


class KodiRpcError(KodiError):
    """JSON-RPC error response from Kodi.

    Attributes:
        method: The JSON-RPC method that returned an error.
        code: The error code from the JSON-RPC response.
        message: The error message from the JSON-RPC response.
    """

    def __init__(self, method: str, code: int, message: str) -> None:
        self.method = method
        self.code = code
        self.message = message
        msg = "%s: [%d] %s" % (method, code, message)
        super().__init__(msg)


class KodiTimeoutError(KodiError):
    """Operation timed out waiting for expected state.

    Attributes:
        condition: Description of the condition that was being waited for.
        elapsed: Duration in seconds that elapsed before timeout.
    """

    def __init__(self, condition: str, elapsed: float) -> None:
        self.condition = condition
        self.elapsed = elapsed
        msg = "Timed out after %.1fs waiting for: %s" % (elapsed, condition)
        super().__init__(msg)
