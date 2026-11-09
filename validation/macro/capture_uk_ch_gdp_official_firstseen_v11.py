#!/usr/bin/env python3
"""V11: strictly gated first-observed official GDP actuals for UK and Switzerland.

ONS Q3 FIRST QUARTERLY GDP is not monthly GDP or revised quarterly accounts.
SECO GDP FLASH Q3 is not Q2, detailed GDP or an underlying sports adjustment.
Source-provenanced, append-only RESEARCH observations only: V9 label-forecast
comparisons are not verified market-consensus surprises or causal FX signals.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import math
import re

from validation.macro.capture_official_postrelease_actuals_v1 import (
    PlainText, Pending, retrieve,
)
from validation.macro.freeze_pre_release_consensus_v1 import (
    digest, exact_event_key, scheduled, utc_iso, utc_text,
)
from validation.macro.freeze_exact_metric_forecasts_v9 import (
    LEDGER as FORECAST_LEDGER, read_rows, validate_existing as validate_v9,
)
from validation.macro.g8_metric_issuer_contract_v8 import metrics_for

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json"
OUT = ROOT / "validation/macro/MACRO_UK_CH_GDP_OFFICIAL_FIRST_SEEN_V11.jsonl"
SCHEMA = "GMFQ_G8_OFFICIAL_GDP_METRIC_ACTUAL_FIRST_OBSERVED_V11"
QUALITY = "ISSUER_GDP_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT"
MAX_LAG = timedelta(days=7)

TARGETS = {
    "UK_REAL_GDP_PRELIM_QOQ_SA": {
        "key": "GBP|2026-11-12|GROWTH|GDP first quarterly estimate, UK",
        "date": "2026-11-12",
        "host": "www.ons.gov.uk",
        "source_url": "https://www.ons.gov.uk/economy/grossdomesticproductgdp/bulletins/gdpfirstquarterlyestimateuk/julytoseptember2026",
        "reference_period": "2026Q3",
        "official_publisher": "Office for National Statistics",
        "quality_constraint": "FIRST_QUARTERLY_GDP_NOT_MONTHLY_OR_REVISED",
    },
    "CH_REAL_GDP_FLASH_QOQ": {
        "key": "CHF|2026-11-16|GROWTH|Swiss GDP flash",
        "date": "2026-11-16",
        "host": "www.seco.admin.ch",
        "source_url": "https://www.seco.admin.ch/en/gdp-flash",
        "reference_period": "2026Q3",
        "official_publisher": "Swiss State Secretariat for Economic Affairs",
        "quality_constraint": "FLASH_QOQ_SOURCE_ADJUSTMENT_UNVERIFIED",
    },
}
ORDER = tuple(TARGETS)
def need(ok, why):
    if not ok:
        raise ValueError("GDP_ISSUER_V11_REJECTED: " + why)


def source_text(raw):
    need(type(raw) is bytes and 16 < len(raw) <= 2_000_000,
         "HTML bytes missing or excessive")
    parser = PlainText()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return parser.value()


def signed_amount(verb, raw):
    need(raw is not None, "explicit rate absent")
    value = float(raw)
    need(math.isfinite(value) and value >= 0 and value < 30,
         "invalid real GDP qoq magnitude")
    return -value if verb.lower() in (
        "decreased", "fallen", "fell", "contracted", "declined", "shrunk",
        "shrank") else value


def parse_ons(raw, *, quarter="Quarter 3", period="July to September",
              short_period="July to Sept", release="12 November 2026"):
    text = source_text(raw)
    # Require bulletin, NOT /releases calendar stub, monthly-GDP article, or
    # later updated quarterly national accounts.
    heading = f"GDP first quarterly estimate, UK: {period} 2026"
    if text.lower().count(heading.lower()) != 1:
        raise Pending("ONS_TARGET_FIRST_QUARTERLY_BULLETIN_NOT_IDENTIFIED")
    if not re.search(r"Release date:\s*" + re.escape(release) + r"\b", text, re.I):
        raise Pending("ONS_WRONG_PUBLICATION_DATE")
    if re.search(r"This release is not yet published", text, re.I):
        raise Pending("ONS_CALENDAR_STUB_NOT_RELEASED")
    # A leading heading section with real UK GDP, not sector output, GDP per
    # head, nominal GDP or a three-month rolling monthly GDP figure.
    lead = text.split(heading, 1)[1]
    lead = re.split(r"(?:\b2\.\s+Headline GDP figures\b|\b2\.\s+GDP\b)",
                    lead, maxsplit=1)[0][:4300]
    expression = (
        r"UK real gross domestic product\s*\(GDP\)\s+"
        r"is estimated to have\s+"
        r"(?P<verb>increased|grown|risen|decreased|fallen|contracted|declined)"
        r"\s+by\s+(?P<rate>\d+(?:\.\d+)?)\s*%\s+in\s+"
        + re.escape(quarter) + r"\s*\(\s*(?:"
        + re.escape(short_period) + r"|" + re.escape(period)
        + r")\s*\)\s*2026\b"
    )
    hits = list(re.finditer(expression, lead, flags=re.I))
    if len(hits) != 1:
        raise Pending("ONS_REAL_GDP_FIRST_ESTIMATE_Q3_NOT_SINGLE_EXACT_MATCH")
    return signed_amount(hits[0].group("verb"), hits[0].group("rate"))


def parse_seco(raw, *, q="third", year=2026):
    text = source_text(raw)
    # On current /en/gdp-flash the title and paragraph advance in place,
    # and the schedule also mentions Q3 before publication. Never parse
    # the schedule's Q3 date or a Q2 value as Q3 GDP.
    header = re.search(
        r"GDP flash for the\s+" + re.escape(q) +
        r"\s+quarter of\s+" + str(year) + r"\s*:", text, re.I)
    if header is None:
        raise Pending("SECO_FLASH_TARGET_QUARTER_NOT_IN_HEADLINE")
    # Isolate headline paragraph, exclude future publication schedule, prior
    # quarters, industrial/services sector figures, or later GDP reports.
    first = text[header.end():]
    first = re.split(r"\bFurther information\b|\bPublication schedule\b",
                     first, maxsplit=1, flags=re.I)[0][:2000]
    rate = (
        r"(?:Swiss economy|Switzerland(?:'s|’s)?\s+quarterly real GDP)"
        r".{0,240}?"
        r"(?P<verb>grew|grown|increased|rose|contracted|decreased|fell|"
        r"declined|shrunk|shrank)"
        r"\s+by\s+(?P<rate>\d+(?:\.\d+)?)\s*%"
        r"\s+in the\s+" + re.escape(q) +
        r"\s+quarter of\s+" + str(year) + r"\b"
    )
    hits = list(re.finditer(rate, first, flags=re.I))
    if len(hits) != 1:
        raise Pending("SECO_FLASH_REAL_GDP_Q3_NOT_SINGLE_EXACT_MATCH")
    return signed_amount(hits[0].group("verb"), hits[0].group("rate"))


PARSERS = {
    "UK_REAL_GDP_PRELIM_QOQ_SA": parse_ons,
    "CH_REAL_GDP_FLASH_QOQ": parse_seco,
}


def release_contracts(official):
    need(official.get("schema") == "GMFQ_MACRO_RELEASE_OFFICIAL_SEED_V1",
         "official calendar invalid")
    by_key = {exact_event_key(e): e for e in official["events"]}
    need(len(by_key) == len(official["events"]), "calendar duplicate key")
    out = {}
    for mid, target in TARGETS.items():
        event = by_key.get(target["key"])
        need(event is not None and event.get("date") == target["date"],
             "GDP issuer event absent from approved calendar")
        metric = [m for m in metrics_for(event) if m["metric_id"] == mid]
        need(len(metric) == 1, "GDP V8 metric contract absent")
        instant = scheduled(event)
        need(instant is not None, "exact local issuer release clock missing")
        out[mid] = {"event": event, "metric": metric[0], "release": instant}
    return out


def forecasts_by_metric(forecasts):
    validate_v9(forecasts)
    selected = {r["metric_id"]: r for r in forecasts if
                r["metric_id"] in TARGETS}
    need(len(selected) == sum(r["metric_id"] in TARGETS for r in forecasts),
         "duplicate forecast metric")
    for mid, r in selected.items():
        need(r["event_key"] == TARGETS[mid]["key"], "V9 forecast mismatched event")
    return selected


def validate_actuals(rows, official, forecasts):
    need(isinstance(rows, list), "actual ledger rows required")
    contracts = release_contracts(official)
    forecast_map = forecasts_by_metric(forecasts)
    prev, seen = "GENESIS", set()
    for row in rows:
        need(isinstance(row, dict) and row.get("schema") == SCHEMA,
             "incorrect issuer GDP actual schema")
        sign = row.get("record_sha256")
        need(sign == digest({k: v for k, v in row.items() if k != "record_sha256"})
             and row.get("previous_record_sha256") == prev,
             "GDP actual archive SHA chain broken")
        mid = row.get("metric_id")
        need(mid in TARGETS and mid not in seen,
             "unknown or duplicate GDP actual")
        seen.add(mid)
        t, c = TARGETS[mid], contracts[mid]
        observed = utc_iso(row.get("observed_at_utc"))
        need(c["release"] <= observed <= c["release"] + MAX_LAG,
             "GDP capture not after release in observation window")
        need(row.get("event_key") == t["key"] and
             row.get("publisher") == t["official_publisher"] and
             row.get("reference_period") == t["reference_period"] and
             row.get("source_url") == t["source_url"] and
             row.get("metric_component") == c["metric"]["component"] and
             row.get("metric_unit_hypothesis") == c["metric"]["unit"] and
             row.get("issuer_source_constraint") == t["quality_constraint"] and
             row.get("official_release_scheduled_utc") ==
             utc_text(c["release"]), "GDP series, publisher or quarter mismatch")
        need(isinstance(row.get("source_html_sha256"), str) and
             re.fullmatch("[a-f0-9]{64}", row["source_html_sha256"]),
             "issuer fingerprint absent")
        actual = row.get("actual_percent")
        need(type(actual) in (float, int) and math.isfinite(actual) and
             -30 < actual < 30, "invalid GDP actual")
        f = forecast_map.get(mid)
        need(row.get("v9_secondary_forecast_sha256") ==
             (f["record_sha256"] if f else None) and
             row.get("v9_secondary_forecast_pct") ==
             (f["forecast_value_percent"] if f else None) and
             row.get("actual_minus_v9_secondary_pp") ==
             (round(actual - f["forecast_value_percent"], 6) if f else None),
             "unproven linkage between official and V9 secondary metric")
        need(row.get("quality") == QUALITY and
             row.get("publisher_first_delivery_PIT_verified") is False and
             row.get("secondary_provider_label_not_survey_certified") is True and
             row.get("gdp_qoq_source_adjustment_not_independently_verified") is True and
             row.get("certified_macro_surprise") is None and
             row.get("FX_signal") is None and
             row.get("eligible_for_Core_Beta_Forward") is False,
             "GDP record promoted into unsupported model/surprise claims")
        prev = sign
    return prev, seen


def capture(official, forecasts, existing, now, fetch=retrieve,
            observed_clock=None):
    if observed_clock is None:
        observed_clock = lambda: now
    contracts = release_contracts(official)
    previous, seen = validate_actuals(existing, official, forecasts)
    need(isinstance(now, datetime) and now.tzinfo is not None and
         now.utcoffset() is not None, "offset-aware clock required")
    now = now.astimezone(timezone.utc)
    f_map = forecasts_by_metric(forecasts)
    added = []
    states = {}
    for mid in ORDER:
        t, c = TARGETS[mid], contracts[mid]
        release = c["release"]
        if mid in seen:
            states[mid] = "ACTUAL_ALREADY_FIRST_OBSERVED_NO_HTTP"
            continue
        if now < release:
            states[mid] = "BEFORE_RELEASE_NO_HTTP"
            continue
        if now > release + MAX_LAG:
            states[mid] = "OUTSIDE_FIRST_OBSERVATION_WINDOW_NO_HTTP"
            continue
        try:
            raw, final = fetch(t["source_url"], t["host"])
            need(final == t["source_url"], "issuer redirect changed exact URL")
            actual = PARSERS[mid](raw)
        except (Pending, OSError, TimeoutError, UnicodeError, ValueError) as exc:
            states[mid] = "SOURCE_NOT_AVAILABLE_OR_TARGET_SERIES_NOT_CERTIFIED"
            continue
        seen_at = observed_clock()
        need(isinstance(seen_at, datetime) and seen_at.tzinfo is not None and
             seen_at.utcoffset() is not None,
             "missing real source observation time")
        seen_at = seen_at.astimezone(timezone.utc)
        need(now <= seen_at <= release + MAX_LAG,
             "successful issuer observation is not after polling or within window")
        f = f_map.get(mid)
        record = {
            "schema": SCHEMA, "metric_id": mid, "event_key": t["key"],
            "publisher": t["official_publisher"],
            "reference_period": t["reference_period"],
            "metric_component": c["metric"]["component"],
            "metric_unit_hypothesis": c["metric"]["unit"],
            "issuer_source_constraint": t["quality_constraint"],
            "source_url": t["source_url"],
            "source_html_sha256": hashlib.sha256(raw).hexdigest(),
            "official_release_scheduled_utc": utc_text(release),
            "observed_at_utc": utc_text(seen_at),
            "actual_percent": actual,
            "v9_secondary_forecast_sha256": f["record_sha256"] if f else None,
            "v9_secondary_forecast_pct": f["forecast_value_percent"] if f else None,
            "actual_minus_v9_secondary_pp":
                round(actual - f["forecast_value_percent"], 6) if f else None,
            "quality": QUALITY,
            "publisher_first_delivery_PIT_verified": False,
            "secondary_provider_label_not_survey_certified": True,
            "gdp_qoq_source_adjustment_not_independently_verified": True,
            "certified_macro_surprise": None,
            "FX_signal": None,
            "eligible_for_Core_Beta_Forward": False,
            "previous_record_sha256": previous,
        }
        record["record_sha256"] = digest(record)
        added.append(record)
        previous = record["record_sha256"]
        states[mid] = "OFFICIAL_METRIC_FIRST_OBSERVED_RESEARCH_ONLY"
    result = existing + added
    validate_actuals(result, official, forecasts)
    return result, {
        "status": "UK_CH_GDP_ISSUER_FIRST_OBSERVATION_RESEARCH_V11",
        "states": states,
        "new_official_metric_actuals": len(added),
        "total_official_metric_actuals": len(result),
        "certified_macro_surprises": 0,
        "verified_event_fx_causality": 0,
        "writes_live_data": False,
        "changes_legacy_archives": False,
    }


def run(official_path=OFFICIAL, forecast_path=FORECAST_LEDGER,
        actual_path=OUT, now=None, fetch=retrieve, observed_clock=None):
    if now is None:
        now = datetime.now(timezone.utc)
    if observed_clock is None:
        observed_clock = lambda: datetime.now(timezone.utc)
    official = json.loads(Path(official_path).read_text(encoding="utf-8"))
    forecasts = read_rows(Path(forecast_path))
    old = read_rows(Path(actual_path))
    records, receipt = capture(official, forecasts, old, now, fetch,
                               observed_clock)
    if len(records) > len(old):
        with Path(actual_path).open("a", encoding="utf-8") as handle:
            for row in records[len(old):]:
                handle.write(json.dumps(row, ensure_ascii=False,
                             sort_keys=True, separators=(",", ":")) + "\n")
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--official", type=Path, default=OFFICIAL)
    p.add_argument("--forecasts", type=Path, default=FORECAST_LEDGER)
    p.add_argument("--actuals", type=Path, default=OUT)
    args = p.parse_args()
    print(json.dumps(run(args.official, args.forecasts, args.actuals),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
