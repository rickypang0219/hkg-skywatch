"""Streamlit entrypoint for the HKG Skywatch MVP."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from math import cos, radians, sin
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from hkg_skywatch.config import DEFAULT_RADIUS_NM, HKG_LAT, HKG_LON, HKG_TZ
from hkg_skywatch.presentation import aircraft_card, flight_board, inject_css
from hkg_skywatch.sources import DataSourceError, fetch_hkia_flights, fetch_live_aircraft
from hkg_skywatch.transforms import (
    AIRCRAFT_COLUMNS,
    cathay_departure_board,
    flatten_hkia_payload,
    hourly_movements,
    parse_adsb_lol,
    parse_opensky,
)

st.set_page_config(
    page_title="HKG Skywatch", page_icon="✈️", layout="wide", initial_sidebar_state="expanded"
)
st.markdown(inject_css(), unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_flight_board(target_date: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Load arrival and departure boards concurrently, cached for five minutes."""
    parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    warnings: list[str] = []
    payloads: dict[bool, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            arrival: pool.submit(fetch_hkia_flights, parsed_date, arrival=arrival)
            for arrival in (True, False)
        }
        for arrival, future in futures.items():
            try:
                payloads[arrival] = future.result()
            except DataSourceError as exc:
                payloads[arrival] = []
                warnings.append(str(exc))
    arrivals = flatten_hkia_payload(payloads[True], parsed_date, arrival=True)
    departures = flatten_hkia_payload(payloads[False], parsed_date, arrival=False)
    return arrivals, departures, warnings


@st.cache_data(ttl=55, show_spinner=False)
def load_aircraft(radius_nm: int) -> tuple[pd.DataFrame, str, str | None, str | None]:
    """Load live aircraft and expose source/fallback state for the UI."""
    try:
        payload, source, fallback_note = fetch_live_aircraft(radius_nm)
        aircraft = parse_adsb_lol(payload) if source == "ADSB.lol" else parse_opensky(payload)
        return aircraft, source, fallback_note, None
    except DataSourceError as exc:
        return pd.DataFrame(columns=AIRCRAFT_COLUMNS), "Unavailable", None, str(exc)


def plane_polygon(longitude: float, latitude: float, track: float) -> list[list[float]]:
    """Build a small heading-aligned aircraft silhouette in WGS84 coordinates."""
    outline = [
        (0.0, 1.65), (0.22, 0.3), (1.05, -0.2), (1.05, -0.52),
        (0.23, -0.35), (0.22, -0.88), (0.5, -1.15), (0.0, -1.02),
        (-0.5, -1.15), (-0.22, -0.88), (-0.23, -0.35), (-1.05, -0.52),
        (-1.05, -0.2), (-0.22, 0.3),
    ]
    theta = radians(track)
    # Keep targets readable without obscuring taxiways or overlapping heavily at HKG.
    scale = 0.004
    lon_scale = max(cos(radians(latitude)), 0.2)
    polygon: list[list[float]] = []
    for east, north in outline:
        rotated_east = east * cos(theta) + north * sin(theta)
        rotated_north = -east * sin(theta) + north * cos(theta)
        polygon.append(
            [longitude + rotated_east * scale / lon_scale, latitude + rotated_north * scale]
        )
    return polygon


