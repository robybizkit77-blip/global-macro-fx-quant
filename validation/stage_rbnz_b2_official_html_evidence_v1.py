#!/usr/bin/env python3
"""Verify independently reviewable RBNZ B2 official HTML-table evidence, stage only.

The rows were read from RBNZ's published public table, NOT from a machine-readable
file fetched by this GitHub runner. They cannot be auto-promoted.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math
from pathlib import Path
from build_chf_nzd_official_rates_staging_v1 import BASE, make_candidate
SOURCE="https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates"
EVIDENCE=Path(__file__).resolve().parent/"fixtures/rbnz_b2_official_table_2026-10-19_review_required.json"

def verify(doc,rates,today=None):
    today=today or dt.datetime.now(dt.timezone.utc).date()
    if doc.get("schema")!="GMFQ_RBNZ_B2_OFFICIAL_HTML_TABLE_EVIDENCE_V1" or doc.get("source_url")!=SOURCE:
        raise ValueError("untrusted official source contract")
    if doc.get("usable_for_automatic_promotion") is not False or "INDEPENDENT_SECOND_REVIEW_REQUIRED" not in doc.get("verification",""):
        raise ValueError("evidence must remain review-required, never automatically approved")
    if "government bond closing yields" not in doc.get("basis","").lower():
        raise ValueError("not the government-bond close basis")
    rows=doc.get("observations")
    if not isinstance(rows,list) or len(rows)<3:
        raise ValueError("insufficient independent source observations")
    dates=set(); result=[]
    for item in rows:
        if set(item)!={"date","2Y","10Y"}:
            raise ValueError("incomplete government-bond source table row")
        day=dt.date.fromisoformat(item["date"])
        if day.isoformat()!=item["date"] or day in dates or day>today:
            raise ValueError("invalid/duplicate/future official date")
        dates.add(day)
        y2,y10=item["2Y"],item["10Y"]
        if any(type(x) not in (float,int) or not math.isfinite(x) or not (0<=x<=18) for x in (y2,y10)):
            raise ValueError("invalid official yield")
        result.append(item)
    if [x["date"] for x in result]!=sorted(x["date"] for x in result):
        raise ValueError("official table dates unordered")
    base=rates["NZD"]
    old=next((x for x in result if x["date"]==base["date"]),None)
    if old is None or abs(old["2Y"]-base["2Y"])>1e-9 or abs(old["10Y"]-base["10Y"])>1e-9:
        raise ValueError("new official HTML-table evidence does not match the existing independently verified NZD anchor")
    if (today-dt.date.fromisoformat(result[-1]["date"])).days>5:
        raise ValueError("new official observation stale")
    return result[-1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,default=EVIDENCE)
    p.add_argument("--rates",type=Path,default=BASE)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--candidate",type=Path,required=True)
    a=p.parse_args()
    root=BASE.parents[2].resolve()
    if any(root in path.resolve().parents or path.resolve()==root for path in (a.receipt,a.candidate)):
        raise SystemExit("staging artifacts MUST be outside the source repository")
    raw=a.evidence.read_bytes()
    doc=json.loads(raw)
    rates=json.loads(a.rates.read_text())
    latest=verify(doc,rates)
    result,receipt=make_candidate(rates,"NZD",latest,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        mode="OFFICIAL_HTML_TABLE_MANUAL_EVIDENCE_INDEPENDENT_SECOND_REVIEW_REQUIRED")
    receipt["evidence_source_url"]=SOURCE
    receipt["evidence_publication_date"]=doc["publication_date"]
    receipt["evidence_verification"]="INDEPENDENT_SECOND_REVIEW_REQUIRED"
    receipt["status"]="OFFICIAL_HTML_TABLE_CANDIDATE_SECOND_REVIEW_REQUIRED" if result else "NO_NEW_OFFICIAL_PAIR"
    assert receipt["eligible_for_automatic_promotion"] is False and receipt["writes_live_data"] is False
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n")
    if result:
        a.candidate.parent.mkdir(parents=True,exist_ok=True)
        a.candidate.write_text(json.dumps(result,separators=(",",":"),ensure_ascii=False)+"\n")
    print(json.dumps(receipt,ensure_ascii=False))
    print("RBNZ_HTML_TABLE_EVIDENCE_STAGING_NO_LIVE_WRITE_PASS")

if __name__=="__main__":main()
