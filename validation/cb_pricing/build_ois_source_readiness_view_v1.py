#!/usr/bin/env python3
"""Generate a public, strictly informational OIS source-readiness view.

One JSON published alongside OIS_OPERATIONAL_VIEW. A source link or access
audit NEVER authorises an official OIS promotion, policy delta or backtest.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from audit_ois_source_access_v1 import ACCESS, VIEW, OFFICIAL, audit

ROOT = Path(__file__).resolve().parents[2]
RATES = ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
CHF_SPOT = ROOT / "live_data/sections/CHF_SNB_10Y_SPOT_CONTEXT.json"
OUT = ROOT / "live_data/sections/OIS_SOURCE_READINESS_VIEW.json"
BLOCKED = ("USD", "EUR", "CHF", "NZD")
EXPLANATION = {
    "USD": "Settlement CME Fed Funds incompleti (manca una serie storica sincronizzata con diritti d'uso verificati).",
    "EUR": "Settlement Eurex €STR FST3 non sincronizzati e non certificati per 3, 6 e 12 mesi.",
    "CHF": "Settlement futures SARON ICE/Eurex non certificati in una stessa serie storica.",
    "NZD": "Il benchmark NZOS ufficiale richiede accesso autorizzato; Bank Bill non equivale a OIS.",
}
NEXT_STEP = {
    "USD": "Ottenere CME ZQ T, T−1, T−5 per gli stessi contratti e verificarne la licenza.",
    "EUR": "Verificare Eurex FST3 con date T, T−1, T−5, convenzioni e permessi d'uso.",
    "CHF": "Validare ICE SA3 oppure Eurex FSR3, senza unire exchange o date differenti.",
    "NZD": "Attivare fonte NZOS/NZOR autorizzata e certificare 3M, 6M, 12M.",
}

def build(plan: dict, operational: dict, official: dict, rates: dict, chf10: dict,
          *, today: str) -> dict:
    date = datetime.strptime(today, "%Y-%m-%d").date()
    evidence = audit(plan, operational, official)
    decisions = evidence["blocked_source_decisions"]
    if set(decisions) != set(BLOCKED):
        raise ValueError("readiness currency universe must be USD EUR CHF NZD")
    items = {}
    for ccy in BLOCKED:
        row = decisions[ccy]
        actual = operational["currencies"][ccy]
        if row["operational_status"] != actual["operational_status"]:
            raise ValueError(f"{ccy}: operational source mismatch")
        source = row["source_url"]
        if not source.startswith("https://"):
            raise ValueError(f"{ccy}: non-HTTPS source link")
        quoted = row["individual_verified_quote_dates"]
        # A quote is only a dated instrument observation, never an OIS curve.
        if row["operational_status"] == "WITHHELD":
            assert actual.get("backtest_eligible_as_official") is False
        items[ccy] = {
            "currency": ccy,
            "status": row["operational_status"],
            "source_reviewed_as_of": evidence["source_reviewed_as_of"],
            "source_title": row["candidate"],
            "source_url": source,
            "obstacle": EXPLANATION[ccy] if row["operational_status"] == "WITHHELD" else "Fonte già attiva: riconfermare licenza e omogeneità.",
            "activation_requirement": NEXT_STEP[ccy] if row["operational_status"] == "WITHHELD" else "Mantenere monitoraggio e verifiche.",
            "indicative_quote_dates": quoted,
            "dates_joinable": False,
            "usable_for_policy_pricing": row["operational_status"] == "GREEN_OFFICIAL",
            "operational_as_of": actual.get("as_of"),
            "price_or_curve_embedded": False,
            "backtest_eligible_as_official": row["operational_status"] == "GREEN_OFFICIAL",
        }
    chf = rates.get("CHF") or {}
    try:
        paired_date = datetime.strptime(chf["date"], "%Y-%m-%d").date()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("canonical CHF paired date unavailable") from exc
    if paired_date > date:
        raise ValueError("canonical CHF paired future-dated")
    snb_valid = (chf10.get("schema") == "GMFQ_CHF_SNB_10Y_SPOT_CONTEXT_V1"
        and chf10.get("status") == "OFFICIAL_PUBLISHED_10Y_INFORMATIONAL"
        and chf10.get("currency") == "CHF" and chf10.get("tenor") == "10Y"
        and chf10.get("has_current_2y") is False
        and chf10.get("eligible_for_curve_spreads") is False
        and chf10.get("eligible_for_core_signals") is False)
    single_day = None
    if snb_valid:
        candidate = datetime.strptime(chf10["as_of"], "%Y-%m-%d").date()
        if 0 <= (date-candidate).days <= 5:
            single_day = candidate.isoformat()
    items["CHF"]["government_rates"] = {
        "last_paired_2y10y_as_of": paired_date.isoformat(),
        "paired_current": 0 <= (date-paired_date).days <= 5,
        "separate_10y_snb_as_of": single_day,
        "has_new_verified_2y": False,
        "cross_date_spread_allowed": False,
    }
    return {
        "schema": "GMFQ_OIS_SOURCE_READINESS_VIEW_V1",
        "status": "READ_ONLY_SOURCE_READINESS",
        "as_of": today,
        "source_reviewed_as_of": evidence["source_reviewed_as_of"],
        "operational_summary": operational["summary"],
        "blocked_currency_count": sum(x["status"] == "WITHHELD" for x in items.values()),
        "currencies": items,
        "no_core_score_effect": True,
        "no_bias_effect": True,
        "no_sizing_effect": True,
        "no_backtest_effect": True,
        "no_automatic_promotions": True,
        "prices_omitted": True,
        "note": "Stato accesso alle fonti; non è una previsione, non certifica nuovi prezzi.",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=str(ACCESS))
    ap.add_argument("--view", default=str(VIEW))
    ap.add_argument("--official", default=str(OFFICIAL))
    ap.add_argument("--rates", default=str(RATES))
    ap.add_argument("--chf10", default=str(CHF_SPOT))
    ap.add_argument("--output", default=str(OUT))
    ap.add_argument("--today", default=datetime.now(timezone.utc).date().isoformat())
    args = ap.parse_args()
    obj = build(*(json.loads(Path(p).read_text(encoding="utf-8"))
                  for p in (args.plan, args.view, args.official, args.rates, args.chf10)), today=args.today)
    Path(args.output).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print("OIS_SOURCE_READINESS_NON_OPERATIVE_PASS",obj["as_of"],obj["blocked_currency_count"])

if __name__ == "__main__":
    main()
