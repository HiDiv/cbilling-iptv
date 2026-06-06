# SPDX-FileCopyrightText: 2026 HiDiv <hidiv71@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for tests/e2e/utils.py — strip_kodi_tags and strip_labels."""

import os
import sys

# Add tests/e2e/ to sys.path so we can import the utils module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "e2e"))

from utils import strip_kodi_tags, strip_labels  # noqa: I001


# --- strip_kodi_tags: positive cases ---


class TestStripKodiTagsPositive:
    """Positive scenarios: tags are correctly removed."""

    def test_single_bold_tag(self):
        assert strip_kodi_tags("[B]text[/B]") == "text"

    def test_single_italic_tag(self):
        assert strip_kodi_tags("[I]italic[/I]") == "italic"

    def test_color_tag_with_value(self):
        assert strip_kodi_tags("[COLOR white]hello[/COLOR]") == "hello"

    def test_color_tag_hex(self):
        assert strip_kodi_tags("[COLOR FF00FF00]green[/COLOR]") == "green"

    def test_nested_color_and_bold(self):
        assert strip_kodi_tags("[COLOR white][B]text[/B][/COLOR]") == "text"

    def test_nested_color_bold_italic(self):
        result = strip_kodi_tags("[COLOR red][B][I]deep[/I][/B][/COLOR]")
        assert result == "deep"

    def test_uppercase_tag(self):
        assert strip_kodi_tags("[UPPERCASE]upper[/UPPERCASE]") == "upper"

    def test_lowercase_tag(self):
        assert strip_kodi_tags("[LOWERCASE]lower[/LOWERCASE]") == "lower"

    def test_light_tag(self):
        assert strip_kodi_tags("[LIGHT]light[/LIGHT]") == "light"

    def test_cr_tag(self):
        assert strip_kodi_tags("[CR]") == ""

    def test_multiple_tags_in_one_string(self):
        text = "[B]Прямой эфир[/B] — [I]live[/I]"
        assert strip_kodi_tags(text) == "Прямой эфир — live"

    def test_russian_label_bold(self):
        assert strip_kodi_tags("[B]Прямой эфир[/B]") == "Прямой эфир"

    def test_case_insensitive_tags(self):
        assert strip_kodi_tags("[b]text[/b]") == "text"
        assert strip_kodi_tags("[color white]x[/color]") == "x"


# --- strip_kodi_tags: negative cases ---


class TestStripKodiTagsNegative:
    """Negative scenarios: strings without tags remain unchanged."""

    def test_plain_text_unchanged(self):
        assert strip_kodi_tags("Hello World") == "Hello World"

    def test_plain_russian_text(self):
        assert strip_kodi_tags("Прямой эфир") == "Прямой эфир"

    def test_square_brackets_not_tags(self):
        # Regular square brackets that don't match Kodi tag pattern
        assert strip_kodi_tags("[unknown]text[/unknown]") == "[unknown]text[/unknown]"

    def test_numeric_content(self):
        assert strip_kodi_tags("12345") == "12345"


# --- strip_kodi_tags: boundary cases ---


class TestStripKodiTagsBoundary:
    """Boundary scenarios: edge cases."""

    def test_empty_string(self):
        assert strip_kodi_tags("") == ""

    def test_only_tags_no_content(self):
        assert strip_kodi_tags("[B][/B]") == ""

    def test_only_color_tags_no_content(self):
        assert strip_kodi_tags("[COLOR white][/COLOR]") == ""

    def test_unclosed_bold_tag(self):
        # Unclosed tag — opening tag is still removed
        assert strip_kodi_tags("[B]text") == "text"

    def test_unclosed_color_tag(self):
        assert strip_kodi_tags("[COLOR red]text") == "text"

    def test_closing_tag_without_opening(self):
        assert strip_kodi_tags("text[/B]") == "text"

    def test_whitespace_only_after_strip(self):
        # Tags with only whitespace content — strip() removes it
        assert strip_kodi_tags("[B] [/B]") == ""

    def test_multiple_spaces_between_tags(self):
        result = strip_kodi_tags("[B]hello[/B]  [I]world[/I]")
        assert result == "hello  world"


# --- strip_labels ---


class TestStripLabels:
    """Tests for strip_labels helper."""

    def test_basic_list(self):
        items = [
            {"label": "[B]Прямой эфир[/B]"},
            {"label": "[B]Архив[/B]"},
            {"label": "[B]Любимые каналы[/B]"},
            {"label": "[B]Медиатека[/B]"},
        ]
        result = strip_labels(items)
        assert result == ["Прямой эфир", "Архив", "Любимые каналы", "Медиатека"]

    def test_empty_list(self):
        assert strip_labels([]) == []

    def test_items_without_label_key(self):
        items = [{"id": 1}, {"id": 2}]
        result = strip_labels(items)
        assert result == ["", ""]

    def test_mixed_items(self):
        items = [
            {"label": "[COLOR white][B]Live[/B][/COLOR]"},
            {"label": "Plain text"},
            {"label": ""},
        ]
        result = strip_labels(items)
        assert result == ["Live", "Plain text", ""]
