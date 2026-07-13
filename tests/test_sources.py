from datetime import date
from unittest.mock import Mock, patch

import pytest

from hkg_skywatch.sources import DataSourceError, fetch_hkia_flights, fetch_live_aircraft


@patch("hkg_skywatch.sources.requests.get")
def test_hkia_request_uses_no_credentials(mock_get):
    response = Mock()
    response.json.return_value = []
    response.raise_for_status.return_value = None
    mock_get.return_value = response
    assert fetch_hkia_flights(date(2026, 7, 13), arrival=False) == []
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["arrival"] == "false"
    assert "Authorization" not in kwargs["headers"]


@patch("hkg_skywatch.sources.fetch_opensky_aircraft")
@patch("hkg_skywatch.sources.fetch_adsb_lol_aircraft")
def test_live_source_falls_back_to_opensky(mock_adsb, mock_opensky):
    mock_adsb.side_effect = DataSourceError("primary unavailable")
    mock_opensky.return_value = {"states": []}
    payload, source, note = fetch_live_aircraft(80)
    assert payload == {"states": []}
    assert source == "OpenSky"
    assert "primary unavailable" in note


@patch("hkg_skywatch.sources.fetch_opensky_aircraft")
@patch("hkg_skywatch.sources.fetch_adsb_lol_aircraft")
def test_live_source_reports_both_failures(mock_adsb, mock_opensky):
    mock_adsb.side_effect = DataSourceError("primary unavailable")
    mock_opensky.side_effect = DataSourceError("fallback unavailable")
    with pytest.raises(DataSourceError, match="Both live position sources failed"):
        fetch_live_aircraft(80)
