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
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from validation.macro import build_g8_causal_countrybook_pilot_v1 as v1

SCHEMA = "GMFQ_G8_CAUSAL_EVIDENCE_BRIDGE_RESEARCH_V2"
MACRO_SERIES = "live_data/sections/MACRO_SERIES.json"
SOURCE_RELEASE_CONTEXT = "validation/macro/G8_US_NZ_PUBLISHED_RELEASE_CONTEXT_2026-11-09.json"

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
# Source identity, not an inferred change in the economic cycle.
# AUD household spending is in *current prices*; Japan's selected retail
# index does not attest its real-volume basis from the runtime unit label.
HOUSEHOLD_PRICE_BASIS = {
    "AU_HOUSEHOLD_SPENDING_history_value": (
        "NOMINAL_CURRENT_PRICE",
        "La spesa delle famiglie è misurata in prezzi correnti: un aumento può "
        "riflettere prezzi più alti e non dimostra maggiori volumi reali."
    ),
    "JP_RETAIL_history_value": (
        "REAL_VOLUME_BASIS_NOT_VERIFIED",
        "La fonte riporta un indice delle vendite: senza metadati sul deflatore "
        "non è dimostrato che il movimento rappresenti consumi reali."
    ),
}
# Recency of observation period only. They are descriptive editorial limits,
# NOT official release freshness/service-level guarantees.
RECENT_DAYS = {"M":75, "Q":135, "W":21}
DATED_DAYS = {"M":150, "Q":210, "W":56}
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
    # Fail closed when the AUD nominal-price series changes identity.
    if ident == "AU_HOUSEHOLD_SPENDING_history_value":
        gate("current price" in str(row.get("unit") or "").lower(),
             "AUD household spending is no longer attested as current price")
    price_basis=HOUSEHOLD_PRICE_BASIS.get(ident)
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
        "household_price_volume_basis":(
            price_basis[0] if price_basis else "SOURCE_UNIT_ONLY_NOT_HARMONIZED"),
        "real_consumption_change_certified":False,
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
    if role=="households":
        for record in evidence:
            caveat=HOUSEHOLD_PRICE_BASIS.get(record["id"])
            if caveat:
                desc+=" "+caveat[1]
    if all(x["status"]=="RECENT_PERIOD_NOT_RELEASE_VERIFIED" for x in evidence):
        desc+=(" Periodi relativamente recenti, ma mancano ancora timestamp "
               "di prima pubblicazione e verifica dell'eventuale revisione.")
    else:
        desc+=(" Sono dati di periodi non sufficientemente recenti per "
               "confermare da soli l'evoluzione attuale.")
    return desc

def publisher_release_facts(*,today,root=v1.ROOT):
    """Separate manually verified 9 Nov source facts from revised series.

    NEVER assume the publication date means first available to our desk.
    A backtest/replay before research observation must see no new source facts.
    """
    raw=(root/SOURCE_RELEASE_CONTEXT).read_bytes()
    doc=json.loads(raw)
    gate(doc.get("schema")=="GMFQ_US_NZ_ISSUER_RELEASE_CONTEXT_RESEARCH_V1"
         and doc.get("research_observed_date")=="2026-11-09"
         and doc.get("status")=="MANUAL_PUBLISHER_RELEASE_FACTS_RESEARCH_STATIC_NOT_AUTOMATIC_DATA_REFRESH"
         and doc.get("safe_for_site") is False
         and doc.get("safe_for_reports") is False
         and doc.get("fx_signal") is None,
         "unreviewed release research snapshot")
    gate(set(doc.get("countries",{}))=={"USD","NZD"},
         "publisher release research has wrong currency set")
    domains={"BEA":"www.bea.gov","STATS_NZ":"www.stats.govt.nz",
             "NZIER_PRIVATE_SURVEY_PUBLISHER":"www.nzier.org.nz"}
    expected={"USD":5,"NZD":6}
    for c, block in doc["countries"].items():
        facts=block["release_facts"]
        gate(len(facts)==expected[c] and
             all(isinstance(block[k],str) and len(block[k])>40
                 for k in ("why_this_matters_it","alternative_it")),
             c+" manual release fact count or analysis changed")
        seen=set()
        for x in facts:
            gate(x["id"] not in seen,c+" duplicate publisher statistic")
            seen.add(x["id"])
            url=urlparse(x["source_url"])
            publisher=x["publisher"]
            gate(publisher in domains and url.scheme=="https"
                 and url.netloc==domains[publisher] and
                 not url.username and not url.password,
                 c+" source URL outside named publisher")
            gate((c=="USD" and x["id"].startswith("US_BEA_")
                  and publisher=="BEA") or
                 (c=="NZD" and
                  ((x["id"].startswith("NZ_STATS_") and publisher=="STATS_NZ")
                   or (x["id"].startswith("NZ_NZIER_")
                       and publisher=="NZIER_PRIVATE_SURVEY_PUBLISHER"))),
                 c+" metric identity/publisher conflict")
            gate(date(2026,8,1)<=date.fromisoformat(x["release_date"])
                 <=date(2026,11,9),c+" unverified release date")
            gate(type(x.get("value")) in (int,float) and math.isfinite(x["value"])
                 and abs(x["value"])<1000,c+" invalid statistic")
            if "previous_value" in x:
                gate(type(x["previous_value"]) in (int,float)
                     and math.isfinite(x["previous_value"])
                     and x.get("previous_period"),c+" invalid previous comparator")
            if x["id"].startswith("NZ_NZIER_"):
                gate(x["group"]=="firms_survey"
                     and x["unit"]=="NET_PERCENT_SA"
                     and x["price_basis"]=="NOT_APPLICABLE",
                     "NZIER survey cannot become firm sales or production")
            if "REAL_PCE" in x["id"] or "REAL_DPI" in x["id"]:
                gate(x["price_basis"]=="REAL_DEFLATED",
                     "nominal US observation cannot replace real")
            if "RETAIL_REAL" in x["id"]:
                gate(x["price_basis"]=="REAL_VOLUME",
                     "nominal retail cannot replace real volume")
            if "ECT_" in x["id"]:
                gate(x["price_basis"]=="NOMINAL_CARD_TRANSACTIONS",
                     "electronic card spend cannot replace real retail")
    return {
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "research_observed_date":"2026-11-09",
        "publisher_release_dates_are_first_desktop_observations":False,
        "static_not_auto_refreshed":True,
        "countries":doc["countries"] if today>=date(2026,11,9) else {},
    }


