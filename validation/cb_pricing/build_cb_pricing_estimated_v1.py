#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CB_PATH = ROOT / "live_data/sections/NATIVE_CB_DATA.json"
OIS_PATH = ROOT / "live_data/sections/OIS_DATA.json"
LIVE_PATH = ROOT / "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json"
NZD_PROXY_PATH = ROOT / "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"
OUT_PATH = ROOT / "live_data/sections/CB_PRICING_ESTIMATED.json"

ELIGIBLE = ("USD", "EUR", "CHF", "NZD")
CONFIDENCE = {"USD": "B", "EUR": "B", "CHF": "B", "NZD": "C"}
LIVE_METHOD_ID = "TRADINGVIEW_DATED_FUTURES_SSR_V2"
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
    for h in ("3m", "6m", "12m"):
        x = hs.get(h) or {}
        if _num(x.get("rate")) is None:
            return False
        if "!" in str(x.get("contract") or "") or "!" in str(x.get("symbol") or ""):
            return False
    return True


def _valid_nzd_directional_proxy(proxy: dict | None) -> dict | None:
    row = proxy or {}
    if row.get("schema") != "GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1":
        return None
    if row.get("status") != "LIVE_DIRECTIONAL_PROXY_READY" or row.get("currency") != "NZD":
        return None
    gov = row.get("governance") or {}
    if gov.get("informational_only") is not True:
        return None
    if gov.get("substitutes_for_ois_level") is not False:
        return None
    if gov.get("policy_delta_from_proxy_allowed") is not False:
        return None
    hs = row.get("horizons") or {}
    if not all(_num((hs.get(h) or {}).get("implied_bank_bill_rate")) is not None for h in ("3m", "6m", "12m")):
        return None
    return row


def build_currency(ccy, cb_row, ois_row, live_row=None, directional_proxy=None):
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
            h: {k: v for k, v in (hs.get(h) or {}).items() if k != "rate"}
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

    # Preserve *indicative* source levels, not a settlement or a tradable
    # rate path. Both versions are retained in the separate quarantine.
    # Do not substitute the old native CB fallback, infer policy deltas, or
    # freeze the other currencies merely because one daily-bar disagrees.
    conflicted = (ccy in ("USD", "EUR", "CHF") and
                  (live_row or {}).get("source_conflict_status") ==
                  "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT")
    if conflicted:
        lr = live_row or {}
        hs = lr.get("horizons") or {}
        vals = {h: _num((hs.get(h) or {}).get("rate"))
                for h in ("3m", "6m", "12m")}
        # An incomplete source is unavailable, never silently native-fallback.
        if any(v is None for v in vals.values()):
            vals = {h: None for h in vals}
        as_of = lr.get("as_of")
        instrument = lr.get("instrument")
        source = lr.get("source")
        source_url = lr.get("source_url")
        source_quality = "SECONDARY_CONFLICTED_INDICATIVE_NOT_OIS"
        freshness_status = "SAME_DAY_SOURCE_CONFLICT_UNRESOLVED"
        confidence = "C"
        input_mode = "LIVE_SECONDARY_CONFLICT_INDICATIVE"
        method_id = LIVE_METHOD_ID
        horizon_meta = {h: {k: v for k, v in (hs.get(h) or {}).items()
                            if k != "rate"} for h in ("3m", "6m", "12m")}
        note = ("Indicative secondary futures quotes have unresolved same-contract/"
                "same-day source disagreement; first and later prints are "
                "preserved separately. Levels may be displayed as provisional "
                "estimates only. No official OIS, policy delta or 1D/1W "
                "repricing is certified.")

    # The EUR native CB quote is a historical secondary snapshot, not a live
    # market path. Never revive it as an active 3-horizon estimate if the
    # independently dated live overlay cannot be used. A source date must be
    # unambiguous and recent, not an observation range such as "Sep 26/29".
    if ccy == "EUR" and input_mode == "NATIVE_CB_FALLBACK":
        try:
            source_day = date.fromisoformat(str(as_of))
            age_days = (date.today() - source_day).days
        except (TypeError, ValueError):
            age_days = None
        if age_days is None or not 0 <= age_days <= 5:
            vals = {h: None for h in ("3m", "6m", "12m")}
            source_quality = "STALE_SECONDARY_WITHHELD"
            freshness_status = "STALE_SOURCE_WITHHELD"
            note = "Historical EUR futures quote is not a current market-pricing observation; use only independently dated verified contracts. No official OIS curve is available."

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
            "policy_delta_bp": (None if conflicted or rate is None or policy_rate is None
                                else round((rate - policy_rate) * 100.0, 1)),
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

    result = {
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
        "change_status": ("CONFLICTED_SECONDARY_NO_REPRICING"
                          if conflicted else "DERIVED_ONLY_FROM_HOMOGENEOUS_SNAPSHOT_HISTORY"),
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
    if conflicted:
        result["source_conflict_status"] = lr["source_conflict_status"]
        result["source_conflict_keys"] = lr.get("source_conflict_keys", [])
    proxy = _valid_nzd_directional_proxy(directional_proxy) if ccy == "NZD" else None
    if proxy is not None:
        result["market_direction_proxy"] = {
            "status": proxy.get("status"),
            "as_of": proxy.get("as_of"),
            "instrument": proxy.get("instrument"),
            "source": proxy.get("source"),
            "source_url": proxy.get("source_url"),
            "source_quality": proxy.get("source_quality"),
            "confidence_grade": proxy.get("confidence_grade"),
            "basis_warning": proxy.get("basis_warning"),
            "mapping_policy": proxy.get("mapping_policy"),
            "horizons": proxy.get("horizons"),
            "substitutes_for_ois_level": False,
            "policy_delta_from_proxy_allowed": False,
        }
    return result


def build(cb, ois, live=None, nzd_proxy=None):
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
            nzd_proxy if ccy == "NZD" else None,
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


def load_nzd_directional_proxy():
    if not NZD_PROXY_PATH.exists():
        return None
    try:
        data = json.loads(NZD_PROXY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _valid_nzd_directional_proxy(data)


def main():
    cb = json.loads(CB_PATH.read_text(encoding="utf-8"))
    ois = json.loads(OIS_PATH.read_text(encoding="utf-8"))
    live = load_live_overlay()
    nzd_proxy = load_nzd_directional_proxy()
    out = build(cb, ois, live, nzd_proxy)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "output": str(OUT_PATH.relative_to(ROOT)),
        "currencies": {k: {"status": v["status"], "input_mode": v.get("input_mode"), "directional_proxy": "market_direction_proxy" in v} for k, v in out["currencies"].items()},
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
