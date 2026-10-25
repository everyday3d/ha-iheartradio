"""WebSocket API handlers for iHeartRadio."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .api import IHeartRadioApiClient, IHeartRadioError
from .const import DOMAIN, POPULAR_GENRES, POPULAR_MARKETS

_LOGGER = logging.getLogger(__name__)

WS_TYPE_SEARCH = "iheartradio/search"
WS_TYPE_STATIONS = "iheartradio/stations"
WS_TYPE_MARKETS = "iheartradio/markets"
WS_TYPE_GENRES = "iheartradio/genres"


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register WebSocket API commands."""
    websocket_api.async_register_command(hass, ws_search)
    websocket_api.async_register_command(hass, ws_stations)
    websocket_api.async_register_command(hass, ws_markets)
    websocket_api.async_register_command(hass, ws_genres)


def _get_api_client(hass: HomeAssistant) -> IHeartRadioApiClient:
    """Retrieve active API client."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise websocket_api.WebSocketError("not_configured", "iHeartRadio integration is not configured")
    entry_bundle = next(iter(entries.values()))
    return entry_bundle["client"]


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SEARCH,
        vol.Required("query"): str,
        vol.Optional("limit", default=25): int,
    }
)
@websocket_api.async_response
async def ws_search(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle live station search."""
    try:
        client = _get_api_client(hass)
        results = await client.async_search(msg["query"], limit=msg.get("limit", 25))
        connection.send_result(msg["id"], {"stations": results})
    except IHeartRadioError as err:
        connection.send_error(msg["id"], "search_failed", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_STATIONS,
        vol.Optional("market_id"): str,
        vol.Optional("genre_id"): int,
        vol.Optional("limit", default=60): int,
    }
)
@websocket_api.async_response
async def ws_stations(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle fetching stations by market or genre."""
    try:
        client = _get_api_client(hass)
        limit = msg.get("limit", 60)
        market_id = msg.get("market_id")
        genre_id = msg.get("genre_id")

        if genre_id is not None:
            stations = await client.async_get_stations_by_genre(genre_id, limit=limit)
        elif market_id is not None:
            stations = await client.async_get_stations_by_market(market_id, limit=limit)
        else:
            # Fallback to local configured market
            coordinator = next(iter(hass.data[DOMAIN].values()))["coordinator"]
            stations = coordinator.market_stations

        connection.send_result(msg["id"], {"stations": stations})
    except IHeartRadioError as err:
        connection.send_error(msg["id"], "fetch_failed", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_MARKETS,
    }
)
@websocket_api.async_response
async def ws_markets(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle listing available markets."""
    market_list = [{"id": mid, "name": mname} for mid, mname in POPULAR_MARKETS.items()]
    connection.send_result(msg["id"], {"markets": market_list})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_GENRES,
    }
)
@websocket_api.async_response
async def ws_genres(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle listing available genres."""
    genre_list = [{"id": gid, "name": gname} for gid, gname in POPULAR_GENRES.items()]
    connection.send_result(msg["id"], {"genres": genre_list})
