# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E test fixtures and pytest hooks.

Provides session-scoped fixtures for Docker container lifecycle, Kodi client
management, ZIP-based addon installation, and automatic artifact collection
on test failure. Also registers the ``skip_kodi_version`` marker for
version-specific test skipping.
"""

import logging
import os
import subprocess
import time
from typing import Dict, Generator, Optional

import pytest
import requests

from tests.e2e.addon_installer import (
    ADDON_ID,
    enable_addon,
    find_addon_zip,
    install_addon_from_zip,
    provision_settings,
    verify_addon_enabled,
)
from tests.e2e.artifacts import ArtifactCollector
from tests.e2e.config import E2EConfig, load_config
from tests.e2e.kodi_client import KodiClient

logger = logging.getLogger(__name__)

# Container name pattern used by docker-compose
_CONTAINER_NAME_TEMPLATE = "kodi-e2e-%s"


def _configure_kodi_settings(http_url: str) -> bool:
    """Configure Kodi settings via JSON-RPC after startup.

    Sets Russian language, enables unknown sources, and configures timezone.
    These settings would normally come from guisettings.xml but since the
    container entrypoint cannot handle a mounted guisettings.xml (sed -i fails
    on bind mounts), we configure them programmatically.

    Args:
        http_url: Kodi HTTP JSON-RPC endpoint URL.

    Returns:
        True if all settings were applied, False otherwise.
    """
    settings_to_apply = [
        ("locale.language", "resource.language.ru_ru"),
    ]

    for setting_id, value in settings_to_apply:
        payload = {
            "jsonrpc": "2.0",
            "method": "Settings.SetSettingValue",
            "params": {"setting": setting_id, "value": value},
            "id": 1,
        }
        try:
            resp = requests.post(http_url, json=payload, timeout=10)
            data = resp.json()
            if data.get("result") is not True:
                logger.error("Failed to set %s=%s: %s", setting_id, value, data)
                return False
            logger.info("Kodi setting %s = %s applied", setting_id, value)
        except Exception as exc:
            logger.error("Error setting %s: %s", setting_id, exc)
            return False

    # Give Kodi time to apply language change (it reloads UI)
    time.sleep(5)
    return True


def _check_required_env_vars(config: E2EConfig) -> Optional[str]:
    """Check that required environment variables are set.

    Returns:
        None if all required vars are present, or a skip message string.
    """
    missing = []  # type: list
    if not config.cbilling_api_url:
        missing.append("CBILLING_API_URL")
    if not config.cbilling_public_key:
        missing.append("CBILLING_PUBLIC_KEY")

    if missing:
        return "Required environment variables not set: %s" % ", ".join(missing)
    return None


def _wait_for_healthcheck(http_url: str, timeout: float = 60.0, interval: float = 2.0) -> bool:
    """Poll Kodi JSON-RPC healthcheck until it responds or timeout expires.

    Args:
        http_url: Kodi HTTP JSON-RPC endpoint URL.
        timeout: Maximum wait time in seconds.
        interval: Polling interval in seconds.

    Returns:
        True if healthcheck passed, False if timeout expired.
    """
    deadline = time.monotonic() + timeout
    payload = {"jsonrpc": "2.0", "method": "JSONRPC.Ping", "id": 1}

    while time.monotonic() < deadline:
        try:
            resp = requests.post(http_url, json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("result") == "pong":
                    return True
        except (requests.ConnectionError, requests.Timeout, ValueError):
            pass
        time.sleep(interval)

    return False


def _start_container(config: E2EConfig) -> bool:
    """Start the Kodi Docker container via docker-compose.

    Args:
        config: E2E configuration with kodi_version.

    Returns:
        True if container started successfully, False otherwise.
    """
    compose_dir = os.path.dirname(os.path.abspath(__file__))
    profile = config.kodi_version

    cmd = [
        "docker",
        "compose",
        "--profile",
        profile,
        "up",
        "-d",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=compose_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error("docker compose up failed: %s", result.stderr.strip())
            return False
        return True
    except Exception as exc:
        logger.error("Failed to start container: %s", exc)
        return False


def _get_kodi_log_tail(container_name: str, lines: int = 200) -> str:
    """Retrieve the last N lines of kodi.log from the container.

    Args:
        container_name: Name of the running Docker container.
        lines: Number of lines to retrieve from the end of the log.

    Returns:
        Log tail as a string, or an error message if retrieval fails.
    """
    cmd = [
        "docker",
        "exec",
        container_name,
        "tail",
        "-n",
        str(lines),
        "/root/.kodi/temp/kodi.log",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
        return "(failed to read kodi.log: %s)" % result.stderr.strip()
    except Exception as exc:
        return "(failed to read kodi.log: %s)" % exc


def _stop_container(config: E2EConfig) -> None:
    """Stop and remove the Kodi Docker container.

    Args:
        config: E2E configuration with kodi_version.
    """
    compose_dir = os.path.dirname(os.path.abspath(__file__))
    profile = config.kodi_version

    cmd = [
        "docker",
        "compose",
        "--profile",
        profile,
        "down",
        "-v",
    ]

    try:
        subprocess.run(
            cmd,
            cwd=compose_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:
        logger.warning("Failed to stop container: %s", exc)


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "skip_kodi_version(version): skip test for the specified Kodi version",
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip tests marked with skip_kodi_version if current version matches."""
    markers = list(item.iter_markers(name="skip_kodi_version"))
    if not markers:
        return

    current_version = os.environ.get("KODI_VERSION", "kodi20")

    for marker in markers:
        skip_versions = marker.args
        if current_version in skip_versions:
            pytest.skip("Test skipped for Kodi version '%s'" % current_version)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_config() -> E2EConfig:
    """Load and validate E2E configuration from environment."""
    return load_config()


