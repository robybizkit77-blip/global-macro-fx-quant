#!/usr/bin/env python3
"""G8 country-book evidence bridge V2: no fabricated household/firm dynamics.

Research ONLY. Sources are current-version *revised histories*, not certified
first-release data, and observation period is not publication date.
The bridge audits 8x3 country domains without generating FX signals.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from validation.macro import build_g8_causal_countrybook_pilot_v1 as v1

SCHEMA = "GMFQ_G8_CAUSAL_EVIDENCE_BRIDGE_RESEARCH_V2"
MACRO_SERIES = "live_data/sections/MACRO_SERIES.json"

# Direct, actual source indicators selected for each domestic channel.
# Absence is deliberate: NZD has no direct firm series in this source.
SELECTORS = {
    "USD": {
        "firms": ["US_NEWORDER_history_NEWORDER", "US_SLOOS_CI_LARGE_MIDDLE_history_value"],
        "labor": ["US_JTSHIR_history_JTSHIR", "US_JTSQUR_history_JTSQUR"],
        "households": ["US_PCEC96_history_value", "US_DSPIC96_history_DSPIC96"],
    },
    "EUR": {
        "firms": ["EA_BLS_CREDIT_STANDARDS_ENTERPRISES_history_value", "EA_IP_history_value"],
        "labor": ["EA_NEGOTIATED_WAGES_YOY_history_value", "EA_UNEMP_history_value"],
        "households": ["EA_RETAIL_VOL_history_value", "EA_ECFIN_BCS_LEAD_INDICATORS_history_Consumer"],
    },
    "GBP": {
        "firms": ["UK_BOE_DMP_LEAD_INDICATORS_history_SalesExpected", "UK_PRODUCTION_history_value"],
        "labor": ["UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value", "UK_UNEMP_RATE_history_value"],
        "households": ["UK_RETAIL_VOL_history_value", "UK_MORTGAGE_APPROVALS_HOUSE_PURCHASE_SA_history_value"],
    },
    "JPY": {
        "firms": ["JP_BOJ_TANKAN_LEAD_INDICATORS_history_Large_Manufacturing_Forecast", "JP_IIP_history_value"],
        "labor": ["JP_UNEMP_RATE_history_value", "JP_EMPLOYED_history_value"],
        "households": ["JP_RETAIL_history_value"],
    },
    "CHF": {
        "firms": ["CH_PRODUCTION_history_value"],
        "labor": ["CH_UNEMP_RATE_history_value", "CH_EMPLOYMENT_history_value"],
        "households": ["CH_RETAIL_REAL_history_value", "CH_SECO_CONSUMER_SENTIMENT_LEAD_history_SECO_Consumer_Sentiment"],
    },
    "CAD": {
        "firms": ["CA_BOC_BOS_LEAD_INDICATORS_history_BOS_Activity_Indicator", "CA_BUSINESS_LOANS_OUTSTANDING_history_value"],
        "labor": ["CA_UNEMP_RATE_history_value", "CA_EMPLOYMENT_history_value"],
        "households": ["CA_RETAIL_VOLUME_history_value", "CA_MORTGAGE_OUTSTANDING_UNINSURED_history_value"],
    },
    "AUD": {
        "firms": ["AU_CREDIT_BUSINESS_CURRENT_SA_history_value", "AU_OECD_CLI_LEAD_INDICATOR_history_OECD_CLI_AUS"],
        "labor": ["AU_UNEMP_RATE_history_value", "AU_WPI_YOY_history_value"],
        "households": ["AU_HOUSEHOLD_SPENDING_history_value", "AU_MORTGAGE_RATE_OWNER_OCC_OUTSTANDING_history_value"],
    },
    "NZD": {
        "firms": [],
        "labor": ["NZ_UNEMP_RATE_history_value", "NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Wage_1Y"],
        "households": ["NZ_RETAIL_VOLUME_Q_history_value"],
    },
}

ROLE_IT = {"firms":"Imprese", "labor":"Lavoro e salari", "households":"Famiglie e consumi"}
# Recency of observation period only. They are descriptive editorial limits,
# NOT official release freshness/service-level guarantees.
RECENT_DAYS = {"M":75, "Q":135, "W":21}
DATED_DAYS = {"M":150, "Q":235, "W":56}
FREQ_OVERRIDES = {
    "JP_BOJ_TANKAN_LEAD_INDICATORS_history_Large_Manufacturing_Forecast": "Q",
    "UK_BOE_DMP_LEAD_INDICATORS_history_SalesExpected": "M",
    "NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent_Wage_1Y": "Q",
    "CH_SECO_CONSUMER_SENTIMENT_LEAD_history_SECO_Consumer_Sentiment": "M",
}

def gate(condition, message):
    if not condition:
        raise ValueError("G8_EVIDENCE_V2_REJECTED: "+message)

def month_end(y,m):
    return date(y,m,calendar.monthrange(y,m)[1])

def observation_end(raw, frequency="M"):
    """Normalize heterogenous source PERIOD tokens; NEVER a release timestamp."""
    s=str(raw).strip()
    q=re.fullmatch(r"(\d{4})-?Q([1-4])",s)
    if q:
        y,n=map(int,q.groups())
        return month_end(y,n*3), "Q"
    if re.fullmatch(r"\d{4}[-/]\d{2}",s):
        y,m=map(int,re.split(r"[-/]",s))
        gate(1<=m<=12,"invalid YYYY-MM observation period")
        return month_end(y,m),frequency
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?",s):
        dt=date.fromisoformat(s[:10])
        if frequency in ("M","Q"):
            return month_end(dt.year,dt.month),frequency
        return dt,frequency
    for fmt in ("%d %b %Y","%d/%m/%Y","%b-%y"):
        try:
            dt=datetime.strptime(s,fmt).date()
            return (month_end(dt.year,dt.month) if frequency in ("M","Q") else dt),frequency
        except ValueError:
            continue
    raise ValueError("G8_EVIDENCE_V2_REJECTED: unsupported observation period "+s)

def inferred_frequency(row):
    hint=str(row.get("frequency") or "").upper()
    if hint in ("M","Q","W"):
        return hint
    if row["id"] in FREQ_OVERRIDES:
        return FREQ_OVERRIDES[row["id"]]
    s=str(row["last_date"])
    return "Q" if re.search(r"-?Q[1-4]$",s) else "M"

def evidence_row(row, *, today):
    ident=row["id"]
    dates=row.get("dates")
    vals=row.get("values")
    gate(isinstance(dates,list) and isinstance(vals,list) and
         len(dates)==len(vals) and len(vals)>=2,
         ident+" missing paired historical series")
    gate(all(type(x) in (float,int) and math.isfinite(x) for x in vals[-2:]),
         ident+" invalid numeric observations")
    gate(row.get("last_date")==dates[-1],
         ident+" inconsistent latest observation date")
    gate(type(row.get("last_value")) in (float,int) and
         math.isclose(row["last_value"],vals[-1],rel_tol=1e-10,abs_tol=1e-8),
         ident+" inconsistent latest observation value")
    freq=inferred_frequency(row)
    end, freq=observation_end(dates[-1],freq)
    prior, _=observation_end(dates[-2],freq)
    gate(prior<end<=today,ident+" non-increasing/future observation")
    days=(today-end).days
    max_gap={"M":45,"Q":106,"W":12}[freq]
    contiguous=(end-prior).days<=max_gap
    change=round(vals[-1]-vals[-2],8) if contiguous else None
    state=("RECENT_PERIOD_NOT_RELEASE_VERIFIED" if days<=RECENT_DAYS[freq]
           else "DATED_PERIOD_NOT_CURRENT" if days<=DATED_DAYS[freq]
           else "STALE_HISTORICAL_PERIOD")
    trend=("SALITA" if change is not None and change>1e-8
           else "DISCESA" if change is not None and change< -1e-8
           else "STABILE" if change is not None else "NO_CONTIGUOUS_COMPARISON")
    return {
        "id":ident,"label":row["label"],
        "observation_period":dates[-1],"prior_observation_period":dates[-2],
        "observation_end_assumed":end.isoformat(),
        "observation_period_age_days":days,"frequency":freq,
        "latest_value":vals[-1],"prior_value":vals[-2],
        "unit":row.get("unit") or "UNIT_NOT_SPECIFIED",
        "change_raw_units":change,
        "direction_of_reported_series":trend,
        "status":state,"contiguous_latest_observations":contiguous,
        "source_file":row.get("source_file"),
        "source_data_lineage":"REVISED_CURRENT_VINTAGE_NOT_FIRST_RELEASE",
        "publisher_release_timestamp":None,
        "direction_not_equivalent_to_causal_evidence":True,
    }

def describe_role(role, evidence):
    label=ROLE_IT[role]
    if not evidence:
        return (
          f"{label}: non esiste una serie diretta selezionata e verificata "
          "nel dataset disponibile. Il passaggio causale rimane non osservato."
        )
    # One main anchor + one cross-check avoids numerical clutter.
    first=evidence[0]
    dir_it={"SALITA":"è salita","DISCESA":"è scesa",
            "STABILE":"è rimasta stabile",
            "NO_CONTIGUOUS_COMPARISON":"non ha un confronto contiguo verificato"}[
                first["direction_of_reported_series"]]
    period=first["observation_period"]
    desc=(f"{label}: «{first['label']}» {dir_it} nella sua ultima "
          f"osservazione ({period}).")
    if len(evidence)>1:
        second=evidence[1]
        status={"SALITA":"in rialzo","DISCESA":"in calo",
                "STABILE":"stabile",
                "NO_CONTIGUOUS_COMPARISON":"non confrontabile"}[
                    second["direction_of_reported_series"]]
        desc+=f" «{second['label']}» è {status} ({second['observation_period']})."
    if all(x["status"]=="RECENT_PERIOD_NOT_RELEASE_VERIFIED" for x in evidence):
        desc+=(" Periodi relativamente recenti, ma mancano ancora timestamp "
               "di prima pubblicazione e verifica dell'eventuale revisione.")
    else:
        desc+=(" Sono dati di periodi non sufficientemente recenti per "
               "confermare da soli l'evoluzione attuale.")
    return desc

def build(*,today,root=v1.ROOT):
    base=v1.build(today=today,root=root)
    rel=MACRO_SERIES
    raw=(root/rel).read_bytes()
    series=json.loads(raw)
    gate(tuple(base["countries"])==v1.FX and
         set(series)==set(v1.FX) and set(SELECTORS)==set(v1.FX),
         "G8 evidence/source mismatch")
    updated={}
    missing=[]
    stale=[]
    for c in v1.FX:
        original=base["countries"][c]
        index={r["id"]:r for r in series[c]}
        gate(len(index)==len(series[c]),c+" duplicate series IDs")
        found={}
        for role in ("firms","labor","households"):
            specs=SELECTORS[c][role]
            gate(len(specs)==len(set(specs)),c+" duplicate selected series")
            out=[]
            for ident in specs:
                gate(ident in index,c+" missing required source "+ident)
                out.append(evidence_row(index[ident],today=today))
            found[role]=out
            if not out:
                missing.append(c+"."+role)
            if out and all(x["status"]!="RECENT_PERIOD_NOT_RELEASE_VERIFIED" for x in out):
                stale.append(c+"."+role)
        note=("La direzione delle serie osservate è una descrizione, non una prova "
              "del canale imprese → salari → consumi. Le date sono periodi "
              "economici, NON date di disponibilità al desk; le serie sono "
              "revisionate e non certificate come prime pubblicazioni.")
        narrative=[
            original["narrative_it"][0],
            original["narrative_it"][1],
            describe_role("firms",found["firms"]),
            describe_role("labor",found["labor"]),
            describe_role("households",found["households"]),
            original["central_bank_conditional_reaction"],
            original["narrative_it"][4], # rates/pricing
            original["narrative_it"][5], # counter, catalysts
            note,
        ]
        updated[c]={
          **original,
          "economic_transmission_observations":found,
          "economic_evidence_summary":{
              "missing_roles":[k for k,v in found.items() if not v],
              "dated_roles":[k for k,v in found.items() if v and not all(
                  x["status"]=="RECENT_PERIOD_NOT_RELEASE_VERIFIED" for x in v)],
              "source_release_times_verified":False,
              "causal_chain_confirmed":False,
              "human_review_required":True,
          },
          "economic_transmission_narrative_it":narrative,
          "human_review_status":"UNREVIEWED_RESEARCH_PILOT",
          "safe_for_reports":False,
          "safe_for_site":False,
        }
    return {
        "schema":SCHEMA,
        "run_date_rome":today.isoformat(),
        "base_countrybook_schema":base["schema"],
        "macro_as_of":base["macro_observation_snapshot_as_of"],
        "source_shas":{**base["source_sha256"],"macro_series":hashlib.sha256(raw).hexdigest()},
        "source_paths":{**base["source_files"],"macro_series":rel},
        "coverage":{
            "countries":8,"roles_possible":24,
            "roles_missing_direct_observation":sorted(missing),
            "roles_without_all_recent_periods":sorted(stale),
            "causal_channels_proven":0,"new_fx_signals":0,
        },
        "no_new_fx_ranking":True,"no_live_site_publication":True,
        "no_report_promotion":True,"publication_timestamps_verified":False,
        "source_revision_vintage_verified":False,
        "countries":updated,
    }

def markdown(book):
    lines=["# Country Book G8 — evidenze economiche e limiti V2",
           f"**Analisi:** {book['run_date_rome']} · **Macro:** {book['macro_as_of']} "
           "· **RICERCA NON PUBBLICATA SUL SITO**","",
           "Le serie qui riportate sono osservazioni economiche revisionate. "
           "Le loro date non sono necessariamente quelle di pubblicazione. "
           "Non si ricavano segnali Forex, probabilità di decisioni o nessi causali certi.",""]
    for c in v1.FX:
        b=book["countries"][c]
        lines.extend([f"## {c} — {b['country']} · {b['bank']}",""])
        lines.extend([s+"\n" for s in b["economic_transmission_narrative_it"]])
        lines.extend(["","**Da aggiornare o verificare:** "+
                      ", ".join(b["economic_evidence_summary"]["missing_roles"]+
                                b["economic_evidence_summary"]["dated_roles"]) or
                      "Nessun ruolo mancante; mancano comunque le date effettive di pubblicazione.",
                      "","---",""])
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--json-out",type=Path)
    parser.add_argument("--md-out",type=Path)
    args=parser.parse_args()
    book=build(today=datetime.now(ZoneInfo("Europe/Rome")).date())
    for path,body in ((args.json_out,json.dumps(book,ensure_ascii=False,indent=2)+"\n"),
                      (args.md_out,markdown(book))):
        if path:
            v1.require(path.resolve().is_relative_to(Path("/tmp")),
                       "research output must stay in /tmp, never site or live_data")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(body,encoding="utf-8")
    print(json.dumps({
      "schema":book["schema"],
      "countries":list(book["countries"]),
      "missing_roles":book["coverage"]["roles_missing_direct_observation"],
      "dated_roles":book["coverage"]["roles_without_all_recent_periods"],
      "direct_channels_proven":0,"fx_signals":0,
    },ensure_ascii=False))
    for c in v1.FX:
        row=book["countries"][c]
        print(c+" | "+row["economic_transmission_narrative_it"][0])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
