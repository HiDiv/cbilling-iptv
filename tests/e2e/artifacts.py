# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Artifact collection for E2E test diagnostics.

Collects screenshots, Kodi logs, and video recordings on test failure.
All collection methods handle errors gracefully — they log warnings and
return None on failure, never interrupting test execution.
"""

import logging
import os
import re
import subprocess
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum length for the sanitized test name portion of filenames
_MAX_NAME_LENGTH = 100


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames.

    Replaces any character that is not alphanumeric, underscore, or hyphen
    with an underscore. Truncates the result to _MAX_NAME_LENGTH characters.

    Args:
        name: Raw string to sanitize.

    Returns:
        Sanitized string safe for use in filenames.
    """
    # Replace non-allowed characters with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    # Collapse multiple consecutive underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Strip leading/trailing underscores
    sanitized = sanitized.strip("_")
    # Truncate to max length
    if len(sanitized) > _MAX_NAME_LENGTH:
        sanitized = sanitized[:_MAX_NAME_LENGTH]
    return sanitized


class ArtifactCollector:
    """Collects screenshots, logs, and video on test failure.

    All public methods catch exceptions internally, log warnings, and
    return None on failure — they never raise or interrupt test execution.

    Args:
        artifacts_dir: Directory path where artifacts will be saved.
            Created automatically if it does not exist.
        kodi_version: Kodi version identifier (e.g. "kodi20") included
            in artifact filenames for disambiguation.
    """

    def __init__(self, artifacts_dir: str, kodi_version: str) -> None:
        self.artifacts_dir = artifacts_dir
        self.kodi_version = kodi_version
        self._recording_process = None  # type: Optional[subprocess.Popen]
        self._recording_filepath = None  # type: Optional[str]

        # Ensure artifacts directory exists
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def _generate_filename(self, test_name: str, extension: str) -> str:
        """Generate a sanitized artifact filename.

        Pattern: {sanitized_test_name}_{kodi_version}_{YYYYMMDD_HHMMSS}.{ext}

        Args:
            test_name: Raw test name to include in the filename.
            extension: File extension without the leading dot.

        Returns:
            Full absolute path to the artifact file.
        """
        sanitized_name = _sanitize_filename(test_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "%s_%s_%s.%s" % (sanitized_name, self.kodi_version, timestamp, extension)
        return os.path.join(self.artifacts_dir, filename)

    def collect_screenshot(self, kodi_client: object, test_name: str) -> Optional[str]:
        """Capture a screenshot from Kodi and save it to the artifacts directory.

        Uses the KodiClient.take_screenshot() method to capture the current
        Kodi display.

        Args:
            kodi_client: A KodiClient instance with a take_screenshot(filepath) method.
            test_name: Name of the test (used in the artifact filename).

        Returns:
            Absolute path to the saved screenshot, or None on failure.
        """
        try:
            filepath = self._generate_filename(test_name, "png")
            kodi_client.take_screenshot(filepath)  # type: ignore[attr-defined]
            logger.info("Screenshot saved: %s", filepath)
            return filepath
        except Exception as exc:
            logger.warning("Failed to capture screenshot for '%s': %s", test_name, exc)
            return None

    def collect_kodi_log(self, container_name: str, test_name: str) -> Optional[str]:
        """Copy kodi.log from the Docker container to the artifacts directory.

        Uses ``docker cp`` to extract the log file from the running container.

        Args:
            container_name: Name or ID of the Docker container running Kodi.
            test_name: Name of the test (used in the artifact filename).

        Returns:
            Absolute path to the saved log file, or None on failure.
        """
        try:
            filepath = self._generate_filename(test_name, "log")
            container_log_path = "%s:/root/.kodi/temp/kodi.log" % container_name
            result = subprocess.run(
                ["docker", "cp", container_log_path, filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    "docker cp failed for '%s': %s",
                    test_name,
                    result.stderr.strip(),
                )
                return None
            logger.info("Kodi log saved: %s", filepath)
            return filepath
        except Exception as exc:
            logger.warning("Failed to collect kodi.log for '%s': %s", test_name, exc)
            return None

    def start_video_recording(self, container_name: str) -> None:
        """Start video recording inside the Kodi container using ffmpeg.

        Records the Xvfb display (:99) to a file inside the container.
        The recording is stopped and retrieved via stop_video_recording().

        Args:
            container_name: Name or ID of the Docker container running Kodi.
        """
        try:
            # Stop any existing recording first
            if self._recording_process is not None:
                self.stop_video_recording()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            container_output = "/tmp/e2e_recording_%s.mp4" % timestamp
            self._recording_filepath = container_output

            # Start ffmpeg recording inside the container
            cmd = [
                "docker",
                "exec",
                "-d",
                container_name,
                "ffmpeg",
                "-y",
                "-f",
                "x11grab",
                "-video_size",
                "1280x720",
                "-framerate",
                "10",
                "-i",
                ":99",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                container_output,
            ]
            self._recording_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Store container name for stop
            self._recording_container = container_name
            logger.info("Video recording started in container '%s'", container_name)
        except Exception as exc:
            logger.warning("Failed to start video recording: %s", exc)
            self._recording_process = None
            self._recording_filepath = None

    def stop_video_recording(self) -> Optional[str]:
        """Stop video recording and copy the file to the artifacts directory.

        Sends SIGINT to the ffmpeg process inside the container, waits for
        it to finish, then copies the recording to the local artifacts dir.

        Returns:
            Absolute path to the saved video file, or None on failure.
        """
        if self._recording_process is None or self._recording_filepath is None:
            return None

        container_name = getattr(self, "_recording_container", None)
        container_output = self._recording_filepath

        # Reset state before attempting stop
        self._recording_process = None
        self._recording_filepath = None

        if container_name is None:
            return None

        try:
            # Send SIGINT to ffmpeg inside the container to stop recording gracefully
            subprocess.run(
                ["docker", "exec", container_name, "pkill", "-INT", "ffmpeg"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Wait for ffmpeg to finalize the file
            time.sleep(2)

            # Copy the recording from the container
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = "recording_%s_%s.mp4" % (self.kodi_version, timestamp)
            local_path = os.path.join(self.artifacts_dir, filename)

            container_src = "%s:%s" % (container_name, container_output)
            result = subprocess.run(
                ["docker", "cp", container_src, local_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning("Failed to copy video recording: %s", result.stderr.strip())
                return None

            logger.info("Video recording saved: %s", local_path)
            return local_path
        except Exception as exc:
            logger.warning("Failed to stop video recording: %s", exc)
            return None
