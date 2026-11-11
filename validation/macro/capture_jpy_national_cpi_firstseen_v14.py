#!/usr/bin/env python3
"""Japan October 2026 national CPI: exact issuer first-runner-seen snapshot.

Read only the Statistics Bureau's NATIONAL 2025-base October *published*
three-component summary. Never confuse Tokyo advance CPI with Japan national,
headline with ex-fresh-food core, or this runner clock with original issuer PIT.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.capture_official_postrelease_actuals_v1 import Pending, PlainText, retrieve
from validation.macro.freeze_pre_release_consensus_v1 import digest, utc_iso, utc_text

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"validation/macro/MACRO_JPY_NATIONAL_CPI_FIRST_SEEN_V14.jsonl"
URL="https://www.stat.go.jp/data/cpi/sokuhou/tsuki/index-z.html"
HOST="www.stat.go.jp"
SCHEMA="GMFQ_JPY_OCT_2026_NATIONAL_CPI_OFFICIAL_FIRST_OBSERVED_V14"
QUALITY="STATISTICS_BUREAU_JAPAN_NATIONAL_CPI_RUNNER_FIRST_SEEN_NOT_ISSUER_PIT"
EVENT="JPY|2026-11-20|INFLATION|Japan Consumer Price Index"
PUBLISHER="Statistics Bureau of Japan"
RELEASE=datetime(2026,11,20,8,30,tzinfo=ZoneInfo("Asia/Tokyo")).astimezone(timezone.utc)
WINDOW=timedelta(days=7)
METRICS=(
    ("JP_CPI_OCT26_HEADLINE_YOY_NSA","総合指数"),
    ("JP_CPI_OCT26_CORE_EX_FRESH_FOOD_YOY_NSA","生鮮食品を除く総合指数"),
    ("JP_CPI_OCT26_EX_FRESH_ENERGY_YOY_NSA","生鮮食品及びエネルギーを除く総合指数"),
)

def need(ok,reason):
    if not ok: raise ValueError("JPY_CPI_ISSUER_V14_REJECTED: "+reason)

def parse_japan(raw):
    need(type(raw) is bytes and 50<len(raw)<=2_000_000,"source HTML invalid")
    p=PlainText()
    p.feed(raw.decode("utf-8",errors="replace"))
    s=unicodedata.normalize("NFKC",p.value()).replace("％","%")
    # This path is a rolling latest month, so old September and Tokyo preview
    # are common even after the scheduled October publication time.
    header=re.search(
        r"2025年基準.{0,35}消費者物価指数.{0,40}全国.{0,50}"
        r"2026年.{0,25}10月分.{0,35}2026年11月20日公表",s,re.S)
    if header is None:
        raise Pending("JAPAN_NATIONAL_OCT_2026_PUBLISHED_HEADER_NOT_PRESENT")
    tail=s[header.end():]
    points=[re.search(r"\(\s*"+str(i)+r"\s*\)",tail) for i in (1,2,3)]
    if not all(points) or not points[0].start()<points[1].start()<points[2].start():
        raise Pending("JAPAN_THREE_NATIONAL_CPI_PRIMARY_POINTS_NOT_PRESENT")
    result={}
    for i,(metric,expected) in enumerate(METRICS):
        start=points[i].end()
        stop=points[i+1].start() if i<2 else min(len(tail),start+500)
        segment=tail[start:stop]
        if expected not in segment[:160]:
            raise Pending("JAPAN_NATIONAL_COMPONENT_WRONG_OR_MISSING_"+metric)
        hits=re.findall(re.escape(expected)+r".{0,145}?前年同月比は\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*の\s*(上昇|下落|低下)",segment)
        if len(hits)!=1:
            raise Pending("JAPAN_NATIONAL_COMPONENT_RATE_AMBIGUOUS_"+metric)
        number,sign=hits[0]
        val=float(number)*(-1 if sign in ("下落","低下") else 1)
        need(math.isfinite(val) and -20<val<35,"component out of CPI reasonable bounds")
        result[metric]=val
    need(len(result)==3,"three components required")
    return result

def validate(rows):
    need(isinstance(rows,list) and len(rows)<=1,"duplicate release archive")
    for row in rows:
        need(isinstance(row,dict) and row.get("schema")==SCHEMA,"schema")
        need(row.get("previous_record_sha256")=="GENESIS" and
             row.get("record_sha256")==digest({k:v for k,v in row.items()
                                               if k!="record_sha256"}),"hash")
        need(row.get("event_key")==EVENT and row.get("source_url")==URL and
             row.get("currency")=="JPY" and row.get("publisher")==PUBLISHER and
             row.get("reference_period")=="2026-10" and
             row.get("base_year")==2025 and row.get("unit")=="PCT_YOY_NSA" and
             row.get("official_scheduled_release_utc")==utc_text(RELEASE),"identity")
        when=utc_iso(row.get("observed_at_utc"))
        need(RELEASE<=when<=RELEASE+WINDOW,"observation outside release window")
        values=row.get("metrics_percent")
        need(isinstance(values,dict) and set(values)=={m for m,_ in METRICS},
             "missing or unexpected Japan CPI measures")
        need(all(type(v) in (int,float) and math.isfinite(v) and -20<v<35
                 for v in values.values()),"invalid rates")
        need(isinstance(row.get("source_html_sha256"),str) and
             re.fullmatch(r"[0-9a-f]{64}",row["source_html_sha256"]),
             "official page fingerprint missing")
        need(row.get("quality")==QUALITY and
             row.get("first_publisher_delivery_PIT_verified") is False and
             row.get("survey_consensus_percent") is None and
             row.get("certified_surprise_pp") is None and
             row.get("market_reaction") is None and
             row.get("FX_signal") is None and
             row.get("eligible_for_Core_Beta_Forward") is False,
             "cannot promote publisher timing, consensus or FX causality")
    return bool(rows)

def capture(old,now,fetch=retrieve,observed_clock=None):
    need(isinstance(now,datetime) and now.tzinfo is not None and
         now.utcoffset() is not None,"aware clock required")
    now=now.astimezone(timezone.utc)
    validate(old)
    if old:
        return old,{"state":"ALREADY_ARCHIVED_NO_HTTP","new_actuals":0,"total_actuals":1,
                    "status":"JPY_NATIONAL_CPI_ISSUER_FIRST_OBSERVED_V14"}
    if now<RELEASE:
        state="BEFORE_RELEASE_NO_HTTP"
    elif now>RELEASE+WINDOW:
        state="OUTSIDE_FIRST_OBSERVATION_WINDOW_NO_HTTP"
    else:
        try:
            raw,final=fetch(URL,HOST)
            need(final==URL,"publisher endpoint changed")
            measures=parse_japan(raw)
        except (Pending,OSError,TimeoutError,UnicodeError):
            state="OFFICIAL_NATIONAL_OCT_CPI_NOT_YET_OBSERVED"
        else:
            seen=observed_clock() if observed_clock else now
            need(isinstance(seen,datetime) and seen.tzinfo is not None and
                 seen.utcoffset() is not None,"issuer observation timestamp missing zone")
            seen=seen.astimezone(timezone.utc)
            need(now<=seen<=RELEASE+WINDOW,"observation before poll or too late")
            row={
                "schema":SCHEMA,"event_key":EVENT,"currency":"JPY",
                "publisher":PUBLISHER,"source_url":URL,
                "reference_period":"2026-10","base_year":2025,"unit":"PCT_YOY_NSA",
                "metrics_percent":measures,
                "source_html_sha256":hashlib.sha256(raw).hexdigest(),
                "official_scheduled_release_utc":utc_text(RELEASE),
                "observed_at_utc":utc_text(seen),"quality":QUALITY,
                "first_publisher_delivery_PIT_verified":False,
                "survey_consensus_percent":None,"certified_surprise_pp":None,
                "market_reaction":None,"FX_signal":None,
                "eligible_for_Core_Beta_Forward":False,
                "previous_record_sha256":"GENESIS",
            }
            row["record_sha256"]=digest(row)
            validate([row])
            return [row],{"state":"OFFICIAL_OCT_NATIONAL_CPI_THREE_COMPONENTS_FIRST_OBSERVED",
                          "new_actuals":1,"total_actuals":1,
                          "status":"JPY_NATIONAL_CPI_ISSUER_FIRST_OBSERVED_V14"}
    return [],{"state":state,"new_actuals":0,"total_actuals":0,
               "status":"JPY_NATIONAL_CPI_ISSUER_FIRST_OBSERVED_V14"}

def run(actual_path=OUT,now=None,fetch=retrieve,observed_clock=None):
    now=now or datetime.now(timezone.utc)
    path=Path(actual_path)
    prior=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
           if line.strip()] if path.is_file() else []
    after,report=capture(prior,now,fetch,
         observed_clock=observed_clock or (lambda:datetime.now(timezone.utc)))
    if len(after)>len(prior):
        with path.open("a",encoding="utf-8") as f:
            for row in after[len(prior):]:
                f.write(json.dumps(row,sort_keys=True,ensure_ascii=False,
                                   separators=(",",":"))+"\n")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--actuals",type=Path,default=OUT)
    args=p.parse_args()
    print(json.dumps(run(args.actuals),sort_keys=True,ensure_ascii=False))

if __name__=="__main__":
    main()
