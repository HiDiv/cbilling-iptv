# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for auth.py — credential verification and server selection."""

import os
import sys
import time
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))

from resources.lib.api_client import CbillingApiError, CbillingAuthError, CbillingTimeoutError
from resources.lib.auth import check_credentials


class MockSettings:
    """Mock Kodi addon settings with getSetting/setSetting."""

    def __init__(self, settings_map=None):
        self._store = settings_map or {}

    def getSetting(self, key):  # noqa: N802
        return self._store.get(key, "")

    def setSetting(self, key, value):  # noqa: N802
        self._store[key] = value

    def getLocalizedString(self, string_id):  # noqa: N802
        return "String_%s" % string_id


class MockContext:
    """Mock AddonContext with settings and api."""

    def __init__(self, settings_map=None, api=None):
        self.settings = MockSettings(settings_map or {})
        self.api = api or MagicMock()


# ---------------------------------------------------------------------------
# Scenario 1: Successful auth (get_auth_info returns {"public_token": "xxx"})
# ---------------------------------------------------------------------------


class TestSuccessfulAuth:
    """Successful auth returns 'true' and updates auth_epoch."""

    def test_successful_auth_returns_true(self):
        """get_auth_info with public_token → returns 'true'."""
        api = MagicMock()
        api.get_auth_info.return_value = {"public_token": "abc123"}
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "true"
        api.get_auth_info.assert_called_once()

    def test_successful_auth_updates_auth_epoch(self):
        """Successful auth sets auth_epoch to current time."""
        api = MagicMock()
        api.get_auth_info.return_value = {"public_token": "abc123"}
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        check_credentials(ctx, cron_job_request=False)
        # auth_epoch should be updated to a recent timestamp
        epoch_val = int(ctx.settings.getSetting("auth_epoch"))
        assert abs(epoch_val - int(time.time())) < 5


# ---------------------------------------------------------------------------
# Scenario 2: Empty public key → returns localized error message (30017)
# ---------------------------------------------------------------------------


class TestEmptyPublicKey:
    """Missing or short public key returns localized error 30017."""

    def test_empty_user_login(self):
        """Empty user_login → returns String_30017."""
        ctx = MockContext(settings_map={"user_login": ""})
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "String_30017"

    def test_short_user_login(self):
        """Single-char user_login → returns String_30017."""
        ctx = MockContext(settings_map={"user_login": "x"})
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "String_30017"

    def test_missing_key_cron_job_logs_info(self):
        """cron_job_request=True still returns String_30017."""
        ctx = MockContext(settings_map={"user_login": ""})
        result = check_credentials(ctx, cron_job_request=True)
        assert result == "String_30017"


# ---------------------------------------------------------------------------
# Scenario 3: Re-auth within skip window → returns "true" without API call
# ---------------------------------------------------------------------------


class TestReauthSkipWindow:
    """Recent auth_epoch within reauth_seconds skips API call."""

    def test_within_skip_window_returns_true(self):
        """auth_epoch within reauth_seconds → returns 'true' without calling API."""
        api = MagicMock()
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": str(int(time.time()) - 10),  # 10 seconds ago
                "reauth_seconds": "120",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "true"
        api.get_auth_info.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 4: CbillingAuthError → returns error message with 30004
# ---------------------------------------------------------------------------


class TestCbillingAuthError:
    """CbillingAuthError raises → returns localized 30004 with message."""

    def test_auth_error_returns_30004_message(self):
        """CbillingAuthError → 'String_30004: Invalid public key'."""
        api = MagicMock()
        api.get_auth_info.side_effect = CbillingAuthError("Invalid public key")
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "String_30004: Invalid public key"

    def test_auth_error_resets_epoch(self):
        """CbillingAuthError resets auth_epoch to '2'."""
        api = MagicMock()
        api.get_auth_info.side_effect = CbillingAuthError("bad key")
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        check_credentials(ctx, cron_job_request=False)
        assert ctx.settings.getSetting("auth_epoch") == "2"


# ---------------------------------------------------------------------------
# Scenario 5: CbillingTimeoutError → returns "Server timeout"
# ---------------------------------------------------------------------------


class TestCbillingTimeoutError:
    """CbillingTimeoutError → returns 'Server timeout'."""

    def test_timeout_error_returns_server_timeout(self):
        """CbillingTimeoutError → 'Server timeout'."""
        api = MagicMock()
        api.get_auth_info.side_effect = CbillingTimeoutError("timed out")
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "Server timeout"


# ---------------------------------------------------------------------------
# Scenario 6: CbillingApiError → returns error message with 30003
# ---------------------------------------------------------------------------


class TestCbillingApiError:
    """CbillingApiError → returns localized 30003 with error details."""

    def test_api_error_returns_30003_message(self):
        """CbillingApiError → 'String_30003: Connection error'."""
        api = MagicMock()
        api.get_auth_info.side_effect = CbillingApiError("Connection error")
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "String_30003: Connection error"


# ---------------------------------------------------------------------------
# Scenario 7: Auth info without public_token → returns localized error (30003)
# ---------------------------------------------------------------------------


class TestMissingPublicToken:
    """auth_info without 'public_token' key → returns String_30003."""

    def test_missing_public_token_returns_30003(self):
        """get_auth_info returns dict without public_token → String_30003."""
        api = MagicMock()
        api.get_auth_info.return_value = {"server": "srv1.example.com"}
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "String_30003"

    def test_empty_auth_info_returns_30003(self):
        """get_auth_info returns empty dict → String_30003."""
        api = MagicMock()
        api.get_auth_info.return_value = {}
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "String_30003"


# ---------------------------------------------------------------------------
# Scenario 8: Auth sets server from auth_info when user_server is empty
# ---------------------------------------------------------------------------


class TestServerFromAuthInfo:
    """Successful auth updates user_server when it is empty."""

    def test_sets_server_when_user_server_empty(self):
        """user_server empty + auth_info has server → sets user_server."""
        api = MagicMock()
        api.get_auth_info.return_value = {
            "public_token": "abc123",
            "server": "cdn1.example.com",
        }
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
                "user_server": "",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "true"
        assert ctx.settings.getSetting("user_server") == "cdn1.example.com"

    def test_does_not_overwrite_existing_server(self):
        """user_server already set → does not overwrite."""
        api = MagicMock()
        api.get_auth_info.return_value = {
            "public_token": "abc123",
            "server": "cdn2.example.com",
        }
        ctx = MockContext(
            settings_map={
                "user_login": "valid_key",
                "auth_epoch": "4",
                "reauth_seconds": "120",
                "user_server": "existing-server.com",
            },
            api=api,
        )
        result = check_credentials(ctx, cron_job_request=False)
        assert result == "true"
        assert ctx.settings.getSetting("user_server") == "existing-server.com"
