#!/usr/bin/env python3
"""One-time verified ECB 29 October 2026 decision and official 17 December meeting.

This updates only EUR issuer facts in a candidate NATIVE_CB_DATA. The canonical
direct-section update validates the runtime mapping separately. It never
changes OIS/futures pricing, macro inputs, FX inputs or other currencies.
Official issuer documentation:
https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.mt.html
https://www.ecb.europa.eu/press/pr/date/2025/html/ecb.pr250424~2643533670.et.html
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

LAST_ISSUER_DECISION = "2026-10-29"
NEXT_ISSUER_MEETING = "2026-12-17"
PRIOR_DATE = "2026-09-10"
OFFICIAL_DECISION_URL = "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.mt.html"
OFFICIAL_SCHEDULE_URL = "https://www.ecb.europa.eu/press/pr/date/2025/html/ecb.pr250424~2643533670.et.html"
NEW_ACTION = "INVARIATO"
NEW_IMPULSE = "HOLD_DATA_DEPENDENT"
NEW_STANCE = "INVARIATA · dati dipendenti"
NEW_CONTEXT = ("BCE 29 ottobre 2026: i tre tassi ufficiali restano invariati; "
               "il tasso sui depositi resta al 2,50%. Il Consiglio segnala "
               "rischi al rialzo per l’inflazione e al ribasso per la crescita "
               "legati all’energia, senza pre-impegnarsi su un percorso dei tassi.")
NEW_NEXT = ("Decisioni dipendenti dai dati e riunione per riunione; nessun "
            "percorso dei tassi predefinito. Prossima riunione 17 dicembre 2026.")
NEW_BIAS = "HOLD · DATA-DIPENDENT"

G8 = {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"}

def patch(cb: dict) -> tuple[dict, str]:
    if not isinstance(cb, dict) or set(cb) != G8:
        raise ValueError("ECB_CATCHUP_FAIL_CLOSED: unexpected G8 CB universe")
    current = cb["EUR"]
    if not isinstance(current, dict):
        raise ValueError("ECB_CATCHUP_FAIL_CLOSED: malformed ECB CB record")
    try:
        old_date = date.fromisoformat(current.get("last_date"))
    except (ValueError, TypeError):
        raise ValueError("ECB_CATCHUP_FAIL_CLOSED: invalid current ECB decision date")
    target = date.fromisoformat(LAST_ISSUER_DECISION)
    if old_date > target:
        return deepcopy(cb), "SKIP_NEWER_CERTIFIED_EUR_DECISION"
    result = deepcopy(cb)
    eur = result["EUR"]
    fields = {
        "last_date": LAST_ISSUER_DECISION, "next_meeting": NEXT_ISSUER_MEETING,
        "action": NEW_ACTION, "impulse": NEW_IMPULSE, "stance": NEW_STANCE,
        "context": NEW_CONTEXT, "official_next": NEW_NEXT, "official_bias": NEW_BIAS,
    }
    if old_date == target:
        if any(eur.get(k) != v for k, v in fields.items()):
            raise ValueError("ECB_CATCHUP_FAIL_CLOSED: decision date already present with different facts")
        return result, "ALREADY_CERTIFIED_NO_CHANGE"
    if (current.get("bank") != "ECB" or current.get("rate") != 2.5
            or current.get("rate_text") != "Deposit 2.50%"
            or current.get("next_meeting") != LAST_ISSUER_DECISION
            or current.get("action") != "RIALZO +25 pb"
            or current.get("impulse") != "TIGHTENING"):
        raise ValueError("ECB_CATCHUP_FAIL_CLOSED: prior certified ECB source does not match")
    for field, value in fields.items():
        eur[field] = value
    assert eur["rate"] == current["rate"] == 2.5
    assert eur["rate_text"] == current["rate_text"]
    assert eur["market_pricing"] == current["market_pricing"]
    assert all(result[k] == cb[k] for k in cb if k != "EUR")
    return result, "OFFICIAL_ECB_2026_10_29_CATCHUP_READY"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("live_data/sections/NATIVE_CB_DATA.json"))
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    original = json.loads(args.input.read_text(encoding="utf-8"))
    candidate, status = patch(original)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if candidate == original:
        args.output.write_bytes(args.input.read_bytes())
    else:
        args.output.write_text(json.dumps(candidate, separators=(",",":"), ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({
        "status": status, "changed": candidate != original,
        "official_decision_date": LAST_ISSUER_DECISION,
        "official_next_meeting": NEXT_ISSUER_MEETING,
        "official_sources": [OFFICIAL_DECISION_URL, OFFICIAL_SCHEDULE_URL],
        "rate_level_changed": False, "market_pricing_unchanged": True,
        "core_or_ois_or_pair_effect": "NONE",
        "record_changed": ["EUR"] if candidate != original else [],
    }, sort_keys=True))

if __name__ == "__main__":
    main()
