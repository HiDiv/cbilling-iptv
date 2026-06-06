# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for logging style consistency in body.py.

Migrated from: test_logging_style.py
"""

import os
import re


def _read_body():
    body_path = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "resources", "lib", "body.py")
    with open(body_path, encoding="utf-8") as f:
        return f.read()


_OLD_STYLE_PATTERNS = [
    (r'xbmc\.log\(["\'](?!.*\[Cbilling\])', "Missing [Cbilling] prefix"),
    (r'xbmc\.log\(["\']THAM', "Old THAM prefix found"),
]


def test_no_old_style_logging():
    """All xbmc.log() calls should use the [Cbilling] prefix."""
    content = _read_body()
    lines = content.split("\n")
    issues = []
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for pattern, description in _OLD_STYLE_PATTERNS:
            if re.search(pattern, line):
                issues.append("Line %d: %s — %s" % (i, description, line.strip()))
    assert not issues, "Logging style issues found:\n" + "\n".join(issues)


def test_debug_log_calls_exist():
    """body.py should contain debug_log() calls."""
    content = _read_body()
    calls = re.findall(r"debug_log\(", content)
    assert len(calls) > 0, "Expected debug_log() calls in body.py"
