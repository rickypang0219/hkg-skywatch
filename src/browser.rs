use gloo_net::http::Request;
use hkg_skywatch::*;
use serde_json::Value;
use std::{cell::RefCell, rc::Rc};
use wasm_bindgen::{prelude::*, JsCast};

#[wasm_bindgen(module = "/web/map.js")]
extern "C" {
    #[wasm_bindgen(catch)]
    fn init_map() -> Result<(), JsValue>;
    #[wasm_bindgen(catch)]
    fn update_map(json: &str, selected: &str) -> Result<(), JsValue>;
}
#[derive(Default)]
struct State {
    planes: Vec<Aircraft>,
    arrivals: Vec<Flight>,
    departures: Vec<Flight>,
    selected: String,
    radius: u32,
    cathay: bool,
    auto: bool,
    busy: bool,
    source: String,
    plane_error: String,
    board_error: String,
    board_date: String,
    board_loaded: f64,
}
fn document() -> web_sys::Document {
    web_sys::window().unwrap().document().unwrap()
}
fn element(id: &str) -> web_sys::Element {
    document().get_element_by_id(id).unwrap()
}
fn html(id: &str, s: &str) {
    element(id).set_inner_html(s)
}
fn input(id: &str) -> web_sys::HtmlInputElement {
    element(id).dyn_into().unwrap()
}
fn clock() -> (String, u32, String) {
    let d = js_sys::Date::new(&JsValue::from_f64(
        js_sys::Date::now() + 8.0 * 3600.0 * 1000.0,
    ));
    (
        format!(
            "{:04}-{:02}-{:02}",
            d.get_utc_full_year(),
            d.get_utc_month() + 1,
            d.get_utc_date()
        ),
        d.get_utc_hours() * 60 + d.get_utc_minutes(),
        format!("{:02}:{:02}", d.get_utc_hours(), d.get_utc_minutes()),
    )
}
async fn fetch(url: &str) -> Result<Value, String> {
    let url = url.to_string();
    let future = async move {
        let response = Request::get(&url).send().await.map_err(|e| e.to_string())?;
        if !response.ok() {
            return Err(format!("HTTP {}", response.status()));
        }
        response.json::<Value>().await.map_err(|e| e.to_string())
    };
    // Each request has a bounded wait; an unavailable upstream cannot freeze controls forever.
    use wasm_bindgen_futures::JsFuture;
    let request = wasm_bindgen_futures::future_to_promise(async move {
        future
            .await
            .map(|v| JsValue::from_str(&v.to_string()))
            .map_err(|e| JsValue::from_str(&e))
    });
    let timeout = wasm_bindgen_futures::future_to_promise(async {
        gloo_timers::future::TimeoutFuture::new(15000).await;
        Err(JsValue::from_str("Request timed out"))
    });
    let promises = js_sys::Array::new();
    promises.push(&request);
    promises.push(&timeout);
    let v = JsFuture::from(js_sys::Promise::race(&promises))
        .await
        .map_err(|e| e.as_string().unwrap_or("Network/CORS error".into()))?;
    serde_json::from_str(&v.as_string().unwrap_or_default()).map_err(|e| e.to_string())
}
fn refresh(state: Rc<RefCell<State>>, force: bool) {
    if state.borrow().busy {
        return;
    }
    state.borrow_mut().busy = true;
    element("refresh").set_text_content(Some("Refreshing…"));
    wasm_bindgen_futures::spawn_local(async move {
        let (date, _, _) = clock();
        let (radius, board_needed) = {
            let s = state.borrow();
            (
                s.radius,
                force || s.board_date != date || js_sys::Date::now() - s.board_loaded > 300000.0,
            )
        };
        let board_state = state.clone();
        let board_date = date.clone();
        let board = async move {
            if !board_needed {
                return;
            }
            let mut results = Vec::new();
            for arrival in [true, false] {
                let url = format!(
                    "{HKIA}?span=1&date={board_date}&lang=en&cargo=false&arrival={arrival}"
                );
                results.push(
                    fetch(&url)
                        .await
                        .and_then(|v| flights(&v, &board_date, arrival)),
                );
            }
            let mut note = String::new();
            if results.iter().any(Result::is_err) {
                let url = web_sys::Url::new_with_base(
                    "data/flights.json",
                    &document().base_uri().unwrap().unwrap(),
                )
                .unwrap()
                .href();
                match fetch(&format!("{url}?t={}",js_sys::Date::now())).await {
                    Ok(v) if v["date"]==board_date => {
                        for (i,key) in ["arrivals","departures"].iter().enumerate() {if results[i].is_err(){results[i]=flights(&v[key],&board_date,i==0)}}
                        let timestamp=text(&v["generated_at"]);
                        note=format!("Official snapshot collected {}. GitHub scheduled updates may be delayed.",if timestamp.is_empty(){"at an unconfirmed time"}else{&timestamp});
                        if let Some(errors)=v["errors"].as_array() {for error in errors {note.push_str(&format!(" {}",text(error)));}}
                    }
                    _=>note="HKIA could not be reached and no snapshot for today is available. Retry Refresh now.".into(),
                }
            }
            let mut s = board_state.borrow_mut();
            if s.board_date != board_date {
                s.arrivals.clear();
                s.departures.clear()
            }
            let mut all_ok = true;
            for (i, r) in results.into_iter().enumerate() {
                match r {
                    Ok(f) => {
                        if i == 0 {
                            s.arrivals = f
                        } else {
                            s.departures = f
                        }
                    }
                    Err(e) => {
                        all_ok = false;
                        note.push_str(&format!(
                            " {} board unavailable: {e}.",
                            if i == 0 { "Arrival" } else { "Departure" }
                        ));
                    }
                }
            }
            s.board_date = board_date;
            s.board_error = note;
            if all_ok {
                s.board_loaded = js_sys::Date::now()
            }
        };
        let positions = async {
            let primary = fetch(&format!(
                "https://api.adsb.lol/v2/lat/{LAT}/lon/{LON}/dist/{radius}"
            ))
            .await
            .and_then(|v| aircraft(&v, false));
            let (result, note) = match primary {
                Ok(a) => (Ok(a), String::new()),
                Err(e) => {
                    let lat = radius as f64 / 60.0;
                    let lon = radius as f64 / 55.6;
                    let fallback=fetch(&format!("https://opensky-network.org/api/states/all?lamin={}&lamax={}&lomin={}&lomax={}&extended=1",LAT-lat,LAT+lat,LON-lon,LON+lon)).await.and_then(|v|aircraft(&v,true));
                    (fallback,format!("ADSB.lol unavailable ({e}); using OpenSky. Registration/type may be missing."))
                }
            };
            let mut s = state.borrow_mut();
            match result {
                Ok(a) => {
                    s.source = a
                        .first()
                        .map(|p| p.source.clone())
                        .unwrap_or(if note.is_empty() {
                            "ADSB.lol".into()
                        } else {
                            "OpenSky".into()
                        });
                    s.planes = a;
                    s.plane_error = note
                }
                Err(e) => {
                    s.planes.clear();
                    s.source = "Unavailable".into();
                    s.plane_error =
                        format!("Both position sources unavailable: {e}. Retry Refresh now.")
                }
            }
            drop(s);
            render(&state);
        };
        // Both sources load independently so a blocked HKIA request doesn't delay the map.
        let board_p = wasm_bindgen_futures::future_to_promise(async move {
            board.await;
            Ok(JsValue::NULL)
        });
        positions.await;
        let _ = wasm_bindgen_futures::JsFuture::from(board_p).await;
        state.borrow_mut().busy = false;
        element("refresh").set_text_content(Some("Refresh now"));
        render(&state);
        if state.borrow().radius != radius {
            refresh(state.clone(), false);
        }
    });
}
fn render(state: &Rc<RefCell<State>>) {
    let s = state.borrow();
    let (date, minutes, time) = clock();
    html("clock", &format!("<span class=live-dot></span>{time} HKT"));
    let visible: Vec<_> = s.planes.iter().filter(|p| !s.cathay || p.cathay).collect();
    let chosen = visible
        .iter()
        .find(|p| p.id == s.selected)
        .or_else(|| visible.first());
    let airborne = visible.iter().filter(|p| !p.ground).count();
    for (id, value) in [
        ("arrivals", s.arrivals.len().to_string()),
        ("departures", s.departures.len().to_string()),
        ("tracked", visible.len().to_string()),
        ("airborne", format!("{airborne} / {}", visible.len())),
    ] {
        html(id, &value)
    }
    html(
        "alerts",
        &[&s.plane_error, &s.board_error]
            .iter()
            .filter(|e| !e.is_empty())
            .map(|e| format!("<p class=notice>{}</p>", escape(e)))
            .collect::<String>(),
    );
    html(
        "map-source",
        &format!(
            "{} · {} NM from HKG · {} · receiver-dependent coverage",
            escape(&s.source),
            s.radius,
            if s.auto {
                "60s automatic refresh"
            } else {
                "automatic refresh paused"
            }
        ),
    );
    if let Err(e) = update_map(
        &serde_json::to_string(&visible).unwrap(),
        chosen.map(|p| p.id.as_str()).unwrap_or(""),
    ) {
        html(
            "map-source",
            &format!("Map unavailable: {}", escape(&format!("{e:?}"))),
        )
    }
    html("detail",&chosen.map(|p|{
        let (name,engine)=model(&p.type_code);
        let fields=[("Registration",if p.registration.is_empty(){"Not available".into()}else{p.registration.clone()}),("ICAO type",if p.type_code.is_empty(){"Not broadcast".into()}else{p.type_code.clone()}),("Altitude",if p.ground{"GROUND".into()}else{format!("{:.0} FT",p.altitude)}),("Ground speed",format!("{:.0} KT",p.speed)),("Track",format!("{:03.0}°",p.track)),("Engine family*",engine.into())];
        format!("<p class=eyebrow>Selected aircraft · {}</p><h2>{}</h2><p class=model>{}</p><dl>{}</dl>",escape(&p.source),escape(&p.callsign),escape(name),fields.iter().map(|(k,v)|format!("<div><dt>{k}</dt><dd>{}</dd></div>",escape(v))).collect::<String>())
    }).unwrap_or("<p class=empty>Select an aircraft on the map to inspect its airframe.</p>".into()));
    let board = cx_board(&s.departures, minutes);
    html(
        "board",
        &if board.is_empty() {
            "<p class=empty>No CX passenger departures available in the current feed.</p>".into()
        } else {
            board.iter().map(|f|format!("<article class=flight><time>{}</time><div><strong>{}</strong><p>HKG → {} · {}</p><span class=\"status {}\">{}</span></div><div class=gate><small>Gate</small>{}</div></article>",escape(&f.time),escape(f.numbers.iter().find(|n|n.starts_with("CX ")).unwrap()),escape(&f.destination),escape(&f.terminal),tone(&f.status),escape(if f.status.is_empty(){"Scheduled"}else{&f.status}),escape(if f.gate.is_empty(){"TBC"}else{&f.gate}))).collect::<String>()
        },
    );
    let a = hourly(&s.arrivals);
    let d = hourly(&s.departures);
    let max = *a.iter().chain(d.iter()).max().unwrap_or(&1).max(&1) as f64;
    html(
        "chart",
        &if s.arrivals.is_empty() && s.departures.is_empty() {
            "<p class=empty>The hourly chart will appear when the HKIA board is available.</p>"
                .into()
        } else {
            format!("<div class=bars>{}</div>",(0..24).map(|h|format!("<div class=hour><div class=bar-pair><div class=arrival style=\"height:{}%;min-height:0\" title=\"{:02}:00 — {} arrivals\"></div><div class=departure style=\"height:{}%;min-height:0\" title=\"{:02}:00 — {} departures\"></div></div><span>{}</span></div>",a[h] as f64/max*100.0,h,a[h],d[h] as f64/max*100.0,h,d[h],if h%2==0{format!("{h:02}")}else{String::new()})).collect::<String>())
        },
    );
    let updated = s
        .arrivals
        .iter()
        .chain(s.departures.iter())
        .map(|f| f.updated.as_str())
        .max()
        .unwrap_or("not available");
    html(
        "board-source",
        &format!(
            "HKIA last updated: {} · Schedule date: {date} HKT",
            escape(updated)
        ),
    );
}
fn listen(id: &str, event: &str, f: impl Fn(web_sys::Event) + 'static) {
    let c = Closure::wrap(Box::new(f) as Box<dyn Fn(web_sys::Event)>);
    element(id)
        .add_event_listener_with_callback(event, c.as_ref().unchecked_ref())
        .unwrap();
    c.forget()
}
pub fn start() {
    console_error_panic_hook::set_once();
    html("app", include_str!("../web/shell.html"));
    if let Err(e) = init_map() {
        html("map-source", &format!("Map failed to load: {e:?}"))
    }
    let s = Rc::new(RefCell::new(State {
        radius: 80,
        auto: true,
        ..Default::default()
    }));
    let x = s.clone();
    listen("radius", "change", move |_| {
        x.borrow_mut().radius = input("radius").value().parse().unwrap_or(80);
        html("radius-value", &format!("{} NM", x.borrow().radius));
        refresh(x.clone(), false)
    });
    let x = s.clone();
    listen("cathay", "change", move |_| {
        x.borrow_mut().cathay = input("cathay").checked();
        render(&x)
    });
    let x = s.clone();
    listen("auto", "change", move |_| {
        x.borrow_mut().auto = input("auto").checked();
        render(&x);
    });
    let x = s.clone();
    listen("refresh", "click", move |_| refresh(x.clone(), true));
    let x = s.clone();
    let callback = Closure::wrap(Box::new(move |event: web_sys::Event| {
        if let Ok(e) = event.dyn_into::<web_sys::CustomEvent>() {
            x.borrow_mut().selected = e.detail().as_string().unwrap_or_default();
            render(&x)
        }
    }) as Box<dyn Fn(web_sys::Event)>);
    document()
        .add_event_listener_with_callback("aircraft-select", callback.as_ref().unchecked_ref())
        .unwrap();
    callback.forget();
    let x = s.clone();
    gloo_timers::callback::Interval::new(60000, move || {
        if x.borrow().auto {
            refresh(x.clone(), false)
        }
    })
    .forget();
    render(&s);
    refresh(s, true);
}
