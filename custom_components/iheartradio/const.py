"""Constants for the iHeartRadio Home Assistant integration."""
from typing import Final

DOMAIN: Final = "iheartradio"
DEFAULT_NAME: Final = "iHeartRadio"

# Configuration and Options keys
CONF_STREAM_TYPE: Final = "stream_type"
CONF_DEFAULT_MARKET: Final = "default_market"
CONF_FAVORITES: Final = "favorites"

# Stream types
STREAM_TYPE_DIRECT: Final = "direct"
STREAM_TYPE_HLS: Final = "hls"
DEFAULT_STREAM_TYPE: Final = STREAM_TYPE_DIRECT

# Default market (New York)
DEFAULT_MARKET: Final = "159"

# API Endpoints
API_BASE_V1: Final = "https://api.iheart.com/api/v1"
API_BASE_V2: Final = "https://api.iheart.com/api/v2"
API_USER_AGENT: Final = "HomeAssistant-iHeartRadio/1.0.0 (https://github.com/everyday3d/ha-iheartradio)"

# Well-known US Markets (Verified API Market IDs)
POPULAR_MARKETS: Final[dict[str, str]] = {
    "159": "New York, NY",
    "187": "Los Angeles, CA",
    "84": "Chicago, IL",
    "145": "Dallas-Ft. Worth, TX",
    "171": "Houston, TX",
    "61": "Atlanta, GA",
    "205": "Philadelphia, PA",
    "42": "Washington, DC",
    "14": "Phoenix, AZ",
    "99": "Boston, MA",
    "193": "Miami-Ft. Lauderdale, FL",
    "245": "Seattle-Tacoma, WA",
    "219": "San Francisco, CA",
    "147": "Denver, CO",
    "111": "Detroit, MI",
    "197": "Minneapolis-St. Paul, MN",
    "237": "Tampa-St. Petersburg, FL",
    "217": "San Diego, CA",
    "119": "St. Louis, MO",
    "131": "Baltimore, MD",
    "201": "Nashville, TN",
    "214": "Austin, TX",
    "152": "Las Vegas, NV",
    "192": "Portland, OR",
    "141": "Charlotte, NC",
    "226": "San Antonio, TX",
    "51": "Orlando, FL",
    "169": "Cleveland, OH",
    "168": "Cincinnati, OH",
    "252": "Milwaukee, WI",
    "170": "Columbus, OH",
    "575": "Digital National (iHeart Exclusive)",
}

# Popular Genres & Format IDs
POPULAR_GENRES: Final[dict[int, str]] = {
    16: "Top 40 & Pop",
    2: "Classic Rock",
    4: "Country",
    8: "Hip Hop & R&B",
    14: "News & Talk",
    17: "Sports",
    1: "Alternative Rock",
    11: "80s & 90s Hits",
    13: "Adult Contemporary / Mix",
    10: "Jazz & Blues",
    3: "Comedy",
    7: "Dance & Electronic",
    12: "Christian & Gospel",
    1201: "iHeartRadio Originals",
}

# Media classes and types
MEDIA_TYPE_RADIO: Final = "radio"
MEDIA_TYPE_STATION: Final = "station"
