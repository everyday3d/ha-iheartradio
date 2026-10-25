"""The iHeartRadio Home Assistant Integration."""
from __future__ import annotations

import asyncio
import logging
import math
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
    ATTR_ACTION,
    ATTR_ANNOUNCE_PLAYER,
    ATTR_CURVE,
    ATTR_DURATION,
    ATTR_DUCK_VOLUME,
    ATTR_ENTITY_ID,
    ATTR_FADE_DURATION,
    ATTR_FADE_OUT,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MESSAGE,
    ATTR_PAUSE_ON_FINISH,
    ATTR_STATION,
    ATTR_SYNC_START,
    ATTR_TARGET_VOLUME,
    ATTR_TTS_ENGINE,
    ATTR_VOLUME_LEVEL,
    ATTR_VOLUMES,
    ATTR_WAIT_TIME,
    CONF_DEFAULT_MARKET,
    CONF_STREAM_TYPE,
    DEFAULT_STREAM_TYPE,
    DOMAIN,
    SERVICE_ANNOUNCE,
    SERVICE_CANCEL_FADE,
    SERVICE_FADE_OUT,
    SERVICE_PLAY_GROUP,
    SERVICE_PLAY_STATION,
    SERVICE_SLEEP_TIMER,
    SERVICE_STOP_GROUP,
    STREAM_TYPE_DIRECT,
    STREAM_TYPE_HLS,
)
from .coordinator import IHeartRadioCoordinator
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []

SCHEMA_PLAY_STATION = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_STATION): cv.string,
    }
)

SCHEMA_FADE_OUT = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_DURATION, default=30): vol.All(vol.Coerce(int), vol.Range(min=1, max=1800)),
        vol.Optional(ATTR_TARGET_VOLUME, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        vol.Optional(ATTR_PAUSE_ON_FINISH, default=True): cv.boolean,
        vol.Optional(ATTR_CURVE, default="linear"): vol.In(["linear", "logarithmic"]),
    }
)

SCHEMA_SLEEP_TIMER = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
        vol.Optional(ATTR_FADE_OUT, default=True): cv.boolean,
        vol.Optional(ATTR_FADE_DURATION, default=60): vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
        vol.Optional(ATTR_ACTION, default="pause"): vol.In(["pause", "stop"]),
    }
)

SCHEMA_CANCEL_FADE = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

SCHEMA_ANNOUNCE = vol.All(
    cv.has_at_least_one_key(ATTR_MESSAGE, ATTR_MEDIA_CONTENT_ID),
    vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_MEDIA_CONTENT_ID): cv.string,
            vol.Optional(ATTR_DUCK_VOLUME, default=0.15): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=1.0)
            ),
            vol.Optional(ATTR_FADE_DURATION, default=2): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=10)
            ),
            vol.Optional(ATTR_WAIT_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional(ATTR_TTS_ENGINE): cv.string,
            vol.Optional(ATTR_ANNOUNCE_PLAYER): cv.string,
        }
    ),
)

SCHEMA_PLAY_GROUP = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_STATION): cv.string,
        vol.Optional(CONF_STREAM_TYPE): vol.In([STREAM_TYPE_DIRECT, STREAM_TYPE_HLS]),
        vol.Optional(ATTR_VOLUME_LEVEL): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=1.0)
        ),
        vol.Optional(ATTR_VOLUMES): vol.Schema(
            {cv.entity_id: vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0))}
        ),
        vol.Optional(ATTR_SYNC_START, default=True): cv.boolean,
    }
)

