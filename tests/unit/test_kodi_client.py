# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for KodiClient, ArtifactCollector, and E2EConfig.

Tests cover JSON-RPC request construction, response parsing, error handling,
navigation method mapping, artifact filename sanitization, KODI_VERSION
validation, and E2EConfig loading from environment.

These tests run without Docker or a running Kodi instance.
"""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

# Ensure tests/e2e modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))

from tests.e2e.artifacts import ArtifactCollector, _sanitize_filename
from tests.e2e.config import VALID_KODI_VERSIONS, load_config
from tests.e2e.exceptions import KodiConnectionError, KodiRpcError
from tests.e2e.kodi_client import KodiClient

# ===========================================================================
# JSON-RPC Request Construction
# ===========================================================================


class TestJsonRpcRequestConstruction:
    """Test JSON-RPC request construction in KodiClient."""

    def test_positive_valid_method_and_params(self):
        """Valid method and params produce a correct JSON-RPC envelope."""
        client = KodiClient()
        # Access the internal method to build a request payload
        # We test by inspecting what send_request would send
        client._request_id = 0  # Reset for predictable ID

        # Mock the websocket to capture the sent payload
        mock_ws = MagicMock()
        response_data = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "pong"})

        async def mock_send(data):
            pass

        async def mock_recv():
            return response_data

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        result = client.send_request("JSONRPC.Ping", {"param1": "value1"})

        assert result == "pong"

    def test_positive_request_id_increments(self):
        """Each request gets a unique auto-incrementing ID."""
        client = KodiClient()
        client._request_id = 0

        id1 = client._next_id()
        id2 = client._next_id()
        id3 = client._next_id()

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    def test_boundary_none_params(self):
        """None params should not include 'params' key in the payload."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        sent_payloads = []

        async def mock_send(data):
            sent_payloads.append(json.loads(data))

        async def mock_recv():
            return json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"})

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        client.send_request("JSONRPC.Ping", None)

        assert len(sent_payloads) == 1
        payload = sent_payloads[0]
        assert "params" not in payload
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "JSONRPC.Ping"
        assert payload["id"] == 1

    def test_boundary_empty_params_dict(self):
        """Empty params dict should be included in the payload."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        sent_payloads = []

        async def mock_send(data):
            sent_payloads.append(json.loads(data))

        async def mock_recv():
            return json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"})

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        client.send_request("JSONRPC.Ping", {})

        assert len(sent_payloads) == 1
        payload = sent_payloads[0]
        assert payload["params"] == {}

    def test_negative_not_connected_raises_error(self):
        """Sending a request without connecting raises KodiConnectionError."""
        client = KodiClient()
        # _ws is None by default (not connected)

        with pytest.raises(KodiConnectionError):
            client.send_request("JSONRPC.Ping")


# ===========================================================================
# Response Parsing
# ===========================================================================


class TestResponseParsing:
    """Test JSON-RPC response parsing."""

    def test_positive_full_response_with_result(self):
        """Full response with result field is parsed correctly."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        response = {"jsonrpc": "2.0", "id": 1, "result": {"files": [{"label": "Channel 1", "file": "url1"}]}}

        async def mock_send(data):
            pass

        async def mock_recv():
            return json.dumps(response)

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        result = client.send_request("Files.GetDirectory", {"directory": "plugin://test/"})

        assert result == {"files": [{"label": "Channel 1", "file": "url1"}]}

    def test_negative_malformed_json_response(self):
        """Malformed JSON response raises KodiRpcError."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()

        async def mock_send(data):
            pass

        async def mock_recv():
            return "not valid json {{{{"

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        with pytest.raises(KodiRpcError) as exc_info:
            client.send_request("JSONRPC.Ping")

        assert "Malformed JSON" in exc_info.value.message

    def test_boundary_empty_files_array(self):
        """Response with empty files array returns empty list from get_container_items."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        response = {"jsonrpc": "2.0", "id": 1, "result": {"files": []}}

        async def mock_send(data):
            pass

        async def mock_recv():
            return json.dumps(response)

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        items = client.get_container_items("plugin://test/")

        assert items == []

    def test_boundary_null_files_field(self):
        """Response with null files field returns empty list."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        response = {"jsonrpc": "2.0", "id": 1, "result": {"files": None}}

        async def mock_send(data):
            pass

        async def mock_recv():
            return json.dumps(response)

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        items = client.get_container_items("plugin://test/")

        assert items == []


# ===========================================================================
# Error Response Handling
# ===========================================================================


class TestErrorResponseHandling:
    """Test JSON-RPC error response handling."""

    def test_positive_error_with_code_and_message_raises(self):
        """Error response with code and message raises KodiRpcError."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"},
        }

        async def mock_send(data):
            pass

        async def mock_recv():
            return json.dumps(response)

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        with pytest.raises(KodiRpcError) as exc_info:
            client.send_request("Invalid.Method")

        assert exc_info.value.code == -32601
        assert exc_info.value.message == "Method not found"
        assert exc_info.value.method == "Invalid.Method"

    def test_negative_malformed_error_object(self):
        """Error response without code/message uses defaults."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        # Error object missing code and message fields
        response = {"jsonrpc": "2.0", "id": 1, "error": {}}

        async def mock_send(data):
            pass

        async def mock_recv():
            return json.dumps(response)

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        with pytest.raises(KodiRpcError) as exc_info:
            client.send_request("Some.Method")

        # Should use defaults: code=-1, message="Unknown error"
        assert exc_info.value.code == -1
        assert exc_info.value.message == "Unknown error"

    def test_boundary_empty_message_string(self):
        """Error response with empty message string still raises."""
        client = KodiClient()
        client._request_id = 0

        mock_ws = MagicMock()
        response = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": ""}}

        async def mock_send(data):
            pass

        async def mock_recv():
            return json.dumps(response)

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        with pytest.raises(KodiRpcError) as exc_info:
            client.send_request("Some.Method")

        assert exc_info.value.code == -32600
        assert exc_info.value.message == ""


# ===========================================================================
# Navigation Method → Action String Mapping
# ===========================================================================


class TestNavigationMethods:
    """Test that navigation methods send the correct action strings."""

    @pytest.fixture()
    def client_with_mock_ws(self):
        """Create a KodiClient with a mock WebSocket that captures sent payloads."""
        client = KodiClient()
        client._request_id = 0

        sent_payloads = []

        mock_ws = MagicMock()

        async def mock_send(data):
            sent_payloads.append(json.loads(data))

        async def mock_recv():
            return json.dumps({"jsonrpc": "2.0", "id": client._request_id, "result": "OK"})

        mock_ws.send = mock_send
        mock_ws.recv = mock_recv
        client._ws = mock_ws

        return client, sent_payloads

    def test_input_up(self, client_with_mock_ws):
        """input_up sends Input.ExecuteAction with action='up'."""
        client, payloads = client_with_mock_ws
        client.input_up()
        assert payloads[-1]["method"] == "Input.ExecuteAction"
        assert payloads[-1]["params"] == {"action": "up"}

    def test_input_down(self, client_with_mock_ws):
        """input_down sends Input.ExecuteAction with action='down'."""
        client, payloads = client_with_mock_ws
        client.input_down()
        assert payloads[-1]["method"] == "Input.ExecuteAction"
        assert payloads[-1]["params"] == {"action": "down"}

    def test_input_left(self, client_with_mock_ws):
        """input_left sends Input.ExecuteAction with action='left'."""
        client, payloads = client_with_mock_ws
        client.input_left()
        assert payloads[-1]["method"] == "Input.ExecuteAction"
        assert payloads[-1]["params"] == {"action": "left"}

    def test_input_right(self, client_with_mock_ws):
        """input_right sends Input.ExecuteAction with action='right'."""
        client, payloads = client_with_mock_ws
        client.input_right()
        assert payloads[-1]["method"] == "Input.ExecuteAction"
        assert payloads[-1]["params"] == {"action": "right"}

    def test_input_select(self, client_with_mock_ws):
        """input_select sends Input.ExecuteAction with action='select'."""
        client, payloads = client_with_mock_ws
        client.input_select()
        assert payloads[-1]["method"] == "Input.ExecuteAction"
        assert payloads[-1]["params"] == {"action": "select"}

    def test_input_back(self, client_with_mock_ws):
        """input_back sends Input.ExecuteAction with action='back'."""
        client, payloads = client_with_mock_ws
        client.input_back()
        assert payloads[-1]["method"] == "Input.ExecuteAction"
        assert payloads[-1]["params"] == {"action": "back"}

    def test_input_home(self, client_with_mock_ws):
        """input_home sends Input.Home (no params)."""
        client, payloads = client_with_mock_ws
        client.input_home()
        assert payloads[-1]["method"] == "Input.Home"
        assert "params" not in payloads[-1]


# ===========================================================================
# Artifact Filename Sanitization
# ===========================================================================


class TestArtifactFilenameSanitization:
    """Test artifact filename sanitization logic."""

    def test_positive_normal_name(self):
        """Normal test name is preserved (with allowed chars)."""
        result = _sanitize_filename("test_addon_lifecycle")
        assert result == "test_addon_lifecycle"

    def test_positive_hyphens_preserved(self):
        """Hyphens are preserved in filenames."""
        result = _sanitize_filename("test-navigation-back")
        assert result == "test-navigation-back"

    def test_negative_special_chars_replaced(self):
        """Special characters are replaced with underscores."""
        result = _sanitize_filename("test[param1]::method<>")
        # All special chars become underscores, collapsed
        assert all(c.isalnum() or c in ("_", "-") for c in result)
        assert "[" not in result
        assert "]" not in result
        assert "<" not in result
        assert ">" not in result

    def test_negative_unicode_replaced(self):
        """Unicode characters are replaced with underscores."""
        result = _sanitize_filename("test_Прямой_эфир")
        # Cyrillic chars should be replaced
        assert all(c.isalnum() or c in ("_", "-") for c in result)

    def test_negative_path_separators_replaced(self):
        """Path separators (/ and \\) are replaced."""
        result = _sanitize_filename("tests/e2e/test_nav.py::test_func")
        assert "/" not in result
        assert "\\" not in result

    def test_boundary_long_name_truncated(self):
        """Names longer than 100 characters are truncated."""
        long_name = "a" * 150
        result = _sanitize_filename(long_name)
        assert len(result) <= 100

    def test_boundary_empty_string(self):
        """Empty string returns empty string."""
        result = _sanitize_filename("")
        assert result == ""

    def test_collector_filename_includes_version_and_timestamp(self, tmp_path):
        """ArtifactCollector generates filenames with version and timestamp."""
        collector = ArtifactCollector(
            artifacts_dir=str(tmp_path),
            kodi_version="kodi20",
        )
        filepath = collector._generate_filename("test_example", "png")

        filename = os.path.basename(filepath)
        assert "kodi20" in filename
        assert filename.endswith(".png")
        assert "test_example" in filename


# ===========================================================================
# KODI_VERSION Validation
# ===========================================================================


class TestKodiVersionValidation:
    """Test KODI_VERSION validation in config module."""

    @pytest.mark.parametrize("version", ["kodi19", "kodi20", "kodi21"])
    def test_positive_valid_versions(self, version, monkeypatch, tmp_path):
        """Valid KODI_VERSION values are accepted."""
        monkeypatch.setenv("KODI_VERSION", version)
        monkeypatch.setenv("CBILLING_API_URL", "http://example.com")
        monkeypatch.setenv("CBILLING_PUBLIC_KEY", "testkey")
        # Point to a non-existent .env so it doesn't interfere
        monkeypatch.setattr("tests.e2e.config.os.path.dirname", lambda x: str(tmp_path))

        # load_config should not raise for valid versions
        # We need to patch the project root detection
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = load_config()
        assert config.kodi_version == version

    @pytest.mark.parametrize("version", ["kodi22", "invalid", "KODI20", "kodi 20"])
    def test_negative_invalid_versions(self, version, monkeypatch, tmp_path):
        """Invalid KODI_VERSION values cause SystemExit."""
        monkeypatch.setenv("KODI_VERSION", version)
        monkeypatch.setenv("CBILLING_API_URL", "http://example.com")
        monkeypatch.setenv("CBILLING_PUBLIC_KEY", "testkey")

        with pytest.raises(SystemExit):
            load_config()

    def test_negative_empty_string(self, monkeypatch):
        """Empty KODI_VERSION causes SystemExit."""
        monkeypatch.setenv("KODI_VERSION", "")
        monkeypatch.setenv("CBILLING_API_URL", "http://example.com")
        monkeypatch.setenv("CBILLING_PUBLIC_KEY", "testkey")

        with pytest.raises(SystemExit):
            load_config()

    def test_boundary_whitespace_only(self, monkeypatch):
        """Whitespace-only KODI_VERSION causes SystemExit."""
        monkeypatch.setenv("KODI_VERSION", "   ")
        monkeypatch.setenv("CBILLING_API_URL", "http://example.com")
        monkeypatch.setenv("CBILLING_PUBLIC_KEY", "testkey")

        with pytest.raises(SystemExit):
            load_config()

    def test_valid_versions_constant(self):
        """VALID_KODI_VERSIONS contains exactly the three supported versions."""
        assert VALID_KODI_VERSIONS == ("kodi19", "kodi20", "kodi21")


# ===========================================================================
# E2EConfig Loading from Environment
# ===========================================================================


class TestE2EConfigLoading:
    """Test E2EConfig loading from environment variables."""

    def test_positive_all_vars_set(self, monkeypatch):
        """All environment variables set produces correct config."""
        monkeypatch.setenv("KODI_HOST", "192.168.1.100")
        monkeypatch.setenv("KODI_HTTP_PORT", "9080")
        monkeypatch.setenv("KODI_WS_PORT", "9190")
        monkeypatch.setenv("KODI_VERSION", "kodi21")
        monkeypatch.setenv("CBILLING_API_URL", "http://api.example.com")
        monkeypatch.setenv("CBILLING_PUBLIC_KEY", "my_public_key")
        monkeypatch.setenv("E2E_RECORD_VIDEO", "1")
        monkeypatch.setenv("E2E_ARTIFACTS_DIR", "/tmp/artifacts")

        config = load_config()

        assert config.kodi_host == "192.168.1.100"
        assert config.kodi_http_port == 9080
        assert config.kodi_ws_port == 9190
        assert config.kodi_version == "kodi21"
        assert config.cbilling_api_url == "http://api.example.com"
        assert config.cbilling_public_key == "my_public_key"
        assert config.record_video is True
        assert config.artifacts_dir == "/tmp/artifacts"

    def test_positive_defaults_used(self, monkeypatch):
        """Default values are used when env vars are not set and no .env file."""
        # Clear all relevant env vars
        for var in (
            "KODI_HOST",
            "KODI_HTTP_PORT",
            "KODI_WS_PORT",
            "KODI_VERSION",
            "CBILLING_API_URL",
            "CBILLING_PUBLIC_KEY",
            "E2E_RECORD_VIDEO",
            "E2E_ARTIFACTS_DIR",
        ):
            monkeypatch.delenv(var, raising=False)

        # Patch _load_dotenv to return empty dict (no .env fallback)
        monkeypatch.setattr("tests.e2e.config._load_dotenv", lambda path: {})

        config = load_config()

        assert config.kodi_host == "localhost"
        assert config.kodi_http_port == 8080
        assert config.kodi_ws_port == 9090
        assert config.kodi_version == "kodi20"
        assert config.cbilling_api_url == ""
        assert config.cbilling_public_key == ""
        assert config.record_video is False
        assert config.artifacts_dir == "tests/e2e/artifacts"

    def test_negative_missing_required_vars_still_loads(self, monkeypatch):
        """Missing CBILLING vars still loads config (validation is in conftest)."""
        monkeypatch.delenv("CBILLING_API_URL", raising=False)
        monkeypatch.delenv("CBILLING_PUBLIC_KEY", raising=False)
        monkeypatch.setenv("KODI_VERSION", "kodi20")

        # Patch _load_dotenv to return empty dict (no .env fallback)
        monkeypatch.setattr("tests.e2e.config._load_dotenv", lambda path: {})

        # load_config does not fail on missing credentials — that's conftest's job
        config = load_config()
        assert config.cbilling_api_url == ""
        assert config.cbilling_public_key == ""

    def test_boundary_empty_values(self, monkeypatch):
        """Empty string values are accepted (treated as unset for credentials)."""
        monkeypatch.setenv("KODI_HOST", "")
        monkeypatch.setenv("CBILLING_API_URL", "")
        monkeypatch.setenv("CBILLING_PUBLIC_KEY", "")
        monkeypatch.setenv("KODI_VERSION", "kodi20")

        config = load_config()

        # Empty host is accepted (user's responsibility)
        assert config.kodi_host == ""
        assert config.cbilling_api_url == ""
        assert config.cbilling_public_key == ""

    def test_positive_record_video_true_values(self, monkeypatch):
        """Record video is True for '1' and 'true' (case-insensitive)."""
        monkeypatch.setenv("KODI_VERSION", "kodi20")

        monkeypatch.setenv("E2E_RECORD_VIDEO", "1")
        config = load_config()
        assert config.record_video is True

        monkeypatch.setenv("E2E_RECORD_VIDEO", "true")
        config = load_config()
        assert config.record_video is True

        monkeypatch.setenv("E2E_RECORD_VIDEO", "TRUE")
        config = load_config()
        assert config.record_video is True

    def test_positive_record_video_false_values(self, monkeypatch):
        """Record video is False for '0', 'false', and empty string."""
        monkeypatch.setenv("KODI_VERSION", "kodi20")

        monkeypatch.setenv("E2E_RECORD_VIDEO", "0")
        config = load_config()
        assert config.record_video is False

        monkeypatch.setenv("E2E_RECORD_VIDEO", "false")
        config = load_config()
        assert config.record_video is False

        monkeypatch.setenv("E2E_RECORD_VIDEO", "")
        config = load_config()
        assert config.record_video is False
