#!/usr/bin/env python3
"""Refresh FX Quant V2's OIS/Futures fallback from dated, verified source layers.

Informational-only. This does not recalculate OIS_DATA, FX Core, live market
prices, portfolio signals or backtests. Each tenor carries its own true quote
date. A missing/older source NEVER receives a fabricated newer date.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "site/fx-quant-v2/ois-pricing-snapshot.json"
OPERATIONAL = ROOT / "live_data/sections/OIS_OPERATIONAL_VIEW.json"
ESTIMATED = ROOT / "live_data/sections/CB_PRICING_ESTIMATED.json"
NZD_PROXY = ROOT / "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
HORIZONS = ("3m", "6m", "12m")
SCHEMA = "GMFQ_FXV2_PRICING_SNAPSHOT_V1"


def require(ok, message):
    if not ok:
        raise ValueError("FXV2_OIS_FALLBACK_REJECTED: " + message)


def candidate(currency, operational, estimated, nzd):
    op = operational.get("currencies", {}).get(currency, {})
    est = estimated.get("currencies", {}).get(currency, {})
    if op.get("operational_status") == "GREEN_OFFICIAL":
        kind = "OIS" if currency == "GBP" else "FUTURES"
        quality = "FONTE UFFICIALE"
        raw = op
        def date_for(item): return item.get("quote_as_of") or op.get("as_of")
        def value_for(item): return item.get("rate")
        def contract_for(item): return item.get("contract") or item.get("symbol")
    elif currency == "NZD" and nzd.get("status") == "LIVE_DIRECTIONAL_PROXY_READY":
        require(nzd.get("governance", {}).get("substitutes_for_ois_level") is False
                and nzd.get("governance", {}).get("policy_delta_from_proxy_allowed") is False,
                "NZD bank-bill proxy may never become an official OIS level")
        kind, quality = "PROXY FUTURES", "PROXY DIREZIONALE"
        raw = nzd
        def date_for(item): return nzd.get("as_of")
        def value_for(item): return item.get("implied_bank_bill_rate")
        def contract_for(item): return item.get("expiry_label")
    elif est.get("status") == "ESTIMATED_ACTIVE":
        kind, quality = "FUTURES SECONDARI", "STIMA INDICATIVA"
        raw = est
        def date_for(item): return item.get("quote_as_of") or est.get("as_of")
        def value_for(item): return item.get("rate")
        def contract_for(item): return item.get("contract") or item.get("symbol")
    else:
        return None
    horizons = {}
    for tenor in HORIZONS:
        item = raw.get("horizons", {}).get(tenor) or {}
        rate = value_for(item)
        asof = date_for(item)
        if (type(rate) not in (int, float) or not math.isfinite(rate)
                or not -5 < rate < 30 or not isinstance(asof, str)):
            continue
        try:
            date.fromisoformat(asof)
        except ValueError:
            continue
        horizons[tenor] = {
            "rate": rate,
            "as_of": asof,
            "change_1d_bp": item.get("change_1d_bp") if
                type(item.get("change_1d_bp")) in (int, float) and
                math.isfinite(item["change_1d_bp"]) else None,
            "change_1w_bp": item.get("change_1w_bp") if
                type(item.get("change_1w_bp")) in (int, float) and
                math.isfinite(item["change_1w_bp"]) else None,
            "contract": contract_for(item),
        }
    return {
        "kind": kind, "quality": quality,
        "source": raw.get("source"), "horizons": horizons
    }


def rebuild(existing, operational, estimated, nzd, *, today):
    require(existing.get("schema") == SCHEMA
            and existing.get("eligible_for_fx_engine") is False
            and existing.get("ui_only") is True, "snapshot research-only contract")
    require(set(existing.get("currencies", {})) == set(G8),
            "all eight currencies must remain present")
    require(isinstance(today, date), "expected actual Rome date")
    result = json.loads(json.dumps(existing, ensure_ascii=False))
    changed = []
    for currency in G8:
        row = result["currencies"][currency]
        require(row.get("kind") in {"OIS", "FUTURES", "FUTURES SECONDARI", "PROXY FUTURES"}
                and set(row.get("horizons", {})) == set(HORIZONS),
                currency + " fallback source type or 3-tenor panel invalid")
        fresh = candidate(currency, operational, estimated, nzd)
        if not fresh:
            continue
        # Instrument-family changes must be separately reviewed, not merged
        # silently into an OIS-labelled or futures-labelled curve.
        require(fresh["kind"] == row["kind"],
                currency + " changed benchmark family; independent review required")
        updated = False
        for h, quote in fresh["horizons"].items():
            require(date.fromisoformat(quote["as_of"]) <= today,
                    currency + " has an impossible future quote")
            previous = row["horizons"][h]
            previous_day = date.fromisoformat(previous["as_of"])
            if date.fromisoformat(quote["as_of"]) < previous_day:
                continue
            if previous != quote:
                row["horizons"][h] = quote
                updated = True
        if updated:
            row["quality"] = fresh["quality"]
            row["source"] = fresh["source"]
            row["as_of"] = max(x["as_of"] for x in row["horizons"].values())
            changed.append(currency)
    if changed:
        result["snapshot_built_from_repo_date"] = today.isoformat()
        result["notes"] = (
            "Automatically refreshed from dated G8 operational futures/OIS, "
            "secondary estimated futures and NZD ASX bank-bill proxy. Each "
            "tenor retains its own observation date; no fake OIS, no FX signal."
        )
    return result, changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="Validate generation and print changes without writing")
    args = parser.parse_args()
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    existing = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    op = json.loads(OPERATIONAL.read_text(encoding="utf-8"))
    est = json.loads(ESTIMATED.read_text(encoding="utf-8"))
    nzd = json.loads(NZD_PROXY.read_text(encoding="utf-8"))
    generated, changed = rebuild(existing, op, est, nzd, today=today)
    if changed and not args.check:
        SNAPSHOT.write_text(json.dumps(generated, indent=2, ensure_ascii=False)
                            + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "UPDATED" if changed else "NO_NEW_QUOTES",
        "changed_currencies": changed,
        "write": bool(changed and not args.check),
        "all_8_currencies": len(generated["currencies"]) == 8,
        "all_24_tenors": all(len(x["horizons"]) == 3 for x in generated["currencies"].values()),
        "fx_core_effect": "NONE",
        "official_ois_imputation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
