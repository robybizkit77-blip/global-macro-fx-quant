#!/usr/bin/env python3
"""Issuer actuals vs SHA-locked prior secondary consensus. No market causality.

After official scheduled release: only BLS ECI Q3 SA civilian compensation
and Statistics Canada August m/m all-industry real GDP. First observed
publisher HTML is recorded with SHA-256, but NOT proven original-release PIT.
Unmatched sources => absent actual, never 0. Appends independently of forecast.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import urllib.request
from datetime import datetime,timezone,timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from validation.macro.freeze_pre_release_consensus_v1 import (
    LEDGER,ROOT,digest,read_existing,utc_iso,utc_text,validate_existing
)
OUT=ROOT/"validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl"
SCHEMA="GMFQ_OFFICIAL_MACRO_ACTUAL_FIRST_SEEN_POST_RELEASE_V1"
ECI="USD|2026-10-30|LABOUR_COST|Employment Cost Index"
GDP="CAD|2026-10-30|GROWTH|Gross domestic product by industry"
TARGETS={
  ECI:{"url":["https://www.bls.gov/news.release/eci.htm"],
       "host":"www.bls.gov","currency":"USD",
       "publisher":"U.S. Bureau of Labor Statistics","period":"2026Q3",
       "unit":"PCT_QOQ_SA_CIVILIAN_TOTAL_COMPENSATION"},
  GDP:{"url":["https://www150.statcan.gc.ca/n1/daily-quotidien/261030/dq261030"+letter+"-eng.htm" for letter in "abcd"],
       "host":"www150.statcan.gc.ca","currency":"CAD",
       "publisher":"Statistics Canada","period":"2026-08",
       "unit":"PCT_MOM_SA_REAL_GDP_ALL_INDUSTRIES"},
}
MAX_BYTES=2_000_000
MAX_CAPTURE_LAG=timedelta(days=14)

class Pending(Exception):pass

def need(condition,reason):
    if not condition:raise ValueError("MACRO_OFFICIAL_ACTUAL_GATE: "+reason)

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.excluded=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.excluded+=1
    def handle_endtag(self,tag):
        if tag in ("script","style") and self.excluded:self.excluded-=1
    def handle_data(self,data):
        if not self.excluded:self.parts.append(data)
    def value(self):
        return re.sub(r"\s+"," ",unescape(" ".join(self.parts))).strip()

def parse_issuer_page(event_key,raw):
    need(event_key in TARGETS,"unknown event")
    need(isinstance(raw,bytes) and 0<len(raw)<=MAX_BYTES,
         "issuer page bytes missing or excessive")
    reader=PlainText();reader.feed(raw.decode("utf-8",errors="replace"))
    text=reader.value()
    if event_key==ECI:
        if not re.search(r"embargoed until.{0,100}8:30 a\.m\.\s*\(ET\)\s*Friday,?\s+October\s+30,?\s+2026",text,re.I):
            raise Pending("ECI_RELEASE_DATE_NOT_OCT30")
        if not re.search(r"EMPLOYMENT COST INDEX\s*[-–—]?\s*SEPTEMBER\s+2026",text,re.I):
            raise Pending("ECI_REFERENCE_PERIOD_NOT_Q3")
        pattern=(r"Compensation costs for civilian workers\s+(increased|decreased)\s+"
                 r"([0-9]+(?:\.[0-9]+)?)\s+percent,?\s+seasonally adjusted,?\s+"
                 r"for the\s+3-month period\s+ending in September\s+2026")
    else:
        if not re.search(r"Gross domestic product by industry,?\s*August\s+2026",text,re.I):
            raise Pending("GDP_REFERENCE_PERIOD_NOT_AUG")
        if not re.search(r"Released:\s*2026-10-30",text,re.I):
            raise Pending("GDP_PUBLICATION_NOT_OCT30")
        pattern=(r"Real gross domestic product\s*\(GDP\)\s+"
                 r"(grew|rose|increased|declined|decreased|fell)\s+"
                 r"([0-9]+(?:\.[0-9]+)?)%\s+in August\b")
    hits=re.findall(pattern,text,re.I)
    if len(hits)!=1:raise Pending("ISSUER_AGGREGATE_SERIES_RATE_NOT_UNAMBIGUOUS")
    verb,value=hits[0]
    actual=float(value)
    need(math.isfinite(actual) and abs(actual)<50,"nonfinite or implausible actual")
    return -actual if verb.lower() in ("decreased","declined","fell") else actual

def retrieve(url,host):
    p=urlsplit(url)
    need(p.scheme=="https" and p.hostname==host
         and not p.username and not p.password and p.port in (None,443),
         "unapproved official source URL")
    req=urllib.request.Request(url,headers={
        "User-Agent":"GMFQ-official-macro-release-audit/1.0",
        "Accept":"text/html,application/xhtml+xml"
    })
    with urllib.request.urlopen(req,timeout=12) as response:
        final=response.geturl()
        p=urlsplit(final)
        need(p.scheme=="https" and p.hostname==host,"unapproved official redirect")
        if response.status!=200 or "html" not in response.headers.get("Content-Type","").lower():
            raise Pending("ISSUER_NO_HTML_200")
        data=response.read(MAX_BYTES+1)
        if not data or len(data)>MAX_BYTES:raise Pending("ISSUER_HTML_INVALID_SIZE")
        return data,final

def validate_actual_log(rows,forecasts):
    validate_existing(forecasts)
    frozen={x["event_key"]:x for x in forecasts}
    prev="GENESIS";seen=set()
    for row in rows:
        need(isinstance(row,dict) and row.get("schema")==SCHEMA,"actual schema")
        content={k:v for k,v in row.items() if k!="record_sha256"}
        need(row.get("record_sha256")==digest(content)
             and row.get("previous_record_sha256")==prev,"actual chain tamper")
        k=row.get("event_key")
        need(k in frozen and k in TARGETS and k not in seen,"actual duplicate/unfrozen event")
        seen.add(k);t=TARGETS[k];f=frozen[k]
        when=utc_iso(row.get("captured_at_utc"))
        published=utc_iso(f["official_scheduled_release_utc"])
        need(published<=when<=published+MAX_CAPTURE_LAG,"actual before release or too late")
        need(row.get("source_url") in t["url"] and
             row.get("publisher")==t["publisher"] and
             row.get("reference_period")==t["period"] and
             row.get("unit")==t["unit"],"wrong issuer series or unit")
        need(row.get("forecast_receipt_sha256")==f["record_sha256"],
             "unmatched first frozen consensus")
        actual=row.get("actual_percent")
        need(type(actual) in (int,float) and math.isfinite(actual) and abs(actual)<50,
             "invalid actual number")
        need(row.get("actual_minus_frozen_consensus_pp")==
             round(actual-f["consensus_value_percent"],6),
             "relative deviation not based on frozen consensus")
        need(isinstance(row.get("source_html_sha256"),str) and
             re.fullmatch(r"[a-f0-9]{64}",row["source_html_sha256"]),
             "missing official raw source fingerprint")
        need(row.get("quality")=="OFFICIAL_PAGE_FIRST_OBSERVATION_NOT_FIRST_RELEASE_PIT"
             and row.get("publisher_first_release_PIT_verified") is False
             and row.get("fx_reaction") is None
             and row.get("CB_Want_Can") is None
             and row.get("eligible_for_Core_Beta_Forward") is False,
             "actual cannot imply policy/FX causality")
        prev=row["record_sha256"]
    return prev,seen

def capture(forecasts,old,now,fetch=retrieve):
    previous,seen=validate_actual_log(old,forecasts)
    need(isinstance(now,datetime) and now.tzinfo is not None
         and now.utcoffset() is not None,"capture clock must be offset-aware")
    now=now.astimezone(timezone.utc)
    added=[];states={}
    for row in forecasts:
        key=row["event_key"]
        if key not in TARGETS:continue
        if key in seen:
            states[key]="ALREADY_FROZEN_OFFICIAL_FIRST_OBSERVATION";continue
        scheduled=utc_iso(row["official_scheduled_release_utc"])
        if now<scheduled:
            states[key]="BEFORE_RELEASE_NO_FETCH";continue
        if now>scheduled+MAX_CAPTURE_LAG:
            states[key]="TOO_LATE_FOR_FIRST_OBSERVATION_REVIEW_REQUIRED";continue
        target=TARGETS[key]
        states[key]="ISSUER_NOT_YET_OBSERVED"
        for url in target["url"]:
            try:
                body,final=fetch(url,target["host"])
                need(final==url,"issuer response moved from source URL")
                observed=parse_issuer_page(key,body)
            except (Pending,TimeoutError,OSError,UnicodeError):
                continue
            # Fail closed for invariant violations; only availability
            # and page-series mismatch may be treated as "still pending".
            record={
                "schema":SCHEMA,"event_key":key,"currency":target["currency"],
                "publisher":target["publisher"],"source_url":url,
                "source_html_sha256":hashlib.sha256(body).hexdigest(),
                "captured_at_utc":utc_text(now),
                "official_scheduled_release_utc":utc_text(scheduled),
                "first_page_observation_not_publisher_delivery_time":True,
                "reference_period":target["period"],"unit":target["unit"],
                "actual_percent":observed,
                "forecast_receipt_sha256":row["record_sha256"],
                "frozen_secondary_consensus_percent":row["consensus_value_percent"],
                "actual_minus_frozen_consensus_pp":
                    round(observed-row["consensus_value_percent"],6),
                "quality":"OFFICIAL_PAGE_FIRST_OBSERVATION_NOT_FIRST_RELEASE_PIT",
                "publisher_first_release_PIT_verified":False,
                "fx_reaction":None,"CB_Want_Can":None,
                "eligible_for_Core_Beta_Forward":False,
                "previous_record_sha256":previous,
            }
            record["record_sha256"]=digest(record)
            added.append(record);previous=record["record_sha256"]
            states[key]="OFFICIAL_ACTUAL_CAPTURED_DESCRIPTIVE_ONLY";break
    new=old+added
    validate_actual_log(new,forecasts)
    return new,{
        "status":"OFFICIAL_ACTUAL_POST_RELEASE_FIRST_CAPTURE_MONITOR",
        "tracked_frozen_events":sum(x["event_key"] in TARGETS for x in forecasts),
        "new_actuals":len(added),"total_actuals":len(new),
        "states":states,
        "actual_first_release_PIT_verified":False,
        "fx_or_rates_causality_verified":False,
        "Core_changed":False,"Beta_or_Forward_changed":False,
    }

def run(forecast_path=LEDGER,actual_path=OUT,now=None):
    if now is None:now=datetime.now(timezone.utc)
    prior=read_existing(forecast_path)
    old=read_existing(actual_path)
    new,receipt=capture(prior,old,now)
    if len(new)>len(old):
        with actual_path.open("a",encoding="utf-8") as handle:
            for row in new[len(old):]:
                handle.write(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n")
    return receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--forecast",type=Path,default=LEDGER)
    p.add_argument("--actuals",type=Path,default=OUT)
    a=p.parse_args()
    print(json.dumps(run(a.forecast,a.actuals),ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
