# Rust + WebAssembly static dashboard

Application state, API requests, normalization, Cathay filtering, aircraft metadata, flight cards and hourly aggregations run in Rust compiled to WebAssembly. A small JavaScript bridge renders the Leaflet map. The deployed website needs no Python runtime or application server.

## Feature parity

- Today's passenger arrivals/departures, counting each official movement once, including codeshares.
- Live map with the same 30–150 NM radius, Cathay-only filter, heading-aligned aircraft, tooltips and click-to-detail.
- Registration, ICAO type, model, altitude, speed, track and the same 30-model engine-family reference.
- Seven current/upcoming CX departure cards, with recent departures filling remaining slots: scheduled time, destination, terminal, gate and status.
- Full 24-hour grouped arrivals/departures chart.
- 60-second refresh toggle, manual refresh, five-minute flight-board cache, errors and OpenSky fallback.

The UI uses a system font, light map and restrained blue accents. Aircraft icons stay at 26px when zooming. Selection and map position survive refreshes. Layout adapts to mobile, controls have keyboard focus indicators and motion respects reduced-motion preferences.

## Run and build

The map uses standard OpenStreetMap tiles, visible attribution and normal browser caching. No map API key is required. Leaflet is vendored locally.

Install [Rust](https://rustup.rs/) and [Trunk](https://trunkrs.dev/):

```sh
rustup target add wasm32-unknown-unknown
cargo install trunk --version 0.21.14 --locked
cargo install wasm-bindgen-cli --version 0.2.104 --locked
cargo run --manifest-path collector/Cargo.toml
trunk serve
```

Open `http://127.0.0.1:8080`. If the shell sets `NO_COLOR=1`, use `env -u NO_COLOR trunk serve` because Trunk expects a boolean.

```sh
cargo fmt --check
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
trunk build --release --locked --public-url ./
```

`dist/` contains the deployable HTML, CSS, JavaScript, WASM and snapshot JSON. Serve it over HTTP/HTTPS; `file://` cannot load this app correctly. Relative URLs support GitHub Pages repository subpaths.

## GitHub Pages

Repository: https://github.com/rickypang0219/hkg-skywatch

Project website (available after Pages is enabled): https://rickypang0219.github.io/hkg-skywatch/

This project uses its own repository subpath. It does not modify the personal website repository or the root URL `https://rickypang0219.github.io/`. No custom domain is configured.

1. Push this repository to GitHub on `main`.
2. In **Settings → Pages → Build and deployment**, choose **GitHub Actions**.
3. Run **Build and deploy WebAssembly dashboard**, or push a commit.

The workflow tests Rust, collects official HKIA data, builds WASM and deploys Pages. A scheduled run requests a refresh every five minutes. GitHub schedules can run late, consume Actions resources, and may be disabled after inactivity. Data collection/deployment start only when the workflow runs in your repository.

Actions cache retains the latest same-day flight snapshot if HKIA temporarily fails. Cache eviction is possible. Missing and previous-day snapshots are not shown as today's flights. No API keys or public CORS proxy are used.

## Data access

| Data | Source | Static website behavior |
| --- | --- | --- |
| Schedule, status, terminal and gate | [Official HKIA JSON](https://data.gov.hk/en-data/dataset/aahk-team1-flight-info) | Browser request, then same-origin official snapshot collected by native Rust |
| Aircraft position and metadata | [ADSB.lol](https://api.adsb.lol/) | Browser fetch every 60 seconds |
| Position fallback | [OpenSky](https://openskynetwork.github.io/opensky-api/rest.html) | Anonymous bounding-box fetch, subject to CORS and quota |
| Aircraft/engine model | Rust reference table | No network needed |

On 3 October 2026, the native Rust collector successfully obtained both official HKIA boards, even though the earlier curl probe returned HTTP 403. The collected JSON includes the official update time. ADSB.lol did not return `Access-Control-Allow-Origin` for the tested origin. Static hosting cannot bypass upstream CORS or anti-bot protection. The app exposes failures and attempts the existing fallback. **Deployment success does not guarantee live API availability.** Reliable 60-second positions require a browser-accessible upstream or server-side relay if both sources disallow browser requests. A GitHub Actions snapshot is not an equivalent real-time replacement; the app does not silently use stale aircraft positions.

HKIA has no separate boarding timestamp; cards show scheduled time and live status. Engines are model-family references, not verified installations for individual aircraft. Community ADS-B coverage is best effort, particularly on the ground.

## Structure

```text
src/lib.rs          Transformations, aggregation and aircraft reference
src/browser.rs      Rust/WASM rendering, refresh and selection state
collector/          Standalone native Rust official-flight snapshot collector
web/map.js          Leaflet rendering bridge
web/shell.html      Dashboard layout
web/style.css       Apple-inspired responsive design
assets/            Pinned Leaflet renderer and BSD license (served locally)
data/flights.json   Official-flight snapshot with collection/update times
.github/workflows/pages.yml   Test, collect, build and deploy
```

The Python app remains as a feature-parity reference. GitHub Pages does not deploy it.

On macOS, `.cargo/config.toml` selects Apple's system linker so Chinese project paths work even when a Nix compiler wrapper is first on PATH. GitHub Actions uses its normal Linux toolchain.

Browser regression checks (development only, with `trunk serve` running in another terminal):

```sh
uv run python tests/wasm_ui_smoke.py
```

Fixtures intercept upstream requests only in the test browser. They are not shipped as dashboard data. The check covers aircraft selection across refresh, filters, hourly bars, mobile overflow, official snapshot fallback, OpenSky fallback and rejection of previous-day snapshots. Set `HKG_TEST_URL` to test an alternative server or repository subpath.

## Verified locally

- Production static bundle generated successfully with Trunk 0.21.14 and wasm-bindgen 0.2.104.
- Native Rust tests, native/collector/WASM Clippy and formatting checks passed.
- Real browser checks passed for the root URL and a GitHub Pages-style subpath; no page errors.
- Aircraft selection survives a 60-second refresh. Cathay filter, mobile marker alignment, hourly counts, snapshot/OpenSky fallback and stale-date rejection passed.
- On 3 October 2026, the real browser showed 437 arrivals and 439 departures from the official snapshot. Live aircraft endpoints timed out in this environment; the UI reported unavailability. Mocked response tests prove the interaction path, not upstream availability.

On 3 October 2026, the first GitHub Actions run passed all Rust tests, formatting, Clippy, official-flight collection and production WASM build. The static artifact uploaded successfully. Deployment returned HTTP 404 because GitHub Pages is not yet enabled for this repository. Choose **Settings → Pages → Build and deployment → Source: GitHub Actions**, then rerun the failed deployment job. Run: https://github.com/rickypang0219/hkg-skywatch/actions/runs/37130083279
