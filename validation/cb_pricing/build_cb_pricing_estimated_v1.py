#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CB_PATH = ROOT / "live_data/sections/NATIVE_CB_DATA.json"
OIS_PATH = ROOT / "live_data/sections/OIS_DATA.json"
LIVE_PATH = ROOT / "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json"
OUT_PATH = ROOT / "live_data/sections/CB_PRICING_ESTIMATED.json"

ELIGIBLE = ("USD", "EUR", "CHF", "NZD")
CONFIDENCE = {"USD": "B", "EUR": "B", "CHF": "B", "NZD": "C"}
LIVE_METHOD_ID = "TRADINGVIEW_EXCHANGE_LABELLED_FUTURES_SSR_V1"
NATIVE_METHOD_ID = "NATIVE_CB_ESTIMATED_V1"


def _num(v):
    try:
        if v is None:
            return None
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _live_usable(ccy: str, live_row: dict | None) -> bool:
    if ccy not in {"USD", "EUR", "CHF"}:
        return False
    row = live_row or {}
    if row.get("status") != "LIVE_SECONDARY_READY":
        return False
    hs = row.get("horizons") or {}
    return all(_num((hs.get(h) or {}).get("rate")) is not None for h in ("3m", "6m", "12m"))


def build_currency(ccy, cb_row, ois_row, live_row=None):
    # Estimated layer is only legal while official OIS remains withheld.
    if (ois_row or {}).get("status") != "WITHHELD":
        return {
            "currency": ccy,
            "status": "NOT_APPLICABLE_OFFICIAL_ACTIVE",
            "official_ois_status": (ois_row or {}).get("status"),
        }

    policy_rate = _num((cb_row or {}).get("rate"))
    if _live_usable(ccy, live_row):
        lr = live_row or {}
        hs = lr.get("horizons") or {}
        vals = {h: _num((hs.get(h) or {}).get("rate")) for h in ("3m", "6m", "12m")}
        as_of = lr.get("as_of")
        instrument = lr.get("instrument")
        source = lr.get("source")
        source_url = lr.get("source_url")
        source_quality = lr.get("source_quality")
        freshness_status = lr.get("freshness_status")
        confidence = lr.get("confidence_grade") or CONFIDENCE[ccy]
        note = lr.get("note")
        input_mode = "LIVE_SECONDARY_OVERLAY"
        method_id = LIVE_METHOD_ID
        horizon_meta = {
            h: {
                k: v
                for k, v in (hs.get(h) or {}).items()
                if k != "rate"
            }
            for h in ("3m", "6m", "12m")
        }
    else:
        mp = (cb_row or {}).get("market_pricing") or {}
        vals = {
            "3m": _num(mp.get("h3m")),
            "6m": _num(mp.get("h6m")),
            "12m": _num(mp.get("h12m")),
        }
        as_of = mp.get("as_of")
        instrument = mp.get("instrument")
        source = mp.get("source")
        source_url = mp.get("source_url")
        source_quality = mp.get("quality")
        freshness_status = mp.get("freshness_status")
        confidence = CONFIDENCE[ccy]
        note = mp.get("note")
        input_mode = "NATIVE_CB_FALLBACK"
        method_id = NATIVE_METHOD_ID
        horizon_meta = {h: {} for h in ("3m", "6m", "12m")}

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
            **horizon_meta[h],
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

    return {
        "currency": ccy,
        "status": status,
        "official_ois_status": "WITHHELD",
        "input_mode": input_mode,
        "method_id": method_id,
        "as_of": as_of,
        "policy_rate": policy_rate,
        "instrument": instrument,
        "source": source,
        "source_url": source_url,
        "source_quality": source_quality,
        "freshness_status": freshness_status,
        "confidence_grade": confidence,
        "horizons": horizons,
        "direction_vs_policy": direction,
        "change_1d_bp": None,
        "change_1w_bp": None,
        "change_status": "DERIVED_ONLY_FROM_HOMOGENEOUS_SNAPSHOT_HISTORY",
        "note": note,
        "governance": {
            "informational_only": True,
            "core_score_effect": "NONE",
            "bias_effect": "NONE",
            "sizing_effect": "NONE",
            "pair_engine_effect": "NONE",
            "backtest_eligible_as_official_ois": False,
        },
    }


def build(cb, ois, live=None):
    live_ccys = ((live or {}).get("currencies") or {}) if isinstance(live, dict) else {}
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
            live_ccys.get(ccy),
        )
    return out


def load_live_overlay():
    if not LIVE_PATH.exists():
        return None
    try:
        data = json.loads(LIVE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("schema") != "GMFQ_CB_PRICING_ESTIMATED_LIVE_QUOTES_V1":
        return None
    if data.get("status") != "INFORMATIONAL_ONLY" or data.get("official_ois_runtime_untouched") is not True:
        return None
    return data


def main():
    cb = json.loads(CB_PATH.read_text(encoding="utf-8"))
    ois = json.loads(OIS_PATH.read_text(encoding="utf-8"))
    live = load_live_overlay()
    out = build(cb, ois, live)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "output": str(OUT_PATH.relative_to(ROOT)),
        "currencies": {k: {"status": v["status"], "input_mode": v.get("input_mode")} for k, v in out["currencies"].items()},
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
