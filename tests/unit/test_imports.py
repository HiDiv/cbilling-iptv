# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for import compatibility (Python 3.8+).

Migrated from: test_imports.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


def test_import_urllib3():
    import urllib3

    assert hasattr(urllib3, "__version__")


def test_import_requests():
    import requests

    assert hasattr(requests, "__version__")


def test_import_charset_normalizer():
    import charset_normalizer

    assert hasattr(charset_normalizer, "__version__")


def test_import_api_client():
    from api_client import CbillingAPI

    assert CbillingAPI is not None


def test_import_api_adapter():
    from api_adapter import ApiAdapter

    assert ApiAdapter is not None


def test_import_utils():
    import utils

    assert utils is not None


def test_import_vod_cache():
    import vod_cache

    assert vod_cache is not None
