#!/usr/bin/env python3
"""Explicit G8 macro-event metrics: no headline/core or MoM/YoY conflation.

Source title is a *release*. Macro surprise is a *precisely defined series*.
This registry is a prospective semantic matching contract, not a claim
that forecasts, actuals or their first-publication timestamps were observed.
Use the existing official calendar date/time and existing frozen V1 ledger.
"""
from __future__ import annotations

import re
from validation.refresh_macro_consensus_secondary_v1 import norm
from validation.macro.freeze_pre_release_consensus_v1 import exact_event_key

SCHEMA="GMFQ_G8_EXACT_MACRO_METRIC_CONTRACT_RESEARCH_V8"
FX=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
# source: official issuer release title EXACTLY as in verified calendar seed.
# Each metric has distinct economic meaning; no real consensus values here.
# Aliases identify only provider *label*; not certified provider data vintage.
SPECS={
    "USD":(
      ("2026-11-10","INFLATION","Consumer Price Index",(
        ("US_CPI_U_HEADLINE_MOM_SA","CPI-U all items", "PCT_MOM_SA",
         ("cpi m m","consumer price index m m"),"BLS_CURRENT_PAGE_PATTERN_PILOT_NOT_LIVE_CERTIFIED"),
        ("US_CPI_U_HEADLINE_YOY_NSA","CPI-U all items", "PCT_YOY_NSA",
         ("cpi y y","consumer price index y y"),"BLS_CURRENT_PAGE_PATTERN_PILOT_NOT_LIVE_CERTIFIED"),
        ("US_CPI_U_CORE_MOM_SA","CPI-U all items ex food & energy","PCT_MOM_SA",
         ("core cpi m m","core consumer price index m m"),"BLS_CURRENT_PAGE_PATTERN_PILOT_NOT_LIVE_CERTIFIED"),
        ("US_CPI_U_CORE_YOY_NSA","CPI-U all items ex food & energy","PCT_YOY_NSA",
         ("core cpi y y","core consumer price index y y"),"BLS_CURRENT_PAGE_PATTERN_PILOT_NOT_LIVE_CERTIFIED"),
      )),
      ("2026-10-30","LABOUR_COST","Employment Cost Index",(
        ("US_ECI_CIVILIAN_COMP_QOQ_SA","Civilian compensation costs","PCT_QOQ_SA",
         ("employment cost index q q",),"EXISTING_VERIFIED_FIRST_SEEN_ISSUER_PARSER"),
      )),
    ),
    "EUR":(
      ("2026-10-30","GROWTH","Euro area preliminary flash GDP",(
        ("EA_REAL_GDP_FLASH_QOQ_SA","Euro area real flash GDP","PCT_QOQ_SA",
         ("prelim flash gdp q q","gdp flash q q",),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
    ),
    "GBP":(
      ("2026-11-12","GROWTH","GDP first quarterly estimate, UK",(
        ("UK_REAL_GDP_PRELIM_QOQ_SA","UK chain-volume GDP first estimate","PCT_QOQ_SA",
         ("prelim gdp q q","gdp first quarterly estimate q q"),
         "NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
    ),
    "JPY":(
      ("2026-10-23","INFLATION","Japan Consumer Price Index",(
        ("JP_CPI_CORE_EX_FRESH_FOOD_YOY","Japan core excluding fresh food (energy included)","PCT_YOY_NSA",
         ("national core cpi y y","japan core cpi y y"),
         "NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
        ("JP_CPI_HEADLINE_YOY","Japan national headline","PCT_YOY_NSA",
         ("national cpi y y","japan cpi y y"),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
      ("2026-11-20","INFLATION","Japan Consumer Price Index",(
        ("JP_CPI_OCT26_HEADLINE_YOY_NSA","Japan national all-items YoY; 2025-base","PCT_YOY_NSA",
         ("japan national cpi october 2026 y y",),"EXACT_2026_OCT_NATIONAL_ISSUER_CAPTURE_V14"),
        ("JP_CPI_OCT26_CORE_EX_FRESH_FOOD_YOY_NSA",
         "Japan national all-items ex fresh food (ENERGY INCLUDED), YoY; 2025-base","PCT_YOY_NSA",
         ("japan national core cpi october 2026 y y",),"EXACT_2026_OCT_NATIONAL_ISSUER_CAPTURE_V14"),
        ("JP_CPI_OCT26_EX_FRESH_ENERGY_YOY_NSA",
         "Japan national all-items ex fresh food and energy YoY; 2025-base","PCT_YOY_NSA",
         ("japan national ex fresh energy cpi october 2026 y y",),"EXACT_2026_OCT_NATIONAL_ISSUER_CAPTURE_V14"),
      )),
    ),
    "CHF":(
      ("2026-11-16","GROWTH","Swiss GDP flash",(
        ("CH_REAL_GDP_FLASH_QOQ","Switzerland flash real GDP; sports-event adjustment to verify","PCT_QOQ",
         ("swiss gdp q q","gdp q q"),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
    ),
    "CAD":(
      ("2026-10-30","GROWTH","Gross domestic product by industry",(
        ("CA_REAL_GDP_ALL_INDUSTRIES_MOM_SA","Canada real GDP by industry","PCT_MOM_SA",
         ("gdp m m","gross domestic product by industry"),"EXISTING_VERIFIED_FIRST_SEEN_ISSUER_PARSER"),
      )),
      ("2026-10-19","INFLATION","Consumer Price Index",(
        ("CA_CPI_HEADLINE_YOY_NSA","Canadian CPI all-items","PCT_YOY_NSA",
         ("cpi y y","consumer price index y y"),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
    ),
    "AUD":(
      ("2026-10-28","INFLATION","Consumer Price Index, Australia",(
        ("AU_CPI_MONTHLY_INDICATOR_HEADLINE_YOY","Australia monthly CPI indicator (not quarterly trimmed mean)","PCT_YOY",
         ("monthly cpi indicator y y","monthly cpi y y"),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
      ("2026-11-19","LABOUR","Labour Force, Australia",(
        ("AU_UNEMP_RATE_SA","Australia seasonally adjusted unemployment rate (level)","PCT_LEVEL_SA",
         ("unemployment rate","australia unemployment rate"),
         "ISSUER_FIRST_OBSERVED_V12_NOT_PUBLISHER_PIT"),
      )),
    ),
    "NZD":(
      ("2026-10-22","INFLATION","Consumers price index",(
        ("NZ_CPI_HEADLINE_QOQ","NZ CPI quarterly change","PCT_QOQ",
         ("cpi q q","consumers price index q q"),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
        ("NZ_CPI_HEADLINE_YOY","NZ CPI annual change","PCT_YOY",
         ("cpi y y","consumers price index y y"),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
      ("2026-12-17","GROWTH","Gross domestic product",(
        ("NZ_REAL_GDP_QOQ","NZ real GDP quarterly change","PCT_QOQ",
         ("gdp q q","gross domestic product q q"),"NO_CERTIFIED_ISSUER_ACTUAL_PARSER"),
      )),
    ),
}
LABEL_SOURCE_IS_NOT_UNIT_ATTESTATION=True

def verify_contract(official):
    if set(SPECS)!=set(FX):
        raise ValueError("METRIC_V8_REJECTED: missing G8 source contracts")
    idx={exact_event_key(e):e for e in official["events"]}
    seen_ids=set()
    n=0
    releases_missing_from_current_seed=[]
    for ccy,entries in SPECS.items():
        for when,kind,title,metrics in entries:
            key="|".join([ccy,when,kind,title])
            if key not in idx:
                # Official seeds rotate. A historical reference may disappear
                # from current seed without invalidating signed archived data.
                # Never manufacture a replacement release/calendar timestamp.
                releases_missing_from_current_seed.append(key)
            aliases=set()
            for ident,component,unit,labels,parser in metrics:
                if ident in seen_ids or not labels or not component or not unit:
                    raise ValueError("METRIC_V8_REJECTED: invalid/duplicate metric "+ident)
                if not re.fullmatch(r"PCT_(?:(?:MOM|YOY|QOQ)(?:_(?:SA|NSA))?|LEVEL_SA)",unit):
                    raise ValueError("METRIC_V8_REJECTED: unknown rate basis "+unit)
                if not parser:
                    raise ValueError("METRIC_V8_REJECTED: omitted parser status "+ident)
                seen_ids.add(ident)
                for label in labels:
                    if label!=norm(label) or label in aliases:
                        raise ValueError("METRIC_V8_REJECTED: duplicate/unnormalized alias "+label)
                    aliases.add(label)
                n+=1
    return {"currencies":8,"metrics":n,
            "releases":sum(len(x) for x in SPECS.values()),
            "templates_missing_in_current_seed":releases_missing_from_current_seed}

def metrics_for(event):
    ent=SPECS.get(event.get("ccy"),())
    for when,kind,title,metrics in ent:
        if (event.get("date"),event.get("event_type"),event.get("title"))==(
            when,kind,title):
            return [
               {"metric_id":ident,"component":component,"unit":unit,
                "provider_aliases":list(labels),"issuer_parser_status":parser,
                "provider_alias_is_not_official_metric_proof":True}
               for ident,component,unit,labels,parser in metrics
            ]
    return []

def interpret_provider_label(event,provider_title):
    """No broad category matches; unique full normalized token identity only."""
    if not provider_title or not isinstance(provider_title,str):
        return None
    label=norm(provider_title)
    matches=[m for m in metrics_for(event) if label in m["provider_aliases"]]
    if len(matches)>1:
        raise ValueError("METRIC_V8_REJECTED: ambiguous provider label "+label)
    return matches[0] if matches else None

def enumerate_secondary_candidates(official,provider_rows,now=None):
    """Returns metric LABEL hypotheses, never frozen forecasts or actuals.
    
    Existing generic consensus.events is left intact. Consumer presentation
    must NOT treat metric_candidates as frozen, verified, or tradeable.
    """
    from validation.refresh_macro_consensus_secondary_v1 import iso_day
    from validation.macro.freeze_pre_release_consensus_v1 import scheduled
    from datetime import datetime,timezone
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("METRIC_V8_REJECTED: timezone required")
    out=[]
    keys=set()
    for event in official["events"]:
        if not metrics_for(event):
            continue
        tick=scheduled(event)
        if tick is None or tick<=now.astimezone(timezone.utc):
            continue
        for p in provider_rows:
            if p.get("currency")!=event["ccy"] or iso_day(p.get("date"))!=iso_day(event["date"]):
                continue
            match=interpret_provider_label(event,p.get("event"))
            if match is None:
                continue
            key=(exact_event_key(event),match["metric_id"])
            if key in keys:
                # Multiple provider rows with same economic metric are
                # ambiguous; hide all rather than selecting one by rank.
                out=[r for r in out if (r["event_key"],r["metric_id"])!=key]
                continue
            keys.add(key)
            out.append({
                "event_key":key[0],"ccy":event["ccy"],
                "official_date":event["date"],
                "official_release_utc":tick.isoformat().replace("+00:00","Z"),
                "metric_id":key[1],"component":match["component"],
                "unit":match["unit"],"provider_event":p["event"],
                "provider_date":p["date"],
                "forecast":p.get("consensus"),
                "forecast_status":"LABEL_MATCHED_UNFROZEN_SECONDARY_NOT_ACCEPTED",
                "provider_semantic_status":"EXACT_LABEL_NOT_SOURCE_SERIES_CERTIFICATION",
                "issuer_actual_parser_status":match["issuer_parser_status"],
                "eligible_for_existing_v1_freeze":False,
                "eligible_for_macro_surprise":False,
                "eligible_for_fx_signals":False,
            })
    return out
