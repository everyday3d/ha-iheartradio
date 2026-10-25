# 📻 iHeartRadio for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/everyday3d/ha-iheartradio?style=flat-square&color=crimson)](https://github.com/everyday3d/ha-iheartradio/releases)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

Hey everyone! Jimmy here from BoxerDawg 3D / Everyday3D. I built this integration so I could easily stream my favorite live radio stations (like Z100, Lite FM, and sports talk) across all the smart speakers in my workshop and home directly through Home Assistant's native Media Browser—without needing an account, subscription, or complex setup.

With this integration, you get thousands of live local AM/FM stations and digital streams directly in Home Assistant, ready to cast or play on any `media_player` entity (Sonos, Google Nest / Chromecast, ESP32 audio players, DLNA, or browser).

---

## 🌟 What It Does

- **📻 Native Media Browser Support**: Shows up directly inside Home Assistant's Media Browser sidebar. Browse stations by your local city, explore genres, or pick from your saved favorites.
- **🎛️ Custom Lovelace Radio Card (`iheartradio-card`)**: A sleek, dedicated dashboard card with live station search, category pills, speaker picker dropdown, and real-time Now Playing controls. Automatically registered and served without copying files to `/config/www`.
- **🗺️ Major Market & City Directory**: Easily browse stations in New York, Los Angeles, Chicago, Dallas, Atlanta, Boston, Phoenix, Miami, and dozens of other cities.
- **🎸 Genre & Format Categories**: Quick access to Classic Rock, Top 40 & Pop, Country, Hip Hop & R&B, News & Talk, Sports Radio, 80s & 90s Hits, and more.
- **⚡ Two Stream Modes**:
  - **Direct Stream (Default)**: Clean, high-compatibility AAC/MP3 stream with virtually instant start times. Works great on Sonos, Google Cast, and ESP32 players.
  - **HLS Stream**: Adaptive bitrate stream for networks where variable bandwidth handling is preferred.
- **🎯 1-Click Automation Service (`iheartradio.play_station`)**: Trigger any station in your automations by simply typing the name (e.g. `Z100`), call letters (e.g. `WHTZ-FM`), or station ID.
- **🛡️ 100% Free & No Account Needed**: Connects directly to public catalog endpoints without tracking tokens or logins.

---

## 🚀 Installation

### Option 1: HACS (Recommended)
1. Open **HACS** in your Home Assistant sidebar.
2. Click the three dots in the top right corner and choose **Custom repositories**.
3. Paste `https://github.com/everyday3d/ha-iheartradio` in the Repository field.
4. Set the Category to **Integration** and click **Add**.
5. Find **iHeartRadio** in your HACS list and click **Download**.
6. Restart Home Assistant.

### Option 2: Manual Installation
1. Download the latest release from the [Releases](https://github.com/everyday3d/ha-iheartradio/releases) page.
2. Copy the `custom_components/iheartradio` folder into your Home Assistant's `config/custom_components/` directory.
3. Restart Home Assistant.

---

## ⚙️ Setup & Configuration

1. In Home Assistant, head over to **Settings** ➔ **Devices & Services**.
2. Click **Add Integration** in the bottom right corner.
3. Search for **iHeartRadio** and click on it.
4. Choose your primary city/market and your stream format preference (Direct Stream or HLS).
5. Click **Submit**. That's it!

> [!TIP]
> You can re-open the integration settings anytime by clicking **Configure** on the iHeartRadio card to change your default city or paste in your favorite station IDs!

---

## 🎵 How to Play Music

### 1. Dedicated Dashboard Card (`iheartradio-card`)
Add the custom card to your dashboard via the Lovelace UI ("Add Card" ➔ search for **iHeartRadio Player Card**), or use YAML:

```yaml
type: custom:iheartradio-card
title: "Workshop Radio"
default_player: media_player.workshop_speaker
```

Features included on the card:
- **Speaker Selector**: Switch playback between any smart speaker in your home.
- **Fast Live Search**: Filter thousands of stations by call letters, city, or name with debounced instant search.
- **Category & Market Pills**: Smooth horizontal scrolling across popular genres and major cities with zero jump-back.
- **Now Playing Strip**: Live stream metadata and instant Play / Pause / Stop controls.

### 2. In the Media Browser
Click **Media** in the Home Assistant sidebar, choose **iHeartRadio**, pick your city or genre, click any station, and pick which speaker you want it to play on!

### 2. In Automations & Scripts
Use the `iheartradio.play_station` action in your automations:

```yaml
alias: "Morning Workshop Radio"
trigger:
  - platform: time
    at: "08:00:00"
action:
  - action: iheartradio.play_station
    target:
      entity_id: media_player.workshop_speaker
    data:
      station: "Z100"
```

You can also use call letters or numeric station IDs:
```yaml
action: iheartradio.play_station
target:
  entity_id: media_player.living_room_sonos
data:
  station: "WLTW-FM"
```

---

## 🤝 Community & Feedback

If you have an idea, run into a bug, or want a new city added to the quick-pick list, feel free to open an issue or drop a discussion thread on [GitHub Issues](https://github.com/everyday3d/ha-iheartradio/issues). Happy listening and happy making!

---

## ⚖️ Trademark & Legal Notice

This is an independent, free, and open-source project created for the Home Assistant and maker communities. It is not affiliated with, sponsored by, or endorsed by iHeartMedia, Inc. or any of its subsidiaries.

All product names, logos, station call letters, audio streams, trademarks, and registered trademarks (including "iHeart", "iHeartRadio", and individual broadcast station marks) are the property of their respective owners. Their inclusion in this integration and its documentation is strictly for identification, directory discovery, and interoperability purposes.
