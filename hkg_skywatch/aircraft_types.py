"""Transparent ICAO type lookup for common aircraft seen at HKG."""

from typing import NamedTuple


class AircraftType(NamedTuple):
    manufacturer: str
    model: str
    engine: str


AIRCRAFT_TYPES: dict[str, AircraftType] = {
    "A20N": AircraftType("Airbus", "A320neo", "CFM LEAP-1A / PW1100G"),
    "A21N": AircraftType("Airbus", "A321neo", "CFM LEAP-1A / PW1100G"),
    "A319": AircraftType("Airbus", "A319", "CFM56-5 / IAE V2500"),
    "A320": AircraftType("Airbus", "A320", "CFM56-5 / IAE V2500"),
    "A321": AircraftType("Airbus", "A321", "CFM56-5 / IAE V2500"),
    "A332": AircraftType("Airbus", "A330-200", "CF6 / PW4000 / Trent 700"),
    "A333": AircraftType("Airbus", "A330-300", "CF6 / PW4000 / Trent 700"),
    "A339": AircraftType("Airbus", "A330-900neo", "Rolls-Royce Trent 7000"),
    "A359": AircraftType("Airbus", "A350-900", "Rolls-Royce Trent XWB-84"),
    "A35K": AircraftType("Airbus", "A350-1000", "Rolls-Royce Trent XWB-97"),
    "A388": AircraftType("Airbus", "A380-800", "Trent 900 / Engine Alliance GP7200"),
    "B38M": AircraftType("Boeing", "737 MAX 8", "CFM LEAP-1B"),
    "B39M": AircraftType("Boeing", "737 MAX 9", "CFM LEAP-1B"),
    "B738": AircraftType("Boeing", "737-800", "CFM56-7B"),
    "B739": AircraftType("Boeing", "737-900", "CFM56-7B"),
    "B744": AircraftType("Boeing", "747-400", "CF6 / PW4000 / RB211"),
    "B748": AircraftType("Boeing", "747-8", "GEnx-2B"),
    "B763": AircraftType("Boeing", "767-300", "CF6 / PW4000 / RB211"),
    "B772": AircraftType("Boeing", "777-200", "GE90 / PW4000 / Trent 800"),
    "B77L": AircraftType("Boeing", "777-200LR / 777F", "GE90-110B/115B"),
    "B77W": AircraftType("Boeing", "777-300ER", "GE90-115B"),
    "B778": AircraftType("Boeing", "777-8", "GE9X"),
    "B779": AircraftType("Boeing", "777-9", "GE9X"),
    "B788": AircraftType("Boeing", "787-8 Dreamliner", "GEnx-1B / Trent 1000"),
    "B789": AircraftType("Boeing", "787-9 Dreamliner", "GEnx-1B / Trent 1000"),
    "B78X": AircraftType("Boeing", "787-10 Dreamliner", "GEnx-1B / Trent 1000"),
    "E190": AircraftType("Embraer", "E190", "GE CF34-10E"),
    "E195": AircraftType("Embraer", "E195", "GE CF34-10E"),
    "E290": AircraftType("Embraer", "E190-E2", "Pratt & Whitney PW1900G"),
    "E295": AircraftType("Embraer", "E195-E2", "Pratt & Whitney PW1900G"),
}


def describe_aircraft(type_code: str | None) -> AircraftType:
    """Return a useful description while staying honest about unknown types."""
    code = (type_code or "").strip().upper()
    return AIRCRAFT_TYPES.get(
        code,
        AircraftType("Unknown", code or "Type not broadcast", "Engine data unavailable"),
    )
