#!/usr/bin/env python3
"""FX Quant V2 Macro Candidate V1: explicit, deterministic, descriptive 8x3 research.

Not an FX scoring engine. No training labels, policy direction, FX bias,
historical PIT, OOS performance, or canonical D.json recalibration.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"site/control-room-preview/macro-v3-current-evidence.json"
TARGET=ROOT/"site/fx-quant-v2/macro-baseline-candidate-v1.json"
CCYS=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
H={"growth_qoq_pct":"PERCENT_QOQ_NONANNUALIZED_WITHIN_COUNTRY",
   "inflation_change_pp":"YOY_CHANGE_OVER_THREE_OBSERVATION_INTERVALS_PP",
   "unemployment_change_pp":"UNEMP_RATE_CHANGE_OVER_THREE_OBSERVATION_INTERVALS_PP"}
SCHEMA="GMFQ_FXV2_MACRO_CANDIDATE_8X3_DESCRIPTIVE_V1"

def must(b,msg):
    if not b:raise ValueError("FXV2_MACRO_BASELINE_GUARD: "+msg)
def num(x):
    return type(x) in (float,int) and math.isfinite(x)
def day(x):
    must(isinstance(x,str) and len(x)==10,"bad ISO date")
    d=dt.date.fromisoformat(x)
    must(d.isoformat()==x,"noncanonical date")
    return d
def classify(x):
    if x>.05:return "UP"
    if x<-.05:return "DOWN"
    return "FLAT_WITHIN_DESCRIPTIVE_0_05PP"
def build(source:dict,today:dt.date)->dict:
    must(source.get("schema")=="GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1"
         and source.get("status")=="OBSERVED_ECONOMIC_CONTEXT_NOT_FX_SIGNAL"
         and source.get("safe_to_recompute_structural_pair_theses") is False
         and source.get("safe_to_republish_D") is False
         and source.get("eligible_for_trading_or_forward_backtest") is False
         and source.get("historic_PIT_OOS_not_certified") is True
         and source.get("source_observation_periods_not_release_days") is True,
         "macro observed research provenance or permissions changed")
    origin=day(source["generated_europe_rome_day"])
    must(dt.timedelta(days=0)<=today-origin<=dt.timedelta(days=10),
         "source publication date future or too old")
    must(source.get("canonical_D_macro_baseline_as_of")=="2026-09-25",
         "legacy model date drift")
    countries=source.get("countries")
    pairs=source.get("pair_context")
    must(isinstance(countries,dict) and set(countries)==set(CCYS) and
         isinstance(pairs,dict) and len(pairs)==28 and
         source.get("summary",{}).get("economic_dimensions")==24,
         "missing 8 currencies, 24 features or 28 pairs")
    features={}
    for code in CCYS:
        r=countries[code]
        must(r.get("not_a_trade_or_policy_signal") is True and
             r.get("macro_score") is None and r.get("FX_strength") is None,
             code+" old score reintroduced")
        g,l,i=r["growth"],r["labour"],r["inflation"]
        gval=g.get("nonannualized_qoq_descriptive_pct")
        must(num(gval) and -50<gval<50 and
             isinstance(g.get("reference_quarter"),str) and
             g["reference_quarter"][:4].isdigit() and
             g["reference_quarter"][-2:-1]=="Q" and
             g["reference_quarter"][-1:] in "1234" and
             day(g["publisher_release_day"])<=today and
             g["is_growth_strength_score"] is False,
             code+" GDP quarter/units invalid")
        prior=g.get("prior_documented_quarter")
        accel=None
        if isinstance(prior,dict):
            p=prior.get("nonannualized_qoq_descriptive_pct")
            q0,q1=prior.get("reference_quarter"),g["reference_quarter"]
            if (num(p) and prior.get("reported_unit")==g.get("reported_unit")
                and isinstance(q0,str) and len(q0)==6 and len(q1)==6
                and q0[:4].isdigit() and q1[:4].isdigit()
                and q0[4]=="Q" and q1[4]=="Q"
                and q0[5] in "1234" and q1[5] in "1234"
                and (int(q1[:4])*4+int(q1[5]) ==
                     int(q0[:4])*4+int(q0[5])+1)):
                accel=round(gval-p,6)
            else:raise ValueError("FXV2_MACRO_BASELINE_GUARD: incompatible GDP prior "+code)
        rows={"growth_qoq_pct":{
            "value":round(gval,6),"unit":"PERCENT_QOQ_NONANNUALIZED_WITHIN_COUNTRY",
            "period":g["reference_quarter"],"publisher_release_day":g["publisher_release_day"],
            "gdp_acceleration_pp":accel,
            "acceleration_quality":"TWO_CONTIGUOUS_QUARTERS" if accel is not None else "UNAVAILABLE_NO_MATCHED_PRIOR",
            "level_does_not_measure_relative_fx_strength":True
        }}
        for label,row in (("inflation_change_pp",i),("unemployment_change_pp",l)):
            delta=row.get("change_over_three_observation_intervals_pp")
            must(num(delta) and -50<delta<50 and
                 num(row.get("observation_value")) and
                 row.get("observed_history_revised_not_historic_PIT") is True and
                 row.get("observation_period_is_not_release_instant") is True,
                 code+" "+label+" revised series contract invalid")
            period=row.get("observation_period")
            must(isinstance(period,str) and len(period) in (7,6) and
                 period[:4].isdigit() and int(period[:4])<=today.year and
                 (period[4:5]=="-" or period[4:5]=="Q"),
                 code+" "+label+" bad period")
            rows[label]={
                "value":round(delta,6),"level":round(row["observation_value"],6),
                "unit":H[label],"period":period,"period_frequency":"Q" if "Q" in period else "M",
                "intervals":3,"intervals_are_not_fixed_calendar_months":True,
                "direction":classify(delta),
                "interpretation":"unemployment ↑ = labour slack ↑; not FX signal" if label.startswith("unemployment")
                else "inflation YoY ↑ = inflation pressure ↑; not automatic CB repricing",
                "series_id":row["series_id"]
            }
        features[code]=rows
    relative={}
    for name,p in sorted(pairs.items()):
        a,b=p["base"],p["quote"]
        must(a in CCYS and b in CCYS and a!=b and name==a+"/"+b and
             p.get("pair_trade_bias") is None and
             p.get("recalculated_structural_thesis") is False,
             name+" pair source not read-only")
        A,B=features[a],features[b]
        compare={}
        for dim in ("inflation_change_pp","unemployment_change_pp"):
            x,y=A[dim],B[dim]
            aligned=x["period"]==y["period"] and x["period_frequency"]==y["period_frequency"]
            compare[dim]={
                "same_period":aligned,
                "delta_base_minus_quote_pp":round(x["value"]-y["value"],6) if aligned else None,
                "reason":"SAME_OBSERVATION_PERIOD_ONLY_NO_FX_BIAS" if aligned else "PERIOD_MISMATCH_NOT_COMPARABLE"
            }
        gx,gy=A["growth_qoq_pct"],B["growth_qoq_pct"]
        # Comparing raw GDP levels across countries is deliberately avoided.
        ga=gx["gdp_acceleration_pp"];gb=gy["gdp_acceleration_pp"]
        aligned=(ga is not None and gb is not None and gx["period"]==gy["period"])
        compare["growth_acceleration_pp"]={
            "same_quarter_and_historical_depth":aligned,
            "delta_base_minus_quote_pp":round(ga-gb,6) if aligned else None,
            "reason":"WITHIN_COUNTRY_ACCELERATIONS_SAME_QUARTER" if aligned else "NO_COMPARABLE_TWO_QUARTER_DEPTH"
        }
        relative[name]={
            "base":a,"quote":b,"contrasts":compare,
            "macro_fx_signal":None,"expected_return":None,"relative_strength_score":None,
            "eligible_for_core":False
        }
    payload={
       "schema":SCHEMA,"as_of_research":origin.isoformat(),
       "published_source_lineage":"MACRO_V3_OBSERVED_REVISED_NOT_PIT",
       "formula_version":"V1_FIXED_NO_CALIBRATED_WEIGHTS",
       "legacy_macro_as_of":"2026-09-25",
       "axes":H,"features":features,"pairs":relative,
       "summary":{
           "currencies":8,"features":24,"pairs":28,
           "gdp_accelerations_calculable":sum(
               z["growth_qoq_pct"]["gdp_acceleration_pp"] is not None
               for z in features.values()),
           "pair_gdp_acceleration_contrasts":sum(
               z["contrasts"]["growth_acceleration_pp"]["same_quarter_and_historical_depth"]
               for z in relative.values()),
           "estimated_macro_scores":0,"trading_signals_generated":0
       },
       "limitations":[
         "Growth QoQ latest readings are descriptive within-country, not cross-country FX strength.",
         "Inflation and unemployment changes span three observation intervals; monthly and quarterly histories are not synchronized automatically.",
         "GDP acceleration requires two adjacent published quarters with compatible units; missing values remain null, not zero.",
         "History is revised observational, not point-in-time releases. No fitted weights, 8-country scale standardization, OOS statistics or FX return calibration.",
         "No changes to D.json, old 24 Macro score values, Core 28 pair state, backtests or policy OIS."
       ],
       "eligible_for_live_fx_signals":False,
       "eligible_for_backtests":False,
       "eligible_for_automatic_core_rebase":False,
       "canonical_fx_core_untouched":True
    }
    # The content receipt is stable for same input even if the workflow ran today.
    payload["source_content_sha256"]=hashlib.sha256(
       json.dumps(source,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return payload

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,default=SOURCE)
    parser.add_argument("--output",type=Path,default=TARGET)
    parser.add_argument("--as-of",type=dt.date.fromisoformat,
        default=dt.datetime.now(ZoneInfo("Europe/Rome")).date())
    a=parser.parse_args()
    source=json.loads(a.input.read_text(encoding="utf-8"))
    output=build(source,a.as_of)
    if a.output.exists():
        before=json.loads(a.output.read_text(encoding="utf-8"))
        if before==output:
            print("FXV2_MACRO_CANDIDATE_UNCHANGED_SOURCE; no synthetic date update")
            return
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("FXV2_MACRO_CANDIDATE_V1_RESEARCH_ONLY",
      json.dumps(output["summary"],sort_keys=True))

if __name__=="__main__":main()
