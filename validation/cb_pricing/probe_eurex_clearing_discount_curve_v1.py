#!/usr/bin/env python3
"""Inspect one official Eurex OTC clearing curve, research only, no schedules.

Retrieve one concrete URL linked by Eurex Clearing on 2026-10-30. Stream
rather than saving the potentially large 50-year CSV. Use only exact
EUR.ESTR.1D type-S discount factors for *unstarted* exact FST3 windows
and observation date 2026-10-29. Source is a clearing model curve from
the Eurex group, NOT an independently executed forward OIS quotation.
No historical OIS accuracy/MAE, no FX or CB pricing promotion, no raw
settlement CSV copied to repo/artifacts.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import argparse, csv, io, itertools, json, math, urllib.request, urllib.error
from pathlib import Path
from validation.cb_pricing.eur_estr_contract_benchmark_bridge_v1 import SOURCE, eur_archive

URL="https://www.eurex.com/resource/blob/5673460/29ad46d1ef7a740197df794a9f33ffc1/data/settlement-prices_20261029.csv"
DATE="2026-10-29"
CURVE="EUR.ESTR.1D"
MAX_ROWS=2_500_000
MAX_TOTAL_CELL_CHARACTERS=180_000_000

def relevant_futures():
    rows=eur_archive(SOURCE.read_text(encoding="utf-8"))["observations"]
    return [r for r in rows if r["quote_date"]==DATE
            and r["accrual_start"]>DATE]

def required_dates(futures):
    return {d for row in futures for d in (row["accrual_start"],row["accrual_end"])}

def fields(row, idx):
    try:
        return (row[idx["datetime"]].strip(),
                row[idx["curve"]].strip(),
                row[idx["maturity"]].strip()[:10],
                row[idx["type"]].strip(),
                row[idx["value"]].strip())
    except (IndexError,KeyError,AttributeError):
        return ("","","","","")

def parse_stream(lines):
    iterator=iter(lines)
    first=next(iterator,"")
    delimiter=";" if first.count(";")>first.count(",") else ","
    stream=csv.reader(itertools.chain([first],iterator),delimiter=delimiter)
    first_fields=next(stream,[])
    norm=["".join(c.lower().split()) for c in first_fields]
    defaults={"datetime":0,"curve":1,"maturity":3,"type":4,"value":5}
    aliases={"datetime":["valuedatetime","valuationdatetime"],
             "curve":["curveid"],"maturity":["maturitydate"],
             "type":["valuetype"],"value":["value"]}
    idx={k:next((norm.index(a) for a in options if a in norm),v)
         for k,(options,v) in ((k,(aliases[k],v)) for k,v in defaults.items())}
    header_recognized="curveid" in norm and "valuetype" in norm
    futures=relevant_futures()
    dates=required_dates(futures)
    factors={}
    timestamps=set()
    counts=Counter()
    types=Counter()
    seen_rows=0
    seen_chars=sum(len(x) for x in first_fields)
    for row in itertools.chain([] if header_recognized else [first_fields],stream):
        seen_rows+=1
        seen_chars+=sum(len(x) for x in row)
        if seen_rows>MAX_ROWS or seen_chars>MAX_TOTAL_CELL_CHARACTERS:
            return report("SOURCE_SCAN_LIMIT_EXCEEDED_NO_RESULTS",counts,types,
                          seen_rows,seen_chars,{},set(),delimiter)
        moment,curve,maturity,typ,raw=fields(row,idx)
        if curve: counts[curve]+=1
        if typ: types[typ]+=1
        if curve!=CURVE or typ!="S" or maturity not in dates:
            continue
        # The clearing date must coincide exactly with the source-day quote.
        if moment[:10]!=DATE:
            continue
        try: value=float(raw)
        except ValueError:continue
        if not math.isfinite(value) or not (0.5<value<1.3):
            continue
        if maturity in factors and abs(factors[maturity]-value)>1e-11:
            return report("CONFLICTING_DUPLICATE_DISCOUNT_FACTORS",counts,types,
                          seen_rows,seen_chars,{},timestamps,delimiter)
        factors[maturity]=value
        timestamps.add(moment)
        if len(factors)==len(dates):
            # Stop as soon as exact needed points were found; partial CSV, not full-history audit.
            break
    status=("EXACT_29OCT_ESTR_DISCOUNT_FACTORS_FOUND" if len(factors)==len(dates) and futures
            else "PARTIAL_ESTR_DISCOUNT_FACTORS_FOUND" if factors and futures
            else "NO_VALID_ESTR_DISCOUNT_FACTORS_FOR_EXACT_WINDOWS")
    return report(status,counts,types,seen_rows,seen_chars,factors,timestamps,delimiter)

def report(status,counts,types,rows,chars,factors,timestamps,delimiter):
    fut=relevant_futures()
    comparable=[]
    if status in ("EXACT_29OCT_ESTR_DISCOUNT_FACTORS_FOUND",
               "PARTIAL_ESTR_DISCOUNT_FACTORS_FOUND") and len(timestamps)==1:
        for x in fut:
            start,end=x["accrual_start"],x["accrual_end"]
            if start not in factors or end not in factors:continue
            period=(date.fromisoformat(end)-date.fromisoformat(start)).days
            s,e=factors[start],factors[end]
            ref=(s/e-1)*360/period*100
            if not (-3<ref<20):continue
            comparable.append({
                "contract":x["contract"],"source_day":DATE,
                "accrual_start":start,"accrual_end":end,
                "eurex_futures_rate_pct":x["rate_pct"],
                "otc_model_estr_forward_from_discount_factors_pct":round(ref,6),
                "futures_minus_clearing_model_bp":round((x["rate_pct"]-ref)*100,4),
                "direct_independent_dealer_quote":False,
                "curve_from_same_eurex_group":True,
                "time_synchronization_with_futures_not_verified":True,
            })
    if status in ("EXACT_29OCT_ESTR_DISCOUNT_FACTORS_FOUND",
               "PARTIAL_ESTR_DISCOUNT_FACTORS_FOUND") and len(timestamps)!=1:
        status="MULTIPLE_VALUATION_TIMESTAMPS_NO_JOIN"
    return {
        "schema":"GMFQ_EUREX_CLEARING_CURVE_PUBLIC_PROBE_V2",
        "status":status,"source_url":URL,"source_date":DATE,
        "expected_curve_id":CURVE,"required_discount_factor_dates":sorted(required_dates(fut)),
        "exact_discount_factor_count":len(factors),
        "processed_rows":rows,"processed_character_count":chars,
        "partial_source_scan_by_design":status!="SOURCE_SCAN_LIMIT_EXCEEDED_NO_RESULTS",
        "valuation_timestamps":sorted(timestamps)[:4],
        "seen_curve_ids":list(counts)[:60],
        "value_type_counts":dict(types),
        "delimiter":delimiter,"matched_futures":comparable,
        "matched_observations_count":len(comparable),
        "independent_OIS_traded_benchmark_count":0,
        "source_is_clearing_model_not_OIS_traded_quote":True,
        "source_group_overlaps_futures_exchange_group":True,
        "no_historical_PIT_certification":True,
        "MAE_vs_true_OIS_bp":None,
        "OIS_forecast_directional_hit_rate":None,
        "eligible_to_modify_live_OIS_or_FX":False,
        "raw_vendor_data_stored":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--once",action="store_true")
    p.add_argument("--out",type=Path,default=Path("/tmp/eurex-clearing-curve-probe.json"))
    a=p.parse_args()
    if not a.out.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("only /tmp research output")
    result={"schema":"GMFQ_EUREX_CLEARING_CURVE_PUBLIC_PROBE_V2",
            "status":"NOT_PROBED","source_url":URL,
            "matched_observations_count":0,"MAE_vs_true_OIS_bp":None,
            "eligible_to_modify_live_OIS_or_FX":False}
    if a.once:
        try:
            req=urllib.request.Request(URL,headers={"User-Agent":"GMFQ-public-research-audit/1.0"})
            with urllib.request.urlopen(req,timeout=25) as response:
                with io.TextIOWrapper(response,encoding="utf-8-sig",newline="") as fh:
                    result=parse_stream(fh)
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError,
                UnicodeError,csv.Error,ValueError) as e:
            result.update(status="PUBLIC_SOURCE_READ_FAILED",
                          error_type=type(e).__name__,
                          status_code=getattr(e,"code",None))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":result["status"],
        "processed_rows":result.get("processed_rows"),
        "needed_factors":result.get("exact_discount_factor_count"),
        "matched":result.get("matched_observations_count"),
        "spreads":result.get("matched_futures"),
        "curve_ids":result.get("seen_curve_ids"),
        "value_types":result.get("value_type_counts")},ensure_ascii=False))

if __name__=="__main__":
    main()
