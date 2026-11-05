#!/usr/bin/env python3
"""Publish SNB CHF matched-date 2Y/10Y *historical research* to FX Quant V2.

No canonical Rates, OIS, signals, backtest, or current-market claim is written.
The statistical history can be valid even if its last observation is not a live quote.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date
from pathlib import Path

SCHEMA = "GMFQ_FXV2_CHF_SNB_PAIRED_HISTORY_V1"
EVIDENCE_SCHEMA = "GMFQ_SNB_CHF_DAILY_PAIRED_SPOT_BACKFILL_READ_ONLY_V1"
SOURCE = "https://data.snb.ch/api/cube/rendeiduebd/data/json/en"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("CHF_V2_HISTORY_REJECTED: " + message)


def build(evidence: dict, previous: dict | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    require(evidence.get("schema") == EVIDENCE_SCHEMA, "source receipt schema")
    require(evidence.get("status") in (
        "PAIRED_OFFICIAL_HISTORY_READY_FOR_REVIEW",
        "OFFICIAL_PAIRED_HISTORY_NOT_CURRENT",
    ), "invalid receipt status")
    require(evidence.get("source") == SOURCE, "not the anchored official SNB spot cube")
    require(evidence.get("paired_source_ready_for_historical_review") is True,
            "historical research not eligible")
    for name in ("writes_operational_rates", "eligible_for_automatic_promotion",
                 "eligible_for_core_signals", "eligible_for_backtests",
                 "current_session_government_rates_certified"):
        require(evidence.get(name) is False, "unexpected production eligibility: " + name)
    require(evidence.get("source_latest_vintage_not_first_release_pit") is True,
            "missing vintage warning")
    require(evidence.get("historic_gap_backfilled_from_observations_not_interpolated") is True
            and evidence.get("unmatched_or_weekend_dates_fabricated") is False,
            "source history might contain imputed dates")
    digest = evidence.get("source_response_sha256", "")
    require(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", digest)),
            "missing source digest")
    source_rows = evidence.get("paired_source_rows")
    require(isinstance(source_rows, list) and len(source_rows) >= 3,
            "insufficient source observations")
    require(len(source_rows) == evidence.get("matched_paired_rows")
            and len(source_rows) - 1 == evidence.get("new_paired_rows"),
            "count mismatch")
    rows = []
    seen = set()
    for item in source_rows:
        raw_date = item.get("date")
        require(isinstance(raw_date, str), "date type")
        d = date.fromisoformat(raw_date)
        require(d.isoformat() == raw_date and d.weekday() < 5 and d <= today
                and raw_date not in seen, "date range/order/duplication")
        require(not rows or rows[-1]["date"] < raw_date, "unsorted source dates")
        y2, y10, curve = item.get("2Y"), item.get("10Y"), item.get("curve_bp")
        require(all(type(v) in (float, int) and math.isfinite(v) and -5 <= v <= 25
                    for v in (y2, y10)), "yield units/range")
        require(type(curve) in (float, int) and math.isfinite(curve)
                and abs((y10 - y2) * 100 - curve) <= 0.002, "curve arithmetic")
        seen.add(raw_date)
        rows.append({"date": raw_date, "2Y": float(y2), "10Y": float(y10),
                     "curve_bp": round((y10 - y2) * 100, 3)})
    last = rows[-1]
    require(rows[0]["date"] == evidence.get("base_date")
            and last["date"] == evidence.get("last_common_date")
            and last["2Y"] == evidence.get("last_common_2Y")
            and last["10Y"] == evidence.get("last_common_10Y"),
            "receipt anchor/last pair mismatch")
    age = (today - date.fromisoformat(last["date"])).days
    require(0 <= age <= 45, "historical SNB source outside reference window")
    if previous is not None:
        require(previous.get("schema") == SCHEMA
                and previous.get("eligible_for_core") is False
                and previous.get("eligible_for_fx_engine") is False
                and previous.get("eligible_for_backtests") is False,
                "previous research data not safe")
        old = previous.get("observations")
        require(isinstance(old, list) and len(old) >= 3, "previous historical rows")
        # Preserve older observations if the canonical anchor advances. Any shared
        # observation must agree: an SNB revision requires manual inspection.
        overlap = {r["date"]: r for r in rows}
        for prior in old:
            if prior["date"] in overlap:
                require(prior == overlap[prior["date"]],
                        "historical source revision requires independent review")
        require(any(prior["date"] in overlap for prior in old),
                "no common source anchor with published history")
        merged = {r["date"]: r for r in old}
        merged.update(overlap)
        rows = [merged[d] for d in sorted(merged)]
        require(rows[-1]["date"] >= old[-1]["date"], "history rollback")
        last = rows[-1]
        if rows == old:
            return previous
    return {
        "schema": SCHEMA,
        "currency": "CHF",
        "quality": "SNB_OFFICIAL_OBSERVED_HISTORICAL_RESEARCH",
        "source": "Swiss National Bank, Confederation spot yields, 2J / 10J",
        "source_url": SOURCE,
        "source_response_sha256": digest,
        "source_latest_vintage_not_point_in_time": True,
        "anchor_date": rows[0]["date"],
        "last_observation_date": last["date"],
        "observation_count": len(rows),
        "observations": rows,
        "meaning": "Same-date SNB 2Y and 10Y observations; dated history, not current market levels",
        "current_session_government_rates_certified": False,
        "eligible_for_core": False,
        "eligible_for_fx_engine": False,
        "eligible_for_backtests": False,
        "eligible_for_automatic_promotion": False,
        "canonical_government_rates_untouched": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asof", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    previous = (json.loads(args.output.read_text(encoding="utf-8"))
                if args.output.is_file() else None)
    feed = build(evidence, previous, args.asof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(feed, indent=2, ensure_ascii=False) + "\n"
    if not args.output.exists() or args.output.read_text(encoding="utf-8") != serialized:
        args.output.write_text(serialized, encoding="utf-8")
    print(json.dumps({"result": "CHF_HISTORY_RESEARCH_READY",
                      "observations": feed["observation_count"],
                      "last_date": feed["last_observation_date"],
                      "core_unchanged": True,
                      "source_digest": feed["source_response_sha256"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
