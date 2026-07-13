from datetime import date, datetime

from hkg_skywatch.aircraft_types import describe_aircraft
from hkg_skywatch.config import HKG_TZ
from hkg_skywatch.transforms import (
    callsign_to_display,
    cathay_departure_board,
    flatten_hkia_payload,
    hourly_movements,
    parse_adsb_lol,
    parse_opensky,
)


def sample_hkia_payload():
    return [
        {
            "date": "2026-07-13",
            "list": [
                {
                    "time": "18:30",
                    "flight": [
                        {"no": "CX 101", "airline": "CPA"},
                        {"no": "BA 7001", "airline": "BAW"},
                    ],
                    "status": "Boarding",
                    "destination": ["LHR"],
                    "terminal": "T1",
                    "aisle": "B",
                    "gate": "25",
                },
                {
                    "time": "20:00",
                    "flight": [{"no": "HX 100", "airline": "CRK"}],
                    "status": None,
                    "destination": ["NRT"],
                    "terminal": "T1",
                    "gate": None,
                },
            ],
            "lastUpdatedTime": "2026-07-13T17:00:00+08:00",
        }
    ]


def test_flatten_hkia_counts_movements_not_codeshares():
    frame = flatten_hkia_payload(sample_hkia_payload(), date(2026, 7, 13), arrival=False)
    assert len(frame) == 2
    assert frame.iloc[0]["flight_numbers"] == "CX 101 / BA 7001"
    assert frame.iloc[0]["destination"] == "LHR"
    assert frame.iloc[1]["gate"] == "TBC"


def test_cathay_board_filters_and_orders_upcoming():
    frame = flatten_hkia_payload(sample_hkia_payload(), date(2026, 7, 13), arrival=False)
    board = cathay_departure_board(
        frame,
        now=datetime(2026, 7, 13, 17, 0, tzinfo=HKG_TZ),
        limit=7,
    )
    assert board["primary_flight"].tolist() == ["CX 101"]


def test_cathay_board_displays_cx_number_when_not_primary_codeshare():
    payload = sample_hkia_payload()
    payload[0]["list"][0]["flight"] = [
        {"no": "UO 558", "airline": "HKE"},
        {"no": "CX 5058", "airline": "CPA"},
    ]
    frame = flatten_hkia_payload(payload, date(2026, 7, 13), arrival=False)
    board = cathay_departure_board(
        frame,
        now=datetime(2026, 7, 13, 17, 0, tzinfo=HKG_TZ),
        limit=7,
    )
    assert board.iloc[0]["primary_flight"] == "CX 5058"


def test_adsb_payload_keeps_type_and_registration():
    payload = {
        "ac": [
            {
                "hex": "780abc",
                "flight": "CPA101 ",
                "r": "B-KQZ",
                "t": "B77W",
                "lat": 22.3,
                "lon": 113.9,
                "alt_baro": 12000,
                "gs": 300,
                "track": 87,
                "seen": 0.4,
            }
        ]
    }
    row = parse_adsb_lol(payload).iloc[0]
    assert row["display_flight"] == "CX 101"
    assert row["type_code"] == "B77W"
    assert row["registration"] == "B-KQZ"
    assert row["is_cathay"]


def test_opensky_units_are_converted():
    payload = {
        "states": [
            [
                "780abc", "CPA101 ", "China", 1, 1, 113.9, 22.3, 1000.0, False,
                100.0, 90.0, 5.0, None, 1100.0, "1234", False, 0, 0,
            ]
        ]
    }
    row = parse_opensky(payload).iloc[0]
    assert round(row["altitude_ft"]) == 3281
    assert round(row["speed_kt"]) == 194
    assert round(row["vertical_rate_fpm"]) == 984


def test_hourly_table_is_complete_and_engine_mapping_is_correct():
    departures = flatten_hkia_payload(sample_hkia_payload(), date(2026, 7, 13), arrival=False)
    hourly = hourly_movements(departures.iloc[0:0], departures)
    assert len(hourly) == 48
    assert hourly.query("hour == 18 and series == 'Departures'")["movements"].item() == 1
    assert describe_aircraft("B77W").engine == "GE90-115B"
    assert describe_aircraft("B779").engine == "GE9X"


def test_callsign_to_display_only_rewrites_cathay():
    assert callsign_to_display("CPA960") == "CX 960"
    assert callsign_to_display("UAE366") == "UAE366"
