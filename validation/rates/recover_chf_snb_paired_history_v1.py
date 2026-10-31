#!/usr/bin/env python3
"""Read-only SNB daily matched CHF 2Y/10Y official historical source recovery.

Strictly observe the same SNB API *spot* instrument/tenor/date basis. Recover
intermediate source-confirmed dates instead of joining stale 2Y to newer 10Y.
Never writes Rates, Macro, OIS or backtests; never auto-approves a candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from check_snb_same_basis_candidate_v1 import (
    SOURCE, KEYS, parse_candidate,
)

ROOT = Path(__file__).resolve().parents[2]
RATES = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
CONTEXT = ROOT / "live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json"
SCHEMA = "GMFQ_SNB_CHF_DAILY_PAIRED_SPOT_BACKFILL_READ_ONLY_V1"


def require(ok, explanation):
    if not ok:
        raise ValueError("SNB_PAIRED_RECOVERY_WITHHELD: " + explanation)


def verify(source: dict, rates: dict, ten: dict, *,
           asof: date, source_hash: str = "") -> dict:
    current = rates.get("CHF") or {}
    original = current.get("date")
    require(original == "2026-09-30"
            and current.get("source", "").startswith("Swiss National Bank")
            and current.get("quality") == "FULL_CURRENT_OFFICIAL"
            and current.get("2Y") == 0.287 and current.get("10Y") == 0.586,
            "unexpected or modified official CHF anchor: independent re-review")
    # Reuse original per-tenor independent source-id/unit/frequency parser.
    candidate = parse_candidate(
        source, certified_date=original,
        certified_2y=current["2Y"], certified_10y=current["10Y"])
    require(candidate.get("eligible_for_automatic_promotion") is False,
            "unapproved candidate is marked promotable")
    if candidate["status"] == "SOURCE_BASIS_NOT_RECONCILED":
        return {"schema": SCHEMA, "status": "SOURCE_BASIS_NOT_RECONCILED",
                "reason": candidate["reason"], "writes_operational_rates": False,
                "eligible_for_automatic_promotion": False}
    require(len(source["timeseries"]) == 2, "wrong number of official maturities")
    by_key = {}
    for serie in source["timeseries"]:
        key = serie["metadata"]["key"]
        require(key in KEYS.values(), "source mislabeled CHF maturity")
        observations = {}
        for ob in serie["values"]:
            d = ob["date"]
            v = ob["value"]
            require(isinstance(d, str) and
                    date.fromisoformat(d).isoformat() == d and
                    isinstance(v, (int, float)) and not isinstance(v, bool) and
                    math.isfinite(v) and -5 <= v <= 25 and
                    d not in observations,
                    "duplicate or non-numeric dated source observation")
            observations[d] = float(v)
        by_key[key] = observations
    require(set(by_key) == set(KEYS.values()), "missing official 2Y or 10Y")
    v2, v10 = by_key[KEYS["2Y"]], by_key[KEYS["10Y"]]
    common = sorted(set(v2) & set(v10))
    assert original in common
    pairs = [{
        "date": d,
        "2Y": v2[d],
        "10Y": v10[d],
        "curve_bp": round((v10[d] - v2[d]) * 100, 3)
    } for d in common if d >= original and d <= asof.isoformat()]
    require(pairs and pairs[0]["date"] == original and
            pairs[0]["2Y"] == current["2Y"] and
            pairs[0]["10Y"] == current["10Y"], "original-source anchor changed")
    missing2 = sorted(d for d in v2 if d > original and d not in v10)
    missing10 = sorted(d for d in v10 if d > original and d not in v2)
    latest = pairs[-1]
    official_ten = (
        ten.get("schema") == "GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1" and
        ten.get("provenance") == "SNB_PUBLIC_PAGE_DATED_EXACT_10Y" and
        ten.get("as_of") == latest["date"] and
        isinstance(ten.get("value_percent"), (int, float)) and
        abs(latest["10Y"] - ten["value_percent"]) <= 0.001 and
        ten.get("has_current_2y") is False and
        ten.get("eligible_for_curve_spreads") is False
    )
    age = (asof - date.fromisoformat(latest["date"])).days
    return {
        "schema": SCHEMA,
        "status": (
            "PAIRED_OFFICIAL_HISTORY_READY_FOR_REVIEW"
            if 0 <= age <= 5 and len(pairs) > 1
            else "OFFICIAL_PAIRED_HISTORY_NOT_CURRENT"
        ),
        "source": SOURCE,
        "source_response_sha256": source_hash,
        "base_date": original,
        "last_common_date": latest["date"],
        "last_common_2Y": latest["2Y"],
        "last_common_10Y": latest["10Y"],
        "last_common_curve_bp": latest["curve_bp"],
        "last_common_age_days": age,
        "paired_source_rows": pairs,
        "matched_paired_rows": len(pairs),
        "new_paired_rows": len(pairs) - 1,
        "source_has_newer_unpaired_2y": any(d > latest["date"] for d in missing2),
        "source_has_newer_unpaired_10y": any(d > latest["date"] for d in missing10),
        "newer_unpaired_dates_by_tenor": {"2Y": missing2[-5:], "10Y": missing10[-5:]},
        "separately_published_snb_10y_matches_same_date": official_ten,
        "historic_gap_backfilled_from_observations_not_interpolated": True,
        "unmatched_or_weekend_dates_fabricated": False,
        "source_latest_vintage_not_first_release_pit": True,
        "writes_operational_rates": False,
        "eligible_for_automatic_promotion": False,
        "eligible_for_core_signals": False,
        "eligible_for_backtests": False,
        "independent_publication_and_review_required": True,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", type=Path, default=None)
    p.add_argument("--asof", type=date.fromisoformat,
                   default=datetime.now(timezone.utc).date())
    p.add_argument("--output", type=Path,
                   default=Path("/tmp/snb-chf-paired-source-recovery.json"))
    args = p.parse_args()
    require(args.output.resolve().is_relative_to(Path("/tmp")),
            "output must stay out of repo and production data")
    if args.fixture:
        raw = args.fixture.read_bytes()
    else:
        day = json.loads(RATES.read_text())["CHF"]["date"]
        q = urlencode({"dimSel": "D0(CHF),D1(2J,10J)",
                       "fromDate": (date.fromisoformat(day) -
                                    timedelta(days=5)).isoformat(),
                       "toDate": args.asof.isoformat()})
        request = Request(SOURCE + "?" + q,
                          headers={"Accept": "application/json",
                                   "User-Agent": "GMFQ-SNB-Official-Paired-Review/1.0"})
        with urlopen(request, timeout=22) as response:
            require(response.status == 200 and "json" in
                    response.headers.get("content-type", "").lower(),
                    "SNB JSON API refused official paired source")
            raw = response.read(2_500_001)
            require(len(raw) < 2_500_001, "source response exceeds 2.5MB")
    result = verify(json.loads(raw), json.loads(RATES.read_text()),
                    json.loads(CONTEXT.read_text()), asof=args.asof,
                    source_hash=hashlib.sha256(raw).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2,
                                      ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "last_common_date": result.get("last_common_date"),
                      "new_paired_rows": result.get("new_paired_rows"),
                      "official_10y_agrees": result.get(
                          "separately_published_snb_10y_matches_same_date"),
                      "written_live": False, "receipt": str(args.output)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
