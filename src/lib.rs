use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const LAT: f64 = 22.308;
pub const LON: f64 = 113.9185;
pub const HKIA: &str = "https://www.hongkongairport.com/flightinfo-rest/rest/flights";

pub fn text(v: &Value) -> String {
    v.as_str().unwrap_or_default().trim().to_string()
}
pub fn number(v: &Value) -> f64 {
    v.as_f64()
        .or_else(|| v.as_str()?.parse().ok())
        .filter(|n| n.is_finite())
        .unwrap_or(0.0)
}
pub fn escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}
pub fn display(c: &str) -> String {
    let c = c.trim().to_uppercase();
    if let Some(n) = c.strip_prefix("CPA") {
        let digits = n.chars().take_while(|c| c.is_ascii_digit()).count();
        if digits > 0
            && (digits == n.len()
                || (digits + 1 == n.len() && n.chars().last().unwrap().is_ascii_uppercase()))
        {
            return format!("CX {n}");
        }
    }
    if c.is_empty() {
        "NO CALLSIGN".into()
    } else {
        c
    }
}
pub fn distance(lat: f64, lon: f64) -> f64 {
    let a = ((lat - LAT).to_radians() / 2.0).sin().powi(2)
        + LAT.to_radians().cos()
            * lat.to_radians().cos()
            * ((lon - LON).to_radians() / 2.0).sin().powi(2);
    3440.065 * 2.0 * a.sqrt().atan2((1.0 - a).max(0.0).sqrt())
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Aircraft {
    pub id: String,
    pub callsign: String,
    pub registration: String,
    pub type_code: String,
    pub lat: f64,
    pub lon: f64,
    pub altitude: f64,
    pub speed: f64,
    pub track: f64,
    pub ground: bool,
    pub cathay: bool,
    pub distance: f64,
    pub source: String,
}
pub fn aircraft(payload: &Value, opensky: bool) -> Result<Vec<Aircraft>, String> {
    let key = if opensky { "states" } else { "ac" };
    let rows = payload[key]
        .as_array()
        .ok_or_else(|| format!("Unexpected {key} response"))?;
    let mut out = Vec::new();
    for row in rows {
        let (lat, lon) = if opensky {
            (row[6].as_f64(), row[5].as_f64())
        } else {
            (row["lat"].as_f64(), row["lon"].as_f64())
        };
        let (Some(lat), Some(lon)) = (lat, lon) else {
            continue;
        };
        if !lat.is_finite() || !lon.is_finite() || lat.abs() > 90.0 || lon.abs() > 180.0 {
            continue;
        }
        let callsign = text(if opensky { &row[1] } else { &row["flight"] }).to_uppercase();
        let ground = if opensky {
            row[8].as_bool().unwrap_or(false)
        } else {
            row["alt_baro"] == "ground"
        };
        out.push(Aircraft {
            id: text(if opensky { &row[0] } else { &row["hex"] }),
            cathay: callsign.starts_with("CPA"),
            callsign: display(&callsign),
            registration: if opensky {
                "Not available from OpenSky".into()
            } else {
                text(&row["r"])
            },
            type_code: if opensky {
                String::new()
            } else {
                text(&row["t"]).to_uppercase()
            },
            lat,
            lon,
            altitude: if ground {
                0.0
            } else if opensky {
                number(&row[7]) * 3.28084
            } else {
                number(&row["alt_baro"])
            },
            speed: if opensky {
                number(&row[9]) * 1.94384
            } else {
                number(&row["gs"])
            },
            track: number(if opensky {
                &row[10]
            } else if row["track"].is_null() {
                &row["calc_track"]
            } else {
                &row["track"]
            })
            .rem_euclid(360.0),
            ground,
            distance: distance(lat, lon),
            source: if opensky {
                "OpenSky".into()
            } else {
                "ADSB.lol".into()
            },
        });
    }
    out.sort_by(|a, b| {
        b.cathay
            .cmp(&a.cathay)
            .then(a.distance.total_cmp(&b.distance))
    });
    Ok(out)
}
#[derive(Clone, Debug)]
pub struct Flight {
    pub time: String,
    pub minutes: Option<u32>,
    pub numbers: Vec<String>,
    pub destination: String,
    pub terminal: String,
    pub gate: String,
    pub status: String,
    pub updated: String,
}
pub fn flights(payload: &Value, date: &str, arrival: bool) -> Result<Vec<Flight>, String> {
    let days = payload.as_array().ok_or("Unexpected HKIA response")?;
    let mut out = Vec::new();
    for day in days.iter().filter(|d| d["date"] == date) {
        if let Some(rows) = day["list"].as_array() {
            for row in rows {
                let time = text(&row["time"]);
                let minutes = time
                    .split_once(':')
                    .and_then(|(h, m)| Some((h.parse::<u32>().ok()?, m.parse::<u32>().ok()?)))
                    .filter(|(h, m)| *h < 24 && *m < 60)
                    .map(|(h, m)| h * 60 + m);
                out.push(Flight {
                    time,
                    minutes,
                    numbers: row["flight"]
                        .as_array()
                        .map(|f| {
                            f.iter()
                                .filter_map(|v| v["no"].as_str().map(|s| s.trim().to_string()))
                                .collect()
                        })
                        .unwrap_or_default(),
                    destination: row[if arrival { "origin" } else { "destination" }]
                        .as_array()
                        .map(|v| v.iter().map(text).collect::<Vec<_>>().join(" / "))
                        .unwrap_or_default(),
                    terminal: text(&row["terminal"]),
                    gate: text(&row["gate"]),
                    status: text(&row["status"]),
                    updated: text(&day["lastUpdatedTime"]),
                });
            }
        }
    }
    Ok(out)
}
pub fn cx_board(flights: &[Flight], minutes: u32) -> Vec<&Flight> {
    let mut cx: Vec<_> = flights
        .iter()
        .filter(|f| f.numbers.iter().any(|n| n.starts_with("CX ")))
        .collect();
    cx.sort_by_key(|f| f.minutes.unwrap_or(u32::MAX));
    let future: Vec<_> = cx
        .iter()
        .copied()
        .filter(|f| f.minutes.is_some_and(|m| m >= minutes))
        .take(7)
        .collect();
    let recent: Vec<_> = cx
        .iter()
        .copied()
        .filter(|f| f.minutes.is_some_and(|m| m < minutes))
        .collect();
    recent
        .iter()
        .skip(recent.len().saturating_sub(7 - future.len()))
        .copied()
        .chain(future)
        .collect()
}
pub fn hourly(flights: &[Flight]) -> [usize; 24] {
    let mut out = [0; 24];
    for f in flights {
        if let Some(m) = f.minutes {
            out[(m / 60) as usize] += 1
        }
    }
    out
}
pub fn tone(status: &str) -> &'static str {
    let s = status.to_lowercase();
    if s.contains("boarding") || s.contains("final call") {
        "active"
    } else if s.contains("cancel") {
        "critical"
    } else if s.contains("delay") {
        "warning"
    } else if s.starts_with("dep") || s.contains("closed") {
        "muted"
    } else {
        "scheduled"
    }
}
pub fn model(code: &str) -> (&str, &str) {
    match code {
        "A20N" => ("Airbus A320neo", "CFM LEAP-1A / PW1100G"),
        "A21N" => ("Airbus A321neo", "CFM LEAP-1A / PW1100G"),
        "A319" => ("Airbus A319", "CFM56-5 / IAE V2500"),
        "A320" => ("Airbus A320", "CFM56-5 / IAE V2500"),
        "A321" => ("Airbus A321", "CFM56-5 / IAE V2500"),
        "A332" => ("Airbus A330-200", "CF6 / PW4000 / Trent 700"),
        "A333" => ("Airbus A330-300", "CF6 / PW4000 / Trent 700"),
        "A339" => ("Airbus A330-900neo", "Rolls-Royce Trent 7000"),
        "A359" => ("Airbus A350-900", "Rolls-Royce Trent XWB-84"),
        "A35K" => ("Airbus A350-1000", "Rolls-Royce Trent XWB-97"),
        "A388" => ("Airbus A380-800", "Trent 900 / Engine Alliance GP7200"),
        "B38M" => ("Boeing 737 MAX 8", "CFM LEAP-1B"),
        "B39M" => ("Boeing 737 MAX 9", "CFM LEAP-1B"),
        "B738" => ("Boeing 737-800", "CFM56-7B"),
        "B739" => ("Boeing 737-900", "CFM56-7B"),
        "B744" => ("Boeing 747-400", "CF6 / PW4000 / RB211"),
        "B748" => ("Boeing 747-8", "GEnx-2B"),
        "B763" => ("Boeing 767-300", "CF6 / PW4000 / RB211"),
        "B772" => ("Boeing 777-200", "GE90 / PW4000 / Trent 800"),
        "B77L" => ("Boeing 777-200LR / 777F", "GE90-110B/115B"),
        "B77W" => ("Boeing 777-300ER", "GE90-115B"),
        "B778" => ("Boeing 777-8", "GE9X"),
        "B779" => ("Boeing 777-9", "GE9X"),
        "B788" => ("Boeing 787-8 Dreamliner", "GEnx-1B / Trent 1000"),
        "B789" => ("Boeing 787-9 Dreamliner", "GEnx-1B / Trent 1000"),
        "B78X" => ("Boeing 787-10 Dreamliner", "GEnx-1B / Trent 1000"),
        "E190" => ("Embraer E190", "GE CF34-10E"),
        "E195" => ("Embraer E195", "GE CF34-10E"),
        "E290" => ("Embraer E190-E2", "Pratt & Whitney PW1900G"),
        "E295" => ("Embraer E195-E2", "Pratt & Whitney PW1900G"),
        _ => (
            if code.is_empty() {
                "Type not broadcast"
            } else {
                code
            },
            "Engine data unavailable",
        ),
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn codeshares_count_once() {
        let v = serde_json::json!([{"date":"2026-10-03","list":[{"time":"18:30","flight":[{"no":"BA 101"},{"no":"CX 101"}],"destination":["LHR"]}]}]);
        let f = flights(&v, "2026-10-03", false).unwrap();
        assert_eq!(f.len(), 1);
        assert_eq!(hourly(&f)[18], 1);
        assert_eq!(cx_board(&f, 1000).len(), 1);
        assert!(flights(&v, "2026-10-04", false).unwrap().is_empty());
    }
    #[test]
    fn conversions_and_missing_coordinates() {
        let v = serde_json::json!({"states":[["abc","CPA101","",0,0,113.9,22.3,1000,false,100,90,5,null,null,"",false,0], ["missing"]]});
        let a = aircraft(&v, true).unwrap();
        assert_eq!(a.len(), 1);
        assert_eq!(a[0].callsign, "CX 101");
        assert_eq!(a[0].altitude.round(), 3281.0);
        assert_eq!(a[0].speed.round(), 194.0);
    }
    #[test]
    fn engines_and_escape() {
        assert_eq!(model("B77W").1, "GE90-115B");
        assert_eq!(model("B779").1, "GE9X");
        assert_eq!(escape("<script>"), "&lt;script&gt;");
        assert_eq!(display("CPAX"), "CPAX");
    }
}
