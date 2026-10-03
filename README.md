# HKG Skywatch

The app has been rewritten in **Rust + WebAssembly** with an Apple-inspired UI and a GitHub Pages deployment workflow. See [RUST_README.md](RUST_README.md) for current setup, static deployment and data-access limitations. The Python files below remain as a reference and are not deployed.

A near-real-time Streamlit dashboard for Hong Kong International Airport (VHHH/HKG). It combines the official HKIA movement board with volunteer ADS-B feeds so an aviation enthusiast can monitor today's passenger movements, inspect live aircraft, and watch Cathay Pacific departures.

## MVP features

- Today's scheduled passenger arrivals and departures, counted as airport movements (codeshares are not double-counted)
- A 24-hour arrivals/departures rhythm chart
- A clickable live aircraft map around HKG, with a Cathay-only filter
- Selected-aircraft registration, ICAO type designator, altitude, speed and track
- A version-controlled reference from common aircraft types to model and engine family
- A CX departure panel with scheduled time, destination, live HKIA status and gate
- 60-second near-real-time refresh, caching, visible errors, and OpenSky fallback

The MVP does **not** require an account or API key.

## Run locally

```bash
uv sync
uv run streamlit run app.py
```

Open the local URL printed by Streamlit (normally `http://localhost:8501`).

Validation:

```bash
uv run ruff check .
uv run pytest
```

## Data sources and trust boundaries

| Need | Source | Access | Important limitation |
| --- | --- | --- | --- |
| Schedule, status, terminal, aisle and gate | [Airport Authority Hong Kong via DATA.GOV.HK](https://data.gov.hk/en-data/dataset/aahk-team1-flight-info) | Official JSON; no key | Exposes scheduled time and live status, but not a separate boarding timestamp |
| Live position and aircraft metadata | [ADSB.lol API](https://api.adsb.lol/) | Community ADS-B; currently no key | Best-effort coverage; public terms warn a key may be required in future |
| Live position fallback | [OpenSky REST API](https://openskynetwork.github.io/opensky-api/rest.html) | Anonymous; 400 daily credits | Live state vectors do not include registration/type; coverage is receiver-dependent |
| Model/engine family | `hkg_skywatch/aircraft_types.py` | Local and version controlled | A type-family reference, not confirmation of a particular airframe's installed engine |

This app does not scrape HKIA HTML. It uses the documented JSON endpoint. ADS-B coordinates are observational and must not be used for navigation, safety, or operational decisions.

## Data flow

```text
HKIA official JSON ──> one row per movement ──> KPIs / hourly chart / CX board

ADSB.lol live radius ──> normalized aircraft ──> click map / aircraft detail
          │
          └─ on failure: OpenSky anonymous bounding box (position-only fallback)

ICAO type code ──> version-controlled model + engine-family reference
```

## Engine reference caveat

The live feed normally provides an ICAO type designator, not a verified engine serial or sub-variant. The lookup correctly distinguishes these examples:

- `B77W` = Boeing 777-300ER = GE90-115B
- `B779` = Boeing 777-9 = GE9X

Some models have multiple engine options, so the UI shows all common families rather than guessing the exact installed engine.

## Next phases

1. Persist daily HKIA snapshots to Parquet/DuckDB and add delay/route trends.
2. Create an OpenSky OAuth client only if you need the higher authenticated quota or five-second resolution. Store credentials in Streamlit secrets; never commit them.
3. Version an OpenSky aircraft metadata snapshot for richer offline fallback joins.
4. Move polling to a FastAPI/WebSocket service if smooth animation or many concurrent viewers becomes a requirement.
5. Deploy to Streamlit Community Cloud after reviewing public-source rate limits and adding uptime monitoring.
