"""Config flow for iHeartRadio integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    ALL_US_MARKETS,
    CONF_DEFAULT_MARKET,
    CONF_FAVORITES,
    CONF_STREAM_TYPE,
    DEFAULT_MARKET,
    DEFAULT_STREAM_TYPE,
    DOMAIN,
    POPULAR_MARKETS,
    STREAM_TYPE_DIRECT,
    STREAM_TYPE_HLS,
)

_LOGGER = logging.getLogger(__name__)


def _get_market_options() -> list[selector.SelectOptionDict]:
    """Generate select options for all US markets."""
    return [
        selector.SelectOptionDict(value=mid, label=f"{name} (ID: {mid})")
        for mid, name in ALL_US_MARKETS.items()
    ]


def _get_stream_type_options() -> list[selector.SelectOptionDict]:
    """Generate select options for stream formats."""
    return [
        selector.SelectOptionDict(
            value=STREAM_TYPE_DIRECT,
            label="Direct Stream (Fastest playback on Sonos, Cast, ESP32)",
        ),
        selector.SelectOptionDict(
            value=STREAM_TYPE_HLS,
            label="HLS Stream (Adaptive bitrate, fallback for web players)",
        ),
    ]


class IHeartRadioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iHeartRadio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            market_name = POPULAR_MARKETS.get(
                user_input.get(CONF_DEFAULT_MARKET, DEFAULT_MARKET), "Default"
            )
            return self.async_create_entry(
                title=f"iHeartRadio ({market_name})",
                data=user_input,
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEFAULT_MARKET, default=DEFAULT_MARKET): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_get_market_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_STREAM_TYPE, default=DEFAULT_STREAM_TYPE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_get_stream_type_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithConfigEntry:
        """Get the options flow for this handler."""
        return IHeartRadioOptionsFlowHandler(config_entry)


class IHeartRadioOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle an options flow for iHeartRadio."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the iHeartRadio options."""
        if user_input is not None:
            # Parse comma-separated or space-separated favorite station IDs
            raw_favorites = user_input.get(CONF_FAVORITES, "")
            parsed_favorites = [
                item.strip()
                for item in raw_favorites.replace(",", " ").split()
                if item.strip()
            ]
            user_input[CONF_FAVORITES] = parsed_favorites
            return self.async_create_entry(title="", data=user_input)

        current_market = self.options.get(
            CONF_DEFAULT_MARKET,
            self.config_entry.data.get(CONF_DEFAULT_MARKET, DEFAULT_MARKET),
        )
        current_stream = self.options.get(
            CONF_STREAM_TYPE,
            self.config_entry.data.get(CONF_STREAM_TYPE, DEFAULT_STREAM_TYPE),
        )
        current_favorites = self.options.get(
            CONF_FAVORITES,
            self.config_entry.data.get(CONF_FAVORITES, []),
        )
        favorites_string = ", ".join(str(f) for f in current_favorites)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_DEFAULT_MARKET, default=current_market): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_get_market_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_STREAM_TYPE, default=current_stream): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_get_stream_type_options(),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_FAVORITES, default=favorites_string): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=False,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
