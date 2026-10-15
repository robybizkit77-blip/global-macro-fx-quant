#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CB_PATH = ROOT / "live_data/sections/NATIVE_CB_DATA.json"
OIS_PATH = ROOT / "live_data/sections/OIS_DATA.json"
RATES_PATH = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
OUT_PATH = ROOT / "live_data/sections/CB_PRICING_ESTIMATED.json"

ELIGIBLE = ("USD", "EUR", "CHF", "NZD")
CONFIDENCE = {"USD": "B", "EUR": "B", "CHF": "B", "NZD": "C"}


def _num(v):
    try:
        if v is None:
            return None
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def build_currency(ccy, cb_row, ois_row, rates_row=None):
    # Estimated layer is only legal while official OIS remains withheld.
    if (ois_row or {}).get("status") != "WITHHELD":
        return {
            "currency": ccy,
            "status": "NOT_APPLICABLE_OFFICIAL_ACTIVE",
            "official_ois_status": (ois_row or {}).get("status"),
        }

    mp = (cb_row or {}).get("market_pricing") or {}
    policy_rate = _num((cb_row or {}).get("rate"))
    vals = {
        "3m": _num(mp.get("h3m")),
        "6m": _num(mp.get("h6m")),
        "12m": _num(mp.get("h12m")),
    }
    n = sum(v is not None for v in vals.values())
    if n == 0:
        status = "WITHHELD"
    elif n == 3:
        status = "ESTIMATED_ACTIVE"
    else:
        status = "ESTIMATED_PARTIAL"

    horizons = {}
    for h, rate in vals.items():
        horizons[h] = {
            "rate": rate,
            "policy_delta_bp": None if rate is None or policy_rate is None else round((rate - policy_rate) * 100.0, 1),
        }

    available_deltas = [x["policy_delta_bp"] for x in horizons.values() if x["policy_delta_bp"] is not None]
    if not available_deltas:
        direction = "WITHHELD"
    elif available_deltas[-1] > 5:
        direction = "UP"
    elif available_deltas[-1] < -5:
        direction = "DOWN"
    else:
        direction = "FLAT"

    r2_change = _num((rates_row or {}).get("chg2_bp"))
    return {
        "currency": ccy,
        "status": status,
        "official_ois_status": "WITHHELD",
        "as_of": mp.get("as_of"),
        "policy_rate": policy_rate,
        "instrument": mp.get("instrument"),
        "source": mp.get("source"),
        "source_url": mp.get("source_url"),
        "source_quality": mp.get("quality"),
        "freshness_status": mp.get("freshness_status"),
        "confidence_grade": CONFIDENCE[ccy],
        "horizons": horizons,
        "direction_vs_policy": direction,
        "two_year_change_1w_proxy_bp": r2_change,
        "two_year_change_note": "Front-end context only; this is the 2Y yield weekly change, not an OIS/futures weekly repricing measure.",
        "note": mp.get("note"),
        "governance": {
            "informational_only": True,
            "core_score_effect": "NONE",
            "bias_effect": "NONE",
            "sizing_effect": "NONE",
            "pair_engine_effect": "NONE",
            "backtest_eligible_as_official_ois": False,
        },
    }


def build(cb, ois, rates):
    out = {
        "schema": "GMFQ_CB_PRICING_ESTIMATED_V1",
        "status": "INFORMATIONAL_ONLY",
        "official_ois_runtime_untouched": True,
        "currencies": {},
    }
    for ccy in ELIGIBLE:
        out["currencies"][ccy] = build_currency(
            ccy,
            (cb or {}).get(ccy) or {},
            ((ois or {}).get("currencies") or {}).get(ccy) or {},
            (rates or {}).get(ccy) or {},
        )
    return out


def main():
    cb = json.loads(CB_PATH.read_text(encoding="utf-8"))
    ois = json.loads(OIS_PATH.read_text(encoding="utf-8"))
    rates = json.loads(RATES_PATH.read_text(encoding="utf-8"))
    out = build(cb, ois, rates)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "output": str(OUT_PATH.relative_to(ROOT)),
        "currencies": {k: v["status"] for k, v in out["currencies"].items()},
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
