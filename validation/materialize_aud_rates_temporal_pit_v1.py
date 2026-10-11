#!/usr/bin/env python3
"""Read-only materializer for RBA 2Y/10Y temporal-PIT history."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

START_DATE = date(2018, 1, 1)
END_DATE = date(2026, 9, 30)
SERIES_2Y = "FCMYGBAG2D"
SERIES_10Y = "FCMYGBAG10D"
URL = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
UA = "global-macro-fx-quant/aud-rates-temporal-pit-v1"


def fetch() -> bytes:
    req = Request(URL, headers={"User-Agent": UA, "Accept": "text/csv,*/*"})
    with urlopen(req, timeout=60) as resp:
        raw = resp.read()
    if len(raw) < 1000:
        raise ValueError(f"RBA F2 response unexpectedly small: {len(raw)} bytes")
    return raw


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
    raw = fetch()
    source_sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig")
    table = list(csv.reader(io.StringIO(text)))
    if len(table) < 12:
        raise ValueError("RBA F2 unexpectedly short CSV")

    title = table[1]
    frequency = table[3]
    source = table[8]
    publication = table[9]
    series = table[10]
    if not series or series[0].strip() != "Series ID":
        raise ValueError("RBA F2 canonical Series ID row missing")
    try:
        i2 = series.index(SERIES_2Y)
        i10 = series.index(SERIES_10Y)
    except ValueError as exc:
        raise ValueError("RBA F2 required official series IDs missing") from exc

    if "2 year" not in title[i2].lower() or "10 year" not in title[i10].lower():
        raise ValueError("RBA F2 series semantic mismatch")
    if frequency[i2].strip() != "Daily" or frequency[i10].strip() != "Daily":
        raise ValueError("RBA F2 required series are no longer Daily")
    if source[i2].strip() != "RBA" or source[i10].strip() != "RBA":
        raise ValueError("RBA F2 required series source is no longer RBA")
    p2 = datetime.strptime(publication[i2].strip(), "%d-%b-%Y").date().isoformat()
    p10 = datetime.strptime(publication[i10].strip(), "%d-%b-%Y").date().isoformat()
    if p2 != p10:
        raise ValueError(f"RBA F2 publication-date mismatch: {p2} vs {p10}")

    rows: list[dict] = []
    for rec in table[11:]:
        if len(rec) <= max(i2, i10):
            continue
        ds = rec[0].strip()
        v2 = rec[i2].strip()
        v10 = rec[i10].strip()
        if not ds or not v2 or not v10:
            continue
        try:
            obs = datetime.strptime(ds, "%d-%b-%Y").date()
            y2 = float(v2)
            y10 = float(v10)
        except ValueError:
            continue
        if obs < START_DATE or obs > END_DATE:
            continue
        if not (-5.0 < y2 < 25.0 and -5.0 < y10 < 25.0):
            raise ValueError(f"RBA implausible yield for {obs}: 2Y={y2} 10Y={y10}")
        rows.append({
            "currency": "AUD",
            "observation_date": obs.isoformat(),
            "yield_2y": y2,
            "yield_10y": y10,
            "curve_bp": round((y10 - y2) * 100.0, 6),
            "source_authority": "Reserve Bank of Australia",
            "source_url_or_series_id": {"url": URL, "series_2y": SERIES_2Y, "series_10y": SERIES_10Y},
            "source_sha256_or_official_record_id": source_sha,
            "source_basis": "official_same_basis_rba_f2_government_bond_daily_yields",
            "publication_timestamp_if_verified": None,
            "availability_rule": "decision_date_strictly_after_observation_date_without_verified_row_publication_timestamp",
            "first_eligible_decision_date": (obs + timedelta(days=1)).isoformat(),
            "pit_status": "TEMPORAL_PIT_CONSERVATIVE_DATE_ONLY",
        })

    rows.sort(key=lambda r: r["observation_date"])
    dates = [r["observation_date"] for r in rows]
    if len(dates) != len(set(dates)):
        raise ValueError("RBA duplicate observation dates")
    if dates != sorted(dates):
        raise ValueError("RBA observations not monotonically ordered")
    if not dates or not dates[0].startswith("2018-"):
        raise ValueError(f"RBA history does not begin in requested start year: {dates[:1]}")
    if dates[-1] != END_DATE.isoformat():
        raise ValueError(f"RBA history does not reach pinned end date {END_DATE}: last={dates[-1] if dates else None}")
    for r in rows:
        if not (date.fromisoformat(r["first_eligible_decision_date"]) > date.fromisoformat(r["observation_date"])):
            raise ValueError(f"Temporal eligibility invariant failed: {r['observation_date']}")

    return {
        "schema": "GMFQ_AUD_RATES_TEMPORAL_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "AUD.rates_2y_10y",
        "evidence_class": "TEMPORAL_PIT_OFFICIAL_MARKET_HISTORY",
        "authority": "Reserve Bank of Australia",
        "source": "F2 Capital Market Yields – Government Bonds – Daily",
        "coverage": {"start_date": dates[0], "end_date": dates[-1], "observations": len(rows)},
        "temporal_rule": {
            "exact_publication_timestamp_verified": False,
            "same_day_use_allowed": False,
            "eligibility": "decision_date > observation_date",
            "reason": "The RBA F2 file exposes a current file publication date, not independently verified historical publication timestamps for every daily row; use conservative next-decision-point availability."
        },
        "series": {"2Y": SERIES_2Y, "10Y": SERIES_10Y},
        "current_file_publication_date": p2,
        "source_sha256": source_sha,
        "semantic_rowset_sha256": semantic_hash(rows),
        "same_basis_2y_10y": True,
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