def source_context_story(c,context):
    if context is None:
        return ""
    rows={x["id"]:x for x in context["release_facts"]}
    def value(s):
        return str(rows[s]["value"]).replace(".",",")
    if c=="USD":
        return ("AGGIORNAMENTO BEA, settembre 2026 (pubblicato il 29 ottobre): "
            "spesa NOMINALE +"+value("US_BEA_SEP2026_NOMINAL_PCE_MOM")
            +"% m/m, spesa REALE "+value("US_BEA_SEP2026_REAL_PCE_MOM")
            +"% m/m, reddito disponibile reale "
            +value("US_BEA_SEP2026_REAL_DPI_MOM")+"% m/m, risparmio "
            +value("US_BEA_SEP2026_SAVING_RATE")
            +"%. Nominale e reale non sono quantità intercambiabili. "
            "Dato revisionabile, un mese non prova una tendenza persistente.")
    if c=="NZD":
        return ("AGGIORNAMENTO FONTI: NZIER Q3 2026, fiducia netta "
            +value("NZ_NZIER_QSBO_SEP2026_GENERAL_CONFIDENCE")
            +"% (da +14%); attività domestica effettiva dichiarata saldo "
            +value("NZ_NZIER_QSBO_SEP2026_OWN_DOMESTIC_ACTIVITY")
            +"%: una survey non è produzione/retail misurato. Stats NZ Q2: "
            "retail VOLUMI "+value("NZ_STATS_JUN2026_RETAIL_REAL_QOQ")
            +"% q/q, retail VALORE +"
            +value("NZ_STATS_JUN2026_RETAIL_NOMINAL_QOQ")
            +"% q/q. Q3: transazioni elettroniche retail VALORE +"
            +value("NZ_STATS_SEP2026_ECT_RETAIL_VALUE_QOQ")
            +"% q/q. I pagamenti nominali non provano consumi reali.")
    return ""


def build(*,today,root=v1.ROOT):
    base=v1.build(today=today,root=root)
    rel=MACRO_SERIES
    raw=(root/rel).read_bytes()
    series=json.loads(raw)
    releases=publisher_release_facts(today=today,root=root)
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
        release_entry=releases["countries"].get(c)
        editorial_release=source_context_story(c,release_entry)
        if release_entry and (today-date(2026,11,9)).days>90:
            editorial_release="FONTE ARCHIVIATA, non aggiornamento corrente. "+editorial_release
        note=("La direzione delle serie osservate è una descrizione, non una prova "
              "del canale imprese → salari → consumi. Le date sono periodi "
              "economici, NON date di disponibilità al desk; le serie sono "
              "revisionate e non certificate come prime pubblicazioni.")
        narrative=[
            original["narrative_it"][0],
            original["narrative_it"][1],
            describe_role("firms",found["firms"]),
            describe_role("labor",found["labor"]),
            describe_role("households",found["households"])+
                (" "+editorial_release if editorial_release else ""),
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
          "publisher_release_context":({
              "research_observed_date":releases["research_observed_date"],
              "static_not_auto_refreshed":True,
              "source_facts":release_entry["release_facts"],
              "alternative_it":release_entry["alternative_it"],
              "replaces_historical_source":False,
              "proves_causal_chain":False,
          } if release_entry else None),
          "human_review_status":"UNREVIEWED_RESEARCH_PILOT",
          "safe_for_reports":False,
          "safe_for_site":False,
        }
    return {
        "schema":SCHEMA,
        "run_date_rome":today.isoformat(),
        "base_countrybook_schema":base["schema"],
        "macro_as_of":base["macro_observation_snapshot_as_of"],
        "source_shas":{**base["source_sha256"],"macro_series":hashlib.sha256(raw).hexdigest(),
                      "manual_release_context":releases["source_sha256"]},
        "source_paths":{**base["source_files"],"macro_series":rel,
                       "manual_release_context":SOURCE_RELEASE_CONTEXT},
        "coverage":{
            "countries":8,"roles_possible":24,
            "roles_missing_direct_observation":sorted(missing),
            "roles_without_all_recent_periods":sorted(stale),
            "causal_channels_proven":0,"new_fx_signals":0,
            "supplementary_release_currencies":sorted(releases["countries"]),
            "source_release_context_not_automated":True,
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
