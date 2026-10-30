#!/usr/bin/env python3
"""One-off public Eurex Clearing OTC curves file probe, no trading promotion.

Fetch ONLY a concrete URL obtained from the Eurex Clearing "Settlement Prices"
Download link, never synthesize dates/URLs or retry/scrape a history.
Inspect CSV format, curve IDs, value types and maturity spans; do not
redistribute the underlying settlement data or manufacture a matched OIS
accuracy claim from zero/forward curves of ambiguous instrument type.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, io, json, re, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlparse

URL="https://www.eurex.com/resource/blob/5673460/29ad46d1ef7a740197df794a9f33ffc1/data/settlement-prices_20261029.csv"
MAX_BYTES=15_000_000

def audit_bytes(raw:bytes):
    if len(raw)>MAX_BYTES: raise ValueError("too many bytes")
    txt=raw.decode("utf-8-sig")
    sample=txt[:4000]
    try: sep=csv.Sniffer().sniff(sample,delimiters=",;\t|").delimiter
    except csv.Error: sep=","
    records=list(csv.reader(io.StringIO(txt),delimiter=sep))
    hdr=records[0] if records else []
    unique=collections.Counter()
    values=collections.Counter()
    samples=[]
    for r in records[1:]:
        if len(r)<2: continue
        if len(r)>=6 and len(hdr)>=6:
            header_map={re.sub(r"\s+","",x.lower()):i for i,x in enumerate(hdr)}
            ci=next((header_map[x] for x in ("curveid","curve") if x in header_map),1)
            vi=next((header_map[x] for x in ("valuetype","type") if x in header_map),4)
        else: ci,vi=1,4
        if len(r)>ci: unique[r[ci]]+=1
        if len(r)>vi: values[r[vi]]+=1
        if len(samples)<2: samples.append([x[:80] for x in r[:6]])
    return {
        "schema":"GMFQ_EUREX_CLEARING_CURVE_PUBLIC_PROBE_V1",
        "official_download_url":URL,
        "source_documentation":"https://www.eurex.com/ec-en/clear/eurex-otc-clear/settlement-prices",
        "quote_expected_date":"2026-10-29",
        "raw_file_sha256":hashlib.sha256(raw).hexdigest(),
        "raw_rows":max(len(records)-1,0),
        "bytes":len(raw),
        "delimiter":sep,
        "header_fields":hdr[:15],
        "sample_fields":samples,
        "curve_id_counts":dict(unique.most_common(60)),
        "value_type_counts":dict(values),
        "same_eurex_group_independence_caveat":True,
        "official_OIS_quote_assigned":False,
        "OIS_error_MAE":None,
        "eligible_for_live_fx":False,
        "raw_file_persisted":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--once",action="store_true")
    p.add_argument("--out",type=Path,default=Path("/tmp/eurex-clearing-curve-probe.json"))
    args=p.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("out must be research /tmp")
    result={"schema":"GMFQ_EUREX_CLEARING_CURVE_PUBLIC_PROBE_V1","status":"NOT_PROBED",
            "official_download_url":URL,"OIS_error_MAE":None,"eligible_for_live_fx":False}
    if args.once:
        try:
            request=urllib.request.Request(URL,headers={"User-Agent":"GMFQ-source-audit/1.0"})
            with urllib.request.urlopen(request,timeout=18) as f:
                content_type=f.headers.get("Content-Type","")
                raw=f.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:
                result.update(status="SOURCE_TOO_LARGE_OR_NONCSV")
            else:
                result=audit_bytes(raw)
                result.update(status="PUBLIC_CURVE_CSV_RETRIEVED",content_type=content_type)
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError,
                UnicodeError,csv.Error,ValueError) as e:
            result.update(status="SOURCE_NOT_VERIFIED",error_type=type(e).__name__,
                          http_status=getattr(e,"code",None))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"rows":result.get("raw_rows"),
        "header":result.get("header_fields"),
        "curve_ids":result.get("curve_id_counts"),"value_types":result.get("value_type_counts"),
        "source":result["official_download_url"]},ensure_ascii=False))

if __name__=="__main__":main()
