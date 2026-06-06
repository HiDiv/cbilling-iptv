# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""E2E test configuration module.

Loads configuration from environment variables with support for .env file
loading. System environment variables always take precedence over .env values.
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional

# Valid Kodi version identifiers
VALID_KODI_VERSIONS = ("kodi19", "kodi20", "kodi21")


def _load_dotenv(env_path: str) -> Dict[str, str]:
    """Parse a .env file and return key-value pairs.

    Skips empty lines and comments (lines starting with #).
    Strips optional quotes from values.

    Args:
        env_path: Absolute path to the .env file.

    Returns:
        Dictionary of parsed environment variables.
    """
    result = {}  # type: Dict[str, str]
    if not os.path.isfile(env_path):
        return result

    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Split on first '='
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes (single or double)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result


def _get_env(key: str, default: str = "", dotenv_vars: Optional[Dict[str, str]] = None) -> str:
    """Get environment variable with .env fallback.

    System environment variables take precedence over .env values.

    Args:
        key: Environment variable name.
        default: Default value if not found anywhere.
        dotenv_vars: Parsed .env variables (fallback source).

    Returns:
        The resolved value.
    """
    # System env takes precedence
    value = os.environ.get(key)
    if value is not None:
        return value
    # Fall back to .env file
    if dotenv_vars and key in dotenv_vars:
        return dotenv_vars[key]
    return default


@dataclass
class E2EConfig:
    """Configuration for E2E test execution.

    Attributes:
        kodi_host: Kodi container hostname.
        kodi_http_port: Kodi HTTP JSON-RPC port.
        kodi_ws_port: Kodi WebSocket JSON-RPC port.
        kodi_version: Target Kodi version (kodi19, kodi20, kodi21).
        cbilling_api_url: Cbilling API base URL.
        cbilling_public_key: Cbilling public key (access code).
        record_video: Whether to record video during test execution.
        artifacts_dir: Directory for storing test artifacts.
    """

    kodi_host: str = "localhost"
    kodi_http_port: int = 8080
    kodi_ws_port: int = 9090
    kodi_version: str = "kodi20"
    cbilling_api_url: str = ""
    cbilling_public_key: str = ""
    record_video: bool = False
    artifacts_dir: str = "tests/e2e/artifacts"


def load_config() -> E2EConfig:
    """Create an E2EConfig instance from environment variables.

    Loads variables from the project root .env file as fallback, with system
    environment variables taking precedence. Validates KODI_VERSION against
    allowed values and exits with an error for invalid values.

    Returns:
        Configured E2EConfig instance.

    Raises:
        SystemExit: If KODI_VERSION is set to an invalid value.
    """
    # Determine project root (two levels up from tests/e2e/)
    config_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(config_dir))
    env_path = os.path.join(project_root, ".env")

    # Load .env file
    dotenv_vars = _load_dotenv(env_path)

    # Read configuration values
    kodi_host = _get_env("KODI_HOST", "localhost", dotenv_vars)
    kodi_http_port = int(_get_env("KODI_HTTP_PORT", "8080", dotenv_vars))
    kodi_ws_port = int(_get_env("KODI_WS_PORT", "9090", dotenv_vars))
    kodi_version = _get_env("KODI_VERSION", "kodi20", dotenv_vars)
    cbilling_api_url = _get_env("CBILLING_API_URL", "", dotenv_vars)
    cbilling_public_key = _get_env("CBILLING_PUBLIC_KEY", "", dotenv_vars)
    record_video_raw = _get_env("E2E_RECORD_VIDEO", "", dotenv_vars)
    artifacts_dir = _get_env("E2E_ARTIFACTS_DIR", "tests/e2e/artifacts", dotenv_vars)

    # Parse record_video boolean
    record_video = record_video_raw.lower() in ("1", "true")

    # Validate KODI_VERSION
    if kodi_version not in VALID_KODI_VERSIONS:
        valid_str = ", ".join(VALID_KODI_VERSIONS)
        sys.exit(f"Error: KODI_VERSION='{kodi_version}' is invalid. Valid values: {valid_str}")

    return E2EConfig(
        kodi_host=kodi_host,
        kodi_http_port=kodi_http_port,
        kodi_ws_port=kodi_ws_port,
        kodi_version=kodi_version,
        cbilling_api_url=cbilling_api_url,
        cbilling_public_key=cbilling_public_key,
        record_video=record_video,
        artifacts_dir=artifacts_dir,
    )
