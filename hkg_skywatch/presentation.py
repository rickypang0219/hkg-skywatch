"""HTML helpers for the instrument-panel visual language."""

from html import escape
from typing import Any

import pandas as pd

from .aircraft_types import describe_aircraft
from .transforms import status_tone


def inject_css() -> str:
    return """
    <style>
    :root { --night:#07141D;--panel:#0D202B;--ink:#E8F1F5;--muted:#8EA4AF;
      --cyan:#4BB9D5;--amber:#F4B942;--line:rgba(151,190,204,.18);--danger:#FF7A68; }
    .stApp { background:
      linear-gradient(rgba(75,185,213,.035) 1px,transparent 1px),
      linear-gradient(90deg,rgba(75,185,213,.035) 1px,transparent 1px),var(--night);
      background-size:32px 32px; }
    [data-testid="stHeader"] { background:rgba(7,20,29,.84); }
    [data-testid="stSidebar"] { background:#091923;border-right:1px solid var(--line); }
    .block-container { max-width:1560px;padding-top:1.5rem;padding-bottom:3rem; }
    h1,h2,h3,.tower-display { font-family:"Avenir Next Condensed","Arial Narrow",sans-serif; }
    p,label,button { font-family:"Avenir Next",Arial,sans-serif; }
    code,.mono,[data-testid="stMetricValue"] { font-family:"SFMono-Regular",Menlo,monospace; }
    .tower-head { display:flex;justify-content:space-between;gap:1.5rem;align-items:flex-end;
      border-bottom:1px solid var(--line);padding:.35rem 0 1rem;margin-bottom:1rem; }
    .tower-kicker { font:700 .69rem/1.2 "SFMono-Regular",monospace;letter-spacing:.18em;
      color:var(--amber);text-transform:uppercase; }
    .tower-title { font:800 clamp(2.5rem,5vw,5.4rem)/.88 "Avenir Next Condensed","Arial Narrow",sans-serif;
      letter-spacing:-.04em;color:var(--ink);margin:.4rem 0 .2rem; }
    .tower-sub { color:var(--muted);font-size:.92rem;margin:0; }
    .live-chip { display:flex;align-items:center;gap:.55rem;color:var(--ink);font:700 .72rem/1 Menlo,monospace;
      letter-spacing:.11em;border:1px solid var(--line);padding:.65rem .8rem;white-space:nowrap; }
    .live-dot { width:.52rem;height:.52rem;border-radius:50%;background:var(--amber);
      box-shadow:0 0 0 .28rem rgba(244,185,66,.12); }
    .section-label { font:700 .68rem/1 Menlo,monospace;letter-spacing:.16em;color:var(--cyan);
      text-transform:uppercase;margin:.25rem 0 .7rem; }
    [data-testid="stMetric"] { background:linear-gradient(145deg,rgba(16,42,55,.94),rgba(10,29,40,.94));
      border:1px solid var(--line);padding:.85rem 1rem; }
    [data-testid="stMetricLabel"] { color:var(--muted);font-size:.72rem;letter-spacing:.07em;text-transform:uppercase; }
    [data-testid="stMetricValue"] { color:var(--ink);font-size:1.72rem; }
    .aircraft-card { background:linear-gradient(145deg,#112D3B,#0B1E29);border:1px solid rgba(244,185,66,.35);
      border-top:3px solid var(--amber);padding:1rem 1.05rem;margin-bottom:1rem; }
    .aircraft-call { color:var(--amber);font:800 1.72rem/1 "Avenir Next Condensed",sans-serif; }
    .aircraft-type { color:var(--ink);font:700 1.06rem/1.25 "Avenir Next",sans-serif;margin:.45rem 0 .85rem; }
    .spec-grid { display:grid;grid-template-columns:1fr 1fr;gap:.65rem; }
    .spec { border-top:1px solid var(--line);padding-top:.45rem;min-width:0; }
    .spec b { display:block;color:var(--muted);font:600 .6rem/1.2 Menlo,monospace;
      letter-spacing:.08em;text-transform:uppercase; }
    .spec span { display:block;color:var(--ink);font:600 .8rem/1.3 Menlo,monospace;
      margin-top:.2rem;overflow-wrap:anywhere; }
    .flight-card { display:grid;grid-template-columns:3.5rem minmax(0,1fr) auto;gap:.75rem;align-items:center;
      border-top:1px solid var(--line);padding:.72rem .1rem; }
    .flight-time { color:var(--ink);font:800 1rem/1 Menlo,monospace; }
    .flight-main { min-width:0; }.flight-no { color:var(--ink);font:700 .83rem/1.25 Menlo,monospace; }
    .flight-route { color:var(--muted);font-size:.72rem;white-space:nowrap;overflow:hidden;
      text-overflow:ellipsis;margin-top:.15rem; }
    .gate { color:var(--amber);font:800 .8rem/1 Menlo,monospace;border-left:1px solid var(--line);
      padding-left:.65rem;text-align:right; }
    .gate small { display:block;color:var(--muted);font-size:.52rem;letter-spacing:.08em;margin-bottom:.2rem; }
    .status { display:inline-block;font:700 .56rem/1 Menlo,monospace;letter-spacing:.05em;text-transform:uppercase;
      padding:.28rem .38rem;margin-top:.3rem;border:1px solid var(--line);color:var(--muted); }
    .status-active { color:var(--amber);border-color:rgba(244,185,66,.45);background:rgba(244,185,66,.08); }
    .status-critical { color:var(--danger);border-color:rgba(255,122,104,.4); }
    .status-warning { color:#F6D078;border-color:rgba(246,208,120,.35); }
    .status-scheduled { color:var(--cyan);border-color:rgba(75,185,213,.35); }
    .source-note { color:var(--muted);font:.64rem/1.45 Menlo,monospace; }
    .empty-card { border:1px dashed var(--line);color:var(--muted);padding:1rem;font-size:.8rem; }
    div[data-testid="stPydeckChart"] { border:1px solid var(--line); }
    .stPlotlyChart { border-top:1px solid var(--line);padding-top:.4rem; }
    button:focus-visible,input:focus-visible { outline:2px solid var(--amber)!important;outline-offset:2px; }
    @media (max-width:720px) { .tower-head { align-items:flex-start;flex-direction:column; }
      .tower-title { font-size:3.25rem; }.live-chip { align-self:flex-start; } }
    </style>
    """