def build_map(aircraft: pd.DataFrame) -> pdk.Deck:
    map_data = aircraft.copy()
    map_data["polygon"] = map_data.apply(
        lambda row: plane_polygon(row["longitude"], row["latitude"], row["track"]), axis=1
    )
    aircraft_layer = pdk.Layer(
        "PolygonLayer",
        id="aircraft",
        data=map_data,
        pickable=True,
        auto_highlight=True,
        get_polygon="polygon",
        get_fill_color="color",
        get_line_color=[232, 241, 245, 170],
        line_width_min_pixels=1,
        stroked=True,
        filled=True,
    )
    airport_layer = pdk.Layer(
        "ScatterplotLayer",
        id="hkg-airport",
        data=[{"longitude": HKG_LON, "latitude": HKG_LAT}],
        get_position="[longitude, latitude]",
        get_radius=3500,
        get_fill_color=[244, 185, 66, 30],
        get_line_color=[244, 185, 66, 180],
        stroked=True,
        filled=True,
        pickable=False,
    )
    return pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        initial_view_state=pdk.ViewState(
            latitude=HKG_LAT, longitude=HKG_LON, zoom=7.55, pitch=28, bearing=0
        ),
        layers=[airport_layer, aircraft_layer],
        tooltip={
            "html": (
                "<b>{display_flight}</b><br/>{type_code} · {registration}"
                "<br/>{altitude_label} · {speed_kt} kt"
            ),
            "style": {
                "backgroundColor": "#0D202B",
                "color": "#E8F1F5",
                "fontFamily": "monospace",
            },
        },
    )


