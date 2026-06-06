# Cbilling.TV IPTV — Kodi Addon

[![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-blue.svg)](LICENSE.txt)
[![Kodi: 19+](https://img.shields.io/badge/kodi-19%2B-blue.svg)](https://kodi.tv/)
[![Python: 3.8+](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org/)

🇷🇺 [Версия на русском](README.ru.md)

A Kodi video addon for watching IPTV channels and VOD content from the [Cbilling.TV](https://cbilling.tv) service. Requires a valid Cbilling.TV subscription.

## Features

- **Live TV** — watch IPTV channels with EPG overlay
- **Archive** — access recorded broadcasts (up to 7 days)
- **EPG** — electronic program guide with local SQLite cache
- **VOD** — movie and series library with metadata preloading
- **Favorites** — save and manage favorite channels locally
- **Search** — search across VOD content

## Requirements

- **Kodi 19+** (Matrix, Nexus, or Omega)
- **Python 3.8+** (bundled with Kodi 19+)
- Active [Cbilling.TV](https://cbilling.tv) subscription
- Public Key from your Cbilling.TV account

## Installation

1. Download the latest release ZIP from the [Releases](https://github.com/HiDiv/cbilling-iptv/releases) page (or build from source using `build_addon.py`).
2. In Kodi, go to **Settings → Add-ons → Install from zip file**.
3. Select the downloaded `plugin.video.cbilling.iptv-<version>.zip`.
4. Wait for the installation confirmation.

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

## Configuration

1. Go to **Add-ons → Video add-ons → Cbilling.TV IPTV**.
2. Right-click → **Settings**.
3. Enter your **Public Key** from the Cbilling.TV dashboard.
4. (Optional) Select a preferred stream server or leave on auto.

## Project Structure

```
plugin.video.cbilling.iptv/
├── default.py              # Addon entry point
├── service.py              # Background service (EPG cron)
├── resources/
│   ├── lib/
│   │   ├── api_client.py   # REST API client
│   │   ├── api_adapter.py  # Data adapter layer
│   │   ├── body.py         # Main UI logic
│   │   ├── vod_cache.py    # VOD metadata cache
│   │   ├── cron.py         # Cron scheduler
│   │   └── utils.py        # Utilities
│   ├── settings.xml        # Addon settings definition
│   └── language/            # Localization strings
├── tests/                   # pytest test suite
└── addon.xml               # Kodi addon metadata
```

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on coding standards, branch naming, commit messages, and the pull request process.

## License

This project is licensed under **AGPL-3.0-only**. See [LICENSE.txt](LICENSE.txt) for the full license text.

## Disclaimer

### No Warranty

This addon is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement. The authors make no guarantees regarding the addon's reliability, availability, or error-free operation.

### Limitation of Liability

In no event shall the authors be liable for any data loss (including but not limited to favorites, watch history, bookmarks, and settings), data corruption during addon updates or reinstallation, or any direct, indirect, incidental, special, or consequential damages arising from the use of or inability to use this addon. Users are advised to back up their data regularly.

### Content Responsibility

This addon does not host, store, or provide any media content. It acts solely as an interface to third-party IPTV services that require a valid user subscription. Users are responsible for ensuring that their use of this addon and any accessed content complies with all applicable laws in their jurisdiction. This addon has no affiliation with any content provider.

See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer in English and Russian.

## Links

- **Forum:** <https://clck.ru/KcXML>
- **Issues:** [GitHub Issues](https://github.com/HiDiv/cbilling-iptv/issues)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- **Security:** [SECURITY.md](SECURITY.md)
