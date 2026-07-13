"""Playwright smoke test for the rendered Streamlit application."""

import json

from playwright.sync_api import sync_playwright


def main() -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200}, device_scale_factor=1)
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded", timeout=30_000)
        page.get_by_text("HKG SKYWATCH", exact=True).wait_for(timeout=60_000)
        page.get_by_text("Today's arrivals", exact=True).wait_for(timeout=30_000)
        page.get_by_text("CX departure board · HKT", exact=True).wait_for(timeout=30_000)
        page.get_by_text("Scheduled passenger movements by hour", exact=False).wait_for(
            timeout=30_000
        )
        page.wait_for_timeout(3_000)
        page.screenshot(path="/tmp/hkg_skywatch.png", full_page=True)
        result = {
            "title": page.title(),
            "canvas_count": page.locator("canvas").count(),
            "flight_cards": page.locator(".flight-card").count(),
            "aircraft_cards": page.locator(".aircraft-card").count(),
            "console_errors": console_errors,
            "page_errors": page_errors,
            "screenshot": "/tmp/hkg_skywatch.png",
        }
        print(json.dumps(result, ensure_ascii=False))
        if page_errors:
            raise AssertionError(f"Browser page errors: {page_errors}")
        if console_errors:
            raise AssertionError(f"Browser console errors: {console_errors}")
        if result["canvas_count"] < 2:
            raise AssertionError("Expected both a map/chart render path to create canvases")
        if result["flight_cards"] < 1:
            raise AssertionError("Expected at least one live CX departure card")
        if result["aircraft_cards"] != 1:
            raise AssertionError("Expected the selected-aircraft detail card")
        browser.close()


if __name__ == "__main__":
    main()