SCHEMA_STOP_GROUP = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_ACTION, default="stop"): vol.In(["stop", "pause"]),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iHeartRadio from a config entry."""
    # Obtain integration metadata asynchronously (Rule: Zero blocking file I/O)
    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info("Setting up %s version %s", DOMAIN, integration.version)

    session = async_get_clientsession(hass)
    client = IHeartRadioApiClient(session)

    # Auto-migrate legacy market IDs from early beta entries
    legacy_migrations = {
        "137": "99",   # Boston, MA
        "143": "84",   # Chicago, IL
        "127": "61",   # Atlanta, GA
        "133": "214",  # Austin, TX
        "151": "111",  # Detroit, MI
        "183": "152",  # Las Vegas, NV
        "207": "14",   # Phoenix, AZ
        "213": "192",  # Portland, OR
        "221": "226",  # San Antonio, TX
        "227": "119",  # St. Louis, MO
        "229": "245",  # Seattle-Tacoma, WA
        "171": "220",  # Houston, TX
        "145": "218",  # Dallas, TX
        "217": "27",   # San Diego, CA
        "219": "28",   # San Francisco, CA
        "147": "37",   # Denver, CO
        "193": "50",   # Miami, FL
        "197": "116",  # Minneapolis, MN
        "237": "58",   # Tampa, FL
        "201": "210",  # Nashville, TN
        "131": "102",  # Baltimore, MD
        "141": "130",  # Charlotte, NC
        "205": "197",  # Pittsburgh, PA
    }
    raw_market = entry.options.get(CONF_DEFAULT_MARKET) or entry.data.get(CONF_DEFAULT_MARKET)
    if raw_market in legacy_migrations:
        new_market = legacy_migrations[raw_market]
        _LOGGER.info("Migrating legacy market ID %s -> %s for %s", raw_market, new_market, entry.title)
        new_data = {**entry.data, CONF_DEFAULT_MARKET: new_market}
        new_options = {**entry.options}
        if CONF_DEFAULT_MARKET in new_options:
            new_options[CONF_DEFAULT_MARKET] = new_market
        hass.config_entries.async_update_entry(entry, data=new_data, options=new_options)

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
            hass.services.async_remove(DOMAIN, SERVICE_FADE_OUT)
            hass.services.async_remove(DOMAIN, SERVICE_SLEEP_TIMER)
            hass.services.async_remove(DOMAIN, SERVICE_CANCEL_FADE)
            hass.services.async_remove(DOMAIN, SERVICE_ANNOUNCE)
            hass.services.async_remove(DOMAIN, SERVICE_PLAY_GROUP)
            hass.services.async_remove(DOMAIN, SERVICE_STOP_GROUP)

            # Rule 14: Clean Lifecycle Unload - cancel and await running background tasks
            active_tasks: dict[str, asyncio.Task] = hass.data.pop(f"{DOMAIN}_tasks", {})
            for task in list(active_tasks.values()):
                if not task.done():
                    task.cancel()
            if active_tasks:
                await asyncio.gather(*active_tasks.values(), return_exceptions=True)

            hass.data.pop(f"{DOMAIN}_last_played", None)
            hass.data.pop(f"{DOMAIN}_groups", None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _validate_targets(hass: HomeAssistant, raw_entity_ids: Any) -> list[str]:
    """Validate target entities: media_player domain & state exists (Rule 14)."""
    target_entity_ids = (
        raw_entity_ids if isinstance(raw_entity_ids, list) else [raw_entity_ids]
    )
    valid_targets: list[str] = []
    for eid in target_entity_ids:
        if not eid.startswith("media_player."):
            _LOGGER.warning("Target %s is not in media_player domain, skipping", eid)
            continue
        if hass.states.get(eid) is None:
            _LOGGER.warning("Target media_player %s does not exist, skipping", eid)
            continue
        valid_targets.append(eid)
    return valid_targets


async def _async_fade_player(
    hass: HomeAssistant,
    entity_id: str,
    target_volume: float,
    duration: int,
    pause_on_finish: bool,
    curve: str,
) -> None:
    """Fade a single media player's volume smoothly over duration."""
    state = hass.states.get(entity_id)
    if not state or state.state in ("off", "idle"):
        _LOGGER.debug("Media player %s is %s, aborting fade", entity_id, state.state if state else "None")
        return

    current_vol = state.attributes.get("volume_level")
    if current_vol is None:
        _LOGGER.warning(
            "Media player %s does not report volume_level; cannot calculate volume fade curve",
            entity_id,
        )
        if pause_on_finish:
            await asyncio.sleep(duration)
            await hass.services.async_call(
                "media_player", "media_pause", {"entity_id": entity_id}, blocking=True
            )
        return

    start_vol = float(current_vol)
    if abs(start_vol - target_volume) < 0.01:
        if pause_on_finish and target_volume == 0.0:
            await hass.services.async_call(
                "media_player", "media_pause", {"entity_id": entity_id}, blocking=True
            )
        return

    step_interval = 1.0 if duration <= 60 else 2.0
    num_steps = max(1, int(duration / step_interval))

    try:
        for step in range(1, num_steps + 1):
            await asyncio.sleep(step_interval)

            curr_state = hass.states.get(entity_id)
            if not curr_state or curr_state.state in ("off", "idle"):
                _LOGGER.debug("Player %s state changed to %s; stopping fade early", entity_id, curr_state.state if curr_state else "None")
                return

            progress = step / num_steps
            if curve == "logarithmic":
                factor = 1.0 - math.pow(1.0 - progress, 1.5)
                vol_now = start_vol + (target_volume - start_vol) * factor
            else:
                vol_now = start_vol + (target_volume - start_vol) * progress

            vol_clamped = max(0.0, min(1.0, round(vol_now, 2)))
            await hass.services.async_call(
                "media_player",
                "volume_set",
                {"entity_id": entity_id, "volume_level": vol_clamped},
                blocking=False,
            )

        if pause_on_finish and target_volume == 0.0:
            await hass.services.async_call(
                "media_player",
                "media_pause",
                {"entity_id": entity_id},
                blocking=True,
            )
            _LOGGER.info("Fade-out complete for %s: paused playback", entity_id)
        else:
            _LOGGER.info("Fade complete for %s at volume %.2f", entity_id, target_volume)

    except asyncio.CancelledError:
        _LOGGER.debug("Fade task cancelled for %s", entity_id)
        raise
    finally:
        active_tasks = hass.data.get(f"{DOMAIN}_tasks", {})
        active_tasks.pop(entity_id, None)


