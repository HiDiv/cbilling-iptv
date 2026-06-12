# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Authentication module — credential verification and stream server selection."""

import time

from resources.lib import kodi_helpers
from resources.lib.api_client import CbillingApiError, CbillingAuthError, CbillingTimeoutError


def check_credentials(ctx, cron_job_request):
    """Verify user credentials against the REST API.

    Skips re-authorization if a previous successful auth occurred within
    the configured reauth_seconds window.

    Args:
        ctx: AddonContext with settings and api_client.
        cron_job_request: If True, log missing-key errors via info_log.

    Returns:
        "true" on success, or an error message string on failure.
    """
    public_key = kodi_helpers.get_setting(ctx.settings, "user_login")
    if not public_key or len(public_key) < 2:
        if cron_job_request:
            kodi_helpers.info_log("Missing public key. Check addon settings")
        return kodi_helpers.get_localized(ctx.settings, 30017)

    # Skip re-authorize during X seconds after successful authorize
    last_auth_epoch = kodi_helpers.get_setting(ctx.settings, "auth_epoch", default="4", cast=int)
    reauth_seconds = kodi_helpers.get_setting(ctx.settings, "reauth_seconds", default="120", cast=int)
    if (int(time.time()) - last_auth_epoch) < reauth_seconds:
        return "true"

    try:
        auth_info = ctx.api.get_auth_info()
        if auth_info and "public_token" in auth_info:
            ctx.settings.setSetting("auth_epoch", str(int(time.time())))
            # Update server from auth info if available
            if auth_info.get("server"):
                current_server = str(ctx.settings.getSetting("user_server"))
                if not current_server or len(current_server) < 2:
                    ctx.settings.setSetting("user_server", auth_info["server"])
            return "true"
        return kodi_helpers.get_localized(ctx.settings, 30003)
    except CbillingAuthError:
        ctx.settings.setSetting("auth_epoch", "2")
        return "%s: %s" % (kodi_helpers.get_localized(ctx.settings, 30004), "Invalid public key")
    except CbillingTimeoutError:
        return "Server timeout"
    except CbillingApiError as e:
        return "%s: %s" % (kodi_helpers.get_localized(ctx.settings, 30003), str(e))


def get_stream_servers(ctx, params):
    """Show dialog to select from available stream servers.

    Args:
        ctx: AddonContext with settings and api_client.
        params: Router parameters dict.
    """
    pass
