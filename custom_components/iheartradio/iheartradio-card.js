/**
 * iHeartRadio Custom Lovelace Card
 * https://github.com/everyday3d/ha-iheartradio
 */

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

class IHeartRadioCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};

    // State
    this._stations = [];
    this._markets = [];
    this._marketsLoaded = false;
    this._loading = false;
    this._selectedCategory = "local"; // "local", "favorites", "genre:<id>", "market:<id>"
    this._searchQuery = "";
    this._searchTimeout = null;
    this._selectedPlayer = localStorage.getItem("iheartradio_selected_player") || "";
    this._availablePlayers = [];

    // Gestural freeze & scroll preservation state (Zero Jump-Back Rule)
    this._scrollPositions = {
      pills: 0,
      grid: 0,
    };
    this._isInteracting = false;
    this._interactionTimer = null;
    this._lastRenderTime = 0;
  }

  setConfig(config) {
    this._config = {
      title: config.title || "iHeartRadio",
      default_player: config.default_player || "",
      columns: config.columns || 3,
      ...config,
    };
    if (!this._selectedPlayer && this._config.default_player) {
      this._selectedPlayer = this._config.default_player;
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._updateAvailablePlayers();

    // Inhibit background DOM re-renders while user is actively scrolling or typing
    if (this._isInteracting) {
      return;
    }

    // Limit re-renders to avoid thrashing on rapid entity telemetry updates
    const now = Date.now();
    if (now - this._lastRenderTime < 400 && this.shadowRoot.innerHTML !== "") {
      this._updateNowPlayingOnly();
      return;
    }
    this._lastRenderTime = now;

    if (!this._hasInitialLoad) {
      this._hasInitialLoad = true;
      this._loadCategoryStations("local");
      this._loadMarkets();
    } else {
      if (!this._marketsLoaded) {
        this._loadMarkets();
      }
      this._render();
    }
  }

  async _loadMarkets() {
    if (!this._hass || this._marketsLoaded) return;
    try {
      const resp = await this._hass.callWS({ type: "iheartradio/markets" });
      if (resp && resp.markets) {
        this._markets = resp.markets;
        this._marketsLoaded = true;
        this._render();
      }
    } catch (err) {
      console.debug("[iHeartRadio Card] Failed to load markets list:", err);
    }
  }

  _markInteraction() {
    this._isInteracting = true;
    if (this._interactionTimer) clearTimeout(this._interactionTimer);
    this._interactionTimer = setTimeout(() => {
      this._isInteracting = false;
    }, 1400);
  }

  _saveScrollPositions() {
    const pills = this.shadowRoot.querySelector(".category-pills");
    if (pills) this._scrollPositions.pills = pills.scrollLeft;

    const grid = this.shadowRoot.querySelector(".stations-scroll-box");
    if (grid) this._scrollPositions.grid = grid.scrollTop;
  }

  _restoreScrollPositions() {
    const pills = this.shadowRoot.querySelector(".category-pills");
    if (pills && this._scrollPositions.pills > 0) {
      pills.scrollLeft = this._scrollPositions.pills;
    }

    const grid = this.shadowRoot.querySelector(".stations-scroll-box");
    if (grid && this._scrollPositions.grid > 0) {
      grid.scrollTop = this._scrollPositions.grid;
    }
  }

  _updateAvailablePlayers() {
    if (!this._hass) return;
    const players = [];
    for (const [entityId, stateObj] of Object.entries(this._hass.states)) {
      if (entityId.startsWith("media_player.")) {
        players.push({
          entity_id: entityId,
          name: stateObj.attributes.friendly_name || entityId,
          state: stateObj.state,
        });
      }
    }
    players.sort((a, b) => a.name.localeCompare(b.name));
    this._availablePlayers = players;

    // Pick first available player if none selected
    if (!this._selectedPlayer && players.length > 0) {
      this._selectedPlayer = players[0].entity_id;
    }
  }

  async _loadCategoryStations(category) {
    if (!this._hass) return;
    this._loading = true;
    this._selectedCategory = category;
    this._render();

    try {
      let resp;
      if (category === "local") {
        resp = await this._hass.callWS({ type: "iheartradio/stations" });
      } else if (category.startsWith("genre:")) {
        const genreId = parseInt(category.replace("genre:", ""), 10);
        resp = await this._hass.callWS({ type: "iheartradio/stations", genre_id: genreId });
      } else if (category.startsWith("market:")) {
        const marketId = category.replace("market:", "");
        resp = await this._hass.callWS({ type: "iheartradio/stations", market_id: marketId });
      }
      this._stations = (resp && resp.stations) ? resp.stations : [];
    } catch (err) {
      console.error("[iHeartRadio Card] Failed to load stations:", err);
      this._stations = [];
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _performSearch(query) {
    if (!this._hass || !query.trim()) {
      this._loadCategoryStations(this._selectedCategory || "local");
      return;
    }
    this._loading = true;
    this._render();

    try {
      const resp = await this._hass.callWS({
        type: "iheartradio/search",
        query: query.trim(),
        limit: 30,
      });
      this._stations = (resp && resp.stations) ? resp.stations : [];
    } catch (err) {
      console.error("[iHeartRadio Card] Search failed:", err);
      this._stations = [];
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _playStation(stationId) {
    if (!this._hass || !this._selectedPlayer) {
      alert("Please select a target media player first!");
      return;
    }
    try {
      await this._hass.callService("iheartradio", "play_station", {
        entity_id: this._selectedPlayer,
        station: String(stationId),
      });
    } catch (err) {
      console.error("[iHeartRadio Card] Play station failed:", err);
    }
  }

  _updateNowPlayingOnly() {
    const bar = this.shadowRoot.querySelector(".now-playing-bar");
    if (!bar) return;
    const playerObj = this._selectedPlayer ? this._hass.states[this._selectedPlayer] : null;
    if (!playerObj) {
      bar.style.display = "none";
      return;
    }
    const isPlaying = playerObj.state === "playing";
    const title = playerObj.attributes.media_title || playerObj.attributes.media_station || "Radio Stream";
    const artist = playerObj.attributes.media_artist || playerObj.attributes.media_channel || "";

    const titleEl = bar.querySelector(".np-title");
    const artistEl = bar.querySelector(".np-artist");
    const playBtn = bar.querySelector(".np-btn-play");

    if (titleEl) titleEl.textContent = title;
    if (artistEl) artistEl.textContent = artist;
    if (playBtn) playBtn.innerHTML = isPlaying ? "⏸" : "▶";
    bar.style.display = isPlaying || playerObj.state === "paused" ? "flex" : "none";
  }

  _renderMarketOptions() {
    if (!this._markets || this._markets.length === 0) return "";
    const byState = {};
    for (const m of this._markets) {
      const st = m.state || "US";
      if (!byState[st]) byState[st] = [];
      byState[st].push(m);
    }
    const sortedStates = Object.keys(byState).sort();
    return sortedStates.map((st) => {
      const stateMarkets = byState[st];
      const opts = stateMarkets.map((m) => {
        const isSel = this._selectedCategory === `market:${m.id}`;
        return `<option value="${escapeHtml(m.id)}" ${isSel ? "selected" : ""}>${escapeHtml(m.name)}</option>`;
      }).join("");
      return `<optgroup label="${escapeHtml(st)}">${opts}</optgroup>`;
    }).join("");
  }

  _render() {
    this._saveScrollPositions();

    const title = escapeHtml(this._config.title || "iHeartRadio");
    const playerObj = this._selectedPlayer ? this._hass.states[this._selectedPlayer] : null;
    const isPlaying = playerObj && playerObj.state === "playing";
    const npTitle = playerObj ? escapeHtml(playerObj.attributes.media_title || playerObj.attributes.media_station || "Radio Stream") : "";
    const npArtist = playerObj ? escapeHtml(playerObj.attributes.media_artist || playerObj.attributes.media_channel || "") : "";

    const categories = [
      { id: "local", label: "📍 Local Stations" },
      { id: "market:99", label: "🦞 Boston" },
      { id: "market:101", label: "📻 Worcester" },
      { id: "market:159", label: "🗽 New York" },
      { id: "market:21", label: "🌴 Los Angeles" },
      { id: "market:84", label: "🌆 Chicago" },
      { id: "market:61", label: "🍑 Atlanta" },
      { id: "market:218", label: "⭐ Dallas" },
      { id: "market:220", label: "🚀 Houston" },
      { id: "market:196", label: "🔔 Philadelphia" },
      { id: "market:42", label: "🏛️ Washington DC" },
      { id: "market:245", label: "☕ Seattle" },
      { id: "market:50", label: "🌴 Miami" },
      { id: "market:37", label: "🏔️ Denver" },
      { id: "market:28", label: "🌉 San Francisco" },
      { id: "market:152", label: "🎰 Las Vegas" },
      { id: "market:210", label: "🎸 Nashville" },
      { id: "market:214", label: "🤠 Austin" },
      { id: "market:14", label: "☀️ Phoenix" },
      { id: "genre:16", label: "🔥 Top 40 & Pop" },
      { id: "genre:2", label: "🎸 Classic Rock" },
      { id: "genre:4", label: "🤠 Country" },
      { id: "genre:8", label: "🎤 Hip Hop & R&B" },
      { id: "genre:14", label: "📰 News & Talk" },
      { id: "genre:17", label: "🏈 Sports Radio" },
      { id: "genre:11", label: "📼 80s & 90s Hits" },
      { id: "genre:10", label: "🎷 Jazz & Blues" },
      { id: "market:575", label: "🌐 Digital Exclusives" },
    ];

    if (this._selectedCategory && this._selectedCategory.startsWith("market:")) {
      const mid = this._selectedCategory.replace("market:", "");
      const exists = categories.some((c) => c.id === this._selectedCategory);
      if (!exists) {
        const found = this._markets.find((m) => String(m.id) === String(mid));
        const customLabel = found ? `📍 ${found.name}` : `📍 Market ${mid}`;
        categories.splice(1, 0, { id: this._selectedCategory, label: customLabel });
      }
    }

    let stationsHtml = "";
    if (this._loading) {
      stationsHtml = `
        <div class="status-msg">
          <div class="spinner"></div>
          <div>Loading stations...</div>
        </div>
      `;
    } else if (this._stations.length === 0) {
      stationsHtml = `
        <div class="status-msg">
          <div>No stations found. Try another search or category.</div>
        </div>
      `;
    } else {
      stationsHtml = this._stations.map((st) => {
        const id = escapeHtml(st.id);
        const name = escapeHtml(st.name || st.callLetters || "Station");
        const freq = escapeHtml(st.freq || st.frequency || "");
        const call = escapeHtml(st.callLetters || "");
        const desc = escapeHtml(st.description || "");
        const sub = [call, freq].filter(Boolean).join(" • ") || desc;
        let logo = st.logo || st.newlogo;
        if (!logo && st.id) logo = `https://i.iheart.com/v3/re/assets/images/${st.id}.png`;
        const logoUrl = escapeHtml(logo || "");

        return `
          <div class="station-card" data-station-id="${id}" title="${name}">
            <div class="station-logo-box">
              ${logoUrl ? `<img src="${logoUrl}" alt="${name}" loading="lazy" class="station-logo" onerror="this.style.display='none'" />` : ""}
              <div class="station-play-overlay">▶</div>
            </div>
            <div class="station-info">
              <div class="station-name">${name}</div>
              <div class="station-sub">${sub}</div>
            </div>
          </div>
        `;
      }).join("");
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--ha-card-font-family, inherit);
          color: var(--primary-text-color, #ffffff);
          box-sizing: border-box;
        }
        ha-card {
          padding: 16px;
          background: var(--ha-card-background, rgba(20, 22, 28, 0.95));
          border-radius: var(--ha-card-border-radius, 16px);
          box-shadow: var(--ha-card-box-shadow, 0 8px 24px rgba(0, 0, 0, 0.28));
          border: 1px solid var(--divider-color, rgba(255, 255, 255, 0.08));
          overflow: hidden;
        }
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 14px;
          gap: 12px;
          flex-wrap: wrap;
        }
        .brand-title {
          font-size: 1.25rem;
          font-weight: 700;
          letter-spacing: -0.02em;
          display: flex;
          align-items: center;
          gap: 8px;
          color: #ff2d55;
        }
        .brand-title span {
          color: var(--primary-text-color, #ffffff);
        }
        .player-selector-wrap {
          display: flex;
          align-items: center;
          gap: 6px;
          background: rgba(255, 255, 255, 0.06);
          padding: 4px 10px;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .player-selector-label {
          font-size: 0.8rem;
          opacity: 0.7;
        }
        .player-select {
          background: transparent;
          color: var(--primary-text-color, #ffffff);
          border: none;
          font-size: 0.85rem;
          font-weight: 600;
          outline: none;
          cursor: pointer;
        }
        .player-select option {
          background: #1c1e24;
          color: #ffffff;
        }
        /* Controls Row: Search & Nationwide Market Dropdown */
        .controls-row {
          display: flex;
          gap: 10px;
          margin-bottom: 12px;
          flex-wrap: wrap;
        }
        .search-container {
          position: relative;
          flex: 1 1 180px;
          margin-bottom: 0;
        }
        .search-input {
          width: 100%;
          box-sizing: border-box;
          padding: 10px 36px 10px 14px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 10px;
          color: var(--primary-text-color, #ffffff);
          font-size: 0.9rem;
          outline: none;
          transition: border-color 0.2s, background 0.2s;
        }
        .search-input:focus {
          border-color: #ff2d55;
          background: rgba(255, 255, 255, 0.08);
        }
        .search-clear {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          cursor: pointer;
          opacity: 0.5;
          font-size: 1rem;
          user-select: none;
        }
        .search-clear:hover {
          opacity: 1;
        }
        .market-selector-wrap {
          flex: 0 1 230px;
          position: relative;
        }
        .market-select {
          width: 100%;
          box-sizing: border-box;
          padding: 10px 12px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 10px;
          color: var(--primary-text-color, #ffffff);
          font-size: 0.85rem;
          font-weight: 500;
          outline: none;
          cursor: pointer;
          transition: border-color 0.2s, background 0.2s;
        }
        .market-select:focus {
          border-color: #ff2d55;
          background: rgba(255, 255, 255, 0.08);
        }
        .market-select option, .market-select optgroup {
          background: #1c1e24;
          color: #ffffff;
        }
        /* Category Pills with horizontal scroll */
        .category-pills {
          display: flex;
          gap: 8px;
          overflow-x: auto;
          scrollbar-width: none;
          -webkit-overflow-scrolling: touch;
          margin-bottom: 14px;
          padding-bottom: 4px;
        }
        .category-pills::-webkit-scrollbar {
          display: none;
        }
        .pill {
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 0.8rem;
          font-weight: 600;
          white-space: nowrap;
          cursor: pointer;
          background: rgba(255, 255, 255, 0.06);
          color: var(--secondary-text-color, #999);
          border: 1px solid rgba(255, 255, 255, 0.08);
          transition: all 0.2s ease;
          user-select: none;
        }
        .pill:hover {
          background: rgba(255, 255, 255, 0.12);
          color: #ffffff;
        }
        .pill.active {
          background: #ff2d55;
          color: #ffffff;
          border-color: #ff2d55;
          box-shadow: 0 2px 8px rgba(255, 45, 85, 0.4);
        }
        /* Station Cards Grid */
        .stations-scroll-box {
          max-height: 420px;
          overflow-y: auto;
          scrollbar-width: thin;
          scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
        }
        .stations-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
          gap: 12px;
        }
        .station-card {
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.07);
          border-radius: 12px;
          padding: 10px;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease;
          user-select: none;
        }
        .station-card:hover {
          transform: translateY(-2px);
          background: rgba(255, 255, 255, 0.09);
          border-color: rgba(255, 45, 85, 0.5);
        }
        .station-card:active {
          transform: translateY(0);
        }
        .station-logo-box {
          width: 80px;
          height: 80px;
          border-radius: 10px;
          background: #111317;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          overflow: hidden;
          margin-bottom: 8px;
        }
        .station-logo {
          width: 100%;
          height: 100%;
          object-fit: contain;
        }
        .station-play-overlay {
          position: absolute;
          inset: 0;
          background: rgba(0, 0, 0, 0.45);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
          color: #ffffff;
          opacity: 0;
          transition: opacity 0.15s ease;
        }
        .station-card:hover .station-play-overlay {
          opacity: 1;
        }
        .station-info {
          width: 100%;
          overflow: hidden;
        }
        .station-name {
          font-size: 0.85rem;
          font-weight: 700;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          color: var(--primary-text-color, #ffffff);
          margin-bottom: 2px;
        }
        .station-sub {
          font-size: 0.72rem;
          color: var(--secondary-text-color, #8e929b);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        /* Now Playing Bar */
        .now-playing-bar {
          margin-top: 14px;
          padding: 10px 14px;
          background: linear-gradient(135deg, rgba(255, 45, 85, 0.18), rgba(255, 45, 85, 0.05));
          border: 1px solid rgba(255, 45, 85, 0.3);
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .np-info {
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .np-badge {
          font-size: 0.65rem;
          font-weight: 800;
          text-transform: uppercase;
          color: #ff2d55;
          letter-spacing: 0.05em;
        }
        .np-title {
          font-size: 0.9rem;
          font-weight: 700;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .np-artist {
          font-size: 0.75rem;
          color: var(--secondary-text-color, #999);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .np-controls {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .np-btn {
          background: #ff2d55;
          color: #ffffff;
          border: none;
          width: 36px;
          height: 36px;
          border-radius: 50%;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1rem;
          transition: transform 0.1s ease, background 0.2s ease;
        }
        .np-btn:hover {
          transform: scale(1.05);
          background: #e0264b;
        }
        .np-btn:active {
          transform: scale(0.95);
        }
        /* Status message */
        .status-msg {
          padding: 40px 20px;
          text-align: center;
          font-size: 0.9rem;
          color: var(--secondary-text-color, #8e929b);
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
        }
        .spinner {
          width: 28px;
          height: 28px;
          border: 3px solid rgba(255, 45, 85, 0.2);
          border-top-color: #ff2d55;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      </style>

      <ha-card>
        <!-- Header -->
        <div class="header">
          <div class="brand-title">
            📻 <span>${title}</span>
          </div>
          <div class="player-selector-wrap">
            <span class="player-selector-label">Speaker:</span>
            <select class="player-select">
              ${this._availablePlayers.map((p) => `
                <option value="${escapeHtml(p.entity_id)}" ${p.entity_id === this._selectedPlayer ? "selected" : ""}>
                  ${escapeHtml(p.name)} ${p.state === "playing" ? "🔊" : ""}
                </option>
              `).join("")}
            </select>
          </div>
        </div>

        <!-- Controls: Search & Nationwide Market Dropdown -->
        <div class="controls-row">
          <div class="search-container">
            <input
              type="text"
              class="search-input"
              placeholder="Search stations, call letters, cities..."
              value="${escapeHtml(this._searchQuery)}"
            />
            ${this._searchQuery ? '<div class="search-clear">✕</div>' : ""}
          </div>
          <div class="market-selector-wrap">
            <select class="market-select" title="Nationwide US Market Selector">
              <option value="">🗺️ Nationwide Markets (${this._markets.length || 274} Cities)...</option>
              ${this._renderMarketOptions()}
            </select>
          </div>
        </div>

        <!-- Category Pills -->
        <div class="category-pills">
          ${categories.map((c) => `
            <div
              class="pill ${this._selectedCategory === c.id && !this._searchQuery ? "active" : ""}"
              data-category="${escapeHtml(c.id)}"
            >
              ${escapeHtml(c.label)}
            </div>
          `).join("")}
        </div>

        <!-- Stations Grid -->
        <div class="stations-scroll-box">
          <div class="stations-grid">
            ${stationsHtml}
          </div>
        </div>

        <!-- Now Playing Bar -->
        <div class="now-playing-bar" style="${isPlaying || (playerObj && playerObj.state === "paused") ? "display:flex" : "display:none"}">
          <div class="np-info">
            <span class="np-badge">Now Streaming</span>
            <div class="np-title">${npTitle}</div>
            <div class="np-artist">${npArtist}</div>
          </div>
          <div class="np-controls">
            <button class="np-btn np-btn-play" title="Play/Pause">${isPlaying ? "⏸" : "▶"}</button>
            <button class="np-btn np-btn-stop" title="Stop">⏹</button>
          </div>
        </div>
      </ha-card>
    `;

    this._bindEvents();
    this._restoreScrollPositions();
  }

  _bindEvents() {
    const root = this.shadowRoot;

    // Player select change
    const playerSelect = root.querySelector(".player-select");
    if (playerSelect) {
      playerSelect.addEventListener("change", (e) => {
        this._selectedPlayer = e.target.value;
        localStorage.setItem("iheartradio_selected_player", this._selectedPlayer);
        this._render();
      });
    }

    // Search input
    const searchInput = root.querySelector(".search-input");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        this._markInteraction();
        this._searchQuery = e.target.value;
        if (this._searchTimeout) clearTimeout(this._searchTimeout);
        this._searchTimeout = setTimeout(() => {
          this._performSearch(this._searchQuery);
        }, 320);
      });
    }

    // Search clear
    const searchClear = root.querySelector(".search-clear");
    if (searchClear) {
      searchClear.addEventListener("click", () => {
        this._markInteraction();
        this._searchQuery = "";
        this._performSearch("");
      });
    }

    // Market dropdown change (Nationwide Selector)
    const marketSelect = root.querySelector(".market-select");
    if (marketSelect) {
      marketSelect.addEventListener("change", (e) => {
        this._markInteraction();
        const mid = e.target.value;
        if (mid) {
          this._searchQuery = "";
          this._loadCategoryStations(`market:${mid}`);
        }
      });
    }

    // Category pills click
    const pills = root.querySelectorAll(".pill");
    pills.forEach((pill) => {
      pill.addEventListener("click", (e) => {
        this._markInteraction();
        const cat = pill.getAttribute("data-category");
        this._searchQuery = "";
        this._loadCategoryStations(cat);
      });
    });

    // Horizontal mouse wheel scroll translation on category pills (Rule 11)
    const pillsBar = root.querySelector(".category-pills");
    if (pillsBar) {
      pillsBar.addEventListener("wheel", (e) => {
        if (e.deltaY !== 0) {
          e.preventDefault();
          pillsBar.scrollLeft += e.deltaY;
          this._markInteraction();
        }
      }, { passive: false });
      pillsBar.addEventListener("scroll", () => this._markInteraction(), { passive: true });
      pillsBar.addEventListener("touchstart", () => this._markInteraction(), { passive: true });
    }

    // Station scroll box touch & scroll listeners (Rule 11)
    const gridBox = root.querySelector(".stations-scroll-box");
    if (gridBox) {
      gridBox.addEventListener("scroll", () => this._markInteraction(), { passive: true });
      gridBox.addEventListener("touchstart", () => this._markInteraction(), { passive: true });
    }

    // Station card click -> Play
    const cards = root.querySelectorAll(".station-card");
    cards.forEach((card) => {
      card.addEventListener("click", () => {
        const stationId = card.getAttribute("data-station-id");
        if (stationId) {
          this._playStation(stationId);
        }
      });
    });

    // Now playing controls
    const playBtn = root.querySelector(".np-btn-play");
    if (playBtn && this._selectedPlayer) {
      playBtn.addEventListener("click", () => {
        this._hass.callService("media_player", "media_play_pause", {
          entity_id: this._selectedPlayer,
        });
      });
    }
    const stopBtn = root.querySelector(".np-btn-stop");
    if (stopBtn && this._selectedPlayer) {
      stopBtn.addEventListener("click", () => {
        this._hass.callService("media_player", "media_stop", {
          entity_id: this._selectedPlayer,
        });
      });
    }
  }
}

customElements.define("iheartradio-card", IHeartRadioCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "iheartradio-card",
  name: "iHeartRadio Player Card",
  description: "Browse, search, and stream iHeartRadio live stations to any media player",
  preview: true,
  documentationURL: "https://github.com/everyday3d/ha-iheartradio",
});

console.info(
  "%c 📻 IHEARTRADIO CARD %c v1.0.0 ",
  "color: white; background: #ff2d55; font-weight: 700; border-radius: 4px 0 0 4px;",
  "color: #ff2d55; background: #1c1e24; font-weight: 700; border-radius: 0 4px 4px 0;"
);
