"""Async API Client for iHeartRadio."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import (
    API_BASE_V1,
    API_BASE_V2,
    API_USER_AGENT,
    STREAM_TYPE_HLS,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10


class IHeartRadioError(Exception):
    """Base exception for iHeartRadio API errors."""


class IHeartRadioConnectionError(IHeartRadioError):
    """Exception raised when network communication fails."""


class IHeartRadioStationNotFoundError(IHeartRadioError):
    """Exception raised when a requested station is not found."""


class IHeartRadioApiClient:
    """Async API Client for iHeartRadio public endpoints."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client with an existing aiohttp session."""
        self._session = session
        self._cache: dict[str, tuple[float, Any]] = {}
        self._headers = {
            "User-Agent": API_USER_AGENT,
            "Accept": "application/json",
        }

    async def _async_request(self, url: str) -> dict[str, Any]:
        """Perform an HTTP GET request with error handling and timeouts."""
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 404:
                    raise IHeartRadioStationNotFoundError(f"Resource not found: {url}")
                if response.status != 200:
                    text = await response.text()
                    raise IHeartRadioError(
                        f"API request failed with HTTP {response.status}: {text[:200]}"
                    )
                return await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error connecting to iHeartRadio at %s: %s", url, err)
            raise IHeartRadioConnectionError(
                f"Communication error with iHeartRadio API: {err}"
            ) from err

    async def async_search(self, keywords: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search live stations by keyword or callsign."""
        clean_query = keywords.strip()
        if not clean_query:
            return []
        url = f"{API_BASE_V1}/catalog/searchAll?keywords={quote(clean_query)}"
        data = await self._async_request(url)
        stations = data.get("stations", [])
        return stations[:limit]

    async def async_get_station(self, station_id: int | str) -> dict[str, Any]:
        """Fetch detailed metadata and stream URLs for a station ID."""
        url = f"{API_BASE_V2}/content/liveStations/{station_id}"
        data = await self._async_request(url)
        hits = data.get("hits", [])
        if not hits:
            raise IHeartRadioStationNotFoundError(f"Station ID {station_id} not found")
        return hits[0]

    async def async_get_stations_by_market(
        self, market_id: int | str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch live stations for a given market ID."""
        url = f"{API_BASE_V2}/content/liveStations?marketId={market_id}&limit={limit}"
        data = await self._async_request(url)
        return data.get("hits", [])

    async def async_get_stations_by_genre(
        self, genre_id: int | str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch live stations for a given genre ID."""
        url = f"{API_BASE_V2}/content/liveStations?genreId={genre_id}&limit={limit}"
        data = await self._async_request(url)
        return data.get("hits", [])

    async def async_get_markets(self) -> list[dict[str, Any]]:
        """Fetch list of markets."""
        url = f"{API_BASE_V2}/content/markets"
        data = await self._async_request(url)
        return data.get("hits", [])

    async def async_get_stream(
        self, station_id: int | str, stream_type: str = STREAM_TYPE_HLS
    ) -> tuple[str, str]:
        """Resolve playable stream URL and MIME type for a station."""
        station = await self.async_get_station(station_id)
        streams = station.get("streams", {})

        stream_url = ""
        mime_type = "audio/aac"

        if stream_type == STREAM_TYPE_HLS:
            # Prefer secure HLS, fallback to shoutcast
            stream_url = (
                streams.get("secure_hls_stream")
                or streams.get("hls_stream")
                or streams.get("secure_shoutcast_stream")
                or streams.get("shoutcast_stream")
            )
        else:
            # Prefer direct Shoutcast/AAC/MP3 stream, fallback to HLS
            stream_url = (
                streams.get("secure_shoutcast_stream")
                or streams.get("shoutcast_stream")
                or streams.get("secure_hls_stream")
                or streams.get("hls_stream")
            )

        if not stream_url:
            raise IHeartRadioStationNotFoundError(
                f"No active stream URL found for station ID {station_id}"
            )

        # Detect MIME type
        if ".m3u8" in stream_url:
            mime_type = "application/x-mpegurl"
        elif "aac" in stream_url.lower():
            mime_type = "audio/aac"
        else:
            mime_type = "audio/mpeg"

        return stream_url, mime_type
