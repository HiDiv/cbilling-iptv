# Build Package Verification Rule

## CRITICALLY IMPORTANT

**ALWAYS verify the contents of the built ZIP after running `build_addon.py`.**

## After Every Build

Run:
```bash
python3 build_addon.py
```

Then immediately verify:
```bash
# Check nothing unwanted got in:
unzip -l dist/plugin.video.cbilling.iptv-*.zip | grep -E "tests/|dev/|\.pytest|\.ruff|\.coverage|pyproject|Makefile|\.kiro|\.env|__pycache__|\.git"

# The command above should produce ZERO output.
# If anything matches — the build script has a bug.
```

## What MUST be in the package

- `addon.xml` — addon metadata
- `default.py` — entry point
- `service.py` — cron service
- `icon.png` — addon icon
- `LICENSE.txt` — license
- `changelog.txt` — changelog (Kodi shows it on update)
- `fanart/` — background art and posters
- `resources/settings.xml` — settings UI definition
- `resources/language/` — localization strings
- `resources/lib/` — all addon Python modules
- `resources/lib/vendor/` — vendored third-party libraries
- `resources/*.png` — UI thumbnails

## What MUST NOT be in the package

- `tests/` — test files
- `dev/` — development Docker environment
- `.kiro/` — IDE configuration
- `.vscode/` — IDE configuration
- `.git/` — version control
- `.venv/`, `venv/` — virtual environment
- `.pytest_cache/`, `.ruff_cache/` — tool caches
- `.coverage` — coverage data
- `pyproject.toml` — dev tooling config
- `Makefile` — dev automation
- `build_addon.py` — build script itself
- `.env`, `.env.example` — secrets and config
- `*.md` — documentation
- `docs/` — documentation directory
- `dist/` — output directory
- `__pycache__/` — bytecode

## Size Check

The addon ZIP should be approximately 2.5–3.0 MB. If it's significantly larger (>3.5 MB), something unwanted likely got included.

## When to Verify

- After modifying `build_addon.py`
- After adding new directories or file types to the project
- Before committing a release build
- After any refactoring that adds/removes directories

Last updated: 2026-06-12