@pytest.fixture(scope="session")
def kodi_container(e2e_config: E2EConfig) -> Generator[str, None, None]:
    """Start Kodi container, install addon from ZIP, yield container name.

    Installation flow:
    1. Verify addon ZIP exists in dist/ (skip if missing)
    2. Start docker-compose with selected profile
    3. Wait for healthcheck (poll every 2s, timeout 60s)
    4. Provision settings.xml (Kodi 20 format)
    5. Install addon from ZIP (unzip inside container)
    6. Enable addon via Addons.SetAddonEnabled
    7. Verify addon appears in Addons.GetAddons within 15s
    8. Yield container name
    9. Teardown: stop container

    Skips all tests if any step fails.

    Yields:
        Container name string (e.g. "kodi-e2e-kodi20").
    """
    # Check required env vars
    skip_msg = _check_required_env_vars(e2e_config)
    if skip_msg:
        pytest.skip(skip_msg)

    # Step 1: Verify addon ZIP exists in dist/
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dist_dir = os.path.join(project_root, "dist")
    zip_filename = find_addon_zip(dist_dir)

    if zip_filename is None:
        pytest.skip("Addon ZIP not found in dist/. Build it first: python3 build_addon.py")

    # Step 2: Start container
    if not _start_container(e2e_config):
        pytest.skip("Failed to start Kodi container (version: %s)" % e2e_config.kodi_version)

    container_name = _CONTAINER_NAME_TEMPLATE % e2e_config.kodi_version
    http_url = "http://%s:%d/jsonrpc" % (e2e_config.kodi_host, e2e_config.kodi_http_port)

    # Step 3: Wait for healthcheck (poll every 2s, timeout 60s)
    if not _wait_for_healthcheck(http_url, timeout=60.0, interval=2.0):
        _stop_container(e2e_config)
        pytest.skip(
            "Kodi container not reachable within 60s (version: %s, url: %s)" % (e2e_config.kodi_version, http_url)
        )

    # Step 4: Provision settings.xml BEFORE enabling the addon
    settings_dict = {
        "user_login": e2e_config.cbilling_public_key,
        "api_url": e2e_config.cbilling_api_url,
        "stb_timezone": "Europe/Moscow",
        "show_vod": "true",
    }
    if not provision_settings(container_name, settings_dict):
        _stop_container(e2e_config)
        pytest.skip("Failed to provision addon settings.xml in container %s" % container_name)

    # Step 5: Install addon from ZIP (unzip inside container)
    if not install_addon_from_zip(container_name, zip_filename):
        _stop_container(e2e_config)
        pytest.skip("Failed to install addon from ZIP in container %s" % container_name)

    # Step 6: Enable addon via Addons.SetAddonEnabled
    if not enable_addon(http_url, ADDON_ID):
        _stop_container(e2e_config)
        pytest.skip("Failed to enable addon %s in container %s" % (ADDON_ID, container_name))

    # Step 7: Verify addon appears in Addons.GetAddons within 15s
    if not verify_addon_enabled(http_url, ADDON_ID, timeout=15.0):
        log_tail = _get_kodi_log_tail(container_name, lines=200)
        _stop_container(e2e_config)
        pytest.skip(
            "Addon %s not found in Addons.GetAddons within 15s.\nLast 200 lines of kodi.log:\n%s" % (ADDON_ID, log_tail)
        )

    # Step 8: Configure Kodi locale (Russian) AFTER addon is installed
    # Switching language forces Kodi to reload localized strings for all
    # installed addons, which is the only reliable way to get addon strings
    # loaded without a full Kodi restart.
    if not _configure_kodi_settings(http_url):
        _stop_container(e2e_config)
        pytest.skip("Failed to configure Kodi settings (locale) in %s" % container_name)

    yield container_name

    # Teardown: stop container
    _stop_container(e2e_config)


