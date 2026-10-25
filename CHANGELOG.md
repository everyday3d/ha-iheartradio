# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-25

### Added
- **📻 Native Media Source (`media_source.py`)**:
  - Full integration with Home Assistant's Media Browser sidebar.
  - Browse live radio stations by local market/city, top genres/formats, digital exclusives, and favorites.
  - Automatic station resolution returning direct HTTPS stream URLs and MIME types (`audio/aac`, `audio/mpeg`, or `application/x-mpegurl`).
- **🗺️ Major US Markets Directory**:
  - Preconfigured quick access to top US radio markets including New York, Los Angeles, Chicago, Dallas, Houston, Atlanta, Philadelphia, Phoenix, Boston, Miami, Seattle, San Francisco, Denver, and more.
- **🎸 Popular Genre & Format Browsing**:
  - Organized stations across Top 40 & Pop, Classic Rock, Country, Hip Hop & R&B, News & Talk, Sports Radio, 80s & 90s Hits, and Jazz.
- **⚡ Dual Stream Delivery**:
  - Direct Shoutcast/AAC/MP3 streaming for minimal playback latency and high compatibility on Sonos, Google Cast, and ESP32 speakers.
  - HLS (`.m3u8`) streaming option for variable bandwidth environments.
- **🎯 `iheartradio.play_station` Automation Action**:
  - Dedicated Home Assistant action to play any station on one or more `media_player` entities by station name, call letters, or numeric ID.
  - Built-in validation verifying target entity domain and availability before dispatching playback.
- **🎛️ Custom Lovelace Radio Player Card (`iheartradio-card`)**:
  - Dedicated dashboard card registered via `async_register_static_paths` and `add_extra_js_url` without manual `/config/www` setup.
  - Live station search querying backend via authenticated WebSocket API (`iheartradio/search`).
  - Speaker selector dropdown querying all `media_player` entities, with active state indicators and `localStorage` persistence.
  - Horizontal category pill strip with mouse wheel delta translation, active touch/scroll gesture freeze (1400ms debounce), and scroll position preservation across re-renders (zero jump-back).
  - Real-time Now Playing bar with Play/Pause and Stop controls.
  - Strict HTML sanitization via `escapeHtml()` across all dynamic station names, calls, frequencies, descriptions, and entity names.
- **🛡️ Full HACS & HA Core Standards Compliance**:
  - Zero blocking file I/O in the async loop (`async_get_integration`).
  - Managed async HTTP sessions via `aiohttp_client.async_get_clientsession(hass)`.
  - Circuit-breaker error reporting using Home Assistant's Issue Registry (`async_create_issue` / `async_delete_issue`).
  - Clean lifecycle unloading (`async_unload_entry`).

### Fixed
- **Boston & US Major Market ID Alignment (#5)**:
  - Corrected Boston, MA market ID from `137` (0 stations) to official iHeartRadio market ID `99` (34 stations including Kiss 108, 100.7 WZLX, WBZ NewsRadio 1030, JAM'N 94.5).
  - Verified and corrected market IDs across all 32 major US markets (Atlanta `61`, Chicago `84`, Austin `214`, Detroit `111`, Las Vegas `152`, Phoenix `14`, Portland `192`, San Antonio `226`, St. Louis `119`, Seattle `245`, Washington DC `42`, Orlando `51`, etc.) so every city directory displays 10–45 live stations.
  - Added Boston quick-select pill to `iheartradio-card.js`.
- **Config Flow Load Failure / Invalid Handler (#4)**:
  - Removed invalid `Platform.MEDIA_SOURCE` reference in `custom_components/iheartradio/__init__.py`. `media_source` is an integration-level component auto-loaded via `async_get_media_source` rather than an entity platform enum, eliminating the `AttributeError: type object 'EntityPlatforms' has no attribute 'MEDIA_SOURCE'` that broke config flow registration.
- **CI Dependency & Private Repository CI Notice (#3)**:
  - Added missing `http` component dependency to `manifest.json` resolving Hassfest validation error.
  - Configured `validate-hacs` workflow to skip gracefully with a notice while the repository is private (HACS action only validates public repositories).
