#!/usr/bin/env python3
"""V10: first runner-observed issuer CPI actuals, four exact BLS measures.

The source is the BLS current-release HTML. The *first observed* snapshot
is not proven to be the first publisher delivery (point-in-time). Optional
V9 secondary provider first-seen matches yield a *descriptive difference*,
never a certified market consensus surprise, policy impact or FX signal.

No writes to live_data, model, legacy V1 forecasts or V1 actuals.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re

from validation.macro.freeze_pre_release_consensus_v1 import (
    digest, scheduled, utc_iso, utc_text
)
from validation.macro.freeze_exact_metric_forecasts_v9 import (
    LEDGER as FORECAST_LEDGER, read_rows, validate_existing as validate_v9
)
from validation.macro.g8_metric_issuer_contract_v8 import metrics_for
from validation.macro import preflight_us_cpi_official_actual_v8 as bls
from validation.macro.capture_official_postrelease_actuals_v1 import Pending, retrieve

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/macro/MACRO_BLS_CPI_EXACT_ACTUAL_FIRST_SEEN_V10.jsonl"
SCHEMA = "GMFQ_BLS_CPI_EXACT_METRIC_ACTUAL_FIRST_OBSERVATION_V10"
KEY = "USD|2026-11-10|INFLATION|Consumer Price Index"
MAX_LAG = timedelta(days=7)
METRICS = tuple(bls.KEYS)
QUALITY = "ISSUER_BLS_HTML_FIRST_RUNNER_OBSERVATION_NOT_PUBLISHER_PIT"
# Independent BLS-owned summary URL protects against a temporarily stale
# or unavailable primary page; both still require the exact dated issuer issue.
ISSUER_URLS = (bls.SOURCE, "https://www.bls.gov/news.release/cpi.nr0.htm")


def need(ok, why):
    if not ok:
        raise ValueError("BLS_CPI_ACTUAL_V10_REJECTED: " + why)


def expected_release():
    stamp = scheduled(bls.TARGET)
    need(stamp is not None, "official clock unavailable")
    return stamp


def forecasts_by_metric(forecasts):
    validate_v9(forecasts)
    subset = [r for r in forecasts if r["event_key"] == KEY]
    got = {r["metric_id"]: r for r in subset}
    need(len(got) == len(subset), "duplicate V9 metric identity")
    need(set(got).issubset(set(METRICS)), "unknown V9 CPI metric")
    return got


def contract_by_metric():
    metrics = metrics_for(bls.TARGET)
    out = {row["metric_id"]: row for row in metrics}
    need(set(out) == set(METRICS), "V8 and BLS CPI parser metric contract changed")
    return out


def validate_actual_log(rows, forecasts):
    need(isinstance(rows, list), "actual rows must be a list")
    link = forecasts_by_metric(forecasts)
    units = contract_by_metric()
    release = expected_release()
    need(len(rows) in (0, len(METRICS)),
         "CPI actual release must be captured as atomic four-metric snapshot")
    previous = "GENESIS"
    captures = set()
    source_hashes = set()
    for i, row in enumerate(rows):
        need(isinstance(row, dict) and row.get("schema") == SCHEMA,
             "unknown actual record schema")
        content = {k: v for k, v in row.items() if k != "record_sha256"}
        need(row.get("record_sha256") == digest(content) and
             row.get("previous_record_sha256") == previous,
             "actual archive signature/chain mismatch")
        metric_id = METRICS[i]
        need(row.get("event_key") == KEY and row.get("metric_id") == metric_id and
             row.get("metric_component") == units[metric_id]["component"] and
             row.get("metric_unit") == units[metric_id]["unit"],
             "actual does not correspond to exact issuer metric")
        observed = utc_iso(row.get("observed_at_utc"))
        need(release <= observed <= release + MAX_LAG,
             "observed actual before release or outside review window")
        need(row.get("official_scheduled_release_utc") == utc_text(release) and
             row.get("reference_period") == "October 2026",
             "wrong BLS date or reference period")
        need(row.get("source_url") in ISSUER_URLS and
             isinstance(row.get("source_html_sha256"), str) and
             re.fullmatch("[0-9a-f]{64}", row["source_html_sha256"]),
             "unverified issuer URL or source fingerprint")
        actual = row.get("actual_percent")
        need(type(actual) in (float, int) and
             math.isfinite(actual) and abs(actual) < 40,
             "missing or impossible CPI actual")
        f = link.get(metric_id)
        expected_sha = f["record_sha256"] if f else None
        expected_value = f["forecast_value_percent"] if f else None
        expected_diff = round(actual - expected_value, 6) if f else None
        need(row.get("v9_provider_observation_sha256") == expected_sha and
             row.get("v9_provider_observation_percent") == expected_value and
             row.get("actual_minus_v9_provider_observation_pp") == expected_diff,
             "actual cannot join to another provider series or forecast vintage")
        need(row.get("quality") == QUALITY and
             row.get("publisher_first_publication_PIT_verified") is False and
             row.get("provider_is_certified_market_survey_consensus") is False and
             row.get("delta_is_certified_macro_surprise") is False and
             row.get("eligible_for_macro_surprise") is False and
             row.get("eligible_for_rates_or_fx_causality") is False and
             row.get("eligible_for_Core_Beta_Forward") is False and
             row.get("FX_signal") is None,
             "actual or proxy delta promoted to false surprise/causality")
        captures.add(row["observed_at_utc"])
        source_hashes.add(row["source_html_sha256"])
        previous = row["record_sha256"]
    need(len(captures) <= 1 and len(source_hashes) <= 1,
         "four figures not from the same immutable issuer source snapshot")
    return previous


def capture(forecasts, existing, now, fetch=retrieve, observed_clock=None):
    if observed_clock is None:
        observed_clock = lambda: now
    validate_actual_log(existing, forecasts)
    need(isinstance(now, datetime) and now.tzinfo is not None and
         now.utcoffset() is not None, "offset-aware poll time required")
    now = now.astimezone(timezone.utc)
    release = expected_release()
    base = {
        "status": "BLS_CPI_EXACT_ACTUAL_RESEARCH_ONLY",
        "event_key": KEY,
        "official_release_scheduled_utc": utc_text(release),
        "metric_actuals_archived": len(existing),
        "new_metrics_archived": 0,
        "forecast_links_available": sum(
            x["event_key"] == KEY for x in forecasts),
        "publisher_first_release_PIT_verified": False,
        "certified_consensus_surprises": 0,
        "fx_signals": 0,
        "writes_live_data": False,
        "legacy_archives_modified": False,
    }
    if existing:
        return existing, {**base, "source_status": "FOUR_METRICS_ALREADY_ARCHIVED_NO_HTTP"}
    if now < release:
        return existing, {**base, "source_status": "BEFORE_RELEASE_NO_HTTP"}
    if now > release + MAX_LAG:
        return existing, {**base, "source_status": "OUTSIDE_OBSERVATION_WINDOW_NO_HTTP"}
    failure_types = []
    raw = url = parsed = None
    for issuer_url in ISSUER_URLS:
        try:
            candidate_raw, final_url = fetch(issuer_url, "www.bls.gov")
            need(final_url == issuer_url,
                 "BLS final URL must equal approved HTTPS publisher URL")
            candidate_parsed = bls.parse(raw=candidate_raw)
            raw, url, parsed = candidate_raw, final_url, candidate_parsed
            break
        except (Pending, OSError, TimeoutError, UnicodeError, ValueError) as exc:
            failure_types.append(type(exc).__name__)
    if parsed is None:
        return existing, {**base,
            "source_status": "ISSUER_NOT_AVAILABLE_OR_EXACT_RELEASE_NOT_PARSABLE",
            "failure_types": failure_types}
    actuals = parsed["metric_actual_pct"]
    need(set(actuals) == set(METRICS), "not all four CPI metrics were parsed")
    observed = observed_clock()
    need(isinstance(observed, datetime) and observed.tzinfo is not None
         and observed.utcoffset() is not None,
         "successful BLS download requires offset-aware observation clock")
    observed = observed.astimezone(timezone.utc)
    need(now <= observed <= release + MAX_LAG,
         "actual observation cannot precede poll or exceed review window")
    link = forecasts_by_metric(forecasts)
    units = contract_by_metric()
    source_hash = hashlib.sha256(raw).hexdigest()
    previous = "GENESIS"
    added = []
    for metric_id in METRICS:
        actual = actuals[metric_id]
        f = link.get(metric_id)
        candidate = f["forecast_value_percent"] if f else None
        record = {
            "schema": SCHEMA,
            "event_key": KEY,
            "metric_id": metric_id,
            "metric_component": units[metric_id]["component"],
            "metric_unit": units[metric_id]["unit"],
            "reference_period": parsed["reference_period"],
            "official_scheduled_release_utc": utc_text(release),
            "observed_at_utc": utc_text(observed),
            "source_url": url,
            "source_html_sha256": source_hash,
            "actual_percent": actual,
            "v9_provider_observation_sha256": f["record_sha256"] if f else None,
            "v9_provider_observation_percent": candidate,
            "actual_minus_v9_provider_observation_pp":
                round(actual - candidate, 6) if f else None,
            "quality": QUALITY,
            "publisher_first_publication_PIT_verified": False,
            "provider_is_certified_market_survey_consensus": False,
            "delta_is_certified_macro_surprise": False,
            "eligible_for_macro_surprise": False,
            "eligible_for_rates_or_fx_causality": False,
            "eligible_for_Core_Beta_Forward": False,
            "FX_signal": None,
            "previous_record_sha256": previous,
        }
        record["record_sha256"] = digest(record)
        added.append(record)
        previous = record["record_sha256"]
    result = existing + added
    validate_actual_log(result, forecasts)
    return result, {
        **base,
        "source_status": "OFFICIAL_CPI_FOUR_METRICS_OBSERVED_AND_ARCHIVED_NOT_PIT",
        "metric_actuals_archived": len(result),
        "new_metrics_archived": len(added),
        "provider_observation_links": sum(
            x["v9_provider_observation_sha256"] is not None for x in added),
        "source_html_sha256": source_hash,
        "issuer_source_url": url,
        "observed_at_utc": utc_text(observed),
        "metric_actual_percent": {
            x["metric_id"]: x["actual_percent"] for x in added},
    }


def run(forecast_path=FORECAST_LEDGER, actual_path=OUT, now=None,
        fetch=retrieve, observed_clock=None):
    if now is None:
        now = datetime.now(timezone.utc)
    if observed_clock is None:
        observed_clock = lambda: datetime.now(timezone.utc)
    forecasts = read_rows(Path(forecast_path))
    old = read_rows(Path(actual_path))
    records, receipt = capture(
        forecasts, old, now, fetch=fetch, observed_clock=observed_clock)
    if len(records) > len(old):
        with Path(actual_path).open("a", encoding="utf-8") as out:
            for row in records[len(old):]:
                out.write(json.dumps(row, ensure_ascii=False,
                                     sort_keys=True, separators=(",", ":")) + "\n")
    return receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--forecasts", type=Path, default=FORECAST_LEDGER)
    p.add_argument("--actuals", type=Path, default=OUT)
    args = p.parse_args()
    print(json.dumps(run(args.forecasts, args.actuals),
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
