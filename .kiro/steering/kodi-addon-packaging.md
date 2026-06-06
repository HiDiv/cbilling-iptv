---
description: Kodi addon packaging rules — ZIP structure, addon.xml, build process
inclusion: auto
fileMatchPattern: "addon.xml|build_addon.py"
---

# Kodi Addon Packaging Rules

## ZIP Package Structure

**CRITICAL**: ZIP must contain addon folder with addon ID as name!

```
plugin.video.cbilling.iptv-2.0.1-dev.zip
└── plugin.video.cbilling.iptv/
    ├── addon.xml
    ├── default.py
    ├── icon.png
    ├── LICENSE.txt
    └── resources/
```

## Version Format
- Production: `2.0.1`
- Development: `2.0.1-dev`

## Files to Exclude
- .git/, venv/, __pycache__/
- Test files, dev scripts, *.md docs
- .env, JSON test files, IDE configs

## Build Command
```bash
python build_addon.py
```

## Installation in Kodi
1. Settings → Add-ons → Install from zip
2. Select ZIP file

---
Last updated: 2025-02-17
