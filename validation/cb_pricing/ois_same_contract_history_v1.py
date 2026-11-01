#!/usr/bin/env python3
"""Append verified, same-listed-contract futures quotes; no OIS curve or trades.

All observations come from the ALREADY-collected secondary contract snapshots.
Distinct quote dates and exact contract identities are essential: neither a
daily workflow run nor a switch to the next futures expiry implies repricing.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from collect_cb_pricing_estimated_live_v1 import saron_window

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json"
HISTORY = ROOT / "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl"
SCHEMA = "GMFQ_OIS_SAME_CONTRACT_QUOTE_V1"
SPECS = {"USD": ("CBOT", "ZQ"), "EUR": ("EUREX", "FST3"), "CHF": ("ICEEUR", "SA3")}
TENORS = {"3m": 90, "6m": 180, "12m": 365}
SOURCE_METHOD = "TRADINGVIEW_DATED_FUTURES_SSR_V2"
QUOTE_EVIDENCE = "SSR_DAILY_BAR_DATA_UPDATE_TIME"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("OIS_SAME_CONTRACT_FAIL_CLOSED: " + message)


def iso_date(raw: str) -> date:
    require(isinstance(raw, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", raw) is not None,
            "missing or invalid source day")
    return date.fromisoformat(raw)


def source_capture_time(value: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), "missing UTC capture time")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset().total_seconds() == 0, "capture not UTC")
    return parsed


def record_key(record: dict) -> tuple[str, str, str]:
    return (record["currency"], record["contract"], record["observation_date"])


def quote_fingerprint(record: dict) -> tuple:
    return tuple(record[k] for k in (
        "currency", "exchange", "contract", "symbol", "expiration",
        "observation_date", "futures_price", "implied_rate",
        "source_method", "source_timestamp_evidence", "official_ois_quote",
        "policy_delta_eligible", "backtest_eligible_as_official",
    ))


def validate_row(row: dict) -> dict:
    require(isinstance(row, dict) and row.get("schema") == SCHEMA, "unknown history row")
    ccy = row.get("currency")
    require(ccy in SPECS, "unsupported currency")
    ex, root = SPECS[ccy]
    contract = row.get("contract")
    require(isinstance(contract, str) and re.fullmatch(
        re.escape(root) + r"[FGHJKMNQUVXZ]\d{4}", contract), "missing dated contract")
    require(row.get("exchange") == ex and row.get("symbol") == ex + ":" + contract,
            "exchange or symbol mismatch")
    quote_day, expiry = iso_date(row.get("observation_date")), iso_date(row.get("expiration"))
    require(quote_day < expiry, "quote at or after expiry")
    captured = source_capture_time(row.get("first_seen_at_utc"))
    require(quote_day <= captured.date() and (captured.date() - quote_day).days <= 6,
            "source timestamp after first seen or too old")
    rate, price = row.get("implied_rate"), row.get("futures_price")
    require(type(rate) in (int, float) and type(price) in (int, float), "non-numeric quote")
    require(-5 <= rate <= 25 and 80 < price < 105 and
            abs((100 - price) - rate) <= 0.0002, "price is not consistent with rate")
    require(row.get("source_method") == SOURCE_METHOD and
            row.get("source_timestamp_evidence") == QUOTE_EVIDENCE, "uncertified observation")
    require(row.get("official_ois_quote") is False and
            row.get("policy_delta_eligible") is False and
            row.get("backtest_eligible_as_official") is False, "forbidden promotion")
    require(row.get("observed_under_horizon") in TENORS, "unmapped horizon")
    provenance = row.get("source_commit")
    require(provenance == "COLLECTOR_VALIDATED_RUNTIME" or
            (isinstance(provenance, str) and re.fullmatch(r"[a-f0-9]{10,40}", provenance)),
            "source provenance unavailable")
    require(set(row) == {
        "schema", "currency", "exchange", "contract", "symbol", "expiration",
        "observation_date", "futures_price", "implied_rate", "observed_under_horizon",
        "first_seen_at_utc", "source_commit", "source_method",
        "source_timestamp_evidence", "official_ois_quote", "policy_delta_eligible",
        "backtest_eligible_as_official",
    }, "unknown or missing history payload")
    return row


def load_history(path: Path = HISTORY) -> list[dict]:
    if not path.exists():
        return []
    result = []
    seen = {}
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = validate_row(json.loads(raw))
        key = record_key(row)
        require(key not in seen, f"duplicate archive identity line {n}")
        seen[key] = row
        result.append(row)
    return result


def candidates(quote_feed: dict) -> tuple[list[dict], list[str]]:
    require(isinstance(quote_feed, dict) and
            quote_feed.get("schema") == "GMFQ_CB_PRICING_ESTIMATED_LIVE_QUOTES_V1" and
            quote_feed.get("status") == "INFORMATIONAL_ONLY" and
            quote_feed.get("official_ois_runtime_untouched") is True, "unexpected source feed")
    g = quote_feed.get("governance") or {}
    require(g.get("backtest_eligible_as_official_ois") is False and
            g.get("core_score_effect") == "NONE" and
            g.get("pair_engine_effect") == "NONE", "source governance drift")
    seen_at = quote_feed.get("generated_at_utc")
    source_capture_time(seen_at)
    out, excluded = [], []
    for ccy, (exchange, _) in SPECS.items():
        entry = (quote_feed.get("currencies") or {}).get(ccy) or {}
        require(entry.get("source_quality") == "SECONDARY_PUBLIC_LIVE_PROXY",
                ccy + ": secondary source identity drift")
        for tenor in TENORS:
            p = (entry.get("horizons") or {}).get(tenor) or {}
            if (p.get("quote_timestamp_verified") is not True or
                    p.get("quote_timestamp_source") != QUOTE_EVIDENCE or
                    not p.get("quote_as_of")):
                excluded.append(ccy + "/" + tenor + ": unverified bar timestamp")
                continue
            rec = {
                "schema": SCHEMA, "currency": ccy, "exchange": exchange,
                "contract": p.get("contract"), "symbol": p.get("symbol"),
                "expiration": p.get("expiration"), "observation_date": p.get("quote_as_of"),
                "futures_price": p.get("futures_price"), "implied_rate": p.get("rate"),
                "observed_under_horizon": tenor, "first_seen_at_utc": seen_at,
                "source_commit": "COLLECTOR_VALIDATED_RUNTIME",
                "source_method": SOURCE_METHOD,
                "source_timestamp_evidence": QUOTE_EVIDENCE,
                "official_ois_quote": False, "policy_delta_eligible": False,
                "backtest_eligible_as_official": False,
            }
            try:
                validate_row(rec)
                if ccy == "CHF" and p.get("mapping") == (
                        f"nearest ICE SARON accrual start to today+{TENORS[tenor]}d; no interpolation"):
                    start, end = saron_window(rec["contract"])
                    expected = (start - date.fromisoformat(seen_at[:10])).days - TENORS[tenor]
                    require(start > date.fromisoformat(rec["observation_date"]) and
                            rec["expiration"] == end.isoformat() and
                            p.get("accrual_start") == start.isoformat() and
                            abs(expected) <= 50,
                            "CHF accrual-start/expiry mismatch")
                else:
                    # Existing immutable October records keep their original
                    # horizon labels; new November CHF feeds cannot revive
                    # the old expiry-based selector.
                    require(ccy != "CHF" or
                            date.fromisoformat(seen_at[:10]) < date(2026, 11, 2),
                            "legacy CHF expiry-based contract selection forbidden")
                    expected = (date.fromisoformat(rec["expiration"]) -
                                date.fromisoformat(seen_at[:10])).days - TENORS[tenor]
                    require(abs(expected) <= 45 and p.get("mapping") ==
                            f"nearest dated listed contract expiry to today+{TENORS[tenor]}d; no interpolation",
                            "expiry selection mismatch")
                out.append(rec)
            except ValueError as err:
                excluded.append(ccy + "/" + tenor + ": " + str(err))
    return out, excluded


def append_verified(feed: dict, history: Path = HISTORY, write: bool = False) -> dict:
    known = load_history(history)
    newest = {record_key(r): r for r in known}
    observations, excluded = candidates(feed)
    appended = []
    for row in observations:
        key = record_key(row)
        old = newest.get(key)
        if old is None:
            newest[key] = row
            appended.append(row)
        else:
            require(quote_fingerprint(old) == quote_fingerprint(row),
                    "contradictory same-contract same-day rate " + str(key))
    if write and appended:
        history.parent.mkdir(parents=True, exist_ok=True)
        with history.open("a", encoding="utf-8") as handle:
            for row in appended:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "schema": "GMFQ_OIS_SAME_CONTRACT_ARCHIVE_RECEIPT_V1",
        "status": "PASS_SOURCE_GOVERNANCE_RESEARCH_ONLY",
        "known_before": len(known), "eligible": len(observations),
        "would_append": len(appended), "written": len(appended) if write else 0,
        "excluded": excluded, "mutated_live_data": False, "official_ois_changes": False,
        "policy_repricing_allowed": False, "fx_bias_effect": "NONE",
    }


def matched_moves(rows: list[dict]) -> list[dict]:
    by_symbol = {}
    for row in rows:
        validate_row(row)
        by_symbol.setdefault((row["currency"], row["symbol"], row["expiration"]), []).append(row)
    moves = []
    for key, matched in sorted(by_symbol.items()):
        ordered = sorted(matched, key=lambda r: r["observation_date"])
        for previous, current in zip(ordered, ordered[1:]):
            first, last = iso_date(previous["observation_date"]), iso_date(current["observation_date"])
            require(last > first, "non-increasing same-contract observations")
            changed = round((current["implied_rate"] - previous["implied_rate"]) * 100, 4)
            moves.append({
                "currency": key[0], "symbol": key[1], "expiration": key[2],
                "from_date": previous["observation_date"],
                "to_date": current["observation_date"],
                "calendar_gap_days": (last - first).days, "observed_change_bp": changed,
                "measurement": "SAME_DATED_FUTURES_CONTRACT",
                "is_verified_daily_ois_repricing": False,
                "is_same_instrument": True, "is_exactly_one_session": False,
                "policy_repricing_signal": False, "backtest_official": False,
            })
    return moves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quotes", type=Path, default=SOURCE)
    ap.add_argument("--history", type=Path, default=HISTORY)
    ap.add_argument("--write", action="store_true",
                    help="Append validated new source quote days to the existing history")
    args = ap.parse_args()
    data = json.loads(args.quotes.read_text(encoding="utf-8"))
    result = append_verified(data, args.history, write=args.write)
    rows = load_history(args.history)
    if args.write:
        require(result["known_before"] + result["written"] == len(rows), "post-append audit")
    result["matched_historical_intervals"] = len(matched_moves(rows))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
