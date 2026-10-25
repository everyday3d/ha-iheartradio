"""The iHeartRadio Home Assistant Integration."""
from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .api import IHeartRadioApiClient, IHeartRadioError
from .const import (
    CONF_STREAM_TYPE,
    DEFAULT_STREAM_TYPE,
    DOMAIN,
)
from .coordinator import IHeartRadioCoordinator
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []

SERVICE_PLAY_STATION = "play_station"
ATTR_ENTITY_ID = "entity_id"
ATTR_STATION = "station"

SCHEMA_PLAY_STATION = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_STATION): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iHeartRadio from a config entry."""
    # Obtain integration metadata asynchronously (Rule: Zero blocking file I/O)
    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info("Setting up %s version %s", DOMAIN, integration.version)

    session = async_get_clientsession(hass)
    client = IHeartRadioApiClient(session)

    # Combine data and options
    entry_config = {**entry.data, **entry.options}
    coordinator = IHeartRadioCoordinator(hass, client, entry_config)

    # Initial catalog fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "entry": entry,
    }

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Register platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register custom actions/services
    _async_register_services(hass)

    # Register WebSocket commands for frontend card
    async_register_websocket_commands(hass)

    # Register Lovelace card static path (Rule: Zero blocking file I/O)
    card_path = os.path.join(os.path.dirname(__file__), "iheartradio-card.js")
    card_exists = await hass.async_add_executor_job(os.path.exists, card_path)
    if card_exists and not hass.data.get(f"{DOMAIN}_static_registered"):
        try:
            await hass.http.async_register_static_paths([
                StaticPathConfig("/iheartradio/iheartradio-card.js", card_path, cache_headers=True)
            ])
            add_extra_js_url(hass, f"/iheartradio/iheartradio-card.js?v={integration.version}")
            hass.data[f"{DOMAIN}_static_registered"] = True
            _LOGGER.info("Registered iHeartRadio Lovelace card at /iheartradio/iheartradio-card.js")
        except Exception as err:
            _LOGGER.debug("Could not register iHeartRadio static path: %s", err)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an iHeartRadio config entry."""
    unload_ok = (
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if PLATFORMS
        else True
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            # Deregister services when last entry is unloaded
            hass.services.async_remove(DOMAIN, SERVICE_PLAY_STATION)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register iHeartRadio integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_PLAY_STATION):
        return

    async def _handle_play_station(call: ServiceCall) -> None:
        """Handle the play_station service call."""
        raw_entity_ids = call.data[ATTR_ENTITY_ID]
        target_entity_ids = (
            raw_entity_ids if isinstance(raw_entity_ids, list) else [raw_entity_ids]
        )
        station_query = str(call.data[ATTR_STATION]).strip()

        # Rule: Frenck standard - strict target validation (whitelist domain & check state existence)
        valid_targets: list[str] = []
        for eid in target_entity_ids:
            if not eid.startswith("media_player."):
                _LOGGER.warning("Target %s is not in media_player domain, skipping", eid)
                continue
            if hass.states.get(eid) is None:
                _LOGGER.warning("Target media_player %s does not exist, skipping", eid)
                continue
            valid_targets.append(eid)

        if not valid_targets:
            raise HomeAssistantError("No valid target media_player entities provided")

        entries = hass.data.get(DOMAIN, {})
        if not entries:
            raise HomeAssistantError("iHeartRadio integration is not configured")

        entry_bundle = next(iter(entries.values()))
        client: IHeartRadioApiClient = entry_bundle["client"]
        options = entry_bundle["entry"].options or entry_bundle["entry"].data
        stream_type = options.get(CONF_STREAM_TYPE, DEFAULT_STREAM_TYPE)

        try:
            # Resolve station query (ID or keyword search)
            station_id = ""
            if station_query.isdigit():
                station_id = station_query
            else:
                results = await client.async_search(station_query, limit=5)
                if not results:
                    raise HomeAssistantError(
                        f"No iHeartRadio stations found matching '{station_query}'"
                    )
                station_id = str(results[0].get("id"))

            stream_url, _ = await client.async_get_stream(station_id, stream_type=stream_type)

            # Dispatch play_media command to validated targets
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": valid_targets,
                    "media_content_id": stream_url,
                    "media_content_type": "music",
                },
                blocking=True,
            )
            _LOGGER.info(
                "Played iHeartRadio station %s on %s",
                station_id,
                valid_targets,
            )
        except IHeartRadioError as err:
            raise HomeAssistantError(f"Failed to play iHeartRadio station: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_STATION,
        _handle_play_station,
        schema=SCHEMA_PLAY_STATION,
    )