def movement_chart(arrivals: pd.DataFrame, departures: pd.DataFrame) -> go.Figure:
    hourly = hourly_movements(arrivals, departures)
    colors = {"Arrivals": "#4BB9D5", "Departures": "#F4B942"}
    figure = go.Figure()
    for series in ("Arrivals", "Departures"):
        frame = hourly[hourly["series"] == series]
        figure.add_bar(
            x=frame["hour_label"],
            y=frame["movements"],
            name=series,
            marker_color=colors[series],
            hovertemplate=f"{series}<br>%{{x}}: %{{y}} movements<extra></extra>",
        )
    figure.update_layout(
        barmode="group",
        height=310,
        margin=dict(l=10, r=10, t=48, b=10),
        title=dict(
            text=(
                "Scheduled passenger movements by hour"
                "<br><sup>One row = one HKIA movement; codeshares are not double-counted</sup>"
            ),
            x=0,
            font=dict(size=16, color="#E8F1F5"),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8EA4AF", family="Avenir Next, Arial"),
        legend=dict(orientation="h", x=1, xanchor="right", y=1.18, yanchor="top"),
        xaxis=dict(showgrid=False, tickmode="linear", dtick=2, title=None),
        yaxis=dict(gridcolor="rgba(142,164,175,.12)", zeroline=False, title="Movements"),
        bargap=0.22,
    )
    return figure


def selected_aircraft(event: Any, aircraft: pd.DataFrame) -> dict[str, Any] | None:
    try:
        objects = event.selection.objects.get("aircraft", [])
        if objects:
            return dict(objects[0])
    except (AttributeError, KeyError, TypeError):
        pass
    if aircraft.empty:
        return None
    cathay = aircraft[aircraft["is_cathay"]]
    return (cathay.iloc[0] if not cathay.empty else aircraft.iloc[0]).to_dict()


def render_header(now: datetime) -> None:
    st.markdown(
        f"""
        <div class="tower-head">
          <div>
            <div class="tower-kicker">VHHH · Chek Lap Kok · Operations view</div>
            <div class="tower-title">HKG SKYWATCH</div>
            <p class="tower-sub">Live airspace, today's movement board, and Cathay departure watch.</p>
          </div>
          <div class="live-chip"><span class="live-dot"></span>LIVE · {now:%H:%M} HKT</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.markdown('<div class="section-label">Airspace controls</div>', unsafe_allow_html=True)
    radius_nm = st.slider(
        "Radius from HKG (NM)", min_value=30, max_value=150, value=DEFAULT_RADIUS_NM, step=10
    )
    cathay_only = st.toggle("Show Cathay aircraft only", value=False)
    auto_refresh = st.toggle("Refresh live positions every 60s", value=True)
    if st.button("Refresh now", use_container_width=True):
        load_aircraft.clear()
        load_flight_board.clear()
        st.rerun()
    st.markdown(
        """
        <div class="source-note" style="margin-top:1rem">
        POSITION SOURCE<br>ADSB.lol → OpenSky fallback<br><br>
        FLIGHT BOARD<br>Airport Authority Hong Kong<br><br>
        No API key is required for this MVP.
        </div>
        """,
        unsafe_allow_html=True,
    )

run_every = "60s" if auto_refresh else None


@st.fragment(run_every=run_every)
def live_dashboard() -> None:
    now = datetime.now(HKG_TZ)
    render_header(now)
    arrivals, departures, flight_warnings = load_flight_board(now.date().isoformat())
    aircraft, position_source, fallback_note, position_error = load_aircraft(radius_nm)
    visible_aircraft = (
        aircraft[aircraft["is_cathay"]].reset_index(drop=True) if cathay_only else aircraft
    )

    if flight_warnings:
        st.warning("HKIA flight board is partially unavailable. " + " | ".join(flight_warnings))
    if position_error:
        st.error("Live aircraft positions are unavailable. " + position_error)
    elif fallback_note:
        st.info(
            "ADSB.lol was unavailable, so the map is using OpenSky. "
            "Registration and type may be missing."
        )

    kpi_cols = st.columns([1, 1, 1, 1.25])
    kpi_cols[0].metric("Today's arrivals", f"{len(arrivals):,}")
    kpi_cols[1].metric("Today's departures", f"{len(departures):,}")
    kpi_cols[2].metric("Aircraft in view", f"{len(visible_aircraft):,}")
    airborne = int((~visible_aircraft["on_ground"]).sum()) if not visible_aircraft.empty else 0
    kpi_cols[3].metric("Airborne / tracked", f"{airborne:,} / {len(visible_aircraft):,}")

    map_col, panel_col = st.columns([2.15, 1], gap="large")
    with map_col:
        st.markdown(
            '<div class="section-label">Live target map · click any aircraft</div>',
            unsafe_allow_html=True,
        )
        if visible_aircraft.empty:
            st.info("No aircraft with usable coordinates are currently available in this view.")
            event = None
        else:
            event = st.pydeck_chart(
                build_map(visible_aircraft),
                on_select="rerun",
                selection_mode="single-object",
                key="hkg-airspace",
                height=610,
                width="stretch",
            )
        st.markdown(
            (
                f'<div class="source-note">Source: {position_source} · {radius_nm} NM from HKG '
                "· cached up to 55 seconds · coverage is receiver-dependent</div>"
            ),
            unsafe_allow_html=True,
        )

    with panel_col:
        chosen = selected_aircraft(event, visible_aircraft)
        st.markdown('<div class="section-label">Aircraft detail</div>', unsafe_allow_html=True)
        st.markdown(aircraft_card(chosen), unsafe_allow_html=True)
        st.markdown(
            '<div class="section-label">CX departure board · HKT</div>',
            unsafe_allow_html=True,
        )
        board = cathay_departure_board(departures, now=now, limit=7)
        st.markdown(flight_board(board), unsafe_allow_html=True)
        st.markdown(
            (
                '<div class="source-note">HKIA open data provides scheduled departure time, '
                "live status and gate, but not a separate boarding timestamp. *Engine is a "
                "model-family reference, not airframe-level confirmation.</div>"
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="section-label" style="margin-top:1.4rem">Today\'s traffic rhythm</div>',
        unsafe_allow_html=True,
    )
    if arrivals.empty and departures.empty:
        st.info("The hourly movement chart will appear when the HKIA board is available.")
    else:
        st.plotly_chart(
            movement_chart(arrivals, departures),
            width="stretch",
            config={"displayModeBar": False},
        )
    freshest = pd.concat([arrivals, departures], ignore_index=True)
    updated = freshest["last_updated"].dropna().max() if not freshest.empty else None
    st.markdown(
        (
            f'<div class="source-note">HKIA flight board last updated: '
            f'{updated or "not available"} · Schedule date: {now:%d %b %Y} HKT</div>'
        ),
        unsafe_allow_html=True,
    )


live_dashboard()
