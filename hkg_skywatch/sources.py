"""HTTP clients for the public aviation data sources used by the MVP."""

from __future__ import annotations

from datetime import date
from typing import Any

import requests

from .config import (
    ADSB_LOL_BASE_URL,
    HKG_LAT,
    HKG_LON,
    HKIA_FLIGHTS_URL,
    OPENSKY_STATES_URL,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)


class DataSourceError(RuntimeError):
    """A user-safe wrapper around upstream request and schema failures."""


def _get_json(url: str, *, params: dict[str, Any] | None = None) -> Any:
    try:
        response = requests.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise DataSourceError(f"{url} is unavailable: {exc}") from exc


def fetch_hkia_flights(target_date: date, *, arrival: bool) -> list[dict[str, Any]]:
    """Fetch HKIA passenger movements for one local calendar date."""
    payload = _get_json(
        HKIA_FLIGHTS_URL,
        params={
            "span": 1,
            "date": target_date.isoformat(),
            "lang": "en",
            "cargo": "false",
            "arrival": str(arrival).lower(),
        },
    )
    if not isinstance(payload, list):
        raise DataSourceError("HKIA returned an unexpected payload shape")
    return payload


def fetch_adsb_lol_aircraft(radius_nm: int) -> dict[str, Any]:
    """Fetch aircraft around HKG with registration and ICAO type enrichment."""
    url = f"{ADSB_LOL_BASE_URL}/v2/lat/{HKG_LAT}/lon/{HKG_LON}/dist/{radius_nm}"
    payload = _get_json(url)
    if not isinstance(payload, dict) or not isinstance(payload.get("ac"), list):
        raise DataSourceError("ADSB.lol returned an unexpected payload shape")
    return payload


def fetch_opensky_aircraft(radius_nm: int) -> dict[str, Any]:
    """Fetch anonymous OpenSky state vectors as a resilient fallback."""
    lat_delta = radius_nm / 60
    lon_delta = radius_nm / 55.6
    payload = _get_json(
        OPENSKY_STATES_URL,
        params={
            "lamin": round(HKG_LAT - lat_delta, 4),
            "lomin": round(HKG_LON - lon_delta, 4),
            "lamax": round(HKG_LAT + lat_delta, 4),
            "lomax": round(HKG_LON + lon_delta, 4),
            "extended": 1,
        },
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("states"), list):
        raise DataSourceError("OpenSky returned an unexpected payload shape")
    return payload


def fetch_live_aircraft(radius_nm: int) -> tuple[dict[str, Any], str, str | None]:
    """Use the richer no-key feed first, then transparently fall back to OpenSky."""
    try:
        return fetch_adsb_lol_aircraft(radius_nm), "ADSB.lol", None
    except DataSourceError as primary_error:
        try:
            return fetch_opensky_aircraft(radius_nm), "OpenSky", str(primary_error)
        except DataSourceError as fallback_error:
            raise DataSourceError(
                f"Both live position sources failed. {primary_error}; {fallback_error}"
            ) from fallback_error
