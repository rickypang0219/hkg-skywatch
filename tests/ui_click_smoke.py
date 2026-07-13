"""Reproduce aircraft selection around the dense HKG airport cluster."""

import json
import os
from time import monotonic

from playwright.sync_api import sync_playwright


def main() -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded", timeout=30_000)
        page.get_by_text("HKG SKYWATCH", exact=True).wait_for(timeout=60_000)
        page.locator("canvas").first.wait_for(timeout=30_000)
        map_box = page.locator("canvas").first.bounding_box()
        if not map_box:
            raise AssertionError("PyDeck map did not render")

        before = page.locator(".aircraft-call").inner_text()
        started = monotonic()
        # HKG sits close to the centre of the fixed map view. Offset clicks sample
        # the dense gate/ground-aircraft cluster without relying on a DOM marker.
        offsets = [(0.50, 0.50), (0.49, 0.52), (0.52, 0.48), (0.47, 0.50)]
        results: list[dict[str, object]] = []
        for x_ratio, y_ratio in offsets:
            page.mouse.click(
                map_box["x"] + map_box["width"] * x_ratio,
                map_box["y"] + map_box["height"] * y_ratio,
            )
            page.wait_for_timeout(2_000)
            title_visible = page.get_by_text("HKG SKYWATCH", exact=True).is_visible()
            detail = page.locator(".aircraft-call").inner_text() if title_visible else "missing"
            results.append({"visible": title_visible, "detail": detail})

        hold_seconds = int(os.environ.get("CLICK_HOLD_SECONDS", "0"))
        if hold_seconds:
            page.wait_for_timeout(hold_seconds * 1_000)
            results.append(
                {
                    "visible_after_hold": page.get_by_text(
                        "HKG SKYWATCH", exact=True
                    ).is_visible(),
                    "detail_after_hold": page.locator(".aircraft-call").inner_text(),
                }
            )

        page.screenshot(path="/tmp/hkg_skywatch_after_click.png", full_page=True)
        output = {
            "before": before,
            "click_results": results,
            "elapsed_seconds": round(monotonic() - started, 2),
            "hold_seconds": hold_seconds,
            "console_errors": console_errors,
            "page_errors": page_errors,
        }
        print(json.dumps(output, ensure_ascii=False))
        if not all(item.get("visible", item.get("visible_after_hold")) for item in results):
            raise AssertionError("App disappeared after an aircraft-map click")
        if console_errors or page_errors:
            raise AssertionError(
                f"Browser errors after click: console={console_errors}, page={page_errors}"
            )
        browser.close()


if __name__ == "__main__":
    main()
