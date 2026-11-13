#!/usr/bin/env python3
"""Derive a research-only G8 historical pricing chart feed from immutable sources.

No interpolated observations, no promotion to official OIS, no FX signal.
Official tenor snapshots are historical published 3M/6M/12M points, which can
still rotate futures contracts. Secondary quotes are single *listed contract*
bars, with unresolved historical conflicts removed. NZD is a 1D/1W proxy with
explicitly derived previous levels, not an observed time series.
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "site/fx-quant-v2/ois-pricing-snapshot.json"
OFFICIAL = ROOT / "validation/cb_pricing/history/OIS_G8_SNAPSHOTS_V1.jsonl"
QUOTES = ROOT / "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl"
CONFLICTS = ROOT / "validation/cb_pricing/history/OIS_SAME_CONTRACT_CONFLICTS_V1.jsonl"
NZD = ROOT / "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"
DEST = ROOT / "site/fx-quant-v2/next/rates-pricing-history-v1.json"
CCYS = ("USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD")
TENORS = ("3m", "6m", "12m")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def good_day(v: object, cutoff: str) -> bool:
    if not isinstance(v, str) or len(v) != 10:
        return False
    try:
        return date.fromisoformat(v).isoformat() == v and v <= cutoff
    except ValueError:
        return False


def number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) < 1000


def prev_weekday(day: str) -> str:
    d = date.fromisoformat(day) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def build(snapshot: dict, archive: list[dict], quotes: list[dict],
          conflicts: list[dict], nzd: dict) -> dict:
    today = snapshot["snapshot_built_from_repo_date"]
    if not good_day(today, today):
        raise ValueError("invalid source snapshot date")
    source_currencies = snapshot["currencies"]
    if set(source_currencies) != set(CCYS):
        raise ValueError("all G8 sources required")

    # Quarantine the original AND conflicting prints, never silently choose one.
    disputed = {
        tuple(x["key"]) for x in conflicts
        if x.get("status") == "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT"
    }
    official_points = defaultdict(dict)
    for rec in archive:
        c = rec.get("currency")
        if c not in ("GBP", "JPY", "CAD", "AUD"):
            continue
        if (rec.get("schema") != "GMFQ_OIS_G8_SNAPSHOT_V1" or
                rec.get("operational_status") != "GREEN_OFFICIAL" or
                rec.get("official_status") != "ACTIVE" or
                rec.get("method_id") != "OFFICIAL_CERTIFIED_V1" or
                rec.get("backtest_eligible_as_official") is not True):
            continue
        day = rec.get("source_as_of")
        if not good_day(day, today) or rec.get("source") != source_currencies[c]["source"]:
            continue
        if str(rec.get("captured_at_utc", ""))[:10] < day:
            continue
        for t in TENORS:
            h = (rec.get("horizons") or {}).get(t) or {}
            v = h.get("rate")
            if not number(v):
                continue
            key = (day, t)
            existing = official_points[c].get(key)
            if not existing or rec["captured_at_utc"] > existing["captured_at_utc"]:
                official_points[c][key] = {
                    "date": day, "rate": round(float(v), 6),
                    "contract": None, "source_class": "OFFICIAL_TENOR",
                    "derived": False, "captured_at_utc": rec["captured_at_utc"]
                }

    secondary = defaultdict(lambda: defaultdict(list))
    for row in quotes:
        c, t, day = row.get("currency"), row.get("observed_under_horizon"), row.get("observation_date")
        if c not in ("USD", "EUR", "CHF") or t not in TENORS or not good_day(day, today):
            continue
        if (row.get("schema") != "GMFQ_OIS_SAME_CONTRACT_QUOTE_V1" or
            row.get("source_method") != "TRADINGVIEW_DATED_FUTURES_SSR_V2" or
            row.get("source_timestamp_evidence") != "SSR_DAILY_BAR_DATA_UPDATE_TIME" or
            row.get("official_ois_quote") is not False or
            row.get("policy_delta_eligible") is not False or
            row.get("backtest_eligible_as_official") is not False):
            continue
        if (c, row.get("contract"), day) in disputed:
            continue
        if not good_day(row.get("expiration"), "2099-12-31"):
            continue
        rate, price = row.get("implied_rate"), row.get("futures_price")
        if not number(rate) or not number(price) or abs((100.0 - price) - rate) > .011:
            continue
        if not str(row.get("first_seen_at_utc", ""))[:10] >= day:
            continue
        secondary[(c, t)][day].append(row)

    # Current contract identities are NOT applied retrospectively to previous
    # instruments. Store contract in every point, break the graph at each roll.
    lines = {}
    for c in CCYS:
        row = source_currencies[c]
        tenors = {}
        for t in TENORS:
            if c in ("GBP", "JPY", "CAD", "AUD"):
                points = [dict(p) for (d, x), p in official_points[c].items() if x == t]
                for p in points:
                    p.pop("captured_at_utc", None)
            elif c in ("USD", "EUR", "CHF"):
                points = []
                for d, candidates in secondary[(c, t)].items():
                    # Different contracts on the same day under one horizon
                    # cannot be assigned an unambiguous point.
                    identities = {(x["contract"], x["expiration"]) for x in candidates}
                    if len(identities) != 1:
                        continue
                    item = min(candidates, key=lambda x: x["first_seen_at_utc"])
                    rates = [x["implied_rate"] for x in candidates]
                    if max(rates) - min(rates) > .00001:
                        continue
                    points.append({
                        "date": d, "rate": round(float(item["implied_rate"]), 6),
                        "contract": item["contract"], "source_class": "SECONDARY_SAME_CONTRACT",
                        "derived": False, "captured_at_utc": item["first_seen_at_utc"]
                    })
            else:  # NZD: current ASX proxy and two explicitly reconstructed references.
                points = []
                source_h = (nzd.get("horizons") or {}).get(t) or {}
                current = (row.get("horizons") or {}).get(t) or {}
                d, rate = row.get("as_of"), current.get("rate")
                if (nzd.get("schema") == "GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1" and
                        nzd.get("currency") == "NZD" and nzd.get("as_of") == d and
                        good_day(d, today) and number(rate) and
                        source_h.get("expiry_label") == current.get("contract") and
                        number(source_h.get("implied_bank_bill_rate")) and
                        abs(source_h["implied_bank_bill_rate"] - rate) < .00001):
                    points.append({"date": d, "rate": round(float(rate), 6),
                                   "contract": current.get("contract"),
                                   "source_class": "BANK_BILL_PROXY",
                                   "derived": False})
                    day1 = prev_weekday(d)
                    if number(source_h.get("change_1d_bp")):
                        points.append({"date": day1,
                                       "rate": round(float(rate - source_h["change_1d_bp"]/100), 6),
                                       "contract": current.get("contract"),
                                       "source_class": "BANK_BILL_PROXY_DELTA_REFERENCE",
                                       "derived": True})
                    week = source_h.get("weekly_reference_trade_date")
                    if (good_day(week, d) and week < d and
                            5 <= (date.fromisoformat(d) - date.fromisoformat(week)).days <= 10
                            and number(source_h.get("change_1w_bp"))):
                        points.append({"date": week,
                                       "rate": round(float(rate - source_h["change_1w_bp"]/100), 6),
                                       "contract": current.get("contract"),
                                       "source_class": "BANK_BILL_PROXY_DELTA_REFERENCE",
                                       "derived": True})
            points.sort(key=lambda x: x["date"])
            tenors[t] = points
        lines[c] = {
            "kind": row["kind"], "quality": row["quality"], "source": row["source"],
            "tenors": tenors, "latest_date": max(
                (p["date"] for t in TENORS for p in tenors[t]), default=None),
            "observed_dates": len({p["date"] for t in TENORS for p in tenors[t] if not p["derived"]}),
            "derived_reference_points": sum(p["derived"] for t in TENORS for p in tenors[t]),
        }
    return {
        "schema": "GMFQ_NEXT_G8_PRICING_HISTORY_V1",
        "as_of": today, "eligible_for_fx_engine": False,
        "eligible_for_backtests_as_official_ois": False,
        "official_ois_created": False,
        "date_gaps_interpolated": False, "excluded_conflicted_contract_days": len(disputed),
        "note": ("Archive quotes have source dates but may be collected later. Official "
                 "published 3M/6M/12M futures tenor series can rotate contracts. "
                 "Secondary rates always retain their listed contract identity; "
                 "NZD past references are derived from ASX proxy deltas, "
                 "not independent observations. No meeting probabilities or signals."),
        "currencies": lines
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEST)
    args = parser.parse_args()
    actual = build(
        json.loads(SNAP.read_text(encoding="utf-8")),
        read_jsonl(OFFICIAL), read_jsonl(QUOTES), read_jsonl(CONFLICTS),
        json.loads(NZD.read_text(encoding="utf-8")))
    if args.check:
        expected = json.loads(args.output.read_text(encoding="utf-8"))
        if expected != actual:
            raise SystemExit("G8 pricing history output differs from immutable archive sources")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(json.dumps({"status": "PASS", "check": args.check,
                      "as_of": actual["as_of"], "coverage": {
                          c: actual["currencies"][c]["observed_dates"] for c in CCYS}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
