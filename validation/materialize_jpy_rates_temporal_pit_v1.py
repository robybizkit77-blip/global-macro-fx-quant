#!/usr/bin/env python3
"""Read-only materializer for Japan MOF JGB 2Y/10Y temporal-PIT history."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

START_DATE = date(2018, 1, 1)
END_DATE = date(2026, 10, 6)
HIST_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
CURRENT_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"
UA = "global-macro-fx-quant/jpy-rates-temporal-pit-v1"


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/csv,text/plain,*/*"})
    with urlopen(req, timeout=60) as resp:
        raw = resp.read()
    if not raw:
        raise ValueError(f"MOF empty response: {url}")
    return raw


def decode_csv(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    raise ValueError("Unable to decode MOF CSV")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def parse_date(s: str) -> date:
    s = str(s).strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    raise ValueError(f"Bad MOF date: {s!r}")


def locate_header(rows: list[list[str]]) -> tuple[int, int, int, int]:
    for ri, row in enumerate(rows[:25]):
        nr = [norm(x) for x in row]
        date_idx = next((i for i, x in enumerate(nr) if x in {"date", "recorddate"} or "date" in x), None)
        two = next((i for i, x in enumerate(nr) if x in {"2y", "2year", "2years", "2yr", "2yrs"}), None)
        ten = next((i for i, x in enumerate(nr) if x in {"10y", "10year", "10years", "10yr", "10yrs"}), None)
        if date_idx is not None and two is not None and ten is not None:
            return ri, date_idx, two, ten
    for ri, row in enumerate(rows[:25]):
        nr = [norm(x) for x in row]
        date_idx = next((i for i, x in enumerate(nr) if "date" in x), None)
        two = next((i for i, x in enumerate(nr) if "2" in x and ("year" in x or x.endswith("y"))), None)
        ten = next((i for i, x in enumerate(nr) if "10" in x and ("year" in x or x.endswith("y"))), None)
        if date_idx is not None and two is not None and ten is not None:
            return ri, date_idx, two, ten
    raise ValueError("MOF Date/2Y/10Y header not found")


def parse_source(raw: bytes, source_url: str) -> list[dict]:
    source_sha = hashlib.sha256(raw).hexdigest()
    table = list(csv.reader(io.StringIO(decode_csv(raw))))
    if not table:
        raise ValueError(f"MOF CSV empty: {source_url}")
    hi, di, i2, i10 = locate_header(table)
    parsed: list[dict] = []
    for rec in table[hi + 1 :]:
        if len(rec) <= max(di, i2, i10):
            continue
        try:
            obs = parse_date(rec[di])
            y2 = float(rec[i2])
            y10 = float(rec[i10])
        except Exception:
            continue
        if obs < START_DATE or obs > END_DATE:
            continue
        if not (-5.0 < y2 < 25.0 and -5.0 < y10 < 25.0):
            raise ValueError(f"MOF implausible yield for {obs}: 2Y={y2} 10Y={y10}")
        parsed.append({
            "currency": "JPY",
            "observation_date": obs.isoformat(),
            "yield_2y": y2,
            "yield_10y": y10,
            "curve_bp": round((y10 - y2) * 100.0, 6),
            "source_authority": "Japan Ministry of Finance",
            "source_url_or_series_id": source_url,
            "source_sha256_or_official_record_id": source_sha,
            "source_basis": "official_same_basis_jgb_interest_rate_csv",
            "publication_timestamp_if_verified": None,
            "availability_rule": "decision_date_strictly_after_observation_date_without_verified_publication_timestamp",
            "first_eligible_decision_date": (obs + timedelta(days=1)).isoformat(),
            "pit_status": "TEMPORAL_PIT_CONSERVATIVE_DATE_ONLY",
        })
    return parsed


def semantic_hash(rows: list[dict]) -> str:
    fields = ("currency", "observation_date", "yield_2y", "yield_10y", "source_basis", "first_eligible_decision_date")
    payload = [{k: r[k] for k in fields} for r in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def materialize() -> dict:
    hist_raw = fetch(HIST_URL)
    current_raw = fetch(CURRENT_URL)
    hist_rows = parse_source(hist_raw, HIST_URL)
    current_rows = parse_source(current_raw, CURRENT_URL)

    by_date: dict[str, dict] = {}
    overlaps = 0
    for row in hist_rows + current_rows:
        d = row["observation_date"]
        prior = by_date.get(d)
        if prior is None:
            by_date[d] = row
            continue
        overlaps += 1
        if float(prior["yield_2y"]) != float(row["yield_2y"]) or float(prior["yield_10y"]) != float(row["yield_10y"]):
            raise ValueError(
                f"MOF overlapping official files disagree on {d}: "
                f"hist=({prior['yield_2y']},{prior['yield_10y']}) current=({row['yield_2y']},{row['yield_10y']})"
            )
        # Prefer the historical archive record when both official files agree;
        # this preserves stable provenance for the archived segment.
        if prior["source_url_or_series_id"] == CURRENT_URL and row["source_url_or_series_id"] == HIST_URL:
            by_date[d] = row

    rows = [by_date[d] for d in sorted(by_date)]
    dates = [r["observation_date"] for r in rows]
    if len(dates) != len(set(dates)):
        raise ValueError("MOF duplicate observation dates after merge")
    if dates != sorted(dates):
        raise ValueError("MOF observations not monotonically ordered")
    if not dates or not dates[0].startswith("2018-"):
        raise ValueError(f"MOF history does not begin in requested start year: {dates[:1]}")
    if dates[-1] != END_DATE.isoformat():
        raise ValueError(f"MOF history does not reach pinned end date {END_DATE}: last={dates[-1] if dates else None}")
    for r in rows:
        if not (date.fromisoformat(r["first_eligible_decision_date"]) > date.fromisoformat(r["observation_date"])):
            raise ValueError(f"Temporal eligibility invariant failed: {r['observation_date']}")

    return {
        "schema": "GMFQ_JPY_RATES_TEMPORAL_PIT_EVIDENCE_V1_RUNTIME",
        "status": "PASS",
        "target": "JPY.rates_2y_10y",
        "evidence_class": "TEMPORAL_PIT_OFFICIAL_MARKET_HISTORY",
        "authority": "Japan Ministry of Finance",
        "source": "JGB Interest Rate historical + current official CSVs",
        "coverage": {"start_date": dates[0], "end_date": dates[-1], "observations": len(rows)},
        "temporal_rule": {
            "exact_publication_timestamp_verified": False,
            "same_day_use_allowed": False,
            "eligibility": "decision_date > observation_date",
            "reason": "No independently verified official publication timestamp is attached to each historical row in the files; use conservative next-decision-point availability."
        },
        "source_hashes": {
            "historical_jgbcme_all": hashlib.sha256(hist_raw).hexdigest(),
            "current_jgbcme": hashlib.sha256(current_raw).hexdigest(),
        },
        "official_file_overlap_rows": overlaps,
        "official_overlap_value_conflict": False,
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
