#!/usr/bin/env python3
"""Compact, audited market-context view for hourly ChatGPT alerts.

Never certify raw data by its mere presence. Eligibility comes exclusively from
build_certified_alert_snapshot.py. The source values are then checked against
the receipt's as-of and source before exposure. No post-event market reaction
is asserted: ECB fixings and latest rates are reference observations only.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SECTIONS = ROOT / "live_data" / "sections"
SCHEMA = "GMFQ_CHATGPT_MARKET_CONTEXT_V1"
RECEIPT_SCHEMA = "GMFQ_HOURLY_ALERT_CERTIFIED_SNAPSHOT_V1"
CCYS = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
HORIZONS = ("3m", "6m", "12m")
MAX_PAIRS = 28


def read_json(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Not a JSON object: {path}")
    return result


def latest(row: Any) -> Any:
    return row[-1] if isinstance(row, list) and row else None


def num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def rounded(value: float, places: int = 2) -> float:
    return float(Decimal(str(value)).quantize(Decimal("1").scaleb(-places), rounding=ROUND_HALF_UP))


def withheld(record: dict) -> dict:
    # Do not reveal stale or estimated values as though they were current.
    return {"state": record.get("state", "UNAVAILABLE"), "as_of": record.get("as_of"),
            "reason": record.get("reason", "Not certified or stale.")}


def eligible(record: Any) -> bool:
    return (isinstance(record, dict) and record.get("state") == "AVAILABLE_CERTIFIED"
            and record.get("alert_eligible") is True
            and isinstance(record.get("as_of"), str)
            and isinstance(record.get("source"), str) and bool(record["source"].strip()))


def ois_view(receipt: dict, source: dict) -> dict:
    output: dict[str, dict] = {}
    for ccy in CCYS:
        rec = receipt["lanes"]["ois"][ccy]
        raw = source.get("currencies", {}).get(ccy, {})
        if not eligible(rec):
            output[ccy] = withheld(rec)
            continue
        if (rec["as_of"] != raw.get("as_of") or rec["source"] != raw.get("source")
                or raw.get("official_status") != "ACTIVE"
                or raw.get("quality") != "OFFICIAL_CERTIFIED"
                or raw.get("operational_status") != "GREEN_OFFICIAL"
                or raw.get("backtest_eligible_as_official") is not True):
            output[ccy] = {"state": "WITHHELD", "reason": "Official OIS receipt/source mismatch."}
            continue
        curve = {}
        for horizon in HORIZONS:
            h = raw.get("horizons", {}).get(horizon, {})
            if not isinstance(h, dict) or not all(num(h.get(k)) for k in ("rate", "policy_delta_bp")):
                curve = {}
                break
            curve[horizon] = {
                "rate_pct": rounded(h["rate"], 4),
                "delta_vs_policy_bp": rounded(h["policy_delta_bp"], 1),
                "change_1d_bp": rounded(h["change_1d_bp"], 1) if num(h.get("change_1d_bp")) else None,
                "change_1w_bp": rounded(h["change_1w_bp"], 1) if num(h.get("change_1w_bp")) else None,
            }
        if len(curve) != len(HORIZONS) or not num(raw.get("policy_rate")):
            output[ccy] = {"state": "WITHHELD", "reason": "Incomplete certified OIS horizons."}
            continue
        output[ccy] = {"state": "AVAILABLE_CERTIFIED", "as_of": rec["as_of"],
                       "source": rec["source"], "policy_rate_pct": rounded(raw["policy_rate"], 3),
                       "horizons": curve}
    return output


def rates_view(receipt: dict, source: dict) -> dict:
    output = {}
    for ccy in CCYS:
        rec = receipt["lanes"]["g8_bonds"][ccy]
        raw = source.get(ccy, {})
        if not eligible(rec):
            output[ccy] = withheld(rec)
            continue
        if rec["as_of"] != raw.get("date") or rec["source"] != raw.get("source"):
            output[ccy] = {"state": "WITHHELD", "reason": "Rates receipt/source mismatch."}
            continue
        if not all(num(raw.get(k)) for k in ("2Y", "10Y")):
            output[ccy] = {"state": "WITHHELD", "reason": "Incomplete certified 2Y/10Y."}
            continue
        output[ccy] = {"state": "AVAILABLE_CERTIFIED", "as_of": rec["as_of"], "source": rec["source"],
                       "government_2y_pct": rounded(raw["2Y"], 4),
                       "government_10y_pct": rounded(raw["10Y"], 4),
                       "10y_minus_2y_bp": rounded((raw["10Y"] - raw["2Y"]) * 100, 1),
                       "change_2y_bp": rounded(raw["chg2_bp"], 1) if num(raw.get("chg2_bp")) else None,
                       "change_10y_bp": rounded(raw["chg10_bp"], 1) if num(raw.get("chg10_bp")) else None}
    return output


def cot_view(receipt: dict, source: dict) -> dict:
    rec = receipt["lanes"]["cot"]
    if not eligible(rec):
        return {"state": rec.get("state", "UNAVAILABLE"), "as_of": rec.get("as_of"),
                "reason": rec.get("reason")}
    rows = {}
    for ccy in CCYS:
        raw = source.get(ccy, {})
        if latest(raw.get("dates")) != rec["as_of"]:
            return {"state": "WITHHELD", "reason": "COT currencies have differing vintages."}
        vals = {key: latest(raw.get(key)) for key in ("net", "long", "short", "netoi", "percentile")}
        if not all(num(x) for x in vals.values()):
            return {"state": "WITHHELD", "reason": "Incomplete COT G8 values."}
        net_prev = raw.get("net", [])
        if not isinstance(net_prev, list) or len(net_prev) < 2 or not num(net_prev[-2]):
            return {"state": "WITHHELD", "reason": "Incomplete COT 1W comparison."}
        pct = int(Decimal(str(vals["percentile"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        net_oi = rounded(vals["netoi"], 1)
        signal = "EXTREME_LONG" if pct >= 80 else "EXTREME_SHORT" if pct <= 20 else "NEUTRAL"
        rows[ccy] = {
            "net_noncommercial": int(vals["net"]), "delta_net_1w": int(vals["net"] - net_prev[-2]),
            "long": int(vals["long"]), "short": int(vals["short"]),
            "net_oi_pct": net_oi, "net_oi_alert_abs_ge_30pct": abs(net_oi) >= 30.0,
            "percentile_104w_rounded": pct, "signal": signal,
        }
    return {"state": "AVAILABLE_CERTIFIED", "as_of": rec["as_of"], "source": rec["source"],
            "percentile_rule": "Display rounded integer; classify on rounded percentile: >=80 extreme long, <=20 extreme short.",
            "net_oi_rule": "Display one decimal; alert inclusive if abs(displayed Net/OI)>=30.0%",
            "currencies": rows}


def fx_view(receipt: dict, pair_source: dict, prices: dict) -> dict:
    rec = receipt["lanes"]["fx"]
    if not eligible(rec):
        return withheld(rec)
    if (prices.get("last_as_of") != rec["as_of"] or pair_source.get("price_asof") != rec["as_of"]
            or pair_source.get("price_source") != rec["source"]
            or prices.get("source") != rec["source"]
            or prices.get("base") != "EUR"):
        return {"state": "WITHHELD", "reason": "ECB FX reference-fixing receipt/source mismatch."}
    history = prices.get("rows", [])
    if not isinstance(history, list) or len(history) < 2:
        return {"state": "WITHHELD", "reason": "ECB FX fixing history absent."}
    now = history[-1]
    prior = history[-2]
    if (now.get("Date") != rec["as_of"]
            or not all(num(now.get(c)) and now[c] > 0 for c in CCYS)
            or not all(num(prior.get(c)) and prior[c] > 0 for c in CCYS)):
        return {"state": "WITHHELD", "reason": "ECB FX last fixing or prior fixing incomplete."}
    pairs = {}
    for i, base in enumerate(CCYS):
        for quote in CCYS[i + 1:]:
            # EUR-based official fixing: currency Q per one unit of currency B.
            key = base + quote
            current = now[quote] / now[base]
            previous = prior[quote] / prior[base]
            pairs[key] = {"fixing": rounded(current, 5), "change_since_prior_fixing_pct": rounded((current / previous - 1) * 100, 3)}
    if len(pairs) != MAX_PAIRS:
        return {"state": "WITHHELD", "reason": "ECB FX cross-rate universe incomplete."}
    return {"state": "AVAILABLE_CERTIFIED", "as_of": rec["as_of"], "source": rec["source"],
            "kind": "ECB_EUR_BASED_REFERENCE_FIXINGS_NOT_INTRADAY_SPOT_OR_CLOSE",
            "prior_fixing_as_of": prior.get("Date"),
            "note": "Pair quote is units of second currency per one of first; crosses derived from ECB EUR fixing. Invert explicitly if discussing reverse ticker.",
            "pairs": pairs}


def build(receipt: dict, ois: dict, rates: dict, cot: dict, pairs: dict, prices: dict) -> dict:
    if receipt.get("schema") != RECEIPT_SCHEMA or not isinstance(receipt.get("lanes"), dict):
        raise ValueError("Invalid certified hourly receipt")
    if not isinstance(receipt.get("generated_at_utc"), str):
        raise ValueError("Certified hourly receipt timestamp absent")
    sections = {"ois_official": ois_view(receipt, ois),
                "government_rates": rates_view(receipt, rates),
                "cot_weekly": cot_view(receipt, cot),
                "fx_ecb_fixing": fx_view(receipt, pairs, prices)}
    return {
        "schema": SCHEMA,
        "generated_at_utc": receipt["generated_at_utc"],
        "evaluation_date_europe_rome": receipt.get("as_of_evaluation_date"),
        "reference_only": True,
        "policy": {
            "fail_closed": True, "withheld_values_are_not_trade_inputs": True,
            "no_inference_of_post_event_reaction": True,
            "government_2y_is_not_ois": True,
            "no_data_means_no_forced_trade": True,
            "certification_authority": "GMFQ_HOURLY_ALERT_CERTIFIED_SNAPSHOT_V1",
        },
        "sections": sections,
        "unavailable": {
            "macro_release_event": receipt["lanes"]["macro"]["state"],
            "credit_spreads": "WITHHELD_NO_CERTIFIED_ADAPTER",
            "equity_sectors": receipt["lanes"]["equity_sectors"]["state"],
            "liquidity": "CONTEXT_ONLY_NOT_CERTIFIED_CREDIT_SPREADS",
            "intraday_post_event_reactions": "WITHHELD_REQUIRES_SEPARATE_TIMESTAMPED_EVENT_PRICING",
        },
        "usage": "Use only AVAILABLE_CERTIFIED figures and cite their as_of/source. Compare facts at consistent dates; never imply reference fixings or historic changes are post-news market reactions. If source is unavailable or this snapshot stale, continue sending hourly ChatGPT alert with WITHHELD.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    obj = build(
        read_json(args.receipt),
        read_json(SECTIONS / "OIS_OPERATIONAL_VIEW.json"),
        read_json(SECTIONS / "NATIVE_RATES_DATA.json"),
        read_json(SECTIONS / "V250_COT_CHART_DATA.json"),
        read_json(SECTIONS / "PAIR_SETUP_OPERATIONAL_VIEW.json"),
        read_json(SECTIONS / "ECB_G8_PRICE_HISTORY.json"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": SCHEMA,
        "ois_available": sum(x.get("state") == "AVAILABLE_CERTIFIED" for x in obj["sections"]["ois_official"].values()),
        "rates_available": sum(x.get("state") == "AVAILABLE_CERTIFIED" for x in obj["sections"]["government_rates"].values()),
        "cot": obj["sections"]["cot_weekly"].get("state"),
        "fx": obj["sections"]["fx_ecb_fixing"].get("state")
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
