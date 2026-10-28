#!/usr/bin/env python3
"""Operational macro-event market CONTEXT: immutable pre-event dated baselines.

BLS ECI and Canada GDP only, with frozen secondary forecasts. Preserve the
first pre-release *runner-observed daily snapshot* of government 2Y/10Y,
EUR-based official ECB fixing and official native 6M instrument when available.
Do not infer daily fix timestamp, 6M OIS from futures or causal event response.

Post values must be *strictly later than issuer release CALENDAR DATE*:
no source with a daily as_of date on the release day counts as intraday
post-news proof. Comparisons span multiple sessions; no alpha/trade signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime,date,timezone,timedelta
from pathlib import Path

from validation.macro.freeze_pre_release_consensus_v1 import (
    LEDGER,ROOT,digest,read_existing,utc_iso,utc_text,validate_existing,
)
from validation.macro.capture_official_postrelease_actuals_v1 import (
    OUT as ACTUAL_LEDGER, ECI, GDP, TARGETS, validate_actual_log,
)

ANCHORS=ROOT/"validation/macro/MACRO_EVENT_PRE_RELEASE_MARKET_ANCHORS_V1.jsonl"
RATES=ROOT/"live_data/sections/NATIVE_RATES_DATA.json"
OIS=ROOT/"live_data/sections/OIS_DATA.json"
FX=ROOT/"live_data/sections/ECB_G8_PRICE_HISTORY.json"
SCHEMA="GMFQ_MACRO_EVENT_MARKET_PRE_RELEASE_DAILY_ANCHOR_V1"
MONITOR_SCHEMA="GMFQ_MACRO_EVENT_CONTEXT_DAILY_MATCH_V1"
SCOPE=(ECI,GDP)
MAX_BASELINE_AGE_DAYS=9
MAX_POST_DAYS=14

def need(ok,reason):
    if not ok:raise ValueError("MACRO_EVENT_MARKET_CONTEXT_REJECTED: "+reason)

def number(x,field):
    need(type(x) in (float,int) and math.isfinite(x),field+": finite actual number")
    return float(x)

def day(s):
    need(isinstance(s,str) and len(s)==10,"source day ISO expected")
    d=date.fromisoformat(s)
    need(d.isoformat()==s,"date noncanonical")
    return d

def latest_rate(row,tenor,not_after):
    h=row["history2" if tenor=="2Y" else "history10"]
    ds=h["dates"];vs=h["values"]
    need(len(ds)==len(vs),"misaligned government yield history")
    usable=[(d,v) for d,v in zip(ds,vs) if isinstance(d,str) and len(d)==10
            and d<=not_after and d<=row["date"]]
    if not usable:return None
    d,v=max(usable,key=lambda x:x[0])
    need(day(d)<=day(row["date"]),"government history later than source snapshot")
    return {"date":d,"yield_pct":number(v,"government_"+tenor),
            "source":row["source"],"source_quality":row.get("quality"),
            "instrument":"GOVERNMENT_"+tenor+"_NOMINAL_YIELD_NOT_PURE_CB_POLICY"}

def latest_fx(history,ccy,not_after):
    need(history.get("base")=="EUR" and "rows" in history,"ECB EUR-based fixing only")
    eligible=[r for r in history["rows"] if r.get("Date")<=not_after]
    if not eligible:return None
    r=max(eligible,key=lambda x:x["Date"])
    val=number(r[ccy],"ECB official fixing")
    need(val>0,"positive ECB quote")
    return {"date":r["Date"],"pair":"EUR/"+ccy,
            "quote_per_euro":val,"source":"ECB_EUR_BASED_REFERENCE_RATE",
            "intraday_release_window_proven":False}

def ois_anchor(ois,ccy,not_after):
    r=ois.get("currencies",{}).get(ccy,{})
    if r.get("status")!="ACTIVE" or not r.get("source"):return None
    # Never relabel an exchange rate future as a central bank OIS curve.
    pro=r.get("provenance",{})
    observations=pro.get("observations",{})
    if "futures" not in r["source"].lower():return None
    entry=observations.get("current")
    if not isinstance(entry,dict) or not isinstance(entry.get("date"),str):
        return None
    if entry["date"]>not_after or entry["date"]!=r.get("as_of"):
        return None
    rate=number(entry.get("6m"),ccy+" futures 6m")
    need(abs(rate-number(r["horizons"]["6m"]["rate"],"futures rate"))<0.0002,
         "6m future observation not same as published horizon")
    return {"date":entry["date"],"six_month_rate_pct":rate,
        "quality":"OFFICIAL_EXCHANGE_FUTURES_NOT_OIS",
        "source":r["source"],"instrument":r.get("source_meta",{}).get("instrument"),
        "contract_mapping":r.get("source_meta",{}).get("contract_mapping"),
        "horizon_mapping":r.get("source_meta",{}).get("horizon_mapping"),
        "event_window_verified":False}

def validate_anchors(rows,forecasts):
    validate_existing(forecasts)
    frozen={r["event_key"]:r for r in forecasts}
    prev="GENESIS";seen=set()
    for a in rows:
        need(a.get("schema")==SCHEMA and
             a.get("record_sha256")==digest({k:v for k,v in a.items() if k!="record_sha256"}) and
             a.get("previous_record_sha256")==prev,"immutable pre-event market anchor chain")
        key=a.get("event_key")
        need(key in SCOPE and key in frozen and key not in seen,
             "no duplicate / unfrozen event market baseline")
        seen.add(key);f=frozen[key]
        capture=utc_iso(a["captured_at_utc"])
        release=utc_iso(f["official_scheduled_release_utc"])
        need(utc_iso(f["captured_at_utc"])<=capture<release,
             "pre-event market snapshot cannot be dated after release")
        need(a["forecast_sha256"]==f["record_sha256"],
             "market anchor must link original forecast vintage")
        for k in ("2Y","10Y","fx"):
            item=a.get(k)
            need(isinstance(item,dict) and day(item["date"])<release.date()
                 and day(item["date"])<=capture.date(),
                 "only pre-event real dates allowed for market anchor")
        need(a["fx"]["pair"]=="EUR/"+f["currency"]
             and a["currency"]==f["currency"],
             "mismatched EUR fixing currency")
        for label in ("2Y","10Y"):
            number(a[label]["yield_pct"],label)
        number(a["fx"]["quote_per_euro"],"fx")
        if a.get("six_month") is not None:
            v=a["six_month"]
            need(v["quality"]=="OFFICIAL_EXCHANGE_FUTURES_NOT_OIS"
                 and day(v["date"])<release.date()
                 and day(v["date"])<=capture.date()
                 and v["event_window_verified"] is False,
                 "futures anchor not event-window OIS")
            number(v["six_month_rate_pct"],"six month")
        need(a["no_intraday_event_reaction_claim"] is True
             and a["PIT_first_publication_certified"] is False
             and a["eligible_for_D_Beta_Forward"] is False,
             "market baseline must not imply causality")
        prev=a["record_sha256"]
    return prev,seen

def capture_anchors(forecasts,existing,rates,ois,fx,now):
    prev,seen=validate_anchors(existing,forecasts)
    need(now.tzinfo is not None and now.utcoffset() is not None,"aware capture clock")
    now=now.astimezone(timezone.utc)
    additions=[];states={}
    need(set(rates)=={"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"},
         "all eight government rate source rows needed")
    for f in forecasts:
        key=f["event_key"]
        if key not in SCOPE:continue
        if key in seen:
            states[key]="PRE_EVENT_SNAPSHOT_ALREADY_IMMUTABLE";continue
        release=utc_iso(f["official_scheduled_release_utc"])
        if now>=release:
            states[key]="NO_PRE_RELEASE_BACKFILL";continue
        cutoff=min(now.date(),release.date()-timedelta(days=1)).isoformat()
        c=f["currency"]
        r2=latest_rate(rates[c],"2Y",cutoff)
        r10=latest_rate(rates[c],"10Y",cutoff)
        rate_fx=latest_fx(fx,c,cutoff)
        if not r2 or not r10 or not rate_fx:
            states[key]="PRE_EVENT_RATE_OR_FX_SOURCE_ABSENT";continue
        points=[r2,r10,rate_fx]
        futures=ois_anchor(ois,c,cutoff)
        if futures:points.append(futures)
        if any((now.date()-day(v["date"])).days>MAX_BASELINE_AGE_DAYS for v in points):
            states[key]="PRE_EVENT_MARKET_SOURCES_TOO_STALE";continue
        record={
          "schema":SCHEMA,"event_key":key,"currency":c,
          "forecast_sha256":f["record_sha256"],
          "captured_at_utc":utc_text(now),"scheduled_release_utc":utc_text(release),
          "2Y":r2,"10Y":r10,"fx":rate_fx,
          "six_month":futures,
          "six_month_unavailable_if_null_not_synthetic_OIS":True,
          "fixed_early_baseline_not_nearest_market_pre_release":True,
          "no_intraday_event_reaction_claim":True,
          "PIT_first_publication_certified":False,
          "eligible_for_D_Beta_Forward":False,
          "previous_record_sha256":prev,
        }
        record["record_sha256"]=digest(record)
        additions.append(record);seen.add(key);prev=record["record_sha256"]
        states[key]="PRE_EVENT_DAILY_MARKET_CONTEXT_FROZEN"
    new=existing+additions
    validate_anchors(new,forecasts)
    return new,{"status":"MACRO_PRE_RELEASE_MARKET_ANCHOR_CHECK",
        "added_anchors":len(additions),"total_anchors":len(new),
        "states":states,"safe_for_new_FX_signal":False,"writes_live_model":False}

def _post(history,anchor,release_date,valuekey):
    # Do NOT assume release-day official market fixing occurred after news.
    # Require an OBSERVATION DAY strictly after the issuer release DATE.
    return None

def post_rates(row,tenor,release_date,end_limit):
    h=row["history2" if tenor=="2Y" else "history10"]
    dates=h["dates"];values=h["values"]
    need(len(dates)==len(values),"rates history lost date/value alignment")
    opts=[(d,v) for d,v in zip(dates,values)
          if isinstance(d,str) and len(d)==10
          and release_date<d<=end_limit and d<=row["date"]]
    if not opts:return None
    dt,val=min(opts,key=lambda p:p[0])
    return {"date":dt,"yield_pct":number(val,"post yield"),
            "source":row["source"],
            "instrument":"GOVERNMENT_"+tenor+"_NOMINAL_YIELD_NOT_PURE_CB_POLICY"}

def post_fx(history,ccy,release_date,end_limit):
    opts=[r for r in history["rows"] if release_date<r["Date"]<=end_limit]
    if not opts:return None
    x=min(opts,key=lambda r:r["Date"])
    return {"date":x["Date"],"quote_per_euro":number(x[ccy],"ECB fixing"),
            "pair":"EUR/"+ccy,"intraday_release_window_proven":False}

def post_futures(ois,ccy,release_date,end_limit,anchor):
    if anchor is None:return None
    data=ois["currencies"].get(ccy,{})
    v=data.get("provenance",{}).get("observations",{}).get("current")
    if not v or not release_date<v.get("date","")<=end_limit:return None
    if data.get("status")!="ACTIVE" or data.get("source")!=anchor["source"]:
        return None
    sm=data.get("source_meta",{})
    if sm.get("instrument")!=anchor["instrument"] or sm.get("contract_mapping")!=anchor["contract_mapping"] or sm.get("horizon_mapping")!=anchor["horizon_mapping"]:
        return None
    return {"date":v["date"],"six_month_rate_pct":number(v.get("6m"),"post 6m futures"),
        "quality":"OFFICIAL_EXCHANGE_FUTURES_NOT_OIS",
        "source":data["source"],"same_mapping_text_but_contract_identity_not_intraday_proven":True}

def build_context(forecasts,anchors,actuals,rates,ois,fx,now):
    validate_anchors(anchors,forecasts)
    validate_actual_log(actuals,forecasts)
    need(now.tzinfo is not None and now.utcoffset() is not None,"aware now")
    now=now.astimezone(timezone.utc)
    by_anchor={r["event_key"]:r for r in anchors}
    by_actual={r["event_key"]:r for r in actuals}
    output=[]
    for f in forecasts:
        key=f["event_key"]
        if key not in SCOPE:continue
        now_label=utc_iso(f["official_scheduled_release_utc"])
        a=by_anchor.get(key)
        actual=by_actual.get(key)
        item={
          "event_key":key,"currency":f["currency"],
          "scheduled_utc":f["official_scheduled_release_utc"],
          "secondary_consensus_percent":f["consensus_value_percent"],
          "forecast_quality":"SECONDARY_FROZEN_PRE_RELEASE_B",
          "official_actual_percent":actual["actual_percent"] if actual else None,
          "official_actual_source_url":actual["source_url"] if actual else None,
          "official_actual_captured_at_utc":actual["captured_at_utc"] if actual else None,
          "official_actual_source_quality":"FIRST_RUNNER_OBSERVATION_NOT_ISSUER_FIRST_RELEASE_PIT" if actual else None,
          "actual_minus_frozen_consensus_pp":actual["actual_minus_frozen_consensus_pp"] if actual else None,
          "pre_event_reference":a and {
             "captured_at_utc":a["captured_at_utc"],
             "2Y":a["2Y"],"10Y":a["10Y"],"fx":a["fx"],"six_month":a["six_month"]},
          "post_event_daily_comparison":None,
          "OIS_post_event_intraday_comparison":None,
          "CB_Want_Can_from_official_statements":None,
          "event_causality_verified":False,
          "FX_trade_signal":None,
          "eligible_for_Core_Beta_Forward":False,
        }
        if now<now_label:item["state"]="PENDING_OFFICIAL_RELEASE"
        elif actual is None:item["state"]="PENDING_OFFICIAL_ACTUAL_ISSUER_VERIFICATION"
        elif a is None:item["state"]="OFFICIAL_ACTUAL_PRESENT_PRE_EVENT_MARKET_ANCHOR_ABSENT"
        else:
            release_day=now_label.date().isoformat()
            deadline=(now_label.date()+timedelta(days=MAX_POST_DAYS)).isoformat()
            c=f["currency"]
            r2=post_rates(rates[c],"2Y",release_day,deadline)
            r10=post_rates(rates[c],"10Y",release_day,deadline)
            q=post_fx(fx,c,release_day,deadline)
            six=post_futures(ois,c,release_day,deadline,a["six_month"])
            parts={}
            for label,pre,post,k,mul in (
                ("2Y",a["2Y"],r2,"yield_pct",100),
                ("10Y",a["10Y"],r10,"yield_pct",100),
                ("ECB_FX",a["fx"],q,"quote_per_euro",1),
                ("SIX_MONTH",a["six_month"],six,"six_month_rate_pct",100)):
                if pre is None or post is None:
                    parts[label]={"status":"NO_MATCHED_POST_EVENT_SOURCE" if pre else "NO_OFFICIAL_PRERELEASE_SOURCE"}
                elif day(post["date"])>now.date():
                    parts[label]={"status":"POST_SOURCE_DATE_NOT_YET_REACHED"}
                else:
                    delta=(post[k]-pre[k])*mul
                    parts[label]={"status":"DESCRIPTIVE_MULTIDAY_CHANGE_NOT_EVENT_CAUSAL",
                        "from":pre["date"],"to":post["date"],
                        "delta_bp" if label!="ECB_FX" else "eur_base_quote_change_pct":
                            round(delta,5) if label!="ECB_FX" else
                            round((post[k]/pre[k]-1)*100,5),
                        "source_type":post.get("quality","OFFICIAL_GOVERNMENT_OR_ECB_REFERENCE"),
                        "start_is_early_first_seen_not_nearest_prerelease":True,
                        "first_publication_intraday_PIT_certified":False}
            item["post_event_daily_comparison"]=parts
            item["state"]="DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY" if any(
                x["status"]=="DESCRIPTIVE_MULTIDAY_CHANGE_NOT_EVENT_CAUSAL" for x in parts.values()
            ) else "PENDING_POST_RELEASE_DAILY_OBSERVATIONS"
        output.append(item)
    return {"schema":MONITOR_SCHEMA,
       "status":"MACRO_FORECAST_ACTUAL_RATES_FX_SOURCE_CLOCK_MONITOR_NONCAUSAL",
       "events":output,
       "summary":{"events":len(output),
           "awaiting_release":sum(x["state"]=="PENDING_OFFICIAL_RELEASE" for x in output),
           "awaiting_actual":sum(x["state"]=="PENDING_OFFICIAL_ACTUAL_ISSUER_VERIFICATION" for x in output),
           "observed_daily_context":sum(x["state"]=="DAILY_CONTEXT_ONLY_NO_EVENT_CAUSALITY" for x in output),
           "issuer_event_intraday_reactions_certified":0,"FX_signals":0},
       "does_not_write_D_or_change_28_pairs":True,
       "no_causality_without_intraday_same_instrument_pre_post":True}

def run(now=None,freeze=True):
    if now is None:now=datetime.now(timezone.utc)
    load=lambda p:json.loads(p.read_text(encoding="utf-8"))
    forecasts=read_existing(LEDGER)
    old=read_existing(ANCHORS)
    rates=load(RATES);ois=load(OIS);fx=load(FX)
    updated,receipt=capture_anchors(forecasts,old,rates,ois,fx,now)
    if freeze and len(updated)>len(old):
        with ANCHORS.open("a",encoding="utf-8") as out:
            for x in updated[len(old):]:
                out.write(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n")
    context=build_context(forecasts,updated,read_existing(ACTUAL_LEDGER),rates,ois,fx,now)
    return receipt,context

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--no-write",action="store_true")
    p.add_argument("--receipt",type=Path)
    a=p.parse_args()
    if a.receipt:need(a.receipt.resolve().is_relative_to(Path("/tmp")),
                     "only /tmp receipt allowed")
    receipt,context=run(freeze=not a.no_write)
    if a.receipt:a.receipt.write_text(json.dumps({"anchor":receipt,"context":context},
                               ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"anchor":receipt,"context_summary":context["summary"]},
                     sort_keys=True))
if __name__=="__main__":main()
