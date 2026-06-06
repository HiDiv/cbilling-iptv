# Developer Notes

Technical notes on known issues and platform limitations that affect this addon.

## Kodi Matrix: Cyrillic Filter Case-Insensitivity Bug

**Status:** Won't Fix (Kodi platform limitation)
**Discovered:** 2026-03-07
**Affects:** Kodi 19.x (Matrix) with Python 3.8

### Summary

The built-in list filter in Kodi Matrix does not perform case-insensitive matching for Cyrillic characters. This is an architectural bug in Kodi's C++ code that cannot be fixed on the addon side.

### Symptoms

- Filtering with uppercase Cyrillic (e.g. typing `НТВ`) correctly finds channels like `НТВ HD`.
- Filtering with lowercase Cyrillic (e.g. typing `нтв`) does **not** find `НТВ HD`.
- Latin characters work correctly: `hbo` finds `HBO`.

### Root Cause

Three functions in Kodi's C++ source are responsible:

1. **`StringUtils::ToLower(std::string)`** in `StringUtils.cpp` uses `::tolower` from C, which operates byte-by-byte. UTF-8 Cyrillic characters are two-byte sequences (e.g. `Н` = `0xD0 0x9D`, `н` = `0xD0 0xBD`), so byte-level `tolower` produces incorrect results.

2. **`StringUtils::FindWords()`** only handles ASCII A-Z for case conversion. Cyrillic code points (`0xD0xx`-`0xD1xx`) are ignored entirely.

3. **`IsUTF8Letter()`** recognizes Latin-1 and Latin Extended ranges but does not recognize Cyrillic (`0xD0`-`0xD1`) as letters at all.

Kodi has a `tolowerUnicode()` for `wchar_t`, but the filter path uses `std::string` (raw UTF-8 bytes), so the Unicode-aware function is never called.

### Workarounds Investigated

| Approach | Result |
|----------|--------|
| System locale `ru_RU.UTF-8` | No effect — `::tolower` still works byte-by-byte |
| `sorttitle` info label | Only affects sorting, not filtering |
| `label2` / `setProperty` | Not used by Kodi's filter mechanism |
| Lowercase labels | Works but degrades visual appearance |

### Recommendation

Accept the limitation and document it for users. The addon correctly passes clean UTF-8 strings as labels. A fix requires changes to Kodi's C++ `StringUtils` to use ICU or `wchar_t` conversion for the filter path.

This may be resolved in Kodi 20 (Nexus) or later. Testing on newer Kodi versions is recommended.

### References

- [GUIMediaWindow.cpp (Matrix branch)](https://github.com/xbmc/xbmc/blob/Matrix/xbmc/windows/GUIMediaWindow.cpp)
- [StringUtils.cpp (Matrix branch)](https://github.com/xbmc/xbmc/blob/Matrix/xbmc/utils/StringUtils.cpp)
