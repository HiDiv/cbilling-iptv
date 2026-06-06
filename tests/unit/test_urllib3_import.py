# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for urllib3 import compatibility with Python 3.8.

Migrated from: test_urllib3_import.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "vendor"))


def test_urllib3_import():
    import urllib3

    assert hasattr(urllib3, "__version__")


def test_urllib3_pool_manager():
    from urllib3 import PoolManager

    http = PoolManager()
    assert http is not None
