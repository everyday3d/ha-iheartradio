# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.2] - 2026-10-25

### Added
- **📡 Cross-Platform Multi-Speaker Synchronized Broadcasts (`iheartradio.play_group`) (#9)**:
  - If your setup is anything like mine, you've probably got an assortment of speakers from different brands—a Sonos in the living room, a Google Nest in the kitchen, and bench speakers in the workshop. Normal speaker grouping refuses to bridge across brands.
  - Added the **`iheartradio.play_group`** action to break right through that wall: it resolves the live station stream URL once and dispatches stream playback commands concurrently across all target speakers to eliminate sequential network lag.
  - Added **independent per-speaker volume balancing**: you can set a baseline master volume or dial in custom per-speaker volume levels (`volumes`) so loud machines in the garage don't force you to blast the kitchen.
- **🛑 Single-Touch Whole-House Shutoff (`iheartradio.stop_group`) (#9)**:
  - Added the **`iheartradio.stop_group`** action to stop or pause playback across all active group speakers in one click without having to specify individual entity IDs in your automations.
- **🎨 Multi-Room Material Design Icons (`icons.json`) (#9)**:
  - Added official action icons for multi-speaker broadcast: `mdi:speaker-multiple` for `play_group` and `mdi:speaker-off` for `stop_group`.

### Improvements & Hardening
- **⚙️ Frenck Architectural Standards Compliance (#9)**:
  - Guarded all service registrations for clean hot-reloads in daemon memory.
  - Added strict target validation ensuring all targets are verified `media_player.*` entities active in Home Assistant.
  - Added clean lifecycle unload in `async_unload_entry` (Rule 14.8) removing all registered services, canceling background tasks, and purging group tracking state when the integration is unloaded.

## [1.0.1] - 2026-10-25

### Added
- **🌙 Smooth Volume Fades & Sleep Timers (`iheartradio.fade_out`, `iheartradio.sleep_timer`, `iheartradio.cancel_fade`)**:
  - Out in my workshop and around the house, I got tired of building complicated repeat loops and delays in Home Assistant automations just to gently wind down the music at the end of the day or set a bedtime timer.
  - Added the **`iheartradio.fade_out`** action so you can smoothly lower or raise speaker volume over 1 to 1800 seconds, with your choice of a standard linear fade or a natural perceptual logarithmic fade, plus an option to automatically pause playback once it reaches zero.
  - Added the **`iheartradio.sleep_timer`** action to set a 1 to 240 minute countdown that automatically fades the volume down during the final seconds before pausing or stopping the speaker.
  - Added the **`iheartradio.cancel_fade`** action so you can instantly cancel any active fade or sleep timer on a speaker without messing with what is currently playing.
- **🎨 Material Design Action Icons (`icons.json`)**:
  - Added an official `icons.json` mapping so all iHeartRadio actions show crisp, recognizable icons (`mdi:radio`, `mdi:volume-minus`, `mdi:sleep`, and `mdi:close-circle-outline`) in Home Assistant's Automation Editor, Action Picker, and Developer Tools.

### Improvements & Hardening
- **⚙️ Core-Standard Service Architecture**:
  - Updated `services.yaml` to move target speaker definitions up to top-level `target:` blocks, matching Home Assistant Core media player services so you can easily target entities, devices, or areas with the native UI picker.
  - Added strict speaker entity whitelisting so actions only send commands to validated `media_player` entities that are active in Home Assistant.
  - Added clean background task management that safely tracks running fade and sleep tasks, stops conflicting tasks on the same speaker, and cancels all active timers cleanly if the integration is reloaded or removed so nothing ever hangs.
- **⚖️ Legal & Trademark Disclaimers**:
  - Added clear trademark, product name, and logo ownership disclaimers to the repository README and Wiki.
- **🧹 Cleaned Deployment Files**:
  - Cleaned internal deployment scripts out of the repository tree and permanently ignored the scripts folder in `.gitignore`.

### Added
- **Nationwide US Markets Directory & Dynamic Market Picker (#7)**:
  - Expanded catalog to all **274 official US radio markets** across all 50 states + DC, PR, and National/Digital.
  - Added dynamic nationwide **Market Selector dropdown** to `iheartradio-card.js` with grouped states (`<optgroup>`), allowing instant switching to any of the 274 US markets.
  - Added state-by-state media browsing hierarchy (`🇺🇸 Browse Markets by State`) in `media_source.py` covering all 52 states and regions with market counts.
  - Updated `config_flow.py` and options flow to support selecting any of the 274 US markets as the user's default local market.
  - Enhanced WebSocket API command `iheartradio/markets` to return nationwide market metadata (`id`, `name`, `city`, `state`).
  - Added legacy market ID migrations for updated official metro endpoints (Los Angeles `21`, Dallas `218`, Houston `220`, Philadelphia `196`, Miami `50`, Denver `37`, San Diego `27`, San Francisco `28`, Tampa `58`, Minneapolis `116`, Baltimore `102`, Charlotte `130`, Pittsburgh `197`).
- **Worcester, MA Market & Regional Station Expansion (#6)**:
  - Added Worcester, MA (`marketId: "101"`) featuring **104.5 WXLO** (`id: 5380`), 96.1 WSRS, and Central Massachusetts stations.
  - Added Worcester category pill (`📻 Worcester`) to `iheartradio-card.js`.
  - Added Worcester to `POPULAR_MARKETS` for setup/options flow and Media Browser directories.
  - Added regional market expansion bridge linking Worcester stations into Greater Boston (`marketId: "99"`), expanding the Boston station catalog to 40 stations including 104.5 WXLO.

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
