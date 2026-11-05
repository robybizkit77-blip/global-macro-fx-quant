#!/usr/bin/env python3
"""FX Quant V2: dated 28-pair arithmetic pricing contrasts, research ONLY.

3m/6m/12m are display buckets, NOT synchronized common-maturity OIS contracts.
No carry, hedge cost, expected return, meeting repricing or live FX signal.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICING = ROOT / "site/fx-quant-v2/ois-pricing-snapshot.json"
MACRO = ROOT / "site/fx-quant-v2/macro-baseline-candidate-v1.json"
TARGET = ROOT / "site/fx-quant-v2/pricing-relative-28pairs-research.json"
G8 = frozenset(("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"))
TENORS = ("3m", "6m", "12m")
KINDS = frozenset(("OIS", "FUTURES", "FUTURES SECONDARI", "PROXY FUTURES"))
SCHEMA = "GMFQ_FXV2_RELATIVE_PRICING_28PAIR_RESEARCH_V1"


def demand(condition, message):
    if not condition:
        raise ValueError("FXV2_RELATIVE_PRICING_REJECTED: " + message)


def source_date(value, label, snapshot_date):
    demand(isinstance(value, str) and len(value) == 10, label + " invalid date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("FXV2_RELATIVE_PRICING_REJECTED: " + label + " invalid ISO date") from exc
    demand(parsed.isoformat() == value and parsed <= snapshot_date,
           label + " newer than snapshot or bad ISO date")
    return parsed


def source_rate(value, label):
    demand(type(value) in (int, float) and -5 < value < 30,
           label + " invalid rate")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("FXV2_RELATIVE_PRICING_REJECTED: " + label) from exc
    demand(number.is_finite(), label + " nonfinite rate")
    return number


def build(pricing, macro, source_bytes):
    demand(pricing.get("schema") == "GMFQ_FXV2_PRICING_SNAPSHOT_V1",
           "unexpected pricing source schema")
    demand(pricing.get("ui_only") is True and
           pricing.get("eligible_for_fx_engine") is False,
           "pricing must remain informational")
    snapshot_date = source_date(
        pricing.get("snapshot_built_from_repo_date"), "snapshot date", date.max)
    currencies = pricing.get("currencies")
    demand(isinstance(currencies, dict) and set(currencies) == G8,
           "need precisely 8 G8 currencies")
    demand(macro.get("schema") == "GMFQ_FXV2_MACRO_CANDIDATE_8X3_DESCRIPTIVE_V1"
           and macro.get("eligible_for_live_fx_signals") is False
           and macro.get("eligible_for_automatic_core_rebase") is False,
           "macro pair universe must remain non-operational")
    pair_keys = list(macro.get("pairs", {}))
    demand(len(pair_keys) == 28 and
           {frozenset(pair.split("/")) for pair in pair_keys} ==
           {frozenset((a, b)) for a in G8 for b in G8 if a != b},
           "macro 28-pair universe mismatch")
    for pair in pair_keys:
        names = pair.split("/")
        demand(len(names) == 2 and names[0] != names[1] and
               all(name in G8 for name in names),
               "invalid pair orientation")
    for c, entry in currencies.items():
        demand(entry.get("kind") in KINDS, c + " unknown instrument kind")
        demand(entry.get("quality") in
               {"FONTE UFFICIALE", "STIMA INDICATIVA", "PROXY DIREZIONALE"},
               c + " unrecognized source quality")
        demand(set(entry.get("horizons", {})) == set(TENORS),
               c + " missing tenor")
        for t in TENORS:
            q = entry["horizons"][t]
            source_date(q.get("as_of"), c + " " + t, snapshot_date)
            source_rate(q.get("rate"), c + " " + t)

    out = {}
    all_comp = []
    for pair in pair_keys:
        base, quote = pair.split("/")
        a, b = currencies[base], currencies[quote]
        horizons = {}
        for t in TENORS:
            x, y = a["horizons"][t], b["horizons"][t]
            xa = source_date(x["as_of"], base + " " + t, snapshot_date)
            ya = source_date(y["as_of"], quote + " " + t, snapshot_date)
            difference = (source_rate(x["rate"], base + t) -
                          source_rate(y["rate"], quote + t)) * Decimal("100")
            spread = float(difference.quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP))
            estimate = (a["quality"] == "STIMA INDICATIVA" or
                        b["quality"] == "STIMA INDICATIVA")
            proxy = (a["kind"] == "PROXY FUTURES" or
                     b["kind"] == "PROXY FUTURES")
            item = {
                "spread_bp": spread,
                "base_rate_pct": x["rate"], "quote_rate_pct": y["rate"],
                "base_as_of": x["as_of"], "quote_as_of": y["as_of"],
                "date_gap_days": abs((xa - ya).days),
                "same_date": xa == ya,
                "base_kind": a["kind"], "quote_kind": b["kind"],
                "base_quality": a["quality"], "quote_quality": b["quality"],
                "base_contract": x.get("contract"),
                "quote_contract": y.get("contract"),
                "estimate_involved": estimate, "proxy_involved": proxy,
                "same_named_family": a["kind"] == b["kind"],
                "policy_repricing_bp": None,
                "fx_signal": None,
            }
            horizons[t] = item
            all_comp.append(item)
        out[pair] = {"base": base, "quote": quote,
                     "horizons": horizons, "fx_signal": None,
                     "expected_return": None, "carry_estimate": None}
    return {
        "schema": SCHEMA,
        "pricing_source_schema": pricing["schema"],
        "pricing_source_content_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "pricing_source_snapshot_date": snapshot_date.isoformat(),
        "calculation": "100 * (base rate percent - quote rate percent) per labeled 3m/6m/12m bucket",
        "comparability": "ARITHMETIC_ONLY_MIXED_OVERNIGHT_FUTURES_BANK_BILL_BASIS_AND_EXPIRIES",
        "source_dates_are_independent": True,
        "same_bucket_does_not_guarantee_same_expiry_or_index": True,
        "not_ois_equivalent": True,
        "not_policy_repricing": True,
        "not_fx_carry": True,
        "no_cross_date_market_move_inferred": True,
        "eligible_for_fx_engine": False,
        "eligible_for_backtests": False,
        "eligible_for_automatic_core_rebase": False,
        "canonical_fx_core_untouched": True,
        "summary": {
            "currencies": len(G8),
            "pairs": len(out),
            "horizon_comparisons": len(all_comp),
            "same_date_comparisons": sum(z["same_date"] for z in all_comp),
            "mixed_date_comparisons": sum(not z["same_date"] for z in all_comp),
            "estimated_comparisons": sum(z["estimate_involved"] for z in all_comp),
            "proxy_comparisons": sum(z["proxy_involved"] for z in all_comp),
            "generated_fx_signals": 0,
            "generated_policy_repricing_signals": 0,
        },
        "pairs": out,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument("--check", action="store_true",
                        help="Compare parsed generated output with checked-in asset")
    args = parser.parse_args()
    source = PRICING.read_bytes()
    result = build(json.loads(source), json.loads(MACRO.read_text()), source)
    if args.check:
        demand(args.output.is_file(), "expected research asset not published")
        demand(json.loads(args.output.read_text()) == result,
               "published contrasts are not synchronized with input pricing snapshot")
        print("FXV2_RELATIVE_28PAIR_SOURCE_PARITY_PASS", result["summary"])
    else:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print("FXV2_RELATIVE_28PAIR_RESEARCH_WRITTEN", result["summary"])


if __name__ == "__main__":
    main()