def aircraft_card(aircraft: dict[str, Any] | None) -> str:
    if not aircraft:
        return '<div class="empty-card">Select an aircraft on the map to inspect its airframe.</div>'
    type_code = str(aircraft.get("type_code") or "").upper()
    details = describe_aircraft(type_code)
    callsign = escape(
        str(aircraft.get("display_flight") or aircraft.get("callsign") or "Unknown")
    )
    model = escape(f"{details.manufacturer} {details.model}".strip())
    return f"""
    <div class="aircraft-card">
      <div class="tower-kicker">Selected target · {escape(str(aircraft.get('source') or 'Live ADS-B'))}</div>
      <div class="aircraft-call">{callsign}</div>
      <div class="aircraft-type">{model}</div>
      <div class="spec-grid">
        <div class="spec"><b>Registration</b><span>{escape(str(aircraft.get('registration') or '—'))}</span></div>
        <div class="spec"><b>ICAO type</b><span>{escape(type_code or 'Not broadcast')}</span></div>
        <div class="spec"><b>Altitude</b><span>{escape(str(aircraft.get('altitude_label') or '—'))}</span></div>
        <div class="spec"><b>Ground speed</b><span>{float(aircraft.get('speed_kt') or 0):,.0f} KT</span></div>
        <div class="spec"><b>Track</b><span>{float(aircraft.get('track') or 0):03.0f}°</span></div>
        <div class="spec"><b>Engine family*</b><span>{escape(details.engine)}</span></div>
      </div>
    </div>
    """


def flight_board(board: pd.DataFrame) -> str:
    if board.empty:
        return '<div class="empty-card">No CX passenger departures found in the current HKIA feed.</div>'
    cards: list[str] = []
    for row in board.to_dict("records"):
        label, tone = status_tone(row.get("status"))
        cards.append(
            f"""
            <div class="flight-card">
              <div class="flight-time">{escape(str(row.get('scheduled_time') or '--:--'))}</div>
              <div class="flight-main">
                <div class="flight-no">{escape(str(row.get('primary_flight') or 'CX'))}</div>
                <div class="flight-route">HKG → {escape(str(row.get('destination') or '—'))} · {escape(str(row.get('terminal') or '—'))}</div>
                <div class="status status-{tone}">{escape(label)}</div>
              </div>
              <div class="gate"><small>GATE</small>{escape(str(row.get('gate') or 'TBC'))}</div>
            </div>
            """
        )
    return "".join(cards)
