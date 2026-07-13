"""Pure transformations from upstream payloads to dashboard-ready tables."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import pandas as pd

from .config import HKG_LAT, HKG_LON, HKG_TZ

FLIGHT_COLUMNS = [
    "date", "movement", "scheduled_at", "scheduled_time", "flight_numbers",
    "primary_flight", "airlines", "destination", "terminal", "aisle", "gate",
    "status", "status_code", "last_updated",
]
AIRCRAFT_COLUMNS = [
    "icao24", "callsign", "display_flight", "registration", "type_code", "latitude",
    "longitude", "altitude_ft", "altitude_label", "speed_kt", "track",
    "vertical_rate_fpm", "on_ground", "is_cathay", "color", "distance_nm",
    "last_seen_seconds", "source",
]


def callsign_to_display(callsign: str | None) -> str:
    """Convert Cathay's ICAO callsign to its public-facing IATA flight number."""
    value = (callsign or "").strip().upper()
    match = re.fullmatch(r"CPA(\d+[A-Z]?)", value)
    return f"CX {match.group(1)}" if match else (value or "NO CALLSIGN")


def flatten_hkia_payload(
    payload: Iterable[dict[str, Any]], target_date: date, *, arrival: bool
) -> pd.DataFrame:
    """Flatten HKIA date buckets while preserving one row per movement."""
    rows: list[dict[str, Any]] = []
    target = target_date.isoformat()
    for day_bucket in payload:
        if day_bucket.get("date") != target:
            continue
        for movement in day_bucket.get("list") or []:
            flights = movement.get("flight") or []
            numbers = [str(item.get("no", "")).strip() for item in flights if item.get("no")]
            airlines = [
                str(item.get("airline", "")).strip()
                for item in flights
                if item.get("airline")
            ]
            scheduled_time = str(movement.get("time") or "").strip()
            try:
                scheduled_at = datetime.strptime(
                    f"{target} {scheduled_time}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=HKG_TZ)
            except ValueError:
                scheduled_at = pd.NaT
            location_key = "origin" if arrival else "destination"
            rows.append(
                {
                    "date": target,
                    "movement": "Arrival" if arrival else "Departure",
                    "scheduled_at": scheduled_at,
                    "scheduled_time": scheduled_time or "--:--",
                    "flight_numbers": " / ".join(numbers),
                    "primary_flight": numbers[0] if numbers else "Unknown",
                    "airlines": " / ".join(airlines),
                    "destination": " / ".join(movement.get(location_key) or []),
                    "terminal": movement.get("terminal") or "—",
                    "aisle": movement.get("aisle") or "—",
                    "gate": movement.get("gate") or "TBC",
                    "status": movement.get("status") or "Scheduled",
                    "status_code": movement.get("statusCode"),
                    "last_updated": day_bucket.get("lastUpdatedTime"),
                }
            )
    return pd.DataFrame(rows, columns=FLIGHT_COLUMNS)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _distance_nm(lat: float, lon: float) -> float:
    """Haversine distance from HKG in nautical miles."""
    radius_nm = 3440.065
    phi1, phi2 = math.radians(HKG_LAT), math.radians(lat)
    dphi = math.radians(lat - HKG_LAT)
    dlambda = math.radians(lon - HKG_LON)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return radius_nm * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_adsb_lol(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in payload.get("ac") or []:
        lat, lon = item.get("lat"), item.get("lon")
        if lat is None or lon is None:
            continue
        callsign = str(item.get("flight") or "").strip().upper()
        altitude_raw = item.get("alt_baro")
        on_ground = altitude_raw == "ground"
        altitude = 0.0 if on_ground else _to_float(altitude_raw)
        track = _to_float(item.get("track", item.get("calc_track"))) % 360
        is_cathay = callsign.startswith("CPA")
        rows.append(
            {
                "icao24": str(item.get("hex") or "").strip().lower(),
                "callsign": callsign or "NO CALLSIGN",
                "display_flight": callsign_to_display(callsign),
                "registration": str(item.get("r") or "Not available").strip(),
                "type_code": str(item.get("t") or "").strip().upper(),
                "latitude": float(lat),
                "longitude": float(lon),
                "altitude_ft": altitude,
                "altitude_label": "GROUND" if on_ground else f"{altitude:,.0f} FT",
                "speed_kt": _to_float(item.get("gs")),
                "track": track,
                "vertical_rate_fpm": _to_float(
                    item.get("baro_rate", item.get("geom_rate"))
                ),
                "on_ground": on_ground,
                "is_cathay": is_cathay,
                "color": [244, 185, 66, 255] if is_cathay else [75, 185, 213, 220],
                "distance_nm": _to_float(
                    item.get("dst"), _distance_nm(float(lat), float(lon))
                ),
                "last_seen_seconds": _to_float(item.get("seen")),
                "source": "ADSB.lol",
            }
        )
    frame = pd.DataFrame(rows, columns=AIRCRAFT_COLUMNS)
    return frame.sort_values(
        ["is_cathay", "distance_nm"], ascending=[False, True], ignore_index=True
    )


def parse_opensky(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for state in payload.get("states") or []:
        if len(state) < 17 or state[5] is None or state[6] is None:
            continue
        callsign = str(state[1] or "").strip().upper()
        is_cathay = callsign.startswith("CPA")
        altitude_ft = _to_float(state[7]) * 3.28084
        on_ground = bool(state[8])
        lat, lon = float(state[6]), float(state[5])
        rows.append(
            {
                "icao24": str(state[0] or "").strip().lower(),
                "callsign": callsign or "NO CALLSIGN",
                "display_flight": callsign_to_display(callsign),
                "registration": "Not available from OpenSky live feed",
                "type_code": "",
                "latitude": lat,
                "longitude": lon,
                "altitude_ft": altitude_ft,
                "altitude_label": "GROUND" if on_ground else f"{altitude_ft:,.0f} FT",
                "speed_kt": _to_float(state[9]) * 1.94384,
                "track": _to_float(state[10]) % 360,
                "vertical_rate_fpm": _to_float(state[11]) * 196.8504,
                "on_ground": on_ground,
                "is_cathay": is_cathay,
                "color": [244, 185, 66, 255] if is_cathay else [75, 185, 213, 220],
                "distance_nm": _distance_nm(lat, lon),
                "last_seen_seconds": 0,
                "source": "OpenSky",
            }
        )
    frame = pd.DataFrame(rows, columns=AIRCRAFT_COLUMNS)
    return frame.sort_values(
        ["is_cathay", "distance_nm"], ascending=[False, True], ignore_index=True
    )


def hourly_movements(arrivals: pd.DataFrame, departures: pd.DataFrame) -> pd.DataFrame:
    """Return a complete 24-hour movement table for the grouped bar chart."""
    frames: list[pd.DataFrame] = []
    for name, frame in (("Arrivals", arrivals), ("Departures", departures)):
        if frame.empty:
            continue
        valid = frame.dropna(subset=["scheduled_at"]).copy()
        valid["hour"] = valid["scheduled_at"].map(lambda value: value.hour)
        counts = (
            valid.groupby("hour", as_index=False)
            .size()
            .rename(columns={"size": "movements"})
        )
        counts["series"] = name
        frames.append(counts)
    base = pd.MultiIndex.from_product(
        [range(24), ["Arrivals", "Departures"]], names=["hour", "series"]
    ).to_frame(index=False)
    observed = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["hour", "movements", "series"])
    )
    result = base.merge(observed, on=["hour", "series"], how="left")
    result["movements"] = result["movements"].fillna(0).astype(int)
    result["hour_label"] = result["hour"].map(lambda value: f"{value:02d}:00")
    return result


def cathay_departure_board(
    departures: pd.DataFrame, *, now: datetime, limit: int = 8
) -> pd.DataFrame:
    """Prioritise current/future CX movements, retaining recent flights as fallback."""
    if departures.empty:
        return departures.copy()
    cx = departures[
        departures["flight_numbers"].str.contains(r"(?:^| / )CX ", regex=True)
    ].copy()
    cx["primary_flight"] = cx["flight_numbers"].map(
        lambda value: next(
            (flight for flight in str(value).split(" / ") if flight.startswith("CX ")),
            "CX",
        )
    )
    cx = cx.sort_values("scheduled_at")
    future = cx[cx["scheduled_at"] >= now]
    if len(future) >= limit:
        return future.head(limit)
    recent = cx[cx["scheduled_at"] < now].tail(limit - len(future))
    return pd.concat([recent, future], ignore_index=True).head(limit)


def status_tone(status: str | None) -> tuple[str, str]:
    """Return a status label and a UI tone token."""
    value = (status or "Scheduled").strip()
    lowered = value.lower()
    if "boarding" in lowered or "final call" in lowered:
        return value, "active"
    if "cancel" in lowered:
        return value, "critical"
    if "delay" in lowered:
        return value, "warning"
    if lowered.startswith("dep") or "closed" in lowered:
        return value, "muted"
    return value, "scheduled"
