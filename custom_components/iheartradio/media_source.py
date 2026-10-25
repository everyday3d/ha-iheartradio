"""iHeartRadio Media Source Implementation."""
from __future__ import annotations

import logging

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source.error import MediaSourceError, Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant

from .api import IHeartRadioApiClient, IHeartRadioError
from .const import (
    ALL_US_MARKETS,
    CONF_DEFAULT_MARKET,
    CONF_STREAM_TYPE,
    DEFAULT_MARKET,
    DEFAULT_STREAM_TYPE,
    DOMAIN,
    POPULAR_GENRES,
    POPULAR_MARKETS,
    US_STATE_NAMES,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up iHeartRadio media source."""
    return IHeartRadioMediaSource(hass)


class IHeartRadioMediaSource(MediaSource):
    """Provide iHeartRadio stations as a media source."""

    name: str = "iHeartRadio"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize iHeartRadio media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _get_active_client(self) -> tuple[IHeartRadioApiClient, dict]:
        """Retrieve client and entry data from hass.data."""
        entries = self.hass.data.get(DOMAIN, {})
        if not entries:
            raise MediaSourceError("iHeartRadio integration is not configured")
        # Return first active entry
        entry_id = next(iter(entries))
        entry_bundle = entries[entry_id]
        return entry_bundle["client"], entry_bundle["entry"].options or entry_bundle["entry"].data

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item identifier to a playable URL."""
        client, options = self._get_active_client()
        identifier = item.identifier.lstrip("/")

        # Format: station/{station_id} or raw station_id
        if identifier.startswith("station/"):
            station_id = identifier.split("/", 1)[1]
        else:
            station_id = identifier

        stream_type = options.get(CONF_STREAM_TYPE, DEFAULT_STREAM_TYPE)

        try:
            stream_url, mime_type = await client.async_get_stream(station_id, stream_type=stream_type)
            _LOGGER.debug("Resolved iHeartRadio station %s to %s (%s)", station_id, stream_url, mime_type)
            return PlayMedia(url=stream_url, mime_type=mime_type)
        except IHeartRadioError as err:
            raise Unresolvable(f"Unable to resolve stream for iHeartRadio station {station_id}: {err}") from err

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse iHeartRadio categories and live stations."""
        client, options = self._get_active_client()
        identifier = item.identifier.lstrip("/") if item.identifier else ""
        default_market = options.get(CONF_DEFAULT_MARKET, DEFAULT_MARKET)

        # 1. Root Level
        if not identifier:
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"market/{default_market}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=f"📍 Local Market ({ALL_US_MARKETS.get(default_market, POPULAR_MARKETS.get(default_market, default_market))})",
                    can_play=False,
                    can_expand=True,
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="favorites",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="⭐ Favorite Stations",
                    can_play=False,
                    can_expand=True,
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="genres",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="🎸 Browse by Genre & Format",
                    can_play=False,
                    can_expand=True,
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="markets",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=f"🗺️ Browse All US Markets ({len(ALL_US_MARKETS)} Cities)",
                    can_play=False,
                    can_expand=True,
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="states",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="🇺🇸 Browse Markets by State",
                    can_play=False,
                    can_expand=True,
                ),
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="market/575",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="🌐 iHeartRadio Digital Exclusive Stations",
                    can_play=False,
                    can_expand=True,
                ),
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title="iHeartRadio",
                can_play=False,
                can_expand=True,
                children=children,
            )

        # 2. Browse by Markets List (Nationwide - All 274 Cities)
        if identifier == "markets":
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"market/{mid}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=f"📍 {mname}",
                    can_play=False,
                    can_expand=True,
                )
                for mid, mname in ALL_US_MARKETS.items()
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="markets",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title=f"All US Markets ({len(ALL_US_MARKETS)} Cities)",
                can_play=False,
                can_expand=True,
                children=children,
            )

        # 3. Browse by US State
        if identifier == "states":
            by_state: dict[str, int] = {}
            for mname in ALL_US_MARKETS.values():
                st = mname.split(", ")[-1] if ", " in mname else "US"
                by_state[st] = by_state.get(st, 0) + 1

            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"state/{st}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=f"🇺🇸 {US_STATE_NAMES.get(st, st)} ({count} Market{'s' if count != 1 else ''})",
                    can_play=False,
                    can_expand=True,
                )
                for st, count in sorted(by_state.items(), key=lambda x: US_STATE_NAMES.get(x[0], x[0]))
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="states",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title="Browse Markets by State",
                can_play=False,
                can_expand=True,
                children=children,
            )

        # 4. Markets in a Specific State
        if identifier.startswith("state/"):
            target_st = identifier.split("/", 1)[1].upper()
            state_name = US_STATE_NAMES.get(target_st, target_st)
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"market/{mid}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=f"📍 {mname}",
                    can_play=False,
                    can_expand=True,
                )
                for mid, mname in ALL_US_MARKETS.items()
                if mname.endswith(f", {target_st}")
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=identifier,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title=f"{state_name} Markets",
                can_play=False,
                can_expand=True,
                children=children,
            )

        # 5. Stations in a Specific Market
        if identifier.startswith("market/"):
            market_id = identifier.split("/", 1)[1]
            market_id = client.LEGACY_MARKET_MAP.get(market_id, market_id)
            market_name = ALL_US_MARKETS.get(market_id, POPULAR_MARKETS.get(market_id, f"Market {market_id}"))
            try:
                raw_stations = await client.async_get_stations_by_market(market_id, limit=60)
            except IHeartRadioError as err:
                raise MediaSourceError(f"Could not load market stations: {err}") from err

            children = [self._build_station_item(st) for st in raw_stations if st.get("id")]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=identifier,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title=f"Stations in {market_name}",
                can_play=False,
                can_expand=True,
                children=children,
            )

        # 4. Browse by Genres List
        if identifier == "genres":
            children = [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"genre/{gid}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=f"🎵 {gname}",
                    can_play=False,
                    can_expand=True,
                )
                for gid, gname in POPULAR_GENRES.items()
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="genres",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title="Genres & Formats",
                can_play=False,
                can_expand=True,
                children=children,
            )

        # 5. Stations in a Specific Genre
        if identifier.startswith("genre/"):
            genre_id = identifier.split("/", 1)[1]
            genre_name = POPULAR_GENRES.get(int(genre_id) if genre_id.isdigit() else 0, f"Genre {genre_id}")
            try:
                raw_stations = await client.async_get_stations_by_genre(genre_id, limit=60)
            except IHeartRadioError as err:
                raise MediaSourceError(f"Could not load genre stations: {err}") from err

            children = [self._build_station_item(st) for st in raw_stations if st.get("id")]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=identifier,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title=f"{genre_name} Stations",
                can_play=False,
                can_expand=True,
                children=children,
            )

        # 6. Favorites List
        if identifier == "favorites":
            entries = self.hass.data.get(DOMAIN, {})
            coordinator = None
            for bundle in entries.values():
                if "coordinator" in bundle:
                    coordinator = bundle["coordinator"]
                    break

            stations = coordinator.favorite_stations if coordinator else []
            children = [self._build_station_item(st) for st in stations if st.get("id")]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="favorites",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title="Favorite Stations",
                can_play=False,
                can_expand=True,
                children=children,
            )

        raise MediaSourceError(f"Unknown media path: {identifier}")

    def _build_station_item(self, station: dict) -> BrowseMediaSource:
        """Construct a playable station BrowseMediaSource item."""
        st_id = str(station.get("id", ""))
        name = station.get("name") or station.get("callLetters") or f"Station {st_id}"
        freq = station.get("freq") or station.get("frequency") or ""
        call = station.get("callLetters") or ""

        # Title formatting: e.g. "Z100 (WHTZ-FM 100.3)" or "Lite FM (106.7)"
        details = " • ".join(filter(None, [call, str(freq) if freq else None]))
        title = f"{name} ({details})" if details else name

        logo = station.get("logo") or station.get("newlogo")
        if not logo and st_id:
            logo = f"https://i.iheart.com/v3/re/assets/images/{st_id}.png"

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"station/{st_id}",
            media_class=MediaClass.MUSIC,
            media_content_type=MediaType.MUSIC,
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=logo,
        )
