#[cfg(not(target_arch = "wasm32"))]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    use chrono::{FixedOffset, Utc};
    use serde_json::{json, Value};
    let now = Utc::now().with_timezone(&FixedOffset::east_opt(8 * 3600).unwrap());
    let date = now.format("%Y-%m-%d").to_string();
    let path = "data/flights.json";
    let old: Value = std::fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(Value::Null);
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(20))
        .user_agent("hkg-skywatch/0.2 personal aviation dashboard")
        .build()?;
    let mut output =
        json!({"date":date,"generated_at":null,"arrivals":null,"departures":null,"errors":[]});
    if old["date"] == date {
        output = old;
        output["errors"] = json!([])
    }
    let mut successes = 0;
    for (arrival, key) in [(true, "arrivals"), (false, "departures")] {
        let result = (|| -> Result<Value, Box<dyn std::error::Error>> {
            let v = client
                .get(hkg_skywatch::HKIA)
                .query(&[
                    ("span", "1"),
                    ("date", date.as_str()),
                    ("lang", "en"),
                    ("cargo", "false"),
                    ("arrival", if arrival { "true" } else { "false" }),
                ])
                .send()?
                .error_for_status()?
                .json::<Value>()?;
            hkg_skywatch::flights(&v, &date, arrival).map_err(std::io::Error::other)?;
            if !v
                .as_array()
                .is_some_and(|days| days.iter().any(|d| d["date"] == date))
            {
                return Err("HKIA response contains no bucket for today".into());
            }
            Ok(v)
        })();
        match result {
            Ok(v) => {
                output[key] = v;
                successes += 1
            }
            Err(e) => {
                eprintln!("{key}: {e}");
                output["errors"]
                    .as_array_mut()
                    .unwrap()
                    .push(json!(format!("{key}: {e}")));
            }
        }
    }
    // Only claim a new collection timestamp when both official boards succeeded.
    if successes == 2 {
        output["generated_at"] = json!(now.to_rfc3339())
    }
    std::fs::create_dir_all("data")?;
    std::fs::write(path, serde_json::to_string_pretty(&output)?)?;
    if successes == 0 {
        eprintln!("No fresh HKIA board. Existing same-day data retained; the UI reports its age.");
    }
    Ok(())
}
#[cfg(target_arch = "wasm32")]
fn main() {}
