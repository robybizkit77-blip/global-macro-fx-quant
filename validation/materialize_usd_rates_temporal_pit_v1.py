#!/usr/bin/env python3
"""Read-only materializer for U.S. Treasury 2Y/10Y temporal-PIT history."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

START_YEAR = 2018
END_DATE = date(2026, 10, 6)
UA = "global-macro-fx-quant/usd-rates-temporal-pit-v1"
BASE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"


def source_url(year: int) -> str:
    return f"{BASE_URL}?data=daily_treasury_yield_curve&field_tdr_date_value={year}"


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1"})
    with urlopen(req, timeout=60) as resp:
        raw = resp.read()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "xml" not in ctype and not raw.lstrip().startswith(b"<?xml"):
            raise ValueError(f"Treasury response is not XML: {url} ({ctype})")
        if len(raw) < 1000:
            raise ValueError(f"Treasury XML unexpectedly small: {url} ({len(raw)} bytes)")
        return raw


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_year(raw: bytes, year: int) -> list[dict]:
    root = ET.fromstring(raw)
    source_sha = hashlib.sha256(raw).hexdigest()
    rows: list[dict] = []
    for elem in root.iter():
        if local(elem.tag).lower() != "properties":
            continue
        props = {local(child.tag): (child.text or "").strip() for child in list(elem)}
        ds = props.get("NEW_DATE") or props.get("Date") or props.get("DATE")
        y2s = props.get("BC_2YEAR")
        y10s = props.get("BC_10YEAR")
        if not ds:
            continue
        if not y2s or not y10s:
            raise ValueError(f"Treasury 2Y/10Y missing for record {ds!r} in {year}")
        obs = datetime.fromisoformat(ds.replace("Z", "+00:00")).date()
        if obs.year != year:
            raise ValueError(f"Treasury year mismatch: requested={year} record={obs}")
        if obs < date(START_YEAR, 1, 1) or obs > END_DATE:
            continue
        y2 = float(y2s)
        y10 = float(y10s)
        if not (-5.0 < y2 < 25.0 and -5.0 < y10 < 25.0):
            raise ValueError(f"Treasury implausible yield for {obs}: 2Y={y2} 10Y={y10}")
        rows.append({
            "currency": "USD",
            "observation_date": obs.isoformat(),
            "yield_2y": y2,
            "yield_10y": y10,
            "curve_bp": round((y10 - y2) * 100.0, 6),
            "source_authority": "U.S. Department of the Treasury",
            "source_family": "Daily Treasury Par Yield Curve Rates",
            "source_url": source_url(year),
            "source_year": year,
            "source_sha256": source_sha,
            "source_basis": "official_same_basis_daily_par_yield_curve",
            "publication_timestamp_verified": False,
            "availability_rule": "decision_date_strictly_after_observation_date_without_verified_publication_timestamp",
            "first_eligible_decision_date": (obs + timedelta(days=1)).isoformat(),
            "pit_status": "TEMPORAL_PIT_CONSERVATIVE_DATE_ONLY",
        })
    if not rows:
        raise ValueError(f"Treasury produced no usable 2Y/10Y observations for {year}")
    return rows


def semantic_hash(rows: list[dict]) -> str:
    fields = (
        "currency",
        "observation_date",
        "yield_2y",
        "yield_10y",
        "source_basis",
        "first_eligible_decision_date",
    )
    payload = [{k: r[k] for k in fields} for r in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def materialize() -> dict:
    rows: list[dict] = []
    annual_hashes: dict[str, str] = {}
    for year in range(START_YEAR, END_DATE.year + 1):
        raw = fetch(source_url(year))
        annual_hashes[str(year)] = hashlib.sha256(raw).hexdigest()
        parsed = parse_year(raw, year)
        rows.extend(parsed)
        print(f"[year {year}] rows={len(parsed)} sha={annual_hashes[str(year)][:12]}", flush=True)
        time.sleep(0.25)

    rows.sort(key=lambda r: r["observation_date"])
    dates = [r["observation_date"] for r in rows]
    if len(dates) != len(set(dates)):
        raise ValueError("Treasury duplicate observation dates")
    if dates != sorted(dates):
        raise ValueError("Treasury observations not monotonically ordered")
    if not dates or dates[0][:4] != str(START_YEAR):
        raise ValueError("Treasury history does not begin in requested start year")
    if dates[-1] != END_DATE.isoformat():
        raise ValueError(f"Treasury history does not reach pinned end date {END_DATE}: last={dates[-1] if dates else None}")
    for r in rows:
        if not (date.fromisoformat(r["first_eligible_decision_date"]) > date.fromisoformat(r["observation_date"])):
            raise ValueError(f"Temporal eligibility invariant failed: {r['observation_date']}")

    return {
        "schema": "GMFQ_USD_RATES_TEMPORAL_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "USD.rates_2y_10y",
        "evidence_class": "TEMPORAL_PIT_OFFICIAL_MARKET_HISTORY",
        "authority": "U.S. Department of the Treasury",
        "source": "Daily Treasury Par Yield Curve Rates XML annual feeds",
        "coverage": {
            "start_year": START_YEAR,
            "end_date": END_DATE.isoformat(),
            "observations": len(rows),
        },
        "temporal_rule": {
            "exact_publication_timestamp_verified": False,
            "same_day_use_allowed": False,
            "eligibility": "decision_date > observation_date",
            "reason": "No independently verified official publication timestamp is attached to each historical daily row; use conservative next-decision-point availability."
        },
        "annual_source_hashes": annual_hashes,
        "semantic_rowset_sha256": semantic_hash(rows),
        "same_basis_2y_10y": True,
        "current_revised_macro_history_used": False,
        "secondary_source_fallback_used": False,
        "changes_live_data": False,
        "changes_engine_rules": False,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    evidence = materialize()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
