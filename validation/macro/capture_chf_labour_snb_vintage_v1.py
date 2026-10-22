#!/usr/bin/env python3
"""Read-only source-byte capture of the current SNB/SECO CHF labour cube.

This captures what our client sees *now*. It CANNOT certify historical initial
publication, source-side release instant, or publication precision on 2026-10-06.
Do not use to auto-promote PIT, Macro scores, pair signals, or the public UI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

URL = "https://data.snb.ch/api/cube/amarbma/data/json/en"
LABEL = "Jobless rate - Seasonally adjusted"
SCHEMA = "GMFQ_CHF_LABOUR_SNB_READONLY_CAPTURE_V1"
MAX_BYTES = 10 * 1024 * 1024


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("CHF_SNB_CAPTURE_REJECTED: " + reason)


def parse_source(raw: bytes) -> dict:
    data = json.loads(raw)
    require(isinstance(data, dict) and isinstance(data.get("timeseries"), list),
            "missing official timeseries collection")
    hits = []
    for item in data["timeseries"]:
        if not isinstance(item, dict):
            continue
        header = item.get("header")
        if (isinstance(header, list) and len(header) == 1 and
            isinstance(header[0], dict) and header[0].get("dim") == "Overview" and
            header[0].get("dimItem") == LABEL):
            hits.append(item)
    require(len(hits) == 1, "ambiguous seasonally adjusted rate identity")
    values = hits[0].get("values")
    require(isinstance(values, list) and bool(values), "missing series values")
    normalized = {}
    for item in values:
        require(isinstance(item, dict), "invalid observation payload")
        period, v = item.get("date"), item.get("value")
        require(isinstance(period, str) and re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", period),
                "invalid monthly period")
        require(type(v) in (float, int) and math.isfinite(v), "invalid numeric rate")
        require(period not in normalized, "duplicate month in source cube")
        normalized[period] = v
    sorted_values = [{"period": k, "value": normalized[k]} for k in sorted(normalized)]
    return {"latest_period": sorted_values[-1]["period"],
            "latest_value": sorted_values[-1]["value"],
            "observations": sorted_values,
            "observation_count": len(sorted_values)}


def record_capture(raw: bytes, headers: dict, started: datetime, ended: datetime,
                   response_url: str, *, expected_period: str | None = None) -> dict:
    target = urlsplit(response_url)
    require(target.scheme == "https" and target.hostname == "data.snb.ch" and
            target.username is None and target.password is None and target.path == urlsplit(URL).path,
            "unexpected final source URL")
    require(started.tzinfo is not None and ended.tzinfo is not None and started <= ended,
            "invalid retrieval UTC clock")
    require(raw and len(raw) <= MAX_BYTES, "missing or oversized source payload")
    core = parse_source(raw)
    if expected_period is not None:
        require(core["latest_period"] == expected_period,
                "source latest period differs from explicit requested period")
    return {"schema": SCHEMA, "identity": "CHF.labour", "authority": "SECO",
            "official_transport": "Swiss National Bank data portal",
            "cube": "amarbma", "series_label": LABEL, "source_url": URL,
            "observation_frequency": "M", "unit": "percent", "transformation": "level",
            "retrieval_started_utc": started.astimezone(timezone.utc).isoformat(),
            "retrieval_completed_utc": ended.astimezone(timezone.utc).isoformat(),
            "http_date_as_reported": headers.get("date"),
            "http_etag_as_reported": headers.get("etag"),
            "http_last_modified_as_reported": headers.get("last-modified"),
            "raw_payload_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_payload_bytes": len(raw),
            "latest_period": core["latest_period"],
            "latest_value": core["latest_value"],
            "observation_count": core["observation_count"],
            "provenance_status": "CONTEMPORANEOUS_CLIENT_CAPTURE_NOT_HISTORICAL_INITIAL_RELEASE",
            "first_release_instant_utc": None,
            "first_release_exact_value_certified": False,
            "historical_vintages_certified": False,
            "safe_to_publish_new_D": False,
            "live_data_written": False}


def fetch_source() -> tuple[bytes, dict, datetime, datetime, str]:
    req = urllib.request.Request(URL, headers={
        "User-Agent": "global-macro-fx-quant-pit-research/1.0", "Accept": "application/json"})
    started = datetime.now(timezone.utc)
    with urllib.request.urlopen(req, timeout=35) as res:
        require(res.status == 200, "SNB non-200 response")
        require("json" in (res.headers.get("Content-Type") or "").lower(),
                "unexpected SNB response MIME type")
        raw = res.read(MAX_BYTES + 1)
        response_url = res.geturl()
        headers = {k.lower(): v for k, v in res.headers.items()}
    ended = datetime.now(timezone.utc)
    return raw, headers, started, ended, response_url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--expected-period", type=str,
                    help="Optional YYYY-MM strict freshness guard; not a past-vintage query")
    args = ap.parse_args()
    if args.expected_period is not None:
        require(re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", args.expected_period),
                "invalid expected period")
    require(not args.output_dir.is_symlink(), "symlink output directory rejected")
    raw, headers, started, ended, response_url = fetch_source()
    record = record_capture(raw, headers, started, ended, response_url,
                            expected_period=args.expected_period)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Write only evidence in the explicitly requested output folder, never live_data.
    (args.output_dir / "snb_amarbma_raw.json").write_bytes(raw)
    (args.output_dir / "capture_manifest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
