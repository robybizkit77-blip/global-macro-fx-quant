#!/usr/bin/env python3
"""FX Quant V2: temporal provenance audit, not a signal backtest.

Only matched listed contracts over consecutive official ECB fixing sessions
can support a descriptive rate-level *change* feature.  Time of first archival
observation controls when a feature might have become known.

This deliberately does NOT fit a strategy, compute a predictive statistic,
backfill macro vintages, create OIS meeting probabilities, or produce returns.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FX_PATH = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
QUOTES_PATH = ROOT / "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl"
MACRO_PATH = ROOT / "site/fx-quant-v2/macro-baseline-candidate-v1.json"
TARGET = ROOT / "site/fx-quant-v2/quant-temporal-readiness-v1.json"
SCHEMA = "GMFQ_FXV2_RATE_FX_TEMPORAL_READINESS_V1"
G8 = frozenset(("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"))
CONTRACT_CCYS = ("USD", "EUR", "CHF")
TENORS = ("3m", "6m", "12m")
TENOR_SET = frozenset(TENORS)
METHOD = "TRADINGVIEW_DATED_FUTURES_SSR_V2"


def need(condition, reason):
    if not condition:
        raise ValueError("FXV2_TEMPORAL_RESEARCH_REJECTED: " + reason)


def iso_day(raw, desc):
    need(isinstance(raw, str) and len(raw) == 10, desc + " missing date")
    try:
        d = date.fromisoformat(raw)
    except (TypeError, ValueError) as e:
        raise ValueError("FXV2_TEMPORAL_RESEARCH_REJECTED: " + desc + " bad date") from e
    need(d.isoformat() == raw, desc + " noncanonical date")
    return d


def utc_first_seen(raw, desc):
    need(isinstance(raw, str) and raw.endswith("Z"), desc + " missing UTC first seen")
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("FXV2_TEMPORAL_RESEARCH_REJECTED: " + desc + " bad time") from e
    need(d.tzinfo is not None and d.utcoffset().total_seconds() == 0,
         desc + " non-UTC first seen")
    return d


def decimal_rate(v, desc):
    need(type(v) in (int, float) and math.isfinite(v) and -5 < v < 30,
         desc + " invalid implied rate")
    try:
        return Decimal(str(v))
    except InvalidOperation as e:
        raise ValueError("FXV2_TEMPORAL_RESEARCH_REJECTED: " + desc) from e


def bp(n):
    return float(n.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def validate_fx(fx):
    need(fx.get("schema") == "GMFQ_ECB_G8_PRICE_HISTORY_V1" and
         fx.get("base") == "EUR" and fx.get("pair_count") == 28 and
         fx.get("status") == "CURRENT_OFFICIAL_HISTORY",
         "ECB FX history schema or official quality invalid")
    need(set(fx.get("currencies", [])) == G8, "ECB FX currency universe drift")
    rows = fx.get("rows")
    need(isinstance(rows, list) and len(rows) >= 100 and fx.get("row_count") == len(rows),
         "insufficient or mislabeled ECB FX rows")
    days = []
    for row in rows:
        d = iso_day(row.get("Date"), "ECB row date")
        need(set(row) == G8 | {"Date"}, "ECB FX missing or extra currency")
        need(row["EUR"] == 1.0 and all(
            type(row[c]) in (int, float) and math.isfinite(row[c]) and row[c] > 0
            for c in G8), "ECB FX nonpositive fixing")
        days.append(d)
    need(days == sorted(set(days)), "ECB FX dates must be strictly ascending unique")
    need(days[0].isoformat() == fx.get("first_as_of") and
         days[-1].isoformat() == fx.get("last_as_of"), "ECB boundaries don't match history")
    return days


def validate_macro(macro):
    need(macro.get("schema") == "GMFQ_FXV2_MACRO_CANDIDATE_8X3_DESCRIPTIVE_V1"
         and macro.get("eligible_for_live_fx_signals") is False
         and macro.get("eligible_for_backtests") is False
         and macro.get("eligible_for_automatic_core_rebase") is False
         and macro.get("canonical_fx_core_untouched") is True,
         "macro source must remain descriptive and explicitly non-PIT")
    pairs = macro.get("pairs", {})
    need(len(pairs) == 28, "macro missing one or more FX pairs")
    universe = {frozenset((a, b)) for a in G8 for b in G8 if a != b}
    need({frozenset(p.split("/")) for p in pairs} == universe,
         "macro pair orientations/coverage invalid")
    for pair, row in pairs.items():
        a, b = pair.split("/")
        need(a in G8 and b in G8 and a != b and row.get("base") == a
             and row.get("quote") == b and row.get("macro_fx_signal") is None
             and row.get("eligible_for_core") is False,
             "macro pair source unexpectedly operational")
    return list(pairs)


def validate_quotes(records):
    seen = set()
    out = defaultdict(list)
    for idx, row in enumerate(records):
        desc = "quote #" + str(idx + 1)
        need(row.get("schema") == "GMFQ_OIS_SAME_CONTRACT_QUOTE_V1" and
             row.get("source_method") == METHOD and
             row.get("source_timestamp_evidence") == "SSR_DAILY_BAR_DATA_UPDATE_TIME"
             and row.get("official_ois_quote") is False and
             row.get("policy_delta_eligible") is False and
             row.get("backtest_eligible_as_official") is False,
             desc + " unexpected OIS/policy/signal provenance")
        ccy = row.get("currency")
        need(ccy in CONTRACT_CCYS and row.get("observed_under_horizon") in TENOR_SET,
             desc + " unknown currency or tenor")
        contract = row.get("contract")
        need(isinstance(contract, str) and contract and
             row.get("symbol") == row.get("exchange") + ":" + contract,
             desc + " contract identity mismatch")
        d = iso_day(row.get("observation_date"), desc + " quote")
        expiry = iso_day(row.get("expiration"), desc + " expiration")
        need(d < expiry, desc + " expired contract")
        seen_at = utc_first_seen(row.get("first_seen_at_utc"), desc)
        need(d <= seen_at.date() and (seen_at.date() - d).days <= 6,
             desc + " first-seen not safely after observation date")
        rate = decimal_rate(row.get("implied_rate"), desc)
        price = row.get("futures_price")
        need(type(price) in (int, float) and math.isfinite(price) and
             abs((Decimal("100") - Decimal(str(price))) - rate) < Decimal("0.0003"),
             desc + " contract quote inconsistent")
        key = (ccy, contract, d)
        need(key not in seen, desc + " duplicate instrument and source date")
        seen.add(key)
        out[(ccy, row["observed_under_horizon"], d)].append(row)
    return out


def build(fx, macro, quotes, fx_bytes, quote_bytes, macro_bytes):
    fx_days = validate_fx(fx)
    pair_keys = validate_macro(macro)
    by_quote = validate_quotes(quotes)
    per_leg = {}
    ambiguous_or_roll_groups = 0
    for prev, now in zip(fx_days, fx_days[1:]):
        for ccy in CONTRACT_CCYS:
            for tenor in TENORS:
                old = {x["contract"]: x for x in by_quote.get((ccy, tenor, prev), ())}
                new = {x["contract"]: x for x in by_quote.get((ccy, tenor, now), ())}
                common = old.keys() & new.keys()
                if len(common) != 1:
                    if old and new:
                        ambiguous_or_roll_groups += 1
                    continue
                contract = next(iter(common))
                a, b = old[contract], new[contract]
                first = utc_first_seen(a["first_seen_at_utc"], "previous")
                last = utc_first_seen(b["first_seen_at_utc"], "current")
                need(last >= first, "contract first-seen time reversed across sessions")
                delta = bp(Decimal("100") * (
                    decimal_rate(b["implied_rate"], "new") -
                    decimal_rate(a["implied_rate"], "old")))
                per_leg[(ccy, tenor, prev, now)] = {
                    "currency": ccy, "tenor": tenor,
                    "previous_market_date": prev.isoformat(),
                    "market_date": now.isoformat(),
                    "same_listed_contract": contract,
                    "previous_implied_rate_pct": a["implied_rate"],
                    "implied_rate_pct": b["implied_rate"],
                    "rate_change_bp": delta,
                    "source_first_known_at_utc": b["first_seen_at_utc"],
                    "source_usable_at_utc": max(a["first_seen_at_utc"],
                                               b["first_seen_at_utc"]),
                    "official_ois": False,
                    "not_policy_repricing": True,
                    "eligible_for_fx_core": False,
                }

    # Only legs referring to the SAME pair of consecutive ECB sessions count
    # as a relative change; no roll, interpolation or different-day pairing.
    by_pair = {p: {"base": p.split("/")[0], "quote": p.split("/")[1],
                   "matched_changes": 0, "market_days": set(),
                   "horizons": {t: 0 for t in TENORS},
                   "fx_signal": None, "expected_return": None}
               for p in pair_keys}
    aligned = []
    for pair, entry in by_pair.items():
        a, b = entry["base"], entry["quote"]
        for prev, now in zip(fx_days, fx_days[1:]):
            for tenor in TENORS:
                x, y = per_leg.get((a, tenor, prev, now)), per_leg.get((b, tenor, prev, now))
                if x is None or y is None:
                    continue
                rate_seen = max(x["source_usable_at_utc"], y["source_usable_at_utc"])
                capture_day = utc_first_seen(rate_seen, "paired observation").date()
                # A strict post-capture ECB fixing ensures no look-ahead from a
                # quote discovered after the ECB reference-rate fixing.
                post = [d.isoformat() for d in fx_days if d > capture_day]
                event = {
                    "pair": pair, "tenor": tenor,
                    "previous_market_date": prev.isoformat(),
                    "market_date": now.isoformat(),
                    "base_contract": x["same_listed_contract"],
                    "quote_contract": y["same_listed_contract"],
                    "base_rate_change_bp": x["rate_change_bp"],
                    "quote_rate_change_bp": y["rate_change_bp"],
                    "relative_rate_change_bp": bp(
                        Decimal(str(x["rate_change_bp"])) -
                        Decimal(str(y["rate_change_bp"]))),
                    "source_usable_at_utc": rate_seen,
                    "first_strictly_post_capture_ecb_date": post[0] if post else None,
                    "following_ecb_date": post[1] if len(post) > 1 else None,
                    "same_day_fx_return": None,
                    "future_fx_return": None,
                    "outcome_used_in_model": False,
                    "is_out_of_sample_prediction": False,
                    "rate_instrument_quality": "SECONDARY_FUTURES_NOT_OIS",
                    "policy_repricing_bp": None,
                    "fx_signal": None,
                }
                aligned.append(event)
                entry["matched_changes"] += 1
                entry["horizons"][tenor] += 1
                entry["market_days"].add(now.isoformat())

    for p, item in by_pair.items():
        n = item["matched_changes"]
        item["market_days"] = sorted(item["market_days"])
        item["distinct_market_days"] = len(item["market_days"])
        item["status"] = (
            "DESCRIPTIVE_ONLY_INSUFFICIENT_PIT_OOS" if n else
            "NO_SAME_CONTRACT_RELATIVE_CHANGE_HISTORY"
        )
        item["eligible_for_predictive_backtest"] = False
        item["eligible_for_fx_engine"] = False

    market_dates = sorted({e["market_date"] for e in aligned})
    captured = sum(e["first_strictly_post_capture_ecb_date"] is not None for e in aligned)
    source_last = max(
        [fx_days[-1].isoformat()] +
        [utc_first_seen(q["first_seen_at_utc"], "quote").date().isoformat()
         for q in quotes]
    )
    return {
        "schema": SCHEMA,
        "report_as_of_evidence_date": source_last,
        "latest_fx_reference_fixing": fx_days[-1].isoformat(),
        "first_fx_reference_fixing": fx_days[0].isoformat(),
        "source_hashes_sha256": {
            "ecb_fx_history": hashlib.sha256(fx_bytes).hexdigest(),
            "same_contract_futures_history": hashlib.sha256(quote_bytes).hexdigest(),
            "macro_candidate_pair_universe": hashlib.sha256(macro_bytes).hexdigest(),
        },
        "method": "SAME_LISTED_FUTURES_CONTRACT_TWO_CONSECUTIVE_ECB_SESSIONS",
        "source_timing": "MAX_OF_BOTH_LEGS_FIRST_SEEN_UTC_BEFORE_ANY_FUTURE_ECB_OUTCOME",
        "fx_future_reference_rule": "FIRST_ECB_FIXING_DATE_STRICTLY_AFTER_FIRST_SEEN_UTC_CALENDAR_DATE",
        "no_expiry_roll_as_market_change": True,
        "no_interpolated_rates": True,
        "no_same_day_fx_reaction_claim": True,
        "macro_point_in_time_feature_history_available": False,
        "registered_prospective_prediction_available": False,
        "trade_rule_calibrated": False,
        "do_not_treat_28_pairs_as_independent": True,
        "max_independent_fx_dimensions_per_date": 7,
        "eligible_for_signals": False,
        "eligible_for_backtests": False,
        "eligible_for_automatic_core_rebase": False,
        "canonical_fx_core_untouched": True,
        "statistical_significance": None,
        "sharpe_ratio": None,
        "out_of_sample_skill": None,
        "summary": {
            "fx_reference_rows": len(fx_days),
            "fx_pairs": len(pair_keys),
            "archived_same_contract_quotes": len(quotes),
            "contract_currencies": len(CONTRACT_CCYS),
            "strict_currency_rate_moves": len(per_leg),
            "strict_relative_pair_moves": len(aligned),
            "distinct_relative_market_days": len(market_dates),
            "pairs_with_any_relative_history": sum(
                item["matched_changes"] > 0 for item in by_pair.values()),
            "pairs_without_relative_history": sum(
                item["matched_changes"] == 0 for item in by_pair.values()),
            "excluded_roll_or_ambiguous_instrument_groups": ambiguous_or_roll_groups,
            "relative_events_with_future_ecb_t0": captured,
            "relative_events_without_future_ecb_t0": len(aligned) - captured,
            "out_of_sample_predictions": 0,
            "generated_fx_signals": 0,
        },
        "pairs": by_pair,
        "relative_rate_observations": aligned,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=TARGET)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fx_bytes, quote_bytes, macro_bytes = (
        FX_PATH.read_bytes(), QUOTES_PATH.read_bytes(), MACRO_PATH.read_bytes())
    quotes = [json.loads(line) for line in quote_bytes.splitlines() if line.strip()]
    out = build(json.loads(fx_bytes), json.loads(macro_bytes), quotes,
                fx_bytes, quote_bytes, macro_bytes)
    if args.check:
        need(args.output.exists(), "research sidecar not built")
        need(json.loads(args.output.read_text()) == out,
             "sidecar out of sync with dated source archives")
        print("FXV2_TEMPORAL_SOURCE_PARITY_PASS", out["summary"])
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        print("FXV2_TEMPORAL_RESEARCH_AUDIT_WRITTEN", out["summary"])


if __name__ == "__main__":
    main()
