#!/usr/bin/env python3
"""Read-only materializer for Bank of Canada 2Y/10Y temporal-PIT history."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

START_DATE = date(2018, 1, 1)
END_DATE = date(2026, 10, 6)
SERIES_2Y = "BD.CDN.2YR.DQ.YLD"
SERIES_10Y = "BD.CDN.10YR.DQ.YLD"
BASE_URL = "https://www.bankofcanada.ca/valet/observations/group/bond_yields_benchmark/json"
UA = "global-macro-fx-quant/cad-rates-temporal-pit-v1"


def source_url() -> str:
    return f"{BASE_URL}?start_date={START_DATE.isoformat()}&end_date={END_DATE.isoformat()}"


def fetch() -> bytes:
    req = Request(source_url(), headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=60) as resp:
        raw = resp.read()
        ctype = (resp.headers.get("Content-Type") or "").lower()
    if len(raw) < 1000:
        raise ValueError(f"Bank of Canada response unexpectedly small: {len(raw)} bytes")
    if "json" not in ctype and not raw.lstrip().startswith(b"{"):
        raise ValueError(f"Bank of Canada response is not JSON: {ctype}")
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
    doc = json.loads(raw.decode("utf-8"))
    detail = doc.get("seriesDetail", {})
    if SERIES_2Y not in detail or SERIES_10Y not in detail:
        raise ValueError("Expected Bank of Canada benchmark series are missing")

    rows: list[dict] = []
    for rec in doc.get("observations", []):
        ds = rec.get("d")
        if not ds:
            continue
        obs = date.fromisoformat(ds)
        if obs < START_DATE or obs > END_DATE:
            continue
        try:
            y2 = float(rec[SERIES_2Y]["v"])
            y10 = float(rec[SERIES_10Y]["v"])
        except Exception:
            continue
        if not (-5.0 < y2 < 25.0 and -5.0 < y10 < 25.0):
            raise ValueError(f"BoC implausible yield for {obs}: 2Y={y2} 10Y={y10}")
        rows.append({
            "currency": "CAD",
            "observation_date": obs.isoformat(),
            "yield_2y": y2,
            "yield_10y": y10,
            "curve_bp": round((y10 - y2) * 100.0, 6),
            "source_authority": "Bank of Canada",
            "source_url_or_series_id": {
                "url": source_url(),
                "series_2y": SERIES_2Y,
                "series_10y": SERIES_10Y,
            },
            "source_sha256_or_official_record_id": source_sha,
            "source_basis": "official_same_basis_selected_benchmark_government_of_canada_bond_yields",
            "publication_timestamp_if_verified": None,
            "availability_rule": "decision_date_strictly_after_observation_date_without_verified_publication_timestamp",
            "first_eligible_decision_date": (obs + timedelta(days=1)).isoformat(),
            "pit_status": "TEMPORAL_PIT_CONSERVATIVE_DATE_ONLY",
        })

    rows.sort(key=lambda r: r["observation_date"])
    dates = [r["observation_date"] for r in rows]
    if len(dates) != len(set(dates)):
        raise ValueError("BoC duplicate observation dates")
    if dates != sorted(dates):
        raise ValueError("BoC observations not monotonically ordered")
    if not dates or not dates[0].startswith("2018-"):
        raise ValueError(f"BoC history does not begin in requested start year: {dates[:1]}")
    if dates[-1] != END_DATE.isoformat():
        raise ValueError(f"BoC history does not reach pinned end date {END_DATE}: last={dates[-1] if dates else None}")
    for r in rows:
        if not (date.fromisoformat(r["first_eligible_decision_date"]) > date.fromisoformat(r["observation_date"])):
            raise ValueError(f"Temporal eligibility invariant failed: {r['observation_date']}")

    return {
        "schema": "GMFQ_CAD_RATES_TEMPORAL_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "CAD.rates_2y_10y",
        "evidence_class": "TEMPORAL_PIT_OFFICIAL_MARKET_HISTORY",
        "authority": "Bank of Canada",
        "source": "Valet API selected benchmark Government of Canada bond yields",
        "coverage": {"start_date": dates[0], "end_date": dates[-1], "observations": len(rows)},
        "temporal_rule": {
            "exact_publication_timestamp_verified": False,
            "same_day_use_allowed": False,
            "eligibility": "decision_date > observation_date",
            "reason": "No independently verified official publication timestamp is attached to each historical daily row; use conservative next-decision-point availability."
        },
        "series": {"2Y": SERIES_2Y, "10Y": SERIES_10Y},
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
