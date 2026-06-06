# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.0.x-dev | ✅ Active development |
| 1X.x.x | ❌ No longer supported |
| < 1X.0.0 | ❌ No longer supported |

Only the latest development version receives security updates. Older versions based on the Stalker Portal API are no longer maintained.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, send an email to: **hidiv71@gmail.com**

Please include:

- A description of the vulnerability
- Steps to reproduce the issue
- The affected version(s)
- Any potential impact assessment

### What to Expect

- You will receive an acknowledgment within **72 hours**.
- The maintainer will investigate and provide an update within **7 days**.
- If the vulnerability is confirmed, a fix will be developed and released as soon as possible.
- You will be credited in the release notes (unless you prefer to remain anonymous).

## Scope

This security policy covers:

- The addon source code (`default.py`, `service.py`, `resources/lib/`)
- Configuration handling (API keys, settings)
- Data storage (SQLite databases, favorites, cache files)

This policy does **not** cover:

- The Cbilling.TV API service itself
- Kodi platform vulnerabilities
- Third-party vendored libraries (report those to their upstream maintainers)

## Best Practices for Users

- Keep your Kodi installation up to date.
- Do not share your Public Key with others.
- Do not commit `.env` files containing API credentials to version control.
- Review addon permissions before installation.