async def _async_sleep_timer_player(
    hass: HomeAssistant,
    entity_id: str,
    total_minutes: int,
    fade_out: bool,
    fade_duration: int,
    action: str,
) -> None:
    """Wait for sleep timer duration and then stop/pause with optional fade."""
    total_seconds = total_minutes * 60
    wait_seconds = max(0, total_seconds - fade_duration) if fade_out else total_seconds

    try:
        if wait_seconds > 0:
            _LOGGER.info(
                "Sleep timer started on %s for %d minutes (fade: %s, duration: %ds)",
                entity_id,
                total_minutes,
                fade_out,
                fade_duration if fade_out else 0,
            )
            await asyncio.sleep(wait_seconds)

        state = hass.states.get(entity_id)
        if not state or state.state in ("off", "idle"):
            _LOGGER.debug("Sleep timer reached on %s, but player is %s", entity_id, state.state if state else "None")
            return

        if fade_out and fade_duration > 0:
            await _async_fade_player(
                hass=hass,
                entity_id=entity_id,
                target_volume=0.0,
                duration=fade_duration,
                pause_on_finish=False,
                curve="linear",
            )

        action_service = "media_stop" if action == "stop" else "media_pause"
        await hass.services.async_call(
            "media_player",
            action_service,
            {"entity_id": entity_id},
            blocking=True,
        )
        _LOGGER.info("Sleep timer finished on %s: executed %s", entity_id, action_service)

    except asyncio.CancelledError:
        _LOGGER.debug("Sleep timer cancelled for %s", entity_id)
        raise
    finally:
        active_tasks = hass.data.get(f"{DOMAIN}_tasks", {})
        active_tasks.pop(entity_id, None)


