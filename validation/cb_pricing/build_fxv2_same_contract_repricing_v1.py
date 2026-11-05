#!/usr/bin/env python3
"""Dated same-listed-contract futures moves for FX Quant V2 research ONLY.

Compute Δ1D only against the *previous calendar weekday's* immutable quote
of the exact same exchange/contract/expiry; Δ1W against exactly seven calendar
days prior. Missing dates, changed contracts, or ANY unresolved same-day source
conflicts produce null, never invented changes. Does not touch official OIS,
FX Core, expected policy paths, backtests or trade signals.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from ois_same_contract_history_v1 import (
    HISTORY, SOURCE, candidates, load_history, quote_fingerprint,
    record_key, require,
)
from reconcile_ois_secondary_conflicts_v1 import (
    CONFLICTS, read_conflicts, validate_conflict_lineage,
)

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "site/fx-quant-v2/ois-same-contract-repricing-research.json"
SCHEMA = "GMFQ_FXV2_SAME_CONTRACT_FUTURES_MOVES_V1"
CURRENCIES = ("USD", "EUR", "CHF")
TENORS = ("3m", "6m", "12m")


def prior_calendar_weekday(day: date) -> date:
    previous = day - timedelta(days=1)
    while previous.weekday() >= 5:
        previous -= timedelta(days=1)
    return previous


def build(feed: dict, archive: list[dict], conflicts: list[dict]) -> dict:
    quality = validate_conflict_lineage(feed, archive, conflicts)
    current, excluded = candidates(feed)
    current_by_tenor = {(r["currency"], r["observed_under_horizon"]): r for r in current}
    known = {record_key(r): r for r in archive}
    disputed = {tuple(e["key"]) for e in conflicts}
    result = {}
    all_status = []
    latest = []
    first_verified_captures = []
    for ccy in CURRENCIES:
        out = {}
        for tenor in TENORS:
            row = current_by_tenor.get((ccy, tenor))
            # The feed may hold a quarantined/unverified raw quote: never
            # substitute the last known price without a matching source key.
            raw = ((feed.get("currencies") or {}).get(ccy) or {}).get("horizons", {}).get(tenor) or {}
            item = {
                "status": "UNVERIFIED_CURRENT_SOURCE",
                "contract": raw.get("contract"),
                "symbol": raw.get("symbol"),
                "expiration": raw.get("expiration"),
                "as_of": raw.get("quote_as_of"),
                "rate_pct": None,
                "change_1d_bp": None,
                "change_1w_bp": None,
                "one_day": None,
                "one_week": None,
                "source_type": "SECONDARY_LISTED_FUTURES_NOT_OIS",
                "source_method": "TRADINGVIEW_DATED_FUTURES_SSR_V2",
                "official_ois": False,
                "policy_repricing_signal": False,
                "fx_signal": None,
            }
            if row is not None:
                key = record_key(row)
                item.update(contract=row["contract"], symbol=row["symbol"],
                            expiration=row["expiration"], as_of=row["observation_date"])
                latest.append(row["observation_date"])
                if key in disputed:
                    item["status"] = "QUARANTINED_CURRENT_DAY"
                elif key not in known:
                    item["status"] = "CURRENT_NOT_YET_ARCHIVED"
                else:
                    signed = known[key]
                    require(quote_fingerprint(row) == quote_fingerprint(signed),
                            f"{ccy}/{tenor}: immutable current quote changed")
                    # Stable first-seen evidence, NOT a new timestamp from
                    # a source recheck with unchanged market bars.
                    first_verified_captures.append(signed["first_seen_at_utc"])
                    item["rate_pct"] = row["implied_rate"]
                    item["status"] = "VERIFIED_CONTRACT_NO_MATCHED_REFERENCE"
                    present = date.fromisoformat(row["observation_date"])
                    references = (
                        ("one_day", prior_calendar_weekday(present)),
                        ("one_week", present - timedelta(days=7)),
                    )
                    for label, ref_day in references:
                        reference_key = (ccy, row["contract"], ref_day.isoformat())
                        previous = known.get(reference_key)
                        if not previous or reference_key in disputed:
                            continue
                        require(previous["symbol"] == row["symbol"]
                                and previous["exchange"] == row["exchange"]
                                and previous["expiration"] == row["expiration"]
                                and previous["source_method"] == row["source_method"]
                                and previous["source_timestamp_evidence"] ==
                                    row["source_timestamp_evidence"],
                                "same contract/source identity mismatch")
                        bp = round((row["implied_rate"] - previous["implied_rate"]) * 100, 4)
                        item[label] = {
                            "from_date": previous["observation_date"],
                            "to_date": row["observation_date"],
                            "change_bp": bp,
                            "same_contract": True,
                            "same_expiration": True,
                            "observation_gap_calendar_days": (present - ref_day).days,
                            "reference_rate_pct": previous["implied_rate"],
                            "current_rate_pct": row["implied_rate"],
                            "not_policy_rate": True,
                        }
                        item["change_1d_bp" if label == "one_day" else "change_1w_bp"] = bp
                    if item["one_day"] or item["one_week"]:
                        item["status"] = "VERIFIED_SAME_CONTRACT_PRICE_CHANGE"
            else:
                if raw.get("quote_timestamp_source") == "QUARANTINED_SAME_CONTRACT_SAME_DAY":
                    item["status"] = "QUARANTINED_CURRENT_DAY"
            all_status.append(item["status"])
            out[tenor] = item
        result[ccy] = out
    return {
        "schema": SCHEMA,
        "data_as_of": max(latest) if latest else None,
        "source_capture_at_utc": max(first_verified_captures) if first_verified_captures else None,
        "source_description": "Secondary source daily futures bars · immutable same-listed-contract archive",
        "source_archive_rows": len(archive),
        "unresolved_source_conflict_events": len(conflicts),
        "source_conflict_lineage_verified": quality["journal_events_validated"],
        "snapshot_research_only": True,
        "eligible_for_fx_engine": False,
        "eligible_for_backtests_as_official_ois": False,
        "eligible_for_policy_repricing_signals": False,
        "official_ois_created": False,
        "unknown_is_null_not_zero": True,
        "strict_reference_dates": {
            "one_day": "exact previous calendar weekday; market holiday remains missing",
            "one_week": "exact seven-calendar-day-ago quote",
            "cross_contract_joins": False,
            "quarantined_reference_used": False,
        },
        "summary": {
            "currencies": 3,
            "horizons": 9,
            "with_verified_1d": sum(
                result[c][h]["one_day"] is not None for c in CURRENCIES for h in TENORS),
            "with_verified_1w": sum(
                result[c][h]["one_week"] is not None for c in CURRENCIES for h in TENORS),
            "withheld_or_unmatched": sum(
                s != "VERIFIED_SAME_CONTRACT_PRICE_CHANGE" for s in all_status),
            "generated_ois_signals": 0, "generated_fx_signals": 0,
        },
        "currencies": result,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quotes", type=Path, default=SOURCE)
    parser.add_argument("--history", type=Path, default=HISTORY)
    parser.add_argument("--conflicts", type=Path, default=CONFLICTS)
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    doc = build(json.loads(args.quotes.read_text(encoding="utf-8")),
                load_history(args.history), read_conflicts(args.conflicts))
    if args.check:
        require(args.output.exists(), "expected same-contract public research missing")
        require(json.loads(args.output.read_text(encoding="utf-8")) == doc,
                "published same-contract research differs from validated sources")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False)
                               + "\n", encoding="utf-8")
    print("FXV2_SAME_CONTRACT_REPRICING_RESEARCH", json.dumps(
        {"status": "CHECK_PASS" if args.check else "WRITTEN",
         "data_as_of": doc["data_as_of"],
         "summary": doc["summary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
