# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Utility functions for e2e tests.

Provides helpers for stripping Kodi formatting tags from UI labels
before comparison in test assertions.
"""

import re
from typing import List

# Pattern matches [COLOR xxx], [/COLOR], [B], [/B], [I], [/I], etc.
_KODI_TAG_PATTERN = re.compile(
    r"\[/?(?:COLOR|B|I|UPPERCASE|LOWERCASE|LIGHT|CR)(?:\s[^\]]*?)?\]",
    re.IGNORECASE,
)


def strip_kodi_tags(text: str) -> str:
    """Remove Kodi formatting tags from a label string.

    Examples:
        >>> strip_kodi_tags("[COLOR white][B]Live[/B][/COLOR]")
        'Live'
        >>> strip_kodi_tags("[B]Прямой эфир[/B]")
        'Прямой эфир'
    """
    return _KODI_TAG_PATTERN.sub("", text).strip()


def strip_labels(items: List[dict]) -> List[str]:
    """Extract and strip labels from a list of container items."""
    return [strip_kodi_tags(item.get("label", "")) for item in items]
