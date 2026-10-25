"""DataUpdateCoordinator for iHeartRadio."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import IHeartRadioApiClient, IHeartRadioError
from .const import CONF_DEFAULT_MARKET, CONF_FAVORITES, DEFAULT_MARKET, DOMAIN

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(hours=6)
ISSUE_API_ERROR = "api_connection_error"


class IHeartRadioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching iHeartRadio catalog and favorite data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: IHeartRadioApiClient,
        entry_data: dict[str, Any],
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.entry_data = entry_data
        self.market_stations: list[dict[str, Any]] = []
        self.favorite_stations: list[dict[str, Any]] = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch station data for market and favorites."""
        market_id = self.entry_data.get(CONF_DEFAULT_MARKET, DEFAULT_MARKET)
        raw_favorites = self.entry_data.get(CONF_FAVORITES, [])

        try:
            # Fetch local market stations
            stations = await self.client.async_get_stations_by_market(market_id, limit=60)
            self.market_stations = stations

            # Fetch favorites if specified
            favorites: list[dict[str, Any]] = []
            for fav in raw_favorites:
                try:
                    fav_id = str(fav).strip()
                    if fav_id:
                        station_data = await self.client.async_get_station(fav_id)
                        favorites.append(station_data)
                except IHeartRadioError as fav_err:
                    _LOGGER.debug("Could not resolve favorite station %s: %s", fav, fav_err)

            self.favorite_stations = favorites

            # Clear any previously registered issue on success
            async_delete_issue(self.hass, DOMAIN, ISSUE_API_ERROR)

            return {
                "market_id": market_id,
                "market_stations": stations,
                "favorite_stations": favorites,
            }
        except IHeartRadioError as err:
            # Register issue in HA Repair registry (circuit-breaker)
            async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_API_ERROR,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="api_connection_error",
                translation_placeholders={"error": str(err)},
            )
            raise UpdateFailed(f"Error communicating with iHeartRadio API: {err}") from err