@pytest.fixture(scope="session")
def kodi_client(e2e_config: E2EConfig, kodi_container: str) -> Generator[KodiClient, None, None]:
    """Create and connect a KodiClient instance for the session.

    Uses 30.0s default timeout for individual requests.
    Skips all tests if connection cannot be established within 30 seconds.

    Yields:
        Connected KodiClient instance.
    """
    ws_url = "ws://%s:%d/jsonrpc" % (e2e_config.kodi_host, e2e_config.kodi_ws_port)
    http_url = "http://%s:%d/jsonrpc" % (e2e_config.kodi_host, e2e_config.kodi_http_port)

    client = KodiClient(ws_url=ws_url, http_url=http_url, timeout=30.0)

    # Attempt connection with retries (poll every 2s, timeout 30s)
    deadline = time.monotonic() + 30.0
    connected = False
    last_error = None  # type: Optional[Exception]

    while time.monotonic() < deadline:
        try:
            client.connect()
            connected = True
            break
        except Exception as exc:
            last_error = exc
            time.sleep(2.0)

    if not connected:
        pytest.skip("Could not connect KodiClient within 30s: %s" % last_error)

    yield client

    # Teardown: close connection
    client.close()


@pytest.fixture(scope="session")
def addon_settings(e2e_config: E2EConfig) -> Dict[str, str]:
    """Load addon credentials from environment configuration.

    Returns:
        Dictionary with keys: api_url, public_key, kodi_version.
    """
    return {
        "api_url": e2e_config.cbilling_api_url,
        "public_key": e2e_config.cbilling_public_key,
        "kodi_version": e2e_config.kodi_version,
    }


@pytest.fixture(autouse=True)
def collect_artifacts_on_failure(
    request: pytest.FixtureRequest,
    e2e_config: E2EConfig,
    kodi_container: str,
    kodi_client: KodiClient,
) -> Generator[None, None, None]:
    """Collect screenshot and kodi.log on test failure.

    This fixture is autouse — it runs for every e2e test automatically.
    On failure, it captures a screenshot and copies kodi.log from the
    container, printing artifact paths to stdout.
    """
    yield

    # Check if the test failed
    if not hasattr(request.node, "rep_call"):
        return
    if not request.node.rep_call.failed:
        return

    test_name = request.node.nodeid
    collector = ArtifactCollector(
        artifacts_dir=e2e_config.artifacts_dir,
        kodi_version=e2e_config.kodi_version,
    )

    # Collect screenshot
    screenshot_path = collector.collect_screenshot(kodi_client, test_name)
    if screenshot_path:
        print("\n  Artifact (screenshot): %s" % os.path.abspath(screenshot_path))

    # Collect kodi.log
    log_path = collector.collect_kodi_log(kodi_container, test_name)
    if log_path:
        print("  Artifact (kodi.log): %s" % os.path.abspath(log_path))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator:
    """Store test result on the item node for use by collect_artifacts_on_failure."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_%s" % rep.when, rep)