async def _async_announce_player(
    hass: HomeAssistant,
    entity_id: str,
    message: str | None,
    media_content_id: str | None,
    duck_volume: float,
    fade_duration: int,
    wait_time: int | None,
    tts_engine: str | None,
    announce_player: str | None,
) -> None:
    """Duck radio volume, play announcement, and restore stream (Rule 14)."""
    target_announce = announce_player or entity_id

    # Validate target announcement player (Rule 14)
    if not target_announce.startswith("media_player.") or hass.states.get(target_announce) is None:
        _LOGGER.warning("Announcement player %s is invalid or does not exist", target_announce)
        return

    # Validate tts engine if provided (Rule 14)
    if tts_engine and (not tts_engine.startswith("tts.") or hass.states.get(tts_engine) is None):
        _LOGGER.warning("TTS engine %s is invalid; must belong to tts domain", tts_engine)
        return

    # Check initial state of the radio speaker
    state = hass.states.get(entity_id)
    is_playing = state is not None and state.state == "playing"
    original_volume = float(state.attributes.get("volume_level", 0.5)) if state else 0.5

    last_played = hass.data.get(f"{DOMAIN}_last_played", {}).get(entity_id)

    try:
        # 1. Duck the radio volume if currently playing
        if is_playing and original_volume > duck_volume:
            await _async_fade_player(
                hass=hass,
                entity_id=entity_id,
                target_volume=duck_volume,
                duration=fade_duration,
                pause_on_finish=False,
                curve="linear",
            )

        # 2. Dispatch announcement
        is_same_player = target_announce == entity_id
        if message:
            # Find TTS engine if not specified
            engine_entity = tts_engine
            if not engine_entity:
                for s in hass.states.async_all("tts"):
                    engine_entity = s.entity_id
                    break

            if engine_entity:
                await hass.services.async_call(
                    "tts",
                    "speak",
                    {
                        "media_player_entity_id": target_announce,
                        "message": message,
                    },
                    target={"entity_id": engine_entity},
                    blocking=True,
                )
            else:
                _LOGGER.warning("No TTS engine available in Home Assistant to speak announcement")
        elif media_content_id:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": target_announce,
                    "media_content_id": media_content_id,
                    "media_content_type": "music",
                },
                blocking=True,
            )

        # 3. Wait for announcement duration
        calc_wait = wait_time
        if calc_wait is None:
            if message:
                words = len(message.split())
                calc_wait = max(4, int(words / 2.5) + 3)
            else:
                calc_wait = 5

        await asyncio.sleep(calc_wait)

        # 4. If same player and was playing an iHeartRadio station, resume playback
        if is_same_player and is_playing and last_played:
            entries = hass.data.get(DOMAIN, {})
            if entries:
                entry_bundle = next(iter(entries.values()))
                client: IHeartRadioApiClient = entry_bundle["client"]
                station_id = last_played["station_id"]
                stream_type = last_played.get("stream_type", DEFAULT_STREAM_TYPE)

                try:
                    stream_url, _ = await client.async_get_stream(station_id, stream_type=stream_type)
                    await hass.services.async_call(
                        "media_player",
                        "play_media",
                        {
                            "entity_id": entity_id,
                            "media_content_id": stream_url,
                            "media_content_type": "music",
                        },
                        blocking=True,
                    )
                    _LOGGER.info("Resumed iHeartRadio station %s on %s after announcement", station_id, entity_id)
                except Exception as err:
                    _LOGGER.warning("Could not resume station %s after announcement: %s", station_id, err)

        # 5. Restore volume back to original level smoothly
        if is_playing and original_volume > duck_volume:
            await _async_fade_player(
                hass=hass,
                entity_id=entity_id,
                target_volume=original_volume,
                duration=fade_duration,
                pause_on_finish=False,
                curve="linear",
            )

    except asyncio.CancelledError:
        _LOGGER.debug("Announce task cancelled for %s", entity_id)
        raise
    finally:
        active_tasks = hass.data.get(f"{DOMAIN}_tasks", {})
        active_tasks.pop(entity_id, None)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register iHeartRadio integration services."""

    async def _handle_play_station(call: ServiceCall) -> None:
        """Handle the play_station service call."""
        valid_targets = _validate_targets(hass, call.data[ATTR_ENTITY_ID])
        if not valid_targets:
            raise HomeAssistantError("No valid target media_player entities provided")

        station_query = str(call.data[ATTR_STATION]).strip()
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
            # Record last played station on targets for auto-resume during announcements
            last_played = hass.data.setdefault(f"{DOMAIN}_last_played", {})
            for eid in valid_targets:
                last_played[eid] = {
                    "station_id": station_id,
                    "stream_type": stream_type,
                }

            _LOGGER.info(
                "Played iHeartRadio station %s on %s",
                station_id,
                valid_targets,
            )
        except IHeartRadioError as err:
            raise HomeAssistantError(f"Failed to play iHeartRadio station: {err}") from err

    async def _handle_fade_out(call: ServiceCall) -> None:
        """Handle the fade_out service call."""
        valid_targets = _validate_targets(hass, call.data[ATTR_ENTITY_ID])
        if not valid_targets:
            raise HomeAssistantError("No valid target media_player entities provided")

        duration = call.data[ATTR_DURATION]
        target_volume = call.data[ATTR_TARGET_VOLUME]
        pause_on_finish = call.data[ATTR_PAUSE_ON_FINISH]
        curve = call.data[ATTR_CURVE]

        active_tasks = hass.data.setdefault(f"{DOMAIN}_tasks", {})
        for eid in valid_targets:
            existing = active_tasks.get(eid)
            if existing and not existing.done():
                existing.cancel()

            task = hass.async_create_task(
                _async_fade_player(hass, eid, target_volume, duration, pause_on_finish, curve)
            )
            active_tasks[eid] = task

    async def _handle_sleep_timer(call: ServiceCall) -> None:
        """Handle the sleep_timer service call."""
        valid_targets = _validate_targets(hass, call.data[ATTR_ENTITY_ID])
        if not valid_targets:
            raise HomeAssistantError("No valid target media_player entities provided")

        duration = call.data[ATTR_DURATION]
        fade_out = call.data[ATTR_FADE_OUT]
        fade_duration = call.data[ATTR_FADE_DURATION]
        action = call.data[ATTR_ACTION]

        active_tasks = hass.data.setdefault(f"{DOMAIN}_tasks", {})
        for eid in valid_targets:
            existing = active_tasks.get(eid)
            if existing and not existing.done():
                existing.cancel()

            task = hass.async_create_task(
                _async_sleep_timer_player(hass, eid, duration, fade_out, fade_duration, action)
            )
            active_tasks[eid] = task

    async def _handle_cancel_fade(call: ServiceCall) -> None:
        """Handle the cancel_fade service call."""
        valid_targets = _validate_targets(hass, call.data[ATTR_ENTITY_ID])
        if not valid_targets:
            raise HomeAssistantError("No valid target media_player entities provided")

        active_tasks = hass.data.setdefault(f"{DOMAIN}_tasks", {})
        for eid in valid_targets:
            existing = active_tasks.get(eid)
            if existing and not existing.done():
                existing.cancel()
                active_tasks.pop(eid, None)
                _LOGGER.info("Cancelled active fade/sleep timer for %s", eid)

    async def _handle_announce(call: ServiceCall) -> None:
        """Handle the announce service call (smart audio ducking)."""
        valid_targets = _validate_targets(hass, call.data[ATTR_ENTITY_ID])
        if not valid_targets:
            raise HomeAssistantError("No valid target media_player entities provided")

        message = call.data.get(ATTR_MESSAGE)
        media_content_id = call.data.get(ATTR_MEDIA_CONTENT_ID)
        duck_volume = call.data[ATTR_DUCK_VOLUME]
        fade_duration = call.data[ATTR_FADE_DURATION]
        wait_time = call.data.get(ATTR_WAIT_TIME)
        tts_engine = call.data.get(ATTR_TTS_ENGINE)
        announce_player = call.data.get(ATTR_ANNOUNCE_PLAYER)

        active_tasks = hass.data.setdefault(f"{DOMAIN}_tasks", {})
        for eid in valid_targets:
            existing = active_tasks.get(eid)
            if existing and not existing.done():
                existing.cancel()

            task = hass.async_create_task(
                _async_announce_player(
                    hass,
                    eid,
                    message,
                    media_content_id,
                    duck_volume,
                    fade_duration,
                    wait_time,
                    tts_engine,
                    announce_player,
                )
            )
            active_tasks[eid] = task

    async def _handle_play_group(call: ServiceCall) -> None:
        """Handle the play_group service call (multi-speaker synchronized broadcast)."""
        valid_targets = _validate_targets(hass, call.data[ATTR_ENTITY_ID])
        if not valid_targets:
            raise HomeAssistantError("No valid target media_player entities provided")

        station_query = str(call.data[ATTR_STATION]).strip()
        entries = hass.data.get(DOMAIN, {})
        if not entries:
            raise HomeAssistantError("iHeartRadio integration is not configured")

        entry_bundle = next(iter(entries.values()))
        client: IHeartRadioApiClient = entry_bundle["client"]
        options = entry_bundle["entry"].options or entry_bundle["entry"].data
        stream_type = call.data.get(CONF_STREAM_TYPE) or options.get(CONF_STREAM_TYPE, DEFAULT_STREAM_TYPE)

        try:
            # Resolve station query (station ID or keyword search)
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

            # 1. Volume balancing across speakers
            global_vol = call.data.get(ATTR_VOLUME_LEVEL)
            custom_vols: dict[str, float] = call.data.get(ATTR_VOLUMES) or {}
            vol_tasks = []
            for eid in valid_targets:
                vol_to_set = custom_vols.get(eid, global_vol)
                if vol_to_set is not None:
                    vol_tasks.append(
                        hass.services.async_call(
                            "media_player",
                            "volume_set",
                            {"entity_id": eid, "volume_level": vol_to_set},
                            blocking=True,
                        )
                    )
            if vol_tasks:
                await asyncio.gather(*vol_tasks, return_exceptions=True)

            # 2. Concurrently dispatch play_media to all validated speakers
            play_tasks = [
                hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": eid,
                        "media_content_id": stream_url,
                        "media_content_type": "music",
                    },
                    blocking=True,
                )
                for eid in valid_targets
            ]
            results = await asyncio.gather(*play_tasks, return_exceptions=True)
            for eid, res in zip(valid_targets, results):
                if isinstance(res, Exception):
                    _LOGGER.warning("Could not dispatch stream to %s: %s", eid, res)

            # 3. Track active group membership & last played station
            active_groups: set[str] = hass.data.setdefault(f"{DOMAIN}_groups", set())
            active_groups.update(valid_targets)

            last_played = hass.data.setdefault(f"{DOMAIN}_last_played", {})
            for eid in valid_targets:
                last_played[eid] = {
                    "station_id": station_id,
                    "stream_type": stream_type,
                }

            _LOGGER.info(
                "Started sync group broadcast of station %s across %d speakers: %s",
                station_id,
                len(valid_targets),
                valid_targets,
            )
        except IHeartRadioError as err:
            raise HomeAssistantError(f"Failed to play iHeartRadio station on group: {err}") from err

    async def _handle_stop_group(call: ServiceCall) -> None:
        """Handle the stop_group service call (stop/pause multi-room broadcast)."""
        raw_targets = call.data.get(ATTR_ENTITY_ID)
        if raw_targets:
            targets = _validate_targets(hass, raw_targets)
        else:
            active_groups: set[str] = hass.data.get(f"{DOMAIN}_groups", set())
            targets = [eid for eid in active_groups if hass.states.get(eid) is not None]

        if not targets:
            _LOGGER.debug("No active group speakers to stop")
            return

        action = call.data.get(ATTR_ACTION, "stop")
        service_name = "media_stop" if action == "stop" else "media_pause"

        stop_tasks = [
            hass.services.async_call(
                "media_player",
                service_name,
                {"entity_id": eid},
                blocking=True,
            )
            for eid in targets
        ]
        results = await asyncio.gather(*stop_tasks, return_exceptions=True)
        for eid, res in zip(targets, results):
            if isinstance(res, Exception):
                _LOGGER.warning("Could not %s on group player %s: %s", action, eid, res)

        active_groups = hass.data.get(f"{DOMAIN}_groups", set())
        for eid in targets:
            active_groups.discard(eid)

        _LOGGER.info("Executed %s across %d group speakers: %s", service_name, len(targets), targets)

    if not hass.services.has_service(DOMAIN, SERVICE_PLAY_STATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_STATION,
            _handle_play_station,
            schema=SCHEMA_PLAY_STATION,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_FADE_OUT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_FADE_OUT,
            _handle_fade_out,
            schema=SCHEMA_FADE_OUT,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SLEEP_TIMER):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SLEEP_TIMER,
            _handle_sleep_timer,
            schema=SCHEMA_SLEEP_TIMER,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CANCEL_FADE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CANCEL_FADE,
            _handle_cancel_fade,
            schema=SCHEMA_CANCEL_FADE,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_ANNOUNCE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ANNOUNCE,
            _handle_announce,
            schema=SCHEMA_ANNOUNCE,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_PLAY_GROUP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PLAY_GROUP,
            _handle_play_group,
            schema=SCHEMA_PLAY_GROUP,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_STOP_GROUP):
        hass.services.async_register(
            DOMAIN,
            SERVICE_STOP_GROUP,
            _handle_stop_group,
            schema=SCHEMA_STOP_GROUP,
        )
