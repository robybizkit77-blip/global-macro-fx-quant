#!/usr/bin/env python3
"""Gate for genuine prospective frozen-Core observations, not new Core signals."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ROME = ZoneInfo("Europe/Rome")
FX = ROOT / "live_data/sections/ECB_G8_PRICE_HISTORY.json"
PAIR = ROOT / "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"
CORE = ROOT / "live_data/sections/D.json"

G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
EXPECTED_UNORDERED_G8 = {
    frozenset((a, b)) for i, a in enumerate(G8) for b in G8[i + 1:]
}


def certified_pair_universe(setup: dict, core: dict) -> bool:
    """The current overlay and frozen Core must cover the SAME canonical G8 28."""
    price_pairs = setup.get("pairs")
    core_pairs = core.get("pairs")
    states = core.get("pairStates")
    if (not isinstance(price_pairs, dict) or len(price_pairs) != 28
            or not isinstance(core_pairs, list) or len(core_pairs) != 28
            or not isinstance(states, dict) or len(states) != 28):
        return False
    names = []
    for key, row in price_pairs.items():
        if (not isinstance(key, str) or len(key) != 6
                or not isinstance(row, dict)):
            return False
        a, b = key[:3], key[3:]
        if (a not in G8 or b not in G8 or a == b
                or row.get("canonical_pair") != a + "/" + b):
            return False
        names.append(a + "/" + b)
    if len(set(names)) != 28:
        return False
    observed = {frozenset(x.split("/")) for x in names}
    if observed != EXPECTED_UNORDERED_G8:
        return False
    model_names = [r.get("pair") if isinstance(r, dict) else None
                   for r in core_pairs]
    return (len(set(model_names)) == 28 and set(model_names) == set(names)
            and set(states) == set(names))



def schedule_attempt(now, event, cron):
    """CET/CEST 19:30 primary and 20:30 real-time backup, no backfill."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware actual schedule clock required")
    if event != "schedule":
        return "MANUAL_ATTEMPT"
    if now.astimezone(ROME).utcoffset().total_seconds() == 7200:
        primary, fallback = "30 17 * * 1-5", "30 18 * * 1-5"
    else:
        primary, fallback = "30 18 * * 1-5", "30 19 * * 1-5"
    if cron == primary:
        return "PRIMARY_1930_ROME"
    if cron == fallback:
        return "FALLBACK_2030_ROME"
    return "SKIPPED_DUPLICATE_DST_UTC_SLOT"


def assess(now, fx, setup, core):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("actual forward observation must have timezone")
    local = now.astimezone(ROME)
    today = local.date().isoformat()
    reasons = []
    if local.weekday() >= 5:
        reasons.append("NOT_ROME_BUSINESS_WEEKDAY")
    if local.hour < 19 or local.hour >= 24:
        reasons.append("NOT_AFTER_1900_ROME")
    if not isinstance(fx, dict) or (
            fx.get("status") != "CURRENT_OFFICIAL_HISTORY"
            or fx.get("source_url") !=
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"):
        reasons.append("ECB_SOURCE_NOT_OFFICIAL_HISTORY")
    # A date label alone does not certify a price. The final official row
    # must be complete, dated as the declared current session and internally
    # counted correctly before it becomes a prospective t0 reference.
    if fx.get("last_as_of") != today:
        reasons.append("ECB_CURRENT_DAY_FIXING_NOT_PRESENT")
    fx_rows = fx.get("rows")
    last = fx_rows[-1] if isinstance(fx_rows, list) and fx_rows else None
    from math import isfinite
    if (not isinstance(last, dict) or last.get("Date") != today
            or not isinstance(fx.get("row_count"), int)
            or fx["row_count"] != len(fx_rows) or len(fx_rows) < 21
            or any(type(last.get(ccy)) not in (int, float)
                   or not isfinite(last[ccy]) or last[ccy] <= 0
                   for ccy in G8)):
        reasons.append("ECB_OFFICIAL_ROW_INTEGRITY_FAILED")
    if (not isinstance(setup, dict) or setup.get("status") != "CURRENT_CANONICAL_ENGINE"
            or setup.get("pair_count") != 28
            or setup.get("price_asof") != today
            or not isinstance(setup.get("pairs"), dict)
            or len(setup["pairs"]) != 28):
        reasons.append("PAIR_SETUP_CURRENT_DAY_28_PAIR_PRICE_NOT_PRESENT")
    if (not isinstance(core, dict) or core.get("asOf") is None
            or not isinstance(core.get("pairs"), list)
            or len(core["pairs"]) != 28
            or not isinstance(core.get("pairStates"), dict)
            or len(core["pairStates"]) != 28):
        reasons.append("CORE_CANONICAL_28_PAIR_SURFACE_MISSING")
    if isinstance(setup, dict) and isinstance(core, dict):
        if not certified_pair_universe(setup, core):
            reasons.append("PAIR_CORE_G8_ORIENTATION_MISMATCH")
        if setup.get("macro_baseline_asof") != core.get("asOf"):
            reasons.append("PAIR_MACRO_BASELINE_MISMATCH")
        audit = setup.get("price_audit")
        if (not isinstance(audit, dict) or audit.get("status") != "PASS"
                or audit.get("as_of") != today
                or audit.get("overlay_asof") != today
                or audit.get("history_asof") != today
                or audit.get("pair_count") != 28
                or audit.get("complete_pair_count") != 28
                or audit.get("no_lookahead") is not True
                or audit.get("returns_complete") is not True):
            reasons.append("PAIR_PRICE_AUDIT_NOT_CERTIFIED")
    if isinstance(core, dict) and isinstance(core.get("asOf"), str):
        try:
            if dt.date.fromisoformat(core["asOf"]) >= local.date():
                reasons.append("CORE_BASELINE_NOT_HISTORICALLY_PREEXISTING")
        except ValueError:
            reasons.append("CORE_BASELINE_DATE_INVALID")
    return {
        "schema": "GMFQ_FORWARD_FROZEN_CORE_CAPTURE_ADMISSION_V1",
        "status": "ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION" if not reasons else "BLOCKED_NO_CAPTURE",
        "checks": reasons,
        "observed_at_utc": now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "local_date": today,
        "core_baseline_as_of": core.get("asOf") if isinstance(core, dict) else None,
        "core_recomputed": False,
        "official_fx_fixing_date": fx.get("last_as_of"),
        "operational_pair_price_as_of": setup.get("price_asof") if isinstance(setup, dict) else None,
        "new_core_signal": False,
        "backfilled": False,
        "writes_model_scores": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        ap.error("admission receipt must remain under /tmp")
    now = dt.datetime.now(dt.timezone.utc)
    result = assess(now, json.loads(FX.read_text()), json.loads(PAIR.read_text()),
                    json.loads(CORE.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
