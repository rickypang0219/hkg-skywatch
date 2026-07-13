"""Shared application configuration."""

from zoneinfo import ZoneInfo

HKG_LAT = 22.3080
HKG_LON = 113.9185
HKG_TZ = ZoneInfo("Asia/Hong_Kong")

HKIA_FLIGHTS_URL = "https://www.hongkongairport.com/flightinfo-rest/rest/flights"
ADSB_LOL_BASE_URL = "https://api.adsb.lol"
OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"

DEFAULT_RADIUS_NM = 80
REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = "hkg-skywatch/0.1 (personal non-commercial aviation dashboard)"
