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
    "EUR": "Eurex FST3: settlement ufficiali non accessibili con il percorso privato richiesto; contratti secondari su date diverse, non curva OIS.",
    "CHF": "Settlement futures SARON ICE/Eurex non certificati in una stessa serie storica.",
    "NZD": "NZOS/NZOR ufficiali richiedono licenza NZdata; nessun accesso certificato attivo. ASX Bank Bill indica solo direzione, non OIS.",
}
NEXT_STEP = {
    "USD": "Ottenere CME ZQ T, T−1, T−5 per gli stessi contratti e verificarne la licenza.",
    "EUR": "Accordo dati istituzionale/vendor autorizzato, poi settlement FST3 T/T−1/T−5 stessa scadenza e verifica diritti, roll e convenzioni.",
    "CHF": "Validare ICE SA3 oppure Eurex FSR3, senza unire exchange o date differenti.",
    "NZD": "Attivare licenza NZOS/NZOR e diritti di uso/visualizzazione; certificare curva 3M/6M/12M e storico T/T−1/T−5.",
}

def build(plan: dict, operational: dict, official: dict, rates: dict, chf10: dict,
          *, today: str) -> dict:
    date = datetime.strptime(today, "%Y-%m-%d").date()
    evidence = audit(plan, operational, official)
    decisions = evidence["blocked_source_decisions"]
    if set(decisions) != set(BLOCKED):
        raise ValueError("readiness currency universe must be USD EUR CHF NZD")
    # The access registry is an immutable catalogue of reviewed source
    # candidates. Dossiers shown as *pending* depend on actual operational
    # certification: a separately approved official source must leave this
    # pending list without the audit itself certifying any data.
    items = {}
    for ccy in BLOCKED:
        row = decisions[ccy]
        actual = operational["currencies"][ccy]
        if row["operational_status"] != actual["operational_status"]:
            raise ValueError(f"{ccy}: operational source mismatch")
        if actual["operational_status"] == "GREEN_OFFICIAL":
            # The source audit already requires corresponding ACTIVE canonical
            # OIS and official backtest qualification. This dossier is resolved.
            continue
        if actual["operational_status"] not in ("WITHHELD", "GREEN_ESTIMATED"):
            raise ValueError(f"{ccy}: unknown pending operational status")
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
            "obstacle": EXPLANATION[ccy] if row["operational_status"] == "WITHHELD" else "Fonte indicativa: manca certificazione operativa.",
            "activation_requirement": NEXT_STEP[ccy],
            "indicative_quote_dates": quoted,
            "dates_joinable": False,
            "usable_for_policy_pricing": False,
            "operational_as_of": actual.get("as_of"),
            "price_or_curve_embedded": False,
            "backtest_eligible_as_official": False,
        }
    # The user must see the useful non-OIS research context without
    # accidentally interpreting a secondary future or bank-bill contract as
    # an official policy curve. Export dates and provenance only, no levels.
    if "EUR" in items:
        q=decisions["EUR"]["individual_verified_quote_dates"]
        if any(h not in ("3m","6m","12m") for h in q):
            raise ValueError("EUR unapproved source tenor")
        days=set(q.values())
        items["EUR"]["research_context"]={
            "kind":"DATED_ESTR_FUTURES_QUOTES_NOT_OIS",
            "instrument":"Eurex FST3 individual dated secondary contract observations",
            "quote_dates":dict(q),
            "full_horizon_set":set(q)=={"3m","6m","12m"},
            "same_date_across_horizons":bool(q) and len(days)==1,
            "status":"MIXED_DATE_QUOTES" if len(days)>1 else
                     "PARTIAL_QUOTES" if len(q)<3 else "CONTRACT_DATES_MATCH_UNLICENSED",
            "rates_embedded":False,"cross_date_join_allowed":False,
            "policy_delta_allowed":False,"eligible_as_ois":False,
        }
    if "NZD" in items:
        p=operational["currencies"]["NZD"].get("market_direction_proxy")
        proxy_ok=(isinstance(p,dict) and
                  p.get("status")=="LIVE_DIRECTIONAL_PROXY_READY" and
                  p.get("source_quality")=="OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY" and
                  p.get("substitutes_for_ois_level") is False and
                  p.get("policy_delta_from_proxy_allowed") is False)
        if proxy_ok:
            asof=p.get("as_of")
            try:
                proxy_day=datetime.strptime(asof,"%Y-%m-%d").date()
            except (TypeError,ValueError) as exc:
                raise ValueError("NZD invalid exchange observation date") from exc
            if proxy_day>date:
                raise ValueError("NZD future-dated bank-bill proxy")
            items["NZD"]["research_context"]={
                "kind":"ASX_NZD_BANK_BILL_DIRECTION_NOT_OIS",
                "instrument":"ASX NZ 90-Day Bank Bill futures",
                "proxy_as_of":asof,
                "status":"RECENT_DIRECTIONAL" if (date-proxy_day).days<=5 else "HISTORICAL_DIRECTIONAL",
                "rates_embedded":False,"policy_delta_allowed":False,
                "eligible_as_ois":False,"substitutes_for_ois_level":False,
            }
        else:
            items["NZD"]["research_context"]={
                "kind":"ASX_NZD_BANK_BILL_DIRECTION_NOT_OIS",
                "proxy_as_of":None,"status":"NO_VALID_DIRECTIONAL_SOURCE",
                "rates_embedded":False,"policy_delta_allowed":False,
                "eligible_as_ois":False,"substitutes_for_ois_level":False,
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
    if "CHF" in items:
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
