#!/usr/bin/env python3
"""First-observed official October 2026 Australian SA unemployment actual.

One scheduled ABS publication, no inference from a previous month's rate,
trend estimate, provider label, market consensus, OIS or FX. Archive is
append-only and first-runner-seen, NOT publisher first-delivery PIT.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.capture_official_postrelease_actuals_v1 import (
    Pending, PlainText, retrieve,
)
from validation.macro.freeze_pre_release_consensus_v1 import (
    digest, utc_iso, utc_text,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/macro/MACRO_AUD_LABOUR_OFFICIAL_FIRST_SEEN_V12.jsonl"
SCHEMA = "GMFQ_AUD_OCT_2026_ABS_LABOUR_OFFICIAL_FIRST_OBSERVED_V12"
QUALITY = "ISSUER_ABS_SA_UNEMPLOYMENT_RUNNER_FIRST_OBSERVATION_NOT_PUBLISHER_PIT"
URL = "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/oct-2026"
HOST = "www.abs.gov.au"
EVENT = "AUD|2026-11-19|LABOUR|Labour Force, Australia"
METRIC = "AU_UNEMP_RATE_SA"
PUBLISHER = "Australian Bureau of Statistics"
REFERENCE = "2026-10"
RELEASE = datetime(2026, 11, 19, 11, 30, tzinfo=ZoneInfo("Australia/Sydney")).astimezone(timezone.utc)
WINDOW = timedelta(days=7)


def need(ok, reason):
    if not ok:
        raise ValueError("AUD_ABS_ISSUER_V12_REJECTED: " + reason)


def parse_abs(raw):
    need(type(raw) is bytes and 20 < len(raw) <= 2_000_000,
         "official HTML bytes invalid")
    p = PlainText()
    p.feed(raw.decode("utf-8", errors="replace"))
    text = p.value()
    # Published issue AND reference period, not a future-release calendar stub.
    if not re.search(r"Reference period\\s+October\\s+2026\\b", text, re.I):
        raise Pending("ABS_WRONG_OR_UNPUBLISHED_REFERENCE_MONTH")
    if not re.search(r"Released\\s+19/11/2026\\b", text, re.I):
        raise Pending("ABS_TARGET_ISSUE_RELEASE_DATE_NOT_PRESENT")
    m = re.search(r"In seasonally adjusted terms,?\\s+in October 2026\\s*:", text, re.I)
    if m is None:
        raise Pending("ABS_SEASONALLY_ADJUSTED_MAIN_STATISTICS_NOT_PRESENT")
    # Only the release's leading SA Key Statistics block. Never reach the
    # trend block, historical table, a graph or a prior period.
    first = text[m.end():]
    stop = re.search(r"\\bIn trend terms\\b|\\bMain features\\b", first, re.I)
    section = first[:min(stop.start() if stop else len(first), 1600)]
    rates = re.findall(
        r"\\bthe unemployment rate\\s+(?:increased|decreased|rose|fell|"
        r"remained unchanged|was unchanged|remained)\\b"
        r"[^.;]{0,90}?\\b(?:to|at)\\s+(\\d+(?:\\.\\d+)?)\\s*%",
        section, re.I)
    if len(rates) != 1:
        raise Pending("ABS_SA_UNEMPLOYMENT_OCT_VALUE_NOT_UNIQUE")
    value = float(rates[0])
    need(math.isfinite(value) and 0 < value < 30,
         "implausible or missing unemployment rate")
    return value


def validate(rows):
    need(isinstance(rows, list), "official archive must be a list")
    need(len(rows) <= 1, "archive cannot contain duplicate October releases")
    previous = "GENESIS"
    for r in rows:
        need(isinstance(r, dict) and r.get("schema") == SCHEMA, "schema mismatch")
        need(r.get("record_sha256") == digest({
            k:v for k,v in r.items() if k != "record_sha256"
        }) and r.get("previous_record_sha256") == previous,
             "archive signature or chain invalid")
        need(r.get("event_key") == EVENT and r.get("metric_id") == METRIC
             and r.get("currency") == "AUD" and r.get("publisher") == PUBLISHER
             and r.get("source_url") == URL
             and r.get("reference_period") == REFERENCE
             and r.get("metric_unit") == "PCT_LEVEL_SA"
             and r.get("official_scheduled_release_utc") == utc_text(RELEASE),
             "release identity, source, period or series mismatch")
        seen = utc_iso(r.get("observed_at_utc"))
        need(RELEASE <= seen <= RELEASE + WINDOW,
             "publisher observation outside release window")
        actual = r.get("actual_percent")
        need(type(actual) in (float, int) and math.isfinite(actual)
             and 0 < actual < 30, "actual rate invalid")
        need(isinstance(r.get("source_html_sha256"), str)
             and re.fullmatch("[0-9a-f]{64}", r["source_html_sha256"]),
             "source bytes fingerprint missing")
        need(r.get("quality") == QUALITY
             and r.get("first_publisher_delivery_PIT_verified") is False
             and r.get("survey_consensus_percent") is None
             and r.get("certified_surprise_pp") is None
             and r.get("market_reaction") is None
             and r.get("FX_signal") is None
             and r.get("eligible_for_Core_Beta_Forward") is False,
             "unsupported PIT, surprise, market or signal claim")
        previous = r["record_sha256"]
    return bool(rows)


def capture(old, now, fetch=retrieve, observed_clock=None):
    need(isinstance(now, datetime) and now.tzinfo is not None
         and now.utcoffset() is not None, "UTC-aware clock required")
    now = now.astimezone(timezone.utc)
    validate(old)
    if old:
        return old, {"status":"AUD_ABS_OFFICIAL_FIRST_OBSERVED_RESEARCH_V12",
                     "state":"ALREADY_ARCHIVED_NO_HTTP","new_actuals":0,
                     "total_actuals":1,"writes_live_data":False}
    if now < RELEASE:
        state = "BEFORE_RELEASE_NO_HTTP"
    elif now > RELEASE + WINDOW:
        state = "OUTSIDE_FIRST_OBSERVATION_WINDOW_NO_HTTP"
    else:
        try:
            raw, final = fetch(URL, HOST)
            need(final == URL, "issuer redirect changed exact source URL")
            actual = parse_abs(raw)
        except (Pending, OSError, TimeoutError, UnicodeError):
            state = "TARGET_ISSUER_RELEASE_NOT_YET_OBSERVED"
        else:
            seen = observed_clock() if observed_clock is not None else now
            need(isinstance(seen, datetime) and seen.tzinfo is not None
                 and seen.utcoffset() is not None,
                 "source observation time requires timezone")
            seen = seen.astimezone(timezone.utc)
            need(now <= seen <= RELEASE + WINDOW,
                 "successful observation not after HTTP poll or outside window")
            row = {
                "schema": SCHEMA, "event_key": EVENT, "metric_id": METRIC,
                "currency": "AUD", "publisher": PUBLISHER,
                "source_url": URL, "reference_period": REFERENCE,
                "metric_unit": "PCT_LEVEL_SA",
                "actual_percent": actual,
                "source_html_sha256": hashlib.sha256(raw).hexdigest(),
                "official_scheduled_release_utc": utc_text(RELEASE),
                "observed_at_utc": utc_text(seen),
                "quality": QUALITY,
                "first_publisher_delivery_PIT_verified": False,
                "survey_consensus_percent": None,
                "certified_surprise_pp": None,
                "market_reaction": None,
                "FX_signal": None,
                "eligible_for_Core_Beta_Forward": False,
                "previous_record_sha256": "GENESIS",
            }
            row["record_sha256"] = digest(row)
            result = [row]
            validate(result)
            return result, {
                "status":"AUD_ABS_OFFICIAL_FIRST_OBSERVED_RESEARCH_V12",
                "state":"OFFICIAL_SA_OCTOBER_UNEMPLOYMENT_FIRST_OBSERVED",
                "new_actuals":1, "total_actuals":1, "writes_live_data":False}
    return [], {"status":"AUD_ABS_OFFICIAL_FIRST_OBSERVED_RESEARCH_V12",
                "state":state,"new_actuals":0,"total_actuals":0,
                "writes_live_data":False}


def run(actual_path=OUT, now=None, fetch=retrieve, observed_clock=None):
    now = now or datetime.now(timezone.utc)
    existing = []
    if Path(actual_path).is_file():
        existing = [json.loads(line) for line in Path(actual_path).read_text(
            encoding="utf-8").splitlines() if line.strip()]
    records, report = capture(
        existing, now, fetch,
        observed_clock=observed_clock or (lambda: datetime.now(timezone.utc)))
    if len(records) > len(existing):
        with Path(actual_path).open("a", encoding="utf-8") as out:
            for r in records[len(existing):]:
                out.write(json.dumps(r, ensure_ascii=False, sort_keys=True,
                                     separators=(",",":")) + "\\n")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--actuals", type=Path, default=OUT)
    args = p.parse_args()
    print(json.dumps(run(actual_path=args.actuals),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
