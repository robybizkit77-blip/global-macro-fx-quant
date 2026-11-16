"""First verified Statistics Canada all-items CPI annual readings."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re

from validation.macro.capture_official_postrelease_actuals_v1 import (
    MAX_BYTES, Pending, PlainText, retrieve,
)
from validation.macro.freeze_pre_release_consensus_v1 import (
    digest, exact_event_key, read_existing, scheduled, utc_iso, utc_text,
)

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json"
OUT = ROOT / "validation/macro/MACRO_STATCAN_CPI_FIRST_SEEN_V1.jsonl"
QUALITY = "ISSUER_CPI_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT"
METRIC = "CA_CPI_HEADLINE_YOY_NSA"
PUBLISHER = "Statistics Canada"
HOST = "www150.statcan.gc.ca"
WINDOW = timedelta(days=2)


def targets(official):
    return {exact_event_key(e): e for e in official["events"] if
            e.get("ccy") == "CAD" and e.get("event_type") == "INFLATION"
            and e.get("title") == "Consumer Price Index" and e.get("source_family") == PUBLISHER
            and str(e.get("quality", "")).startswith("OFFICIAL_")}


def issue_urls(release_date):
    stamp = date.fromisoformat(release_date).strftime("%y%m%d")
    return tuple(f"https://{HOST}/n1/daily-quotidien/{stamp}/dq{stamp}{letter}-eng.htm"
                 for letter in "abcd")


def parse_release(raw, release_date, period):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise Pending("Invalid Statistics Canada HTML")
    month = period.split()[0]
    source = raw.decode("utf-8")
    heading = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, re.I | re.S)
    if heading is None or not re.fullmatch(
        r"\s*Consumer Price Index\s*,\s*" + re.escape(period) + r"\s*", heading[1], re.I,
    ):
        raise Pending("Wrong CPI article or reference month")
    text = PlainText()
    text.feed(source[heading.end():])
    content = text.value()
    if not re.search(r"\bReleased:\s*" + re.escape(release_date) + r"\b", content, re.I):
        raise Pending("Wrong Statistics Canada release date")
    # Isolate the headline paragraph before charts, component and core readings.
    lead = re.split(r"\bChart\s+1\b", content, maxsplit=1, flags=re.I)[0][:4800]
    prefix = r"\bThe Consumer Price Index\s*\(\s*CPI\s*\)\s+"
    tail = r"\s+(?:year over year|on a year-over-year basis)\s+in\s+" + re.escape(month) + r"\b"
    matches = re.findall(
        prefix + r"(rose|increased|fell|decreased|declined)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%" + tail,
        lead, re.I,
    )
    unchanged = re.findall(prefix + r"(?:was|remained) unchanged" + tail, lead, re.I)
    if len(matches) == 1 and not unchanged:
        verb, magnitude = matches[0]
        value = float(magnitude)
        if math.isfinite(value) and value < 50:
            return -value if verb.lower() in {"fell", "decreased", "declined"} else value
    if not matches and len(unchanged) == 1:
        return 0.0
    raise Pending("Aggregate annual CPI is absent or ambiguous")


def validate(rows, official):
    events = targets(official)
    previous, seen = "GENESIS", set()
    for row in rows:
        key = row.get("event_key")
        event = events.get(key)
        body = {k: v for k, v in row.items() if k != "record_sha256"}
        value = row.get("actual_percent")
        if not (event and key not in seen and row.get("previous_record_sha256") == previous
                and row.get("record_sha256") == digest(body) and row.get("metric_id") == METRIC
                and row.get("publisher") == PUBLISHER and row.get("quality") == QUALITY
                and row.get("reference_period") == event["reference_period"]
                and row.get("source_url") in issue_urls(event["date"])
                and re.fullmatch(r"[a-f0-9]{64}", row.get("source_html_sha256", ""))
                and type(value) in (int, float) and math.isfinite(value) and abs(value) < 50):
            raise ValueError("Invalid Statistics Canada CPI archive record")
        release = scheduled(event)
        observed = utc_iso(row.get("observed_at_utc"))
        if release is None or not release <= observed <= release + WINDOW:
            raise ValueError("Statistics Canada CPI observation outside source window")
        previous = row["record_sha256"]
        seen.add(key)
    return previous, seen


def capture(official, rows, now, fetch=retrieve, observed_clock=None):
    if now.utcoffset() is None:
        raise ValueError("An offset-aware release clock is required")
    observed_clock = observed_clock or (lambda: now)
    previous, seen = validate(rows, official)
    result = list(rows)
    state = "NO_RELEASE_IN_CAPTURE_WINDOW"
    for key, event in targets(official).items():
        release = scheduled(event)
        if release is None or not release <= now <= release + WINDOW:
            continue
        if key in seen:
            state = "ALREADY_OBSERVED"
            continue
        state = "OFFICIAL_HEADLINE_NOT_YET_VERIFIED"
        for url in issue_urls(event["date"]):
            try:
                raw, final = fetch(url, HOST)
                if final != url:
                    continue
                value = parse_release(raw, event["date"], event["reference_period"])
            except (Pending, OSError, UnicodeError, ValueError):
                continue
            observed = observed_clock()
            if observed.utcoffset() is None or not now <= observed <= release + WINDOW:
                raise ValueError("Invalid Statistics Canada observation clock")
            record = {
                "event_key": key, "metric_id": METRIC, "publisher": PUBLISHER,
                "reference_period": event["reference_period"], "observed_at_utc": utc_text(observed),
                "actual_percent": value, "source_url": url, "quality": QUALITY,
                "source_html_sha256": hashlib.sha256(raw).hexdigest(), "previous_record_sha256": previous,
            }
            record["record_sha256"] = digest(record)
            previous = record["record_sha256"]
            result.append(record)
            state = "OFFICIAL_HEADLINE_OBSERVED"
            break
    validate(result, official)
    return result, state


def run():
    official = json.loads(SEED.read_text(encoding="utf-8"))
    original = read_existing(OUT)
    rows, state = capture(official, original, datetime.now(timezone.utc),
                          observed_clock=lambda: datetime.now(timezone.utc))
    if len(rows) > len(original):
        with OUT.open("a", encoding="utf-8") as f:
            for row in rows[len(original):]:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"state": state, "new_actuals": len(rows) - len(original)}))


if __name__ == "__main__":
    run()
