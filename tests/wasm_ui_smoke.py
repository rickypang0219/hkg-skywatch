"""Exercise the WASM bundle with deterministic upstream fixtures, never production demo data."""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

date = datetime.now(ZoneInfo("Asia/Hong_Kong")).date().isoformat()
flight = [
    {
        "date": date,
        "lastUpdatedTime": date + "T12:00:00+08:00",
        "list": [
            {
                "time": "23:59",
                "flight": [{"no": "BA 701"}, {"no": "CX 101"}],
                "destination": ["LHR"],
                "origin": ["LHR"],
                "gate": "25",
                "terminal": "T1",
                "status": "Boarding",
            }
        ],
    }
]
planes = {
    "ac": [
        {
            "hex": "780abc",
            "flight": "CPA101",
            "r": "B-KQZ",
            "t": "B77W",
            "lat": 22.308,
            "lon": 113.9185,
            "alt_baro": "ground",
            "gs": 0,
            "track": 40,
        },
        {
            "hex": "780def",
            "flight": "UAE366",
            "r": "A6-ABC",
            "t": "A388",
            "lat": 22.50,
            "lon": 114.1,
            "alt_baro": 15000,
            "gs": 300,
            "track": 120,
        },
    ]
}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    page.clock.install()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route(
        "**/flightinfo-rest/**",
        lambda r: r.fulfill(json=flight, headers={"access-control-allow-origin": "*"}),
    )
    page.route(
        "https://api.adsb.lol/**",
        lambda r: r.fulfill(json=planes, headers={"access-control-allow-origin": "*"}),
    )
    page.goto(os.environ.get("HKG_TEST_URL", "http://127.0.0.1:8080"), wait_until="networkidle")
    page.locator("#tracked").get_by_text("2", exact=True).wait_for()
    assert page.locator("#arrivals").inner_text() == "1"
    assert page.locator("#departures").inner_text() == "1"
    assert page.locator("#board .flight").count() == 1
    assert "GE90-115B" in page.locator("#detail").inner_text()
    page.locator('[data-aircraft-id="780def"]').click()
    assert "Airbus A380-800" in page.locator("#detail").inner_text()
    page.clock.fast_forward(61_000)
    page.get_by_role("button", name="Refresh now").wait_for()
    assert "Airbus A380-800" in page.locator("#detail").inner_text()
    page.get_by_role("button", name="Refresh now").click()
    page.get_by_role("button", name="Refresh now").wait_for()
    assert "Airbus A380-800" in page.locator("#detail").inner_text()
    page.locator("#cathay").check()
    assert page.locator("#tracked").inner_text() == "1"
    assert page.locator(".plane-marker").count() == 1
    assert "Boeing 777-300ER" in page.locator("#detail").inner_text()
    page.locator("#auto").uncheck()
    assert not page.locator("#auto").is_checked()
    assert page.locator(".hour").count() == 24
    page.screenshot(path="/tmp/hkg-wasm-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(600)  # Leaflet debounces window-resize invalidation.
    map_bounds = page.locator("#map").bounding_box()
    marker_bounds = page.locator('[data-aircraft-id="780abc"]').bounding_box()
    assert map_bounds and marker_bounds
    assert map_bounds["x"] <= marker_bounds["x"] <= map_bounds["x"] + map_bounds["width"]
    assert map_bounds["y"] <= marker_bounds["y"] <= map_bounds["y"] + map_bounds["height"]
    page.screenshot(path="/tmp/hkg-wasm-mobile.png", full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # Exercise the two static-hosting fallbacks rather than assuming APIs always work.
    page.route(
        "**/flightinfo-rest/**",
        lambda r: r.fulfill(
            status=503, body="Unavailable", headers={"access-control-allow-origin": "*"}
        ),
    )
    page.route(
        "**/data/flights.json*",
        lambda r: r.fulfill(
            json={
                "date": date,
                "generated_at": date + "T12:00:00+08:00",
                "arrivals": flight,
                "departures": flight,
                "errors": [],
            }
        ),
    )
    page.route(
        "https://api.adsb.lol/**",
        lambda r: r.fulfill(
            status=503, body="Unavailable", headers={"access-control-allow-origin": "*"}
        ),
    )
    page.route(
        "https://opensky-network.org/**",
        lambda r: r.fulfill(
            json={
                "states": [
                    [
                        "780abc",
                        "CPA101",
                        "China",
                        1,
                        1,
                        113.9185,
                        22.308,
                        1000,
                        False,
                        100,
                        90,
                        5,
                        None,
                        1100,
                        "1234",
                        False,
                        0,
                    ]
                ]
            },
            headers={"access-control-allow-origin": "*"},
        ),
    )
    page.get_by_role("button", name="Refresh now").click()
    page.locator("#map-source").get_by_text("OpenSky", exact=False).wait_for()
    page.locator("#alerts").get_by_text("Official snapshot", exact=False).wait_for()
    assert page.locator("#arrivals").inner_text() == "1"
    assert "Not available from OpenSky" in page.locator("#detail").inner_text()
    page.route(
        "**/data/flights.json*",
        lambda r: r.fulfill(json={"date": "2000-01-01", "arrivals": flight, "departures": flight}),
    )
    page.reload(wait_until="networkidle")
    page.locator("#alerts").get_by_text("no snapshot for today", exact=False).wait_for()
    assert page.locator("#arrivals").inner_text() == "0"
    assert not errors, errors
    print(
        json.dumps(
            {
                "page_errors": errors,
                "selection": "passed",
                "filter": "passed",
                "codeshares": "passed",
                "mobile": "passed",
                "snapshot_and_opensky_fallback": "passed",
                "stale_date_rejected": "passed",
            }
        )
    )
    browser.close()
