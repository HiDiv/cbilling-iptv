# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Addon installer module for E2E tests.

Handles ZIP-based addon installation inside a running Kodi Docker container,
settings provisioning in Kodi 20 format, and addon activation via JSON-RPC.
"""

import glob
import logging
import os
import subprocess
import time
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Addon constants
ADDON_ID = "plugin.video.cbilling.iptv"
ADDONS_INSTALL_PATH = "/root/.kodi/addons/"
ZIP_MOUNT_PATH = "/addons_zip/"
SETTINGS_DIR = "/root/.kodi/userdata/addon_data/%s" % ADDON_ID
SETTINGS_PATH = "%s/settings.xml" % SETTINGS_DIR


def find_addon_zip(dist_dir: str) -> Optional[str]:
    """Locate the built addon ZIP file in the dist/ directory.

    Searches for ZIP files matching the addon ID pattern
    (``plugin.video.cbilling.iptv-*.zip``). If multiple ZIPs are found,
    returns the one with the most recent modification time.

    Args:
        dist_dir: Path to the dist/ directory containing built ZIPs.

    Returns:
        Filename (not full path) of the addon ZIP, or None if not found.
    """
    if not os.path.isdir(dist_dir):
        logger.warning("dist directory does not exist: %s", dist_dir)
        return None

    pattern = os.path.join(dist_dir, "%s-*.zip" % ADDON_ID)
    matches = glob.glob(pattern)

    if not matches:
        logger.warning("No addon ZIP found matching pattern: %s", pattern)
        return None

    # Sort by modification time (newest first) and return the filename
    matches.sort(key=os.path.getmtime, reverse=True)
    result = os.path.basename(matches[0])
    logger.info("Found addon ZIP: %s", result)
    return result


def install_addon_from_zip(container_name: str, zip_filename: str) -> bool:
    """Install the addon by unzipping inside the container.

    Extracts the addon ZIP from the mounted ``/addons_zip/`` directory
    to ``/root/.kodi/addons/`` inside the container using ``docker exec``.

    Args:
        container_name: Name of the running Docker container.
        zip_filename: Filename of the ZIP (e.g. ``plugin.video.cbilling.iptv-2.0.4-dev.zip``).

    Returns:
        True if installation succeeded, False otherwise.
    """
    zip_path_in_container = "%s%s" % (ZIP_MOUNT_PATH, zip_filename)

    # Unzip the addon into the addons directory using Python's zipfile module
    # (unzip binary may not be available in minimal container images)
    python_script = "import zipfile; zipfile.ZipFile('%s').extractall('%s')" % (
        zip_path_in_container,
        ADDONS_INSTALL_PATH,
    )
    cmd = [
        "docker",
        "exec",
        container_name,
        "python3",
        "-c",
        python_script,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(
                "Failed to extract addon ZIP in container %s: %s",
                container_name,
                result.stderr.strip(),
            )
            return False
        logger.info(
            "Addon installed from %s to %s in container %s",
            zip_path_in_container,
            ADDONS_INSTALL_PATH,
            container_name,
        )

        # Trigger Kodi to rescan the addons directory so it discovers the new addon
        scan_cmd = [
            "docker",
            "exec",
            container_name,
            "kodi-send",
            "--action=UpdateLocalAddons",
        ]
        scan_result = subprocess.run(
            scan_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if scan_result.returncode != 0:
            logger.warning(
                "kodi-send UpdateLocalAddons failed (non-fatal): %s",
                scan_result.stderr.strip(),
            )
        else:
            logger.info("Triggered UpdateLocalAddons in container %s", container_name)
            # Give Kodi time to process the addon database update
            time.sleep(5)

        return True
    except subprocess.TimeoutExpired:
        logger.error("Timeout extracting addon ZIP in container %s", container_name)
        return False
    except Exception as exc:
        logger.error("Error installing addon from ZIP: %s", exc)
        return False


def provision_settings(container_name: str, settings_dict: Dict[str, str]) -> bool:
    """Create settings.xml in Kodi 20 format inside the container.

    Generates a settings XML file with the provided key-value pairs and
    writes it to the addon's settings path inside the container. The
    directory is created if it does not exist.

    Kodi 20 format::

        <settings version="2">
            <setting id="key">value</setting>
        </settings>

    Args:
        container_name: Name of the running Docker container.
        settings_dict: Dictionary of setting ID to value mappings.

    Returns:
        True if settings were provisioned successfully, False otherwise.
    """
    # Build settings XML in Kodi 20 format
    lines = ['<settings version="2">']
    for setting_id, value in settings_dict.items():
        lines.append('    <setting id="%s">%s</setting>' % (setting_id, value))
    lines.append("</settings>")
    settings_xml = "\n".join(lines) + "\n"

    try:
        # Create the settings directory
        mkdir_cmd = [
            "docker",
            "exec",
            container_name,
            "mkdir",
            "-p",
            SETTINGS_DIR,
        ]
        mkdir_result = subprocess.run(
            mkdir_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if mkdir_result.returncode != 0:
            logger.error(
                "Failed to create settings directory in container %s: %s",
                container_name,
                mkdir_result.stderr.strip(),
            )
            return False

        # Write settings.xml via stdin pipe to docker exec
        write_cmd = [
            "docker",
            "exec",
            "-i",
            container_name,
            "bash",
            "-c",
            "cat > %s" % SETTINGS_PATH,
        ]
        write_result = subprocess.run(
            write_cmd,
            input=settings_xml,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if write_result.returncode != 0:
            logger.error(
                "Failed to write settings.xml in container %s: %s",
                container_name,
                write_result.stderr.strip(),
            )
            return False

        logger.info(
            "Provisioned settings.xml with %d settings in container %s",
            len(settings_dict),
            container_name,
        )
        return True
    except subprocess.TimeoutExpired:
        logger.error("Timeout provisioning settings in container %s", container_name)
        return False
    except Exception as exc:
        logger.error("Error provisioning settings: %s", exc)
        return False


def enable_addon(http_url: str, addon_id: str) -> bool:
    """Enable the addon via JSON-RPC Addons.SetAddonEnabled.

    Sends a JSON-RPC request to Kodi's HTTP endpoint to enable the
    specified addon.

    Args:
        http_url: Kodi HTTP JSON-RPC endpoint URL (e.g. ``http://localhost:8080/jsonrpc``).
        addon_id: The addon identifier (e.g. ``plugin.video.cbilling.iptv``).

    Returns:
        True if the addon was enabled successfully, False otherwise.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": True},
        "id": 1,
    }

    try:
        resp = requests.post(http_url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") == "OK":
            logger.info("Addon %s enabled successfully via JSON-RPC", addon_id)
            return True

        # Check for error in response
        error = data.get("error")
        if error:
            logger.error(
                "JSON-RPC error enabling addon %s: [%s] %s",
                addon_id,
                error.get("code", -1),
                error.get("message", "Unknown error"),
            )
        else:
            logger.error("Unexpected response enabling addon %s: %s", addon_id, data)
        return False
    except requests.Timeout:
        logger.error("Timeout enabling addon %s at %s", addon_id, http_url)
        return False
    except requests.RequestException as exc:
        logger.error("HTTP error enabling addon %s: %s", addon_id, exc)
        return False
    except Exception as exc:
        logger.error("Error enabling addon %s: %s", addon_id, exc)
        return False


def verify_addon_enabled(
    http_url: str,
    addon_id: str,
    timeout: float = 15.0,
) -> bool:
    """Verify the addon appears in Addons.GetAddons with enabled=true.

    Polls the Kodi JSON-RPC endpoint every 2 seconds until the addon
    is found in the list of enabled addons or the timeout expires.

    Args:
        http_url: Kodi HTTP JSON-RPC endpoint URL.
        addon_id: The addon identifier to verify.
        timeout: Maximum time in seconds to wait for the addon to appear.

    Returns:
        True if the addon is found and enabled within the timeout, False otherwise.
    """
    deadline = time.monotonic() + timeout
    poll_interval = 2.0

    while time.monotonic() < deadline:
        payload = {
            "jsonrpc": "2.0",
            "method": "Addons.GetAddons",
            "params": {"enabled": True},
            "id": 1,
        }

        try:
            resp = requests.post(http_url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            addons = data.get("result", {}).get("addons") or []
            for addon in addons:
                if addon.get("addonid") == addon_id:
                    logger.info(
                        "Addon %s verified as enabled (found in GetAddons)",
                        addon_id,
                    )
                    return True
        except (requests.RequestException, ValueError) as exc:
            logger.debug("Polling GetAddons failed (will retry): %s", exc)

        time.sleep(poll_interval)

    logger.error(
        "Addon %s not found in enabled addons after %.1fs",
        addon_id,
        timeout,
    )
    return False


class AddonInstaller:
    """High-level addon installer for E2E tests.

    Combines all installation steps into a single class that manages
    the full lifecycle: ZIP installation, settings provisioning, addon
    activation, and verification.

    Args:
        container_name: Name of the running Docker container.
        http_url: Kodi HTTP JSON-RPC endpoint URL.
    """

    def __init__(self, container_name: str, http_url: str) -> None:
        self.container_name = container_name
        self.http_url = http_url

    def install_from_zip(self, zip_path_in_container: str) -> bool:
        """Unzip addon to /root/.kodi/addons/ inside the container.

        Args:
            zip_path_in_container: Full path to the ZIP file inside the container
                (e.g. ``/addons_zip/plugin.video.cbilling.iptv-2.0.4-dev.zip``).

        Returns:
            True if installation succeeded, False otherwise.
        """
        zip_filename = os.path.basename(zip_path_in_container)
        return install_addon_from_zip(self.container_name, zip_filename)

    def provision_settings(self, settings: Dict[str, str]) -> bool:
        """Create settings.xml in Kodi 20 format before enabling addon.

        Args:
            settings: Dictionary of setting ID to value mappings.

        Returns:
            True if settings were provisioned successfully, False otherwise.
        """
        return provision_settings(self.container_name, settings)

    def enable_addon(self, addon_id: str) -> bool:
        """Enable addon via JSON-RPC Addons.SetAddonEnabled.

        Args:
            addon_id: The addon identifier to enable.

        Returns:
            True if the addon was enabled successfully, False otherwise.
        """
        return enable_addon(self.http_url, addon_id)

    def verify_addon_enabled(self, addon_id: str, timeout: float = 15.0) -> bool:
        """Verify addon appears in Addons.GetAddons with enabled=true.

        Args:
            addon_id: The addon identifier to verify.
            timeout: Maximum time in seconds to wait.

        Returns:
            True if the addon is found and enabled within the timeout.
        """
        return verify_addon_enabled(self.http_url, addon_id, timeout=timeout)
